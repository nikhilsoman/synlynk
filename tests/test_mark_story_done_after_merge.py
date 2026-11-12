import json
import sqlite3
import pytest

from synlynk.events import _sync_merged_pr_stories, scan_local_events


@pytest.fixture
def test_db(tmp_path, monkeypatch):
    """Set up an isolated test DB with stories table."""
    db_path = str(tmp_path / "state.db")
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE stories ("
        "  story_id TEXT PRIMARY KEY, "
        "  title TEXT, "
        "  status TEXT DEFAULT 'open', "
        "  gh_issue TEXT, "
        "  goal_id TEXT, "
        "  created_at TEXT DEFAULT CURRENT_TIMESTAMP"
        ")"
    )
    conn.execute(
        "CREATE TABLE events ("
        "  id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "  event_type TEXT, "
        "  payload_json TEXT, "
        "  emitted_by TEXT, "
        "  created_at TEXT DEFAULT CURRENT_TIMESTAMP, "
        "  parent_event_id INTEGER"
        ")"
    )
    conn.execute(
        "CREATE TABLE subscriptions ("
        "  harness_name TEXT, "
        "  event_type TEXT, "
        "  last_seen_event_id INTEGER, "
        "  PRIMARY KEY (harness_name, event_type)"
        ")"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS goals ("
        "  goal_id TEXT PRIMARY KEY, "
        "  outcome TEXT"
        ")"
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr("synlynk._get_db", lambda *a, **k: sqlite3.connect(db_path))
    monkeypatch.setattr("synlynk.db._get_db", lambda *a, **k: sqlite3.connect(db_path))
    return db_path


def test_sync_merged_pr_stories_by_story_id(test_db):
    """Detects explicit story-id in PR body and marks it done."""
    conn = sqlite3.connect(test_db)
    conn.execute(
        "INSERT INTO stories (story_id, title, status) VALUES ('story-alpha-123', 'Alpha Task', 'open')"
    )
    conn.commit()
    conn.close()

    synced = _sync_merged_pr_stories(
        pr_number=501,
        pr_title="feat: implement alpha",
        pr_body="Part of roadmap milestone, completing story-alpha-123.",
    )

    assert "story-alpha-123" in synced

    conn = sqlite3.connect(test_db)
    status = conn.execute("SELECT status FROM stories WHERE story_id='story-alpha-123'").fetchone()[0]
    conn.close()
    assert status == "done"


def test_sync_merged_pr_stories_by_gh_issue_reference(test_db):
    """Detects Closes #<issue> in PR body and marks linked story done."""
    conn = sqlite3.connect(test_db)
    conn.execute(
        "INSERT INTO stories (story_id, title, status, gh_issue) VALUES ('story-beta-456', 'Beta Fix', 'open', '4999')"
    )
    conn.commit()
    conn.close()

    synced = _sync_merged_pr_stories(
        pr_number=502,
        pr_title="fix: resolve memory leak",
        pr_body="Fixes memory leak on agent dispatch. Closes #4999.",
    )

    assert "story-beta-456" in synced

    conn = sqlite3.connect(test_db)
    status = conn.execute("SELECT status FROM stories WHERE story_id='story-beta-456'").fetchone()[0]
    conn.close()
    assert status == "done"


def test_sync_merged_pr_stories_ignores_already_done(test_db):
    """Already completed stories are not redundantly processed."""
    conn = sqlite3.connect(test_db)
    conn.execute(
        "INSERT INTO stories (story_id, title, status) VALUES ('story-gamma-789', 'Gamma Done', 'done')"
    )
    conn.commit()
    conn.close()

    synced = _sync_merged_pr_stories(
        pr_number=503,
        pr_title="chore: cleanup",
        pr_body="Related to story-gamma-789.",
    )

    assert synced == []
