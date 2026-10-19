"""Unit tests for the Historical Capability Backfill Engine and CLI Command."""

import sqlite3
import pytest
from synlynk.capability_backfill import run_capability_backfill, cmd_capability_backfill


@pytest.fixture
def backfill_db():
    conn = sqlite3.connect(":memory:")
    conn.execute("""
        CREATE TABLE stories (
            story_id TEXT PRIMARY KEY,
            title TEXT,
            discipline TEXT DEFAULT 'backend'
        )
    """)
    conn.execute("""
        CREATE TABLE capability_ratings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            story_id TEXT NOT NULL REFERENCES stories(story_id),
            agent TEXT NOT NULL,
            discipline TEXT NOT NULL DEFAULT 'backend',
            quality REAL NOT NULL DEFAULT 0.0,
            quality_verified INTEGER DEFAULT 0,
            pr_review_cycles INTEGER DEFAULT 0,
            model_at_completion TEXT
        )
    """)
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


def test_backfill_dry_run_leaves_db_unchanged(backfill_db):
    backfill_db.execute("INSERT INTO stories VALUES ('s-1', 'Fix deadlock bug in memory cache', 'backend')")
    backfill_db.execute("INSERT INTO capability_ratings (story_id, agent, discipline, quality) VALUES ('s-1', 'codex', 'backend', 8.5)")
    backfill_db.commit()

    report = run_capability_backfill(backfill_db, dry_run=True)
    assert report["total_ratings_analyzed"] == 1
    assert report["updated_count"] == 1
    assert report["dry_run"] is True

    # Ensure DB was not mutated
    row = backfill_db.execute("SELECT discipline FROM capability_ratings WHERE story_id='s-1'").fetchone()
    assert row[0] == "backend"


def test_backfill_live_updates_legacy_disciplines_to_sfia(backfill_db):
    # Insert a programming task, a testing task, and a requirements task
    backfill_db.execute("INSERT INTO stories VALUES ('s-1', 'Fix race condition in thread pool', 'backend')")
    backfill_db.execute("INSERT INTO stories VALUES ('s-2', 'Write unit test suite with mock assertions', 'testing')")
    backfill_db.execute("INSERT INTO stories VALUES ('s-3', 'Draft technical spec for multi-agent architecture', 'architecture')")

    backfill_db.execute("INSERT INTO capability_ratings (story_id, agent, discipline, quality, quality_verified) VALUES ('s-1', 'codex', 'backend', 9.0, 1)")
    backfill_db.execute("INSERT INTO capability_ratings (story_id, agent, discipline, quality, quality_verified) VALUES ('s-2', 'grok', 'testing', 8.5, 1)")
    backfill_db.execute("INSERT INTO capability_ratings (story_id, agent, discipline, quality, quality_verified) VALUES ('s-3', 'claude', 'architecture', 8.0, 1)")
    backfill_db.commit()

    report = run_capability_backfill(backfill_db, dry_run=False)
    assert report["updated_count"] == 3

    # Check updated disciplines in capability_ratings
    r1 = backfill_db.execute("SELECT discipline FROM capability_ratings WHERE story_id='s-1'").fetchone()[0]
    r2 = backfill_db.execute("SELECT discipline FROM capability_ratings WHERE story_id='s-2'").fetchone()[0]
    r3 = backfill_db.execute("SELECT discipline FROM capability_ratings WHERE story_id='s-3'").fetchone()[0]

    assert r1 == "PROG"
    assert r2 == "TEST"
    assert r3 == "REQM"


def test_backfill_sample_floor_and_attribution_reporting(backfill_db):
    # Insert 10 PROG tasks for codex and 2 TEST tasks for grok
    for i in range(10):
        sid = f"s-prog-{i}"
        backfill_db.execute(f"INSERT INTO stories VALUES ('{sid}', 'Implement function {i}', 'backend')")
        backfill_db.execute(f"INSERT INTO capability_ratings (story_id, agent, discipline, quality, quality_verified) VALUES ('{sid}', 'codex', 'backend', 9.0, 1)")

    for i in range(2):
        sid = f"s-test-{i}"
        backfill_db.execute(f"INSERT INTO stories VALUES ('{sid}', 'Write test {i}', 'testing')")
        backfill_db.execute(f"INSERT INTO capability_ratings (story_id, agent, discipline, quality, quality_verified) VALUES ('{sid}', 'grok', 'testing', 8.0, 1)")
    backfill_db.commit()

    report = run_capability_backfill(backfill_db, dry_run=False, min_sample=5)
    summary = report["summary"]

    codex_prog = next(s for s in summary if s["agent"] == "codex" and s["discipline"] == "PROG")
    grok_test = next(s for s in summary if s["agent"] == "grok" and s["discipline"] == "TEST")

    assert codex_prog["task_count"] == 10
    assert codex_prog["sample_floor_met"] is True
    assert grok_test["task_count"] == 2
    assert grok_test["sample_floor_met"] is False  # below min_sample 5
