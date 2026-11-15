"""Tests for Autonomous Post-Release SOP Engine."""

import json
import sqlite3
import pytest
from synlynk.release_sop import (
    get_current_repo_version,
    extract_release_notes,
    create_and_push_git_tag,
    publish_github_release,
    mark_milestone_shipped_in_db,
    execute_post_release_sop,
)
from synlynk.tpm_sweep import check_and_trigger_post_release


def test_get_current_repo_version(tmp_path):
    vfile = tmp_path / "VERSION"
    vfile.write_text("0.33.0\n", encoding="utf-8")
    assert get_current_repo_version(str(tmp_path)) == "0.33.0"


def test_extract_release_notes_from_changelog(tmp_path):
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(
        "# Changelog\n\n## [v0.32.5] - 2026-11-15\n\n### Added\n- Feature A\n- Feature B\n\n## [v0.32.4] - 2026-11-14\n\n### Fixed\n- Bug 1\n",
        encoding="utf-8",
    )
    notes = extract_release_notes("0.32.5", repo_root=str(tmp_path))
    assert "## [v0.32.5]" in notes
    assert "Feature A" in notes
    assert "Feature B" in notes
    assert "## [v0.32.4]" not in notes


def test_create_and_push_git_tag_dry_run():
    ok, msg = create_and_push_git_tag("0.33.0", dry_run=True)
    assert ok is True
    assert "[DRY-RUN]" in msg
    assert "v0.33.0" in msg


def test_publish_github_release_dry_run():
    ok, msg = publish_github_release("0.33.0", notes="Some notes", dry_run=True)
    assert ok is True
    assert "[DRY-RUN]" in msg


def test_mark_milestone_shipped_in_db(tmp_path):
    conn = sqlite3.connect(tmp_path / "test.db")
    conn.execute(
        "CREATE TABLE approval_tickets (id INTEGER PRIMARY KEY, story_id TEXT, action TEXT, status TEXT, shipped_at TIMESTAMP)"
    )
    conn.execute(
        "CREATE TABLE roadmap_phases (version TEXT, status TEXT)"
    )
    conn.execute(
        "INSERT INTO approval_tickets (story_id, action, status) VALUES ('v0.33.0', 'release_proposal', 'approved')"
    )
    conn.execute(
        "INSERT INTO roadmap_phases (version, status) VALUES ('v0.33.0', 'in_progress')"
    )
    conn.commit()

    count = mark_milestone_shipped_in_db("v0.33.0", conn=conn)
    assert count == 1

    ticket = conn.execute("SELECT status FROM approval_tickets WHERE story_id='v0.33.0'").fetchone()
    assert ticket[0] == "shipped"

    phase = conn.execute("SELECT status FROM roadmap_phases WHERE version='v0.33.0'").fetchone()
    assert phase[0] == "shipped"
    conn.close()


def test_execute_post_release_sop_dry_run(tmp_path):
    res = execute_post_release_sop(
        version="0.33.0",
        repo_root=str(tmp_path),
        dry_run=True,
        skip_marketing=True,
    )
    assert res["success"] is True
    assert res["version"] == "0.33.0"
    assert res["steps"]["git_tag"]["ok"] is True
    assert res["steps"]["gh_release"]["ok"] is True
    assert res["steps"]["db_closeout"]["ok"] is True


def test_check_and_trigger_post_release_all_done(tmp_path, monkeypatch):
    conn = sqlite3.connect(tmp_path / "test.db")
    conn.execute(
        "CREATE TABLE approval_tickets (id INTEGER PRIMARY KEY, story_id TEXT, action TEXT, status TEXT, constituent_story_ids TEXT)"
    )
    conn.execute(
        "CREATE TABLE stories (story_id TEXT PRIMARY KEY, status TEXT)"
    )
    stories = ["story-1", "story-2"]
    conn.execute(
        "INSERT INTO approval_tickets (story_id, action, status, constituent_story_ids) "
        "VALUES ('v0.33.0', 'release_proposal', 'approved', ?)",
        (json.dumps(stories),),
    )
    conn.execute("INSERT INTO stories VALUES ('story-1', 'done')")
    conn.execute("INSERT INTO stories VALUES ('story-2', 'merged')")
    conn.commit()

    called = []
    def mock_execute_sop(version=None, repo_root=".", dry_run=False):
        called.append(version)
        return {"success": True}

    monkeypatch.setattr("synlynk.release_sop.execute_post_release_sop", mock_execute_sop)

    res = check_and_trigger_post_release(conn=conn, repo_root=str(tmp_path))
    assert res is not None
    assert res["release_version"] == "v0.33.0"
    assert called == ["v0.33.0"]
    conn.close()


def test_check_and_trigger_post_release_pending_stories(tmp_path):
    conn = sqlite3.connect(tmp_path / "test.db")
    conn.execute(
        "CREATE TABLE approval_tickets (id INTEGER PRIMARY KEY, story_id TEXT, action TEXT, status TEXT, constituent_story_ids TEXT)"
    )
    conn.execute(
        "CREATE TABLE stories (story_id TEXT PRIMARY KEY, status TEXT)"
    )
    stories = ["story-1", "story-2"]
    conn.execute(
        "INSERT INTO approval_tickets (story_id, action, status, constituent_story_ids) "
        "VALUES ('v0.33.0', 'release_proposal', 'approved', ?)",
        (json.dumps(stories),),
    )
    conn.execute("INSERT INTO stories VALUES ('story-1', 'done')")
    conn.execute("INSERT INTO stories VALUES ('story-2', 'in_progress')")
    conn.commit()

    res = check_and_trigger_post_release(conn=conn, repo_root=str(tmp_path))
    assert res is None
    conn.close()
