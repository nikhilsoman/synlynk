"""synlynk.wal_ledger: Single-Writer SQLite WAL Ledger enforcement and resilient write serializer.

Invariant 4: Guarantees that every SQLite connection to the state ledger
enforces WAL mode, busy timeout, and resilient write transactions with exponential backoff.
"""

from __future__ import annotations

import contextlib
import logging
import os
import random
import sqlite3
import time
from typing import Dict, Iterator, Optional, Any

logger = logging.getLogger("synlynk.wal_ledger")


class WALConcurrencyError(RuntimeError):
    """Raised when a write transaction fails to acquire a write lock after retries."""


def ensure_wal_pragmas(conn: sqlite3.Connection) -> Dict[str, Any]:
    """Configure and enforce standard high-concurrency WAL pragmas on an open SQLite connection.

    Pragmas applied:
      - PRAGMA journal_mode=WAL
      - PRAGMA synchronous=NORMAL
      - PRAGMA busy_timeout=30000 (30 seconds)
      - PRAGMA foreign_keys=ON

    Returns:
        dict containing the effective pragma values.
    """
    try:
        # Check if database is in-memory
        row = conn.execute("PRAGMA database_list").fetchone()
        db_file = row[2] if row and len(row) > 2 else ""

        # Apply pragmas
        conn.execute("PRAGMA busy_timeout=30000")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")

        if db_file and db_file != "":
            # Only set journal_mode=WAL on disk-backed databases
            conn.execute("PRAGMA journal_mode=WAL")

        journal_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        sync_mode = conn.execute("PRAGMA synchronous").fetchone()[0]
        timeout = conn.execute("PRAGMA busy_timeout").fetchone()[0]
        fkeys = conn.execute("PRAGMA foreign_keys").fetchone()[0]

        return {
            "journal_mode": str(journal_mode),
            "synchronous": int(sync_mode),
            "busy_timeout": int(timeout),
            "foreign_keys": int(fkeys),
        }
    except Exception as exc:
        logger.warning("Failed to enforce WAL pragmas on SQLite connection: %s", exc)
        return {
            "journal_mode": "unknown",
            "synchronous": 0,
            "busy_timeout": 0,
            "foreign_keys": 0,
            "error": str(exc),
        }


@contextlib.contextmanager
def write_transaction(
    conn: sqlite3.Connection,
    max_retries: int = 10,
    initial_backoff: float = 0.05,
    max_backoff: float = 1.0,
) -> Iterator[sqlite3.Connection]:
    """Context manager for executing serialized write transactions under WAL mode.

    Begins with `BEGIN IMMEDIATE` to acquire a write lock immediately without
    permitting deadlocks. If the database is locked by a concurrent process,
    retries with exponential backoff and jitter up to `max_retries`.

    Yields:
        The SQLite connection within an active transaction.
    """
    acquired = False
    for attempt in range(max_retries):
        try:
            conn.execute("BEGIN IMMEDIATE")
            acquired = True
            break
        except sqlite3.OperationalError as err:
            err_msg = str(err).lower()
            if ("locked" in err_msg or "busy" in err_msg) and attempt < max_retries - 1:
                delay = min(max_backoff, initial_backoff * (2 ** attempt))
                jitter = delay * (0.8 + 0.4 * random.random())
                time.sleep(jitter)
            else:
                raise WALConcurrencyError(
                    f"Failed to acquire SQLite write lock after {attempt + 1} attempts: {err}"
                ) from err

    if not acquired:
        raise WALConcurrencyError(
            f"Failed to acquire SQLite write lock after {max_retries} attempts"
        )

    try:
        yield conn
        conn.execute("COMMIT")
    except Exception:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        raise


def check_wal_health(db_path: str) -> Dict[str, Any]:
    """Check the health, existence, and WAL configuration of a SQLite database file."""
    if not os.path.exists(db_path):
        return {
            "healthy": False,
            "exists": False,
            "error": f"Database file not found at {db_path}",
        }

    try:
        conn = sqlite3.connect(f"file:{os.path.abspath(db_path)}?mode=ro", uri=True, timeout=5.0)
        try:
            journal_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
            sync_mode = conn.execute("PRAGMA synchronous").fetchone()[0]
            fkeys = conn.execute("PRAGMA foreign_keys").fetchone()[0]
            wal_exists = os.path.exists(f"{db_path}-wal")
            shm_exists = os.path.exists(f"{db_path}-shm")

            is_wal = str(journal_mode).lower() == "wal"
            return {
                "healthy": is_wal,
                "exists": True,
                "journal_mode": str(journal_mode),
                "synchronous": int(sync_mode),
                "foreign_keys": int(fkeys),
                "wal_file_present": wal_exists,
                "shm_file_present": shm_exists,
            }
        finally:
            conn.close()
    except Exception as exc:
        return {
            "healthy": False,
            "exists": True,
            "error": str(exc),
        }
