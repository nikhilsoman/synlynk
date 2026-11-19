"""Migration 35: per-cell round-robin rotation state for sub-floor harness exploration.

See docs/superpowers/specs/2026-11-18-harness-routing-manifest-mechanics-design.md Section 2.
"""
import sqlite3

from synlynk.migrations import Migration


def _up(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS routing_rotation_state (
            task_type      TEXT PRIMARY KEY,
            rotation_index INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_capability_ratings_harness_task "
        "ON capability_ratings(agent, task_type)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_cost_entries_harness_task "
        "ON cost_entries(agent, type_id)"
    )


MIGRATION = Migration(version=35, name="routing_rotation_state", up=_up)
