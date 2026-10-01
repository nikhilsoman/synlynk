import os
import subprocess
import sys
import venv

import pytest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.mark.e2e
def test_hermetic_wheel_build_and_sandbox_run(tmp_path):
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()

    build = subprocess.run(
        [sys.executable, "-m", "pip", "wheel", "--no-deps", "-w", str(dist_dir), ROOT],
        capture_output=True,
        text=True,
    )
    assert build.returncode == 0, build.stderr

    wheels = list(dist_dir.glob("synlynk-*.whl"))
    assert len(wheels) == 1, f"expected exactly one wheel, found {wheels}"
    wheel_path = wheels[0]

    sandbox_venv = tmp_path / "sandbox_env"
    venv.create(sandbox_venv, with_pip=True)

    if sys.platform == "win32":
        venv_pip = sandbox_venv / "Scripts" / "pip.exe"
        venv_synlynk = sandbox_venv / "Scripts" / "synlynk.exe"
    else:
        venv_pip = sandbox_venv / "bin" / "pip"
        venv_synlynk = sandbox_venv / "bin" / "synlynk"

    install = subprocess.run(
        [str(venv_pip), "install", str(wheel_path)],
        capture_output=True,
        text=True,
    )
    assert install.returncode == 0, install.stderr

    run = subprocess.run(
        [str(venv_synlynk), "--version"],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )
    assert run.returncode == 0, run.stderr
    assert "synlynk" in (run.stdout + run.stderr).lower()
