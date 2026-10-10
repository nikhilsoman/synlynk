# Containerized Dispatch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let `synlynk dispatch --container-image <ref>` run the existing `sh -c` harness command inside `docker run`, with the job worktree and its git directory mounted, and fail closed instead of falling back to the host.

**Architecture:** `synlynk/container_exec.py` builds the argv. `dispatch_agent` calls it immediately before the current `Popen(["sh", "-c", shell_cmd], ...)`. No image leaves that `Popen` unchanged. The runner image is a separate Debian image with `stub-harness` on `PATH`. `Dockerfile.sovereign` is not modified.

**Tech Stack:** Python 3 stdlib, Docker (CLI only; unit tests use a fake `docker`), pytest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-10-04-containerized-dispatch-design.md`

**Decision:** `dec-ff9a9005`, recorded in `project-docs/decisions/2026-10-04-containerized-dispatch-spec-review-20261.md`. Approve with required changes. Those changes are already in the spec: bridge networking is not egress isolation, and the parity test must prove the fake `docker` ran.

**Branch:** `feat/grok/containerized-dispatch`, worktree `.worktrees/feat-grok-containerized-dispatch`. Every commit trailer is `Co-Authored-By: Grok <noreply@x.ai>`. Do not commit on `main`.

---

## File map

| File | Responsibility |
|---|---|
| `synlynk/container_exec.py` | Image-token check, git mounts, env rewrite, `docker run` argv. |
| `synlynk/dispatch.py` | Call `wrap` at the spawn. Suppress host failover when an image is set. Record a dead client as `failed`. |
| `synlynk/cli.py` | `--container-image` on `synlynk dispatch`, passed through to `dispatch_agent`. |
| `tests/test_container_exec.py` | Spec §9 cases 1–5 and the image-token rule. No daemon. |
| `tests/test_dispatch_container.py` | Spec §9 cases 6–8 against `dispatch_agent`. |
| `tests/test_dispatch_pipeline_shim.py` | Signature still accepts every previous kwarg, plus `container_image`. |
| `docker/stub-harness` | The executable inside the runner image. |
| `docker/Dockerfile.runner` | `debian:bookworm-slim`, `git`, CA certificates, `stub-harness`. |
| `.github/workflows/sovereign-build.yml` | A second job that builds and smoke-tests the runner. No push. |

Do not edit `docker/Dockerfile.sovereign`, `docker/entrypoint.sh`, or any value in `HARNESS_CAPABILITY_BASELINES`. Do not add `container_image` to `DispatchRequest`. The adapter pipeline does not spawn the process. `skip_permissions` is already a `dispatch_agent` argument that is not on `DispatchRequest`; follow that pattern.

## Task 1: `container_exec` and the argv contract

**Files:**
- Create: `synlynk/container_exec.py`
- Test: `tests/test_container_exec.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_container_exec.py`:

```python
import os
import subprocess

import pytest

from synlynk.container_exec import (
    ContainerExecError,
    resolve_container_image,
    wrap,
)


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _init_repo(path):
    path.mkdir()
    _git(path, "init")
    _git(path, "config", "user.email", "test@example.com")
    _git(path, "config", "user.name", "Test")
    (path / "README").write_text("hello\n", encoding="utf-8")
    _git(path, "add", "README")
    _git(path, "commit", "-m", "init")
    return path


def _pairs(argv):
    return list(zip(argv, argv[1:]))


def _mounts(argv):
    return [dst for flag, dst in _pairs(argv) if flag == "-v"]


def _env_flags(argv):
    return [value for flag, value in _pairs(argv) if flag == "-e"]


def test_no_image_returns_the_host_spawn_unchanged():
    cmd = ["sh", "-c", "echo hi"]
    env = {"HOME": "/Users/me", "PATH": "/usr/bin"}
    wrapped, wrapped_env, cwd = wrap(cmd, env, "/tmp/work", None)
    assert wrapped == cmd
    assert wrapped_env == env
    assert cwd == "/tmp/work"
    assert wrapped_env is not env


def test_blank_image_is_rejected():
    with pytest.raises(ContainerExecError):
        resolve_container_image("   ", {})
    with pytest.raises(ContainerExecError):
        resolve_container_image("repo name:tag", {})
    assert resolve_container_image(None, {}) is None
    assert resolve_container_image(None, {"container_image": "example.test/runner:stub"}) == (
        "example.test/runner:stub"
    )
    assert resolve_container_image(
        "example.test/override:1",
        {"container_image": "example.test/baseline:1"},
    ) == "example.test/override:1"


def test_ordinary_repo_mounts_only_the_worktree(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.delenv("DOCKER_HOST", raising=False)
    cmd, client, cwd = wrap(
        ["sh", "-c", "true"],
        {
            "HOME": "/Users/me",
            "TMPDIR": "/var/folders/tmp",
            "PATH": "/Users/me/bin",
            "SHELL": "/bin/zsh",
            "SSH_AUTH_SOCK": "/tmp/agent.sock",
            "GIT_AUTHOR_NAME": "Ada",
            "GIT_AUTHOR_EMAIL": "ada@example.com",
        },
        str(repo),
        "example.test/runner:stub",
        docker_bin="/usr/local/bin/docker",
    )
    assert cmd[0] == "/usr/local/bin/docker"
    assert ("--network", "bridge") in _pairs(cmd)
    assert ("--network", "host") not in _pairs(cmd)
    assert "--privileged" not in cmd
    assert "--read-only" in cmd
    assert ("--cap-drop", "ALL") in _pairs(cmd)
    assert ("--security-opt", "no-new-privileges") in _pairs(cmd)
    assert ("--user", f"{os.getuid()}:{os.getgid()}") in _pairs(cmd)
    assert ("--tmpfs", "/tmp:rw,nosuid,nodev,mode=1777") in _pairs(cmd)
    assert ("-w", os.path.abspath(repo)) in _pairs(cmd)
    assert _mounts(cmd) == [f"{os.path.abspath(repo)}:{os.path.abspath(repo)}"]
    assert not any("docker.sock" in part for part in cmd)
    dash = cmd.index("--")
    assert cmd[dash + 1] == "example.test/runner:stub"
    assert cmd[dash + 2:] == ["sh", "-c", "true"]
    envs = _env_flags(cmd)
    assert "HOME=/tmp" in envs
    assert "TMPDIR=/tmp" in envs
    assert "GIT_AUTHOR_NAME=Ada" in envs
    assert "GIT_AUTHOR_EMAIL=ada@example.com" in envs
    assert not any(item.startswith("PATH=") for item in envs)
    assert not any(item.startswith("SHELL=") for item in envs)
    assert not any(item.startswith("SSH_AUTH_SOCK=") for item in envs)
    assert not any(item.startswith("DOCKER_HOST=") for item in envs)
    assert "DOCKER_HOST" not in client
    assert cwd == str(repo)


def test_linked_worktree_mounts_gitdir_and_commondir(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    worktree = tmp_path / "job"
    _git(repo, "worktree", "add", "-b", "job", str(worktree))
    cmd, _client, _cwd = wrap(
        ["sh", "-c", "true"],
        {"GIT_AUTHOR_NAME": "Ada"},
        str(worktree),
        "example.test/runner:stub",
        docker_bin="/usr/bin/docker",
    )
    mounts = _mounts(cmd)
    gitdir = subprocess.check_output(
        ["git", "rev-parse", "--git-dir"], cwd=worktree, text=True
    ).strip()
    common = subprocess.check_output(
        ["git", "rev-parse", "--git-common-dir"], cwd=worktree, text=True
    ).strip()
    assert f"{os.path.abspath(worktree)}:{os.path.abspath(worktree)}" in mounts
    assert f"{os.path.abspath(gitdir)}:{os.path.abspath(gitdir)}" in mounts
    assert f"{os.path.abspath(common)}:{os.path.abspath(common)}" in mounts
    assert os.path.abspath(gitdir) != os.path.abspath(worktree)
    assert os.path.abspath(common) != os.path.abspath(gitdir)


def test_broken_gitdir_raises_before_any_docker_argv(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    (repo / ".git").rename(repo / ".git.bak")
    (repo / ".git").write_text("gitdir: /no/such/gitdir\n", encoding="utf-8")
    with pytest.raises(ContainerExecError, match="does not exist"):
        wrap(
            ["sh", "-c", "true"],
            {},
            str(repo),
            "example.test/runner:stub",
            docker_bin="/usr/bin/docker",
        )


def test_docker_host_is_copied_to_the_client_only(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv("DOCKER_HOST", "unix:///Users/me/.orbstack/run/docker.sock")
    cmd, client, _cwd = wrap(
        ["sh", "-c", "true"],
        {"HOME": "/Users/me"},
        str(repo),
        "example.test/runner:stub",
        docker_bin="/usr/bin/docker",
    )
    assert client["DOCKER_HOST"] == "unix:///Users/me/.orbstack/run/docker.sock"
    assert not any(item.startswith("DOCKER_HOST=") for item in _env_flags(cmd))
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `python3 -m pytest tests/test_container_exec.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.container_exec'`.

- [ ] **Step 3: Write `synlynk/container_exec.py`**

```python
"""Build a docker run argv for one dispatch. No image means the host spawn."""

from __future__ import annotations

import os
import re


class ContainerExecError(RuntimeError):
    """The container spawn cannot be built. Callers must not fall back to the host."""


def resolve_container_image(explicit: str | None, baseline: dict | None) -> str | None:
    """The flag wins. Neither source means the host path. A blank token is an error."""
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
    """Absolute directories to bind at the same path. The worktree is always first."""
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
    """Environment of the docker client. The harness does not see this dict."""
    client = dict(env)
    docker_host = os.environ.get("DOCKER_HOST")
    if docker_host:
        client["DOCKER_HOST"] = docker_host
    return client


def wrap(cmd, env, cwd, image, *, docker_bin: str | None = None, uid: int | None = None, gid: int | None = None):
    """Return ``(argv, client_env, cwd)``.

    ``image is None`` returns a copy of the host spawn. A set image returns
    ``docker run`` whose command is ``cmd`` unchanged. ``--user`` is numeric,
    so the image does not need a matching ``/etc/passwd`` entry; files created
    on the bind mount are owned by that uid and gid on the host.
    """
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
```

- [ ] **Step 4: Re-run the tests**

Run: `python3 -m pytest tests/test_container_exec.py -v`

Expected: PASS, 6 tests.

- [ ] **Step 5: Commit**

```bash
git add synlynk/container_exec.py tests/test_container_exec.py
git commit -m "$(cat <<'EOF'
feat: build a docker run argv for opt-in dispatch

Co-Authored-By: Grok <noreply@x.ai>
EOF
)"
```

## Task 2: Spawn through `dispatch_agent` and fail closed

**Files:**
- Modify: `synlynk/dispatch.py` (`dispatch_agent` signature near line 2999, the recursive call near line 3894, the `Popen` near line 3866, the job dict near line 3930, the `dconn.commit()` near line 4086)
- Modify: `tests/test_dispatch_pipeline_shim.py`
- Test: `tests/test_dispatch_container.py`

- [ ] **Step 1: Write the failing dispatch tests**

Create `tests/test_dispatch_container.py`:

```python
import os
import stat
import subprocess
import textwrap

import pytest

import synlynk.dispatch as dispatch_mod
from synlynk.container_exec import ContainerExecError
from synlynk.costs import extract_tokens


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _repo(path):
    path.mkdir()
    _git(path, "init")
    _git(path, "config", "user.email", "test@example.com")
    _git(path, "config", "user.name", "Test")
    (path / "AGENTS.md").write_text("<!-- synlynk:start version=\"0.13.0\" tool=\"codex\" -->\n", encoding="utf-8")
    (path / "README").write_text("hello\n", encoding="utf-8")
    _git(path, "add", "AGENTS.md", "README")
    _git(path, "commit", "-m", "init")
    return path


def _write_fake_docker(path, log_path):
    path.write_text(
        textwrap.dedent(
            f"""\
            #!/usr/bin/env python3
            import os, sys
            args = sys.argv[1:]
            with open({str(log_path)!r}, "a", encoding="utf-8") as handle:
                handle.write("\\0".join(sys.argv) + "\\n")
            if os.environ.get("FAKE_DOCKER_EXIT"):
                sys.exit(int(os.environ["FAKE_DOCKER_EXIT"]))
            if "--" not in args:
                sys.exit(2)
            rest = args[args.index("--") + 2:]
            os.execvp(rest[0], rest)
            """
        ),
        encoding="utf-8",
    )
    path.chmod(path.stat().st_mode | stat.S_IEXEC)


def _write_stub(path):
    path.write_text(
        "#!/bin/sh\nprintf '%s\\n' 'Input tokens: 11' 'Output tokens: 7'\n"
        "exit \"${STUB_EXIT:-0}\"\n",
        encoding="utf-8",
    )
    path.chmod(path.stat().st_mode | stat.S_IEXEC)


def test_parity_requires_the_fake_docker_argv(tmp_path, monkeypatch):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log_path = tmp_path / "docker-argv.log"
    _write_fake_docker(bin_dir / "docker", log_path)
    _write_stub(bin_dir / "stub-harness")
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    repo = _repo(tmp_path / "repo")
    host_log = tmp_path / "host.log"
    container_log = tmp_path / "container.log"
    shell = (
        f"stub-harness > {host_log} 2>&1; echo $? > {host_log}.exit"
    )
    subprocess.run(["sh", "-c", shell], cwd=repo, check=True, env={**os.environ, "STUB_EXIT": "3"})
    from synlynk.container_exec import wrap

    docker_bin = str(bin_dir / "docker")
    argv, client, cwd = wrap(
        ["sh", "-c", f"stub-harness > {container_log} 2>&1; echo $? > {container_log}.exit"],
        {"HOME": "/Users/me", "PATH": "/hidden"},
        str(repo),
        "example.test/runner:stub",
        docker_bin=docker_bin,
    )
    completed = subprocess.run(argv, cwd=cwd, env={**client, "PATH": os.environ["PATH"], "STUB_EXIT": "3"}, check=False)
    assert completed.returncode == 0
    recorded = log_path.read_text(encoding="utf-8")
    assert "example.test/runner:stub" in recorded
    assert "\0sh\0-c\0" in recorded
    assert host_log.read_bytes() == container_log.read_bytes()
    assert (tmp_path / "host.log.exit").read_text(encoding="utf-8").strip() == "3"
    assert (tmp_path / "container.log.exit").read_text(encoding="utf-8").strip() == "3"
    host_tokens = extract_tokens(host_log.read_text(encoding="utf-8"))
    container_tokens = extract_tokens(container_log.read_text(encoding="utf-8"))
    assert (host_tokens.input_tokens, host_tokens.output_tokens, host_tokens.cache_read_tokens) == (11, 7, 0)
    assert (
        container_tokens.input_tokens,
        container_tokens.output_tokens,
        container_tokens.cache_read_tokens,
    ) == (11, 7, 0)


def test_missing_docker_raises_and_does_not_fail_over(tmp_path, monkeypatch):
    repo = _repo(tmp_path / "repo")
    monkeypatch.chdir(repo)
    calls = []
    monkeypatch.setattr(dispatch_mod, "_secondary_harness", lambda *args, **kwargs: calls.append(args) or "codex")
    real_which = dispatch_mod.shutil.which

    def which(name, *args, **kwargs):
        if name == "docker":
            return None
        return real_which(name, *args, **kwargs)

    monkeypatch.setattr(dispatch_mod.shutil, "which", which)
    monkeypatch.setattr(dispatch_mod, "_preflight_dispatch", lambda *a, **kw: {"passed": True, "sentinel": None, "reason": None})
    with pytest.raises(ContainerExecError, match="not on PATH"):
        dispatch_mod.dispatch_agent(
            "codex",
            "review the sandbox",
            skip_preflight=True,
            force_agent=True,
            context_mode="none",
            container_image="example.test/runner:stub",
        )
    assert calls == []


def test_dead_client_records_failure_without_failover(tmp_path, monkeypatch):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log_path = tmp_path / "docker-argv.log"
    _write_fake_docker(bin_dir / "docker", log_path)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("FAKE_DOCKER_EXIT", "3")
    repo = _repo(tmp_path / "repo")
    monkeypatch.chdir(repo)
    calls = []
    monkeypatch.setattr(dispatch_mod, "_secondary_harness", lambda *args, **kwargs: calls.append(args) or "agy")
    monkeypatch.setattr(dispatch_mod, "_preflight_dispatch", lambda *a, **kw: {"passed": True, "sentinel": None, "reason": None})
    job = dispatch_mod.dispatch_agent(
        "codex",
        "review the sandbox",
        skip_preflight=True,
        force_agent=True,
        context_mode="none",
        container_image="example.test/runner:stub",
    )
    assert calls == []
    assert job["status"] == "failed"
    assert job["exit_code"] == 3
    exit_file = job["log_file"] + ".exit"
    assert open(exit_file, encoding="utf-8").read().strip() == "3"
    recorded = log_path.read_text(encoding="utf-8")
    assert "example.test/runner:stub" in recorded
```

In `tests/test_dispatch_pipeline_shim.py`, add `"container_image"` to `existing_kwargs`. The assertion stays `issubset`: old callers still construct `dispatch_agent` without the new argument.

- [ ] **Step 2: Run the new tests and confirm they fail**

Run: `python3 -m pytest tests/test_dispatch_container.py tests/test_dispatch_pipeline_shim.py::test_dispatch_agent_still_accepts_all_existing_kwargs -v`

Expected: FAIL. `dispatch_agent()` has no `container_image` parameter, and the shim set is not a subset until that parameter exists.

- [ ] **Step 3: Thread the image through `dispatch_agent`**

Add the import next to the other `synlynk` imports at the top of `synlynk/dispatch.py`:

```python
from synlynk.container_exec import ContainerExecError, resolve_container_image, wrap as wrap_container
```

Add this parameter at the end of `dispatch_agent`, after `skip_permissions: bool = False`:

```python
                   container_image: str | None = None) -> dict:
```

On the recursive startup-failover `return dispatch_agent(...)` call, add `container_image=container_image`. That call is not taken when an image is set. Passing the argument keeps a later edit from dropping it.

Immediately before `proc = subprocess.Popen(["sh", "-c", shell_cmd], ...)`, replace that `Popen` with:

```python
    container_image = resolve_container_image(container_image, baselines)
    spawn_cmd = ["sh", "-c", shell_cmd]
    spawn_env = proc_env
    spawn_cwd = worktree_path
    stderr_target = subprocess.DEVNULL
    stderr_handle = None
    if container_image is not None:
        docker_bin = shutil.which("docker")
        if not docker_bin:
            raise ContainerExecError(
                "docker is not on PATH; refusing to fall back to a host subprocess"
            )
        spawn_cmd, spawn_env, spawn_cwd = wrap_container(
            spawn_cmd,
            proc_env,
            worktree_path,
            container_image,
            docker_bin=docker_bin,
        )
        stderr_handle = open(log_file, "a", encoding="utf-8")
        stderr_target = stderr_handle
    try:
        proc = subprocess.Popen(
            spawn_cmd,
            stdout=subprocess.DEVNULL,
            stderr=stderr_target,
            start_new_session=True,
            cwd=spawn_cwd,
            env=spawn_env,
        )
    except Exception:
        if local_slot_claimed:
            dconn.rollback()
        raise
    finally:
        if stderr_handle is not None:
            stderr_handle.close()
```

`baselines` is the dict already loaded for `agent` before the shell string is built. Do not call `resolve_container_image` a second time later.

Replace the startup-failover condition so an image skips it:

```python
    try:
        startup_exit = proc.poll()
    except (AttributeError, OSError):
        startup_exit = None
    container_failed = container_image is not None and startup_exit not in (None, 0)
    if container_failed:
        exit_path = log_file + ".exit"
        if not os.path.exists(exit_path):
            with open(exit_path, "w", encoding="utf-8") as exit_handle:
                exit_handle.write(f"{startup_exit}\n")
    elif _startup_failover and startup_exit not in (None, 0):
```

Leave the body of the `elif` exactly as it is today, including `_startup_failover=False` on the recursive call.

In the `job = { ... }` literal, `status` and `exit_code` become:

```python
        "status": "failed" if container_failed else "running",
        "exit_code": startup_exit if container_failed else None,
```

When `container_failed` is true, also set `"ended_at"` to `time.strftime("%Y-%m-%dT%H:%M:%S")` instead of `None`.

Immediately before the existing `dconn.commit()` that follows the `UPDATE` / `INSERT OR REPLACE` of `daemon_jobs`, add:

```python
            if container_failed:
                dconn.execute(
                    "UPDATE daemon_jobs SET status=?, exit_code=?, completed_at=? WHERE job_id=?",
                    ("failed", startup_exit, job["ended_at"], job_id),
                )
```

Do not pass `-d`. Do not open a second execution path. `synlynk exec` stays untouched.

- [ ] **Step 4: Re-run the tests**

Run: `python3 -m pytest tests/test_container_exec.py tests/test_dispatch_container.py tests/test_dispatch_pipeline_shim.py::test_dispatch_agent_still_accepts_all_existing_kwargs -v`

Expected: PASS. If `test_dead_client_records_failure_without_failover` fails because `prepare_worktree` refuses the temp repo, keep the git init from `_repo` and fix only the worktree helper call the traceback names. Do not skip the test. The assertion that matters is: fake `docker` ran, the job is `failed` with exit `3`, and `_secondary_harness` was not called.

- [ ] **Step 5: Commit**

```bash
git add synlynk/dispatch.py tests/test_dispatch_container.py tests/test_dispatch_pipeline_shim.py
git commit -m "$(cat <<'EOF'
feat: spawn an image-backed dispatch inside docker run

Co-Authored-By: Grok <noreply@x.ai>
EOF
)"
```

## Task 3: CLI flag and the shipped baselines

**Files:**
- Modify: `synlynk/cli.py` (dispatch parser after `--dangerously-skip-permissions`, and the `dispatch_agent(...)` call near line 2311)
- Test: `tests/test_dispatch_container.py` (append the two tests below)

- [ ] **Step 1: Write the failing CLI tests**

Append to `tests/test_dispatch_container.py`:

```python
def test_dispatch_flag_overrides_baseline_and_defaults_to_host():
    from synlynk.container_exec import resolve_container_image
    from synlynk._constants import HARNESS_CAPABILITY_BASELINES

    assert resolve_container_image(None, {}) is None
    assert resolve_container_image("example.test/flag:1", {"container_image": "example.test/base:1"}) == (
        "example.test/flag:1"
    )
    for name, baseline in HARNESS_CAPABILITY_BASELINES.items():
        assert "container_image" not in baseline, name


def test_dispatch_parser_accepts_container_image_without_a_default():
    from synlynk.cli import build_parser

    parser = build_parser()
    named = parser.parse_args([
        "dispatch", "codex", "--task", "review",
        "--container-image", "example.test/runner:stub",
    ])
    assert named.container_image == "example.test/runner:stub"
    absent = parser.parse_args(["dispatch", "codex", "--task", "review"])
    assert absent.container_image is None
```

- [ ] **Step 2: Run the parser test and confirm it fails**

Run: `python3 -m pytest tests/test_dispatch_container.py::test_dispatch_parser_accepts_container_image_without_a_default -v`

Expected: FAIL because `container_image` is not an attribute (`argparse` exits with an unrecognized-arguments error, surfaced as `SystemExit`).

- [ ] **Step 3: Add the flag and pass it through**

After the `--dangerously-skip-permissions` `add_argument` block in `build_parser`:

```python
    dispatch_parser.add_argument(
        "--container-image",
        default=None,
        dest="container_image",
        help=(
            "Run this dispatch inside a container of this image. "
            "Absent means the host subprocess. There is no default image."
        ),
    )
```

In the `dispatch_agent(...)` call, add:

```python
                                 container_image=getattr(args, "container_image", None),
```

Do not set `container_image` on any harness in `synlynk/_constants.py`.

- [ ] **Step 4: Re-run the container tests**

Run: `python3 -m pytest tests/test_container_exec.py tests/test_dispatch_container.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add synlynk/cli.py tests/test_dispatch_container.py
git commit -m "$(cat <<'EOF'
feat: add synlynk dispatch --container-image

Co-Authored-By: Grok <noreply@x.ai>
EOF
)"
```

## Task 4: Runner image and the smoke job

**Files:**
- Create: `docker/stub-harness`
- Create: `docker/Dockerfile.runner`
- Modify: `.github/workflows/sovereign-build.yml`

- [ ] **Step 1: Add the stub and the Dockerfile**

`docker/stub-harness`:

```sh
#!/bin/sh
printf '%s\n' 'Input tokens: 11' 'Output tokens: 7'
if [ -w . ]; then
    printf 'ok\n' > stub-marker
fi
if [ -n "${STUB_EXIT:-}" ]; then
    exit "$STUB_EXIT"
fi
exit 0
```

`docker/Dockerfile.runner`:

```dockerfile
FROM debian:bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY docker/stub-harness /usr/local/bin/stub-harness
RUN chmod 755 /usr/local/bin/stub-harness

# Runtime identity is `docker run --user <host uid>:<host gid>`.
# The image intentionally has no matching account.
```

Do not copy the synlynk tree into this image. Do not change `Dockerfile.sovereign`.

- [ ] **Step 2: Add a non-publishing smoke job**

Append this job to `.github/workflows/sovereign-build.yml`. Leave the existing `build` job, its GHCR login, and its push step unchanged. The workflow already triggers on `docker/**`.

```yaml
  runner-smoke:
    runs-on: ubuntu-latest
    permissions:
      contents: read
    steps:
      - uses: actions/checkout@v4

      - name: Build runner image
        run: docker build -f docker/Dockerfile.runner -t synlynk-runner:test .

      - name: Run stub-harness against a mounted worktree
        run: |
          mkdir -p "$RUNNER_TEMP/work"
          docker run --rm -v "$RUNNER_TEMP/work:/work" -w /work synlynk-runner:test stub-harness
          test -f "$RUNNER_TEMP/work/stub-marker"
          set +e
          docker run --rm -e STUB_EXIT=3 synlynk-runner:test stub-harness >"$RUNNER_TEMP/stub.out"
          code=$?
          set -e
          test "$code" -eq 3
          grep -q "Input tokens: 11" "$RUNNER_TEMP/stub.out"
          grep -q "Output tokens: 7" "$RUNNER_TEMP/stub.out"
```

- [ ] **Step 3: Build and run the smoke locally if `docker` is available**

Run:

```bash
docker build -f docker/Dockerfile.runner -t synlynk-runner:test .
workdir=$(mktemp -d)
docker run --rm -v "$workdir:/work" -w /work synlynk-runner:test stub-harness
test -f "$workdir/stub-marker"
```

Expected: the build succeeds and `stub-marker` exists. If `docker` is not on `PATH` or the daemon is down, say so in the PR. Do not treat that as a unit-test failure. The unit tests do not build this image.

- [ ] **Step 4: Commit**

```bash
git add docker/stub-harness docker/Dockerfile.runner .github/workflows/sovereign-build.yml
git commit -m "$(cat <<'EOF'
feat: add the untrusted-harness runner image

Co-Authored-By: Grok <noreply@x.ai>
EOF
)"
```

## Task 5: Check the spec against the diff

- [ ] **Step 1: Run the container tests once more**

Run: `python3 -m pytest tests/test_container_exec.py tests/test_dispatch_container.py tests/test_dispatch_pipeline_shim.py::test_dispatch_agent_still_accepts_all_existing_kwargs -v`

Expected: PASS.

- [ ] **Step 2: Confirm the non-goals stayed out**

Run:

```bash
git diff origin/main -- docker/Dockerfile.sovereign docker/entrypoint.sh synlynk/_constants.py
```

Expected: no diff for the sovereign Dockerfile and entrypoint. `synlynk/_constants.py` has no new `container_image` key. `synlynk exec` has no new container branch.

- [ ] **Step 3: Do not open the PR from this plan**

The session that executes the plan opens the PR. The body says the containerization half of #1925 only, links the spec and `dec-ff9a9005`, and does not merge.

## Self-review

Spec §2 opt-in and the empty baseline: Task 3. Boundary argv, env rewrites, and git mounts: Task 1. Bridge is not described as an egress policy in the spec; this plan does not add `--network host` or an egress proxy. Spawn seam, missing `docker`, and dead-client failover: Task 2. CLI flag: Task 3. Runner image and smoke job: Task 4. `synlynk exec`, Podman, GHCR publish, and the harness plugin registry are absent on purpose.
