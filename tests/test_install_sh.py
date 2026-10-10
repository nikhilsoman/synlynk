import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_install_sh_check_prereqs_missing_python_exits_nonzero(tmp_path):
    fake_path = tmp_path / "bin"
    fake_path.mkdir()
    env = {"PATH": str(fake_path), "HOME": str(tmp_path)}
    result = subprocess.run(
        ["/bin/sh", str(ROOT / "install.sh"), "--check-prereqs"],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    output = result.stdout + result.stderr
    assert "python3 >= 3.10" in output
    assert not (tmp_path / ".synlynk").exists()
