import sqlite3
import subprocess
from pathlib import Path

from synlynk.topology_discovery import discover_topology, ARCHETYPE_CONTAINER, ARCHETYPE_MONOREPO
from synlynk.onboarding_state import get_or_create_session, advance_stage, STAGES
from synlynk.probe_binding import probe_all_dependencies, probe_all_harnesses
from synlynk.fleet_templates import apply_fleet_template
from synlynk.first_win_loop import verify_first_win_effect
from synlynk.db import _migrate_onboarding_sessions


def _init_git_repo(path: Path) -> None:
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True, capture_output=True)


def test_full_onboarding_matrix(tmp_path):
    # 1. Setup multi-project container ~/dev
    dev_dir = tmp_path / "dev"
    dev_dir.mkdir()
    p1 = dev_dir / "proj1"
    p1.mkdir()
    _init_git_repo(p1)
    (p1 / "README.md").write_text("# Proj 1\n")
    subprocess.run(["git", "add", "README.md"], cwd=p1, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Init"], cwd=p1, check=True, capture_output=True)

    # 2. Topology discovery
    topo = discover_topology(str(dev_dir))
    assert topo["archetype"] == ARCHETYPE_CONTAINER
    assert len(topo["workspaces"]) == 1

    # 3. Probe dependencies & harnesses
    deps = probe_all_dependencies()
    assert "git" in deps
    harnesses = probe_all_harnesses()
    assert "codex" in harnesses

    # 4. State session advancement
    db_path = p1 / ".synlynk" / "state.db"
    db_path.parent.mkdir(parents=True)
    conn = sqlite3.connect(str(db_path))
    _migrate_onboarding_sessions(conn)

    session = get_or_create_session(conn, "proj1")
    for stg in STAGES[1:]:
        session = advance_stage(conn, session["session_id"], stg)
    assert session["current_stage"] == STAGES[-1]
    conn.close()

    # 5. Apply fleet template
    tpl_res = apply_fleet_template(str(p1), "saas_web")
    assert tpl_res["status"] == "applied"


def test_monorepo_first_win_matrix(tmp_path):
    # 1. Setup a monorepo structure
    repo = tmp_path / "mono-project"
    repo.mkdir()
    _init_git_repo(repo)
    (repo / "pnpm-workspace.yaml").write_text("packages:\n  - 'packages/*'\n")
    (repo / "README.md").write_text("# Mono Project\n")
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Init"], cwd=repo, check=True, capture_output=True)

    # 2. Topology discovery identifies the monorepo archetype
    topo = discover_topology(str(repo))
    assert topo["archetype"] == ARCHETYPE_MONOREPO
    assert len(topo["workspaces"]) == 1

    # 3. Simulate a first-win build producing a real diff on a branch
    subprocess.run(["git", "checkout", "-b", "feat/first-win"], cwd=repo, check=True, capture_output=True)
    (repo / "CONTRIBUTING.md").write_text("# Contributing Guide\n")
    subprocess.run(["git", "add", "CONTRIBUTING.md"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "docs: add contributing guide"], cwd=repo, check=True, capture_output=True)

    # 4. Verify the first-win effect is detected
    assert verify_first_win_effect(str(repo), "feat/first-win", base_branch="HEAD~1") is True
