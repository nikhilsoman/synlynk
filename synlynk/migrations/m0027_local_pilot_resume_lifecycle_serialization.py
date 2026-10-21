"""Migration 27: serialize staged and active Local resume authorizations."""

import sqlite3

from synlynk.migrations import Migration


def _up(conn: sqlite3.Connection) -> None:
    staged = conn.execute(
        "SELECT authorization_id FROM local_pilot_resume_authorizations "
        "WHERE state = 'activating' ORDER BY rowid"
    ).fetchall()
    for (authorization_id,) in staged[1:]:
        conn.execute(
            """UPDATE local_pilot_resume_authorizations
            SET state = 'failed', revoked_at = CURRENT_TIMESTAMP,
                terminal_reason = 'migration_27_reconciled_surplus_activating_authorization'
            WHERE authorization_id = ?""",
            (authorization_id,),
        )
    conn.execute(
        """CREATE UNIQUE INDEX IF NOT EXISTS idx_local_pilot_resume_one_inflight
        ON local_pilot_resume_authorizations(state)
        WHERE state IN ('activating', 'active')"""
    )


MIGRATION = Migration(version=27, name="local_pilot_resume_lifecycle_serialization", up=_up)
