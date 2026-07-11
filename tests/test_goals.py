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
