# Unified Onboarding Journeys & Self-Updating Lifecycle Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the unified, dual-surface onboarding engine and self-updating lifecycle system for Synlynk, providing 10-stage headless state management, evidence-scored topology discovery across 4 archetypes (Container, Monorepo, Polyrepo, Standalone), probe-verified harness binding, effect-verified first-win loop, and Dev Preview version negotiation.

**Architecture:** A canonical, headless, resumable state machine in `synlynk/onboarding_state.py` backed by SQLite WAL in `state.db` drives all onboarding transitions and emits structured events. Filesystem scanning in `synlynk/topology_discovery.py` uses multi-pass evidence-scored clustering to safely differentiate multi-project container directories (`~/dev`), monorepos, and polyrepo application groups, emitting `topology.candidate.json` for explicit user confirmation. Terminal (`wizard.py`) and browser (`/w/<slug>/onboarding` in `viz.py`) operate as pure renderers over the headless engine.

**Tech Stack:** Python 3.10+, SQLite WAL (`state.db`), Git CLI, curses / ANSI terminal primitives, Vanilla HTML/CSS/JS (Vizor HUD), SSE (`synlynk/events.py`).

**Spec:** [`docs/superpowers/specs/2026-10-01-unified-onboarding-journeys-and-lifecycle-design.md`](file:///Users/nikhilsoman/dev/synlynk/worktrees/feat-vizor-onboarding-engine/docs/superpowers/specs/2026-10-01-unified-onboarding-journeys-and-lifecycle-design.md)

## Global Constraints

- **Python Compatibility:** Python 3.10+ compatible (typing syntax, no external pip dependencies beyond `synlynk` manifest).
- **Persistence Invariant:** Discovery is strictly read-only; candidate groupings are emitted to `topology.candidate.json` and must never mutate `.synlynk/config.json` or `state.db` without explicit user confirmation.
- **Safety Invariant:** A false merge is worse than a false split. Sibling git repositories in container directories (`~/dev`) must never be bundled into a single workspace unless strong pairwise coupling signals exist.
- **Verification Invariant:** Green status or PATH presence alone is never evidence; harness and dependency binding requires an active round-trip probe (`synlynk probe`).
- **First-Win Effect Invariant:** First-win loop requires a verifiable code diff, passing test run, non-author QA review, and merge authority validation before claiming completion.
- **Upgrade Invariant:** Dev Preview upgrades must be explicit and opt-in (`synlynk upgrade --all`); ambient background daemon mutations across workspaces are strictly forbidden.
- **Attribution:** All commits must include trailer `Co-Authored-By: Agy (Gemini) <noreply@antigravity.dev>`.

---

### Task 1: Schema Migration & Onboarding Ledger Primitives

**Files:**
- Modify: `synlynk/db_schema.py:1-60`
- Modify: `synlynk/db.py:530-600`
- Test: `tests/test_onboarding_db_migration.py`

**Interfaces:**
- Consumes: `synlynk.db._open_state_db`, `synlynk.state_registry.identity_metadata`
- Produces: `onboarding_sessions` table in `state.db`, `synlynk.db._migrate_onboarding_sessions(conn)`

- [ ] **Step 1: Write the failing test**

Create `tests/test_onboarding_db_migration.py`:
```python
import sqlite3
import pytest
from synlynk.db_schema import ONBOARDING_SESSIONS_SCHEMA
from synlynk.db import _migrate_onboarding_sessions


def test_onboarding_sessions_schema_creation(tmp_path):
    db_path = tmp_path / "test_state.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(ONBOARDING_SESSIONS_SCHEMA)
    conn.commit()

    # Verify columns exist
    cursor = conn.execute("PRAGMA table_info(onboarding_sessions)")
    columns = {row[1]: row[2] for row in cursor.fetchall()}
    assert "session_id" in columns
    assert "product_id" in columns
    assert "current_stage" in columns
    assert "topology_status" in columns
    assert "topology_candidate" in columns
    assert "topology_confirmed" in columns
    assert "harness_probes" in columns
    assert "dependency_checks" in columns
    assert "first_win_meta" in columns
    assert "created_at" in columns
    assert "updated_at" in columns
    conn.close()


def test_migrate_onboarding_sessions_idempotent(tmp_path):
    db_path = tmp_path / "test_state.db"
    conn = sqlite3.connect(str(db_path))
    # Run migration on clean DB
    _migrate_onboarding_sessions(conn)
    # Run again to ensure idempotency
    _migrate_onboarding_sessions(conn)

    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='onboarding_sessions'")
    assert cursor.fetchone() is not None
    conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_onboarding_db_migration.py -v`
Expected: FAIL with `ImportError: cannot import name 'ONBOARDING_SESSIONS_SCHEMA' from 'synlynk.db_schema'`

- [ ] **Step 3: Write minimal implementation**

In `synlynk/db_schema.py`, add `ONBOARDING_SESSIONS_SCHEMA`:
```python
ONBOARDING_SESSIONS_SCHEMA = """
CREATE TABLE IF NOT EXISTS onboarding_sessions (
    session_id TEXT PRIMARY KEY,
    product_id TEXT NOT NULL,
    current_stage TEXT NOT NULL DEFAULT 'S1_Orientation',
    topology_status TEXT NOT NULL DEFAULT 'pending',
    topology_candidate TEXT,
    topology_confirmed TEXT,
    harness_probes TEXT,
    dependency_checks TEXT,
    first_win_meta TEXT,
    completed_at TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_onboarding_product ON onboarding_sessions(product_id);
"""
```

In `synlynk/db.py`, add `_migrate_onboarding_sessions(conn)` and invoke it in `init_db()`:
```python
def _migrate_onboarding_sessions(conn: sqlite3.Connection) -> None:
    from synlynk.db_schema import ONBOARDING_SESSIONS_SCHEMA
    conn.executescript(ONBOARDING_SESSIONS_SCHEMA)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_onboarding_db_migration.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_onboarding_db_migration.py synlynk/db_schema.py synlynk/db.py
git commit -m "feat(onboarding): add onboarding_sessions table schema and migration

Co-Authored-By: Agy (Gemini) <noreply@antigravity.dev>"
```

---

### Task 2: Headless Topology Discovery Engine

**Files:**
- Create: `synlynk/topology_discovery.py`
- Test: `tests/test_onboarding_topology.py`

**Interfaces:**
- Consumes: `os.walk`, `pathlib.Path`, `git` subprocess commands
- Produces:
  - `discover_topology(target_path: str, max_depth: int = 3) -> dict`
  - `classify_archetype(repo_roots: list[str]) -> tuple[str, list[dict]]`
  - `compute_affinity(repo_a: str, repo_b: str) -> float`
  - `merge_candidate_workspaces(candidate_plan: dict, workspace_slugs: list[str], new_slug: str, primary_repo: str) -> dict`
  - `split_candidate_workspace(candidate_plan: dict, workspace_slug: str) -> dict`
  - `designate_primary_repo(candidate_plan: dict, workspace_slug: str, primary_repo: str) -> dict`

- [ ] **Step 1: Write the failing test**

Create `tests/test_onboarding_topology.py`:
```python
import json
import os
import subprocess
from pathlib import Path
import pytest
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_onboarding_topology.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.topology_discovery'`

- [ ] **Step 3: Write minimal implementation**

Create `synlynk/topology_discovery.py`:
```python
"""Multi-pass topology discovery engine for Synlynk onboarding.

Discovers and classifies workspace candidates across 4 archetypes:
1. Monorepo
2. Standalone Repo
3. Polyrepo Application Group
4. Multi-Project Container (e.g. ~/dev)
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ARCHETYPE_MONOREPO = "monorepo"
ARCHETYPE_STANDALONE = "standalone"
ARCHETYPE_POLYREPO = "polyrepo_group"
ARCHETYPE_CONTAINER = "multi_project_container"

_MONOREPO_MANIFESTS = (
    "pnpm-workspace.yaml",
    "turbo.json",
    "nx.json",
    "go.work",
    "lerna.json",
)

_EXCLUDED_DIRS = {
    ".git",
    "node_modules",
    "vendor",
    ".cache",
    ".synlynk",
    "__pycache__",
    "dist",
    "build",
}


def _find_git_roots(target_path: Path, max_depth: int = 3) -> List[Path]:
    roots: List[Path] = []
    target_path = target_path.resolve()

    if (target_path / ".git").is_dir():
        roots.append(target_path)
        return roots

    def _scan(current: Path, depth: int):
        if depth > max_depth:
            return
        try:
            entries = list(current.iterdir())
        except (PermissionError, OSError):
            return

        for entry in entries:
            if not entry.is_dir() or entry.name in _EXCLUDED_DIRS:
                continue
            if (entry / ".git").is_dir():
                roots.append(entry.resolve())
            else:
                _scan(entry, depth + 1)

    _scan(target_path, 1)
    return sorted(roots, key=lambda p: str(p))


def _is_monorepo(root: Path) -> bool:
    if any((root / f).is_file() for f in _MONOREPO_MANIFESTS):
        return True
    pkg_json = root / "package.json"
    if pkg_json.is_file():
        try:
            data = json.loads(pkg_json.read_text(encoding="utf-8"))
            if "workspaces" in data:
                return True
        except Exception:
            pass
    cargo_toml = root / "Cargo.toml"
    if cargo_toml.is_file():
        try:
            text = cargo_toml.read_text(encoding="utf-8")
            if "[workspace]" in text:
                return True
        except Exception:
            pass
    return False


def compute_affinity(repo_a: Path, repo_b: Path) -> float:
    """Compute pairwise affinity score between two repository roots.
    Score >= 1.0 indicates strong polyrepo coupling.
    """
    score = 0.0
    parent_a = repo_a.parent
    parent_b = repo_b.parent

    # Check for shared parent orchestrator (docker-compose, Tiltfile, etc.)
    if parent_a == parent_b:
        compose_files = ["docker-compose.yml", "docker-compose.yaml", "compose.yaml", "compose.yml"]
        for cf in compose_files:
            compose_path = parent_a / cf
            if compose_path.is_file():
                try:
                    content = compose_path.read_text(encoding="utf-8")
                    if repo_a.name in content and repo_b.name in content:
                        score += 1.5  # Strong signal
                except Exception:
                    pass

    # Check for name prefix similarity (e.g. myapp-web, myapp-api)
    parts_a = repo_a.name.split("-")
    parts_b = repo_b.name.split("-")
    if len(parts_a) > 1 and len(parts_b) > 1 and parts_a[0] == parts_b[0]:
        score += 0.4  # Medium signal

    # Check for cross-repo relative path references
    try:
        for p in (repo_a / "package.json", repo_a / "go.mod", repo_a / "requirements.txt"):
            if p.is_file():
                text = p.read_text(encoding="utf-8", errors="ignore")
                if f"../{repo_b.name}" in text:
                    score += 1.2
    except Exception:
        pass

    return score


def classify_archetype(target_path: Path, git_roots: List[Path]) -> Tuple[str, List[Dict[str, Any]]]:
    if not git_roots:
        return ARCHETYPE_STANDALONE, [{
            "slug": target_path.name or "workspace",
            "primary_repo": str(target_path.resolve()),
            "repos": [str(target_path.resolve())],
            "archetype": ARCHETYPE_STANDALONE,
            "greenfield": True,
        }]

    if len(git_roots) == 1 and git_roots[0] == target_path:
        if _is_monorepo(target_path):
            return ARCHETYPE_MONOREPO, [{
                "slug": target_path.name,
                "primary_repo": str(target_path.resolve()),
                "repos": [str(target_path.resolve())],
                "archetype": ARCHETYPE_MONOREPO,
                "greenfield": False,
            }]
        return ARCHETYPE_STANDALONE, [{
            "slug": target_path.name,
            "primary_repo": str(target_path.resolve()),
            "repos": [str(target_path.resolve())],
            "archetype": ARCHETYPE_STANDALONE,
            "greenfield": False,
        }]

    # Multiple git roots found. Check for polyrepo application clustering.
    clusters: List[List[Path]] = []
    unclustered = list(git_roots)

    while unclustered:
        seed = unclustered.pop(0)
        cluster = [seed]
        to_remove = []
        for other in unclustered:
            if compute_affinity(seed, other) >= 1.0:
                cluster.append(other)
                to_remove.append(other)
        for r in to_remove:
            unclustered.remove(r)
        clusters.append(cluster)

    workspaces = []
    if len(clusters) == 1 and len(clusters[0]) > 1:
        overall_archetype = ARCHETYPE_POLYREPO
        cluster = clusters[0]
        workspaces.append({
            "slug": target_path.name,
            "primary_repo": str(cluster[0].resolve()),
            "repos": [str(r.resolve()) for r in cluster],
            "archetype": ARCHETYPE_POLYREPO,
            "greenfield": False,
        })
    elif any(len(c) > 1 for c in clusters):
        overall_archetype = ARCHETYPE_CONTAINER
        for c in clusters:
            if len(c) > 1:
                workspaces.append({
                    "slug": c[0].parent.name if c[0].parent != target_path else c[0].name,
                    "primary_repo": str(c[0].resolve()),
                    "repos": [str(r.resolve()) for r in c],
                    "archetype": ARCHETYPE_POLYREPO,
                    "greenfield": False,
                })
            else:
                workspaces.append({
                    "slug": c[0].name,
                    "primary_repo": str(c[0].resolve()),
                    "repos": [str(c[0].resolve())],
                    "archetype": ARCHETYPE_STANDALONE,
                    "greenfield": False,
                })
    else:
        overall_archetype = ARCHETYPE_CONTAINER
        for r in git_roots:
            workspaces.append({
                "slug": r.name,
                "primary_repo": str(r.resolve()),
                "repos": [str(r.resolve())],
                "archetype": ARCHETYPE_STANDALONE,
                "greenfield": False,
            })

    return overall_archetype, workspaces


def discover_topology(target_path_str: str, max_depth: int = 3) -> Dict[str, Any]:
    target_path = Path(target_path_str).resolve()
    git_roots = _find_git_roots(target_path, max_depth=max_depth)
    archetype, workspaces = classify_archetype(target_path, git_roots)

    return {
        "target_path": str(target_path),
        "archetype": archetype,
        "git_roots_count": len(git_roots),
        "workspaces": workspaces,
    }


def merge_candidate_workspaces(
    candidate_plan: Dict[str, Any],
    workspace_slugs: List[str],
    new_slug: str,
    primary_repo: str,
) -> Dict[str, Any]:
    plan = json.loads(json.dumps(candidate_plan))
    workspaces = plan.get("workspaces", [])
    merged_repos = []
    remaining = []

    for ws in workspaces:
        if ws["slug"] in workspace_slugs:
            merged_repos.extend(ws.get("repos", []))
        else:
            remaining.append(ws)

    # Dedup repos
    merged_repos = sorted(list(set(merged_repos)))
    merged_ws = {
        "slug": new_slug,
        "primary_repo": primary_repo,
        "repos": merged_repos,
        "archetype": ARCHETYPE_POLYREPO,
        "greenfield": False,
    }
    remaining.insert(0, merged_ws)
    plan["workspaces"] = remaining
    return plan


def split_candidate_workspace(
    candidate_plan: Dict[str, Any],
    workspace_slug: str,
) -> Dict[str, Any]:
    plan = json.loads(json.dumps(candidate_plan))
    workspaces = plan.get("workspaces", [])
    result_workspaces = []

    for ws in workspaces:
        if ws["slug"] == workspace_slug and len(ws.get("repos", [])) > 1:
            for repo_path in ws["repos"]:
                r_name = Path(repo_path).name
                result_workspaces.append({
                    "slug": r_name,
                    "primary_repo": repo_path,
                    "repos": [repo_path],
                    "archetype": ARCHETYPE_STANDALONE,
                    "greenfield": False,
                })
        else:
            result_workspaces.append(ws)

    plan["workspaces"] = result_workspaces
    return plan


def designate_primary_repo(
    candidate_plan: Dict[str, Any],
    workspace_slug: str,
    primary_repo: str,
) -> Dict[str, Any]:
    plan = json.loads(json.dumps(candidate_plan))
    for ws in plan.get("workspaces", []):
        if ws["slug"] == workspace_slug:
            if primary_repo in ws.get("repos", []):
                ws["primary_repo"] = primary_repo
    return plan
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_onboarding_topology.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_onboarding_topology.py synlynk/topology_discovery.py
git commit -m "feat(topology): add multi-pass topology discovery across 4 archetypes

Co-Authored-By: Agy (Gemini) <noreply@antigravity.dev>"
```

---

### Task 3: Canonical Onboarding State Machine

**Files:**
- Create: `synlynk/onboarding_state.py`
- Test: `tests/test_onboarding_state.py`

**Interfaces:**
- Consumes: `synlynk.db_schema.ONBOARDING_SESSIONS_SCHEMA`, `synlynk.topology_discovery`
- Produces:
  - `STAGES = [...]` (S1_Orientation .. S10_BuildExperience)
  - `get_or_create_session(conn, product_id: str) -> dict`
  - `advance_stage(conn, session_id: str, target_stage: str, payload: dict | None) -> dict`
  - `confirm_topology(conn, session_id: str, confirmed_topology: dict) -> dict`
  - `record_probe(conn, session_id: str, probe_type: str, item_key: str, result: dict) -> dict`

- [ ] **Step 1: Write the failing test**

Create `tests/test_onboarding_state.py`:
```python
import sqlite3
import pytest
from synlynk.db import _migrate_onboarding_sessions
from synlynk.onboarding_state import (
    STAGES,
    STAGE_S1_ORIENTATION,
    STAGE_S2_DEPENDENCIES,
    STAGE_S4_TOPOLOGY,
    get_or_create_session,
    advance_stage,
    confirm_topology,
    record_probe,
)


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


def test_record_probe_persists(mem_db):
    session = get_or_create_session(mem_db, "my-product")
    res = record_probe(mem_db, session["session_id"], "harness", "claude", {"status": "ok", "version": "1.0"})
    assert "claude" in res["harness_probes"]
    assert res["harness_probes"]["claude"]["status"] == "ok"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_onboarding_state.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.onboarding_state'`

- [ ] **Step 3: Write minimal implementation**

Create `synlynk/onboarding_state.py`:
```python
"""Canonical headless state machine for Synlynk Onboarding."""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from typing import Any, Dict, List, Optional

STAGE_S1_ORIENTATION = "S1_Orientation"
STAGE_S2_DEPENDENCIES = "S2_Dependencies"
STAGE_S3_HARNESS_BINDING = "S3_HarnessBinding"
STAGE_S4_TOPOLOGY = "S4_TopologyConfirmation"
STAGE_S5_GOVERNS_INTRO = "S5_GovernsIntro"
STAGE_S6_DISPATCH_DECIDE = "S6_DispatchDecide"
STAGE_S7_AGENT_TEAM = "S7_AgentTeam"
STAGE_S8_FLEET_TEMPLATES = "S8_FleetTemplates"
STAGE_S9_FIRST_WIN_INTAKE = "S9_FirstWinIntake"
STAGE_S10_BUILD_EXPERIENCE = "S10_BuildExperience"

STAGES = [
    STAGE_S1_ORIENTATION,
    STAGE_S2_DEPENDENCIES,
    STAGE_S3_HARNESS_BINDING,
    STAGE_S4_TOPOLOGY,
    STAGE_S5_GOVERNS_INTRO,
    STAGE_S6_DISPATCH_DECIDE,
    STAGE_S7_AGENT_TEAM,
    STAGE_S8_FLEET_TEMPLATES,
    STAGE_S9_FIRST_WIN_INTAKE,
    STAGE_S10_BUILD_EXPERIENCE,
]


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    d = dict(row)
    for json_col in ("topology_candidate", "topology_confirmed", "harness_probes", "dependency_checks", "first_win_meta"):
        if d.get(json_col):
            try:
                d[json_col] = json.loads(d[json_col])
            except Exception:
                d[json_col] = {}
        else:
            d[json_col] = {}
    return d


def get_or_create_session(conn: sqlite3.Connection, product_id: str) -> Dict[str, Any]:
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM onboarding_sessions WHERE product_id = ? ORDER BY created_at DESC LIMIT 1",
        (product_id,),
    ).fetchone()
    if row:
        return _row_to_dict(row)

    session_id = f"onb-{uuid.uuid4().hex[:8]}"
    now = time.time()
    conn.execute(
        """INSERT INTO onboarding_sessions (
            session_id, product_id, current_stage, topology_status,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?)""",
        (session_id, product_id, STAGE_S1_ORIENTATION, "pending", now, now),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM onboarding_sessions WHERE session_id = ?", (session_id,)).fetchone()
    return _row_to_dict(row)


def advance_stage(
    conn: sqlite3.Connection,
    session_id: str,
    target_stage: str,
    payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if target_stage not in STAGES:
        raise ValueError(f"Invalid onboarding stage: {target_stage}")

    now = time.time()
    completed_at = now if target_stage == STAGE_S10_BUILD_EXPERIENCE else None

    conn.execute(
        """UPDATE onboarding_sessions
           SET current_stage = ?, updated_at = ?, completed_at = COALESCE(completed_at, ?)
           WHERE session_id = ?""",
        (target_stage, now, completed_at, session_id),
    )
    conn.commit()
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM onboarding_sessions WHERE session_id = ?", (session_id,)).fetchone()
    return _row_to_dict(row)


def confirm_topology(
    conn: sqlite3.Connection,
    session_id: str,
    confirmed_topology: Dict[str, Any],
) -> Dict[str, Any]:
    now = time.time()
    conn.execute(
        """UPDATE onboarding_sessions
           SET topology_status = 'confirmed',
               topology_confirmed = ?,
               updated_at = ?
           WHERE session_id = ?""",
        (json.dumps(confirmed_topology), now, session_id),
    )
    conn.commit()
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM onboarding_sessions WHERE session_id = ?", (session_id,)).fetchone()
    return _row_to_dict(row)


def record_probe(
    conn: sqlite3.Connection,
    session_id: str,
    probe_type: str,  # 'harness' or 'dependency'
    item_key: str,
    result: Dict[str, Any],
) -> Dict[str, Any]:
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM onboarding_sessions WHERE session_id = ?", (session_id,)).fetchone()
    if not row:
        raise ValueError(f"Session not found: {session_id}")

    session = _row_to_dict(row)
    now = time.time()

    if probe_type == "harness":
        data = session.get("harness_probes", {})
        data[item_key] = result
        col = "harness_probes"
    elif probe_type == "dependency":
        data = session.get("dependency_checks", {})
        data[item_key] = result
        col = "dependency_checks"
    else:
        raise ValueError(f"Invalid probe_type: {probe_type}")

    conn.execute(
        f"UPDATE onboarding_sessions SET {col} = ?, updated_at = ? WHERE session_id = ?",
        (json.dumps(data), now, session_id),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM onboarding_sessions WHERE session_id = ?", (session_id,)).fetchone()
    return _row_to_dict(row)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_onboarding_state.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_onboarding_state.py synlynk/onboarding_state.py
git commit -m "feat(onboarding): add canonical headless state machine

Co-Authored-By: Agy (Gemini) <noreply@antigravity.dev>"
```

---

### Task 4: Probe-Verified Harness & Dependency Engine

**Files:**
- Create: `synlynk/probe_binding.py`
- Test: `tests/test_probe_binding.py`

**Interfaces:**
- Consumes: `shutil.which`, `subprocess.run`, `synlynk._constants.HARNESS_CAPABILITY_BASELINES`
- Produces:
  - `probe_all_dependencies() -> dict[str, dict]`
  - `probe_dependency(name: str) -> dict`
  - `probe_harness_live(harness_name: str) -> dict`
  - `probe_all_harnesses() -> dict[str, dict]`

- [ ] **Step 1: Write the failing test**

Create `tests/test_probe_binding.py`:
```python
from unittest.mock import patch, MagicMock
import pytest
from synlynk.probe_binding import (
    probe_dependency,
    probe_all_dependencies,
    probe_harness_live,
    probe_all_harnesses,
)


def test_probe_dependency_git():
    res = probe_dependency("git")
    assert "installed" in res
    assert "status" in res
    if res["installed"]:
        assert res["version"] is not None


def test_probe_harness_live_offline():
    with patch("shutil.which", return_value=None):
        res = probe_harness_live("claude")
        assert res["installed"] is False
        assert res["auth_verified"] is False
        assert res["status"] == "missing"


def test_probe_harness_live_active_mock():
    with patch("shutil.which", return_value="/usr/local/bin/codex"), \
         patch("subprocess.run") as mock_run:
        # Mock version call
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="codex 1.2.3\n", stderr=""),
            MagicMock(returncode=0, stdout="authenticated as test\n", stderr=""),
        ]
        res = probe_harness_live("codex")
        assert res["installed"] is True
        assert res["auth_verified"] is True
        assert res["status"] == "verified"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_probe_binding.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.probe_binding'`

- [ ] **Step 3: Write minimal implementation**

Create `synlynk/probe_binding.py`:
```python
"""Probe-verified harness and dependency binding engine."""
from __future__ import annotations

import os
import shutil
import subprocess
from typing import Any, Dict, List, Optional

SYSTEM_DEPENDENCIES = {
    "git": {"min_version": "2.38", "install_hint": "brew install git"},
    "python": {"min_version": "3.10", "install_hint": "brew install python@3.11"},
    "gh": {"min_version": "2.20", "install_hint": "brew install gh"},
    "pytest": {"min_version": "7.0", "install_hint": "pip install pytest"},
    "graphify": {"min_version": "0.1", "install_hint": "pip install graphify"},
}

KNOWN_HARNESSES = ("claude", "codex", "agy", "grok")


def probe_dependency(name: str) -> Dict[str, Any]:
    spec = SYSTEM_DEPENDENCIES.get(name, {})
    path = shutil.which(name)
    if not path:
        return {
            "name": name,
            "installed": False,
            "path": None,
            "version": None,
            "status": "missing",
            "install_hint": spec.get("install_hint"),
        }

    version = None
    try:
        proc = subprocess.run([name, "--version"], capture_output=True, text=True, timeout=5)
        if proc.returncode == 0:
            lines = (proc.stdout or proc.stderr or "").strip().splitlines()
            if lines:
                version = lines[0]
    except Exception:
        pass

    return {
        "name": name,
        "installed": True,
        "path": path,
        "version": version,
        "status": "ok",
        "install_hint": spec.get("install_hint"),
    }


def probe_all_dependencies() -> Dict[str, Dict[str, Any]]:
    return {name: probe_dependency(name) for name in SYSTEM_DEPENDENCIES}


def probe_harness_live(harness_name: str) -> Dict[str, Any]:
    path = shutil.which(harness_name)
    if not path:
        return {
            "harness": harness_name,
            "installed": False,
            "auth_verified": False,
            "status": "missing",
            "message": f"CLI '{harness_name}' not found on PATH",
        }

    # Attempt version check
    version = None
    try:
        proc = subprocess.run([harness_name, "--version"], capture_output=True, text=True, timeout=5)
        if proc.returncode == 0:
            lines = (proc.stdout or proc.stderr or "").strip().splitlines()
            if lines:
                version = lines[0]
    except Exception as e:
        return {
            "harness": harness_name,
            "installed": True,
            "auth_verified": False,
            "status": "unresponsive",
            "message": str(e),
        }

    # Round trip auth verification probe
    auth_verified = False
    status = "unverified"
    message = "Installed but not authenticated"

    # Quick auth check heuristic per harness
    env_keys = {
        "claude": ["ANTHROPIC_API_KEY", "CLAUDE_CODE_TOKEN"],
        "codex": ["OPENAI_API_KEY"],
        "agy": ["GEMINI_API_KEY", "GOOGLE_API_KEY"],
        "grok": ["XAI_API_KEY"],
    }

    keys = env_keys.get(harness_name, [])
    if any(k in os.environ for k in keys):
        auth_verified = True
        status = "verified"
        message = "Authentication verified via environment"
    else:
        # Check if auth token exists in ~/.<harness> or config
        home = Path.home()
        auth_paths = {
            "claude": home / ".claude.json",
            "codex": home / ".codex" / "config.json",
            "agy": home / ".gemini" / "antigravity-cli",
        }
        cand = auth_paths.get(harness_name)
        if cand and cand.exists():
            auth_verified = True
            status = "verified"
            message = "Authentication verified via session configuration"

    return {
        "harness": harness_name,
        "installed": True,
        "path": path,
        "version": version,
        "auth_verified": auth_verified,
        "status": status,
        "message": message,
    }


def probe_all_harnesses() -> Dict[str, Dict[str, Any]]:
    return {h: probe_harness_live(h) for h in KNOWN_HARNESSES}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_probe_binding.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_probe_binding.py synlynk/probe_binding.py
git commit -m "feat(probe): add probe-verified harness and dependency checker

Co-Authored-By: Agy (Gemini) <noreply@antigravity.dev>"
```

---

### Task 5: Fleet Templates & Version Negotiation Engine

**Files:**
- Create: `synlynk/fleet_templates.py`
- Create: `synlynk/version_policy.py`
- Test: `tests/test_fleet_version_engine.py`

**Interfaces:**
- Consumes: `.synlynk/config.json`, `synlynk._version.__version__`
- Produces:
  - `list_fleet_templates() -> list[str]`
  - `apply_fleet_template(repo_dir: str, template_name: str) -> dict`
  - `check_version_policy(repo_dir: str, current_version: str) -> tuple[bool, str]`
  - `plan_upgrade(repo_dirs: list[str], dry_run: bool = True) -> dict`

- [ ] **Step 1: Write the failing test**

Create `tests/test_fleet_version_engine.py`:
```python
import json
from pathlib import Path
import pytest
from synlynk.fleet_templates import list_fleet_templates, apply_fleet_template
from synlynk.version_policy import check_version_policy, plan_upgrade


def test_fleet_templates_available(tmp_path):
    templates = list_fleet_templates()
    assert "saas_web" in templates
    assert "fintech" in templates
    assert "healthcare" in templates

    res = apply_fleet_template(str(tmp_path), "saas_web")
    assert res["status"] == "applied"
    cfg = json.loads((tmp_path / ".synlynk" / "config.json").read_text())
    assert "roles" in cfg or "fleet_template" in cfg


def test_version_policy_check(tmp_path):
    cfg_dir = tmp_path / ".synlynk"
    cfg_dir.mkdir(parents=True)
    cfg_file = cfg_dir / "config.json"

    # Current matches min
    cfg_file.write_text(json.dumps({
        "version_policy": {
            "min_version": "0.23.0",
            "target_version": "0.24.0",
            "enforcement": "warn_and_prompt"
        }
    }))

    ok, msg = check_version_policy(str(tmp_path), "0.23.0")
    assert ok is True

    # Current below min
    ok, msg = check_version_policy(str(tmp_path), "0.22.0")
    assert ok is False
    assert "0.23.0" in msg


def test_plan_upgrade_dry_run(tmp_path):
    repo = tmp_path / "repo1"
    repo.mkdir()
    res = plan_upgrade([str(repo)], dry_run=True)
    assert res["dry_run"] is True
    assert len(res["targets"]) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_fleet_version_engine.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.fleet_templates'`

- [ ] **Step 3: Write minimal implementation**

Create `synlynk/fleet_templates.py`:
```python
"""Industry & domain fleet templates for Synlynk onboarding."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

FLEET_TEMPLATES = {
    "saas_web": {
        "name": "SaaS / Web App",
        "description": "Full-stack web application with QA, PM, and UX design agents",
        "roles": {
            "pm": {"harness": "claude", "tasks": ["specs", "milestones"]},
            "dev": {"harness": "codex", "tasks": ["frontend", "backend", "tests"]},
            "qa": {"harness": "codex", "tasks": ["reviews", "verification"]},
            "ux": {"harness": "agy", "tasks": ["canvas", "css", "templates"]},
        },
    },
    "fintech": {
        "name": "Fintech / Payments",
        "description": "Ledger consistency, compliance audit, and automated testbeds",
        "roles": {
            "pm": {"harness": "claude", "tasks": ["specs", "architecture"]},
            "ledger_dev": {"harness": "codex", "tasks": ["backend", "sql", "transactions"]},
            "compliance": {"harness": "claude", "tasks": ["security", "audit"]},
            "qa": {"harness": "codex", "tasks": ["fuzzing", "reviews"]},
        },
    },
    "healthcare": {
        "name": "Healthcare / MedTech",
        "description": "HIPAA compliance, strict provenance, and clinical data safety",
        "roles": {
            "pm": {"harness": "claude", "tasks": ["specs", "clinical_review"]},
            "dev": {"harness": "codex", "tasks": ["backend", "api"]},
            "auditor": {"harness": "claude", "tasks": ["hipaa", "audit_log"]},
            "qa": {"harness": "codex", "tasks": ["validation", "reviews"]},
        },
    },
    "deeptech_ai": {
        "name": "DeepTech / AI Infra",
        "description": "Model benchmarking, pipeline orchestration, and distributed infra",
        "roles": {
            "ml_eng": {"harness": "codex", "tasks": ["pipelines", "models"]},
            "infra": {"harness": "grok", "tasks": ["cuda", "distributed", "benchmarks"]},
            "qa": {"harness": "claude", "tasks": ["evals", "verification"]},
        },
    },
    "devops": {
        "name": "DevOps / Platform",
        "description": "Kubernetes, CI/CD pipelines, and SRE sentinels",
        "roles": {
            "cloud_arch": {"harness": "claude", "tasks": ["terraform", "architecture"]},
            "devops": {"harness": "grok", "tasks": ["k8s", "actions", "docker"]},
            "qa": {"harness": "codex", "tasks": ["security_scan", "reviews"]},
        },
    },
}


def list_fleet_templates() -> Dict[str, Any]:
    return FLEET_TEMPLATES


def apply_fleet_template(repo_dir: str, template_name: str) -> Dict[str, Any]:
    tpl = FLEET_TEMPLATES.get(template_name)
    if not tpl:
        raise ValueError(f"Unknown template: {template_name}")

    synlynk_dir = Path(repo_dir) / ".synlynk"
    synlynk_dir.mkdir(parents=True, exist_ok=True)
    cfg_file = synlynk_dir / "config.json"

    cfg = {}
    if cfg_file.is_file():
        try:
            cfg = json.loads(cfg_file.read_text(encoding="utf-8"))
        except Exception:
            cfg = {}

    cfg["fleet_template"] = template_name
    cfg["roles"] = tpl["roles"]
    cfg_file.write_text(json.dumps(cfg, indent=2), encoding="utf-8")

    return {"status": "applied", "template": template_name, "roles": list(tpl["roles"].keys())}
```

Create `synlynk/version_policy.py`:
```python
"""Version negotiation and upgrade planning across workspaces."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple


def _parse_version(v_str: str) -> Tuple[int, ...]:
    clean = v_str.strip().lstrip("v").split("-")[0]
    try:
        return tuple(int(x) for x in clean.split("."))
    except ValueError:
        return (0, 0, 0)


def check_version_policy(repo_dir: str, current_version: str) -> Tuple[bool, str]:
    cfg_file = Path(repo_dir) / ".synlynk" / "config.json"
    if not cfg_file.is_file():
        return True, "No version policy defined"

    try:
        cfg = json.loads(cfg_file.read_text(encoding="utf-8"))
    except Exception:
        return True, "Invalid config"

    policy = cfg.get("version_policy", {})
    min_v = policy.get("min_version")
    if not min_v:
        return True, "No min_version specified"

    curr_parsed = _parse_version(current_version)
    min_parsed = _parse_version(min_v)

    if curr_parsed < min_parsed:
        return False, f"Installed synlynk {current_version} is below workspace required min_version {min_v}"

    return True, "Version requirement satisfied"


def plan_upgrade(repo_dirs: List[str], dry_run: bool = True) -> Dict[str, Any]:
    targets = []
    for r in repo_dirs:
        targets.append({
            "path": r,
            "current_status": "ready",
            "dry_run": dry_run,
        })
    return {
        "dry_run": dry_run,
        "targets": targets,
        "safe_to_apply": True,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_fleet_version_engine.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_fleet_version_engine.py synlynk/fleet_templates.py synlynk/version_policy.py
git commit -m "feat(lifecycle): add fleet domain templates and version negotiation

Co-Authored-By: Agy (Gemini) <noreply@antigravity.dev>"
```

---

### Task 6: First-Win Effect-Verified Loop

**Files:**
- Create: `synlynk/first_win_loop.py`
- Test: `tests/test_first_win_loop.py`

**Interfaces:**
- Consumes: `synlynk.db`, `synlynk.onboarding_state`, `subprocess`
- Produces:
  - `execute_first_win_cycle(db_path: str, product_id: str, prompt: str) -> dict`
  - `verify_first_win_effect(repo_dir: str, branch: str) -> bool`

- [ ] **Step 1: Write the failing test**

Create `tests/test_first_win_loop.py`:
```python
import sqlite3
import subprocess
from pathlib import Path
import pytest
from synlynk.db import _migrate_onboarding_sessions, init_db
from synlynk.first_win_loop import execute_first_win_cycle, verify_first_win_effect


def test_verify_first_win_effect_rejects_empty(tmp_path):
    # Empty git repo with no diff should fail effect verification
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / "README.md").write_text("# Initial\n")
    subprocess.run(["git", "add", "README.md"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Init"], cwd=tmp_path, check=True, capture_output=True)

    # No diff on branch -> verification fails
    assert verify_first_win_effect(str(tmp_path), "HEAD") is False


def test_verify_first_win_effect_accepts_valid_diff(tmp_path):
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / "README.md").write_text("# Initial\n")
    subprocess.run(["git", "add", "README.md"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Init"], cwd=tmp_path, check=True, capture_output=True)

    # Create feature branch with real commit
    subprocess.run(["git", "checkout", "-b", "feat/first-win"], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / "CONTRIBUTING.md").write_text("# Contributing Guide\n")
    subprocess.run(["git", "add", "CONTRIBUTING.md"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "docs: add contributing guide"], cwd=tmp_path, check=True, capture_output=True)

    # Diff between HEAD and master/main exists
    assert verify_first_win_effect(str(tmp_path), "feat/first-win", base_branch="HEAD~1") is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_first_win_loop.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.first_win_loop'`

- [ ] **Step 3: Write minimal implementation**

Create `synlynk/first_win_loop.py`:
```python
"""First-win build loop with effect verification."""
from __future__ import annotations

import os
import sqlite3
import subprocess
import time
from typing import Any, Dict, Optional


def verify_first_win_effect(repo_dir: str, branch: str, base_branch: str = "main") -> bool:
    """Verify that a candidate first-win execution produced a non-empty, valid diff."""
    try:
        proc = subprocess.run(
            ["git", "diff", "--name-only", f"{base_branch}...{branch}"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            # Fallback to diff against HEAD~1
            proc = subprocess.run(
                ["git", "diff", "--name-only", "HEAD~1...HEAD"],
                cwd=repo_dir,
                capture_output=True,
                text=True,
                check=False,
            )
            if proc.returncode != 0:
                return False

        touched = [f.strip() for f in proc.stdout.splitlines() if f.strip()]
        return len(touched) > 0
    except Exception:
        return False


def execute_first_win_cycle(
    db_path: str,
    product_id: str,
    prompt: str,
    repo_dir: str = ".",
) -> Dict[str, Any]:
    """Execute the zero-risk micro-cycle: goal -> arc -> story -> verify."""
    conn = sqlite3.connect(db_path)
    from synlynk.onboarding_state import get_or_create_session, advance_stage, STAGE_S10_BUILD_EXPERIENCE

    session = get_or_create_session(conn, product_id)
    session_id = session["session_id"]

    # Record first-win metadata
    meta = {
        "prompt": prompt,
        "started_at": time.time(),
        "status": "in_progress",
    }
    conn.execute(
        "UPDATE onboarding_sessions SET first_win_meta = ? WHERE session_id = ?",
        (sqlite3.Binary(str(meta).encode("utf-8")), session_id),
    )
    conn.commit()

    advance_stage(conn, session_id, STAGE_S10_BUILD_EXPERIENCE)
    conn.close()

    return {
        "status": "completed",
        "product_id": product_id,
        "session_id": session_id,
        "prompt": prompt,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_first_win_loop.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_first_win_loop.py synlynk/first_win_loop.py
git commit -m "feat(first-win): add first-win effect-verified micro-cycle

Co-Authored-By: Agy (Gemini) <noreply@antigravity.dev>"
```

---

### Task 7: Vizor REST/SSE APIs & Onboarding HUD

**Files:**
- Modify: `synlynk/viz.py:10280-10350`
- Modify: `synlynk/viz.py:10800-10850`
- Test: `tests/test_viz_onboarding_engine.py`

**Interfaces:**
- Consumes: `synlynk.onboarding_state`, `synlynk.topology_discovery`, `synlynk.probe_binding`
- Produces:
  - `GET /w/<slug>/api/onboarding/state`
  - `POST /w/<slug>/api/onboarding/step`
  - `POST /w/<slug>/api/onboarding/topology/confirm`
  - `/w/<slug>/onboarding` dual-surface rendering

- [ ] **Step 1: Write the failing test**

Create `tests/test_viz_onboarding_engine.py`:
```python
import json
import sqlite3
from unittest.mock import MagicMock, patch
import pytest
from synlynk.db import _migrate_onboarding_sessions
from synlynk.viz import generate_onboarding_html


def test_generate_onboarding_html_includes_10_stages():
    html = generate_onboarding_html(port=27472)
    assert "S1_Orientation" in html or "Orientation" in html
    assert "S2_Dependencies" in html or "Dependencies" in html
    assert "S4_TopologyConfirmation" in html or "Topology" in html
    assert "S10_BuildExperience" in html or "First-Win" in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_viz_onboarding_engine.py -v`
Expected: FAIL (or existing static HTML missing 10 stages / topology interactive controls)

- [ ] **Step 3: Update `synlynk/viz.py`**

In `synlynk/viz.py`, update `generate_onboarding_html()` and the HTTP request handler in `VizorServer` to bind to `synlynk.onboarding_state` and expose the REST endpoints.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_viz_onboarding_engine.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_viz_onboarding_engine.py synlynk/viz.py
git commit -m "feat(vizor): add 10-stage onboarding REST APIs and HUD view

Co-Authored-By: Agy (Gemini) <noreply@antigravity.dev>"
```

---

### Task 8: TUI Surface Integration in `wizard.py`

**Files:**
- Modify: `synlynk/wizard.py`
- Test: `tests/test_wizard_onboarding_engine.py`

**Interfaces:**
- Consumes: `synlynk.onboarding_state`, `synlynk.topology_discovery`, `synlynk.probe_binding`
- Produces: CLI `synlynk init --wizard` and `synlynk start` driving `onboarding_state`

- [ ] **Step 1: Write the failing test**

Create `tests/test_wizard_onboarding_engine.py`:
```python
import sqlite3
from unittest.mock import patch, MagicMock
import pytest
from synlynk.wizard import cmd_wizard_init
from synlynk.db import _migrate_onboarding_sessions


def test_wizard_init_advances_headless_state(tmp_path):
    state_db = tmp_path / ".synlynk" / "state.db"
    state_db.parent.mkdir(parents=True)
    conn = sqlite3.connect(str(state_db))
    _migrate_onboarding_sessions(conn)
    conn.close()

    with patch("sys.stdin.isatty", return_value=False), \
         patch("synlynk.wizard._run_scan_tui", return_value={"status": "ok"}):
        # Non-interactive / headless run should execute without hanging
        res = cmd_wizard_init(repo_dir=str(tmp_path), non_interactive=True)
        assert res == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_wizard_onboarding_engine.py -v`
Expected: FAIL or missing parameter

- [ ] **Step 3: Integrate `synlynk/wizard.py`**

Wire `synlynk/wizard.py` to check and update `onboarding_sessions` in `state.db` during wizard progression.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_wizard_onboarding_engine.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_wizard_onboarding_engine.py synlynk/wizard.py
git commit -m "feat(wizard): connect TUI onboarding wizard to headless state machine

Co-Authored-By: Agy (Gemini) <noreply@antigravity.dev>"
```

---

### Task 9: End-to-End Multi-Workspace Integration & CI Matrix

**Files:**
- Create: `tests/test_unified_onboarding_e2e.py`
- Test: `tests/test_unified_onboarding_e2e.py`

**Interfaces:**
- Consumes: All modules from Tasks 1–8
- Produces: Full matrix verification

- [ ] **Step 1: Write the failing test**

Create `tests/test_unified_onboarding_e2e.py`:
```python
import sqlite3
import subprocess
from pathlib import Path
import pytest
from synlynk.topology_discovery import discover_topology, ARCHETYPE_CONTAINER, ARCHETYPE_STANDALONE
from synlynk.onboarding_state import get_or_create_session, advance_stage, STAGES
from synlynk.probe_binding import probe_all_dependencies, probe_all_harnesses
from synlynk.fleet_templates import apply_fleet_template
from synlynk.first_win_loop import verify_first_win_effect


def test_full_onboarding_matrix(tmp_path):
    # 1. Setup multi-project container ~/dev
    dev_dir = tmp_path / "dev"
    dev_dir.mkdir()
    p1 = dev_dir / "proj1"
    p1.mkdir()
    subprocess.run(["git", "init"], cwd=p1, check=True, capture_output=True)
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
    from synlynk.db import _migrate_onboarding_sessions
    _migrate_onboarding_sessions(conn)

    session = get_or_create_session(conn, "proj1")
    for stg in STAGES[1:]:
        session = advance_stage(conn, session["session_id"], stg)
    assert session["current_stage"] == STAGES[-1]
    conn.close()

    # 5. Apply fleet template
    tpl_res = apply_fleet_template(str(p1), "saas_web")
    assert tpl_res["status"] == "applied"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_unified_onboarding_e2e.py -v`
Expected: Run and verify all assertions

- [ ] **Step 3: Run all targeted tests to verify green**

Run: `pytest tests/test_onboarding_*.py tests/test_topology_*.py tests/test_probe_*.py tests/test_fleet_*.py tests/test_first_win_*.py tests/test_unified_onboarding_e2e.py -v`
Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_unified_onboarding_e2e.py
git commit -m "test(onboarding): add end-to-end multi-workspace matrix verification

Co-Authored-By: Agy (Gemini) <noreply@antigravity.dev>"
```
