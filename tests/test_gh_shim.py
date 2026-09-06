import os
import stat
import subprocess
import sys


def _fake_gh(tmp_path):
    path = tmp_path / "gh"
    path.write_text("#!/bin/sh\nprintf 'gh-ran:%s' \"$GH_TOKEN\"\n")
    path.chmod(stat.S_IRWXU)
    return path


def _run_shim(tmp_path, env):
    shim = tmp_path / "shim"
    shim.mkdir(exist_ok=True)
    shim_path = shim / "gh"
    shim_path.write_text(
        f"#!{sys.executable}\n"
        "from synlynk.gh_shim import main\n"
        "raise SystemExit(main(shim_dir=__import__('os').path.dirname(__file__)))\n"
    )
    shim_path.chmod(stat.S_IRWXU)
    return subprocess.run([str(shim_path), "--version"], env=env, text=True, capture_output=True)


def test_shim_non_harness_execs_real_gh(tmp_path):
    _fake_gh(tmp_path)
    env = {"PATH": str(tmp_path), "PYTHONPATH": os.getcwd()}
    result = _run_shim(tmp_path, env)
    assert result.returncode == 0
    assert result.stdout == "gh-ran:"


def test_shim_harness_without_token_refuses_real_gh(tmp_path):
    _fake_gh(tmp_path)
    env = {"PATH": str(tmp_path), "PYTHONPATH": os.getcwd(), "SYNLYNK_HARNESS": "1"}
    result = _run_shim(tmp_path, env)
    assert result.returncode == 1
    assert result.stdout == ""
    assert "synlynk gh --role <role> --" in result.stderr


def test_shim_harness_with_allow_host_execs_real_gh(tmp_path):
    _fake_gh(tmp_path)
    env = {
        "PATH": str(tmp_path),
        "PYTHONPATH": os.getcwd(),
        "SYNLYNK_HARNESS": "1",
        "SYNLYNK_GH_WRITE_ALLOW_HOST_AUTH": "1",
    }
    result = _run_shim(tmp_path, env)
    assert result.returncode == 0
    assert result.stdout == "gh-ran:"


def test_shim_harness_with_token_execs_real_gh(tmp_path):
    _fake_gh(tmp_path)
    env = {
        "PATH": str(tmp_path),
        "PYTHONPATH": os.getcwd(),
        "CLAUDECODE": "1",
        "GH_TOKEN": "app-token",
    }
    result = _run_shim(tmp_path, env)
    assert result.returncode == 0
    assert result.stdout == "gh-ran:app-token"


def test_shim_does_not_classify_ci_as_harness():
    from synlynk.gh_shim import _is_harness_session

    assert not _is_harness_session({"CI": "1", "GITHUB_ACTIONS": "true"})


def test_shim_routes_known_role_to_synlynk(monkeypatch):
    from synlynk import gh_shim

    calls = []

    def fake_exec(binary, args, env):
        calls.append((binary, args, env))
        raise RuntimeError("exec captured")

    monkeypatch.setattr(gh_shim.os, "execvpe", fake_exec)
    env = {"PATH": "/unused", "SYNLYNK_HARNESS": "1", "SYNLYNK_GH_ROLE": "qa"}
    try:
        gh_shim.run_shim(["pr", "view", "1"], env=env, shim_dir="/unused/shim")
    except RuntimeError as exc:
        assert str(exc) == "exec captured"
    assert calls[0][0] == sys.executable
    assert calls[0][1][-6:] == ["--role", "qa", "--", "pr", "view", "1"]


def test_gh_shim_cli_prints_installable_environment(tmp_path, monkeypatch, capsys):
    from synlynk import gh_shim

    monkeypatch.setenv("HOME", str(tmp_path))
    assert gh_shim.install_shim() == str(tmp_path / ".synlynk" / "gh-shim")
    assert (tmp_path / ".synlynk" / "gh-shim" / "gh").exists()
    assert gh_shim.shim_env() == f'export PATH="{tmp_path / ".synlynk" / "gh-shim"}:$PATH"'
