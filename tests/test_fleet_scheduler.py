import os
import sqlite3
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture
def scheduler_db(monkeypatch, tmp_path):
    """Fresh state.db with schema + migrations applied, cwd set to a temp project."""
    from synlynk import _DB_SCHEMA
    from synlynk.db import _migrate_db

    project_dir = tmp_path / "proj"
    project_dir.mkdir()
    monkeypatch.chdir(project_dir)
    os.makedirs(".synlynk", exist_ok=True)
    db_path = ".synlynk/state.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(_DB_SCHEMA)
    _migrate_db(conn)
    conn.commit()
    conn.close()

    monkeypatch.setattr("synlynk._get_db", lambda: sqlite3.connect(db_path))
    yield db_path


def test_stories_table_has_priority_and_readiness_columns(scheduler_db):
    conn = sqlite3.connect(scheduler_db)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(stories)")}
    conn.close()
    assert "priority" in cols
    assert "readiness" in cols


def test_priority_defaults_to_5_and_readiness_defaults_to_draft(scheduler_db):
    conn = sqlite3.connect(scheduler_db)
    conn.execute(
        "INSERT INTO stories (story_id, title) VALUES ('story-t1', 'test story')"
    )
    conn.commit()
    row = conn.execute(
        "SELECT priority, readiness FROM stories WHERE story_id='story-t1'"
    ).fetchone()
    conn.close()
    assert row == (5, "draft")
