"""Migration 36: requested_harness attribution on cost_entries/capability_ratings.

daemon_jobs already records requested_harness/actual_harness (see db_schema.py
and db.py's defensive ALTER TABLE loop) via dispatch.py's
_log_routing_fallback/take_routing_fallback mechanism. cost_entries and
capability_ratings had no equivalent column, so a reroute (e.g. local ->
fallback) was never attributable in cost or quality-rating reporting, only
in the job record itself. This migration extends the same, already-proven
pattern to both tables; synlynk/db.py:_insert_cost_row and
synlynk/jobs.py:_write_capability_rating are updated in a follow-up task to
actually populate it from the job row's own requested_harness value.

See docs/superpowers/specs/2026-11-18-harness-routing-manifest-mechanics-design.md
Section 6.
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
