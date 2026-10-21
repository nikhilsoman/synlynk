"""Migration 27: serialize staged and active Local resume authorizations."""

import sqlite3

from synlynk.migrations import Migration


def _up(conn: sqlite3.Connection) -> None:
    conn.execute(
        """CREATE UNIQUE INDEX IF NOT EXISTS idx_local_pilot_resume_one_inflight
        ON local_pilot_resume_authorizations(state)
        WHERE state IN ('activating', 'active')"""
    )


MIGRATION = Migration(version=27, name="local_pilot_resume_lifecycle_serialization", up=_up)
