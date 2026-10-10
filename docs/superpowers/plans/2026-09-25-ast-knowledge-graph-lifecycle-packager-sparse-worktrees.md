# AST Knowledge Graph Lifecycle, Rich Context Packager & AST-Scoped Sparse Worktrees Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement UI graph refresh action button, automated background refresh on git drift in watch.py, rich AST context packager in pack.py (with signature inlining and test discovery), and AST-guided directory cone derivation for sparse worktrees in worktree_sparse.py.

**Architecture:** Enhances Vizor UI (`synlynk/viz.py`), daemon watch loop (`synlynk/watch.py`), context generator (`synlynk/pack.py`), and sparse worktree engine (`synlynk/worktree_sparse.py`) using Graphify AST graphs.

**Tech Stack:** Python 3.10+, SQLite, pytest, Vanilla JS / HTML5

**Spec:** `docs/superpowers/specs/2026-09-25-ast-knowledge-graph-lifecycle-packager-sparse-worktrees-design.md`

## Global Constraints
- Zero external token cost for AST extraction and graph analysis ($0.00 token cost, pure offline execution).
- Graceful degradation: all components must fall back safely if `.synlynk/graphify-out/` or Graphify is unavailable.
- All commits must include trailer: `Co-Authored-By: Agy (Gemini) <noreply@antigravity.dev>`.
- Python 3.10 and 3.12 compatibility; 100% green unit tests.

---

### Task 1: Rich AST Context Packager (`synlynk/pack.py`)

**Files:**
- Modify: `synlynk/pack.py`
- Test: `tests/test_pack_rich.py`

**Interfaces:**
- Consumes: `.synlynk/graphify-out/graph.json`
- Produces: `synthesize_context_pack(repo_root: str, task_text: str = "", story_id: Optional[str] = None, token_budget: int = 1500) -> str`

- [ ] **Step 1: Write the failing tests in `tests/test_pack_rich.py`**
  - Test canonical community clustering in output.
  - Test signature and docstring inlining for top target symbols.
  - Test reverse test suite discovery (detecting `tests/test_*.py` callers).
  - Test token budget bounding.

- [ ] **Step 2: Run test to confirm failure**
  - `pytest tests/test_pack_rich.py`

- [ ] **Step 3: Implement rich context synthesis in `synlynk/pack.py`**
  - Enhance node scoring and attribute parsing (`signature`, `docstring`, `desc`, `kind`).
  - Extract test callers from inbound edge map.
  - Render formatted markdown sections: *Primary Subsystems & Communities*, *Target Symbols & Interfaces*, *Suggested Verification Test Targets*.

- [ ] **Step 4: Run tests to confirm pass**
  - `pytest tests/test_pack_rich.py tests/test_pack.py`

- [ ] **Step 5: Commit Task 1**
  - `git commit -m "feat(pack): rich AST context packager with signatures and test discovery (#1787)"`

---

### Task 2: AST-Guided Sparse Worktrees (`synlynk/worktree_sparse.py`)

**Files:**
- Modify: `synlynk/worktree_sparse.py`
- Test: `tests/test_worktree_sparse_ast.py`

**Interfaces:**
- Consumes: `synlynk.pack.synthesize_context_pack` / `.synlynk/graphify-out/graph.json`
- Produces: `derive_sparse_cone_paths_from_graph(repo_root: str, task_text: str = "", story_id: Optional[str] = None, max_dirs: int = 8) -> List[str]`

- [ ] **Step 1: Write the failing tests in `tests/test_worktree_sparse_ast.py`**
  - Test `derive_sparse_cone_paths_from_graph()` with sample graph JSON returning minimal directory cones.
  - Test fallback to `MANDATORY_SPARSE_CONE_DIRS` when graph is missing or unparseable.

- [ ] **Step 2: Run test to confirm failure**
  - `pytest tests/test_worktree_sparse_ast.py`

- [ ] **Step 3: Implement `derive_sparse_cone_paths_from_graph()` in `synlynk/worktree_sparse.py`**
  - Query graph file paths for target symbols, 1-hop callers, and callees.
  - Extract top-level directory names.
  - Merge and sort deduplicated directory cones with mandatory paths.

- [ ] **Step 4: Run tests to confirm pass**
  - `pytest tests/test_worktree_sparse_ast.py tests/test_worktree_sparse.py`

- [ ] **Step 5: Commit Task 2**
  - `git commit -m "feat(worktree): AST-guided cone directory derivation for sparse worktrees (#1787)"`

---

### Task 3: Automated Lifecycle Triggers in `watch.py` & `dispatch.py`

**Files:**
- Modify: `synlynk/watch.py`
- Modify: `synlynk/dispatch.py`
- Test: `tests/test_watch_graph_drift.py`

**Interfaces:**
- Consumes: `synlynk.scan._run_graphify_extract`
- Produces: `_trigger_background_graph_refresh(repo_root: str)`

- [ ] **Step 1: Write the failing tests in `tests/test_watch_graph_drift.py`**
  - Test `watch.py` detecting HEAD commit drift and calling background extract hook.
  - Test debounce cooldown behavior (no re-trigger within cooldown window).
  - Test `dispatch.py` JIT cache check triggering extraction when graph is missing.

- [ ] **Step 2: Run test to confirm failure**
  - `pytest tests/test_watch_graph_drift.py`

- [ ] **Step 3: Implement background trigger in `synlynk/watch.py` and JIT check in `synlynk/dispatch.py`**
  - Add `_trigger_background_graph_refresh` in `synlynk/watch.py` running in detached thread with cooldown check.
  - Check graph file freshness in `synlynk/dispatch.py` prior to packing context.

- [ ] **Step 4: Run tests to confirm pass**
  - `pytest tests/test_watch_graph_drift.py`

- [ ] **Step 5: Commit Task 3**
  - `git commit -m "feat(watch+dispatch): automated background graph refresh on git drift (#1787)"`

---

### Task 4: Topbar UI Manual Refresh Button & Status Feedback (`synlynk/viz.py`)

**Files:**
- Modify: `synlynk/viz.py`
- Test: `tests/test_viz_refresh_button.py`

**Interfaces:**
- Consumes: `POST /w/<slug>/api/graph/refresh`
- Produces: `#am-kg-refresh-btn` and iframe reload handler

- [ ] **Step 1: Write the failing tests in `tests/test_viz_refresh_button.py`**
  - Verify `#am-kg-refresh-btn` button markup exists in `_ARCHITECT_MAP_JS` / `tube.html` and `logical.html`.
  - Verify click event listener and POST endpoint invocation logic.

- [ ] **Step 2: Run test to confirm failure**
  - `pytest tests/test_viz_refresh_button.py`

- [ ] **Step 3: Implement refresh button and interactive JS handler in `synlynk/viz.py`**
  - Add `<button id="am-kg-refresh-btn" class="am-btn am-btn-subtle">🔄 Refresh Graph</button>` into `.am-kg-topbar`.
  - Add event listener: disable button, add spinner, call `fetch('/w/' + slug + '/api/graph/refresh', {method: 'POST'})`, reload iframe on completion, update status chip, show toast.

- [ ] **Step 4: Run tests to confirm pass**
  - `pytest tests/test_viz_refresh_button.py tests/test_viz_unified_canvas.py`

- [ ] **Step 5: Commit Task 4**
  - `git commit -m "feat(viz): topbar manual graph refresh action and loading feedback (#1787)"`

---

### Task 5: Full Regression, State Sync & Documentation Checkpoint

**Files:**
- Modify: `project-docs/devlogs/agy.md`
- Modify: `project-docs/costs.md`
- Modify: `project-docs/memory.md`

- [ ] **Step 1: Run focused regression suite**
  - `pytest tests/test_pack_rich.py tests/test_worktree_sparse_ast.py tests/test_watch_graph_drift.py tests/test_viz_refresh_button.py tests/test_viz_unified_canvas.py`

- [ ] **Step 2: Run full test suite across workspace**
  - `pytest tests/`

- [ ] **Step 3: Update documentation and checkpoint**
  - Record task completion in `project-docs/devlogs/agy.md`, `project-docs/costs.md`, `project-docs/memory.md`.
  - `git commit -m "docs: finalize phase 1 AST knowledge graph lifecycle and packager integration (#1787)"`
