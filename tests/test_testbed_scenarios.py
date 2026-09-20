"""Tests for synlynk.testbed.invariants and synlynk.testbed.scenarios."""
from unittest.mock import MagicMock
import pytest

from synlynk.testbed.driver import ExecResult, NodeHandle
from synlynk.testbed.invariants import InvariantAsserter, InvariantReport
from synlynk.testbed.scenarios import (
    ScenarioResult,
    ScenarioRunner,
)


def test_invariant_asserter_clean():
    mock_driver = MagicMock()
    # Mock SQLite query returning 0 active duplicate leases
    mock_driver.exec_command.return_value = ExecResult(returncode=0, stdout="0\n", stderr="")

    asserter = InvariantAsserter(driver=mock_driver)
    nodes = ["node-1", "node-2"]

    report = asserter.check_all(nodes)
    assert report.all_passed is True
    assert report.lease_mutual_exclusion is True
    assert report.zero_orphan_leases is True


def test_invariant_asserter_failure():
    mock_driver = MagicMock()
    # Mock SQLite query returning 2 duplicate active leases (violation)
    mock_driver.exec_command.return_value = ExecResult(returncode=0, stdout="2\n", stderr="")

    asserter = InvariantAsserter(driver=mock_driver)
    nodes = ["node-1", "node-2"]

    report = asserter.check_all(nodes)
    assert report.all_passed is False
    assert report.lease_mutual_exclusion is False


def test_scenario_runner_brownfield_init():
    mock_driver = MagicMock()
    mock_driver.exec_command.return_value = ExecResult(returncode=0, stdout="synlynk initialized\n", stderr="")

    node = NodeHandle(node_id="node-1", ip="192.168.139.213", driver_type="orbstack")
    runner = ScenarioRunner(driver=mock_driver)

    result = runner.run_brownfield_init(node)
    assert result.status == "PASSED"
    assert result.name == "brownfield_init"


def test_scenario_runner_p2p_mesh():
    mock_driver = MagicMock()
    def mock_exec(node_id, cmd, env=None):
        if "sqlite3" in cmd:
            return ExecResult(returncode=0, stdout="0\n", stderr="")
        return ExecResult(returncode=0, stdout="Event received\n", stderr="")

    mock_driver.exec_command.side_effect = mock_exec

    n1 = NodeHandle(node_id="node-1", ip="192.168.139.213", driver_type="orbstack")
    n2 = NodeHandle(node_id="node-2", ip="192.168.139.214", driver_type="orbstack")

    runner = ScenarioRunner(driver=mock_driver)
    result = runner.run_p2p_mesh(n1, n2)
    assert result.status == "PASSED"
    assert result.name == "p2p_mesh"


def test_scenario_runner_task_lease_recovery():
    mock_driver = MagicMock()
    def mock_exec(node_id, cmd, env=None):
        if "sqlite3" in cmd:
            return ExecResult(returncode=0, stdout="0\n", stderr="")
        return ExecResult(returncode=0, stdout="Reclaimed 1 lease\n", stderr="")

    mock_driver.exec_command.side_effect = mock_exec

    n1 = NodeHandle(node_id="node-1", ip="192.168.139.213", driver_type="orbstack")
    n2 = NodeHandle(node_id="node-2", ip="192.168.139.214", driver_type="orbstack")

    runner = ScenarioRunner(driver=mock_driver)
    result = runner.run_task_lease_recovery(n1, n2)
    assert result.status == "PASSED"
    assert result.name == "task_lease_recovery"
    mock_driver.inject_fault.assert_called_with("node-1", "kill")
