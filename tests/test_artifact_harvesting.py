import pytest
import sqlite3
import json
from pathlib import Path
from synlynk import _get_db
from synlynk.db import cmd_decision_record

def test_decisions_table_has_goal_and_story_columns(tmp_path, monkeypatch):
    test_db = tmp_path / "state.db"
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(test_db))
    conn = _get_db(db_path=str(test_db))
    cols = [r[1] for r in conn.execute("PRAGMA table_info(decisions)").fetchall()]
    assert "goal_id" in cols
    assert "story_id" in cols
    conn.close()

def test_cmd_decision_record_auto_binds_goal(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "project-docs" / "decisions").mkdir(parents=True, exist_ok=True)
    test_db = tmp_path / "state.db"
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(test_db))
    conn = _get_db(db_path=str(test_db))

    # Insert a parent goal
    conn.execute("INSERT OR IGNORE INTO goals (goal_id, outcome, criterion) VALUES ('goal-e3840370', 'Vizor Control Plane', 'ok')")
    conn.commit()

    # Record decision mentioning Vizor
    cmd_decision_record(
        decision_id="dec-test-123",
        topic="Vizor Canvas LOD Zoom Architecture",
        date="2026-09-26",
        panel=["agy", "claude"],
        inputs={"agy": "Recommend LOD zoom"},
        synthesis="LOD zoom is best",
        decision_text="Decision: Adopt LOD zoom",
    )

    row = conn.execute("SELECT decision_id, goal_id, topic FROM decisions WHERE decision_id='dec-test-123'").fetchone()
    assert row is not None
    assert row[1] == "goal-e3840370"
    conn.close()

def test_harvest_workspace_artifacts(tmp_path, monkeypatch):
    from synlynk.context import harvest_workspace_artifacts
    test_db = tmp_path / "state.db"
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(test_db))
    conn = _get_db(db_path=str(test_db))

    # Create dummy specs and plans directory
    specs_dir = tmp_path / "docs" / "superpowers" / "specs"
    specs_dir.mkdir(parents=True)
    spec_file = specs_dir / "2026-09-26-vizor-test-feature-design.md"
    spec_file.write_text("# Vizor Test Feature Design\n**Governing Goal:** `goal-e3840370`\n**Issue:** #9999\n")

    conn.execute("INSERT OR IGNORE INTO goals (goal_id, outcome, criterion) VALUES ('goal-e3840370', 'Vizor Control Plane', 'ok')")
    conn.commit()

    harvested = harvest_workspace_artifacts(repo_root=str(tmp_path), conn=conn)
    assert len(harvested) >= 1
    assert any(h["path"].endswith("2026-09-26-vizor-test-feature-design.md") and h["goal_id"] == "goal-e3840370" for h in harvested)
    conn.close()
