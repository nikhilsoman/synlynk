"""Unit tests for multi-track quota tracking and dual-read cost engine (MC-2)."""

import json
import sqlite3
import pytest

from synlynk.quota import (
    _upsert_agent_quota,
    _read_agent_quota_rows,
    _quota_status_for_agent,
    resolve_harness_track,
)


@pytest.fixture
def db_conn(tmp_path):
    import synlynk as sl
    db_file = tmp_path / "state.db"
    conn = sl._get_db(str(db_file))
    try:
        yield conn
    finally:
        conn.close()


def test_resolve_harness_track():
    assert resolve_harness_track("agy", "gemini-3.7-flash") == "gemini"
    assert resolve_harness_track("agy", "gemini-1.5-pro") == "gemini"
    assert resolve_harness_track("agy", "claude-sonnet-5") == "claude_proxy"
    assert resolve_harness_track("agy", "claude-3-5-sonnet") == "claude_proxy"
    assert resolve_harness_track("agy", "gpt-5") == "gpt_oss"
    assert resolve_harness_track("agy", "deepseek-r1") == "gpt_oss"
    assert resolve_harness_track("agy", "qwen2.5-coder") == "gpt_oss"
    assert resolve_harness_track("claude", "claude-sonnet-5") == "default"
    assert resolve_harness_track("codex", "gpt-5") == "default"
    assert resolve_harness_track("grok", "grok-3") == "default"


def test_multitrack_quota_isolation(db_conn):
    # Upsert distinct tracks for Antigravity (Google AI Pro multi-track)
    _upsert_agent_quota(
        "agy",
        "5h",
        limit_tokens=200_000,
        used_tokens=150_000,
        track="gemini",
        model="gemini-3.7-flash",
        conn=db_conn,
    )
    _upsert_agent_quota(
        "agy",
        "5h",
        limit_tokens=100_000,
        used_tokens=20_000,
        track="claude_proxy",
        model="claude-sonnet-5",
        conn=db_conn,
    )
    _upsert_agent_quota(
        "agy",
        "5h",
        limit_tokens=100_000,
        used_tokens=90_000,
        track="gpt_oss",
        model="deepseek-r1",
        conn=db_conn,
    )

    rows = _read_agent_quota_rows(db_conn, "agy")
    assert len(rows) == 3
    tracks = {r["track"]: r for r in rows}
    assert "gemini" in tracks
    assert "claude_proxy" in tracks
    assert "gpt_oss" in tracks

    assert tracks["gemini"]["headroom"] == 50_000
    assert tracks["claude_proxy"]["headroom"] == 80_000
    assert tracks["gpt_oss"]["headroom"] == 10_000

    # Quota status with track filtering
    status_gemini = _quota_status_for_agent(db_conn, "agy", estimated_tokens=60_000, track="gemini")
    assert status_gemini["status"] == "exhausted"

    status_claude = _quota_status_for_agent(db_conn, "agy", estimated_tokens=60_000, track="claude_proxy")
    assert status_claude["status"] == "ok"
    assert status_claude["headroom"] == 80_000


def test_multitrack_migration_existing_db(tmp_path):
    # Create legacy table without track column
    db_file = tmp_path / "legacy.db"
    conn = sqlite3.connect(str(db_file))
    conn.execute("""
        CREATE TABLE harness_quotas (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            harness      TEXT NOT NULL,
            model        TEXT NOT NULL DEFAULT 'unknown',
            quota_type   TEXT NOT NULL,
            unit         TEXT NOT NULL DEFAULT 'tokens',
            limit_tokens INTEGER NOT NULL,
            used_tokens  INTEGER NOT NULL DEFAULT 0,
            reset_at     TIMESTAMP,
            updated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(harness, model, quota_type, unit)
        )
    """)
    conn.execute("""
        INSERT INTO harness_quotas (harness, model, quota_type, unit, limit_tokens, used_tokens)
        VALUES ('claude', 'unknown', '5h', 'tokens', 100000, 10000)
    """)
    conn.commit()
    conn.close()

    # Run _get_db which triggers migration
    import synlynk as sl
    migrated_conn = sl._get_db(str(db_file))
    try:
        cols = {row[1] for row in migrated_conn.execute("PRAGMA table_info(harness_quotas)")}
        assert "track" in cols
        row = migrated_conn.execute("SELECT track FROM harness_quotas WHERE harness='claude'").fetchone()
        assert row[0] == "default"
    finally:
        migrated_conn.close()
