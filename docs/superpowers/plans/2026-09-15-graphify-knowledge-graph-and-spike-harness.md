# Graphify Knowledge Graph Substrate, Multi-Repo Mesh & Reusable Spike Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate the Graphify AST Knowledge Graph substrate into Synlynk's discovery engine, Vizor views, living agent charters, CLI commands, multi-repo mesh, and productize the empirical A/B Spike Evaluation Harness (`synlynk spike eval`).

**Architecture:** A 4-phase, 12-task modular rollout that strictly adheres to the "Opt-in, JIT-Bound, Graceful Fallback" contract. Task execution is distributed across all 4 harnesses per the capability matrix: Codex handles Python/CLI/tests/graph traversal engines, Grok handles D3/SVG canvas rendering in Vizor, Agy handles skills/FTUE onboarding/templates, and Claude handles charter adaptation and spike decision panel integration.

**Tech Stack:** Python 3 (stdlib, `sqlite3`, `argparse`, `ast`, `json`, `subprocess`), Tree-sitter AST via `graphifyy` (external process), D3.js v7 / SVG canvas, Pytest.

**Spec:** [`docs/superpowers/specs/2026-09-15-graphify-knowledge-graph-and-spike-harness.md`](file:///Users/nikhilsoman/dev/feat+graphify-knowledge-graph-and-spike-harness/docs/superpowers/specs/2026-09-15-graphify-knowledge-graph-and-spike-harness.md)

## Global Constraints

- **License Compliance:** Graphify is Apache-2.0; Synlynk is MIT. Process isolation across CLI/JSON interfaces only — no direct source code vendoring or relicensing.
- **Context Ceiling Guardrail:** Traversal payloads and context packs injected into prompts MUST NOT exceed 2,000 tokens (enforced via `_cut_to_token_budget`).
- **Offline & Zero-Cost Default:** `graphify extract` MUST always be invoked with `--code-only`. No deep LLM multi-modal mode in default CLI or daemon loops.
- **Graceful Fallback Invariant:** If `graphify` is missing from `PATH` or corrupted, all Synlynk commands MUST fall back to native stdlib AST discovery with zero unhandled exceptions.
- **Git Worktree-First Policy:** All feature branches and dispatches run in isolated worktrees with appropriate Co-Authored-By trailers.

---

## Fleet Capability Allocation Matrix

| Phase & Domain | Assigned Harness | Assigned Role | Deliverables |
| :--- | :--- | :--- | :--- |
| **Phase 1: Core AST & Tooling** | `codex` | `dev` | Tool installer (`synlynk tool install`), AST integration in `discovery.py` |
| **Phase 1: Vizor D3 Canvas** | `grok` | `infra` | Interactive D3/SVG call-graph view & staleness badge in `viz_views.py` |
| **Phase 1: Onboarding Wizard** | `agy` | `content` | FTUE wizard integration in `coldstart.py` and `/onboarding` |
| **Phase 2: Charter Skills** | `agy` | `content` | 4 role-specific skills authored in `.synlynk/skills/` |
| **Phase 2: Charter Adaptation** | `claude` | `architect` | Living charter injection in `charters.py` and `agent_cli.py` |
| **Phase 2: Context Packs** | `codex` | `dev` | `synlynk pack` and Turn-1 dispatch injection in `dispatch.py` |
| **Phase 3: Impact & Blast Radius** | `codex` | `dev` | `synlynk impact` CLI and AST traversal algorithm in `impact.py` |
| **Phase 3: PR Gate Attestation** | `codex` | `verifier` / `qa` | `synlynk pr check --impact-attested` in `pr_check.py` |
| **Phase 3: Cycle Healing** | `codex` | `dev` | `synlynk heal --cycles` and circular dependency detection |
| **Phase 4: Multi-Repo Mesh** | `codex` | `dev` | Multi-repo aggregator and global mesh in `multirepo_graph.py` |
| **Phase 4: Spike Engine** | `codex` | `dev` | `synlynk spike eval` harness, shadow worktrees, metrics collector |
| **Phase 4: Spike Panel Review** | `claude` | `pm` / `architect` | Receipt generator and `synlynk decide --panel` integration |

---

## Phase 1: Core AST Provider & Vizor Embed

### Task 1: Tool Installer & Preflight Detector (`synlynk tool install graphify`)
**Harness:** `codex` | **Role:** `dev`

**Files:**
- Create: `synlynk/tool_installer.py`
- Modify: `synlynk/taxonomy.py:45-55`
- Modify: `synlynk/cli.py:120-150`
- Test: `tests/test_tool_installer.py`

**Interfaces:**
- Consumes: `shutil.which`, `subprocess.run`
- Produces: `is_tool_available(tool_name: str) -> bool`, `install_tool(tool_name: str) -> bool`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_tool_installer.py
import pytest
from synlynk.tool_installer import is_tool_available, install_tool, RECOMMENDED_TOOLS


def test_recommended_tools_registry():
    assert "graphify" in RECOMMENDED_TOOLS
    entry = RECOMMENDED_TOOLS["graphify"]
    assert entry["package"] == "graphifyy"
    assert entry["license"] == "Apache-2.0"
    assert "token reduction" in entry["description"].lower()


def test_is_tool_available_false_when_missing(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: None)
    assert is_tool_available("graphify") is False


def test_is_tool_available_true_when_present(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: "/usr/local/bin/graphify")
    assert is_tool_available("graphify") is True


def test_install_tool_invokes_uv_or_pipx(monkeypatch):
    invoked = []

    def mock_run(cmd, capture_output, text, check):
        invoked.append(cmd)
        class Res:
            returncode = 0
            stdout = "Installed graphifyy"
        return Res()

    monkeypatch.setattr("shutil.which", lambda name: "/usr/local/bin/uv" if name == "uv" else None)
    monkeypatch.setattr("subprocess.run", mock_run)

    success = install_tool("graphify")
    assert success is True
    assert len(invoked) == 1
    assert invoked[0] == ["uv", "tool", "install", "graphifyy"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_tool_installer.py -v`  
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.tool_installer'`

- [ ] **Step 3: Implement `synlynk/tool_installer.py` and register CLI command**

Create `synlynk/tool_installer.py`:
```python
"""1-Click installer and preflight detector for recommended ecosystem tools."""

import shutil
import subprocess
from typing import Dict, Any, Optional

RECOMMENDED_TOOLS: Dict[str, Dict[str, Any]] = {
    "graphify": {
        "binary": "graphify",
        "package": "graphifyy",
        "description": "Deterministic AST Knowledge Graph for 20x token reduction and blast radius analysis",
        "license": "Apache-2.0",
        "install_methods": ["uv", "pipx", "pip"],
    },
    "gh": {
        "binary": "gh",
        "package": "gh",
        "description": "GitHub official CLI for PR reviews and repository management",
        "license": "MIT",
        "install_methods": ["brew", "apt"],
    },
}


def is_tool_available(tool_name: str) -> bool:
    """Check if the tool binary is available on PATH."""
    config = RECOMMENDED_TOOLS.get(tool_name)
    binary = config["binary"] if config else tool_name
    return shutil.which(binary) is not None


def install_tool(tool_name: str) -> bool:
    """Install a recommended tool using available package managers."""
    if tool_name not in RECOMMENDED_TOOLS:
        raise ValueError(f"Unknown tool: {tool_name}. Registered tools: {list(RECOMMENDED_TOOLS.keys())}")

    config = RECOMMENDED_TOOLS[tool_name]
    package = config["package"]

    # Prefer uv, then pipx, then pip
    if shutil.which("uv"):
        cmd = ["uv", "tool", "install", package]
    elif shutil.which("pipx"):
        cmd = ["pipx", "install", package]
    elif shutil.which("pip"):
        cmd = ["pip", "install", package]
    else:
        return False

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return res.returncode == 0
    except (subprocess.SubprocessError, OSError):
        return False
```

Wire into `synlynk/cli.py` and `synlynk/taxonomy.py`:
Add `tool install` command handler calling `install_tool(args.tool_name)`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_tool_installer.py -v`  
Expected: PASS (4/4 tests passed)

- [ ] **Step 5: Commit**

```bash
git add synlynk/tool_installer.py synlynk/cli.py synlynk/taxonomy.py tests/test_tool_installer.py
git commit -m "feat(tools): add 1-click tool installer and preflight detector

Co-Authored-By: Codex <noreply@openai.com>"
```

---

### Task 2: Deterministic AST Integration with Staleness Anchor (`synlynk/discovery.py`)
**Harness:** `codex` | **Role:** `dev`

**Files:**
- Modify: `synlynk/discovery.py:10-72`
- Test: `tests/test_discovery_graphify.py`

**Interfaces:**
- Consumes: `is_tool_available("graphify")`, `subprocess.run(["git", "rev-parse", "HEAD"])`
- Produces: `scan_workspace_static(repo_root: str) -> Dict[str, Any]` with `knowledge_graph` section containing `nodes_count`, `edges_count`, `communities_count`, `built_at_commit`, and `stale: bool`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_discovery_graphify.py
import json
import pytest
from pathlib import Path
from synlynk.discovery import scan_workspace_static


def test_scan_workspace_static_fallback_when_graphify_absent(tmp_path, monkeypatch):
    monkeypatch.setattr("synlynk.discovery._is_graphify_installed", lambda: False)
    (tmp_path / "app.py").write_text("def hello(): pass")

    res = scan_workspace_static(str(tmp_path))
    assert "domain" in res
    assert "physical" in res
    assert "logical" in res
    assert res.get("knowledge_graph") is None or res["knowledge_graph"]["available"] is False


def test_scan_workspace_static_uses_graphify_cache_and_checks_staleness(tmp_path, monkeypatch):
    monkeypatch.setattr("synlynk.discovery._is_graphify_installed", lambda: True)
    monkeypatch.setattr("synlynk.discovery._get_head_commit", lambda root: "commit_abc123")

    out_dir = tmp_path / ".synlynk" / "graphify-out"
    out_dir.mkdir(parents=True)
    manifest = {
        "built_at_commit": "commit_abc123",
        "nodes_count": 42,
        "edges_count": 84,
        "communities_count": 5,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest))

    res = scan_workspace_static(str(tmp_path))
    assert res["knowledge_graph"]["available"] is True
    assert res["knowledge_graph"]["stale"] is False
    assert res["knowledge_graph"]["nodes_count"] == 42
    assert res["knowledge_graph"]["built_at_commit"] == "commit_abc123"


def test_scan_workspace_static_flags_stale_when_head_advanced(tmp_path, monkeypatch):
    monkeypatch.setattr("synlynk.discovery._is_graphify_installed", lambda: True)
    monkeypatch.setattr("synlynk.discovery._get_head_commit", lambda root: "commit_xyz789")

    out_dir = tmp_path / ".synlynk" / "graphify-out"
    out_dir.mkdir(parents=True)
    manifest = {
        "built_at_commit": "commit_abc123",
        "nodes_count": 42,
        "edges_count": 84,
        "communities_count": 5,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest))

    res = scan_workspace_static(str(tmp_path))
    assert res["knowledge_graph"]["available"] is True
    assert res["knowledge_graph"]["stale"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_discovery_graphify.py -v`  
Expected: FAIL with missing helper / attribute assertions.

- [ ] **Step 3: Modify `synlynk/discovery.py` to support Graphify AST and staleness anchor**

Update `synlynk/discovery.py`:
```python
def _is_graphify_installed() -> bool:
    return shutil.which("graphify") is not None


def _get_head_commit(repo_root: str) -> str:
    try:
        res = subprocess.run(
            ["git", "-C", repo_root, "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True, timeout=2,
        )
        return res.stdout.strip()
    except Exception:
        return ""


def _read_graphify_manifest(repo_root: str) -> Optional[Dict[str, Any]]:
    manifest_path = Path(repo_root) / ".synlynk" / "graphify-out" / "manifest.json"
    if manifest_path.is_file():
        try:
            return json.loads(manifest_path.read_text(errors="ignore"))
        except Exception:
            return None
    return None
```
In `scan_workspace_static()`, populate `"knowledge_graph"` key safely with fallback.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_discovery_graphify.py tests/test_discovery_static.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add synlynk/discovery.py tests/test_discovery_graphify.py
git commit -m "feat(discovery): integrate Graphify AST knowledge graph with commit staleness anchor

Co-Authored-By: Codex <noreply@openai.com>"
```

---

### Task 3: Vizor View 2 (Logical View) Graphify Topological Embed & D3 Canvas
**Harness:** `grok` | **Role:** `infra`

**Files:**
- Modify: `synlynk/viz_views.py:158-190`
- Modify: `synlynk/viz.py:2204-2270`
- Test: `tests/test_viz_graphify.py`

**Interfaces:**
- Consumes: `.synlynk/graphify-out/graph.json`
- Produces: Enhanced `extract_logical_nodes()` with Graphify community clusters, node centrality ranks, and amber staleness banner if `head_sha != built_at_commit`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_viz_graphify.py
import json
import sqlite3
import pytest
from pathlib import Path
from synlynk.viz_views import extract_logical_nodes, init_workspace_view_tables


def test_extract_logical_nodes_enriches_from_graphify_when_present(tmp_path, monkeypatch):
    conn = sqlite3.connect(":memory:")
    init_workspace_view_tables(conn)

    out_dir = tmp_path / ".synlynk" / "graphify-out"
    out_dir.mkdir(parents=True)
    graph_data = {
        "nodes": [
            {"id": "synlynk.discovery:scan_workspace_static", "label": "scan_workspace_static", "kind": "function", "community": 2},
            {"id": "synlynk.cli:main", "label": "main", "kind": "function", "community": 2},
        ],
        "edges": [
            {"source": "synlynk.cli:main", "target": "synlynk.discovery:scan_workspace_static", "kind": "calls"}
        ]
    }
    (out_dir / "graph.json").write_text(json.dumps(graph_data))
    (out_dir / "manifest.json").write_text(json.dumps({"built_at_commit": "sha123"}))

    nodes, edges = extract_logical_nodes(conn, str(tmp_path))
    node_labels = [n["label"] for n in nodes]
    assert "scan_workspace_static" in node_labels
    assert "main" in node_labels
    assert len(edges) >= 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_viz_graphify.py -v`  
Expected: FAIL because `extract_logical_nodes` currently only checks `.py` directory files.

- [ ] **Step 3: Update `synlynk/viz_views.py` to ingest Graphify graph.json**

In `synlynk/viz_views.py::extract_logical_nodes()`:
Check if `.synlynk/graphify-out/graph.json` exists. If present, parse its nodes and edges into `workspace_view_nodes` with `view = 'logical'` and `provenance = 'graphify'`. If missing, fall back to directory-based package/module extraction.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_viz_graphify.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add synlynk/viz_views.py synlynk/viz.py tests/test_viz_graphify.py
git commit -m "feat(viz): embed Graphify AST call-graph and communities into Vizor Logical View

Co-Authored-By: Grok <noreply@x.ai>"
```

---

### Task 4: FTUE Onboarding Wizard 1-Click Integration & Docs
**Harness:** `agy` | **Role:** `content`

**Files:**
- Modify: `synlynk/coldstart.py`
- Modify: `synlynk/viz.py:5099-5135`
- Create: `docs/tools/graphify.md`
- Test: `tests/test_coldstart_graphify.py`

**Interfaces:**
- Consumes: `is_tool_available("graphify")`, `install_tool("graphify")`
- Produces: Prominent checkbox in `synlynk init` / Vizor `/onboarding`: `[x] Graphify AST Knowledge Graph (Recommended: ~20x token savings)`.

- [ ] **Step 1: Write failing test**

```python
# tests/test_coldstart_graphify.py
from synlynk.coldstart import get_onboarding_recommendations


def test_onboarding_recommends_graphify_when_missing(monkeypatch):
    monkeypatch.setattr("synlynk.tool_installer.is_tool_available", lambda tool: False)
    recs = get_onboarding_recommendations()
    tools = [r["name"] for r in recs]
    assert "graphify" in tools
    assert recs[tools.index("graphify")]["recommended"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_coldstart_graphify.py -v`  
Expected: FAIL

- [ ] **Step 3: Implement onboarding recommendations and documentation**

Implement `get_onboarding_recommendations()` in `synlynk/coldstart.py`, wire into `/onboarding` in `synlynk/viz.py`, and author `docs/tools/graphify.md`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_coldstart_graphify.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add synlynk/coldstart.py synlynk/viz.py docs/tools/graphify.md tests/test_coldstart_graphify.py
git commit -m "docs(onboarding): add Graphify to FTUE onboarding wizard and author user guide

Co-Authored-By: AGY <noreply@antigravity.dev>"
```

---

## Phase 2: Role-Specific Charter Skills & Context Packs

### Task 5: Materialize 4 Role-Specific Charter Skills
**Harness:** `agy` | **Role:** `content`

**Files:**
- Create: `.synlynk/skills/graphify-architecture-audit/SKILL.md`
- Create: `.synlynk/skills/graphify-pr-impact/SKILL.md`
- Create: `.synlynk/skills/graphify-symbol-navigator/SKILL.md`
- Create: `.synlynk/skills/graphify-domain-sweep/SKILL.md`
- Test: `tests/test_graphify_skills.py`

**Interfaces:**
- Produces: Documented SKILL.md specs with YAML frontmatter, execution workflows, and CLI/MCP invocations.

- [ ] **Step 1: Write failing test verifying skill validity**

```python
# tests/test_graphify_skills.py
from pathlib import Path


def test_all_four_graphify_skills_exist_and_have_valid_frontmatter():
    skills_dir = Path(".synlynk/skills")
    required_skills = [
        "graphify-architecture-audit",
        "graphify-pr-impact",
        "graphify-symbol-navigator",
        "graphify-domain-sweep",
    ]
    for skill in required_skills:
        skill_file = skills_dir / skill / "SKILL.md"
        assert skill_file.is_file(), f"Missing skill file: {skill_file}"
        content = skill_file.read_text()
        assert content.startswith("---"), f"Skill {skill} missing YAML frontmatter"
        assert "name: " in content
        assert "description: " in content
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_graphify_skills.py -v`  
Expected: FAIL (missing skill files)

- [ ] **Step 3: Create the 4 SKILL.md files**

Create each SKILL.md matching Section 4 of the spec:
- `graphify-architecture-audit`: God nodes query, community boundary audit, cyclic dependency detection.
- `graphify-pr-impact`: PR diff symbol resolution, caller tree traversal, test coverage verification.
- `graphify-symbol-navigator`: Surgical 1-hop neighbor subgraph queries, interface signature inspection.
- `graphify-domain-sweep`: Multi-modal deep extraction on reference standards and chapter-cited PRDs.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_graphify_skills.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add .synlynk/skills/ tests/test_graphify_skills.py
git commit -m "feat(skills): add 4 role-specific Graphify skills for agent charters

Co-Authored-By: AGY <noreply@antigravity.dev>"
```

---

### Task 6: Wire Charter Adaptation & MCP Tool Manifest
**Harness:** `claude` | **Role:** `architect`

**Files:**
- Modify: `synlynk/charters.py`
- Modify: `synlynk/agent_cli.py`
- Test: `tests/test_charter_graphify.py`

**Interfaces:**
- Consumes: `.synlynk/skills/graphify-*`
- Produces: `synlynk charters adapt` binds skills to appropriate roles (`architect` $\to$ `graphify-architecture-audit`, `qa`/`verifier` $\to$ `graphify-pr-impact`, `dev` $\to$ `graphify-symbol-navigator`, `pm` $\to$ `graphify-domain-sweep`).

- [ ] **Step 1: Write failing test**

```python
# tests/test_charter_graphify.py
import pytest
from synlynk.charters import adapt_charters_for_installed_tools


def test_adapt_charters_injects_graphify_skills(tmp_path, monkeypatch):
    monkeypatch.setattr("synlynk.tool_installer.is_tool_available", lambda tool: True)
    updated = adapt_charters_for_installed_tools()
    assert "graphify-architecture-audit" in updated["architect"]["skills"]
    assert "graphify-pr-impact" in updated["qa"]["skills"]
    assert "graphify-symbol-navigator" in updated["dev"]["skills"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_charter_graphify.py -v`  
Expected: FAIL

- [ ] **Step 3: Update `synlynk/charters.py` to adapt charters based on installed tools**

Update `adapt_charters_for_installed_tools()` to inspect `is_tool_available("graphify")` and attach corresponding skill paths to agent roles.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_charter_graphify.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add synlynk/charters.py synlynk/agent_cli.py tests/test_charter_graphify.py
git commit -m "feat(charters): inject Graphify skills into living agent charters

Co-Authored-By: Claude Sonnet <noreply@anthropic.com>"
```

---

### Task 7: Context Pack Generator & Dispatch Integration (`synlynk pack`)
**Harness:** `codex` | **Role:** `dev`

**Files:**
- Create: `synlynk/pack.py`
- Modify: `synlynk/dispatch.py:1596-1630`
- Modify: `synlynk/cli.py`
- Test: `tests/test_pack.py`

**Interfaces:**
- Consumes: `.synlynk/graphify-out/graph.json`
- Produces: `synthesize_context_pack(repo_root: str, task_text: str, token_budget: int = 1500) -> str`. Automatically injected into `_format_prompt_for_agent()` on Turn 1.

- [ ] **Step 1: Write failing test**

```python
# tests/test_pack.py
import json
import pytest
from pathlib import Path
from synlynk.pack import synthesize_context_pack, _cut_to_token_budget


def test_cut_to_token_budget():
    text = "word " * 3000
    cut = _cut_to_token_budget(text, token_budget=1500)
    # 1 token ~= 4 chars, 1500 tokens ~= 6000 chars
    assert len(cut) <= 6100
    assert "[Context truncated to 1500 token budget]" in cut


def test_synthesize_context_pack_extracts_target_symbols(tmp_path):
    out_dir = tmp_path / ".synlynk" / "graphify-out"
    out_dir.mkdir(parents=True)
    graph = {
        "nodes": [
            {"id": "synlynk.daemon:run_loop", "label": "run_loop", "file": "synlynk/daemon.py", "line": 145},
            {"id": "synlynk.db:init_db", "label": "init_db", "file": "synlynk/db.py", "line": 20},
        ],
        "edges": [
            {"source": "synlynk.daemon:run_loop", "target": "synlynk.db:init_db", "kind": "calls"}
        ]
    }
    (out_dir / "graph.json").write_text(json.dumps(graph))

    pack = synthesize_context_pack(str(tmp_path), task_text="Fix error in run_loop during startup")
    assert "## Task Context Pack" in pack
    assert "run_loop" in pack
    assert "synlynk/daemon.py" in pack
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_pack.py -v`  
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.pack'`

- [ ] **Step 3: Implement `synlynk/pack.py` and integrate into `synlynk/dispatch.py`**

Create `synlynk/pack.py`:
- Matches task keywords against symbols in `graph.json`.
- Extracts 1-hop inbound and outbound edges.
- Formats markdown summary and enforces budget ceiling.
- Wire into `_format_prompt_for_agent()` in `synlynk/dispatch.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_pack.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add synlynk/pack.py synlynk/dispatch.py synlynk/cli.py tests/test_pack.py
git commit -m "feat(pack): synthesize JIT task context packs from knowledge graph

Co-Authored-By: Codex <noreply@openai.com>"
```

---

## Phase 3: High-Leverage Commands & Verification Gates

### Task 8: Blast Radius Calculator (`synlynk impact`)
**Harness:** `codex` | **Role:** `dev`

**Files:**
- Create: `synlynk/impact.py`
- Modify: `synlynk/cli.py`
- Modify: `synlynk/taxonomy.py`
- Test: `tests/test_impact.py`

**Interfaces:**
- Consumes: Symbol name or file path, `.synlynk/graphify-out/graph.json`
- Produces: `ImpactReport` listing all upstream callers, downstream callees, and corresponding tests.

- [ ] **Step 1: Write failing test**

```python
# tests/test_impact.py
import json
import pytest
from synlynk.impact import calculate_impact


def test_calculate_impact_returns_callers_and_tests(tmp_path):
    out_dir = tmp_path / ".synlynk" / "graphify-out"
    out_dir.mkdir(parents=True)
    graph = {
        "nodes": [
            {"id": "synlynk.db:get_user", "label": "get_user", "file": "synlynk/db.py", "line": 50},
            {"id": "synlynk.auth:login", "label": "login", "file": "synlynk/auth.py", "line": 20},
            {"id": "tests.test_auth:test_login", "label": "test_login", "file": "tests/test_auth.py", "line": 10},
        ],
        "edges": [
            {"source": "synlynk.auth:login", "target": "synlynk.db:get_user", "kind": "calls"},
            {"source": "tests.test_auth:test_login", "target": "synlynk.auth:login", "kind": "calls"},
        ]
    }
    (out_dir / "graph.json").write_text(json.dumps(graph))

    report = calculate_impact(str(tmp_path), target="get_user")
    assert report["target"] == "get_user"
    assert "login" in [c["label"] for c in report["upstream_callers"]]
    assert "test_login" in [t["label"] for t in report["associated_tests"]]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_impact.py -v`  
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.impact'`

- [ ] **Step 3: Implement `synlynk/impact.py` and register CLI command**

Implement BFS/DFS traversal resolving callers, callees, and tests tagged with `tests/` path prefixes. Add CLI verb `impact` in `synlynk/cli.py` and `synlynk/taxonomy.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_impact.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add synlynk/impact.py synlynk/cli.py synlynk/taxonomy.py tests/test_impact.py
git commit -m "feat(impact): add synlynk impact command for instant blast-radius calculation

Co-Authored-By: Codex <noreply@openai.com>"
```

---

### Task 9: Graph-Attested PR Gate (`synlynk pr check --impact-attested`)
**Harness:** `codex` | **Role:** `verifier` / `qa`

**Files:**
- Modify: `synlynk/pr_check.py`
- Test: `tests/test_pr_check_impact.py`

**Interfaces:**
- Consumes: Git diff against base branch, `calculate_impact()`
- Produces: Verification gate ensuring modified symbols have test executions recorded in CI/telemetry.

- [ ] **Step 1: Write failing test**

```python
# tests/test_pr_check_impact.py
import pytest
from synlynk.pr_check import check_pr_impact_attestation


def test_pr_check_fails_when_affected_symbol_has_no_tests(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "synlynk.pr_check._get_modified_symbols_from_diff",
        lambda root: ["critical_auth_function"]
    )
    monkeypatch.setattr(
        "synlynk.impact.calculate_impact",
        lambda root, sym: {"associated_tests": []}
    )

    result = check_pr_impact_attestation(str(tmp_path))
    assert result["passed"] is False
    assert "critical_auth_function has no associated test coverage" in result["error"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_pr_check_impact.py -v`  
Expected: FAIL

- [ ] **Step 3: Implement `--impact-attested` in `synlynk/pr_check.py`**

Wire `check_pr_impact_attestation()` into `synlynk pr check` flag parser.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_pr_check_impact.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add synlynk/pr_check.py tests/test_pr_check_impact.py
git commit -m "feat(pr): add --impact-attested verification gate to synlynk pr check

Co-Authored-By: Codex <noreply@openai.com>"
```

---

### Task 10: Import Cycle Detector & Story Generator (`synlynk heal --cycles`)
**Harness:** `codex` | **Role:** `dev`

**Files:**
- Create: `synlynk/heal_cycles.py`
- Modify: `synlynk/cli.py`
- Modify: `synlynk/taxonomy.py`
- Test: `tests/test_heal_cycles.py`

**Interfaces:**
- Consumes: `.synlynk/graphify-out/graph.json`, `synlynk/db.py` (`create_story`)
- Produces: Detects elementary cycles in package import graphs and creates prioritized refactoring stories in `state.db`.

- [ ] **Step 1: Write failing test**

```python
# tests/test_heal_cycles.py
import json
import pytest
from synlynk.heal_cycles import detect_import_cycles, heal_import_cycles


def test_detect_import_cycles_identifies_circular_dependencies(tmp_path):
    out_dir = tmp_path / ".synlynk" / "graphify-out"
    out_dir.mkdir(parents=True)
    graph = {
        "nodes": [
            {"id": "pkg_a", "label": "pkg_a", "kind": "module"},
            {"id": "pkg_b", "label": "pkg_b", "kind": "module"},
        ],
        "edges": [
            {"source": "pkg_a", "target": "pkg_b", "kind": "imports"},
            {"source": "pkg_b", "target": "pkg_a", "kind": "imports"},
        ]
    }
    (out_dir / "graph.json").write_text(json.dumps(graph))

    cycles = detect_import_cycles(str(tmp_path))
    assert len(cycles) == 1
    assert set(cycles[0]) == {"pkg_a", "pkg_b"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_heal_cycles.py -v`  
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.heal_cycles'`

- [ ] **Step 3: Implement `synlynk/heal_cycles.py` using Tarjan's / Johnson's cycle algorithm**

Detect cycles in the dependency graph, format actionable refactoring story descriptions, and insert into `state.db`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_heal_cycles.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add synlynk/heal_cycles.py synlynk/cli.py synlynk/taxonomy.py tests/test_heal_cycles.py
git commit -m "feat(heal): add circular import detector and story auto-creator

Co-Authored-By: Codex <noreply@openai.com>"
```

---

## Phase 4: Multi-Repo Knowledge Mesh & Spike Evaluation Harness

### Task 11: Multi-Repo Knowledge Mesh Aggregator (`~/.synlynk/global-graph.json`)
**Harness:** `codex` | **Role:** `dev`

**Files:**
- Create: `synlynk/multirepo_graph.py`
- Modify: `synlynk/cli.py`
- Test: `tests/test_multirepo_graph.py`

**Interfaces:**
- Consumes: Multiple repo paths (`synlynk init --multi` or `synlynk join`)
- Produces: Federated graph `~/.synlynk/global-graph.json` with cross-repository HTTP and schema edges.

- [ ] **Step 1: Write failing test**

```python
# tests/test_multirepo_graph.py
import json
import pytest
from synlynk.multirepo_graph import merge_fleet_graphs, infer_cross_repo_edges


def test_merge_fleet_graphs_combines_multiple_repos(tmp_path):
    repo_a = tmp_path / "repo_a"
    repo_b = tmp_path / "repo_b"
    for r in (repo_a, repo_b):
        (r / ".synlynk" / "graphify-out").mkdir(parents=True)

    (repo_a / ".synlynk" / "graphify-out" / "graph.json").write_text(json.dumps({
        "nodes": [{"id": "repo_a:api_endpoint", "label": "/users", "kind": "route"}],
        "edges": []
    }))
    (repo_b / ".synlynk" / "graphify-out" / "graph.json").write_text(json.dumps({
        "nodes": [{"id": "repo_b:client_fetch", "label": "fetch('/users')", "kind": "fetch"}],
        "edges": []
    }))

    merged = merge_fleet_graphs([str(repo_a), str(repo_b)])
    assert len(merged["nodes"]) == 2

    edges = infer_cross_repo_edges(merged)
    assert len(edges) == 1
    assert edges[0]["source"] == "repo_b:client_fetch"
    assert edges[0]["target"] == "repo_a:api_endpoint"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_multirepo_graph.py -v`  
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.multirepo_graph'`

- [ ] **Step 3: Implement `synlynk/multirepo_graph.py`**

Implement multi-repo merger, namespace prefixing, and heuristic cross-boundary edge inference.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_multirepo_graph.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add synlynk/multirepo_graph.py synlynk/cli.py tests/test_multirepo_graph.py
git commit -m "feat(mesh): add multi-repo federated knowledge mesh and cross-repo edge inference

Co-Authored-By: Codex <noreply@openai.com>"
```

---

### Task 12: Reusable Spike Evaluation Engine (`synlynk spike eval`)
**Harness:** `codex` & `claude` | **Role:** `dev` / `architect`

**Files:**
- Create: `synlynk/spike.py`
- Modify: `synlynk/cli.py`
- Modify: `synlynk/taxonomy.py`
- Test: `tests/test_spike.py`

**Interfaces:**
- Consumes: Candidate name, scenario, baseline
- Produces: Automated isolated shadow worktree benchmark, telemetry collection, and receipt markdown in `project-docs/spikes/`.

- [ ] **Step 1: Write failing test**

```python
# tests/test_spike.py
import pytest
from synlynk.spike import run_spike_eval, generate_spike_receipt


def test_generate_spike_receipt_computes_deltas():
    baseline_stats = {"input_tokens": 38500, "turns": 9, "duration_s": 28.2, "recall": 0.80}
    candidate_stats = {"input_tokens": 1200, "turns": 1, "duration_s": 0.8, "recall": 1.00}

    receipt = generate_spike_receipt(
        candidate="graphify",
        scenario="codebase-exploration",
        baseline="grep-native",
        baseline_metrics=baseline_stats,
        candidate_metrics=candidate_stats,
    )
    assert "# Spike Evaluation Receipt: graphify" in receipt
    assert "-96.9%" in receipt  # token savings delta
    assert "+20.0%" in receipt  # recall delta
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_spike.py -v`  
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.spike'`

- [ ] **Step 3: Implement `synlynk/spike.py` and wire into `synlynk decide --panel`**

Implement automated worktree provisioning, baseline vs. candidate runner, telemetry comparison, and receipt generator.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_spike.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add synlynk/spike.py synlynk/cli.py synlynk/taxonomy.py tests/test_spike.py
git commit -m "feat(spike): add reusable spike evaluation harness and receipt generator

Co-Authored-By: Claude Sonnet <noreply@anthropic.com>"
```

---

## Verification Checklist & Acceptance Gates

1. **Full Test Suite:** Run `pytest tests/test_tool_installer.py tests/test_discovery_graphify.py tests/test_viz_graphify.py tests/test_coldstart_graphify.py tests/test_graphify_skills.py tests/test_charter_graphify.py tests/test_pack.py tests/test_impact.py tests/test_pr_check_impact.py tests/test_heal_cycles.py tests/test_multirepo_graph.py tests/test_spike.py -v`. All 12 test suites must pass 100% green.
2. **Zero-Failure Fallback Check:** Run full test suite with `PATH=""` or monkeypatched `shutil.which = lambda x: None`. Zero crashes or unhandled exceptions.
3. **Commit Attestation:** Every commit contains the required `Co-Authored-By` trailer matching the executing harness.
4. **Token Budget Verification:** Verify `_cut_to_token_budget` strictly bounds generated context packs to $\le 1,500$ tokens.
