"""Migration 25: durable independent-review selections for Local pilot jobs."""

import sqlite3

from synlynk.migrations import Migration


def _up(conn: sqlite3.Connection) -> None:
    conn.execute(
        """CREATE TABLE IF NOT EXISTS local_pilot_review_selections (
            job_id TEXT PRIMARY KEY REFERENCES local_pilot_evidence(job_id),
            candidate_json TEXT NOT NULL,
            selected_harness TEXT NOT NULL,
            selection_reason TEXT NOT NULL,
            selected_at TEXT NOT NULL
        )"""
    )


MIGRATION = Migration(version=25, name="local_pilot_review_selection", up=_up)
