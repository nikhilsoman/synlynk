"""Unit tests for Dynamic 1% Attribution and Multi-Model Window Engine."""

import sqlite3
import pytest
from synlynk.capability_window import (
    calculate_sfia_volume_distribution,
    get_active_sfia_disciplines,
    sync_harness_models_window,
)


@pytest.fixture
def mock_db():
    conn = sqlite3.connect(":memory:")
    conn.execute("""
        CREATE TABLE daemon_jobs (
            job_id TEXT PRIMARY KEY,
            agent TEXT NOT NULL,
            task TEXT NOT NULL,
            status TEXT NOT NULL,
            completed_at TEXT,
            resolved_model TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE cost_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT,
            agent TEXT,
            model TEXT,
            recorded_at TEXT,
            total_cost_usd REAL
        )
    """)
    conn.execute("""
        CREATE TABLE harness_models (
            harness_name TEXT NOT NULL,
            model_id TEXT NOT NULL,
            first_seen_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            superseded_by TEXT,
            discovery_source TEXT NOT NULL DEFAULT 'curated',
            provider TEXT NOT NULL DEFAULT 'native',
            rate_input_per_mtok REAL,
            rate_output_per_mtok REAL,
            rate_cache_read_per_mtok REAL,
            rate_cache_write_per_mtok REAL,
            rate_tool_use_per_mtok REAL,
            rate_currency TEXT NOT NULL DEFAULT 'usd',
            rate_source TEXT,
            complexity_tier TEXT,
            max_effort_level TEXT,
            context_window_tokens INTEGER,
            max_output_tokens INTEGER,
            discovered_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (harness_name, model_id, provider)
        )
    """)
    return conn


def test_sfia_volume_distribution_and_1_percent_threshold(mock_db):
    # Insert 95 PROG tasks, 4 TEST tasks, 1 GRAP task, and 0 ANIM tasks
    for i in range(95):
        mock_db.execute(
            "INSERT INTO daemon_jobs VALUES (?, 'codex', 'Fix bug and implement parser function', 'done', datetime('now'), 'gpt-5.6')",
            (f"j-prog-{i}",),
        )
    for i in range(4):
        mock_db.execute(
            "INSERT INTO daemon_jobs VALUES (?, 'grok', 'Write unit test assertions and mock fixtures', 'done', datetime('now'), 'grok-4.6')",
            (f"j-test-{i}",),
        )
    mock_db.execute(
        "INSERT INTO daemon_jobs VALUES ('j-grap-1', 'agy', 'Design SVG vector icons and graphics', 'done', datetime('now'), 'gemini-3.8')",
    )
    mock_db.commit()

    dist = calculate_sfia_volume_distribution(mock_db)
    assert dist["PROG"]["count"] == 95
    assert dist["PROG"]["percentage"] == 0.95
    assert dist["TEST"]["count"] == 4
    assert dist["TEST"]["percentage"] == 0.04
    assert dist["GRAP"]["count"] == 1
    assert dist["GRAP"]["percentage"] == 0.01

    active_disciplines = get_active_sfia_disciplines(mock_db, threshold=0.01)
    assert "PROG" in active_disciplines
    assert "TEST" in active_disciplines
    assert "GRAP" in active_disciplines
    assert "ANIM" not in active_disciplines
    assert "SNDD" not in active_disciplines


def test_sync_harness_models_sliding_window(mock_db):
    # Insert an active recent model and an old inactive model in harness_models
    mock_db.execute("""
        INSERT INTO harness_models (harness_name, model_id, first_seen_at, last_seen_at, status)
        VALUES
        ('codex', 'gpt-5.6-terra', datetime('now', '-20 days'), datetime('now', '-2 days'), 'active'),
        ('claude', 'claude-3-opus', datetime('now', '-90 days'), datetime('now', '-45 days'), 'active')
    """)

    # Insert a new model seen in cost_entries
    mock_db.execute("""
        INSERT INTO cost_entries (job_id, agent, model, recorded_at, total_cost_usd)
        VALUES ('j-new-1', 'grok', 'grok-4.6', datetime('now', '-1 days'), 0.50)
    """)
    mock_db.commit()

    synced = sync_harness_models_window(mock_db, lookback_days=30)
    assert len(synced) >= 2

    # Check database state
    active = [row[0] for row in mock_db.execute("SELECT model_id FROM harness_models WHERE status='active'").fetchall()]
    deprecated = [row[0] for row in mock_db.execute("SELECT model_id FROM harness_models WHERE status='deprecated'").fetchall()]

    assert "gpt-5.6-terra" in active
    assert "claude-3-opus" in deprecated
    assert "grok-4.6" in active
