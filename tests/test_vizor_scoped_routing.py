import http.server
import json
import sqlite3
import threading
from urllib.request import urlopen
from urllib.error import HTTPError

import pytest

from synlynk.vizor_daemon import build_workspace_routing_handler


@pytest.fixture
def running_test_server(tmp_path, monkeypatch):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    monkeypatch.setattr("synlynk.vizor_daemon.CACHE_ROOT", cache_dir)

    # Setup 2 workspaces in registry
    reg_file = tmp_path / "product-registry.json"
    repo1 = tmp_path / "repo1"
    repo1.mkdir()
    db1 = tmp_path / "db1.sqlite"
    c1 = sqlite3.connect(str(db1))
    c1.execute("CREATE TABLE stories (id INTEGER PRIMARY KEY, story_id TEXT, title TEXT, status TEXT, stage TEXT, governs_stage TEXT, goal_id TEXT, repo_id TEXT, type_id TEXT)")
    c1.execute("INSERT INTO stories (story_id, title) VALUES ('s1', 'Repo 1 Task')")
    c1.commit(); c1.close()

    repo2 = tmp_path / "repo2"
    repo2.mkdir()
    db2 = tmp_path / "db2.sqlite"
    c2 = sqlite3.connect(str(db2))
    c2.execute("CREATE TABLE stories (id INTEGER PRIMARY KEY, story_id TEXT, title TEXT, status TEXT, stage TEXT, governs_stage TEXT, goal_id TEXT, repo_id TEXT, type_id TEXT)")
    c2.execute("INSERT INTO stories (story_id, title) VALUES ('s2', 'Repo 2 Task')")
    c2.commit(); c2.close()

    reg_data = {
        "products": {
            "ws-one": {"slug": "ws-one", "repo_path": str(repo1), "canonical_path": str(db1)},
            "ws-two": {"slug": "ws-two", "repo_path": str(repo2), "canonical_path": str(db2)},
        },
        "version": 1,
    }
    reg_file.write_text(json.dumps(reg_data))
    monkeypatch.setenv("SYNLYNK_REGISTRY_PATH", str(reg_file))

    handler_cls = build_workspace_routing_handler()
    server = http.server.HTTPServer(("127.0.0.1", 0), handler_cls)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    yield port
    server.shutdown()
    server.server_close()


def test_scoped_api_board_returns_correct_workspace(running_test_server):
    port = running_test_server
    # Test ws-one
    with urlopen(f"http://127.0.0.1:{port}/w/ws-one/api/board") as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode())
        assert data["identity_slug"] == "ws-one"
        assert len(data["cards"]) == 1
        assert data["cards"][0]["story_id"] == "s1"

    # Test ws-two
    with urlopen(f"http://127.0.0.1:{port}/w/ws-two/api/board") as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode())
        assert data["identity_slug"] == "ws-two"
        assert len(data["cards"]) == 1
        assert data["cards"][0]["story_id"] == "s2"


def test_scoped_api_rejects_unknown_workspace(running_test_server):
    port = running_test_server
    with pytest.raises(HTTPError) as exc:
        urlopen(f"http://127.0.0.1:{port}/w/unknown-ws/api/board")
    assert exc.value.code == 404
