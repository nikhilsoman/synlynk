import sqlite3
import subprocess
from pathlib import Path

import pytest
from synlynk.db import _migrate_onboarding_sessions
from synlynk.onboarding_state import (
    STAGES,
    STAGE_S1_ORIENTATION,
    STAGE_S2_DEPENDENCIES,
    STAGE_S4_TOPOLOGY,
    get_or_create_session,
    advance_stage,
    propose_topology,
    confirm_topology,
    discover_and_confirm_topology,
    record_probe,
)
from synlynk.topology_discovery import ARCHETYPE_STANDALONE


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


@pytest.fixture
def mem_db():
    conn = sqlite3.connect(":memory:")
    _migrate_onboarding_sessions(conn)
    yield conn
    conn.close()


def test_get_or_create_session_resumable(mem_db):
    s1 = get_or_create_session(mem_db, "my-product")
    assert s1["product_id"] == "my-product"
    assert s1["current_stage"] == STAGE_S1_ORIENTATION

    # Advance stage
    s2 = advance_stage(mem_db, s1["session_id"], STAGE_S2_DEPENDENCIES)
    assert s2["current_stage"] == STAGE_S2_DEPENDENCIES

    # Re-calling get_or_create returns existing session at S2
    resumed = get_or_create_session(mem_db, "my-product")
    assert resumed["session_id"] == s1["session_id"]
    assert resumed["current_stage"] == STAGE_S2_DEPENDENCIES


def test_confirm_topology_persists(mem_db):
    session = get_or_create_session(mem_db, "my-product")
    candidate = {"archetype": "standalone", "workspaces": [{"slug": "my-product"}]}
    updated = confirm_topology(mem_db, session["session_id"], candidate)
    assert updated["topology_status"] == "confirmed"
    assert updated["topology_confirmed"]["archetype"] == "standalone"


def test_propose_topology_stores_discovery_candidate(mem_db, tmp_path):
    repo = _init_git_repo(tmp_path, "standalone-app")
    session = get_or_create_session(mem_db, "standalone-app")
    updated = propose_topology(mem_db, session["session_id"], str(repo))
    assert updated["topology_status"] == "proposed"
    assert updated["topology_candidate"]["archetype"] == ARCHETYPE_STANDALONE
    assert len(updated["topology_candidate"]["workspaces"]) == 1


def test_discover_and_confirm_topology_feeds_discovery_into_confirm(mem_db, tmp_path):
    repo = _init_git_repo(tmp_path, "standalone-app")
    session = get_or_create_session(mem_db, "standalone-app")
    updated = discover_and_confirm_topology(mem_db, session["session_id"], str(repo))
    assert updated["topology_status"] == "confirmed"
    assert updated["topology_candidate"]["archetype"] == ARCHETYPE_STANDALONE
    assert updated["topology_confirmed"]["archetype"] == ARCHETYPE_STANDALONE
    assert updated["topology_confirmed"]["workspaces"][0]["slug"] == "standalone-app"


def test_record_probe_persists(mem_db):
    session = get_or_create_session(mem_db, "my-product")
    res = record_probe(mem_db, session["session_id"], "harness", "claude", {"status": "ok", "version": "1.0"})
    assert "claude" in res["harness_probes"]
    assert res["harness_probes"]["claude"]["status"] == "ok"
