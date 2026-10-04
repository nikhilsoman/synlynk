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
    (path / "AGENTS.md").write_text(
        '<!-- synlynk:start version="0.13.0" tool="codex" -->\n', encoding="utf-8"
    )
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
    shell = f"stub-harness > {host_log} 2>&1; echo $? > {host_log}.exit"
    subprocess.run(["sh", "-c", shell], cwd=repo, check=True, env={**os.environ, "STUB_EXIT": "3"})
    from synlynk.container_exec import wrap

    docker_bin = str(bin_dir / "docker")
    argv, client, cwd = wrap(
        ["sh", "-c", f"stub-harness > {container_log} 2>&1; echo $? > {container_log}.exit"],
        {"HOME": "/Users/me", "PATH": "/hidden"},
        str(repo),
        "example-test/runner:stub",
        docker_bin=docker_bin,
    )
    completed = subprocess.run(argv, cwd=cwd, env={**client, "PATH": os.environ["PATH"], "STUB_EXIT": "3"}, check=False)
    assert completed.returncode == 0
    recorded = log_path.read_text(encoding="utf-8")
    assert "example-test/runner:stub" in recorded
    assert "\0sh\0-c\0" in recorded
    assert host_log.read_bytes() == container_log.read_bytes()
    assert (tmp_path / "host.log.exit").read_text(encoding="utf-8").strip() == "3"
    assert (tmp_path / "container.log.exit").read_text(encoding="utf-8").strip() == "3"
    host_tokens = extract_tokens(host_log.read_text(encoding="utf-8"))
    container_tokens = extract_tokens(container_log.read_text(encoding="utf-8"))
    assert (host_tokens.input_tokens, host_tokens.output_tokens, host_tokens.cache_read_tokens) == (11, 7, 0)
    assert (container_tokens.input_tokens, container_tokens.output_tokens, container_tokens.cache_read_tokens) == (11, 7, 0)


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
            "codex", "review the sandbox", skip_preflight=True, force_agent=True,
            context_mode="none", container_image="example-test/runner:stub",
        )
    assert calls == []


def test_dead_client_records_failure_without_failover(tmp_path, monkeypatch, git_worktree_repo):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log_path = tmp_path / "docker-argv.log"
    _write_fake_docker(bin_dir / "docker", log_path)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("FAKE_DOCKER_EXIT", "3")
    real_build_env = dispatch_mod._build_subprocess_env

    def build_env(*args, **kwargs):
        env = real_build_env(*args, **kwargs)
        env.update({"FAKE_DOCKER_EXIT": "3", "STUB_EXIT": "3"})
        return env

    monkeypatch.setattr(dispatch_mod, "_build_subprocess_env", build_env)
    repo = _repo(tmp_path / "repo")
    monkeypatch.chdir(repo)
    calls = []
    monkeypatch.setattr(dispatch_mod, "_secondary_harness", lambda *args, **kwargs: calls.append(args) or "agy")
    monkeypatch.setattr(dispatch_mod, "_preflight_dispatch", lambda *a, **kw: {"passed": True, "sentinel": None, "reason": None})
    job = dispatch_mod.dispatch_agent(
        "codex", "review the sandbox", skip_preflight=True, force_agent=True,
        context_mode="none", container_image="example-test/runner:stub",
    )
    assert calls == []
    assert job["status"] == "failed"
    assert job["exit_code"] == 3
    exit_file = job["log_file"] + ".exit"
    assert open(exit_file, encoding="utf-8").read().strip() == "3"
    recorded = log_path.read_text(encoding="utf-8")
    assert "example-test/runner:stub" in recorded


def test_dispatch_flag_overrides_baseline_and_defaults_to_host():
    from synlynk.container_exec import resolve_container_image
    from synlynk._constants import HARNESS_CAPABILITY_BASELINES

    assert resolve_container_image(None, {}) is None
    assert resolve_container_image("example-test/flag:1", {"container_image": "example-test/base:1"}) == (
        "example-test/flag:1"
    )
    for name, baseline in HARNESS_CAPABILITY_BASELINES.items():
        assert "container_image" not in baseline, name


def test_dispatch_parser_accepts_container_image_without_a_default():
    from synlynk.cli import build_parser

    parser = build_parser()
    named = parser.parse_args([
        "dispatch", "codex", "--task", "review",
        "--container-image", "example-test/runner:stub",
    ])
    assert named.container_image == "example-test/runner:stub"
    absent = parser.parse_args(["dispatch", "codex", "--task", "review"])
    assert absent.container_image is None
