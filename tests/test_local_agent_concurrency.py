"""Tests the local-agent concurrency guard in dispatch_agent(): max_concurrent
running 'local' jobs from .agents/local.json is enforced before spawning a new one."""
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from synlynk.dispatch import _local_concurrency_exceeded


def _db_with_running_jobs(count, agent="local"):
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE daemon_jobs (job_id TEXT, agent TEXT, status TEXT)"
    )
    for i in range(count):
        conn.execute(
            "INSERT INTO daemon_jobs (job_id, agent, status) VALUES (?, ?, 'running')",
            (f"job-{i}", agent),
        )
    conn.commit()
    return conn


class TestLocalConcurrencyGuard(unittest.TestCase):
    def test_not_exceeded_when_under_limit(self):
        conn = _db_with_running_jobs(0)
        self.assertFalse(_local_concurrency_exceeded(conn, max_concurrent=1))

    def test_exceeded_when_at_limit(self):
        conn = _db_with_running_jobs(1)
        self.assertTrue(_local_concurrency_exceeded(conn, max_concurrent=1))

    def test_other_agents_dont_count(self):
        conn = _db_with_running_jobs(3, agent="codex")
        self.assertFalse(_local_concurrency_exceeded(conn, max_concurrent=1))

    def test_invalid_limit_fails_safe_to_one(self):
        conn = _db_with_running_jobs(1)
        self.assertTrue(_local_concurrency_exceeded(conn, max_concurrent="bad"))


class TestSchedulerLocalConcurrency(unittest.TestCase):
    def test_scheduler_leaves_local_job_queued_at_capacity(self):
        from synlynk.jobs import _dispatch_ready_jobs

        db_file = tempfile.NamedTemporaryFile()
        conn = sqlite3.connect(db_file.name)
        conn.execute(
            "CREATE TABLE daemon_jobs ("
            "job_id TEXT PRIMARY KEY, agent TEXT, task TEXT, story_id TEXT, "
            "status TEXT, priority INTEGER, depends_on TEXT, enqueued_at TEXT, "
            "log_path TEXT)"
        )
        conn.execute(
            "INSERT INTO daemon_jobs "
            "(job_id, agent, task, status, priority, depends_on, enqueued_at) "
            "VALUES ('running-local', 'local', 'busy', 'running', 5, '[]', 'now')"
        )
        conn.execute(
            "INSERT INTO daemon_jobs "
            "(job_id, agent, task, status, priority, depends_on, enqueued_at) "
            "VALUES ('queued-local', 'local', 'wait', 'queued', 5, '[]', 'now')"
        )
        conn.commit()

        with patch("synlynk._get_db", return_value=conn), \
             patch("synlynk.dispatch_agent") as dispatch:
            self.assertEqual(_dispatch_ready_jobs(max_parallel=4), 0)
            self.assertFalse(dispatch.called)
        conn = sqlite3.connect(db_file.name)
        status = conn.execute(
            "SELECT status FROM daemon_jobs WHERE job_id='queued-local'"
        ).fetchone()[0]
        self.assertEqual(status, "queued")
        conn.close()
        db_file.close()


if __name__ == "__main__":
    unittest.main()
