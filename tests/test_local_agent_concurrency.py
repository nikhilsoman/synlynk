"""Tests the local-agent concurrency guard in dispatch_agent(): max_concurrent
running 'local' jobs from .agents/local.json is enforced before spawning a new one."""
import sqlite3
import unittest

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


if __name__ == "__main__":
    unittest.main()
