"""Migration 22: rename the legacy subscriptions agent column."""
import sqlite3

from synlynk.migrations import Migration


def _up(conn: sqlite3.Connection) -> None:
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='subscriptions'"
    ).fetchone()
    if not exists:
        return

    columns = {row[1] for row in conn.execute("PRAGMA table_info(subscriptions)")}
    if "agent_name" in columns and "harness_name" not in columns:
        conn.execute(
            "ALTER TABLE subscriptions RENAME COLUMN agent_name TO harness_name"
        )


MIGRATION = Migration(version=22, name="subscriptions_harness_name", up=_up)
