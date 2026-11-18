"""Tests for synlynk/roadmap_studio.py — Roadmap Studio's Vizor-side read/write layer.

See docs/superpowers/specs/2026-11-15-roadmap-studio-visual-proposal-ui-design.md.
"""
import json
import sqlite3

import pytest
import synlynk as sl


def _seed(conn):
    conn.execute(
        """CREATE TABLE IF NOT EXISTS stories (
            story_id TEXT PRIMARY KEY,
            title TEXT,
            role TEXT,
            readiness TEXT,
            status TEXT,
            priority INTEGER DEFAULT 5,
            estimated_tokens INTEGER,
            gh_issue TEXT,
            proposal_order INTEGER
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS approval_tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            story_id TEXT,
            action TEXT,
            issue_url TEXT,
            status TEXT,
            opened_at TIMESTAMP,
            resolved_at TIMESTAMP,
            constituent_story_ids TEXT,
            theme TEXT
        )"""
    )
    conn.execute(
        "INSERT INTO stories (story_id, title, role, readiness, status, priority) VALUES "
        "('s1','Task 1','dev','ready','open',5), "
        "('s2','Task 2','qa','ready','open',5), "
        "('s3','Task 3','dev','advisory','open',5), "
        "('s4','Task 4','dev','draft','done',5)"
    )
    conn.execute(
        "INSERT INTO approval_tickets (id, story_id, action, issue_url, status, constituent_story_ids, theme) VALUES "
        "(1, 'v0.33.0', 'release_proposal', 'https://github.com/test/1', 'open', ?, 'Test Theme')",
        (json.dumps(["s1", "s2"]),),
    )
    conn.commit()


def test_studio_data_returns_open_tickets_and_backlog(tmp_path):
    db_file = tmp_path / "state.db"
    conn = sl._get_db(str(db_file))
    conn.row_factory = sqlite3.Row
    try:
        _seed(conn)
        from synlynk.roadmap_studio import studio_data

        data = studio_data(conn=conn)
        assert len(data["tickets"]) == 1
        ticket = data["tickets"][0]
        assert ticket["id"] == 1
        assert ticket["release_version"] == "v0.33.0"
        assert ticket["theme"] == "Test Theme"
        story_ids = {s["story_id"] for s in ticket["stories"]}
        assert story_ids == {"s1", "s2"}
        # s3 is advisory and unclaimed -> backlog. s4 is draft but status='done' -> excluded.
        backlog_ids = {s["story_id"] for s in data["backlog"]}
        assert backlog_ids == {"s3"}
    finally:
        conn.close()


def test_studio_data_returns_none_for_unset_ticket_theme(tmp_path):
    db_file = tmp_path / "state.db"
    conn = sl._get_db(str(db_file))
    conn.row_factory = sqlite3.Row
    try:
        _seed(conn)
        conn.execute("UPDATE approval_tickets SET theme=NULL WHERE id=1")
        conn.commit()

        from synlynk.roadmap_studio import studio_data

        assert studio_data(conn=conn)["tickets"][0]["theme"] is None
    finally:
        conn.close()


def test_studio_data_sorts_tickets_naturally_by_version(tmp_path):
    db_file = tmp_path / "state.db"
    conn = sl._get_db(str(db_file))
    conn.row_factory = sqlite3.Row
    try:
        _seed(conn)
        # Insert out of order: v0.40.0, v0.39.0, v0.39.1
        conn.execute(
            "INSERT INTO approval_tickets (id, story_id, action, issue_url, status, constituent_story_ids, theme) VALUES "
            "(2, 'v0.40.0', 'release_proposal', 'https://github.com/test/2', 'held', '[]', 'Theme 40'), "
            "(3, 'v0.39.0', 'release_proposal', 'https://github.com/test/3', 'held', '[]', 'Theme 39'), "
            "(4, 'v0.39.1', 'release_proposal', 'https://github.com/test/4', 'held', '[]', 'Theme 39.1')"
        )
        conn.commit()

        from synlynk.roadmap_studio import studio_data

        versions = [t["release_version"] for t in studio_data(conn=conn)["tickets"]]
        assert versions == ["v0.33.0", "v0.39.0", "v0.39.1", "v0.40.0"]
    finally:
        conn.close()


def test_approve_ticket_resolves_only_that_ticket(tmp_path):
    db_file = tmp_path / "state.db"
    conn = sl._get_db(str(db_file))
    conn.row_factory = sqlite3.Row
    try:
        _seed(conn)
        conn.execute(
            "INSERT INTO approval_tickets (id, story_id, action, issue_url, status, constituent_story_ids) VALUES "
            "(2, 'v0.33.1', 'release_proposal', 'https://github.com/test/2', 'open', ?)",
            (json.dumps(["s3"]),),
        )
        conn.commit()

        from synlynk.roadmap_studio import approve_ticket

        result = approve_ticket(1, conn=conn)
        assert result["ok"] is True
        assert result["promoted_count"] == 2
        statuses = {r[0]: r[1] for r in conn.execute("SELECT id, status FROM approval_tickets").fetchall()}
        assert statuses[1] == "resolved"
        assert statuses[2] == "open"
        readiness = {r[0]: r[1] for r in conn.execute("SELECT story_id, readiness FROM stories").fetchall()}
        assert readiness["s1"] == "ready"
        assert readiness["s2"] == "ready"
        assert readiness["s3"] == "advisory"
    finally:
        conn.close()


def test_approve_ticket_raises_keyerror_for_unknown_ticket(tmp_path):
    db_file = tmp_path / "state.db"
    conn = sl._get_db(str(db_file))
    conn.row_factory = sqlite3.Row
    try:
        _seed(conn)
        from synlynk.roadmap_studio import approve_ticket

        with pytest.raises(KeyError):
            approve_ticket(999, conn=conn)
    finally:
        conn.close()


def test_hold_ticket(tmp_path):
    db_file = tmp_path / "state.db"
    conn = sl._get_db(str(db_file))
    conn.row_factory = sqlite3.Row
    try:
        _seed(conn)
        from synlynk.roadmap_studio import hold_ticket

        result = hold_ticket(1, conn=conn)
        assert result["ok"] is True
        status = conn.execute("SELECT status FROM approval_tickets WHERE id=1").fetchone()[0]
        assert status == "held"
    finally:
        conn.close()


def test_revise_ticket_is_non_persistent(tmp_path):
    db_file = tmp_path / "state.db"
    conn = sl._get_db(str(db_file))
    conn.row_factory = sqlite3.Row
    try:
        _seed(conn)
        from synlynk.roadmap_studio import revise_ticket

        result = revise_ticket(1, "please split this into two releases", conn=conn)
        assert result == {
            "ok": True,
            "ticket_id": 1,
            "instructions": "please split this into two releases",
            "persisted": False,
        }
        # No table/column anywhere stores the instruction — ticket row is untouched.
        row = dict(conn.execute("SELECT * FROM approval_tickets WHERE id=1").fetchone())
        assert row["status"] == "open"
    finally:
        conn.close()


def test_drop_story(tmp_path):
    db_file = tmp_path / "state.db"
    conn = sl._get_db(str(db_file))
    conn.row_factory = sqlite3.Row
    try:
        _seed(conn)
        from synlynk.roadmap_studio import drop_story

        result = drop_story("s1", conn=conn)
        assert result["ok"] is True
        readiness = conn.execute("SELECT readiness FROM stories WHERE story_id='s1'").fetchone()[0]
        assert readiness == "deferred"
    finally:
        conn.close()


def test_reorder_stories_writes_sequential_proposal_order(tmp_path):
    db_file = tmp_path / "state.db"
    conn = sl._get_db(str(db_file))
    conn.row_factory = sqlite3.Row
    try:
        _seed(conn)
        from synlynk.roadmap_studio import reorder_stories

        result = reorder_stories(1, ["s2", "s1"], conn=conn)
        assert result["ok"] is True
        orders = {r[0]: r[1] for r in conn.execute("SELECT story_id, proposal_order FROM stories WHERE story_id IN ('s1','s2')").fetchall()}
        assert orders == {"s2": 0, "s1": 1}
    finally:
        conn.close()


def test_reorder_stories_rejects_story_not_in_ticket(tmp_path):
    db_file = tmp_path / "state.db"
    conn = sl._get_db(str(db_file))
    conn.row_factory = sqlite3.Row
    try:
        _seed(conn)
        from synlynk.roadmap_studio import reorder_stories

        with pytest.raises(ValueError):
            reorder_stories(1, ["s1", "s3"], conn=conn)
    finally:
        conn.close()


def test_pin_story_appends_to_constituent_story_ids(tmp_path):
    db_file = tmp_path / "state.db"
    conn = sl._get_db(str(db_file))
    conn.row_factory = sqlite3.Row
    try:
        _seed(conn)
        from synlynk.roadmap_studio import pin_story

        result = pin_story(1, "s3", conn=conn)
        assert result["ok"] is True
        assert result["over_cap"] is False
        raw = conn.execute("SELECT constituent_story_ids FROM approval_tickets WHERE id=1").fetchone()[0]
        assert set(json.loads(raw)) == {"s1", "s2", "s3"}
    finally:
        conn.close()


def test_pin_story_flags_over_cap_but_still_pins(tmp_path):
    db_file = tmp_path / "state.db"
    conn = sl._get_db(str(db_file))
    conn.row_factory = sqlite3.Row
    try:
        _seed(conn)
        conn.execute(
            "INSERT INTO stories (story_id, title, role, readiness, status, priority) VALUES "
            "('s5','Task 5','dev','advisory','open',5), "
            "('s6','Task 6','dev','advisory','open',5), "
            "('s7','Task 7','dev','advisory','open',5)"
        )
        conn.execute(
            "UPDATE approval_tickets SET constituent_story_ids=? WHERE id=1",
            (json.dumps(["s1", "s2", "s3", "s5", "s6"]),),
        )
        conn.commit()
        from synlynk.roadmap_studio import pin_story

        result = pin_story(1, "s7", conn=conn)
        assert result["ok"] is True
        assert result["over_cap"] is True
        raw = conn.execute("SELECT constituent_story_ids FROM approval_tickets WHERE id=1").fetchone()[0]
        assert len(json.loads(raw)) == 6
    finally:
        conn.close()


def test_pin_story_is_idempotent(tmp_path):
    db_file = tmp_path / "state.db"
    conn = sl._get_db(str(db_file))
    conn.row_factory = sqlite3.Row
    try:
        _seed(conn)
        from synlynk.roadmap_studio import pin_story

        pin_story(1, "s1", conn=conn)
        raw = conn.execute("SELECT constituent_story_ids FROM approval_tickets WHERE id=1").fetchone()[0]
        assert json.loads(raw) == ["s1", "s2"]
    finally:
        conn.close()
