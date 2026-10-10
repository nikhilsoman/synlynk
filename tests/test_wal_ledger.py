"""Tests for synlynk.wal_ledger: SQLite WAL enforcement and write transaction serializer."""

import os
import sqlite3
import threading
import time
import pytest

from synlynk.wal_ledger import (
    ensure_wal_pragmas,
    write_transaction,
    check_wal_health,
    WALConcurrencyError,
)


def test_ensure_wal_pragmas_applies_wal_mode_and_settings(tmp_path):
    db_path = tmp_path / "test_wal.db"
    conn = sqlite3.connect(str(db_path))
    try:
        res = ensure_wal_pragmas(conn)
        assert res["journal_mode"].lower() == "wal"
        assert res["synchronous"] == 1  # NORMAL
        assert res["busy_timeout"] >= 30000
        assert res["foreign_keys"] == 1

        # Verify directly via PRAGMA queries
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
        assert conn.execute("PRAGMA synchronous").fetchone()[0] == 1
        assert conn.execute("PRAGMA busy_timeout").fetchone()[0] >= 30000
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    finally:
        conn.close()


def test_ensure_wal_pragmas_handles_memory_database():
    conn = sqlite3.connect(":memory:")
    try:
        res = ensure_wal_pragmas(conn)
        assert res["journal_mode"].lower() in ("memory", "wal")
        assert res["busy_timeout"] >= 30000
    finally:
        conn.close()


def test_write_transaction_commits_on_success(tmp_path):
    db_path = tmp_path / "tx_test.db"
    conn = sqlite3.connect(str(db_path))
    ensure_wal_pragmas(conn)
    conn.execute("CREATE TABLE items (id TEXT PRIMARY KEY, val TEXT)")

    with write_transaction(conn):
        conn.execute("INSERT INTO items VALUES ('1', 'apple')")

    row = conn.execute("SELECT val FROM items WHERE id='1'").fetchone()
    assert row is not None
    assert row[0] == "apple"
    conn.close()


def test_write_transaction_rolls_back_on_error(tmp_path):
    db_path = tmp_path / "tx_rollback.db"
    conn = sqlite3.connect(str(db_path))
    ensure_wal_pragmas(conn)
    conn.execute("CREATE TABLE items (id TEXT PRIMARY KEY, val TEXT)")

    with pytest.raises(RuntimeError, match="fail"):
        with write_transaction(conn):
            conn.execute("INSERT INTO items VALUES ('1', 'apple')")
            raise RuntimeError("fail")

    row = conn.execute("SELECT val FROM items WHERE id='1'").fetchone()
    assert row is None
    conn.close()


class MockFlakyConn:
    def __init__(self, fail_count=2):
        self.fail_count = fail_count
        self.calls = 0
        self.committed = False
        self.rolled_back = False

    def execute(self, sql, *args):
        if sql.strip().upper() == "BEGIN IMMEDIATE":
            self.calls += 1
            if self.calls <= self.fail_count:
                raise sqlite3.OperationalError("database is locked")
            return None
        elif sql.strip().upper() == "COMMIT":
            self.committed = True
            return None
        elif sql.strip().upper() == "ROLLBACK":
            self.rolled_back = True
            return None
        return None


def test_write_transaction_retries_on_database_locked():
    mock_conn = MockFlakyConn(fail_count=2)
    with write_transaction(mock_conn, max_retries=5, initial_backoff=0.01):
        mock_conn.execute("INSERT INTO t VALUES (1)")

    assert mock_conn.calls == 3
    assert mock_conn.committed is True


def test_write_transaction_raises_when_retries_exhausted():
    mock_conn = MockFlakyConn(fail_count=10)
    with pytest.raises((sqlite3.OperationalError, WALConcurrencyError)):
        with write_transaction(mock_conn, max_retries=3, initial_backoff=0.01):
            pass

    assert mock_conn.calls == 3


def test_check_wal_health(tmp_path):
    db_path = tmp_path / "healthy.db"
    conn = sqlite3.connect(str(db_path))
    ensure_wal_pragmas(conn)
    conn.execute("CREATE TABLE t (x INT)")
    conn.close()

    health = check_wal_health(str(db_path))
    assert health["healthy"] is True
    assert health["journal_mode"].lower() == "wal"
    assert health["exists"] is True
