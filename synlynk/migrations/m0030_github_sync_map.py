"""Migration 30: github_sync_map — cache of local-row <-> GitHub-number pairs.

This is a cache of a GitHub-side fact, not a second source of truth for
roadmap/cost data (gh:#2653 design, §3.4): it exists purely so sync runs
don't re-derive GitHub issue/milestone numbers by API search every time.
"""

import sqlite3

from synlynk.migrations import Migration


def _up(conn: sqlite3.Connection) -> None:
    conn.execute(
        """CREATE TABLE IF NOT EXISTS github_sync_map (
            entity_type    TEXT NOT NULL,
            entity_id      TEXT NOT NULL,
            github_number  INTEGER NOT NULL,
            github_node_id TEXT,
            content_hash   TEXT,
            last_synced_at TEXT DEFAULT (datetime('now')),
            PRIMARY KEY (entity_type, entity_id)
        )"""
    )


MIGRATION = Migration(
    version=30,
    name="github_sync_map",
    up=_up,
)
