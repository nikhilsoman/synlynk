"""Tests for synlynk.testbed.cli, QA charter binding, and policy verification."""
import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from synlynk.charters import TOOL_ROLE_SKILLS
from synlynk.policy import verify_testbed_receipt
from synlynk.testbed.cli import (
    generate_testbed_receipt,
    run_testbed_cli,
)
from synlynk.testbed.scenarios import ScenarioResult


def test_charter_testbed_skill_binding():
    assert "testbed" in TOOL_ROLE_SKILLS
    assert TOOL_ROLE_SKILLS["testbed"]["qa"] == "testbed-acceptance-runner"
    assert TOOL_ROLE_SKILLS["testbed"]["verifier"] == "testbed-acceptance-runner"
    assert TOOL_ROLE_SKILLS["testbed"]["architect"] == "testbed-topology-audit"


def test_generate_testbed_receipt():
    scenarios = [
        ScenarioResult(name="p2p_mesh", status="PASSED", duration_seconds=12.4),
        ScenarioResult(name="task_lease_recovery", status="PASSED", duration_seconds=18.1),
    ]
    receipt = generate_testbed_receipt(
        target_version="v1.1.0-dev (commit 284f810c)",
        driver_type="orbstack",
        scenarios=scenarios,
        attested_by="<@charlie, qa, claude>",
    )
    assert receipt["overall_verdict"] == "PASSED"
    assert receipt["target_version"] == "v1.1.0-dev (commit 284f810c)"
    assert len(receipt["scenarios_executed"]) == 2
    assert "signature" in receipt
    assert receipt["attested_by"] == "<@charlie, qa, claude>"


def test_policy_verify_testbed_receipt(tmp_path):
    receipts_dir = tmp_path / "project-docs" / "receipts"
    receipts_dir.mkdir(parents=True)

    receipt_file = receipts_dir / "testbed-receipt-284f810c.json"
    receipt_data = {
        "receipt_id": "rcpt-test-1",
        "target_version": "v1.1.0-dev (commit 284f810c)",
        "overall_verdict": "PASSED",
        "signature": "mock-ed25519-signature",
    }
    receipt_file.write_text(json.dumps(receipt_data))

    # Passing receipt
    assert verify_testbed_receipt(commit_sha="284f810c", receipts_dir=receipts_dir) is True

    # Missing receipt
    assert verify_testbed_receipt(commit_sha="unknown_sha", receipts_dir=receipts_dir) is False

    # Failed receipt
    fail_file = receipts_dir / "testbed-receipt-fail1234.json"
    fail_file.write_text(json.dumps({"overall_verdict": "FAILED"}))
    assert verify_testbed_receipt(commit_sha="fail1234", receipts_dir=receipts_dir) is False


def test_run_testbed_cli_status():
    mock_driver = MagicMock()
    mock_driver.list_nodes.return_value = []
    with patch("synlynk.testbed.cli.get_driver", return_value=mock_driver):
        res = run_testbed_cli(["status"])
        assert res == 0
