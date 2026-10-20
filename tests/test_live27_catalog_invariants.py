"""Fleet-wide catalog invariants for LIVE-27."""

import sqlite3

import pytest

from synlynk.db import get_active_harness_models
from synlynk.models import (
    _curated_model_ids,
    is_plausible_model_id,
    resolve_tier_model,
)


HARNESS_NAMES = ("codex", "grok", "agy", "claude", "muse")
TIERS = ("fast", "pro", "reasoning")
AUTHORITATIVE_SOURCES = ("curated", "curated_fallback", "config_file", "cli:probe")


def _catalog_db() -> sqlite3.Connection:
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


def _insert(
    conn: sqlite3.Connection,
    harness: str,
    model_id: str,
    source: str,
    discovered_at: str,
    tier: str = "pro",
) -> None:
    conn.execute(
        """
        INSERT INTO harness_models
            (harness_name, model_id, first_seen_at, last_seen_at,
             status, discovery_source, complexity_tier, discovered_at)
        VALUES (?, ?, ?, ?, 'active', ?, ?, ?)
        """,
        (harness, model_id, discovered_at, discovered_at, source, tier, discovered_at),
    )


def test_active_catalog_rows_are_plausible_model_ids(monkeypatch):
    import synlynk as sl

    conn = _catalog_db()
    for harness in HARNESS_NAMES:
        model_id = next(iter(_curated_model_ids(harness)))
        _insert(conn, harness, model_id, "curated", "2026-10-01T00:00:00+00:00")
    monkeypatch.setattr(sl, "_get_db", lambda: conn)

    rows = conn.execute(
        "SELECT model_id FROM harness_models"
    ).fetchall()
    assert rows
    assert all(is_plausible_model_id(row[0]) for row in rows)


@pytest.mark.parametrize("harness", HARNESS_NAMES)
@pytest.mark.parametrize("tier", TIERS)
@pytest.mark.parametrize("authoritative_source", AUTHORITATIVE_SOURCES)
def test_execution_log_never_outranks_authoritative_source(
    harness, tier, authoritative_source
):
    conn = _catalog_db()
    _insert(
        conn,
        harness,
        f"{harness}-authoritative-{authoritative_source}",
        authoritative_source,
        "2026-10-01T00:00:00+00:00",
        tier,
    )
    _insert(conn, harness, f"{harness}-log", "execution_log", "2026-10-19T00:00:00+00:00", tier)

    rows = get_active_harness_models(conn, harness=harness, tier=tier)

    assert rows[0]["discovery_source"] in AUTHORITATIVE_SOURCES
    assert rows.index(next(row for row in rows if row["discovery_source"] == "execution_log")) > 0


@pytest.mark.parametrize("harness", HARNESS_NAMES)
@pytest.mark.parametrize("tier", TIERS)
def test_resolution_is_plausible_and_current_catalog_member(monkeypatch, harness, tier):
    import synlynk as sl

    conn = _catalog_db()
    _insert(conn, harness, "'unknown'\nsynlynk/db.py:3772:", "execution_log", "2026-10-19T00:00:00+00:00", tier)
    monkeypatch.setattr(sl, "_get_db", lambda: conn)

    resolved = resolve_tier_model(tier, harness)

    assert is_plausible_model_id(resolved)
    assert resolved in _curated_model_ids(harness)


def test_discovered_fallback_respects_requested_tier(monkeypatch):
    import synlynk as sl
    import synlynk.db as db

    conn = _catalog_db()
    _insert(
        conn,
        "agy",
        "gemini-3.8-flash-medium",
        "cli:probe",
        "2026-10-01T00:00:00+00:00",
        "fast",
    )
    _insert(
        conn,
        "agy",
        "claude-opus-4-6-thinking",
        "cli:probe",
        "2026-10-02T00:00:00+00:00",
        "reasoning",
    )
    monkeypatch.setattr(sl, "_get_db", lambda: conn)

    original_get_active = db.get_active_harness_models
    skipped_tiers = set()

    def empty_first_tier_lookup(conn, harness=None, tier=None):
        if harness == "agy" and tier is not None and tier not in skipped_tiers:
            skipped_tiers.add(tier)
            return []
        return original_get_active(conn, harness=harness, tier=tier)

    monkeypatch.setattr(db, "get_active_harness_models", empty_first_tier_lookup)

    assert resolve_tier_model("fast", "agy") == "gemini-3.8-flash-medium"
    assert resolve_tier_model("reasoning", "agy") == "claude-opus-4-6-thinking"

