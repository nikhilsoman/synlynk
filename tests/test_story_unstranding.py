import os
import sqlite3
import time
from unittest.mock import patch

import pytest

from synlynk.jobs import reclaim_stranded_stories


@pytest.fixture
def test_db(tmp_path):
    db_path = tmp_path / "test_state.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE stories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            story_id TEXT NOT NULL UNIQUE,
            title TEXT,
            status TEXT NOT NULL DEFAULT 'open',
            readiness TEXT NOT NULL DEFAULT 'draft',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE daemon_jobs (
            job_id TEXT PRIMARY KEY,
            agent TEXT NOT NULL,
            task TEXT NOT NULL,
            story_id TEXT,
            status TEXT NOT NULL DEFAULT 'queued',
            pid INTEGER,
            started_at TEXT,
            completed_at TEXT,
            exit_code INTEGER
        )
    """)
    conn.commit()
    yield conn, str(db_path)
    conn.close()


def test_reclaim_stranded_stories_dry_run(test_db):
    conn, _ = test_db
    # Story 1: in_progress with dead PID (stranded)
    conn.execute("INSERT INTO stories (story_id, title, status, readiness) VALUES ('s1', 'Task 1', 'in_progress', 'in_progress')")
    conn.execute("INSERT INTO daemon_jobs (job_id, agent, task, story_id, status, pid, started_at) VALUES ('j1', 'codex', 't1', 's1', 'running', 99999999, '2026-09-11T00:00:00')")

    # Story 2: in_progress with active PID (not stranded)
    current_pid = os.getpid()
    conn.execute("INSERT INTO stories (story_id, title, status, readiness) VALUES ('s2', 'Task 2', 'in_progress', 'in_progress')")
    conn.execute("INSERT INTO daemon_jobs (job_id, agent, task, story_id, status, pid, started_at) VALUES ('j2', 'codex', 't2', 's2', 'running', ?, '2026-09-11T00:00:00')", (current_pid,))

    # Story 3: in_progress with NO job (stranded)
    conn.execute("INSERT INTO stories (story_id, title, status, readiness) VALUES ('s3', 'Task 3', 'in_progress', 'in_progress')")

    # Story 4: already ready (untouched)
    conn.execute("INSERT INTO stories (story_id, title, status, readiness) VALUES ('s4', 'Task 4', 'ready', 'ready')")
    conn.commit()

    with patch("synlynk.jobs._pid_is_alive", side_effect=lambda pid: pid == current_pid):
        stranded = reclaim_stranded_stories(conn=conn, dry_run=True)
        assert len(stranded) == 2
        stranded_ids = {s["story_id"] for s in stranded}
        assert stranded_ids == {"s1", "s3"}

        # Verify DB not changed in dry run
        row1 = conn.execute("SELECT status FROM stories WHERE story_id='s1'").fetchone()
        assert row1[0] == "in_progress"


def test_reclaim_stranded_stories_execution(test_db):
    conn, _ = test_db
    conn.execute("INSERT INTO stories (story_id, title, status, readiness) VALUES ('s1', 'Task 1', 'in_progress', 'in_progress')")
    conn.execute("INSERT INTO daemon_jobs (job_id, agent, task, story_id, status, pid, started_at) VALUES ('j1', 'codex', 't1', 's1', 'running', 99999999, '2026-09-11T00:00:00')")

    current_pid = os.getpid()
    conn.execute("INSERT INTO stories (story_id, title, status, readiness) VALUES ('s2', 'Task 2', 'in_progress', 'in_progress')")
    conn.execute("INSERT INTO daemon_jobs (job_id, agent, task, story_id, status, pid, started_at) VALUES ('j2', 'codex', 't2', 's2', 'running', ?, '2026-09-11T00:00:00')", (current_pid,))
    conn.commit()

    with patch("synlynk.jobs._pid_is_alive", side_effect=lambda pid: pid == current_pid):
        reclaimed = reclaim_stranded_stories(conn=conn, dry_run=False)
        assert len(reclaimed) == 1
        assert reclaimed[0]["story_id"] == "s1"

        # Verify s1 was updated to ready
        row1 = conn.execute("SELECT status, readiness FROM stories WHERE story_id='s1'").fetchone()
        assert row1[0] == "ready"
        assert row1[1] == "ready"

        # Verify s2 stayed in_progress
        row2 = conn.execute("SELECT status, readiness FROM stories WHERE story_id='s2'").fetchone()
        assert row2[0] == "in_progress"
        assert row2[1] == "in_progress"
