import concurrent.futures
import os
import sqlite3
import threading
import time

import pytest

import synlynk
from synlynk.lineage import (
    record_job_superseded,
    record_story_superseded,
    ensure_lineage_schema,
)


def test_sqlite_pragmas_configured(tmp_path):
    db_file = str(tmp_path / "test_pragmas.db")
    # Call internal _connect
    conn = synlynk._get_db(db_file)
    try:
        journal_mode = conn.execute("PRAGMA journal_mode").fetchone()[0].lower()
        busy_timeout = conn.execute("PRAGMA busy_timeout").fetchone()[0]
        synchronous = conn.execute("PRAGMA synchronous").fetchone()[0]

        assert journal_mode == "wal"
        assert busy_timeout == 30000
        assert synchronous == 1  # 1 corresponds to NORMAL
    finally:
        conn.close()


def test_concurrent_multi_thread_access(tmp_path):
    db_file = str(tmp_path / "concurrent.db")
    
    # Initialize DB
    init_conn = synlynk._get_db(db_file)
    init_conn.execute("CREATE TABLE counter (id INTEGER PRIMARY KEY, val INTEGER)")
    init_conn.execute("INSERT INTO counter (id, val) VALUES (1, 0)")
    init_conn.commit()
    init_conn.close()

    errors = []
    num_threads = 12
    iterations_per_thread = 20

    def worker(worker_id):
        try:
            for _ in range(iterations_per_thread):
                conn = synlynk._get_db(db_file)
                try:
                    conn.execute("UPDATE counter SET val = val + 1 WHERE id = 1")
                    conn.commit()
                finally:
                    conn.close()
                time.sleep(0.002)
        except Exception as e:
            errors.append((worker_id, str(e)))

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"Encountered database errors during concurrent access: {errors}"

    verify_conn = synlynk._get_db(db_file)
    total_val = verify_conn.execute("SELECT val FROM counter WHERE id = 1").fetchone()[0]
    verify_conn.close()
    assert total_val == num_threads * iterations_per_thread


def test_lineage_concurrent_writes(tmp_path):
    db_file = str(tmp_path / "lineage_concurrent.db")
    init_conn = sqlite3.connect(db_file)
    init_conn.execute("""
        CREATE TABLE daemon_jobs (
            job_id TEXT PRIMARY KEY,
            agent TEXT NOT NULL,
            task TEXT NOT NULL,
            story_id TEXT,
            status TEXT NOT NULL DEFAULT 'queued'
        )
    """)
    init_conn.execute("""
        CREATE TABLE stories (
            story_id TEXT PRIMARY KEY,
            title TEXT,
            status TEXT NOT NULL DEFAULT 'open'
        )
    """)
    init_conn.commit()
    init_conn.close()

    errors = []

    def writer(idx):
        try:
            job_a = f"job-{idx}-a"
            job_b = f"job-{idx}-b"
            conn = sqlite3.connect(db_file, timeout=30.0)
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA busy_timeout = 30000")
            conn.execute("INSERT INTO daemon_jobs (job_id, agent, task) VALUES (?, 'codex', 'test')", (job_a,))
            conn.execute("INSERT INTO daemon_jobs (job_id, agent, task) VALUES (?, 'codex', 'test')", (job_b,))
            conn.commit()
            conn.close()

            ok = record_job_superseded(job_a, job_b, db_path=db_file)
            assert ok is True
        except Exception as e:
            errors.append((idx, str(e)))

    threads = [threading.Thread(target=writer, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"Lineage concurrency errors: {errors}"
