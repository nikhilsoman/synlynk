"""Opt-in WAL soak against the real state-db schema and migration path."""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import tempfile
import threading
import time
from pathlib import Path

import pytest

from synlynk.wal_ledger import WALConcurrencyError, write_transaction

pytestmark = pytest.mark.soak

OPS_PER_WORKER = 8
LOCK_RETRIES = 5
BACKOFF_SECONDS = 0.01


@pytest.fixture
def isolated_db_path():
    tmpdir = tempfile.mkdtemp(prefix="synlynk-soak-")
    db_path = os.path.join(tmpdir, "state.db")
    yield db_path
    shutil.rmtree(tmpdir, ignore_errors=True)


def _open_state_db(db_path: str) -> sqlite3.Connection:
    """Use the same schema/migration entrypoint as synlynk.db callers."""
    import synlynk

    return synlynk.open_state_db(mode="test", explicit_path=db_path)


def _init_schema(db_path: str, workers: int) -> dict[str, int]:
    conn = _open_state_db(db_path)
    try:
        for worker_id in range(workers):
            conn.execute(
                "INSERT OR IGNORE INTO stories (story_id, title) VALUES (?, ?)",
                (f"soak-story-{worker_id}", f"Soak story {worker_id}"),
            )
        conn.commit()
        return {
            table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("cost_entries", "capability_ratings", "daemon_jobs")
        }
    finally:
        conn.close()


def _is_lock_error(exc: BaseException) -> bool:
    message = str(exc).lower()
    return "locked" in message or "busy" in message


def _worker(db_path: str, worker_id: int, results: dict[int, dict]) -> None:
    conn = _open_state_db(db_path)
    successes = 0
    lock_failures = 0
    unrecoverable: list[str] = []
    latencies: list[float] = []
    try:
        for op_index in range(OPS_PER_WORKER):
            job_id = f"soak-{worker_id}-{op_index}"
            started = time.perf_counter()
            try:
                with write_transaction(
                    conn,
                    max_retries=LOCK_RETRIES,
                    initial_backoff=BACKOFF_SECONDS,
                    max_backoff=0.2,
                ):
                    now = time.strftime("%Y-%m-%dT%H:%M:%S")
                    conn.execute(
                        "INSERT INTO cost_entries "
                        "(session_date, harness, job_id, total_cost_usd, cost_source) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (now[:10], "soak-harness", job_id, 0.01, "estimated_manual"),
                    )
                    conn.execute(
                        "INSERT INTO capability_ratings "
                        "(story_id, agent, model_version, quality, signal_source) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (
                            f"soak-story-{worker_id}",
                            f"soak-agent-{worker_id}",
                            "soak",
                            1.0,
                            "soak",
                        ),
                    )
                    conn.execute(
                        "INSERT INTO daemon_jobs "
                        "(job_id, agent, harness, task, story_id, status, enqueued_at, "
                        "dispatch_context) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            job_id,
                            f"soak-agent-{worker_id}",
                            "soak-harness",
                            "SQLite WAL soak workload",
                            f"soak-story-{worker_id}",
                            "done",
                            now,
                            "soak",
                        ),
                    )
                    conn.execute(
                        "UPDATE daemon_jobs SET status = 'completed', completed_at = ? "
                        "WHERE job_id = ?",
                        (now, job_id),
                    )
                successes += 1
                latencies.append(time.perf_counter() - started)
            except (WALConcurrencyError, sqlite3.OperationalError) as exc:
                if _is_lock_error(exc) or isinstance(exc, WALConcurrencyError):
                    lock_failures += 1
                    unrecoverable.append(f"{job_id}: {exc}")
                else:
                    raise
    finally:
        conn.close()
    results[worker_id] = {
        "attempts": OPS_PER_WORKER,
        "successes": successes,
        "lock_failures": lock_failures,
        "unrecoverable": unrecoverable,
        "latencies": latencies,
    }


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = (len(ordered) - 1) * percentile / 100
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower)


@pytest.mark.parametrize("num_workers", [20, 50])
def test_concurrent_writers_no_corruption(isolated_db_path, num_workers):
    baseline = _init_schema(isolated_db_path, num_workers)
    results: dict[int, dict] = {}
    threads = [
        threading.Thread(target=_worker, args=(isolated_db_path, worker_id, results))
        for worker_id in range(num_workers)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    expected_writes = num_workers * OPS_PER_WORKER
    total_successes = sum(result["successes"] for result in results.values())
    total_lock_failures = sum(result["lock_failures"] for result in results.values())
    all_latencies = [
        latency
        for result in results.values()
        for latency in result["latencies"]
    ]
    unrecoverable = [
        error
        for result in results.values()
        for error in result["unrecoverable"]
    ]

    conn = _open_state_db(isolated_db_path)
    try:
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        counts = {
            table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("cost_entries", "capability_ratings", "daemon_jobs")
        }
    finally:
        conn.close()

    assert not unrecoverable, "unrecoverable SQLite lock errors: " + "; ".join(unrecoverable)
    assert total_successes == expected_writes
    assert counts == {
        table: baseline[table] + expected_writes
        for table in ("cost_entries", "capability_ratings", "daemon_jobs")
    }

    report = {
        "num_workers": num_workers,
        "ops_per_worker": OPS_PER_WORKER,
        "expected_writes": expected_writes,
        "successful_writes": total_successes,
        "total_lock_failures": total_lock_failures,
        "p95_latency_seconds": _percentile(all_latencies, 95),
        "row_counts": counts,
    }
    report_dir = Path(__file__).with_name("reports")
    report_dir.mkdir(exist_ok=True)
    report_path = report_dir / f"{int(time.time())}-soak-{num_workers}.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("SOAK_REPORT " + json.dumps(report, sort_keys=True))
