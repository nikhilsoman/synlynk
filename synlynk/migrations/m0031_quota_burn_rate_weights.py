"""Migration 31: per-harness/model quota burn-rate weights."""

import sqlite3

from synlynk.migrations import Migration


def _up(conn: sqlite3.Connection) -> None:
    conn.execute(
        """CREATE TABLE IF NOT EXISTS quota_burn_rate_weights (
            harness      TEXT NOT NULL,
            model        TEXT NOT NULL,
            multiplier   REAL NOT NULL DEFAULT 1.0,
            sample_count INTEGER NOT NULL DEFAULT 0,
            updated_at   TEXT DEFAULT (datetime('now')),
            PRIMARY KEY (harness, model)
        )"""
    )


MIGRATION = Migration(version=31, name="quota_burn_rate_weights", up=_up)
