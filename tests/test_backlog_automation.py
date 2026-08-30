import os
import sqlite3

import pytest


@pytest.fixture
def db_conn(tmp_path, monkeypatch):
    db_path = str(tmp_path / "state.db")
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", db_path)
    from synlynk import _get_db
    conn = _get_db()
    yield conn
    conn.close()


def test_backlog_proposals_table_exists(db_conn):
    cols = {row[1] for row in db_conn.execute("PRAGMA table_info(backlog_proposals)")}
    assert cols == {
        "id", "signal_hash", "title", "source", "status",
        "gh_issue_url", "story_id", "goal_id", "goal_match_basis",
        "session_id", "ts",
    }
