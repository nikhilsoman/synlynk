import json
import sqlite3

import pytest


def _write_policy(tmp_path, overrides):
    policy_dir = tmp_path / ".synlynk"
    policy_dir.mkdir(parents=True, exist_ok=True)
    (policy_dir / "policy.json").write_text(json.dumps({"overrides": overrides}))


def test_gate_mode_defaults_to_enforce_when_key_absent(tmp_path, monkeypatch):
    from synlynk.policy_gates import gate_mode
    _write_policy(tmp_path, {"merge_authority": {"cross_harness_review_required": True}})
    monkeypatch.chdir(tmp_path)
    assert gate_mode("merge_authority", "cross_harness_review_required_mode") == "enforce"


def test_gate_mode_reads_observe_value(tmp_path, monkeypatch):
    from synlynk.policy_gates import gate_mode
    _write_policy(tmp_path, {"merge_authority": {"cross_harness_review_required": True, "cross_harness_review_required_mode": "observe"}})
    monkeypatch.chdir(tmp_path)
    assert gate_mode("merge_authority", "cross_harness_review_required_mode") == "observe"


def test_gate_mode_defaults_to_enforce_when_policy_file_missing(tmp_path, monkeypatch):
    from synlynk.policy_gates import gate_mode
    monkeypatch.chdir(tmp_path)
    assert gate_mode("governs_authority", "require_linked_goal_mode") == "enforce"


def test_gate_mode_reads_governs_authority_independently(tmp_path, monkeypatch):
    from synlynk.policy_gates import gate_mode
    _write_policy(tmp_path, {"governs_authority": {"require_linked_goal": True, "require_linked_goal_mode": "observe"}, "merge_authority": {"cross_harness_review_required": True}})
    monkeypatch.chdir(tmp_path)
    assert gate_mode("governs_authority", "require_linked_goal_mode") == "observe"
    assert gate_mode("merge_authority", "cross_harness_review_required_mode") == "enforce"


def test_classify_cross_harness_verdict_pass():
    from synlynk.policy_gates import classify_cross_harness_verdict
    verdict, detail = classify_cross_harness_verdict(True, "implementation codex / gpt-5.3-codex reviewed by claude / claude-sonnet-5")
    assert verdict == "pass"
    assert "reviewed by" in detail


def test_classify_cross_harness_verdict_warn_on_same_harness():
    from synlynk.policy_gates import classify_cross_harness_verdict
    verdict, detail = classify_cross_harness_verdict(False, "implementing and reviewing jobs use the same harness+model (codex / gpt-5.3-codex)")
    assert verdict == "warn"


@pytest.mark.parametrize("detail", [
    "no implementing job provenance found for PR #2100",
    "no reviewing job provenance found for PR #2100",
    "ambiguous implementation job provenance for PR #2100",
    "incomplete harness/model provenance (implementing=job-1, reviewing=job-2)",
])
def test_classify_cross_harness_verdict_insufficient_data(detail):
    from synlynk.policy_gates import classify_cross_harness_verdict
    verdict, _ = classify_cross_harness_verdict(False, detail)
    assert verdict == "insufficient_data"


def test_classify_governs_violations_pass_on_empty_list():
    from synlynk.policy_gates import classify_governs_violations
    verdict, detail = classify_governs_violations([])
    assert verdict == "pass"
    assert detail == "no GOVERNS linkage violations"


def test_classify_governs_violations_warn_on_violations():
    from synlynk.policy_gates import classify_governs_violations
    verdict, detail = classify_governs_violations([{"job_id": "job-1", "story_id": None, "reason": "missing story_id"}])
    assert verdict == "warn"
    assert "job-1" in detail


def _db_with_events(tmp_path, rows):
    from synlynk.migrations.runner import run_pending_migrations
    conn = sqlite3.connect(tmp_path / "state.db")
    run_pending_migrations(conn)
    for pr_number, gate, verdict in rows:
        conn.execute(
            "INSERT INTO policy_gate_events (pr_number, gate, mode, verdict, detail, recorded_at) "
            "VALUES (?, ?, 'observe', ?, 'detail', '2026-10-07T00:00:00+00:00')",
            (pr_number, gate, verdict),
        )
    conn.commit()
    return conn


def test_record_gate_event_writes_row(tmp_path):
    from synlynk.policy_gates import record_gate_event
    conn = _db_with_events(tmp_path, [])
    record_gate_event(conn, pr_number=2100, gate="governs_authority", mode="observe", verdict="pass", detail="no violations")
    row = conn.execute("SELECT pr_number, gate, mode, verdict, detail FROM policy_gate_events").fetchone()
    assert row == (2100, "governs_authority", "observe", "pass", "no violations")


def test_record_gate_event_does_not_raise_on_write_failure(tmp_path):
    from synlynk.policy_gates import record_gate_event
    conn = sqlite3.connect(tmp_path / "state.db")
    record_gate_event(conn, pr_number=2100, gate="governs_authority", mode="observe", verdict="pass", detail="no violations")


def test_gate_streak_counts_consecutive_passes(tmp_path):
    from synlynk.policy_gates import gate_streak
    conn = _db_with_events(tmp_path, [(1, "governs_authority", "pass"), (2, "governs_authority", "pass"), (3, "governs_authority", "pass")])
    assert gate_streak(conn, "governs_authority") == 3


def test_gate_streak_resets_on_most_recent_warn(tmp_path):
    from synlynk.policy_gates import gate_streak
    conn = _db_with_events(tmp_path, [(1, "governs_authority", "pass"), (2, "governs_authority", "warn"), (3, "governs_authority", "pass"), (4, "governs_authority", "pass")])
    assert gate_streak(conn, "governs_authority") == 2


def test_gate_streak_resets_on_insufficient_data(tmp_path):
    from synlynk.policy_gates import gate_streak
    conn = _db_with_events(tmp_path, [(1, "cross_harness_review", "pass"), (2, "cross_harness_review", "insufficient_data")])
    assert gate_streak(conn, "cross_harness_review") == 0


def test_gate_streak_is_scoped_per_gate(tmp_path):
    from synlynk.policy_gates import gate_streak
    conn = _db_with_events(tmp_path, [(1, "governs_authority", "pass"), (1, "cross_harness_review", "warn"), (2, "governs_authority", "pass")])
    assert gate_streak(conn, "governs_authority") == 2
    assert gate_streak(conn, "cross_harness_review") == 0


def test_gate_streak_returns_none_when_no_events(tmp_path):
    from synlynk.migrations.runner import run_pending_migrations
    from synlynk.policy_gates import gate_streak
    conn = sqlite3.connect(tmp_path / "state.db")
    run_pending_migrations(conn)
    assert gate_streak(conn, "governs_authority") is None


def test_evaluate_gate_enforce_mode_blocks_on_warn(tmp_path, monkeypatch):
    from synlynk.policy_gates import _evaluate_gate
    _write_policy(tmp_path, {"governs_authority": {"require_linked_goal": True}})
    monkeypatch.chdir(tmp_path)
    conn = _db_with_events(tmp_path, [])
    result = _evaluate_gate(conn, pr_number=2100, gate="governs_authority", mode_key="require_linked_goal_mode", verdict=("warn", "job-1 missing story"))
    assert result.should_block is True
    assert result.verdict == "warn"


def test_evaluate_gate_observe_mode_does_not_block_on_warn(tmp_path, monkeypatch):
    from synlynk.policy_gates import _evaluate_gate
    _write_policy(tmp_path, {"governs_authority": {"require_linked_goal": True, "require_linked_goal_mode": "observe"}})
    monkeypatch.chdir(tmp_path)
    conn = _db_with_events(tmp_path, [])
    result = _evaluate_gate(conn, pr_number=2100, gate="governs_authority", mode_key="require_linked_goal_mode", verdict=("warn", "job-1 missing story"))
    assert result.should_block is False
    assert "[OBSERVE MODE" in result.message
    assert conn.execute("SELECT verdict, mode FROM policy_gate_events WHERE pr_number=2100").fetchone() == ("warn", "observe")


def test_evaluate_gate_pass_never_blocks_regardless_of_mode(tmp_path, monkeypatch):
    from synlynk.policy_gates import _evaluate_gate
    _write_policy(tmp_path, {"governs_authority": {"require_linked_goal": True}})
    monkeypatch.chdir(tmp_path)
    conn = _db_with_events(tmp_path, [])
    result = _evaluate_gate(conn, pr_number=2100, gate="governs_authority", mode_key="require_linked_goal_mode", verdict=("pass", "no violations"))
    assert result.should_block is False


def test_cmd_policy_gate_status_reports_streak_and_threshold(tmp_path, monkeypatch, capsys):
    from synlynk.policy_cli import cmd_policy_gate_status
    monkeypatch.chdir(tmp_path)
    conn = _db_with_events(tmp_path, [(1, "governs_authority", "pass"), (2, "governs_authority", "pass")])
    conn.close()
    monkeypatch.setattr("synlynk.policy_cli._get_db", lambda: sqlite3.connect(tmp_path / "state.db"))
    exit_code = cmd_policy_gate_status()
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "governs_authority" in out
    assert "streak: 2" in out
    assert "100" in out


def test_cmd_policy_gate_status_reports_no_data_for_unrecorded_gate(tmp_path, monkeypatch, capsys):
    from synlynk.migrations.runner import run_pending_migrations
    from synlynk.policy_cli import cmd_policy_gate_status
    monkeypatch.chdir(tmp_path)
    conn = sqlite3.connect(tmp_path / "state.db")
    run_pending_migrations(conn)
    conn.close()
    monkeypatch.setattr("synlynk.policy_cli._get_db", lambda: sqlite3.connect(tmp_path / "state.db"))
    exit_code = cmd_policy_gate_status()
    assert exit_code == 0
    assert "no data yet" in capsys.readouterr().out
