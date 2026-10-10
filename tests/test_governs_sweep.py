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
