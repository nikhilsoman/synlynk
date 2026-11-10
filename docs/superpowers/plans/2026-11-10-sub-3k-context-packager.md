# Graph-Backed Context Packager for Sub-3k Token Agent Dispatch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the Sub-3k Token Context Packager for standard agent dispatches (`story-5ce5a997`), enforce a Zero-Drift Graph Currency Contract across `origin/main`, provide an explicit `--full-context` escape hatch for epics, and register the Non-Code Document Sidecar Graph roadmap horizon under `goal-34c225e1`.

**Architecture:**
- **Zero-Drift Currency Engine**: Drop stale commit threshold from 25 to 0. Automatically trigger JIT incremental AST extraction before dispatch if `built_at_commit != git rev-parse HEAD`. Atomically stamp `manifest.json` and `graph.json`.
- **Graph Slicing & Blast Radius**: Restrict AST graph traversal in `synlynk/impact.py` to 1-hop inbound callers, 1-hop outbound dependencies, and linked test targets.
- **Adaptive AST Compactor**: Strip implementation bodies while preserving full def/class signatures with type hints and single-line docstring summaries.
- **Strict Budget Allocator**: Assemble prompts within partitioned envelopes guaranteeing total prompt size $\le$ 3,000 tokens for all default dispatches.
- **Escape Hatch & CLI**: Provide `--full-context` on `synlynk dispatch` and `--inspect` on `synlynk pack`.
- **Document Sidecar Horizon**: Formalize the non-code document graph under `goal-34c225e1` with deterministic activation triggers.

**Tech Stack:** Python 3.12+, Graphify AST Engine, SQLite 3 (WAL mode), pytest, Synlynk Dispatch Subsystem.

**Spec:** [`docs/superpowers/specs/2026-11-10-sub-3k-context-packager-design.md`](file:///Users/nikhilsoman/dev/synlynk/docs/superpowers/specs/2026-11-10-sub-3k-context-packager-design.md) (Committed on branch `feat/agy/sub-3k-context-packager` at `9f23e227`).

---

## Global Constraints

- Standard task dispatch prompts without `--full-context` MUST NOT exceed 3,000 tokens (`len(prompt) // 4` ceiling).
- No AST function or method signature may be truncated mid-token; signatures must remain valid parseable definitions.
- Graph extraction, compaction, and impact analysis must remain 100% offline with zero external network or LLM dependencies.
- Every commit on `main` must maintain graph synchronization (`built_at_commit == HEAD`).
- Existing dispatch behaviors for legacy agents must remain backwards-compatible.

---

### Task 1: Zero-Drift Graph Currency & Atomic Commit Stamping Substrate

**Files:**
- Modify: `synlynk/dispatch.py:2745-2825`
- Modify: `synlynk/scan.py:240-270`
- Test: `tests/test_graph_currency.py`

**Interfaces:**
- Consumes: `synlynk.discovery._get_head_commit(repo_root)`
- Produces: `_graph_needs_refresh(repo_root, graph_file) -> bool`, atomic stamping in `_run_graphify_extract(repo_root)`

- [x] **Step 1: Write failing test for zero-drift graph currency**
  Create `tests/test_graph_currency.py` asserting:
  1. `_graph_needs_refresh` returns `True` when `built_at_commit != HEAD` (distance $\ge 1$), rejecting the legacy 25-commit delay.
  2. `_run_graphify_extract` updates `built_at_commit` in **both** `.synlynk/graphify-out/manifest.json` and `.synlynk/graphify-out/graph.json`.
  3. Pre-dispatch check automatically executes `_run_graphify_extract` when a commit delta is detected.

- [x] **Step 2: Run test to confirm failure**
  Run `pytest tests/test_graph_currency.py` and verify failure against current 25-commit threshold.

- [x] **Step 3: Implement Zero-Drift threshold and dual stamping**
  1. In `synlynk/dispatch.py`: set `_GRAPH_STALE_COMMIT_THRESHOLD = 0`.
  2. In `synlynk/scan.py`: update `_run_graphify_extract` to atomically stamp `built_at_commit` into `graph.json` alongside `manifest.json`.
  3. In `synlynk/dispatch.py:_format_prompt_for_agent`: ensure JIT refresh runs whenever `built_at_commit != HEAD`.

- [x] **Step 4: Run test and ensure pass**
  Run `pytest tests/test_graph_currency.py -v` and confirm all tests pass.

- [x] **Step 5: Commit changes**
  Committed in `46616e03`: `feat(graph): implement zero-drift graph currency and dual atomic stamping`

---

### Task 2: 1-Hop AST Graph Slicing & Blast Radius Extraction

**Files:**
- Modify: `synlynk/impact.py:25-155`
- Test: `tests/test_impact_slice.py`

**Interfaces:**
- Consumes: `.synlynk/graphify-out/graph.json`
- Produces: `slice_1hop_impact(repo_root: str, target: str, max_callers: int = 5, max_callees: int = 5) -> Dict[str, Any]`

- [x] **Step 1: Write failing test for 1-hop impact slicing**
  Create `tests/test_impact_slice.py` asserting:
  1. `slice_1hop_impact` extracts direct inbound callers (1-hop only) and direct outbound dependencies.
  2. Associated unit tests from `tests/` or `test/` are accurately segregated.
  3. Caller and callee lists are strictly bounded by `max_callers` and `max_callees` to prevent unbounded array expansion.

- [x] **Step 2: Run test to confirm failure**
  Run `pytest tests/test_impact_slice.py` and confirm `slice_1hop_impact` does not exist.

- [x] **Step 3: Implement `slice_1hop_impact` in `synlynk/impact.py`**
  Implement:
  - Exact seed node matching with fallback loose label matching.
  - 1-hop BFS traversal for inbound callers (depth=1).
  - 1-hop BFS traversal for outbound dependencies (depth=1).
  - Test node extraction filter (`_is_test_node`).

- [x] **Step 4: Run test and ensure pass**
  Run `pytest tests/test_impact_slice.py -v` and verify clean execution.

- [x] **Step 5: Commit changes**
  Committed in `819931ec`: `feat(impact): add bounded 1-hop AST graph slicing and test target extraction`

---

### Task 3: Adaptive AST Compactor & Strict Budget Allocator

**Files:**
- Modify: `synlynk/pack.py:30-290`
- Modify: `synlynk/cli.py:2880-2920`
- Test: `tests/test_pack_sub3k.py`

**Interfaces:**
- Consumes: `synlynk.impact.slice_1hop_impact`, `synlynk.pack._get_ast_signature`
- Produces: `synthesize_sub3k_context_pack(repo_root, task_text, story_id, max_tokens=3000) -> str`
- CLI: `synlynk pack --budget 3000 --inspect <story-id>`

- [x] **Step 1: Write failing test for sub-3k pack synthesis and budgeting**
  Create `tests/test_pack_sub3k.py` asserting:
  1. `synthesize_sub3k_context_pack` returns a compacted payload with partitioned sections (Subsystems, Interfaces, Blast Radius, Tests).
  2. Docstrings are truncated to single-line summaries $\le 120$ characters.
  3. Method bodies are omitted while retaining complete signatures and type hints.
  4. Prompt token count is strictly $\le 3,000$ tokens across multi-symbol queries.
  5. `cmd_pack` with `--inspect` outputs section token counts.

- [x] **Step 2: Run test to confirm failure**
  Run `pytest tests/test_pack_sub3k.py` and verify failure.

- [x] **Step 3: Implement `synthesize_sub3k_context_pack` in `synlynk/pack.py`**
  Implement:
  - Adaptive signature extraction formatting (`_compact_ast_signature`).
  - Budget allocator with partitioned limits:
    - AST signatures & Interfaces: 1,200 tokens.
    - Blast radius & Callers: 400 tokens.
    - Test verification targets: 400 tokens.
  - `--inspect` flag parsing and reporting in `synlynk/cli.py:cmd_pack`.

- [x] **Step 4: Run test and ensure pass**
  Run `pytest tests/test_pack_sub3k.py -v` and confirm all test assertions pass.

- [x] **Step 5: Commit changes**
  Committed in `008826f7`: `feat(pack): implement sub-3k adaptive AST packager and inspection CLI`

---

### Task 4: Dispatch Pipeline Integration & `--full-context` Flag

**Files:**
- Modify: `synlynk/dispatch.py:2970-3070`
- Modify: `synlynk/cli.py:1200-1300`
- Test: `tests/test_dispatch_sub3k_gate.py`

**Interfaces:**
- Consumes: `synlynk.pack.synthesize_sub3k_context_pack`
- Produces: `_format_prompt_for_agent(..., full_context=False)`, `synlynk dispatch --full-context`

- [x] **Step 1: Write failing test for dispatch gate and `--full-context` flag**
  Create `tests/test_dispatch_sub3k_gate.py` asserting:
  1. Standard dispatch prompt is compiled using sub-3k budgeting by default.
  2. Passing `full_context=True` bypasses the 3,000 token limit.
  3. `CONTEXT_BUDGET_EXCEEDED` sentinel alert is recorded if an uncompressed standard prompt exceeds 3,000 tokens.
  4. CLI argument parser accepts `--full-context` and propagates to dispatch.

- [x] **Step 2: Run test to confirm failure**
  Run `pytest tests/test_dispatch_sub3k_gate.py` and verify failure.

- [x] **Step 3: Implement sub-3k default and `--full-context` in `synlynk/dispatch.py`**
  1. Wire `--full-context` into `dispatch` parser in `synlynk/cli.py`.
  2. Update `_format_prompt_for_agent` to default to sub-3k budgeting.
  3. If `not full_context and token_estimate > 3000`: trigger compression and log `_warn_context_budget_exceeded`.

- [x] **Step 4: Run test and ensure pass**
  Run `pytest tests/test_dispatch_sub3k_gate.py -v` and confirm all tests pass.

- [x] **Step 5: Commit changes**
  Committed in `c6bc6806`: `feat(dispatch): integrate sub-3k context packager with --full-context bypass gate`

---

### Task 5: Post-Merge & Watch Lifecycle Auto-Sweep

**Files:**
- Modify: `synlynk/watch.py:200-260`
- Modify: `synlynk/pr_check.py:35-50`
- Modify: `synlynk/cli.py:230-245`
- Test: `tests/test_lifecycle_graph_sweep.py`

**Interfaces:**
- Consumes: `synlynk.scan._run_graphify_extract`
- Produces: Background graph sweep on PR check/merge and daemon/watch HEAD revision advance.

- [x] **Step 1: Write test for lifecycle auto-sweep**
  Create `tests/test_lifecycle_graph_sweep.py` asserting:
  1. When daemon/watch detects HEAD advance, background extract is dispatched.
  2. When `synlynk pr check` runs, graph extract sweeps to guarantee current AST.

- [x] **Step 2: Run test and confirm failure**
  Run `pytest tests/test_lifecycle_graph_sweep.py`.

- [x] **Step 3: Wire auto-sweep in `watch.py` and `pr_check.py`**
  Trigger `check_and_refresh_ast_on_drift` and `trigger_post_merge_graph_sweep`.

- [x] **Step 4: Run test and ensure pass**
  Run `pytest tests/test_lifecycle_graph_sweep.py -v`.

- [x] **Step 5: Commit changes**
  Committed in `5042b18c`: `feat(lifecycle): wire post-merge and watch auto-sweep for zero-drift graph currency`

---

### Task 6: Roadmap & Document Sidecar Horizon Registration (`goal-34c225e1`)

**Files:**
- Modify: `project-docs/memory.md`
- Test: Verification query against `state.db`

- [x] **Step 1: Verify `goal-34c225e1` status in `state.db`**
  Confirmed `goal-34c225e1` is active and represents the curated markdown document sidecar (`gh:#4937`, `story-a94646a3`).

- [x] **Step 2: Register roadmap milestone entry for Document Sidecar Graph**
  Documented future horizon linking `goal-34c225e1` to `v0.32.1` / `v0.33.0` with explicit trigger criteria (Role: architect/pm/docs, Domain: specs/plans, dual-graph separation `doc_graph.json`).

- [x] **Step 3: Document architectural memory in `project-docs/memory.md`**
  Recorded the architectural pattern: code graph stays `--code-only` (`graph.json`), documentation sidecar resides at `doc_graph.json`, cross-referenced via markdown links.

- [x] **Step 4: Commit documentation updates**
  `git add project-docs/memory.md docs/superpowers/plans/2026-11-10-sub-3k-context-packager.md && git commit -m "docs(roadmap): record document sidecar graph horizon and architectural memory under goal-34c225e1"`
