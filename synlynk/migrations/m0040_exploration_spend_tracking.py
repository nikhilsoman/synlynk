"""Migration 40: per-harness spend accumulated by exploratory dispatches.

The routing policy can use this ledger to keep exploratory traffic visible and
bounded independently for each harness.  The migration only owns storage;
callers decide when an exploratory dispatch is recorded.
"""

import sqlite3

from synlynk.migrations import Migration


def _up(conn: sqlite3.Connection) -> None:
    conn.execute(
        """CREATE TABLE IF NOT EXISTS exploration_spend (
            harness         TEXT NOT NULL PRIMARY KEY,
            total_cost_usd  REAL NOT NULL DEFAULT 0.0,
            sample_count    INTEGER NOT NULL DEFAULT 0,
            updated_at      TEXT DEFAULT (datetime('now'))
        )"""
    )


MIGRATION = Migration(version=40, name="exploration_spend_tracking", up=_up)
