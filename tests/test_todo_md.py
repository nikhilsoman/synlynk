"""Priority projection coverage for the generated task list (#2413)."""

from __future__ import annotations

import sqlite3


def _seed(conn: sqlite3.Connection, story_id: str, title: str, *, status: str = "ready",
          goal_id: str | None = None, created_at: str = "2026-10-19 00:00:00") -> None:
    conn.execute(
        "INSERT INTO stories (story_id, title, status, goal_id, created_at) VALUES (?, ?, ?, ?, ?)",
        (story_id, title, status, goal_id, created_at),
    )


def test_todo_prioritizes_active_roadmap_then_active_goals_and_collapses_legacy(
    tmp_path, monkeypatch
):
    import synlynk
    from synlynk.db import _generate_todo_md

    db_path = tmp_path / "state.db"
    docs = tmp_path / "project-docs"
    docs.mkdir()
    monkeypatch.setattr(synlynk, "DB_PATH", str(db_path))
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(db_path))
    monkeypatch.setenv("SYNLYNK_TEST_ISOLATED_DB", "1")
    monkeypatch.setenv("SYNLYNK_TEST_PROJECT_DIR", "1")
    monkeypatch.setattr(synlynk, "_is_migrated", lambda: False)
    monkeypatch.setattr(synlynk, "_docs_dir", lambda: str(docs))

    conn = synlynk._get_db()
    try:
        conn.execute("INSERT INTO roadmap_arcs (version, status) VALUES ('v1.0.0-preview', 'in_progress')")
        conn.execute(
            "INSERT INTO goals (goal_id, outcome, criterion) VALUES (?, ?, ?)",
            ("goal-eacab0dc", "Keep state aligned", "Roadmap reflects current sprint"),
        )
        _seed(conn, "story-sprint", "Sprint work")
        _seed(conn, "story-goal", "Goal work", goal_id="goal-eacab0dc")
        _seed(conn, "story-ordinary", "Ordinary work", status="draft")
        _seed(conn, "story-legacy", "Legacy work", created_at="2000-01-01 00:00:00")
        conn.execute(
            "INSERT INTO roadmap_phases (arc_version, phase_title, status, story_id) VALUES (?, ?, ?, ?)",
            ("v1.0.0-preview", "Current phase", "in_progress", "story-sprint"),
        )
        conn.commit()
    finally:
        conn.close()

    _generate_todo_md()
    content = (docs / "todo.md").read_text()
    assert content.index("Sprint work") < content.index("Goal work") < content.index("Ordinary work")
    assert "Legacy work" not in content
    assert "1 legacy story omitted" in content
