import os
import sqlite3

import pytest


@pytest.fixture
def db_conn(tmp_path, monkeypatch):
    db_path = str(tmp_path / "state.db")
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", db_path)
    from synlynk import _get_db
    conn = _get_db()
    yield conn
    conn.close()


def test_backlog_proposals_table_exists(db_conn):
    cols = {row[1] for row in db_conn.execute("PRAGMA table_info(backlog_proposals)")}
    assert cols == {
        "id", "signal_hash", "title", "source", "status",
        "gh_issue_url", "story_id", "goal_id", "goal_match_basis",
        "session_id", "ts",
    }


from unittest.mock import MagicMock, patch


def test_compute_signal_hash_is_stable_and_source_sensitive():
    from synlynk.backlog_automation import compute_signal_hash
    h1 = compute_signal_hash("Fix the flaky retry test", "marker")
    h2 = compute_signal_hash("fix the FLAKY retry test", "marker")
    h3 = compute_signal_hash("Fix the flaky retry test", "session_close")
    assert h1 == h2  # normalized (case/whitespace insensitive)
    assert h1 != h3  # source is part of the hash


def test_has_ledger_duplicate_true_after_insert(db_conn):
    from synlynk.backlog_automation import compute_signal_hash, has_ledger_duplicate, record_proposal
    h = compute_signal_hash("Some discovered thing", "marker")
    assert has_ledger_duplicate(db_conn, h) is False
    record_proposal(
        db_conn, signal_hash=h, title="Some discovered thing", source="marker",
        status="declined", gh_issue_url=None, story_id=None, goal_id=None,
        goal_match_basis=None, session_id=None,
    )
    assert has_ledger_duplicate(db_conn, h) is True


def test_search_similar_issues_parses_gh_output():
    from synlynk.backlog_automation import search_similar_issues
    fake_result = MagicMock(returncode=0, stdout='[{"title": "Fix the flaky retry test", "url": "https://github.com/x/y/issues/42"}]')
    with patch("subprocess.run", return_value=fake_result) as mock_run:
        hits = search_similar_issues("Fix flaky retry test")
    assert hits == [{"title": "Fix the flaky retry test", "url": "https://github.com/x/y/issues/42"}]
    args = mock_run.call_args[0][0]
    assert args[:3] == ["gh", "issue", "list"]


def test_search_similar_issues_empty_on_gh_failure():
    from synlynk.backlog_automation import search_similar_issues
    fake_result = MagicMock(returncode=1, stdout="", stderr="rate limited")
    with patch("subprocess.run", return_value=fake_result):
        assert search_similar_issues("anything") == []
