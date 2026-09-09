"""Tests the local-agent concurrency guard in dispatch_agent(): max_concurrent
running 'local' jobs from .agents/local.json is enforced before spawning a new one."""
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch

import synlynk
from synlynk import dispatch as dispatch_module
from synlynk.dispatch import _defer_local_concurrency, _local_concurrency_exceeded


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

    def test_defer_propagates_persistence_errors(self):
        conn = sqlite3.connect(":memory:")
        with self.assertRaises(sqlite3.OperationalError):
            _defer_local_concurrency(
                conn, job_id="job-1", agent="local", task="wait", story_id=None,
                reason="local_concurrency",
            )


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

        def package_lookup(name, default=None):
            if name == "_get_db":
                return lambda: conn
            return default

        with patch("synlynk.jobs._pkg", side_effect=package_lookup):
            self.assertEqual(_dispatch_ready_jobs(max_parallel=4), 0)
        conn = sqlite3.connect(db_file.name)
        status = conn.execute(
            "SELECT status FROM daemon_jobs WHERE job_id='queued-local'"
        ).fetchone()[0]
        self.assertEqual(status, "queued")
        conn.close()
        db_file.close()

    def test_concurrent_direct_dispatch_claims_one_local_slot(self):
        db_file = tempfile.NamedTemporaryFile()
        setup = sqlite3.connect(db_file.name)
        setup.execute(
            "CREATE TABLE daemon_jobs ("
            "job_id TEXT PRIMARY KEY, agent TEXT, task TEXT, story_id TEXT, "
            "status TEXT, priority INTEGER, depends_on TEXT, enqueued_at TEXT, "
            "log_path TEXT, pid INTEGER, started_at TEXT, completed_at TEXT, "
            "dispatch_context TEXT, "
            "worktree_path TEXT, worktree_branch TEXT)"
        )
        setup.commit()
        setup.close()

        barrier = threading.Barrier(2)
        first_check = threading.local()
        real_exceeded = dispatch_module._local_concurrency_exceeded
        popen_calls = []
        results = []
        errors = []

        def synchronized_exceeded(conn, max_concurrent=1):
            exceeded = real_exceeded(conn, max_concurrent=max_concurrent)
            if not getattr(first_check, "done", False):
                first_check.done = True
                barrier.wait(timeout=5)
            return exceeded

        class FakeProcess:
            pid = 12345

            def poll(self):
                return None

        def fake_popen(*args, **kwargs):
            # subprocess.run() also uses the module-level Popen object. Count
            # only the detached process launch performed by dispatch_agent.
            if kwargs.get("start_new_session"):
                popen_calls.append(1)
            return FakeProcess()

        def dispatch_once(job_id):
            conn = sqlite3.connect(db_file.name, timeout=5)
            try:
                results.append(
                    dispatch_module.dispatch_agent(
                        "local",
                        "run a local task",
                        job_id=job_id,
                        db_conn=lambda conn=conn: conn,
                        context_mode="none",
                        skip_preflight=True,
                    )
                )
            except Exception as exc:  # surfaced by assertions below
                errors.append(exc)
            finally:
                conn.close()

        threads = [
            threading.Thread(target=dispatch_once, args=(job_id,))
            for job_id in ("direct-a", "direct-b")
        ]
        with patch.object(dispatch_module, "_local_max_concurrent", return_value=1), \
             patch.object(dispatch_module, "_local_concurrency_exceeded", side_effect=synchronized_exceeded), \
             patch("synlynk.local_agent_seed.seed_local_capability_envelope"), \
             patch.object(dispatch_module, "_create_job_worktree", return_value={
                 "path": db_file.name + ".worktree",
                 "base_branch": "main",
                 "base_sha": "deadbeef",
             }), \
             patch.object(dispatch_module.subprocess, "Popen", side_effect=fake_popen), \
             patch.object(synlynk, "load_config", return_value={}):
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=10)

        self.assertEqual(errors, [])
        self.assertEqual(len(popen_calls), 1)
        self.assertEqual(sum(bool(result.get("deferred")) for result in results), 1)
        conn = sqlite3.connect(db_file.name)
        statuses = dict(conn.execute("SELECT job_id, status FROM daemon_jobs"))
        conn.close()
        self.assertEqual(sorted(statuses.values()), ["queued", "running"])
        db_file.close()


if __name__ == "__main__":
    unittest.main()
