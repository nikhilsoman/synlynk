"""Regression tests for gh:#2441: execution-log fragments corrupting harness_models.

Covers both halves of the fix: malformed model ids are rejected before any
INSERT into harness_models, and resolve_tier_model's untiered fallback skips
rows that fail shape validation.
"""

import sqlite3

GARBAGE_IDS = [
    "'unknown'\nsynlynk/db.py:3772:",
    'job.get("model_version")',
    '_pkg("extract_model_version")(log_text,',
]


def _memory_catalog_db():
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


def test_execution_log_fragments_rejected_at_insert_time():
    from synlynk.capability_window import sync_harness_models_window
    from synlynk.models import is_plausible_model_id

    for garbage in GARBAGE_IDS:
        assert not is_plausible_model_id(garbage)
    assert is_plausible_model_id("gpt-5.6-luna")

    conn = _memory_catalog_db()
    for i, garbage in enumerate(GARBAGE_IDS):
        conn.execute(
            "INSERT INTO cost_entries (job_id, agent, model, recorded_at, total_cost_usd)"
            " VALUES (?, 'codex', ?, datetime('now'), 0.10)",
            (f"j-garbage-{i}", garbage),
        )
        conn.execute(
            "INSERT INTO daemon_jobs VALUES (?, 'codex', 'task', 'done', datetime('now'), ?)",
            (f"j-job-{i}", garbage),
        )
    conn.execute(
        "INSERT INTO cost_entries (job_id, agent, model, recorded_at, total_cost_usd)"
        " VALUES ('j-good', 'codex', 'gpt-5.6-luna', datetime('now'), 0.10)"
    )
    conn.commit()

    sync_harness_models_window(conn)

    model_ids = [row[0] for row in conn.execute("SELECT model_id FROM harness_models").fetchall()]
    assert model_ids == ["gpt-5.6-luna"]
    conn.close()


def test_upsert_harness_model_rejects_malformed_id():
    from synlynk.db import upsert_harness_model

    conn = _memory_catalog_db()
    for garbage in GARBAGE_IDS:
        upsert_harness_model(conn, "codex", garbage, discovery_source="execution_log")
    conn.commit()
    assert conn.execute("SELECT COUNT(*) FROM harness_models").fetchone()[0] == 0
    upsert_harness_model(conn, "codex", "gpt-5.6-luna", discovery_source="execution_log")
    conn.commit()
    assert conn.execute("SELECT COUNT(*) FROM harness_models").fetchone()[0] == 1
    conn.close()


def _insert_raw_catalog_row(conn, harness, model_id, discovered_at):
    conn.execute(
        "INSERT INTO harness_models (harness_name, model_id, first_seen_at,"
        " last_seen_at, status, discovery_source, provider, discovered_at)"
        " VALUES (?, ?, ?, ?, 'active', 'execution_log', 'native', ?)",
        (harness, model_id, discovered_at, discovered_at, discovered_at),
    )


def test_resolve_tier_model_skips_garbage_fallback_row(project_dir, monkeypatch):
    import synlynk as sl
    import synlynk.models as models

    monkeypatch.setattr(models, "_static_tier_model", lambda tier, harness, repo_path=None: "stale-static-model")
    conn = sl._get_db()
    # Newest discovery is a scraped fragment; an older well-shaped row exists.
    _insert_raw_catalog_row(conn, "codex", GARBAGE_IDS[0], "2026-10-19T00:00:00+00:00")
    _insert_raw_catalog_row(conn, "codex", "gpt-5.6-luna", "2026-10-14T00:00:00+00:00")
    conn.commit()
    conn.close()

    assert models.resolve_tier_model("pro", "codex") == "gpt-5.6-luna"


def test_resolve_tier_model_falls_back_to_static_when_only_garbage(project_dir, monkeypatch):
    import synlynk as sl
    import synlynk.models as models

    monkeypatch.setattr(models, "_static_tier_model", lambda tier, harness, repo_path=None: "curated-fallback-model")
    conn = sl._get_db()
    for i, garbage in enumerate(GARBAGE_IDS):
        _insert_raw_catalog_row(conn, "codex", garbage, f"2026-10-{10 + i}T00:00:00+00:00")
    conn.commit()
    conn.close()

    assert models.resolve_tier_model("pro", "codex") == "curated-fallback-model"
