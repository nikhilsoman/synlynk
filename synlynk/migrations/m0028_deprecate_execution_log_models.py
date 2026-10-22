"""Migration 28: retire all execution-log model discoveries."""

import sqlite3

from synlynk.migrations import Migration


def deprecate_execution_log_models(conn: sqlite3.Connection) -> int:
    """Mark every execution-log discovery deprecated without deleting it.

    Execution logs are observational evidence, not a source of authority for
    the current model catalog.  Retaining the rows preserves the incident
    audit trail while removing both malformed and stale observations from
    active model resolution.
    """
    cursor = conn.execute(
        """
        UPDATE harness_models
        SET status = 'deprecated'
        WHERE discovery_source = 'execution_log'
          AND status != 'deprecated'
        """
    )
    return cursor.rowcount


def _up(conn: sqlite3.Connection) -> None:
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='harness_models'"
    ).fetchone()
    if exists:
        deprecate_execution_log_models(conn)


MIGRATION = Migration(
    version=28,
    name="deprecate_execution_log_models",
    up=_up,
)
