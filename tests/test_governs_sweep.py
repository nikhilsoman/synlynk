import sqlite3

from synlynk.db import _migrate_db


def _db(tmp_path):
    conn = sqlite3.connect(str(tmp_path / "state.db"))
    _migrate_db(conn)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS state_identity ("
        "product_id TEXT NOT NULL, mode TEXT NOT NULL DEFAULT 'repo', "
        "canonical_path TEXT NOT NULL DEFAULT ''"
        ")"
    )
    conn.execute("INSERT INTO state_identity(product_id) VALUES ('prod-test')")
    conn.commit()
    return conn


def test_sweep_is_audit_only_and_never_manufactures_goals(tmp_path):
    from synlynk.governs_cli import cmd_governs_sweep

    conn = _db(tmp_path)
    conn.execute(
        "INSERT INTO stories (story_id, title, goal_id, status) "
        "VALUES ('story-ghost', 'Generic Story', NULL, 'todo')"
    )
    conn.commit()

    stats = cmd_governs_sweep(conn=conn, dry_run=False, strict=True)

    assert stats["total_stories"] == 1
    assert stats["unresolved_count"] == 1
    assert stats["linked_updated"] == 0
    assert conn.execute("SELECT COUNT(*) FROM goals").fetchone()[0] == 0
    assert conn.execute(
        "SELECT link_status, skip_reason FROM goal_contributions WHERE story_id='story-ghost'"
    ).fetchone() == ("unresolved", "no scoped goal matched during audit sweep")


def test_sweep_reports_existing_scoped_coverage_without_relinking(tmp_path):
    from synlynk.governs_cli import cmd_governs_sweep

    conn = _db(tmp_path)
    conn.execute(
        "INSERT INTO goals (goal_id, outcome, criterion, product_id, status) "
        "VALUES ('goal-local', 'Local Goal', 'Criteria', 'prod-test', 'active')"
    )
    conn.execute(
        "INSERT INTO stories (story_id, title, goal_id, governs_stage, status) "
        "VALUES ('story-linked', 'Already linked', 'goal-local', 'open', 'done')"
    )
    conn.commit()

    stats = cmd_governs_sweep(conn=conn, dry_run=False, strict=True)

    assert stats["initially_linked"] == 1
    assert stats["linked_updated"] == 0
    assert conn.execute(
        "SELECT governs_stage FROM stories WHERE story_id='story-linked'"
    ).fetchone()[0] == "open"


def test_audit_reports_active_story_invariants(tmp_path):
    from synlynk.governs_cli import cmd_governs_audit

    conn = _db(tmp_path)
    conn.execute(
        "INSERT INTO stories (story_id, title, status, gh_issue) "
        "VALUES ('story-a', 'A', 'open', '42')"
    )
    conn.execute(
        "INSERT INTO stories (story_id, title, status, gh_issue) "
        "VALUES ('story-b', 'B', 'in_progress', '42')"
    )
    conn.commit()

    result = cmd_governs_audit(conn=conn)

    assert result["active_stories_without_goal"] == 2
    assert result["active_stories_without_phase"] == 2
    assert result["duplicate_active_issue_stories"] == 1
    assert result["passed"] is False


def test_audit_strict_fails_on_active_story_without_goal(tmp_path):
    import pytest
    from synlynk.governs_cli import cmd_governs_audit

    conn = _db(tmp_path)
    conn.execute(
        "INSERT INTO stories (story_id, title, status) VALUES ('story-ghost', 'Ghost', 'open')"
    )
    conn.commit()

    with pytest.raises(RuntimeError, match="active stories lack a goal"):
        cmd_governs_audit(conn=conn, strict=True)


def test_audit_normalizes_prefixed_issue_identity(tmp_path):
    from synlynk.governs_cli import cmd_governs_audit

    conn = _db(tmp_path)
    conn.execute(
        "INSERT INTO roadmap_arcs (version, title, status) VALUES ('v-test', 'Test', 'planned')"
    )
    conn.execute(
        "INSERT INTO roadmap_phases (arc_version, phase_title, status) VALUES ('v-test', 'Test phase', 'planned')"
    )
    conn.execute(
        "INSERT INTO goals (goal_id, outcome, criterion, product_id, phase_id, placement_status) "
        "VALUES ('goal-local', 'Local Goal', 'Criteria', 'prod-test', 1, 'placed')"
    )
    conn.execute(
        "INSERT INTO stories (story_id, title, status, gh_issue, goal_id) "
        "VALUES ('story-a', 'A', 'open', '42', 'goal-local')"
    )
    conn.execute(
        "INSERT INTO stories (story_id, title, status, gh_issue, goal_id) "
        "VALUES ('story-b', 'B', 'in_progress', '#42', 'goal-local')"
    )
    conn.commit()

    result = cmd_governs_audit(conn=conn)

    assert result["duplicate_active_issue_stories"] == 1
