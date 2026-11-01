import pytest

from synlynk import _get_db
from synlynk.governs_cli import cmd_governs_audit


def test_governs_audit_reports_unplaced_goals_without_mutating():
    conn = _get_db()
    conn.execute(
        "INSERT INTO goals (goal_id, outcome, criterion, placement_status, placement_reason) "
        "VALUES ('goal-audit', 'Audit', 'Audit', 'unplaced', 'speculative')"
    )
    conn.commit()
    before = conn.execute("SELECT COUNT(*) FROM goals").fetchone()[0]
    result = cmd_governs_audit(conn=conn)
    after = conn.execute("SELECT COUNT(*) FROM goals").fetchone()[0]
    conn.close()
    assert result["unplaced_goals"] == 1
    assert result["passed"] is True
    assert result["missing_placement_reasons"] == 0
    assert before == after


def test_governs_audit_strict_allows_explicitly_reasoned_unplaced_goal():
    conn = _get_db()
    conn.execute(
        "INSERT INTO goals (goal_id, outcome, criterion, placement_status, placement_reason) "
        "VALUES ('goal-audit-strict', 'Audit', 'Audit', 'unplaced', 'speculative')"
    )
    conn.commit()
    assert cmd_governs_audit(conn=conn, strict=True)["passed"] is True
    conn.close()
