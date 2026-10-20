"""Migration 22: cost ledger stores per-turn usage breakdown."""
import sqlite3

from synlynk.migrations import Migration


def _up(conn: sqlite3.Connection) -> None:
    info = conn.execute("PRAGMA table_info(cost_entries)").fetchall()
    cols = {row[1] for row in info}
    
    if "turn_usage_json" not in cols:
        conn.execute(
            "ALTER TABLE cost_entries ADD COLUMN turn_usage_json TEXT"
        )


MIGRATION = Migration(version=22, name="cost_entries_turn_usage_json", up=_up)
