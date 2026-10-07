"""Runner for versioned migrations numbered 16 and above.

Versions 1-15 are applied by synlynk.db._run_legacy_migration_and_repairs
before this runner is ever called — see synlynk/migrations/__init__.py.
"""
import sqlite3
from datetime import datetime, timezone

from synlynk.migrations import Migration
from synlynk.migrations.m0016_cost_entries_pr_number import MIGRATION as M0016
from synlynk.migrations.m0017_daemon_job_purpose import MIGRATION as M0017
from synlynk.migrations.m0018_policy_gate_events import MIGRATION as M0018

# Static, explicitly-imported registry. Append future Migration entries here
# in ascending version order — no dynamic directory scanning.
MIGRATIONS: list[Migration] = [M0016, M0017, M0018]


def _ensure_migration_history_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """CREATE TABLE IF NOT EXISTS migration_history (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at TEXT NOT NULL
        )"""
    )


def run_pending_migrations(conn: sqlite3.Connection) -> None:
    _ensure_migration_history_table(conn)
    conn.commit()

    current_version = conn.execute("PRAGMA user_version").fetchone()[0]
    pending = sorted(
        (m for m in MIGRATIONS if m.version > current_version),
        key=lambda m: m.version,
    )
    for migration in pending:
        migration.up(conn)
        conn.execute(f"PRAGMA user_version = {migration.version}")
        conn.execute(
            "INSERT OR REPLACE INTO migration_history (version, name, applied_at) VALUES (?, ?, ?)",
            (migration.version, migration.name, datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
