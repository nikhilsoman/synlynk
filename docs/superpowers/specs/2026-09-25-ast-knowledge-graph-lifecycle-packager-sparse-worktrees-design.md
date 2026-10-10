# Design Specification: AST Knowledge Graph Lifecycle Triggers, Rich Context Packager & AST-Scoped Sparse Worktrees

**Status:** Approved  
**Date:** 2026-09-25  
**Author:** Agy (Antigravity) & Nikhil Soman  
**Governing Goal:** `goal-e3840370` (*Consolidated Vizor Master Control Plane*)  
**Issue / Story:** Issue #1787 / `story-3cddd9d2`  
**License Compliance:** MIT / Apache-2.0  

---

## 1. Executive Summary & Problem Statement

### 1.1 Background & Opportunities
In Milestone v0.22.0, we introduced local zero-cost AST extraction via Graphify, rendering interactive knowledge graphs across Vizor's Architect Map (`tube.html`) and Logical View (`logical.html`). In PR #1785, we shipped Level-of-Detail (LOD) zoom degree filtering, Google Maps-style zoom steppers, and canonical node metadata.

However, three critical operational opportunities remain:
1. **Graph Lifecycle Freshness:** When code changes are committed or merged to `main`, the AST knowledge graph becomes stale. Currently, extraction is only triggered on `synlynk scan --deep` or via manual API calls. We need both explicit UI action controls and automated background refresh hooks.
2. **High-Context Agent Bootstrapping:** Dispatched agents currently spend exploratory turns and tokens locating target interfaces and relevant test suites. The context packager (`synlynk/pack.py`) needs to leverage community clusters, symbol signatures/docstrings, and reverse call-edge test discovery to bootstrap agents on Turn 1 with zero hallucination.
3. **Monorepo Storage & Checkout Amplification:** Agent worktree isolation across dozens of parallel jobs consumes significant disk space and I/O when cloning full repositories. By leveraging the AST knowledge graph's dependency closures, we can automatically derive the minimal sparse cone directories (`scoped_paths`) required for each task.

---

## 2. Architecture & Subsystems

```
┌────────────────────────────────────────────────────────────────────────┐
│                        1. Vizor UI Refresh Action                      │
│  • Topbar "🔄 Refresh Graph" action button on tube.html & logical.html │
│  • Visual spinner + POST /w/<slug>/api/graph/refresh + iframe reload   │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                    2. Automated Lifecycle Triggers                     │
│  • synlynk watch: Background re-extraction on git HEAD SHA drift       │
│  • synlynk dispatch: Pre-dispatch JIT cache validator                  │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   3. Rich AST Context Packager (pack.py)               │
│  • Subsystem / Canonical Community clustering                          │
│  • Inlined function signatures & docstrings (Turn-1 zero read)         │
│  • Reverse caller test suite discovery ("Suggested Test Targets")      │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│             4. AST-Assisted Sparse Worktrees (worktree_sparse.py)      │
│  • derive_sparse_cone_paths_from_graph(repo_root, task, story_id)      │
│  • Sub-second isolated sparse checkouts containing only closure files   │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Detailed Component Specifications

### 3.1 Subsystem 1: UI Manual Refresh Button (`synlynk/viz.py`)
- **Location:** In the `.am-kg-topbar` floating toolbar in `tube.html` and `logical.html`.
- **Elements:**
  - `<button id="am-kg-refresh-btn" class="am-btn am-btn-subtle" title="Re-extract AST and rebuild knowledge graph">🔄 Refresh Graph</button>`
- **Interaction Behavior:**
  - On click, button is disabled, spinner animation is applied (`.am-btn.loading`), text changes to `Refreshing...`.
  - Sends `POST /w/<slug>/api/graph/refresh`.
  - On 200 OK, reloads the embedded iframe, updates `#am-kg-status-chip` with `✓ Graph refreshed`, displays toast, and restores button state.
  - On error, displays error toast and restores button state.

### 3.2 Subsystem 2: Automated Lifecycle Triggers (`synlynk/watch.py` & `synlynk/dispatch.py`)
- **`synlynk/watch.py`:**
  - In `watch_loop()` / `_check_workspace_state()`, compare current git `HEAD` SHA with `.synlynk/graphify-out/manifest.json` `head_commit`.
  - If drift is detected (`current_head != head_commit`) and no extraction is actively running, trigger a non-blocking background daemon thread `_trigger_background_graph_refresh(repo_root)` with a 30-second debounce cooldown.
- **`synlynk/dispatch.py`:**
  - In `_format_prompt_for_agent()`, verify `.synlynk/graphify-out/graph.json` exists and is readable. If missing, trigger a lightweight JIT extraction before packaging context.

### 3.3 Subsystem 3: Rich AST Context Packager (`synlynk/pack.py`)
- **Function Signature:**
  ```python
  def synthesize_context_pack(
      repo_root: str,
      task_text: str = "",
      story_id: Optional[str] = None,
      token_budget: int = 1500,
  ) -> str
  ```
- **Output Format:**
  ```markdown
  ## Task Context Pack (Generated via AST Knowledge Graph)

  ### Primary Subsystems & Communities
  - **Subsystem:** `synlynk/viz.py · VizorHandler` (Module Cluster)
  - **Subsystem:** `synlynk/worktree_sparse.py` (Core Engine)

  ### Target Symbols & Interfaces
  - `create_sparse_cone_worktree(repo_root, worktree_path, branch, base_ref, scoped_paths=None) -> bool` [synlynk/worktree_sparse.py:L33]
    *Creates an isolated git worktree configured with cone-mode sparse checkout.*
    - Inbound Callers: `dispatch.py:L1420`, `test_worktree_sparse.py:L22`
    - Outbound Callees: `is_sparse_worktree`, `expand_sparse_cone`

  ### Suggested Verification Test Targets
  - `pytest tests/test_worktree_sparse.py`
  - `pytest tests/test_viz_unified_canvas.py`
  ```

### 3.4 Subsystem 4: AST-Guided Sparse Worktrees (`synlynk/worktree_sparse.py`)
- **New API:**
  ```python
  def derive_sparse_cone_paths_from_graph(
      repo_root: str,
      task_text: str = "",
      story_id: Optional[str] = None,
  ) -> List[str]
  ```
- **Behavior:**
  - Queries Graphify AST graph for matched symbols + 1-hop caller and callee files.
  - Extracts the unique directory prefixes (e.g. `synlynk`, `tests`).
  - Merges with `MANDATORY_SPARSE_CONE_DIRS = (".synlynk", "project-docs", "tests", "synlynk")`.
  - Automatically passed as `scoped_paths` to `create_sparse_cone_worktree()`.

---

## 4. Verification & Testing Strategy

1. **Unit Tests:**
   - `tests/test_viz_refresh_button.py`: Verify `#am-kg-refresh-btn` and click handlers in `tube.html` & `logical.html`.
   - `tests/test_pack_rich.py`: Verify subsystem clustering, docstring/signature inlining, test target discovery, and token bounding.
   - `tests/test_worktree_sparse_ast.py`: Verify `derive_sparse_cone_paths_from_graph()` derives correct directory cones from AST graph fixtures.
   - `tests/test_watch_graph_drift.py`: Verify `watch.py` detects commit drift and initiates background refresh.
2. **Regression Suite:**
   - Run full test suite across Python 3.10 and 3.12 (`pytest tests/`).
