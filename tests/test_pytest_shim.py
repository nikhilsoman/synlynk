import os
import stat
import subprocess
import sys


def _fake_pytest(tmp_path):
    path = tmp_path / "pytest"
    path.write_text("#!/bin/sh\nprintf '%s\\n' \"$@\"\n")
    path.chmod(stat.S_IRWXU)
    return path


def _run_shim(tmp_path, args):
    shim_path = tmp_path / "shim" / "pytest"
    from synlynk.pytest_shim import write_shim

    write_shim(str(shim_path))
    env = {
        "PATH": f"{shim_path.parent}{os.pathsep}{tmp_path}",
        "PYTHONPATH": os.getcwd(),
        "SYNLYNK_ALLOW_CWD_FALLBACK": "1",
    }
    return subprocess.run([str(shim_path), *args], env=env, text=True, capture_output=True)


def test_shim_strips_verbosity_and_appends_quiet(tmp_path):
    _fake_pytest(tmp_path)

    result = _run_shim(tmp_path, ["tests/", "-v", "-m", "not local_hardware"])

    assert result.returncode == 0
    assert result.stdout.splitlines() == ["tests/", "-m", "not local_hardware", "-q"]


def test_shim_preserves_existing_quiet_flag(tmp_path):
    _fake_pytest(tmp_path)

    result = _run_shim(tmp_path, ["tests/foo_test.py", "-q"])

    assert result.returncode == 0
    assert result.stdout.splitlines() == ["tests/foo_test.py", "-q"]


def test_shim_removes_all_verbose_spellings(tmp_path):
    _fake_pytest(tmp_path)

    result = _run_shim(tmp_path, ["-vv", "tests/", "--verbose", "-vvv", "-v"])

    assert result.returncode == 0
    assert result.stdout.splitlines() == ["tests/", "-q"]


def test_pytest_shim_engages_under_login_shell(tmp_path):
    import shutil
    import pytest

    zsh = shutil.which("zsh")
    if not zsh:
        pytest.skip("zsh not installed")
    _fake_pytest(tmp_path)
    from synlynk.dispatch import _setup_shim_zdotdir
    from synlynk.pytest_shim import write_shim

    shim_dir = tmp_path / "shim"
    shim_dir.mkdir()
    shim_path = shim_dir / "pytest"
    write_shim(str(shim_path))
    zdot_dir = _setup_shim_zdotdir(str(shim_dir))

    env = {
        "PATH": f"{tmp_path}{os.pathsep}/usr/bin:/bin",
        "PYTHONPATH": os.getcwd(),
        "SYNLYNK_ALLOW_CWD_FALLBACK": "1",
        "SYNLYNK_SHIM_DIR": str(shim_dir),
        "ZDOTDIR": zdot_dir,
        "HOME": str(tmp_path / "home"),
    }
    (tmp_path / "home").mkdir()
    (tmp_path / "home" / ".zprofile").write_text(f'export PATH="{tmp_path}:$PATH"\n')

    res = subprocess.run(
        [zsh, "-lc", "pytest test.py -v"],
        env=env,
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0
    assert res.stdout.strip().splitlines() == ["test.py", "-q"]

