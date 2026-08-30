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


def test_resolve_goal_uses_explicit_goal_id(db_conn):
    from synlynk.db import cmd_goal_create
    from synlynk.backlog_automation import resolve_goal
    goal_id = cmd_goal_create("Ship X", "X is shipped", role="pm")
    resolved_id, basis = resolve_goal(db_conn, goal_id=goal_id)
    assert resolved_id == goal_id
    assert "explicit" in basis


def test_resolve_goal_creates_new_goal_when_requested(db_conn):
    from synlynk.backlog_automation import resolve_goal
    resolved_id, basis = resolve_goal(
        db_conn, new_goal_outcome="Backlog stays current",
        new_goal_criterion="No discovered work sits unfiled for >1 session",
    )
    row = db_conn.execute("SELECT outcome FROM goals WHERE goal_id=?", (resolved_id,)).fetchone()
    assert row[0] == "Backlog stays current"
    assert "new goal created" in basis


def test_resolve_goal_returns_none_when_nothing_given(db_conn):
    from synlynk.backlog_automation import resolve_goal
    resolved_id, basis = resolve_goal(db_conn)
    assert resolved_id is None
    assert "no goal" in basis


def test_file_backlog_item_happy_path(db_conn):
    from synlynk.backlog_automation import file_backlog_item
    from synlynk.db import cmd_goal_create

    goal_id = cmd_goal_create("Ship X", "X is shipped", role="pm")

    search_result = MagicMock(returncode=0, stdout="[]", stderr="")
    create_result = MagicMock(returncode=0, stdout="https://github.com/nikhilsoman/synlynk/issues/9001\n", stderr="")
    repo_result = MagicMock(returncode=0, stdout="nikhilsoman/synlynk\n", stderr="")
    view_result = MagicMock(returncode=0, stdout="555", stderr="")
    subissue_result = MagicMock(returncode=0, stdout="{}", stderr="")

    # Call order matches file_backlog_item -> search_similar_issues, then
    # _create_github_issue's internal sequence: create, repo_view, id_view, sub_issue_post.
    with patch("subprocess.run", side_effect=[search_result, create_result, repo_result, view_result, subissue_result]):
        outcome = file_backlog_item(
            db_conn, title="Investigate flaky test", body="details here",
            source="marker", goal_id=goal_id, parent_issue=1198,
        )

    assert outcome["status"] == "filed"
    assert outcome["gh_issue_url"] == "https://github.com/nikhilsoman/synlynk/issues/9001"
    story = db_conn.execute(
        "SELECT title, goal_id FROM stories WHERE story_id=?", (outcome["story_id"],)
    ).fetchone()
    assert story == ("Investigate flaky test", goal_id)
    ledger_row = db_conn.execute(
        "SELECT status, gh_issue_url, story_id FROM backlog_proposals WHERE story_id=?",
        (outcome["story_id"],),
    ).fetchone()
    assert ledger_row == ("filed", outcome["gh_issue_url"], outcome["story_id"])


def test_file_backlog_item_skips_ledger_duplicate(db_conn):
    from synlynk.backlog_automation import file_backlog_item, compute_signal_hash, record_proposal
    h = compute_signal_hash("Already proposed thing", "marker")
    record_proposal(db_conn, signal_hash=h, title="Already proposed thing", source="marker",
                     status="declined", gh_issue_url=None, story_id=None, goal_id=None,
                     goal_match_basis=None, session_id=None)
    with patch("subprocess.run") as mock_run:
        outcome = file_backlog_item(db_conn, title="Already proposed thing", body="x", source="marker")
    assert outcome["status"] == "skipped_duplicate"
    mock_run.assert_not_called()


def test_file_backlog_item_skips_gh_title_duplicate(db_conn):
    from synlynk.backlog_automation import file_backlog_item
    search_result = MagicMock(
        returncode=0,
        stdout='[{"title": "Investigate flaky test", "url": "https://github.com/x/y/issues/42"}]',
        stderr="",
    )
    with patch("subprocess.run", return_value=search_result) as mock_run:
        outcome = file_backlog_item(db_conn, title="Investigate flaky test", body="x", source="marker")
    assert outcome["status"] == "skipped_duplicate_gh"
    assert outcome["gh_issue_url"] == "https://github.com/x/y/issues/42"
    # only the search call — no issue was created
    assert mock_run.call_count == 1
    assert mock_run.call_args[0][0][:3] == ["gh", "issue", "list"]


def test_collect_session_material_reads_closing_summary(db_conn, tmp_path, monkeypatch):
    from synlynk.backlog_automation import collect_session_material
    db_conn.execute(
        "INSERT INTO sessions (session_id, title, status, opened_at, closing_summary) "
        "VALUES (?, ?, 'closed', '2026-08-29T10:00:00', ?)",
        ("sess-1", "Test session", "Shipped X, discovered Y needs follow-up"),
    )
    db_conn.commit()
    material = collect_session_material(db_conn, "sess-1")
    assert material["closing_summary"] == "Shipped X, discovered Y needs follow-up"
    assert material["session_id"] == "sess-1"


def test_collect_session_material_missing_session(db_conn):
    from synlynk.backlog_automation import collect_session_material
    material = collect_session_material(db_conn, "does-not-exist")
    assert material is None


def test_cli_backlog_note_invokes_file_backlog_item(db_conn, capsys):
    from synlynk import cli
    with patch("synlynk.backlog_automation.file_backlog_item") as mock_file:
        mock_file.return_value = {"status": "filed", "gh_issue_url": "https://x/9001", "story_id": "backlog-abc"}
        cli.main(["backlog", "note", "Found a gap", "--body", "details"])
    mock_file.assert_called_once()
    _, kwargs = mock_file.call_args
    assert kwargs["title"] == "Found a gap"
    assert kwargs["body"] == "details"
    assert kwargs["source"] == "marker"
    out = capsys.readouterr().out
    assert "filed" in out
    assert "https://x/9001" in out


def test_cli_backlog_scan_session_prints_material(db_conn, capsys):
    from synlynk import cli
    db_conn.execute(
        "INSERT INTO sessions (session_id, title, status, opened_at, closing_summary) "
        "VALUES (?, ?, 'closed', '2026-08-29T10:00:00', ?)",
        ("sess-2", "Another session", "Nothing notable"),
    )
    db_conn.commit()
    cli.main(["backlog", "scan-session", "--session-id", "sess-2"])
    out = capsys.readouterr().out
    assert "Nothing notable" in out
