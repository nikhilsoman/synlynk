import os
import sqlite3
import pytest

from synlynk.lineage import (
    record_job_superseded,
    get_job_lineage,
    record_story_superseded,
    ensure_lineage_schema,
)
from synlynk.jobs import scan_zombie_running_jobs


def _setup_db(tmp_path):
    db_path = str(tmp_path / "state.db")
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE daemon_jobs (
            job_id TEXT PRIMARY KEY,
            agent TEXT NOT NULL,
            task TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'queued',
            pid INTEGER,
            started_at TEXT,
            enqueued_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE stories (
            story_id TEXT PRIMARY KEY,
            title TEXT,
            status TEXT DEFAULT 'open'
        )
        """
    )
    conn.commit()
    conn.close()
    return db_path


def test_record_job_superseded_updates_schema_and_status(tmp_path):
    db_path = _setup_db(tmp_path)
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, status, pid, started_at, enqueued_at) "
        "VALUES ('job-1', 'codex', 'task 1', 'running', 999999, '2026-09-11T12:00:00Z', '2026-09-11T12:00:00Z')"
    )
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, status, pid, started_at, enqueued_at) "
        "VALUES ('job-2', 'codex', 'task 1 retry', 'running', 12345, '2026-09-11T12:05:00Z', '2026-09-11T12:05:00Z')"
    )
    conn.commit()
    conn.close()

    ok = record_job_superseded("job-1", "job-2", db_path=db_path)
    assert ok is True

    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT status, superseded_by FROM daemon_jobs WHERE job_id='job-1'").fetchone()
    conn.close()

    assert row[0] == "superseded"
    assert row[1] == "job-2"


def test_superseded_jobs_excluded_from_zombies(tmp_path):
    db_path = _setup_db(tmp_path)
    conn = sqlite3.connect(db_path)
    # job-1 has a dead pid, but is superseded by job-2
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, status, pid, started_at, enqueued_at) "
        "VALUES ('job-1', 'codex', 'stale task', 'running', 999999, '2026-09-11T10:00:00Z', '2026-09-11T10:00:00Z')"
    )
    # job-active has a dead pid and is NOT superseded
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, status, pid, started_at, enqueued_at) "
        "VALUES ('job-dead', 'codex', 'dead task', 'running', 999998, '2026-09-11T10:00:00Z', '2026-09-11T10:00:00Z')"
    )
    conn.commit()
    conn.close()

    record_job_superseded("job-1", "job-2", db_path=db_path)

    zombies = scan_zombie_running_jobs(db_path)
    zombie_ids = [z["job_id"] for z in zombies if z.get("action") == "reap"]

    assert "job-1" not in zombie_ids
    assert "job-dead" in zombie_ids


def test_get_job_lineage_traverses_chain(tmp_path):
    db_path = _setup_db(tmp_path)
    conn = sqlite3.connect(db_path)
    conn.execute("INSERT INTO daemon_jobs (job_id, agent, task, enqueued_at) VALUES ('j1', 'a', 't', 't1')")
    conn.execute("INSERT INTO daemon_jobs (job_id, agent, task, enqueued_at) VALUES ('j2', 'a', 't', 't2')")
    conn.execute("INSERT INTO daemon_jobs (job_id, agent, task, enqueued_at) VALUES ('j3', 'a', 't', 't3')")
    conn.commit()
    conn.close()

    record_job_superseded("j1", "j2", db_path=db_path)
    record_job_superseded("j2", "j3", db_path=db_path)

    lineage = get_job_lineage("j1", db_path=db_path)
    assert len(lineage) == 3
    assert lineage[0]["job_id"] == "j1"
    assert lineage[1]["job_id"] == "j2"
    assert lineage[2]["job_id"] == "j3"
