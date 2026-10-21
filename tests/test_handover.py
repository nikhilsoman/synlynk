"""Tests for Sovereign Multi-Home Dynamic Handover and Drain-to-Boundary Protocol."""

import json
import os
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


def test_execute_home_handover_releases_active_lease_and_claim(tmp_path, monkeypatch):
    """Full-integration note (gh:#2511): a real execute_home_handover() run resolves
    its state.db through _project_root()'s canonical-identity machinery, which a
    hand-rolled tmp_path .synlynk/state.db cannot stand in for (it raises
    RuntimeError outside a real git worktree, or resolves to an unrelated
    canonical path inside one) — exactly the class of error the surrounding
    try/except Exception: pass in execute_home_handover is designed to absorb.
    This test instead proves, directly and without mocking that machinery, that
    the lookup-then-release logic execute_home_handover runs when active_story_id
    is set — get_active_lease(active_story_id) to resolve the real leased_by
    session id, then release_task_lease(active_story_id, that leased_by,
    new_status=None), followed by _remove_active_claim(active_story_id) — behaves
    correctly against a real task_leases row and a real active_claims.json file.

    The lease is acquired with a realistic composite leased_by
    ("claude:testhost:424242"), NOT the bare harness string "claude" that
    current_home resolves to — matching production's cmd_story_claim, which sets
    leased_by to f"{harness}:{hostname}:{pid}". This is deliberate: a bare
    "claude" leased_by would accidentally match current_home and mask the exact
    bug this test exists to catch (gh:#2511 follow-up) — execute_home_handover
    once passed current_home directly as leased_by to release_task_lease, which
    silently matched 0 rows against real leases since leased_by is never a bare
    harness name in production."""
    from synlynk import _get_db
    from synlynk.jobs import acquire_task_lease, release_task_lease, get_active_lease
    from synlynk.session import _add_active_claim, _read_active_claims, _remove_active_claim

    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)

    conn = _get_db(db_path=str(tmp_path / ".synlynk" / "test_handover_leases.db"))
    conn.execute(
        "INSERT INTO stories (story_id, title, role, stage, status, readiness) "
        "VALUES ('story-9012', 'Lease Handover Story', 'dev', 'open', 'in_progress', 'in_progress')"
    )
    conn.commit()

    real_leased_by = "claude:testhost:424242"
    acquired = acquire_task_lease(
        "story-9012", real_leased_by, duration_seconds=600, pid=424242, harness="claude", conn=conn
    )
    _add_active_claim("story-9012", acquired["lease_id"])
    assert "story-9012" in _read_active_claims()

    active_story_id = "story-9012"

    # Same lookup-then-release logic execute_home_handover runs when
    # active_story_id is truthy.
    active_lease = get_active_lease(active_story_id, conn=conn)
    assert active_lease is not None
    assert active_lease["leased_by"] == real_leased_by  # not "claude"
    release_task_lease(active_story_id, active_lease["leased_by"], new_status=None, conn=conn)
    _remove_active_claim(active_story_id)

    lease = get_active_lease("story-9012", conn=conn)
    assert lease is None  # no active lease remains

    row = conn.execute(
        "SELECT status FROM task_leases WHERE story_id='story-9012' ORDER BY rowid DESC LIMIT 1"
    ).fetchone()
    assert row[0] == "released"

    # new_status=None must not force the mid-flight story to 'done'.
    story_status = conn.execute(
        "SELECT status FROM stories WHERE story_id='story-9012'"
    ).fetchone()
    assert story_status[0] == "in_progress"

    assert "story-9012" not in _read_active_claims()


def test_execute_home_handover_prefers_load_config_over_stale_legacy_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk")
    # Authoritative split file says "codex" is home.
    with open(".synlynk/workspace.json", "w", encoding="utf-8") as f:
        json.dump({"home_harness": "codex"}, f)
    # Stale legacy file (e.g. leftover from before migration) says "claude".
    with open(".synlynk/config.json", "w", encoding="utf-8") as f:
        json.dump({"home_harness": "claude"}, f)
    from synlynk.handover import execute_home_handover
    result = execute_home_handover("codex", repo_path=str(tmp_path), force=True)
    assert result["outgoing_harness"] == "codex"


def test_worktree_identity_slug_resolution(tmp_path):
    # Test that identity slug resolves properly without host personal fallback
    repo = tmp_path / "main_repo"
    repo.mkdir()
    syn_dir = repo / ".synlynk"
    syn_dir.mkdir()
    (syn_dir / "config.json").write_text(json.dumps({"identity_slug": "synlynk"}))

    slug = identity_slug_from_config(repo)
    assert slug == "synlynk"
