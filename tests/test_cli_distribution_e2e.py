"""End-to-end and diagnostic tests for CLI binary integrity, multi-user isolation, and PATH precedence.

Covers Hotfix v0.26.2 (gh:#2624):
1. Detecting broken CLI entrypoints (e.g. ModuleNotFoundError from orphaned editable installs).
2. Detecting cross-user UID ownership collisions on shared binaries.
3. Detecting PATH shadowing where shared/system locations shadow user-local installs.
4. Automated remediation via synlynk doctor --fix cli.
5. Multi-user UID namespacing for /tmp state.
6. Full wheel build & clean venv entrypoint execution.
"""

import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
import pytest

from synlynk._constants import VERSION
from synlynk.doctor import (
    _hc_cli_entrypoint_health,
    cmd_doctor,
    cmd_doctor_fix,
    HEALTH_CHECKS,
)
from synlynk.testbed.installer import build_local_wheel


def test_doctor_includes_cli_entrypoint_health():
    """_hc_cli_entrypoint_health must be registered in HEALTH_CHECKS."""
    assert _hc_cli_entrypoint_health in HEALTH_CHECKS


def test_doctor_detects_broken_cli_entrypoint(tmp_path, monkeypatch):
    """Reproduction of gh:#2624: broken script that crashes with ModuleNotFoundError."""
    broken_dir = tmp_path / "broken_bin"
    broken_dir.mkdir()
    broken_synlynk = broken_dir / "synlynk"
    # Write a script that mimics the broken Homebrew stub
    broken_synlynk.write_text(
        "#!/bin/sh\n"
        "echo \"Traceback (most recent call last):\" >&2\n"
        "echo \"  File \\\"/opt/homebrew/bin/synlynk\\\", line 3, in <module>\" >&2\n"
        "echo \"    from synlynk import main\" >&2\n"
        "echo \"ModuleNotFoundError: No module named 'synlynk'\" >&2\n"
        "exit 1\n"
    )
    broken_synlynk.chmod(0o755)

    monkeypatch.setenv("PATH", f"{broken_dir}:{os.environ.get('PATH', '')}")

    check = _hc_cli_entrypoint_health()
    assert check.name == "cli_entrypoint_health"
    assert check.status == "fail"
    assert "ModuleNotFoundError" in check.message or "failed" in check.message
    assert str(broken_synlynk) in check.message
    assert "reinstall" in check.fix.lower() or "pipx" in check.fix.lower() or "install.sh" in check.fix.lower()


def test_doctor_detects_missing_cli(monkeypatch):
    """If synlynk is not on PATH, doctor must fail with clear instructions."""
    monkeypatch.setenv("PATH", "")
    check = _hc_cli_entrypoint_health()
    assert check.name == "cli_entrypoint_health"
    assert check.status == "fail"
    assert "not found" in check.message.lower()


def test_doctor_detects_foreign_owned_binary(tmp_path, monkeypatch):
    """If the active binary is owned by a different UID, warn about cross-user collision."""
    bin_dir = tmp_path / "mock_bin"
    bin_dir.mkdir()
    mock_synlynk = bin_dir / "synlynk"
    mock_synlynk.write_text(f"#!/bin/sh\necho 'synlynk {VERSION}'\nexit 0\n")
    mock_synlynk.chmod(0o755)

    monkeypatch.setenv("PATH", f"{bin_dir}:{os.environ.get('PATH', '')}")

    current_uid = os.getuid() if hasattr(os, "getuid") else 1000
    foreign_uid = current_uid + 42

    orig_stat = os.stat

    def fake_stat(path, *args, **kwargs):
        st = orig_stat(path, *args, **kwargs)
        if str(path) == str(mock_synlynk):
            # Return a stat_result-like object with foreign st_uid
            class FakeStat:
                st_mode = st.st_mode
                st_uid = foreign_uid
                st_gid = st.st_gid
                st_size = st.st_size
                st_mtime = st.st_mtime
            return FakeStat()
        return st

    monkeypatch.setattr(os, "stat", fake_stat)

    check = _hc_cli_entrypoint_health()
    assert check.status in ("warn", "fail")
    assert str(foreign_uid) in check.message or "foreign" in check.message.lower() or "collision" in check.message.lower()


def test_doctor_detects_path_shadowing(tmp_path, monkeypatch):
    """Warn when an unisolated shared directory shadows an isolated user-local binary."""
    shared_dir = tmp_path / "opt" / "homebrew" / "bin"
    shared_dir.mkdir(parents=True)
    shared_synlynk = shared_dir / "synlynk"
    shared_synlynk.write_text(f"#!/bin/sh\necho 'synlynk {VERSION}'\nexit 0\n")
    shared_synlynk.chmod(0o755)

    user_dir = tmp_path / "home" / "user" / ".local" / "bin"
    user_dir.mkdir(parents=True)
    user_synlynk = user_dir / "synlynk"
    user_synlynk.write_text(f"#!/bin/sh\necho 'synlynk {VERSION}'\nexit 0\n")
    user_synlynk.chmod(0o755)

    # Shared directory precedes user-local directory in PATH
    monkeypatch.setenv("PATH", f"{shared_dir}:{user_dir}")
    monkeypatch.setenv("HOME", str(tmp_path / "home" / "user"))

    check = _hc_cli_entrypoint_health()
    assert check.status == "warn"
    assert "shadow" in check.message.lower()
    assert str(shared_synlynk) in check.message or str(shared_dir) in check.message
    assert "PATH" in check.fix


def test_doctor_fix_cli_remediation(tmp_path, monkeypatch, capsys):
    """cmd_doctor_fix('cli') inspects shell rc files and provides PATH remediation."""
    fake_home = tmp_path / "user"
    fake_home.mkdir()
    zshrc = fake_home / ".zshrc"
    zshrc.write_text("# existing zshrc\nexport FOO=1\n")

    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setenv("SHELL", "/bin/zsh")

    class Args:
        yes = True

    ret = cmd_doctor_fix("cli", args=Args())
    assert ret == 0
    updated = zshrc.read_text()
    assert ".local/bin" in updated
    assert 'export PATH="$HOME/.local/bin:$PATH"' in updated


def test_multi_user_tmp_isolation(tmp_path, monkeypatch):
    """User temp files must be isolated to /tmp/synlynk-{uid} with mode 0700."""
    from synlynk.runtime import get_user_tmp_dir

    uid = os.getuid() if hasattr(os, "getuid") else "default"
    tmp_dir = get_user_tmp_dir()
    assert str(uid) in str(tmp_dir)
    assert tmp_dir.exists()

    # Permissions check on posix
    if hasattr(os, "getuid"):
        mode = stat.S_IMODE(tmp_dir.stat().st_mode)
        assert mode == 0o700


@pytest.mark.e2e
def test_wheel_build_and_cli_endpoints_e2e(tmp_path):
    """Builds a real wheel, installs it in a clean venv, and exercises primary CLI endpoints."""
    workspace_root = Path(__file__).resolve().parent.parent
    wheel_dir = tmp_path / "wheel_dist"
    wheel_dir.mkdir()

    wheel_path = build_local_wheel(workspace_root, output_dir=wheel_dir)
    assert wheel_path.exists(), f"Wheel not built at {wheel_path}"

    venv_dir = tmp_path / "test_venv"
    subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)

    pip_exe = venv_dir / "bin" / "pip"
    synlynk_exe = venv_dir / "bin" / "synlynk"

    # Install the built wheel
    subprocess.run([str(pip_exe), "install", str(wheel_path)], check=True)
    assert synlynk_exe.exists(), f"Entrypoint {synlynk_exe} was not created"

    # 1. synlynk --version
    res_ver = subprocess.run([str(synlynk_exe), "--version"], capture_output=True, text=True)
    assert res_ver.returncode == 0
    assert VERSION in res_ver.stdout

    # 2. synlynk --help
    res_help = subprocess.run([str(synlynk_exe), "--help"], capture_output=True, text=True)
    assert res_help.returncode == 0
    assert "doctor" in res_help.stdout
    assert "init" in res_help.stdout

    # 3. synlynk init in a test repo
    test_repo = tmp_path / "sample_repo"
    test_repo.mkdir()
    subprocess.run(["git", "init"], cwd=test_repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=test_repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=test_repo, check=True)
    (test_repo / "README.md").write_text("# Test Repo\n")
    subprocess.run(["git", "add", "."], cwd=test_repo, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=test_repo, check=True)

    env = {
        **os.environ,
        "PATH": f"{venv_dir / 'bin'}:{os.environ.get('PATH', '')}",
        "VIRTUAL_ENV": str(venv_dir),
        "SYNLYNK_REGISTRY_PATH": str(tmp_path / "test-reg.json"),
        "SYNLYNK_STATE_DB_PATH": str(test_repo / "state.db"),
        "SYNLYNK_ALLOW_STATE_DB_FALLBACK": "1",
        "SYNLYNK_ALLOW_CWD_FALLBACK": "1",
    }
    res_init = subprocess.run(
        [str(synlynk_exe), "init", "--auto-defaults"],
        cwd=test_repo,
        capture_output=True,
        text=True,
        env=env,
    )
    assert res_init.returncode == 0

    # Initialize empty db for status
    subprocess.run([str(synlynk_exe), "migrate"], cwd=test_repo, capture_output=True, env=env)

    # 4. synlynk doctor
    res_doc = subprocess.run(
        [str(synlynk_exe), "doctor"],
        cwd=test_repo,
        capture_output=True,
        text=True,
        env=env,
    )
    assert "synlynk doctor" in res_doc.stdout
    assert "cli_entrypoint_health" in res_doc.stdout

    # 5. synlynk status
    res_status = subprocess.run(
        [str(synlynk_exe), "status"],
        cwd=test_repo,
        capture_output=True,
        text=True,
        env=env,
    )
    assert res_status.returncode == 0
    assert "SYNLYNK" in res_status.stdout

    # 6. synlynk upgrade --help
    res_up = subprocess.run([str(synlynk_exe), "upgrade", "--help"], capture_output=True, text=True)
    assert res_up.returncode == 0

    # 7. synlynk viz --help
    res_viz = subprocess.run([str(synlynk_exe), "viz", "--help"], capture_output=True, text=True)
    assert res_viz.returncode == 0
