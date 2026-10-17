"""Migration 22: ensure subscriptions harmony with harness rename.

The harness rename (agent_name -> harness_name) for subscriptions is handled
by synlynk.db._run_harness_rename_migration in the legacy path (v1-15).
This migration ensures the same rename is applied for fresh DBs created via
the versioned runner, keeping user_version and migration_history aligned
across legacy and fresh paths. Idempotent and safe to re-run.
"""

import sqlite3

from synlynk.migrations import Migration


def _up(conn: sqlite3.Connection) -> None:
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    if "subscriptions" not in tables:
        return
    cols = {row[1] for row in conn.execute("PRAGMA table_info(subscriptions)").fetchall()}
    if "agent_name" in cols and "harness_name" not in cols:
        conn.execute("ALTER TABLE subscriptions RENAME COLUMN agent_name TO harness_name")
    # Also handle the broader harness rename set for completeness if legacy path was skipped
    for tbl, old_col, new_col in [
        ("harness_verb_map", "agent_name", "harness_name"),
        ("harness_verb_map", "agent_command", "harness_command"),
        ("harness_version_history", "agent_name", "harness_name"),
        ("cycle_capability", "agent_name", "harness_name"),
        ("harness_status", "agent_name", "harness_name"),
    ]:
        if tbl not in tables:
            continue
        tcols = {row[1] for row in conn.execute(f"PRAGMA table_info({tbl})").fetchall()}
        if old_col in tcols and new_col not in tcols:
            conn.execute(f"ALTER TABLE {tbl} RENAME COLUMN {old_col} TO {new_col}")


MIGRATION = Migration(version=22, name="subscriptions_harness_name", up=_up)
