"""Smoke tests that the roadmap_studio module functions server.py delegates to
raise the same exception types _handle_board_status_request's pattern expects
(ValueError->400, KeyError->404), so the new _handle_roadmap_studio_* handlers
added in synlynk/viz/server.py behave consistently with the Board route handlers.
"""
import json
import http.server
import sqlite3
import threading
from urllib.request import urlopen

import pytest
import synlynk as sl
from synlynk.roadmap_studio import approve_ticket, pin_story, reorder_stories
from synlynk.vizor_daemon import build_workspace_routing_handler


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


def _serve(handler_cls):
    server = http.server.HTTPServer(("127.0.0.1", 0), handler_cls)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def _register_workspace(tmp_path, monkeypatch, *, slug="roadmap-test"):
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    config_dir = repo_path / ".synlynk"
    config_dir.mkdir()
    (config_dir / "config.json").write_text(json.dumps({"identity_slug": slug}))
    db_path = tmp_path / "state.db"
    registry_path = tmp_path / "product-registry.json"
    registry_path.write_text(
        json.dumps(
            {
                "version": 1,
                "products": {
                    slug: {
                        "slug": slug,
                        "repo_path": str(repo_path),
                        "canonical_path": str(db_path),
                    }
                },
            }
        )
    )
    monkeypatch.setenv("SYNLYNK_REGISTRY_PATH", str(registry_path))
    monkeypatch.setattr(
        "synlynk.vizor_daemon._registered_workspaces",
        lambda: {slug: {"repo_path": str(repo_path)}},
    )
    return slug, db_path


def test_scoped_get_returns_roadmap_studio_json_for_registered_workspace(tmp_path, monkeypatch):
    slug, db_path = _register_workspace(tmp_path, monkeypatch)
    conn = sqlite3.connect(db_path)
    try:
        _seed(conn)
    finally:
        conn.close()

    server = _serve(build_workspace_routing_handler())
    try:
        with urlopen(
            f"http://127.0.0.1:{server.server_port}/w/{slug}/api/roadmap_studio"
        ) as response:
            assert response.status == 200
            payload = json.loads(response.read().decode("utf-8"))
        assert payload["tickets"][0]["release_version"] == "v1"
        assert payload["tickets"][0]["stories"][0]["story_id"] == "s1"
    finally:
        server.shutdown()
        server.server_close()


def test_scoped_get_returns_empty_fallback_for_pre_migration_database(tmp_path, monkeypatch):
    slug, db_path = _register_workspace(tmp_path, monkeypatch)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "CREATE TABLE approval_tickets ("
            "id INTEGER PRIMARY KEY, story_id TEXT, action TEXT, issue_url TEXT, status TEXT)"
        )
        conn.execute(
            "CREATE TABLE stories (story_id TEXT PRIMARY KEY, title TEXT, readiness TEXT, status TEXT)"
        )
        conn.commit()
    finally:
        conn.close()

    server = _serve(build_workspace_routing_handler())
    try:
        with urlopen(
            f"http://127.0.0.1:{server.server_port}/w/{slug}/api/roadmap_studio"
        ) as response:
            assert response.status == 200
            assert json.loads(response.read().decode("utf-8")) == {
                "tickets": [],
                "backlog": [],
            }
    finally:
        server.shutdown()
        server.server_close()


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
