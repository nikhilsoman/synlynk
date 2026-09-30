import concurrent.futures
import http.server
import json
import os
from pathlib import Path
import sqlite3
import threading
from urllib.request import urlopen, Request
import pytest
from synlynk.vizor_daemon import build_workspace_routing_handler


def test_concurrent_multi_workspace_and_root_cwd(tmp_path, monkeypatch):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    monkeypatch.setattr("synlynk.vizor_daemon.CACHE_ROOT", cache_dir)

    # Workspace A: alpha
    repo_a = tmp_path / "alpha_repo"
    repo_a.mkdir()
    db_a = tmp_path / "alpha.db"
    ca = sqlite3.connect(str(db_a))
    ca.execute("CREATE TABLE stories (id INTEGER PRIMARY KEY, story_id TEXT, title TEXT, status TEXT, stage TEXT, governs_stage TEXT, goal_id TEXT, repo_id TEXT, type_id TEXT)")
    ca.execute("INSERT INTO stories (story_id, title, status, stage, governs_stage) VALUES ('alpha-1', 'Alpha Card', 'open', 'open', 'open')")
    ca.commit(); ca.close()

    # Workspace B: beta
    repo_b = tmp_path / "beta_repo"
    repo_b.mkdir()
    db_b = tmp_path / "beta.db"
    cb = sqlite3.connect(str(db_b))
    cb.execute("CREATE TABLE stories (id INTEGER PRIMARY KEY, story_id TEXT, title TEXT, status TEXT, stage TEXT, governs_stage TEXT, goal_id TEXT, repo_id TEXT, type_id TEXT)")
    cb.execute("INSERT INTO stories (story_id, title, status, stage, governs_stage) VALUES ('beta-1', 'Beta Card', 'open', 'open', 'open')")
    cb.commit(); cb.close()

    reg_file = tmp_path / "product-registry.json"
    reg_data = {
        "products": {
            "alpha": {"slug": "alpha", "repo_path": str(repo_a), "canonical_path": str(db_a)},
            "beta": {"slug": "beta", "repo_path": str(repo_b), "canonical_path": str(db_b)},
        },
        "version": 1
    }
    reg_file.write_text(json.dumps(reg_data))
    monkeypatch.setenv("SYNLYNK_REGISTRY_PATH", str(reg_file))

    # Simulate launchd CWD = /
    monkeypatch.chdir("/")

    server = http.server.HTTPServer(("127.0.0.1", 0), build_workspace_routing_handler())
    port = server.server_address[1]
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()

    try:
        def fetch_board(slug):
            url = f"http://127.0.0.1:{port}/w/{slug}/api/board"
            with urlopen(url) as r:
                return json.loads(r.read().decode())

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
            f_alpha = ex.submit(fetch_board, "alpha")
            f_beta = ex.submit(fetch_board, "beta")
            res_alpha = f_alpha.result()
            res_beta = f_beta.result()

        assert res_alpha["identity_slug"] == "alpha"
        assert res_alpha["cards"][0]["story_id"] == "alpha-1"

        assert res_beta["identity_slug"] == "beta"
        assert res_beta["cards"][0]["story_id"] == "beta-1"

        # Mutate alpha stage to execute
        req = Request(
            f"http://127.0.0.1:{port}/w/alpha/api/board/stage",
            data=json.dumps({"story_id": "alpha-1", "stage": "execute"}).encode(),
            headers={"Content-Type": "application/json"}
        )
        with urlopen(req) as r:
            assert r.status == 200

        # Verify alpha updated, beta unaffected
        res_alpha_2 = fetch_board("alpha")
        res_beta_2 = fetch_board("beta")
        assert res_alpha_2["cards"][0]["governs_stage"] == "execute"
        assert res_beta_2["cards"][0]["governs_stage"] == "open"

    finally:
        server.shutdown()
        server.server_close()
