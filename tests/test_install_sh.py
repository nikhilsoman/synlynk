import os
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_install_sh_without_pipx_prints_guidance_and_exits_nonzero(tmp_path):
    fake_path = tmp_path / "bin"
    fake_path.mkdir()
    os.symlink(shutil.which("python3"), fake_path / "python3")
    env = os.environ.copy()
    env.update({"PATH": str(fake_path), "HOME": str(tmp_path)})
    result = subprocess.run(
        ["/bin/bash", str(ROOT / "install.sh")],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    output = result.stdout + result.stderr
    assert "https://pipx.pypa.io/stable/" in output
    assert "pipx install git+https://github.com/nikhilsoman/synlynk" in output
    assert not (tmp_path / ".synlynk").exists()
