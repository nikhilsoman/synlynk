"""Migration 36: requested_harness attribution on cost_entries/capability_ratings.

daemon_jobs already records requested_harness and actual_harness. Extend that
same attribution to the reporting tables so reroutes remain visible in cost
and capability-rating data.
"""
import sqlite3

from synlynk.migrations import Migration


def _up(conn: sqlite3.Connection) -> None:
    for table in ("cost_entries", "capability_ratings"):
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        if not exists:
            continue

        cols = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        if "requested_harness" not in cols:
            try:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN requested_harness TEXT")
            except sqlite3.OperationalError as exc:
                if "duplicate column name" not in str(exc).lower():
                    raise


MIGRATION = Migration(version=36, name="requested_harness_attribution", up=_up)
