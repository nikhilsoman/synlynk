import json
import os
import sqlite3
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from synlynk.db import _migrate_onboarding_sessions
from synlynk.onboarding_state import get_or_create_session
from synlynk.topology_discovery import (
    discover_topology,
    compute_affinity,
    classify_archetype,
    merge_candidate_workspaces,
    split_candidate_workspace,
    designate_primary_repo,
    ARCHETYPE_CONTAINER,
    ARCHETYPE_MONOREPO,
    ARCHETYPE_POLYREPO,
    ARCHETYPE_STANDALONE,
)
from synlynk.viz import VizorHandler


def _init_git_repo(path: Path, name: str) -> Path:
    repo_dir = path / name
    repo_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_dir, check=True, capture_output=True)
    (repo_dir / "README.md").write_text(f"# {name}\n")
    subprocess.run(["git", "add", "README.md"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_dir, check=True, capture_output=True)
    return repo_dir


def test_discover_standalone_repo(tmp_path):
    repo = _init_git_repo(tmp_path, "standalone-app")
    topo = discover_topology(str(repo))
    assert topo["archetype"] == ARCHETYPE_STANDALONE
    assert len(topo["workspaces"]) == 1
    assert topo["workspaces"][0]["slug"] == "standalone-app"
    assert topo["workspaces"][0]["primary_repo"] == str(repo.resolve())


def test_discover_monorepo(tmp_path):
    repo = _init_git_repo(tmp_path, "mono-project")
    (repo / "pnpm-workspace.yaml").write_text("packages:\n  - 'packages/*'\n")
    topo = discover_topology(str(repo))
    assert topo["archetype"] == ARCHETYPE_MONOREPO
    assert len(topo["workspaces"]) == 1
    assert topo["workspaces"][0]["slug"] == "mono-project"


def test_discover_container_directory_does_not_merge(tmp_path):
    dev_dir = tmp_path / "dev"
    dev_dir.mkdir()
    repo1 = _init_git_repo(dev_dir, "unrelated-proj1")
    repo2 = _init_git_repo(dev_dir, "unrelated-proj2")

    topo = discover_topology(str(dev_dir))
    assert topo["archetype"] == ARCHETYPE_CONTAINER
    # Distinct workspaces proposed; parent is NOT a workspace
    assert len(topo["workspaces"]) == 2
    slugs = {w["slug"] for w in topo["workspaces"]}
    assert slugs == {"unrelated-proj1", "unrelated-proj2"}


def test_discover_polyrepo_application_group(tmp_path):
    app_dir = tmp_path / "app-group"
    app_dir.mkdir()
    web_repo = _init_git_repo(app_dir, "myapp-web")
    api_repo = _init_git_repo(app_dir, "myapp-api")

    # Add strong signal: shared docker-compose referencing both
    compose = app_dir / "docker-compose.yml"
    compose.write_text("""
version: '3.8'
services:
  web:
    build: ./myapp-web
  api:
    build: ./myapp-api
""")

    topo = discover_topology(str(app_dir))
    assert topo["archetype"] == ARCHETYPE_POLYREPO
    assert len(topo["workspaces"]) == 1
    ws = topo["workspaces"][0]
    assert len(ws["repos"]) == 2
    assert str(web_repo.resolve()) in ws["repos"]
    assert str(api_repo.resolve()) in ws["repos"]


def test_topology_manual_override_merge_and_split(tmp_path):
    dev_dir = tmp_path / "dev"
    dev_dir.mkdir()
    repo1 = _init_git_repo(dev_dir, "svc1")
    repo2 = _init_git_repo(dev_dir, "svc2")

    topo = discover_topology(str(dev_dir))
    assert len(topo["workspaces"]) == 2

    # User manually merges svc1 and svc2 into 'my-system'
    merged = merge_candidate_workspaces(topo, ["svc1", "svc2"], "my-system", str(repo1.resolve()))
    assert len(merged["workspaces"]) == 1
    assert merged["workspaces"][0]["slug"] == "my-system"
    assert merged["workspaces"][0]["primary_repo"] == str(repo1.resolve())
    assert len(merged["workspaces"][0]["repos"]) == 2

    # User splits 'my-system' back into standalone
    split = split_candidate_workspace(merged, "my-system")
    assert len(split["workspaces"]) == 2


def test_viz_topology_confirm_runs_discovery_entry_point(tmp_path):
    """Integration: VizorHandler topology/confirm wires topology_discovery.

    Approach: call discovery before confirm_topology (confirm itself only
    persists). Empty/discover payloads hit discover_and_confirm_topology via
    the real viz/server.py entry point — not topology_discovery in isolation.
    """
    repo = _init_git_repo(tmp_path, "standalone-app")

    conn = sqlite3.connect(":memory:")
    _migrate_onboarding_sessions(conn)
    get_or_create_session(conn, "standalone-app")

    body = json.dumps({"target_path": str(repo), "discover": True}).encode("utf-8")

    with patch("synlynk.open_state_db", return_value=(conn, True)):
        handler = VizorHandler.__new__(VizorHandler)
        handler.server = MagicMock(server_port=27472)
        handler.require_auth = False
        handler.path = "/w/standalone-app/api/onboarding/topology/confirm"
        handler.requestline = ""
        handler.request_version = "HTTP/1.1"
        handler.client_address = ("127.0.0.1", 12345)
        handler.headers = {
            "Cookie": "synlynk_local_token=123",
            "Content-Length": str(len(body)),
        }
        handler.wfile = MagicMock()
        handler.rfile = MagicMock()
        handler.rfile.read.return_value = body
        handler._authorize_write = MagicMock(return_value=True)

        handler.do_POST()

    args, _ = handler.wfile.write.call_args_list[-1]
    data = json.loads(args[0].decode("utf-8"))
    assert data["topology_status"] == "confirmed"
    assert data["topology_candidate"]["archetype"] == ARCHETYPE_STANDALONE
    assert data["topology_confirmed"]["archetype"] == ARCHETYPE_STANDALONE
    assert data["topology_confirmed"]["workspaces"][0]["slug"] == "standalone-app"
    assert data["topology_confirmed"]["workspaces"][0]["primary_repo"] == str(repo.resolve())
