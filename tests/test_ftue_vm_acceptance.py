import os
import shutil
import subprocess
from unittest.mock import MagicMock, patch
import pytest
from synlynk.testbed.driver import ExecResult, NodeHandle, OrbDriver


def _is_orbctl_available():
    if not shutil.which("orbctl"):
        return False
    try:
        res = subprocess.run(["orbctl", "status"], capture_output=True, text=True, timeout=2.0)
        return res.returncode == 0 and "running" in res.stdout.lower()
    except Exception:
        return False


def test_orb_driver_provisioning_sequence():
    """Unit test verifying OrbDriver executes the full FTUE install and lifecycle ladder."""
    driver = OrbDriver(orbctl_bin="orbctl")

    with patch("subprocess.run") as mock_run:
        # Mock create
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="", stderr=""),  # orbctl create
            MagicMock(returncode=0, stdout="192.168.215.2\n", stderr=""),  # hostname -I
            MagicMock(returncode=0, stdout="", stderr=""),  # orbctl push
            MagicMock(returncode=0, stdout="synlynk 0.23.0-dev\n", stderr=""),  # pipx install & synlynk --version
            MagicMock(returncode=0, stdout="DRY RUN — no files will be written", stderr=""),  # init --dry-run
            MagicMock(returncode=0, stdout="All steps complete", stderr=""),  # init --yes
            MagicMock(returncode=0, stdout="", stderr=""),  # orbctl delete
        ]

        node = driver.create_node("synlynk-ftue-test", base_image="ubuntu:noble")
        assert node.node_id == "synlynk-ftue-test"
        assert node.ip == "192.168.215.2"

        driver.copy_file(node.node_id, "/tmp/synlynk.whl", "/tmp/synlynk.whl")

        res_ver = driver.exec_command(node.node_id, "pipx install /tmp/synlynk.whl && synlynk --version")
        assert res_ver.ok
        assert "0.23.0" in res_ver.stdout

        res_dry = driver.exec_command(node.node_id, "mkdir -p /tmp/fresh && cd /tmp/fresh && synlynk init --dry-run")
        assert res_dry.ok
        assert "DRY RUN" in res_dry.stdout

        res_init = driver.exec_command(node.node_id, "cd /tmp/fresh && synlynk init --yes")
        assert res_init.ok
        assert "complete" in res_init.stdout

        driver.destroy_node(node.node_id)
        assert mock_run.call_count == 7


@pytest.mark.skipif(not _is_orbctl_available(), reason="Live OrbStack daemon not running on host")
def test_live_orb_ftue_e2e(tmp_path):
    """End-to-end VM acceptance test on live OrbStack instance."""
    driver = OrbDriver()
    node_id = f"test-ftue-{int(os.getpid())}"
    node = driver.create_node(node_id, base_image="ubuntu:noble")
    try:
        # Verify node ip
        assert node.ip != "127.0.0.1"
        res = driver.exec_command(node_id, "uname -a")
        assert res.ok
        assert "Linux" in res.stdout
    finally:
        driver.destroy_node(node_id)
