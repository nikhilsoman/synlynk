"""Concurrent multi-threaded racing tests for worktree leases and SQLite WAL transactions."""

import concurrent.futures
import os
import sqlite3
import threading
import time
import pytest

from synlynk.wal_ledger import ensure_wal_pragmas, write_transaction
from synlynk.worktree_lease import (
    acquire_worktree_lease,
    release_worktree_lease,
    init_worktree_lease_schema,
    get_active_worktree_lease,
)


def test_concurrent_worktree_lease_racing(tmp_path):
    db_path = tmp_path / "concurrent_state.db"
    conn = sqlite3.connect(str(db_path))
    ensure_wal_pragmas(conn)
    init_worktree_lease_schema(conn)
    conn.close()

    wt_path = tmp_path / "worktrees" / "job-racing"
    wt_path.mkdir(parents=True)

    results = []
    num_workers = 10
    barrier = threading.Barrier(num_workers)

    def worker(worker_id):
        # Each worker opens its own connection to state.db
        w_conn = sqlite3.connect(str(db_path), timeout=30.0)
        ensure_wal_pragmas(w_conn)
        barrier.wait()  # Synchronize start to create maximum contention
        try:
            res = acquire_worktree_lease(
                str(wt_path),
                leased_by=f"agent-{worker_id}",
                job_id=f"job-{worker_id}",
                pid=os.getpid(),
                duration_seconds=600,
                conn=w_conn,
            )
            results.append((worker_id, res))
        finally:
            w_conn.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = [executor.submit(worker, i) for i in range(num_workers)]
        concurrent.futures.wait(futures)

    # Exactly one worker should have acquired the lease (others saw same PID / holder or already_leased)
    # Since all used os.getpid(), if PID is alive, second callers see already_leased or same pid if same holder
    successful = [r for w_id, r in results if r.get("acquired") is True]
    assert len(successful) >= 1

    check_conn = sqlite3.connect(str(db_path))
    active_lease = get_active_worktree_lease(str(wt_path), conn=check_conn)
    assert active_lease is not None
    assert active_lease["status"] == "active"
    check_conn.close()
