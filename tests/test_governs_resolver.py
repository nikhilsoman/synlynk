import pytest
import sqlite3
import tempfile
import os
from synlynk import _get_db
from synlynk.db import cmd_goal_create

def test_resolve_explicit_goal(tmp_path, monkeypatch):
    from synlynk.governs_resolver import resolve_parent_goal
    test_db = tmp_path / "state.db"
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(test_db))
    conn = _get_db(db_path=str(test_db))
    
    goal_id, reason = resolve_parent_goal(explicit_goal="goal-custom123", conn=conn)
    assert goal_id == "goal-custom123"
    assert reason == "explicit_argument"
    conn.close()

def test_resolve_in_band_header(tmp_path, monkeypatch):
    from synlynk.governs_resolver import resolve_parent_goal
    test_db = tmp_path / "state.db"
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(test_db))
    conn = _get_db(db_path=str(test_db))
    
    spec_content = """# My Cool Feature Design
**Date:** 2026-09-26
**Governing Goal:** `goal-e3840370` (Vizor Control Plane)
**Issue:** #1787

## Context
Some description here.
"""
    spec_file = tmp_path / "test_spec.md"
    spec_file.write_text(spec_content)

    goal_id, reason = resolve_parent_goal(file_path=str(spec_file), conn=conn)
    assert goal_id == "goal-e3840370"
    assert reason == "in_band_header"
    conn.close()

def test_resolve_parent_story_link(tmp_path, monkeypatch):
    from synlynk.governs_resolver import resolve_parent_goal
    test_db = tmp_path / "state.db"
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(test_db))
    conn = _get_db(db_path=str(test_db))
    
    # Insert parent goal first
    conn.execute(
        "INSERT OR IGNORE INTO goals (goal_id, outcome, criterion) VALUES ('goal-e3840370', 'Vizor Control Plane', 'All views verified')"
    )
    # Insert story with goal_id
    conn.execute(
        "INSERT INTO stories (story_id, title, goal_id, gh_issue) VALUES (?, ?, ?, ?)",
        ("story-viz123", "Vizor Feature", "goal-e3840370", "1787")
    )
    conn.commit()

    goal_id, reason = resolve_parent_goal(story_id="story-viz123", conn=conn)
    assert goal_id == "goal-e3840370"
    assert reason == "parent_story_link"

    # Also resolve by issue number
    goal_id2, reason2 = resolve_parent_goal(issue_number=1787, conn=conn)
    assert goal_id2 == "goal-e3840370"
    assert reason2 == "parent_story_link"
    conn.close()

def test_resolve_domain_keyword_heuristic(tmp_path, monkeypatch):
    from synlynk.governs_resolver import resolve_parent_goal
    test_db = tmp_path / "state.db"
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(test_db))
    conn = _get_db(db_path=str(test_db))

    # Path matching vizor
    goal_id, reason = resolve_parent_goal(file_path="synlynk/viz_views.py", conn=conn)
    assert goal_id == "goal-e3840370"
    assert "domain_heuristic" in reason

    # Branch matching book
    goal_id2, reason2 = resolve_parent_goal(branch="feat/agy/docs-book-chapter-3", conn=conn)
    assert goal_id2 == "goal-0c4e96ff"
    assert "domain_heuristic" in reason2

    # DeepSeek / Jev keyword
    goal_id3, reason3 = resolve_parent_goal(text_content="Implement Jev policy router and TypeSafe model", conn=conn)
    assert goal_id3 == "goal-c7113f58"
    assert "domain_heuristic" in reason3
    conn.close()

def test_resolve_master_loop_fallback(tmp_path, monkeypatch):
    from synlynk.governs_resolver import resolve_parent_goal
    test_db = tmp_path / "state.db"
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(test_db))
    conn = _get_db(db_path=str(test_db))

    goal_id, reason = resolve_parent_goal(text_content="random generic task without keywords", conn=conn)
    assert goal_id == "goal-eacab0dc"
    assert reason == "master_loop_fallback"
    conn.close()
