import os
import shutil
import subprocess
from unittest.mock import MagicMock, patch
import pytest
from synlynk.testbed.driver import ExecResult, NodeHandle, OrbDriver
import json

from synlynk.testbed.scenarios import ScenarioRunner


def _enable_enforce_policy(project_dir, monkeypatch, mode="enforce"):
    import synlynk.db as db

    policy_path = project_dir / ".synlynk" / "policy.json"
    policy_path.parent.mkdir(parents=True, exist_ok=True)
    policy_path.write_text(json.dumps({
        "overrides": {
            "merge_authority": {
                "cross_harness_review_required": True,
                "cross_harness_review_required_mode": mode,
            }
        }
    }))
    monkeypatch.chdir(project_dir)
    monkeypatch.setattr(db, "_pr_closing_issue_numbers", lambda _pr: [])
    monkeypatch.setattr(db, "_pr_head_branch", lambda _pr: "feat/review-gate-matrix")


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


def test_review_gate_matrix_reproduces_solo_harness_gap(project_dir, monkeypatch):
    """Solo-harness and gateway identities reproduce the review-gate gap."""
    import synlynk

    _enable_enforce_policy(project_dir, monkeypatch)
    conn = synlynk._get_db()

    results = ScenarioRunner().run_review_gate_matrix(conn)

    by_name = {result.name: result for result in results}
    assert by_name["review_gate_matrix:alice"].status == "PASSED"
    assert by_name["review_gate_matrix:bob"].status == "PASSED"
    assert by_name["review_gate_matrix:charlie"].status == "PASSED"

    assert by_name["review_gate_matrix:dana"].status == "FAILED"
    assert "same harness+model" in by_name["review_gate_matrix:dana"].details
    assert by_name["review_gate_matrix:erin"].status == "FAILED"
    assert "same harness+model" in by_name["review_gate_matrix:erin"].details

    print(
        f"ci_headless verdict: {by_name['review_gate_matrix:ci-bot'].status} "
        f"-- {by_name['review_gate_matrix:ci-bot'].details}"
    )
    conn.close()


@pytest.mark.parametrize("mode,expected_should_block", [("observe", False), ("enforce", True)])
def test_cross_harness_gate_mode_blocks_only_in_enforce(
    project_dir, monkeypatch, mode, expected_should_block
):
    """The raw verdict fails; only enforce mode blocks on that verdict."""
    import synlynk
    import synlynk.db as db
    from synlynk.policy_gates import _evaluate_gate, classify_cross_harness_verdict
    from synlynk.testbed.identities import SOLO_AND_EDGE_IDENTITIES

    _enable_enforce_policy(project_dir, monkeypatch, mode=mode)
    conn = synlynk._get_db()
    solo_claude = SOLO_AND_EDGE_IDENTITIES["solo_claude"]
    pr_number = 9100
    conn.execute(
        "INSERT INTO cost_entries (session_date, agent, harness, model, cost_source, pr_number) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("2026-11-21", solo_claude.harness, solo_claude.harness, solo_claude.model, "test", pr_number),
    )
    conn.execute(
        "INSERT INTO cost_entries (session_date, agent, harness, model, cost_source, pr_number, agent_role) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("2026-11-21", solo_claude.harness, solo_claude.harness, solo_claude.model, "test", pr_number, "qa"),
    )
    conn.commit()

    ok, message = db._cross_harness_review_verdict(conn, pr_number)
    assert not ok

    evaluation = _evaluate_gate(
        conn,
        pr_number=pr_number,
        gate="cross_harness_review",
        mode_key="cross_harness_review_required_mode",
        policy_section="merge_authority",
        verdict=classify_cross_harness_verdict(ok, message),
    )

    assert evaluation.verdict == "warn"
    assert evaluation.should_block is expected_should_block
    conn.close()
