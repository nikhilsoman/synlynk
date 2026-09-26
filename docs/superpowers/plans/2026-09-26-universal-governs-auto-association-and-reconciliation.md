# Universal GOVERNS Lifecycle Auto-Association, Stage Progression & Vizor Reconciliation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement 100% deterministic GOVERNS lifecycle auto-association, event-driven 7-stage state machine transitions, artifact reverse-indexing, and `synlynk governs sweep` fleet reconciliation.

**Architecture:** Build modular components: `synlynk/governs_resolver.py` for context-aware goal resolution, `synlynk/governs_fsm.py` for event-driven stage transitions, `synlynk/governs_cli.py` for the reconciliation sweep, and wire lifecycle hooks into `events.py`, `team.py`, `board.py`, and `uxcore.py`.

**Tech Stack:** Python 3.10+, SQLite 3, Git, AST / Markdown Parser, Pytest.

**Spec:** `docs/superpowers/specs/2026-09-26-universal-governs-auto-association-and-reconciliation-design.md`

## Global Constraints
- **Zero-Token Local Operation:** All parsing, AST analysis, goal resolution, and SQLite updates must run 100% locally with zero external API / token costs.
- **Git Worktree-First Policy:** All feature implementation must happen in a dedicated worktree (`feat/agy/universal-governs-auto-association`).
- **Co-Authored Trailer:** All git commits must include: `Co-Authored-By: Agy (Gemini) <noreply@antigravity.dev>`.
- **Backward Compatibility:** All existing `state.db` databases and schemas must migrate idempotently without data loss or downtime.

---

### Task 1: Goal Kinds (`kind='feature' | 'loop'`) and Schema Migration

**Files:**
- Modify: `synlynk/db.py`, `synlynk/__init__.py`, `synlynk/cli.py`
- Test: `tests/test_goals_kinds.py`

**Interfaces:**
- Produces: `goals.kind` column in `state.db` (`'feature'` | `'loop'`), updated `cmd_goal_create(..., kind="feature")`, updated `cmd_goal_list()`.

- [ ] **Step 1: Write failing tests for goal kinds and migrations**
  Create `tests/test_goals_kinds.py` asserting schema migration adds `kind` with default `'feature'`, `cmd_goal_create` supports `--kind loop`, and `cmd_goal_list` displays goal kinds.
- [ ] **Step 2: Run test to confirm failure**
  Run `pytest tests/test_goals_kinds.py` and verify failure.
- [ ] **Step 3: Implement schema migration and CLI updates**
  Update `_get_db()` and `synlynk/db.py` to add `kind TEXT NOT NULL DEFAULT 'feature'` to `goals` if missing. Update `cmd_goal_create` and `cmd_goal_list`.
- [ ] **Step 4: Verify test passes**
  Run `pytest tests/test_goals_kinds.py` to confirm 100% pass.
- [ ] **Step 5: Commit**
  Commit with message `feat(governs): add goal kinds (feature vs loop) and schema migration`.

---

### Task 2: Deterministic Context Auto-Resolver (`GovernsResolver`)

**Files:**
- Create: `synlynk/governs_resolver.py`
- Test: `tests/test_governs_resolver.py`

**Interfaces:**
- Produces: `resolve_parent_goal(file_path=None, story_id=None, issue_number=None, branch=None, text_content=None, explicit_goal=None, conn=None) -> tuple[str, str]`

- [ ] **Step 1: Write failing tests for GovernsResolver**
  Create `tests/test_governs_resolver.py` asserting 5-tier resolution (explicit flag, markdown headers, issue inheritance, keyword/path heuristic, master loop fallback `goal-eacab0dc`).
- [ ] **Step 2: Run test to confirm failure**
  Run `pytest tests/test_governs_resolver.py`.
- [ ] **Step 3: Implement `GovernsResolver`**
  Write `synlynk/governs_resolver.py` with deterministic heuristics and in-band markdown parsing.
- [ ] **Step 4: Verify test passes**
  Run `pytest tests/test_governs_resolver.py`.
- [ ] **Step 5: Commit**
  Commit with message `feat(governs): implement deterministic GovernsResolver`.

---

### Task 3: Event-Driven 7-Stage Lifecycle State Machine (FSM)

**Files:**
- Create: `synlynk/governs_fsm.py`
- Modify: `synlynk/events.py`, `synlynk/db.py`
- Test: `tests/test_governs_fsm.py`

**Interfaces:**
- Produces: `advance_story_governs_stage(story_id_or_ref, event_type, event_payload=None, conn=None) -> str`

- [ ] **Step 1: Write failing tests for stage transitions**
  Create `tests/test_governs_fsm.py` verifying stage transitions (`spec_or_plan_committed` -> `visualize`, `pr_opened` -> `execute`, `pr_merged` -> `release`, `story_done` -> `sustain`).
- [ ] **Step 2: Run test to confirm failure**
  Run `pytest tests/test_governs_fsm.py`.
- [ ] **Step 3: Implement `synlynk/governs_fsm.py` and hook into `events.py`**
  Implement `advance_story_governs_stage` and trigger it in `emit_event()`.
- [ ] **Step 4: Verify test passes**
  Run `pytest tests/test_governs_fsm.py`.
- [ ] **Step 5: Commit**
  Commit with message `feat(governs): implement event-driven 7-stage lifecycle state machine`.

---

### Task 4: In-Session Artifact Registration & `synlynk decide` Goal Binding

**Files:**
- Modify: `synlynk/team.py`, `synlynk/db.py`, `synlynk/context.py`
- Test: `tests/test_artifact_harvesting.py`

**Interfaces:**
- Produces: `decisions.goal_id`, `decisions.story_id` in `state.db`, auto-binding during `synlynk decide --record`, auto-indexing of specs and plans during checkpoint.

- [ ] **Step 1: Write failing tests for decision and spec indexing**
  Create `tests/test_artifact_harvesting.py` asserting `cmd_decision_record` binds `goal_id`, and `checkpoint` registers specs.
- [ ] **Step 2: Run test to confirm failure**
  Run `pytest tests/test_artifact_harvesting.py`.
- [ ] **Step 3: Implement artifact registration and decision binding**
  Update `decisions` schema to add `goal_id` and `story_id`. Wire `GovernsResolver` in `cmd_decision_record` and `context.py`.
- [ ] **Step 4: Verify test passes**
  Run `pytest tests/test_artifact_harvesting.py`.
- [ ] **Step 5: Commit**
  Commit with message `feat(governs): register in-session decisions and specs to state.db`.

---

### Task 5: Fleet Reconciliation Command (`synlynk governs sweep`)

**Files:**
- Create: `synlynk/governs_cli.py`
- Modify: `synlynk/cli.py`
- Test: `tests/test_governs_sweep.py`

**Interfaces:**
- Produces: `cmd_governs_sweep(repo_root=None, dry_run=False, strict=False, verbose=False) -> dict` and CLI command `synlynk governs sweep`.

- [ ] **Step 1: Write failing tests for governs sweep**
  Create `tests/test_governs_sweep.py` testing backfilling unlinked stories, advancing stagnant stages, and harvesting unindexed specs.
- [ ] **Step 2: Run test to confirm failure**
  Run `pytest tests/test_governs_sweep.py`.
- [ ] **Step 3: Implement `synlynk/governs_cli.py` and register in `cli.py`**
  Implement the sweep engine with detailed reporting and batch SQLite updates.
- [ ] **Step 4: Verify test passes**
  Run `pytest tests/test_governs_sweep.py`.
- [ ] **Step 5: Commit**
  Commit with message `feat(governs): implement synlynk governs sweep reconciliation command`.

---

### Task 6: Vizor Board & Dual-Pivot Gantt Integration Verification

**Files:**
- Modify: `synlynk/board.py`, `synlynk/uxcore.py`, `synlynk/viz.py`
- Test: `tests/test_viz_governs_board.py`

**Interfaces:**
- Produces: Balanced 7-column card distribution on `board.html` and 100% mapped story trees in `gantt.html` Goal-First pivot.

- [ ] **Step 1: Write integration tests for Board & Gantt data projection**
  Create `tests/test_viz_governs_board.py` asserting `/api/board` and `get_gantt_data()` return fully connected cards across all 7 GOVERNS columns and mapped goals.
- [ ] **Step 2: Run test to verify behavior**
  Run `pytest tests/test_viz_governs_board.py`.
- [ ] **Step 3: Verify and refine board/gantt projections**
  Ensure cards carry correct deep links and stage metadata.
- [ ] **Step 4: Verify full test suite passes**
  Run `pytest tests/test_goals_kinds.py tests/test_governs_resolver.py tests/test_governs_fsm.py tests/test_artifact_harvesting.py tests/test_governs_sweep.py tests/test_viz_governs_board.py`.
- [ ] **Step 5: Commit**
  Commit with message `feat(governs): verify 100% Vizor Board and Dual-Pivot Gantt integration`.
