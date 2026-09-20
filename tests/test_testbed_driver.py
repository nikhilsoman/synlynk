"""Tests for synlynk.testbed.driver (OrbDriver and DockerDriver)."""
import subprocess
from unittest.mock import MagicMock, patch
import pytest

from synlynk.testbed.driver import (
    ExecResult,
    NodeHandle,
    OrbDriver,
    DockerDriver,
    TestbedDriver,
)


def test_node_handle_and_exec_result_dataclasses():
    handle = NodeHandle(
        node_id="test-node-1",
        ip="192.168.139.201",
        driver_type="orbstack",
        status="running",
    )
    assert handle.node_id == "test-node-1"
    assert handle.ip == "192.168.139.201"
    assert handle.driver_type == "orbstack"

    res = ExecResult(returncode=0, stdout="hello", stderr="", duration_seconds=0.12)
    assert res.returncode == 0
    assert res.stdout == "hello"
    assert res.ok is True

    err_res = ExecResult(returncode=1, stdout="", stderr="error", duration_seconds=0.05)
    assert err_res.ok is False


def test_orb_driver_create_node():
    driver = OrbDriver(orbctl_bin="orbctl")
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="Created\n", stderr=""), # orbctl create
            MagicMock(returncode=0, stdout="192.168.139.213\n", stderr=""), # ip fetch
        ]
        handle = driver.create_node(node_id="node-1", base_image="ubuntu:noble")
        assert handle.node_id == "node-1"
        assert handle.ip == "192.168.139.213"
        assert handle.driver_type == "orbstack"
        assert mock_run.call_count == 2
        mock_run.assert_any_call(
            ["orbctl", "create", "ubuntu:noble", "node-1"],
            capture_output=True,
            text=True,
            check=True,
        )


def test_orb_driver_exec_command():
    driver = OrbDriver(orbctl_bin="orbctl")
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="v1.0.0\n",
            stderr="",
        )
        res = driver.exec_command("node-1", "synlynk --version", env={"FOO": "BAR"})
        assert res.returncode == 0
        assert res.stdout == "v1.0.0\n"
        assert mock_run.called
        args, kwargs = mock_run.call_args
        assert args[0][0:3] == ["orbctl", "-m", "node-1"]


def test_orb_driver_fault_injection():
    driver = OrbDriver(orbctl_bin="orbctl")
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        # Test kill fault
        driver.inject_fault("node-1", "kill")
        mock_run.assert_called_with(
            ["orbctl", "stop", "-f", "node-1"],
            capture_output=True,
            text=True,
            check=True,
        )

        # Test partition fault
        driver.inject_fault("node-1", "partition")
        assert mock_run.called


def test_orb_driver_destroy_node():
    driver = OrbDriver(orbctl_bin="orbctl")
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        driver.destroy_node("node-1")
        mock_run.assert_called_with(
            ["orbctl", "delete", "-f", "node-1"],
            capture_output=True,
            text=True,
            check=True,
        )


def test_docker_driver_lifecycle():
    driver = DockerDriver(docker_bin="docker", network="synlynk-testbed")
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="synlynk-testbed\n", stderr=""), # network inspect/create
            MagicMock(returncode=0, stdout="container-sha-123\n", stderr=""), # docker run -d
            MagicMock(returncode=0, stdout="172.18.0.2\n", stderr=""), # docker inspect IP
        ]
        handle = driver.create_node(node_id="ci-node-1", base_image="ubuntu:noble")
        assert handle.node_id == "ci-node-1"
        assert handle.ip == "172.18.0.2"
        assert handle.driver_type == "docker"
