import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_install_sh_python_floor_check(tmp_path):
    """--check-prereqs exits 0 when a Python >= 3.10 is on PATH."""
    assert sys.version_info >= (3, 10)
    bindir = tmp_path / "bin"
    bindir.mkdir()
    python3 = shutil.which("python3")
    assert python3
    os.symlink(python3, bindir / "python3")
    # /usr/bin/python3 is 3.9 on current macOS; the floor check must see >= 3.10.
    env = {"PATH": f"{bindir}:/bin:/usr/bin", "HOME": str(tmp_path)}
    res = subprocess.run(
        ["/bin/sh", str(ROOT / "install.sh"), "--check-prereqs"],
        env=env,
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, res.stderr
