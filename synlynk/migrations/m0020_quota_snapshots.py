"""Migration 20: subscription-quota snapshots, separate from cost_entries."""
import sqlite3

from synlynk.migrations import Migration


def _up(conn: sqlite3.Connection) -> None:
    conn.execute(
        """CREATE TABLE IF NOT EXISTS quota_snapshots (
            id INTEGER PRIMARY KEY,
            harness TEXT NOT NULL,
            window TEXT NOT NULL,
            used_percent REAL NOT NULL,
            resets_at TEXT,
            captured_at TEXT NOT NULL,
            source TEXT NOT NULL,
            staleness_seconds INTEGER,
            job_id TEXT
        )"""
    )
    conn.execute(
        """CREATE INDEX IF NOT EXISTS idx_quota_snapshots_harness_window
           ON quota_snapshots(harness, window, captured_at, id)"""
    )


MIGRATION = Migration(version=20, name="quota_snapshots", up=_up)
