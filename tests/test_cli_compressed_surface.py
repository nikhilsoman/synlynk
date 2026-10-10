"""Tests for CLI compressed surface projection (Invariant 5)."""

import pytest
from synlynk.governs_cli import cmd_governs
from synlynk.governs_compressed import compress_governs_stage, format_compressed_governs_summary
from synlynk.wal_ledger import ensure_wal_pragmas
from synlynk.worktree_lease import init_worktree_lease_schema
import sqlite3


@pytest.fixture
def mock_db(tmp_path):
    db_path = tmp_path / "state.db"
    conn = sqlite3.connect(str(db_path))
    ensure_wal_pragmas(conn)
    conn.execute("""
        CREATE TABLE stories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            story_id TEXT UNIQUE,
            title TEXT,
            goal_id TEXT,
            governs_stage TEXT,
            status TEXT
        )
    """)
    conn.execute("INSERT INTO stories (story_id, title, goal_id, governs_stage, status) VALUES ('s-1', 'Dream Spec', 'g-1', 'dream', 'open')")
    conn.execute("INSERT INTO stories (story_id, title, goal_id, governs_stage, status) VALUES ('s-2', 'Build Engine', 'g-1', 'work', 'open')")
    conn.execute("INSERT INTO stories (story_id, title, goal_id, governs_stage, status) VALUES ('s-3', 'Verify Tests', 'g-1', 'verify', 'open')")
    conn.commit()
    yield conn
    conn.close()


def test_cmd_governs_default_compressed(mock_db, capsys):
    cmd_governs(full=False, conn=mock_db)
    out = capsys.readouterr().out
    assert "Compressed 5-Stage View" in out
    assert "1. Plan" in out
    assert "2. Build" in out
    assert "3. Verify" in out
    assert "s-1" in out
    assert "s-2" in out
    assert "s-3" in out


def test_cmd_governs_full_flag(mock_db, capsys):
    cmd_governs(full=True, conn=mock_db)
    out = capsys.readouterr().out
    assert "Full 7-Stage FSM" in out
    assert "1. Dream" in out
    assert "3. Work" in out
