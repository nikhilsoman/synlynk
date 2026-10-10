import http.server
import json
import subprocess
import threading

import pytest

from synlynk.vizor_daemon import build_workspace_routing_handler


def test_boardroom_html_renders_cards():
    from synlynk.viz import generate_boardroom_html

    html = generate_boardroom_html(workspace_slug="synlynk", autonomy_mode="supervised")
    assert "Sovereign Boardroom" in html
    assert "Autonomy Dial" in html
    assert "Nikhil Soman" in html
    assert "synlynk" in html


def test_boardroom_html_marks_active_dial_mode():
    from synlynk.viz import generate_boardroom_html

    html = generate_boardroom_html(workspace_slug="synlynk", autonomy_mode="autonomous")
    assert "active" in html


@pytest.fixture
def genesis_key(tmp_path):
    key_path = tmp_path / "identity.key"
    subprocess.run(
        ["ssh-keygen", "-t", "ed25519", "-N", "", "-f", str(key_path)],
        check=True,
        capture_output=True,
    )
    return str(key_path), str(key_path) + ".pub"


@pytest.fixture
def running_board_server(tmp_path, monkeypatch):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    monkeypatch.setattr("synlynk.vizor_daemon.CACHE_ROOT", cache_dir)

    reg_file = tmp_path / "product-registry.json"
    repo1 = tmp_path / "repo1"
    repo1.mkdir()
    db1 = tmp_path / "db1.sqlite"
    import sqlite3

    conn = sqlite3.connect(str(db1))
    conn.execute(
        "CREATE TABLE stories (id INTEGER PRIMARY KEY, story_id TEXT, title TEXT, "
        "status TEXT, stage TEXT, governs_stage TEXT, goal_id TEXT, repo_id TEXT, type_id TEXT)"
    )
    conn.commit()
    conn.close()

    reg_data = {
        "products": {
            "board-ws": {"slug": "board-ws", "repo_path": str(repo1), "canonical_path": str(db1)},
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

    yield port, repo1

    server.shutdown()
    server.server_close()


def test_board_page_route_renders_boardroom_hud(running_board_server):
    from urllib.request import urlopen

    port, _ = running_board_server
    with urlopen(f"http://127.0.0.1:{port}/w/board-ws/board") as resp:
        assert resp.status == 200
        body = resp.read().decode()
        assert "Sovereign Boardroom" in body
        assert "board-ws" in body


def test_board_proposals_api_returns_pending(running_board_server):
    from urllib.request import urlopen

    port, repo1 = running_board_server
    proposals_dir = repo1 / ".synlynk" / "proposals"
    proposals_dir.mkdir(parents=True)
    (proposals_dir / "prop-aaa11111.json").write_text(
        json.dumps(
            {
                "proposal_id": "prop-aaa11111",
                "gate": "release_tag",
                "title": "Tag v0.24.0",
                "description": "Public autonomous release",
                "budget_usd": 0.0,
                "created_at": 1700000000.0,
                "status": "pending",
                "signer_identity": None,
                "signed_at": None,
                "receipt": None,
            }
        )
    )

    with urlopen(f"http://127.0.0.1:{port}/w/board-ws/api/board/proposals") as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode())
        assert len(data["proposals"]) == 1
        assert data["proposals"][0]["proposal_id"] == "prop-aaa11111"
        assert data["proposals"][0]["status"] == "pending"


def test_board_proposals_sign_api_signs_proposal(running_board_server, genesis_key):
    from urllib.request import urlopen, Request

    port, repo1 = running_board_server
    key_path, _pub_path = genesis_key

    proposals_dir = repo1 / ".synlynk" / "proposals"
    proposals_dir.mkdir(parents=True)
    (proposals_dir / "prop-bbb22222.json").write_text(
        json.dumps(
            {
                "proposal_id": "prop-bbb22222",
                "gate": "budget_topup",
                "title": "API Top-up",
                "description": "",
                "budget_usd": 50.0,
                "created_at": 1700000000.0,
                "status": "pending",
                "signer_identity": None,
                "signed_at": None,
                "receipt": None,
            }
        )
    )

    req = Request(
        f"http://127.0.0.1:{port}/w/board-ws/api/board/proposals/sign",
        data=json.dumps({"proposal_id": "prop-bbb22222", "key_path": key_path}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(req) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode())
        assert data["ok"] is True
        assert data["proposal"]["status"] == "approved"
        assert data["proposal"]["receipt"]
