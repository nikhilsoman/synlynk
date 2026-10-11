import os
import shutil
import sqlite3
import tempfile
import threading
import time
import json
import pytest

pytestmark = pytest.mark.soak


@pytest.fixture
def isolated_db_path():
    tmpdir = tempfile.mkdtemp(prefix="synlynk-soak-")
    db_path = os.path.join(tmpdir, "state.db")
    yield db_path
    shutil.rmtree(tmpdir, ignore_errors=True)


def _init_schema(db_path):
    conn = sqlite3.connect(db_path, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        "CREATE TABLE cost_entries (id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "job_id TEXT, harness TEXT, total_cost_usd REAL)"
    )
    conn.execute(
        "CREATE TABLE capability_ratings (id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "agent TEXT, story_id TEXT, quality REAL)"
    )
    conn.execute(
        "CREATE TABLE daemon_jobs (job_id TEXT PRIMARY KEY, status TEXT, updated_at REAL)"
    )
    conn.commit()
    conn.close()


def _worker(db_path, worker_id, duration_s, results):
    attempts = 0
    successes = 0
    lock_failures = 0
    latencies = []
    conn = sqlite3.connect(db_path, timeout=5)
    conn.execute("PRAGMA busy_timeout=5000")
    deadline = time.monotonic() + duration_s
    i = 0
    while time.monotonic() < deadline:
        attempts += 1
        start = time.monotonic()
        try:
            conn.execute(
                "INSERT INTO cost_entries (job_id, harness, total_cost_usd) VALUES (?, ?, ?)",
                (f"job-{worker_id}-{i}", "soak-harness", 0.01),
            )
            conn.execute(
                "INSERT INTO capability_ratings (agent, story_id, quality) VALUES (?, ?, ?)",
                (f"agent-{worker_id}", f"story-{worker_id}-{i}", 1.0),
            )
            conn.execute(
                "INSERT OR REPLACE INTO daemon_jobs (job_id, status, updated_at) VALUES (?, ?, ?)",
                (f"job-{worker_id}", "running", time.time()),
            )
            conn.commit()
            successes += 1
            latencies.append(time.monotonic() - start)
        except sqlite3.OperationalError:
            lock_failures += 1
            conn.rollback()
        i += 1
    conn.close()
    results[worker_id] = {
        "attempts": attempts,
        "successes": successes,
        "lock_failures": lock_failures,
        "latencies": latencies,
    }


@pytest.mark.parametrize("num_workers", [20, 50])
def test_concurrent_writers_no_corruption(isolated_db_path, num_workers):
    _init_schema(isolated_db_path)
    results = {}
    threads = [
        threading.Thread(target=_worker, args=(isolated_db_path, i, 10.0, results))
        for i in range(num_workers)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    conn = sqlite3.connect(isolated_db_path)
    integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
    assert integrity == "ok"

    total_attempts = sum(r["attempts"] for r in results.values())
    total_lock_failures = sum(r["lock_failures"] for r in results.values())
    failure_rate = total_lock_failures / total_attempts if total_attempts else 0
    assert failure_rate < 0.01, f"lock failure rate {failure_rate:.4f} exceeds 1% threshold"

    report = {
        "num_workers": num_workers,
        "total_attempts": total_attempts,
        "total_lock_failures": total_lock_failures,
        "failure_rate": failure_rate,
    }
    report_dir = os.path.join(os.path.dirname(__file__), "reports")
    os.makedirs(report_dir, exist_ok=True)
    report_path = os.path.join(report_dir, f"{int(time.time())}-soak-{num_workers}.json")
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    conn.close()
