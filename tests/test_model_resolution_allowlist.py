"""LIVE-27 resolution ordering and curated allowlist invariants."""

import sqlite3


def _catalog_db():
    conn = sqlite3.connect(":memory:")
    conn.execute(
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
            complexity_tier TEXT,
            discovered_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (harness_name, model_id, provider)
        )
        """
    )
    return conn


def _insert(conn, harness, model_id, source, discovered_at, tier="pro"):
    conn.execute(
        """
        INSERT INTO harness_models
            (harness_name, model_id, first_seen_at, last_seen_at,
             status, discovery_source, complexity_tier, discovered_at)
        VALUES (?, ?, ?, ?, 'active', ?, ?, ?)
        """,
        (harness, model_id, discovered_at, discovered_at, source, tier, discovered_at),
    )


def test_self_report_outranks_newer_execution_log():
    """gh:#2449: self_report ranks above execution_log, even when the log row is newer."""
    import synlynk.db as db

    conn = _catalog_db()
    _insert(conn, "codex", "gpt-5.6-luna", "self_report", "2026-10-01T00:00:00+00:00")
    _insert(conn, "codex", "gpt-5.6-terra", "execution_log", "2026-10-19T00:00:00+00:00")

    rows = db.get_active_harness_models(conn, harness="codex", tier="pro")

    assert [row["discovery_source"] for row in rows] == ["self_report", "execution_log"]
    assert rows[0]["model_id"] == "gpt-5.6-luna"


def test_authoritative_sources_outrank_newer_execution_log_rows(monkeypatch):
    import synlynk as sl
    import synlynk.models as models

    conn = _catalog_db()
    _insert(conn, "grok", "grok-4.6", "curated", "2026-10-01T00:00:00+00:00")
    _insert(conn, "grok", "grok-4.7", "execution_log", "2026-10-19T00:00:00+00:00")
    monkeypatch.setattr(sl, "_get_db", lambda: conn)

    assert models.resolve_tier_model("pro", "grok") == "grok-4.6"


def test_resolution_returns_only_active_allowlisted_models_for_every_harness(monkeypatch):
    import synlynk as sl
    import synlynk.models as models

    conn = _catalog_db()
    dirty_rows = {
        "codex": "None,",
        "grok": "grok-3",
        "agy": "gemini-1.5-pro",
        "claude": "claude-3-5-sonnet-20241022",
        "muse": "retired-muse-model",
    }
    for harness, model_id in dirty_rows.items():
        _insert(conn, harness, model_id, "execution_log", "2026-10-19T00:00:00+00:00")
    monkeypatch.setattr(sl, "_get_db", lambda: conn)

    for harness in dirty_rows:
        resolved = models.resolve_tier_model("pro", harness)
        assert resolved in models._curated_model_ids(harness)
        assert models.is_plausible_model_id(resolved)
        assert resolved not in {"grok-3", "gemini-1.5-pro", "None,"}
