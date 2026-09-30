import sqlite3
from pathlib import Path
import pytest
from synlynk.vizor_daemon import WorkspaceContext
from synlynk.board import (
    board_data_for_context,
    update_stage_for_context,
    update_status_for_context,
)

@pytest.fixture
def sample_workspace(tmp_path):
    repo_dir = tmp_path / "repo_test"
    repo_dir.mkdir()
    db_path = tmp_path / "state.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE stories (
            id INTEGER PRIMARY KEY,
            story_id TEXT UNIQUE,
            title TEXT,
            status TEXT DEFAULT 'open',
            stage TEXT DEFAULT 'open',
            governs_stage TEXT DEFAULT 'open',
            goal_id TEXT,
            repo_id TEXT,
            type_id TEXT
        )
    """)
    conn.execute("""
        INSERT INTO stories (story_id, title, status, stage, governs_stage, goal_id)
        VALUES ('story-001', 'Test Story', 'open', 'open', 'open', 'goal-123')
    """)
    conn.commit()
    conn.close()
    return WorkspaceContext(slug="test-slug", repo_path=repo_dir, db_path=db_path)

def test_board_data_for_context_reads_explicit_db(sample_workspace):
    res = board_data_for_context(sample_workspace)
    assert res["identity_slug"] == "test-slug"
    assert len(res["cards"]) == 1
    assert res["cards"][0]["story_id"] == "story-001"
    assert res["filters"]["goals"] == ["goal-123"]

def test_update_stage_for_context_mutates_explicit_db(sample_workspace):
    ok = update_stage_for_context(sample_workspace, "story-001", "visualize")
    assert ok is True
    res = board_data_for_context(sample_workspace)
    assert res["cards"][0]["governs_stage"] == "visualize"

def test_update_status_for_context_mutates_explicit_db(sample_workspace):
    ok = update_status_for_context(sample_workspace, "story-001", "in_progress")
    assert ok is True
    res = board_data_for_context(sample_workspace)
    assert res["cards"][0]["status"] == "in_progress"

def test_board_data_for_context_filters(sample_workspace):
    # Match existing goal
    res = board_data_for_context(sample_workspace, goal_id="goal-123")
    assert len(res["cards"]) == 1
    # Non-matching goal
    res_none = board_data_for_context(sample_workspace, goal_id="non-existent")
    assert len(res_none["cards"]) == 0

def test_update_stage_invalid_value(sample_workspace):
    with pytest.raises(ValueError, match="invalid stage"):
        update_stage_for_context(sample_workspace, "story-001", "invalid-stage")

def test_update_status_invalid_value(sample_workspace):
    with pytest.raises(ValueError, match="invalid status"):
        update_status_for_context(sample_workspace, "story-001", "invalid-status")

def test_update_nonexistent_story_returns_false(sample_workspace):
    assert update_stage_for_context(sample_workspace, "ghost-story", "visualize") is False
    assert update_status_for_context(sample_workspace, "ghost-story", "done") is False

