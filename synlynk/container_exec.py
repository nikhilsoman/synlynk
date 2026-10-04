"""Build a docker run argv for one dispatch. No image means the host spawn."""

from __future__ import annotations

import os
import re


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


def wrap(
    cmd,
    env,
    cwd,
    image,
    *,
    docker_bin: str | None = None,
    uid: int | None = None,
    gid: int | None = None,
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
    for mount in git_mounts(worktree):
        argv.extend(["-v", f"{mount}:{mount}"])
    for key, value in harness_env(env).items():
        argv.extend(["-e", f"{key}={value}"])
    argv.append("--")
    argv.append(image)
    argv.extend(list(cmd))
    return argv, client_env(env), cwd
