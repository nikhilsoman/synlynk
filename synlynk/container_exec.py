"""Build a docker run argv for one dispatch. No image means the host spawn."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import time


class ContainerExecError(RuntimeError):
    """The container spawn cannot be built; callers must not fall back to the host."""


def resolve_container_image(explicit: str | None, baseline: dict | None) -> str | None:
    """Resolve the image, with an explicit value taking precedence over a baseline."""
    if explicit is not None:
        candidate = explicit
    else:
        candidate = (baseline or {}).get("container_image")
    if candidate is None:
        return None
    if not isinstance(candidate, str) or candidate == "" or any(ch.isspace() for ch in candidate):
        raise ContainerExecError(
            "container image ref must be a single non-empty token with no whitespace"
        )
    return candidate


def _inside(parent: str, child: str) -> bool:
    parent_real = os.path.realpath(parent)
    child_real = os.path.realpath(child)
    try:
        return os.path.commonpath([parent_real, child_real]) == parent_real
    except ValueError:
        return False


def git_mounts(worktree: str) -> list[str]:
    """Return absolute directories to bind at the same path, with the worktree first."""
    worktree_abs = os.path.abspath(worktree)
    git_path = os.path.join(worktree_abs, ".git")
    if os.path.isdir(git_path):
        return [worktree_abs]
    if not os.path.isfile(git_path):
        raise ContainerExecError(
            f"cannot resolve git dir for container mount: {git_path} is not a file or directory"
        )
    with open(git_path, encoding="utf-8") as handle:
        text = handle.read()
    match = re.search(r"^gitdir:\s*(.+)$", text, re.MULTILINE)
    if not match:
        raise ContainerExecError(f"cannot resolve git dir: {git_path} has no gitdir: line")
    raw = match.group(1).strip()
    gitdir = raw if os.path.isabs(raw) else os.path.normpath(os.path.join(worktree_abs, raw))
    if not os.path.isdir(gitdir):
        raise ContainerExecError(f"cannot resolve git dir: {gitdir} does not exist")
    mounts = [worktree_abs]
    if not _inside(worktree_abs, gitdir):
        mounts.append(os.path.abspath(gitdir))
    commondir_path = os.path.join(gitdir, "commondir")
    if os.path.isfile(commondir_path):
        with open(commondir_path, encoding="utf-8") as handle:
            raw_common = handle.read().strip()
        if not raw_common:
            raise ContainerExecError(f"cannot resolve common git dir: {commondir_path} is empty")
        common = (
            raw_common
            if os.path.isabs(raw_common)
            else os.path.normpath(os.path.join(gitdir, raw_common))
        )
        if not os.path.isdir(common):
            raise ContainerExecError(f"cannot resolve common git dir: {common} does not exist")
        if not _inside(worktree_abs, common) and os.path.abspath(common) not in mounts:
            mounts.append(os.path.abspath(common))
    return mounts


# PATH would hide the CLI installed in the image. SHELL and SSH_AUTH_SOCK point
# at host paths. DOCKER_HOST belongs to the client process, never to -e.
_DROP_FROM_HARNESS = {"PATH", "SHELL", "SSH_AUTH_SOCK", "DOCKER_HOST"}


def harness_env(env: dict) -> dict:
    rewritten = {key: value for key, value in env.items() if key not in _DROP_FROM_HARNESS}
    rewritten["HOME"] = "/tmp"
    rewritten["TMPDIR"] = "/tmp"
    return rewritten


def client_env(env: dict) -> dict:
    """Return the environment of the docker client; the harness does not see this dict."""
    client = dict(env)
    docker_host = os.environ.get("DOCKER_HOST")
    if docker_host:
        client["DOCKER_HOST"] = docker_host
    return client


def read_container_id(cidfile: str | None, *, attempts: int = 100, delay: float = 0.01) -> str:
    if not cidfile:
        return ""
    for _attempt in range(max(1, attempts)):
        try:
            with open(cidfile, encoding="utf-8") as handle:
                value = handle.read().strip()
            if value:
                return value
        except OSError:
            pass
        if delay:
            time.sleep(delay)
    return ""


def inspect_container(container_id: str) -> dict[str, str]:
    docker = shutil.which("docker")
    if not docker:
        return {"state": "error", "reason": "docker_unavailable"}
    completed = subprocess.run(
        [docker, "inspect", "--format", "{{.State.Running}}", container_id],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        combined = f"{completed.stdout}\n{completed.stderr}".lower()
        if "no such" in combined or "not found" in combined:
            return {"state": "stopped"}
        return {"state": "error", "reason": "docker_inspect_failed"}
    return {"state": "running" if completed.stdout.strip().lower() == "true" else "stopped"}


def stop_container(container_id: str, grace_seconds: float) -> None:
    docker = shutil.which("docker")
    if not docker:
        raise ContainerExecError("docker is not on PATH")
    timeout = str(max(0, int(grace_seconds)))
    completed = subprocess.run(
        [docker, "stop", "--time", timeout, container_id],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise ContainerExecError(completed.stderr.strip() or "docker stop failed")


def wrap(
    cmd,
    env,
    cwd,
    image,
    *,
    docker_bin: str | None = None,
    uid: int | None = None,
    gid: int | None = None,
    cidfile: str | None = None,
):
    """Return ``(argv, client_env, cwd)`` for a host or containerized spawn."""
    if image is None:
        return list(cmd), dict(env), cwd
    image = resolve_container_image(image, None)
    if not docker_bin:
        raise ContainerExecError("docker binary path is required when an image is set")
    if not cwd:
        raise ContainerExecError("container dispatch requires a job worktree")
    worktree = os.path.abspath(cwd)
    user_id = os.getuid() if uid is None else uid
    group_id = os.getgid() if gid is None else gid
    argv = [
        docker_bin,
        "run",
        "--rm",
        "--network",
        "bridge",
        "--read-only",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--user",
        f"{user_id}:{group_id}",
        "--tmpfs",
        "/tmp:rw,nosuid,nodev,mode=1777",
        "-w",
        worktree,
    ]
    if cidfile:
        argv.extend(["--cidfile", os.path.abspath(cidfile)])
    for mount in git_mounts(worktree):
        argv.extend(["-v", f"{mount}:{mount}"])
    for key, value in harness_env(env).items():
        argv.extend(["-e", f"{key}={value}"])
    argv.append("--")
    argv.append(image)
    argv.extend(list(cmd))
    return argv, client_env(env), cwd
