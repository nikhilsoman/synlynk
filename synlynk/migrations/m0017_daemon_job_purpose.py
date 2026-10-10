"""Migration 17: persist typed dispatch task metadata for provenance checks."""
import sqlite3

from synlynk.migrations import Migration


def _up(conn: sqlite3.Connection) -> None:
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='daemon_jobs'"
    ).fetchone()
    if not exists:
        return
    for name, definition in (
        ("task_type", "TEXT"),
        ("task_type_explicit", "INTEGER"),
        ("purpose", "TEXT"),
    ):
        cols = {row[1] for row in conn.execute("PRAGMA table_info(daemon_jobs)")}
        if name in cols:
            continue
        try:
            conn.execute(f"ALTER TABLE daemon_jobs ADD COLUMN {name} {definition}")
        except sqlite3.OperationalError as exc:
            # Concurrent CLI startup may apply the same additive migration.
            # Ignore only the winner's duplicate-column result.
            if "duplicate column name" not in str(exc).lower():
                raise
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_daemon_jobs_purpose ON daemon_jobs(purpose)"
    )


MIGRATION = Migration(version=17, name="daemon_job_typed_purpose", up=_up)
