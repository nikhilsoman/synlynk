"""Migration 35: routing rotation state + capability/cost lookup indexes.

Backs synlynk/routing.py's LiveQueryRouter: a sub-floor (<5 samples)
harness×task_type pair round-robins via the pointer in this table instead
of defaulting to one hardcoded fallback harness.

See docs/superpowers/specs/2026-11-18-harness-routing-manifest-mechanics-design.md.
"""
import sqlite3

from synlynk.migrations import Migration


def _up(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS routing_rotation_state (
            task_type   TEXT NOT NULL,
            cursor      INTEGER NOT NULL DEFAULT 0,
            updated_at  TEXT DEFAULT (datetime('now')),
            PRIMARY KEY (task_type)
        )
    """)
    cap_cols = {row[1] for row in conn.execute("PRAGMA table_info(capability_ratings)")}
    if {"agent", "discipline"} <= cap_cols:
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_capability_ratings_harness_task "
            "ON capability_ratings(agent, discipline)"
        )
    elif {"agent", "task_type"} <= cap_cols:
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_capability_ratings_harness_task "
            "ON capability_ratings(agent, task_type)"
        )
    cost_cols = {row[1] for row in conn.execute("PRAGMA table_info(cost_entries)")}
    if {"agent", "type_id"} <= cost_cols:
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_cost_entries_harness_task "
            "ON cost_entries(agent, type_id)"
        )


MIGRATION = Migration(version=35, name="routing_rotation_state", up=_up)
