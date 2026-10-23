"""Regression tests for the complete LIVE-27 execution-log remediation."""

import sqlite3

from synlynk.migrations.m0028_deprecate_execution_log_models import (
    deprecate_execution_log_models,
)


def _catalog_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """
        CREATE TABLE harness_models (
            harness_name TEXT NOT NULL,
            model_id TEXT NOT NULL,
            first_seen_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            superseded_by TEXT,
            discovery_source TEXT NOT NULL DEFAULT 'curated',
            provider TEXT NOT NULL DEFAULT 'native',
            discovered_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (harness_name, model_id, provider)
        );
        """
    )
    return conn


def _insert(conn, harness, model_id, status, source):
    conn.execute(
        """
        INSERT INTO harness_models
            (harness_name, model_id, first_seen_at, last_seen_at,
             status, discovery_source)
        VALUES (?, ?, '2026-10-19T00:00:00+00:00',
                '2026-10-19T00:00:00+00:00', ?, ?)
        """,
        (harness, model_id, status, source),
    )


def test_deprecates_every_execution_log_row_and_preserves_audit_rows():
    conn = _catalog_db()
    _insert(conn, "local", "Ornith-1.0-9B-4bit", "stale", "execution_log")
    _insert(conn, "muse", "muse-spark-1.3", "stale", "execution_log")
    _insert(conn, "codex", "None,", "deprecated", "execution_log")
    _insert(conn, "codex", "gpt-5.6-luna", "active", "curated")

    assert deprecate_execution_log_models(conn) == 2

    rows = conn.execute(
        "SELECT harness_name, model_id, status, discovery_source "
        "FROM harness_models ORDER BY harness_name, model_id"
    ).fetchall()
    assert rows == [
        ("codex", "None,", "deprecated", "execution_log"),
        ("codex", "gpt-5.6-luna", "active", "curated"),
        ("local", "Ornith-1.0-9B-4bit", "deprecated", "execution_log"),
        ("muse", "muse-spark-1.3", "deprecated", "execution_log"),
    ]

    # The remediation is idempotent and never deletes audit rows.
    assert deprecate_execution_log_models(conn) == 0
    assert conn.execute(
        "SELECT COUNT(*) FROM harness_models WHERE discovery_source='execution_log'"
    ).fetchone()[0] == 3
