"""Migration 23: deprecate invalid execution-log model discoveries."""

import sqlite3

from synlynk.migrations import Migration


def cleanse_execution_log_models(conn: sqlite3.Connection) -> int:
    """Deprecate execution-log rows that are not current catalog models.

    Execution logs are observational input, not an authority for the model
    catalog.  Keep the rows for auditability, but remove malformed and retired
    candidates from the active catalog.  The predicates intentionally reuse
    the same validation and catalog-membership helpers as model resolution.
    """
    from synlynk.models import _curated_model_ids, is_plausible_model_id

    rows = conn.execute(
        "SELECT rowid, harness_name, model_id FROM harness_models "
        "WHERE discovery_source = 'execution_log' AND status != 'deprecated'"
    ).fetchall()
    deprecated_rowids = []
    allowlists: dict[str, set[str]] = {}
    for rowid, harness_name, model_id in rows:
        allowed = allowlists.setdefault(harness_name, _curated_model_ids(harness_name))
        if not is_plausible_model_id(model_id) or model_id not in allowed:
            deprecated_rowids.append(rowid)

    if deprecated_rowids:
        conn.executemany(
            "UPDATE harness_models SET status = 'deprecated' WHERE rowid = ?",
            ((rowid,) for rowid in deprecated_rowids),
        )
    return len(deprecated_rowids)


def _up(conn: sqlite3.Connection) -> None:
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='harness_models'"
    ).fetchone()
    if exists:
        cleanse_execution_log_models(conn)


MIGRATION = Migration(version=23, name="cleanse_execution_log_models", up=_up)
