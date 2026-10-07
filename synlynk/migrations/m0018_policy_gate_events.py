"""Migration 18: durable observe-mode gate verdict log for synlynk pr check."""
import sqlite3

from synlynk.migrations import Migration


def _up(conn: sqlite3.Connection) -> None:
    conn.execute(
        """CREATE TABLE IF NOT EXISTS policy_gate_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pr_number INTEGER NOT NULL,
            gate TEXT NOT NULL,
            mode TEXT NOT NULL,
            verdict TEXT NOT NULL,
            detail TEXT NOT NULL,
            recorded_at TEXT NOT NULL
        )"""
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_policy_gate_events_gate "
        "ON policy_gate_events(gate, id)"
    )


MIGRATION = Migration(version=18, name="policy_gate_events", up=_up)
