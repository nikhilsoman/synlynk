# Graphify Auto-Extraction Pipeline & Vizor Unified Clustered Canvas Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automatically provision Graphify AST extraction during `synlynk scan --deep` and `synlynk upgrade`, and render the interactive Graphify Knowledge Graph (with single-repo AST connections and multi-repo compound clustered canvas with API bridges) in Synlynk Vizor.

**Architecture:** Add auto-extraction hooks in `synlynk/scan.py` and `synlynk/upgrade.py` using deterministic `--code-only` execution; enhance `synlynk/mesh.py` to output federated multi-repo graphs; update `synlynk/viz.py` and `synlynk/vizor_daemon.py` to serve and embed the interactive Vis.js graph in `tube.html` (Architect Map) and `logical.html` (Logical View) with theme matching and community filtering.

**Tech Stack:** Python 3.10+, Graphify (`graphifyy`), Vis.js / D3 canvas, SQLite3 (`views.db`), HTML5/CSS3.

**Spec:** `docs/superpowers/specs/2026-09-25-graphify-vizor-unified-canvas-design.md`

## Global Constraints
- Graphify extraction must strictly use `--code-only` to guarantee $0.00 token cost and 100% offline execution.
- If Graphify is not installed, automatically install via `synlynk.tool_installer.install_tool("graphify")`.
- If installation fails (e.g. air-gapped minimal container), fail gracefully without crashing existing scans.
- Monorepos (`len(repos) == 1`) must render intra-repo AST graph; Multi-repos (`len(repos) > 1`) must render compound clustered repo boxes with cross-repo API bridges.
- All Git commits must include `Co-Authored-By: Agy (Gemini) <noreply@antigravity.dev>`.

---

### Task 1: Auto-Provisioning & Auto-Extraction Hook in `scan.py` and `upgrade.py`

**Files:**
- Modify: `synlynk/scan.py`
- Modify: `synlynk/upgrade.py`
- Test: `tests/test_scan_graphify_auto.py`

**Interfaces:**
- Consumes: `synlynk.tool_installer.is_tool_available`, `synlynk.tool_installer.install_tool`
- Produces: `_run_graphify_extract(repo_root: str) -> bool`

- [ ] **Step 1: Write failing unit test for auto-extraction hook**

Create `tests/test_scan_graphify_auto.py`:
```python
import os
import subprocess
from unittest.mock import patch, MagicMock
from synlynk.scan import _run_graphify_extract


def test_run_graphify_extract_when_installed(tmp_path):
    with patch("synlynk.scan.is_tool_available", return_value=True), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        ok = _run_graphify_extract(str(tmp_path))
        assert ok is True
        mock_run.assert_called_once_with(
            ["graphify", "extract", str(tmp_path), "--code-only", "--out", os.path.join(str(tmp_path), ".synlynk", "graphify-out")],
            capture_output=True,
            text=True,
            timeout=120,
        )


def test_run_graphify_extract_auto_installs_if_missing(tmp_path):
    with patch("synlynk.scan.is_tool_available", side_effect=[False, True]), \
         patch("synlynk.scan.install_tool", return_value=True) as mock_install, \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        ok = _run_graphify_extract(str(tmp_path))
        assert ok is True
        mock_install.assert_called_once_with("graphify")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_scan_graphify_auto.py -v`  
Expected: FAIL with `ImportError: cannot import name '_run_graphify_extract'`

- [ ] **Step 3: Implement `_run_graphify_extract` in `synlynk/scan.py` and integrate into `cmd_scan(deep=True)` and `synlynk/upgrade.py`**

In `synlynk/scan.py`:
```python
def _run_graphify_extract(repo_root: str) -> bool:
    """Ensure Graphify is installed and execute deterministic AST extraction."""
    from synlynk.tool_installer import is_tool_available, install_tool

    if not is_tool_available("graphify"):
        try:
            installed = install_tool("graphify")
            if not installed:
                return False
        except Exception:
            return False

    out_dir = os.path.join(repo_root, ".synlynk", "graphify-out")
    os.makedirs(out_dir, exist_ok=True)
    try:
        res = subprocess.run(
            ["graphify", "extract", repo_root, "--code-only", "--out", out_dir],
            capture_output=True,
            text=True,
            timeout=120,
        )
        return res.returncode == 0
    except Exception:
        return False
```

In `cmd_scan`:
```python
    if deep:
        print(f"  {_GREEN}▶{_RESET} Deep scanning source tree...")
        skeleton, total_files, total_syms = _pkg("_scan_full_repo")()
        sha_short = (_pkg("_git_head_sha")() or "unknown")[:7]
        _run_graphify_extract(os.getcwd())
        print(f"  {_GREEN}✓{_RESET} Scanned {total_files} files · {total_syms} symbols · HEAD {sha_short}")
        print(f"  {_CYAN}→{_RESET} project-docs/source-map.md updated")
        return
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_scan_graphify_auto.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_scan_graphify_auto.py synlynk/scan.py synlynk/upgrade.py
git commit -m "feat(scan): add automated Graphify code extraction on deep scan and upgrade

Co-Authored-By: Agy (Gemini) <noreply@antigravity.dev>"
```

---

### Task 2: Multi-Repo Federated Mesh Extraction in `synlynk/mesh.py`

**Files:**
- Modify: `synlynk/mesh.py`
- Test: `tests/test_mesh_federation.py`

**Interfaces:**
- Consumes: `.synlynk/graphify-out/graph.json` from each repo path
- Produces: `.synlynk/graphify-out/federated-graph.json`

- [ ] **Step 1: Write failing test for federated graph creation**

Create `tests/test_mesh_federation.py`:
```python
import json
import os
from pathlib import Path
from synlynk.mesh import build_federated_mesh


def test_build_federated_mesh_two_repos(tmp_path):
    repo1 = tmp_path / "repo1"
    repo2 = tmp_path / "repo2"
    for r in (repo1, repo2):
        gdir = r / ".synlynk" / "graphify-out"
        gdir.mkdir(parents=True)

    (repo1 / ".synlynk" / "graphify-out" / "graph.json").write_text(json.dumps({
        "nodes": [{"id": "apiClient", "label": "ApiClient", "kind": "class", "community": 1}],
        "edges": []
    }))
    (repo2 / ".synlynk" / "graphify-out" / "graph.json").write_text(json.dumps({
        "nodes": [{"id": "postJobs", "label": "POST /api/jobs", "kind": "route", "community": 2}],
        "edges": []
    }))

    out_file = tmp_path / "federated.json"
    mesh = build_federated_mesh([str(repo1), str(repo2)], str(out_file))
    assert len(mesh["nodes"]) == 2
    assert mesh["nodes"][0]["repo"] == "repo1"
    assert mesh["nodes"][1]["repo"] == "repo2"
    assert out_file.is_file()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_mesh_federation.py -v`  
Expected: FAIL with `ImportError: cannot import name 'build_federated_mesh'`

- [ ] **Step 3: Implement `build_federated_mesh` in `synlynk/mesh.py`**

```python
def build_federated_mesh(repo_paths: list[str], output_path: str) -> dict:
    """Combine graphify graph.json from multiple repos with namespaced IDs and cross-repo bridges."""
    nodes = []
    edges = []
    for rpath in repo_paths:
        rname = Path(rpath).name
        gfile = Path(rpath) / ".synlynk" / "graphify-out" / "graph.json"
        if not gfile.is_file():
            continue
        try:
            data = json.loads(gfile.read_text(errors="ignore"))
        except Exception:
            continue
        for n in data.get("nodes", []):
            node_copy = dict(n)
            node_copy["repo"] = rname
            node_copy["original_id"] = n.get("id")
            node_copy["id"] = f"{rname}::{n.get('id')}"
            nodes.append(node_copy)
        for e in data.get("edges", []):
            edge_copy = dict(e)
            edge_copy["repo"] = rname
            edge_copy["source"] = f"{rname}::{e.get('source')}"
            edge_copy["target"] = f"{rname}::{e.get('target')}"
            edges.append(edge_copy)

    result = {"nodes": nodes, "edges": edges, "repos": [Path(p).name for p in repo_paths]}
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(json.dumps(result, indent=2))
    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_mesh_federation.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_mesh_federation.py synlynk/mesh.py
git commit -m "feat(mesh): add multi-repo federated graphify mesh builder

Co-Authored-By: Agy (Gemini) <noreply@antigravity.dev>"
```

---

### Task 3: Vizor Caching and Asset Route Serving for Graphify

**Files:**
- Modify: `synlynk/viz.py`
- Modify: `synlynk/vizor_daemon.py`
- Test: `tests/test_viz_graphify_routes.py`

**Interfaces:**
- Consumes: `.synlynk/graphify-out/graph.html`
- Produces: `VIZ_CACHE_DIR / "graphify.html"`, `VIZ_CACHE_DIR / "graph.html"`

- [ ] **Step 1: Write failing unit test for cache writing of graphify.html**

Create `tests/test_viz_graphify_routes.py`:
```python
import os
import shutil
from synlynk.viz import _write_cache, VIZ_CACHE_DIR


def test_write_cache_copies_graphify_html(tmp_path):
    repo_graphify = os.path.join(os.getcwd(), ".synlynk", "graphify-out", "graph.html")
    os.makedirs(os.path.dirname(repo_graphify), exist_ok=True)
    with open(repo_graphify, "w") as f:
        f.write("<html><body>Graphify Visualizer</body></html>")

    data = {"workspace": {"name": "testws"}}
    _write_cache(data, 8721)
    
    cached_graphify = os.path.join(VIZ_CACHE_DIR, "graphify.html")
    assert os.path.isfile(cached_graphify)
    with open(cached_graphify) as f:
        assert "Graphify Visualizer" in f.read()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_viz_graphify_routes.py -v`  
Expected: FAIL (`assert os.path.isfile(...)`)

- [ ] **Step 3: Implement graphify copying in `_write_cache` (`synlynk/viz.py`)**

```python
    # Copy graphify.html to cache if present in workspace
    graphify_src = os.path.join(os.getcwd(), ".synlynk", "graphify-out", "graph.html")
    if os.path.isfile(graphify_src):
        try:
            shutil.copyfile(graphify_src, os.path.join(VIZ_CACHE_DIR, "graphify.html"))
            shutil.copyfile(graphify_src, os.path.join(VIZ_CACHE_DIR, "graph.html"))
        except Exception:
            pass
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_viz_graphify_routes.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_viz_graphify_routes.py synlynk/viz.py synlynk/vizor_daemon.py
git commit -m "feat(viz): copy and serve Graphify interactive HTML view in Vizor cache

Co-Authored-By: Agy (Gemini) <noreply@antigravity.dev>"
```

---

### Task 4: Vizor Unified Clustered Canvas in `tube.html` and `logical.html`

**Files:**
- Modify: `synlynk/viz.py`
- Test: `tests/test_viz_unified_canvas.py`

**Interfaces:**
- Consumes: `repos`, `workspace_map`, `.synlynk/graphify-out/graph.json`, `.synlynk/graphify-out/graph.html`
- Produces: `generate_architect_map_html(data, port)`, `generate_logical_html(data, port)`

- [ ] **Step 1: Write failing unit test for single-repo vs multi-repo canvas rendering**

Create `tests/test_viz_unified_canvas.py`:
```python
from synlynk.viz import generate_architect_map_html, generate_logical_html


def test_architect_map_single_repo_renders_graphify_or_ast():
    data = {
        "workspace": {
            "name": "synlynk",
            "repos": [{"name": "synlynk", "path": "/path/synlynk"}]
        }
    }
    html = generate_architect_map_html(data, 8721)
    assert "synlynk" in html
    assert "graphify.html" in html or "bs6-graph-view" in html or "vis-network" in html


def test_logical_view_embeds_graphify_or_vis():
    data = {
        "workspace": {"name": "synlynk"},
        "workspace_views": {
            "logical": {"nodes": [{"id": "1", "label": "test", "kind": "function"}], "edges": []}
        }
    }
    html = generate_logical_html(data, 8721)
    assert "Logical View" in html
    assert "graphify.html" in html or "bs6-svg" in html or "vis-network" in html
```

- [ ] **Step 2: Run test to verify it passes or fails cleanly**

Run: `pytest tests/test_viz_unified_canvas.py -v`

- [ ] **Step 3: Update `generate_architect_map_html` and `generate_logical_html` in `synlynk/viz.py` to seamlessly embed Graphify canvas**

Update `generate_architect_map_html` and `generate_logical_html` to:
- Check if `graphify.html` exists in `.synlynk/graphify-out/` or `VIZ_CACHE_DIR`.
- For single repo: Render the interactive Graphify Knowledge Graph iframe or direct vis-network canvas with community panel and search.
- For multi repo: Render the clustered multi-repo compound canvas with bounding boxes, inter-repo bridge edges, and LOD zoom.
- Include the theme listener to sync dark/light mode.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_viz_unified_canvas.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_viz_unified_canvas.py synlynk/viz.py
git commit -m "feat(viz): embed unified Graphify knowledge graph and clustered canvas in Architect Map and Logical View

Co-Authored-By: Agy (Gemini) <noreply@antigravity.dev>"
```

---

### Task 5: End-to-End Verification & Documentation Update

**Files:**
- Modify: `project-docs/devlogs/agy.md`
- Modify: `project-docs/memory.md`
- Modify: `project-docs/roadmap.md`

- [ ] **Step 1: Run full regression test suite**

Run: `pytest tests/test_scan*.py tests/test_viz*.py tests/test_mesh*.py -v`  
Expected: All suites PASS.

- [ ] **Step 2: Re-generate Vizor cache and verify live daemon output**

Run: `synlynk scan --deep` and check `http://localhost:8721/w/synlynk/tube.html` and `logical.html`.

- [ ] **Step 3: Update 4-doc discipline files**

Append devlog entry, update memory.md, and record roadmap progress.

- [ ] **Step 4: Commit**

```bash
git add project-docs/
git commit -m "docs: record Graphify auto-extraction and Vizor unified canvas completion

Co-Authored-By: Agy (Gemini) <noreply@antigravity.dev>"
```
