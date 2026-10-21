"""Migration 27: serialize staged and active Local resume authorizations."""

import sqlite3

from synlynk.migrations import Migration


def _up(conn: sqlite3.Connection) -> None:
    active_exists = conn.execute(
        "SELECT 1 FROM local_pilot_resume_authorizations WHERE state = 'active'"
    ).fetchone() is not None
    staged = conn.execute(
        "SELECT authorization_id FROM local_pilot_resume_authorizations "
        "WHERE state = 'activating' ORDER BY rowid"
    ).fetchall()
    surplus_staged = staged if active_exists else staged[1:]
    for (authorization_id,) in surplus_staged:
        conn.execute(
            """UPDATE local_pilot_resume_authorizations
            SET state = 'failed', revoked_at = CURRENT_TIMESTAMP,
                terminal_reason = 'migration_27_reconciled_surplus_activating_authorization'
            WHERE authorization_id = ?""",
            (authorization_id,),
        )
    conn.execute(
        """CREATE UNIQUE INDEX IF NOT EXISTS idx_local_pilot_resume_one_inflight
        ON local_pilot_resume_authorizations((1))
        WHERE state IN ('activating', 'active')"""
    )


MIGRATION = Migration(version=27, name="local_pilot_resume_lifecycle_serialization", up=_up)
