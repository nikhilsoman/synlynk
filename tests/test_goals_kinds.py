import pytest
import sqlite3
import tempfile
import os
from pathlib import Path
from synlynk import _get_db
from synlynk.db import cmd_goal_create, cmd_goal_list

def test_goals_schema_has_kind_column(tmp_path, monkeypatch):
    test_db = tmp_path / "state.db"
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(test_db))
    conn = _get_db(db_path=str(test_db))
    cols = [r[1] for r in conn.execute("PRAGMA table_info(goals)").fetchall()]
    assert "kind" in cols

def test_goals_migration_adds_kind_if_missing(tmp_path, monkeypatch):
    test_db = tmp_path / "legacy_state.db"
    conn = sqlite3.connect(str(test_db))
    conn.execute("""
        CREATE TABLE goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            goal_id TEXT NOT NULL UNIQUE,
            outcome TEXT NOT NULL,
            criterion TEXT NOT NULL,
            deadline TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("INSERT INTO goals (goal_id, outcome, criterion) VALUES ('goal-123', 'Old Outcome', 'Old Criterion')")
    conn.commit()
    conn.close()

    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(test_db))
    # Opening via _get_db should auto-migrate
    migrated_conn = _get_db(db_path=str(test_db))
    cols = [r[1] for r in migrated_conn.execute("PRAGMA table_info(goals)").fetchall()]
    assert "kind" in cols
    row = migrated_conn.execute("SELECT goal_id, kind FROM goals WHERE goal_id='goal-123'").fetchone()
    assert row[1] == "feature"
    migrated_conn.close()

def test_cmd_goal_create_supports_loop_kind(tmp_path, monkeypatch, capsys):
    test_db = tmp_path / "state.db"
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(test_db))
    goal_id = cmd_goal_create(
        outcome="Universal GOVERNS enforcement",
        criterion="Every prompt belongs to something above and triggers below",
        kind="loop"
    )
    assert goal_id.startswith("goal-")
    conn = _get_db(db_path=str(test_db))
    row = conn.execute("SELECT goal_id, outcome, kind FROM goals WHERE goal_id=?", (goal_id,)).fetchone()
    assert row[2] == "loop"
    conn.close()
