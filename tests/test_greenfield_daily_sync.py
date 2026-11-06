"""Unit tests for Multi-Channel Daily Sync Engine (v0.28.5)."""
from __future__ import annotations

import os
import sqlite3
import pytest

from synlynk.greenfield.daily_sync import (
    generate_daily_sync,
    format_cli_greeting,
    format_vizor_payload,
    format_discord_embed,
)


def test_generate_daily_sync_with_state_db(tmp_path):
    """Verify daily sync aggregates yesterday's changes and unblocked tasks."""
    db_file = tmp_path / ".synlynk" / "state.db"
    db_file.parent.mkdir(parents=True)
    conn = sqlite3.connect(str(db_file))
    from synlynk.db_schema import _DB_SCHEMA, ONBOARDING_SESSIONS_SCHEMA
    conn.executescript(_DB_SCHEMA)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS cost_entries (id INTEGER PRIMARY KEY, task TEXT, cost_usd REAL, tokens_in INTEGER, tokens_out INTEGER, timestamp TEXT)"
    )

    conn.execute(
        "INSERT INTO stories (story_id, title, readiness, priority) VALUES (?, ?, ?, ?)",
        ("story-101", "Build Whisper Transcription Core", "ready", 1),
    )
    conn.execute(
        "INSERT INTO cost_entries (task, cost_usd, tokens_in, tokens_out, timestamp) VALUES (?, ?, ?, ?, ?)",
        ("Scaffold Setup", 0.42, 1000, 200, "2026-11-06T12:00:00Z"),
    )
    conn.commit()
    conn.close()

    sync_data = generate_daily_sync(str(tmp_path))
    assert "Whisper Transcription Core" in sync_data["up_next_task"]
    assert sync_data["burn_cost_usd"] == pytest.approx(0.42)

    # Test CLI formatting
    greeting = format_cli_greeting(sync_data)
    assert "Synlynk Daily Sync" in greeting
    assert "Whisper Transcription Core" in greeting

    # Test Vizor JSON payload
    vizor = format_vizor_payload(sync_data)
    assert vizor["type"] == "daily_sync_digest"
    assert vizor["hero_card"]["burn_rate_usd"] == pytest.approx(0.42)

    # Test Discord rich embed
    embed = format_discord_embed(sync_data)
    assert "Daily Standup" in embed["title"]
    assert len(embed["fields"]) == 2
