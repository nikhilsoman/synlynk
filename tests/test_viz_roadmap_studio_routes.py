"""Smoke tests that the roadmap_studio module functions server.py delegates to
raise the same exception types _handle_board_status_request's pattern expects
(ValueError->400, KeyError->404), so the new _handle_roadmap_studio_* handlers
added in synlynk/viz/server.py behave consistently with the Board route handlers.
"""
import json
import sqlite3

import pytest
import synlynk as sl
from synlynk.roadmap_studio import approve_ticket, pin_story, reorder_stories


def _seed(conn):
    conn.execute(
        """CREATE TABLE IF NOT EXISTS stories (
            story_id TEXT PRIMARY KEY, title TEXT, role TEXT, readiness TEXT,
            status TEXT, priority INTEGER DEFAULT 5, estimated_tokens INTEGER,
            gh_issue TEXT, proposal_order INTEGER
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS approval_tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT, story_id TEXT, action TEXT,
            issue_url TEXT, status TEXT, opened_at TIMESTAMP, resolved_at TIMESTAMP,
            constituent_story_ids TEXT
        )"""
    )
    conn.execute("INSERT INTO stories (story_id, title, readiness, status) VALUES ('s1','T1','ready','open')")
    conn.execute(
        "INSERT INTO approval_tickets (id, story_id, action, issue_url, status, constituent_story_ids) "
        "VALUES (1, 'v1', 'release_proposal', 'https://x/1', 'open', ?)",
        (json.dumps(["s1"]),),
    )
    conn.commit()


def test_approve_ticket_raises_keyerror_maps_to_404_in_handler(tmp_path):
    conn = sl._get_db(str(tmp_path / "state.db"))
    conn.row_factory = sqlite3.Row
    try:
        _seed(conn)
        with pytest.raises(KeyError):
            approve_ticket(12345, conn=conn)
    finally:
        conn.close()


def test_reorder_stories_raises_valueerror_maps_to_400_in_handler(tmp_path):
    conn = sl._get_db(str(tmp_path / "state.db"))
    conn.row_factory = sqlite3.Row
    try:
        _seed(conn)
        with pytest.raises(ValueError):
            reorder_stories(1, ["not-a-member"], conn=conn)
    finally:
        conn.close()


def test_pin_story_returns_ok_dict_shape_handler_passes_through(tmp_path):
    conn = sl._get_db(str(tmp_path / "state.db"))
    conn.row_factory = sqlite3.Row
    try:
        _seed(conn)
        result = pin_story(1, "s1", conn=conn)
        assert result == {"ok": True, "ticket_id": 1, "story_id": "s1", "over_cap": False}
    finally:
        conn.close()
