"""Migration 18: add immutable human attestations for legacy job provenance."""
import sqlite3

from synlynk.migrations import Migration


def _up(conn: sqlite3.Connection) -> None:
    conn.execute(
        """CREATE TABLE IF NOT EXISTS job_provenance_attestations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT NOT NULL UNIQUE REFERENCES daemon_jobs(job_id),
            role TEXT NOT NULL,
            task_type TEXT NOT NULL,
            purpose TEXT NOT NULL CHECK (purpose IN ('implementation', 'review', 'other')),
            attested_by TEXT NOT NULL,
            rationale TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT 'local-cli',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_job_provenance_attestations_job "
        "ON job_provenance_attestations(job_id)"
    )
    conn.executescript("""
        CREATE TRIGGER IF NOT EXISTS job_provenance_attestations_no_update
        BEFORE UPDATE ON job_provenance_attestations
        BEGIN
            SELECT RAISE(ABORT, 'job provenance attestations are append-only');
        END;
        CREATE TRIGGER IF NOT EXISTS job_provenance_attestations_no_delete
        BEFORE DELETE ON job_provenance_attestations
        BEGIN
            SELECT RAISE(ABORT, 'job provenance attestations are append-only');
        END;
    """)


MIGRATION = Migration(version=18, name="job_provenance_human_attestations", up=_up)
