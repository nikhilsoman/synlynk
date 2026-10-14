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
