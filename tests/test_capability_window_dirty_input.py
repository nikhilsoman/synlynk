"""Regression tests for gh:#2448 historical model ingestion hardening."""

import sqlite3

from synlynk.capability_window import sync_harness_models_window


def _catalog_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """
        CREATE TABLE daemon_jobs (
            job_id TEXT PRIMARY KEY, agent TEXT, task TEXT, status TEXT,
            completed_at TEXT, resolved_model TEXT
        );
        CREATE TABLE cost_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT, agent TEXT,
            model TEXT, recorded_at TEXT, total_cost_usd REAL
        );
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


def test_sync_rejects_garbage_and_retired_ids_but_keeps_catalog_ids():
    conn = _catalog_db()
    dirty = [
        "'unknown'\\nsynlynk/db.py:3772:",
        "None,",
        "grok-3",  # retired, although it has a plausible shape
        "gemini-1.5-pro",  # retired, although it has a plausible shape
    ]
    for index, model_id in enumerate(dirty):
        conn.execute(
            "INSERT INTO cost_entries (job_id, agent, model, recorded_at) "
            "VALUES (?, ?, ?, ?)",
            (f"dirty-{index}", "grok" if index == 2 else "codex", model_id,
             f"2026-10-19T00:00:0{index}+00:00"),
        )
    conn.execute(
        "INSERT INTO cost_entries (job_id, agent, model, recorded_at) "
        "VALUES ('good', 'grok', 'grok-4.7', '2026-10-19T00:00:10+00:00')"
    )

    sync_harness_models_window(conn)

    rows = conn.execute(
        "SELECT harness_name, model_id FROM harness_models ORDER BY model_id"
    ).fetchall()
    assert rows == [("grok", "grok-4.7")]


def test_sync_assigns_explicit_distinct_timestamps_and_preserves_authority():
    conn = _catalog_db()
    conn.execute(
        "INSERT INTO harness_models "
        "(harness_name, model_id, first_seen_at, last_seen_at, "
        "discovery_source, discovered_at) VALUES (?, ?, ?, ?, ?, ?)",
        (
            "grok", "grok-4.6", "2026-10-18T00:00:00+00:00",
            "2026-10-18T00:00:00+00:00", "curated", "2026-10-18T00:00:00+00:00",
        ),
    )
    for index, model_id in enumerate(("grok-4.7", "grok-4.6")):
        conn.execute(
            "INSERT INTO cost_entries (job_id, agent, model, recorded_at) "
            "VALUES (?, 'grok', ?, '2026-10-19 05:52:48')",
            (f"job-{index}", model_id),
        )

    sync_harness_models_window(conn)

    rows = conn.execute(
        "SELECT model_id, discovery_source, discovered_at FROM harness_models "
        "ORDER BY discovered_at DESC"
    ).fetchall()
    assert rows[0][0] == "grok-4.6"
    assert rows[0][1] == "curated"
    assert len({row[2] for row in rows}) == len(rows)
    assert all(row[2] != "2026-10-19 05:52:48" for row in rows[1:])
