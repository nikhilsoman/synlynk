"""Tests for Sovereign Multi-Home Dynamic Handover and Drain-to-Boundary Protocol."""

import json
import sqlite3
from pathlib import Path

import pytest

from synlynk.handover import (
    calculate_drain_horizon,
    complete_harness_drain,
    execute_home_handover,
    is_harness_draining,
    load_handover_state,
    record_handover_state,
)
from synlynk.product_store import identity_slug_from_config


def test_calculate_drain_horizon_no_active_story(tmp_path):
    # Empty workspace without active story
    synlynk_dir = tmp_path / ".synlynk"
    synlynk_dir.mkdir()
    
    res = calculate_drain_horizon("agy", repo_path=tmp_path)
    assert res["harness"] == "agy"
    assert res["active_story"] is None
    assert res["draining"] is False
    assert res["drain_horizon_minutes"] == 0
    assert res["safe_to_switch_immediate"] is True


def test_calculate_drain_horizon_with_active_story(tmp_path):
    # Setup state.db with an in-progress story
    synlynk_dir = tmp_path / ".synlynk"
    synlynk_dir.mkdir()
    db_path = synlynk_dir / "state.db"
    
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE stories (id TEXT PRIMARY KEY, title TEXT, discipline TEXT, role TEXT, status TEXT, updated_at TEXT)"
    )
    conn.execute(
        "INSERT INTO stories (id, title, discipline, role, status, updated_at) "
        "VALUES ('story-1234', 'Active Test Story', 'dev', 'dev', 'in_progress', '2026-09-19T20:00:00Z')"
    )
    conn.commit()
    conn.close()

    res = calculate_drain_horizon("claude", repo_path=tmp_path)
    assert res["harness"] == "claude"
    assert res["active_story"] is not None
    assert res["active_story_id"] == "story-1234"
    assert res["draining"] is True
    assert res["drain_horizon_minutes"] > 0
    assert res["safe_to_switch_immediate"] is False


def test_execute_home_handover_drain_flow(tmp_path, monkeypatch):
    synlynk_dir = tmp_path / ".synlynk"
    synlynk_dir.mkdir()
    config_path = synlynk_dir / "config.json"
    config_path.write_text(json.dumps({"home_harness": "claude"}))
    
    # Active story in state.db
    db_path = synlynk_dir / "state.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE stories (id TEXT PRIMARY KEY, title TEXT, discipline TEXT, role TEXT, status TEXT, updated_at TEXT)"
    )
    conn.execute(
        "INSERT INTO stories (id, title, discipline, role, status, updated_at) "
        "VALUES ('story-5678', 'Active Migration', 'dev', 'dev', 'in_progress', '2026-09-19T20:00:00Z')"
    )
    conn.commit()
    conn.close()

    monkeypatch.chdir(tmp_path)
    
    # Execute handover from claude to agy
    res = execute_home_handover("agy", repo_path=tmp_path)
    assert res["status"] == "switched"
    assert res["incoming_harness"] == "agy"
    assert res["outgoing_harness"] == "claude"
    assert res["draining"] is True
    assert res["active_story_id"] == "story-5678"

    # Check handover.json persisted
    assert is_harness_draining("claude", repo_path=tmp_path) is True
    assert is_harness_draining("agy", repo_path=tmp_path) is False

    # Complete drain
    complete_harness_drain("claude", repo_path=tmp_path)
    assert is_harness_draining("claude", repo_path=tmp_path) is False


def test_worktree_identity_slug_resolution(tmp_path):
    # Test that identity slug resolves properly without host personal fallback
    repo = tmp_path / "main_repo"
    repo.mkdir()
    syn_dir = repo / ".synlynk"
    syn_dir.mkdir()
    (syn_dir / "config.json").write_text(json.dumps({"identity_slug": "synlynk"}))

    slug = identity_slug_from_config(repo)
    assert slug == "synlynk"
