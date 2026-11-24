"""Migration 39: cache sub-floor exploration spend on routing state."""
import sqlite3

from synlynk.migrations import Migration


def _up(conn: sqlite3.Connection) -> None:
    cols = {row[1] for row in conn.execute("PRAGMA table_info(routing_rotation_state)")}
    if "exploration_spend_usd" not in cols:
        conn.execute(
            "ALTER TABLE routing_rotation_state "
            "ADD COLUMN exploration_spend_usd REAL NOT NULL DEFAULT 0"
        )


MIGRATION = Migration(version=39, name="exploration_spend_cap", up=_up)
