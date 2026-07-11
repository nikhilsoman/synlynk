import sqlite3

from synlynk import _get_db


def test_goals_table_created():
    conn = _get_db()
    cols = {row[1] for row in conn.execute("PRAGMA table_info(goals)")}
    assert cols == {"id", "goal_id", "outcome", "criterion", "deadline", "status", "created_at"}
    conn.close()


def test_goal_contributions_table_created():
    conn = _get_db()
    cols = {row[1] for row in conn.execute("PRAGMA table_info(goal_contributions)")}
    assert cols == {"id", "goal_id", "story_id"}
    conn.close()


def test_goal_id_columns_added_to_stories_and_roadmap_arcs():
    conn = _get_db()
    story_cols = {row[1]: row for row in conn.execute("PRAGMA table_info(stories)")}
    roadmap_cols = {row[1]: row for row in conn.execute("PRAGMA table_info(roadmap_arcs)")}

    assert "goal_id" in story_cols
    assert "goal_id" in roadmap_cols
    assert story_cols["goal_id"][3] == 0
    assert roadmap_cols["goal_id"][3] == 0

    story_fks = conn.execute("PRAGMA foreign_key_list(stories)").fetchall()
    roadmap_fks = conn.execute("PRAGMA foreign_key_list(roadmap_arcs)").fetchall()
    assert any(row[3] == "goal_id" and row[2] == "goals" and row[4] == "goal_id" for row in story_fks)
    assert any(row[3] == "goal_id" and row[2] == "goals" and row[4] == "goal_id" for row in roadmap_fks)
    conn.close()


def test_goal_create_returns_goal_id_and_persists():
    from synlynk.db import cmd_goal_create
    goal_id = cmd_goal_create(
        outcome="Ship agent role split to v0.10.0",
        criterion="synlynk dispatch routes 100% of implementation work to non-Claude agents",
        deadline="2026-09-01",
    )
    assert goal_id.startswith("goal-")
    conn = _get_db()
    row = conn.execute(
        "SELECT outcome, criterion, deadline, status FROM goals WHERE goal_id=?", (goal_id,)
    ).fetchone()
    conn.close()
    assert row == (
        "Ship agent role split to v0.10.0",
        "synlynk dispatch routes 100% of implementation work to non-Claude agents",
        "2026-09-01",
        "active",
    )


def test_goal_list_prints_active_goals(capsys):
    from synlynk.db import cmd_goal_create, cmd_goal_list
    cmd_goal_create(outcome="Outcome A", criterion="Criterion A")
    cmd_goal_list()
    captured = capsys.readouterr()
    assert "Outcome A" in captured.out
