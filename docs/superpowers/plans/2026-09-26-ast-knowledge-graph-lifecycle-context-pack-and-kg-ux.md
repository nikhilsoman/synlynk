# AST Knowledge Graph Lifecycle, Rich Context Packaging, Minimal Cone Worktrees & Deep Interactive UX Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement automated background AST extraction on HEAD drift, graph-backed sub-1.5k token context packaging with reverse test discovery, AST-guided minimal cone sparse worktrees, topological feature schemas for Jev System 1 routing, and deep Vizor interactive UX (ego network inspect, `/api/source` code drawer, kind-based L0 filters, ESC exit ergonomics) under master goal `goal-e3840370`.

**Architecture:** A unified pipeline connecting the background AST extractor (`synlynk watch`, `POST /api/graph/refresh`) to task packaging (`synlynk pack`), lightweight worktree checkout (`synlynk worktree_sparse`), fast routing feature emission, and rich interactive Vizor canvas views (`tube.html`, `logical.html`) with sliding syntax-highlighted code inspection.

**Tech Stack:** Python 3.10+, AST parser, SQLite3 (`state.db`), vis-network (JavaScript), HTML5/CSS3 sliding drawer.

**Spec:** `docs/superpowers/specs/2026-09-26-ast-knowledge-graph-lifecycle-context-pack-and-kg-ux-design.md`

## Global Constraints
- All extraction must run strictly with `--code-only` guaranteeing $0.00 token cost and 100% offline execution.
- If `graph.json` is absent, all consumers (`synlynk pack`, `synlynk worktree_sparse`, `tube.html`) must degrade gracefully without crashing.
- Path traversal protection on `/api/source` must strictly reject any file path resolving outside `repo_root`.
- All Git commits must include `Co-Authored-By: Agy (Gemini) <noreply@antigravity.dev>`.

---

### Task 1: AST Extraction Drift Watcher & Cache Invalidation

**Files:**
- Modify: `synlynk/watch.py`
- Modify: `synlynk/scan.py`
- Test: `tests/test_watch_graph_drift.py`

**Interfaces:**
- Produces: `check_and_refresh_ast_on_drift(repo_root: str) -> bool`
- Updates: `.synlynk/manifest.json` with `built_at = HEAD_SHA`

- [ ] **Step 1: Write failing test for HEAD drift detection and background extraction**

```python
# tests/test_watch_graph_drift.py
import json
import pytest
from pathlib import Path
from synlynk.watch import check_and_refresh_ast_on_drift

def test_watch_detects_head_drift_and_triggers_extract(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    syn = repo / ".synlynk"
    syn.mkdir()
    manifest = syn / "manifest.json"
    manifest.write_text(json.dumps({"built_at": "old-sha-123"}))
    
    # Mock git rev-parse HEAD
    monkeypatch.setattr("synlynk.watch._get_head_commit", lambda r: "new-sha-456")
    extracted = []
    monkeypatch.setattr("synlynk.scan._run_graphify_extract", lambda r, code_only: extracted.append(r) or True)
    
    refreshed = check_and_refresh_ast_on_drift(str(repo))
    assert refreshed is True
    assert len(extracted) == 1
    updated_manifest = json.loads(manifest.read_text())
    assert updated_manifest["built_at"] == "new-sha-456"
```

- [ ] **Step 2: Run test to confirm failure**
- [ ] **Step 3: Implement `check_and_refresh_ast_on_drift` in `synlynk/watch.py`**
- [ ] **Step 4: Verify test passes**
- [ ] **Step 5: Commit changes**

---

### Task 2: High-Density Context Packager with AST Signatures & Reverse Test Discovery

**Files:**
- Modify: `synlynk/pack.py`
- Test: `tests/test_pack_rich_context.py`

**Interfaces:**
- Produces: `synthesize_context_pack(repo_root: str, task_text: str, story_id: Optional[str], token_budget: int = 1500) -> str`
- Produces: `extract_symbol_signatures_and_tests(repo_root: str, symbols: List[str]) -> Dict[str, Any]`

- [ ] **Step 1: Write failing test for signature inlining and reverse test mapping**

```python
# tests/test_pack_rich_context.py
import json
import pytest
from pathlib import Path
from synlynk.pack import synthesize_context_pack

def test_synthesize_context_pack_inlines_signatures_and_tests(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    syn = repo / ".synlynk" / "graphify-out"
    syn.mkdir(parents=True)
    
    # Create dummy source and test files
    src = repo / "calculator.py"
    src.write_text('def add(a: int, b: int) -> int:\n    """Add two numbers."""\n    return a + b\n')
    
    test_file = repo / "tests" / "test_calc.py"
    test_file.parent.mkdir(parents=True)
    test_file.write_text('from calculator import add\ndef test_add():\n    assert add(1, 2) == 3\n')
    
    graph_data = {
        "nodes": [
            {"id": "calculator.py::add", "name": "add", "file": "calculator.py", "kind": "Function", "community": 0},
            {"id": "tests/test_calc.py::test_add", "name": "test_add", "file": "tests/test_calc.py", "kind": "Function", "community": 0}
        ],
        "edges": [
            {"source": "tests/test_calc.py::test_add", "target": "calculator.py::add", "relation": "calls"}
        ]
    }
    (syn / "graph.json").write_text(json.dumps(graph_data))
    
    pack = synthesize_context_pack(str(repo), task_text="Fix bug in add function")
    assert "calculator.py::add" in pack
    assert "def add(a: int, b: int) -> int" in pack
    assert "Add two numbers" in pack
    assert "tests/test_calc.py" in pack
```

- [ ] **Step 2: Run test to confirm failure**
- [ ] **Step 3: Implement AST signature parsing and test lookup in `synlynk/pack.py`**
- [ ] **Step 4: Verify test passes**
- [ ] **Step 5: Commit changes**

---

### Task 3: AST-Guided Minimal Cone Derivation for Sparse Worktrees & Jev Feature Vector

**Files:**
- Modify: `synlynk/worktree_sparse.py`
- Modify: `synlynk/impact.py`
- Test: `tests/test_worktree_sparse_ast.py`

**Interfaces:**
- Produces: `derive_sparse_cone_paths_from_graph(repo_root: str, task_text: str, story_id: Optional[str]) -> List[str]`
- Produces: `export_topological_features(repo_root: str, task_text: str) -> Dict[str, Any]`

- [ ] **Step 1: Write failing test for minimal cone derivation and topological metrics**

```python
# tests/test_worktree_sparse_ast.py
import json
import pytest
from pathlib import Path
from synlynk.worktree_sparse import derive_sparse_cone_paths_from_graph
from synlynk.impact import export_topological_features

def test_derive_sparse_cone_paths_and_features(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    syn = repo / ".synlynk" / "graphify-out"
    syn.mkdir(parents=True)
    
    graph_data = {
        "nodes": [
            {"id": "synlynk/db.py::conn", "file": "synlynk/db.py", "community": 1},
            {"id": "synlynk/viz.py::handler", "file": "synlynk/viz.py", "community": 0}
        ],
        "edges": [
            {"source": "synlynk/viz.py::handler", "target": "synlynk/db.py::conn", "relation": "calls"}
        ]
    }
    (syn / "graph.json").write_text(json.dumps(graph_data))
    
    cones = derive_sparse_cone_paths_from_graph(str(repo), task_text="viz database handler")
    assert "synlynk" in cones
    assert ".synlynk" in cones
    assert "tests" in cones
    
    features = export_topological_features(str(repo), task_text="viz database handler")
    assert "impact_score" in features
    assert "blast_radius_files" in features
    assert features["blast_radius_files"] >= 1
```

- [ ] **Step 2: Run test to confirm failure**
- [ ] **Step 3: Implement minimal cone and feature extraction**
- [ ] **Step 4: Verify test passes**
- [ ] **Step 5: Commit changes**

---

### Task 4: Secure `/api/source` Code Inspection Endpoint

**Files:**
- Modify: `synlynk/viz.py`
- Modify: `synlynk/vizor_daemon.py`
- Test: `tests/test_viz_source_api.py`

**Interfaces:**
- Route: `GET /api/source?file=<path>&start=<line>&end=<line>`
- Security: Path traversal rejected with HTTP 403/400

- [ ] **Step 1: Write failing test for `/api/source` endpoint**

```python
# tests/test_viz_source_api.py
import urllib.request
import json
import pytest
from synlynk.viz import VizorHandler

def test_api_source_endpoint_returns_file_content(tmp_path, monkeypatch):
    test_file = tmp_path / "demo.py"
    test_file.write_text("line 1\nline 2\nline 3\nline 4\nline 5\n")
    
    from synlynk.viz import _get_source_slice
    res = _get_source_slice(str(tmp_path), "demo.py", start_line=2, end_line=4)
    assert res["status"] == "ok"
    assert res["start_line"] == 2
    assert res["end_line"] == 4
    assert res["content"] == "line 2\nline 3\nline 4"

def test_api_source_rejects_path_traversal(tmp_path):
    from synlynk.viz import _get_source_slice
    res = _get_source_slice(str(tmp_path), "../../etc/passwd")
    assert res["status"] == "error"
```

- [ ] **Step 2: Run test to confirm failure**
- [ ] **Step 3: Implement `_get_source_slice` and route handling in `VizorHandler`**
- [ ] **Step 4: Verify test passes**
- [ ] **Step 5: Commit changes**

---

### Task 5: Deep Vizor KG UX (Ego Mask, Multi-Click Grow, Source Drawer & L0 Kind Filters)

**Files:**
- Modify: `synlynk/viz.py` (`tube.html`, `logical.html`, Graphify template injection)
- Test: `tests/test_viz_kg_interactive.py`

**Interfaces:**
- Injected PostMessage listeners: `inspect-node`, `grow-ego-network`, `open-source-drawer`, `filter-kind-l0`, `reset-inspect`
- Sliding drawer DOM: `.kg-source-drawer`

- [ ] **Step 1: Write failing test verifying template script injection and drawer elements**

```python
# tests/test_viz_kg_interactive.py
import pytest
from synlynk.viz import generate_architect_map_html

def test_architect_map_contains_kg_source_drawer_and_inspect_scripts(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".synlynk").mkdir()
    
    html = generate_architect_map_html(str(repo), repos=[str(repo)])
    assert "kg-source-drawer" in html
    assert "filter-kind-l0" in html
    assert "grow-ego-network" in html
    assert "keydown" in html or "Escape" in html
```

- [ ] **Step 2: Run test to confirm failure**
- [ ] **Step 3: Implement sliding code drawer, ego-network isolate/grow script, and L0 kind filter toolbar**
- [ ] **Step 4: Verify test passes**
- [ ] **Step 5: Commit changes**

---

## Plan Verification Checkpoints
1. Full test suite: `pytest tests/test_watch_graph_drift.py tests/test_pack_rich_context.py tests/test_worktree_sparse_ast.py tests/test_viz_source_api.py tests/test_viz_kg_interactive.py` passes 100%.
2. Full repository regression suite: `pytest` passes all 3,290+ tests.
3. PR created on GitHub, approved via QA gate authority, and merged into `main`.
