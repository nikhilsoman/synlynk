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
    assert resolve_container_image(None, {"container_image": "example-test/runner:stub"}) == (
        "example-test/runner:stub"
    )
    assert resolve_container_image(
        "example-test/override:1",
        {"container_image": "example-test/baseline:1"},
    ) == "example-test/override:1"


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
            "SSH_AUTH_SOCK": "/tmp/agent-sock",
            "GIT_AUTHOR_NAME": "Ada",
            "GIT_AUTHOR_EMAIL": "ada@example.com",
        },
        str(repo),
        "example-test/runner:stub",
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
    assert cmd[dash + 1] == "example-test/runner:stub"
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
        "example-test/runner:stub",
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
            "example-test/runner:stub",
            docker_bin="/usr/bin/docker",
        )


def test_docker_host_is_copied_to_the_client_only(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv("DOCKER_HOST", "unix:///Users/me/orbstack/run/docker.sock")
    cmd, client, _cwd = wrap(
        ["sh", "-c", "true"],
        {"HOME": "/Users/me"},
        str(repo),
        "example-test/runner:stub",
        docker_bin="/usr/bin/docker",
    )
    assert client["DOCKER_HOST"] == "unix:///Users/me/orbstack/run/docker.sock"
    assert not any(item.startswith("DOCKER_HOST=") for item in _env_flags(cmd))
