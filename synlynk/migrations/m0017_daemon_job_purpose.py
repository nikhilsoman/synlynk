"""Migration 17: persist typed dispatch task metadata for provenance checks."""
import sqlite3

from synlynk.migrations import Migration


def _up(conn: sqlite3.Connection) -> None:
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='daemon_jobs'"
    ).fetchone()
    if not exists:
        return
    cols = {row[1] for row in conn.execute("PRAGMA table_info(daemon_jobs)")}
    if "task_type" not in cols:
        conn.execute("ALTER TABLE daemon_jobs ADD COLUMN task_type TEXT")
    if "purpose" not in cols:
        conn.execute("ALTER TABLE daemon_jobs ADD COLUMN purpose TEXT")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_daemon_jobs_purpose ON daemon_jobs(purpose, gh_write_target)"
    )


MIGRATION = Migration(version=17, name="daemon_job_typed_purpose", up=_up)
