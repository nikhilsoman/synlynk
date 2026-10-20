"""Regression tests for gh:#2447 canonical model-catalog cleansing."""

import sqlite3

from synlynk.migrations.m0023_cleanse_execution_log_models import (
    cleanse_execution_log_models,
)


def _catalog_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """
        CREATE TABLE harness_models (
            harness_name TEXT NOT NULL, model_id TEXT NOT NULL,
            first_seen_at TEXT NOT NULL, last_seen_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active', superseded_by TEXT,
            discovery_source TEXT NOT NULL DEFAULT 'curated',
            provider TEXT NOT NULL DEFAULT 'native', discovered_at TEXT NOT NULL
                DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (harness_name, model_id, provider)
        );
        """
    )
    return conn


def _insert(conn, harness, model_id, source, status="active"):
    conn.execute(
        "INSERT INTO harness_models "
        "(harness_name, model_id, first_seen_at, last_seen_at, status, discovery_source) "
        "VALUES (?, ?, '2026-10-19T00:00:00+00:00', '2026-10-19T00:00:00+00:00', ?, ?)",
        (harness, model_id, status, source),
    )


def test_cleanse_deprecates_malformed_and_retired_execution_log_rows_only():
    conn = _catalog_db()
    malformed = "'unknown'\nsynlynk/db.py:3772:"
    for model_id, harness in (
        ("None,", "codex"),
        (malformed, "codex"),
        ("grok-3", "grok"),
        ("gemini-1.5-pro", "agy"),
    ):
        _insert(conn, harness, model_id, "execution_log")

    _insert(conn, "grok", "grok-4.7", "execution_log")
    _insert(conn, "codex", "gpt-5.6-luna", "curated")
    _insert(conn, "grok", "grok-4.6", "config_file")
    _insert(conn, "agy", "gemini-3.8-flash-high", "cli:agy")
    _insert(conn, "codex", "not-a-current-model", "curated")

    assert cleanse_execution_log_models(conn) == 4

    rows = conn.execute(
        "SELECT harness_name, model_id, status, discovery_source "
        "FROM harness_models ORDER BY harness_name, model_id"
    ).fetchall()
    by_key = {(harness, model_id): (status, source) for harness, model_id, status, source in rows}
    assert by_key[("codex", "None,")] == ("deprecated", "execution_log")
    assert by_key[("codex", malformed)] == ("deprecated", "execution_log")
    assert by_key[("grok", "grok-3")] == ("deprecated", "execution_log")
    assert by_key[("agy", "gemini-1.5-pro")] == ("deprecated", "execution_log")
    assert by_key[("grok", "grok-4.7")] == ("active", "execution_log")
    assert by_key[("codex", "gpt-5.6-luna")] == ("active", "curated")
    assert by_key[("grok", "grok-4.6")] == ("active", "config_file")
    assert by_key[("agy", "gemini-3.8-flash-high")] == ("active", "cli:agy")
    assert by_key[("codex", "not-a-current-model")] == ("active", "curated")

    # A second run is idempotent and does not touch already-deprecated rows.
    assert cleanse_execution_log_models(conn) == 0
