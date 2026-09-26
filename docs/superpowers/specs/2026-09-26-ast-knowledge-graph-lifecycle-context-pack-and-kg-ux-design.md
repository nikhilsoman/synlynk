# Design Spec: AST Knowledge Graph Lifecycle Automation, Rich Context Packaging, Minimal Cone Worktrees & Deep Interactive UX

**Date:** 2026-09-26  
**Status:** Approved  
**Governing Goal:** `goal-e3840370` (*Consolidated Vizor Master Control Plane: Unified Interactive Web HUD, GOVERNS Lifecycle Board, Architectural Views, Onboarding Journey, and Hosted Fleet Radar*)  
**Associated Stories:** `story-3cddd9d2` (Issue #1787), `story-503a76f2` (Issue #1790), `story-0f7043d7` (Issue #1712)  
**Authors:** @nikhilsoman, @agy  

---

## 1. Executive Summary & Goals

This specification unifies the lifecycle, packaging, execution, and presentation layers of the Synlynk AST Knowledge Graph into a high-performance system:
1. **Zero-Token Offline AST Lifecycle:** Automates AST extraction hooks on `git HEAD` drift inside `synlynk watch` and provides an authenticated 1-click `/api/graph/refresh` endpoint with automatic Vizor cache invalidation.
2. **High-Density Task Context Packaging (`synlynk pack`):** Extracts targeted function/class signatures, docstrings, caller/callee chords, and reverse test mappings (`tests/test_*.py` importing the target symbols) bounded within a 1,500-token budget for subagent dispatches.
3. **AST-Guided Shallow/Sparse Worktrees (`synlynk/worktree_sparse.py`):** Automatically computes the minimal directory and file cone required for an agent task based on AST dependency radius, reducing worktree checkout time and disk footprint by over 70%.
4. **Sub-20ms Jev System 1 Feature Vector:** Emits deterministic topological metrics (`impact_score`, `blast_radius`, `community_span`, `component_kind`) providing zero-token grounding for fast routing and merge policy evaluations.
5. **Deep Vizor KG Interactive UX:**
   - **Inspect-Mode Ego Network:** Single-click isolates a symbol's 1-hop dependency cluster with multi-click progressive neighborhood growth.
   - **`/api/source` Code Inspection Drawer:** Sliding syntax-highlighted code drawer anchored to exact line ranges (`#L10-L45`) without leaving the canvas.
   - **Kind-Based Level 0 Filtering & Cluster Physics:** Overview filters for `Service Class`, `Module Cluster`, `Test Suite`, and density-responsive spring forces.
   - **Ergonomic Exit:** Keyboard `ESC` and empty-canvas click smoothly exit inspection mode back to global overview.

---

## 2. Architecture Diagram

```mermaid
flowchart TD
    subgraph Storage ["Workspace State & Artifacts (.synlynk/)"]
        M[(state.db)]
        G[(graphify-out/graph.json)]
        MAN[manifest.json]
    end

    subgraph Lifecycle ["Lifecycle & Extraction Engine"]
        W[synlynk watch] -->|Detect HEAD drift| EX[Graphify Extractor]
        VR[POST /api/graph/refresh] -->|UI Trigger| EX
        EX -->|Write AST & Commit SHA| G
        EX -->|Update HEAD Stamp| MAN
    end

    subgraph Consumers ["AST Graph Consumers"]
        G --> PK[synlynk pack Engine]
        G --> SW[synlynk worktree_sparse]
        G --> JEV[Jev System 1 Feature Vector]
    end

    subgraph Vizor ["Vizor Interactive UX (tube.html / logical.html)"]
        G --> VZ[Unified Graph Canvas]
        VZ --> EGO[Inspect Ego Network & Multi-Click Grow]
        VZ --> SRC[/api/source Sliding Code Drawer]
        VZ --> FLT[Kind-Based L0 Filter Toolbar]
        VZ --> LOD[LOD Zoom Bar & Mousewheel LOD]
    end
```

---

## 3. Subsystem A: AST Extraction Lifecycle & Background Daemon Watchers

### 3.1 Background Watch Drift Detection (`synlynk/watch.py`)
- `synlynk watch` maintains the last extracted `built_at` commit hash.
- On every poll cycle (~10s), if `git rev-parse HEAD` differs from `manifest.json.built_at` and repo files have changed:
  - Invokes `_run_graphify_extract(repo_root, code_only=True)` in a background non-blocking thread or subprocess.
  - Updates `manifest.json` with `built_at = HEAD_SHA`.
  - Triggers Vizor cache invalidation via `synlynk.viz._write_cache()`.

### 3.2 1-Click Refresh Endpoint (`POST /api/graph/refresh`)
- Route handled by `VizorHandler` in `synlynk/viz.py` and `WorkspaceRoutingHandler` in `synlynk/vizor_daemon.py`.
- Authenticated via local session token (`synlynk.local_http_auth`).
- Runs synchronous or asynchronous extraction based on `?async=1`.
- Returns `{ "status": "ok", "nodes": N, "edges": M, "duration_ms": D, "head_commit": "SHA" }`.

---

## 4. Subsystem B: Graph-Backed Context Packager (`synlynk/pack.py`)

### 4.1 Extraction & Reverse Test Discovery
For a given task or story:
1. **Keyword & Symbol Match:** Searches `nodes` in `graph.json` for matching class, function, or module names.
2. **1-Hop Neighborhood:** Gathers incoming (callers) and outgoing (callees) edges.
3. **Signature & Docstring Extraction:** Reads the source file using AST parser to extract the `def/class` definition line, parameters, type annotations, and docstring (omitting internal function body lines to maximize token density).
4. **Reverse Test Mapping:** Inspects `tests/` AST nodes that import or call the matched symbols, including the test file paths and test function names.
5. **Token Bounding:** Formats context into Markdown sections and truncates cleanly at `token_budget` (default: 1,500 tokens).

### 4.2 Output Format Example
```markdown
# Context Pack: AST Knowledge Graph Grounding
**Target Symbols:** `synlynk.viz.VizorHandler`, `synlynk.scan._run_graphify_extract`
**Dominant Communities:** `synlynk/viz.py · VizorHandler` (C0), `synlynk/scan.py` (C2)

## Symbol Signatures & Contracts
- `synlynk.viz.VizorHandler`: class handling HTTP endpoints (`do_GET`, `do_POST`, `_handle_graph_refresh_request`)
  - Callees: `synlynk.scan._run_graphify_extract`, `synlynk.local_http_auth.authorize_local_request`
  - Callers: `synlynk.vizor_daemon.WorkspaceRoutingHandler`

## Associated Verification Tests
- `tests/test_viz_graphify_routes.py`: `test_graph_refresh_post_endpoint`
- `tests/test_scan_graphify_auto.py`: `test_auto_extraction_on_deep_scan`
```

---

## 5. Subsystem C: AST-Guided Shallow/Sparse Worktrees (`synlynk/worktree_sparse.py`)

### 5.1 Minimal Cone Derivation
When creating a task worktree via `synlynk dispatch` or `synlynk worktree create`:
1. Mandatory directories always included: `.synlynk/`, `project-docs/`, `tests/`, and core package root.
2. The AST graph is queried with the task description / story ID to determine:
   - Primary modified files.
   - 1-hop caller/callee file paths.
   - Associated test file paths.
3. The derived directory set is converted to `git sparse-checkout set --cone <dirs>`.
4. If `graph.json` is missing or query yields zero matches, gracefully falls back to full workspace checkout without failing the dispatch.

---

## 6. Subsystem D: Topological Feature Schema for Jev Fast Routing

### 6.1 Feature Vector Output
To support sub-20ms System 1 typed routing without LLM roundtrips:
`synlynk impact --json` and `synlynk pack --features` produce a normalized JSON vector:
```json
{
  "task_id": "story-3cddd9d2",
  "impact_score": 0.42,
  "blast_radius_files": 4,
  "blast_radius_symbols": 18,
  "community_span": 2,
  "is_core_system": true,
  "primary_language": "python",
  "has_test_coverage": true,
  "suggested_harness": "codex",
  "risk_level": "medium"
}
```

---

## 7. Subsystem E: Vizor Deep Interactive UX & Source Inspection

### 7.1 Inspect-Mode Ego Network & Multi-Click Growth
- **Initial Click (Ego Level 1):** Clicking any node dims all unrelated nodes and edges, highlighting the selected node and its direct 1-hop incoming and outgoing connections.
- **Subsequent Click on Neighbor (Ego Level 2):** Clicking an already-connected neighbor expands the visible subnet to include that neighbor's 1-hop connections (progressive cluster growth).
- **Empty-Canvas Click or ESC Key:** Resets the inspect mask, smoothly transitioning back to the full overview graph.

### 7.2 `/api/source` Code Inspection Drawer
- **Backend Route:** `GET /api/source?file=<relative_path>&start=<line>&end=<line>`
  - Path traversal protection: validated to resolve strictly inside `repo_root`.
  - Returns `{ "file": path, "start_line": S, "end_line": E, "content": code_str, "language": "python" }`.
- **UI Sliding Drawer:**
  - Embedded sliding drawer on right side of canvas (`.kg-source-drawer`).
  - Code rendered with syntax highlighting (Prism.js / Highlight.js style or lightweight HTML tokenizer), line numbers, and copy-link button.

### 7.3 Kind-Based Level 0 Filtering & Density Physics
- Level 0 view offers semantic toggle chips in `.am-kg-topbar`:
  - `[x] Services & Classes`
  - `[x] CLI Handlers & Routers`
  - `[x] Module Clusters`
  - `[ ] Test Suites` (default off in L0 to declutter architecture view)
- Density-responsive vis-network physics:
  - Repulsion spring length adjusted dynamically based on visible node count to eliminate overlapping labels.

---

## 8. Verification & Testing Matrix

| Test Suite | Coverage & Scenarios |
|:---|:---|
| `tests/test_pack_rich_context.py` | AST signature extraction, reverse test lookup, caller/callee chords, 1,500-token bound |
| `tests/test_worktree_sparse_ast.py` | Minimal cone derivation from blast radius, fallback on missing graph, git sparse-checkout integration |
| `tests/test_viz_source_api.py` | `GET /api/source` endpoint, path traversal security, line range slicing, error handling |
| `tests/test_viz_kg_interactive.py` | Inspect ego mask, multi-click growth events, postMessage listeners, ESC exit handler |
| `tests/test_watch_graph_drift.py` | HEAD drift detection in `synlynk watch`, background re-extraction trigger, manifest timestamp update |

---

## 9. Sign-off & Implementation Readiness

- Spec approved and aligned with architecture guidelines.
- Proceeding to write implementation plan in `docs/superpowers/plans/2026-09-26-ast-knowledge-graph-lifecycle-context-pack-and-kg-ux.md`.
