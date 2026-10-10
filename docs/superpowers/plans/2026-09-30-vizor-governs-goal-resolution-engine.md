# Living GOVERNS Goal Resolution & Alignment Engine Implementation Plan (Spec 3)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Tasks are executed via `synlynk dispatch` across capability-aligned harnesses (Codex, Agy, Grok, Claude).

**Goal:** Build and verify the Living GOVERNS Engine: workspace-scoped goal tenancy (`goals.product_id`), deterministic auto-association on all 6 story-write paths, an edge-first dual-pivot Gantt projection resolving Defect 2 ("0 tasks" on releases), and real-time SSE governance relay updates across workspaces.

**Architecture:** Anchor all goal resolution to `state_identity.product_id` via a new `synlynk/governs_engine.py` module. Replace hardcoded fleet constants (`_DOMAIN_GOAL_MAP`, `DEFAULT_MASTER_GOAL`) with workspace-authored `goal_aliases` (DB + `.synlynk/config.json`) and keyword extraction. Make `synlynk governs sweep` an audit-only reconciliation tool that never manufactures foreign goals. Wire `associate_story()` into all story creation paths and rebuild `uxcore.get_gantt_data()` with an edge-first attachment hierarchy.

**Tech Stack:** Python 3.10+, SQLite3 (WAL mode), Regex AST, SSE (`text/event-stream`), Vanilla JS/CSS (Vizor Web HUD).

**Spec:** [`docs/superpowers/specs/2026-09-30-vizor-governs-goal-resolution-engine-design.md`](../specs/2026-09-30-vizor-governs-goal-resolution-engine-design.md)

## Global Constraints

- **Invariant 1 (Goal Tenancy):** Every `goals` row belongs to exactly one `product_id`. No code path may create, read, or link foreign goals.
- **Invariant 2 (Continuous Association):** Association happens at story write time. `synlynk governs sweep` is an audit tool, not a creator.
- **Invariant 3 (Projection Completeness):** Stories attach to Gantt via `goal_contributions` edges first. "0 tasks" on a release owning stories is a bug.
- **Invariant 4 (Live Alignment):** Association changes emit `goal_realigned` SSE events filtered by `product_id` at both emit and consume sides.
- **Fail-Closed Resolution:** Unresolved stories land with `link_status='unresolved'`, never defaulting to a hardcoded master goal.
- **Transaction Safety:** Story insertion and goal association execute within the caller's single transaction (PR #1205 guard).
- **Harness Routing:** Dispatch tasks according to Capability-Based Task Allocation: CLI/DB/plumbing to Codex, CSS/templates/Vizor HTML to Agy, JS/streaming to Grok, reviews to QA/Codex.

---

### Task 1: Schema Migration, Tenancy Column, and Alias Storage

**Files:**
- Modify: `synlynk/db_schema.py`
- Modify: `synlynk/db.py`
- Test: `tests/test_governs_engine_tenancy.py`

**Interfaces:**
- Consumes: `state_identity.product_id` from `state_registry.py`
- Produces: `goals.product_id`, `goal_aliases` table, `goal_contributions.resolution_reason`, `goal_contributions.resolved_at`, and migration logic in `synlynk/db.py`

- [ ] **Step 1: Write failing tests for tenancy schema, backfill, and quarantine**

```python
# tests/test_governs_engine_tenancy.py
import sqlite3
import pytest
from synlynk.db import init_db, migrate_db

def test_goals_schema_has_product_id(tmp_path):
    db_file = tmp_path / "state.db"
    init_db(str(db_file))
    conn = sqlite3.connect(str(db_file))
    cols = [r[1] for r in conn.execute("PRAGMA table_info(goals)").fetchall()]
    assert "product_id" in cols
    conn.close()

def test_goal_aliases_table_exists(tmp_path):
    db_file = tmp_path / "state.db"
    init_db(str(db_file))
    conn = sqlite3.connect(str(db_file))
    cols = [r[1] for r in conn.execute("PRAGMA table_info(goal_aliases)").fetchall()]
    assert "goal_id" in cols
    assert "pattern" in cols
    assert "product_id" in cols
    conn.close()

def test_migration_quarantines_phantom_goals(tmp_path):
    db_file = tmp_path / "state.db"
    init_db(str(db_file))
    conn = sqlite3.connect(str(db_file))
    conn.execute(
        "INSERT INTO goals (goal_id, outcome, criterion, status) VALUES (?, ?, ?, ?)",
        ("goal-foreign1", "Foreign", "Auto-reconciled during GOVERNS sweep", "active")
    )
    conn.commit()
    conn.close()
    
    # Run migration
    migrate_db(str(db_file))
    
    conn = sqlite3.connect(str(db_file))
    row = conn.execute("SELECT status FROM goals WHERE goal_id='goal-foreign1'").fetchone()
    assert row[0] == "quarantined"
    conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_governs_engine_tenancy.py -v`
Expected: FAIL with missing columns or table.

- [ ] **Step 3: Implement schema changes and migration**

In `synlynk/db_schema.py`:
- Add `product_id TEXT` to `CREATE TABLE IF NOT EXISTS goals`.
- Add `CREATE TABLE IF NOT EXISTS goal_aliases (id INTEGER PRIMARY KEY AUTOINCREMENT, goal_id TEXT NOT NULL REFERENCES goals(goal_id), pattern TEXT NOT NULL, product_id TEXT NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, UNIQUE(goal_id, pattern));`.
- Add `resolution_reason TEXT` and `resolved_at TIMESTAMP` to `goal_contributions`.
- In `synlynk/db.py`, add migration helper `_migrate_governs_tenancy(conn)` checking `PRAGMA table_info`, backfilling `product_id` from `state_identity`, and quarantining phantom auto-reconciled goals with no contributions.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_governs_engine_tenancy.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add synlynk/db_schema.py synlynk/db.py tests/test_governs_engine_tenancy.py
git commit -m "feat(governs): add product_id tenancy and goal_aliases schema migration (Spec 3)"
```

---

### Task 2: Living GOVERNS Engine Core and Waterfall Resolution

**Files:**
- Create: `synlynk/governs_engine.py`
- Modify: `synlynk/governs_resolver.py`
- Test: `tests/test_governs_engine_tenancy.py`
- Test: `tests/test_governs_auto_association.py`

**Interfaces:**
- Consumes: `goals`, `goal_aliases`, `state_identity`
- Produces: `GoalResolution`, `scoped_goals()`, `resolve_goal_for_story()`, `associate_story()`

- [ ] **Step 1: Write failing tests for pure waterfall without hardcoded fleet IDs**

```python
# tests/test_governs_auto_association.py
import pytest
import sqlite3
from synlynk.db import init_db
from synlynk.governs_engine import scoped_goals, associate_story, GoalResolution

def test_no_hardcoded_goal_ids_in_source():
    import synlynk.governs_resolver as gr
    assert not hasattr(gr, "DEFAULT_MASTER_GOAL")
    assert not hasattr(gr, "DEFAULT_GOAL_MAP")

def test_waterfall_resolves_via_workspace_alias(tmp_path):
    db_file = tmp_path / "state.db"
    init_db(str(db_file))
    conn = sqlite3.connect(str(db_file))
    conn.execute("INSERT OR REPLACE INTO state_identity (product_id, canonical_name) VALUES ('prod-rxcc', 'rxcc')")
    conn.execute("INSERT INTO goals (goal_id, outcome, criterion, product_id, status) VALUES ('goal-rxcc1', 'RxCC Engine', 'Criteria', 'prod-rxcc', 'active')")
    conn.execute("INSERT INTO goal_aliases (goal_id, pattern, product_id) VALUES ('goal-rxcc1', 'billing|stripe|invoice', 'prod-rxcc')")
    conn.commit()
    
    res = associate_story(conn, "story-101", title="Fix billing stripe webhook", emit=False)
    assert res.goal_id == "goal-rxcc1"
    assert res.reason == "workspace_alias"
    assert res.confidence == "inferred"
    conn.close()

def test_unresolved_story_lands_with_link_status_unresolved(tmp_path):
    db_file = tmp_path / "state.db"
    init_db(str(db_file))
    conn = sqlite3.connect(str(db_file))
    conn.execute("INSERT OR REPLACE INTO state_identity (product_id, canonical_name) VALUES ('prod-rxcc', 'rxcc')")
    conn.commit()
    
    res = associate_story(conn, "story-unmapped", title="Quantum widget optimizer", emit=False)
    assert res.goal_id is None
    assert res.reason == "unresolved"
    
    # Verify goal_contributions record
    row = conn.execute("SELECT link_status, skip_reason FROM goal_contributions WHERE story_id='story-unmapped'").fetchone()
    assert row is not None
    assert row[0] == "unresolved"
    conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_governs_auto_association.py -v`
Expected: FAIL (module/functions missing, hardcoded constants present).

- [ ] **Step 3: Implement `synlynk/governs_engine.py` and refactor `synlynk/governs_resolver.py`**

- In `synlynk/governs_resolver.py`: Remove `_DOMAIN_GOAL_MAP` and `DEFAULT_MASTER_GOAL`. Keep pure text matching logic accepting dynamic candidate rules/aliases.
- In `synlynk/governs_engine.py`:
  - Implement `workspace_product_id(conn) -> str`
  - Implement `scoped_goals(conn, status='active') -> list[dict]` filtering `product_id = ? OR product_id IS NULL`. Also read declarative aliases from `.synlynk/config.json`.
  - Implement `GoalResolution` dataclass.
  - Implement 7-tier scoped waterfall:
    1. Explicit argument (`explicit_goal`) validated against `scoped_goals` (fail closed with `RuntimeError` if foreign).
    2. In-band header (`**Governing Goal:** ...`).
    3. Parent/issue inheritance.
    4. Workspace aliases (`goal_aliases` + config.json), longest match wins.
    5. Derived keyword match from active goals' outcome/criterion (>= 2 hits).
    6. Workspace default goal (if exactly one active master goal exists).
    7. Unresolved fallback (`goal_id=None`, records `link_status='unresolved'`).
  - Implement `associate_story(conn, story_id, ...)` executing in caller transaction, recording both `goal_contributions` and `stories.goal_id`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_governs_auto_association.py tests/test_governs_engine_tenancy.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add synlynk/governs_engine.py synlynk/governs_resolver.py tests/test_governs_auto_association.py tests/test_governs_engine_tenancy.py
git commit -m "feat(governs): living GOVERNS engine waterfall and scoped candidate resolver (Spec 3)"
```

---

### Task 3: Continuous Write-Time Auto-Association and Audit-Only Sweep

**Files:**
- Modify: `synlynk/backlog.py`
- Modify: `synlynk/db.py`
- Modify: `synlynk/story_provisioning.py`
- Modify: `synlynk/heal_cycles.py`
- Modify: `synlynk/governs_cli.py`
- Test: `tests/test_governs_auto_association.py`
- Test: `tests/test_governs_sweep.py`

**Interfaces:**
- Consumes: `governs_engine.associate_story()`
- Produces: Automatic association on all story write paths; audit-only `synlynk governs sweep` without foreign goal insertions

- [ ] **Step 1: Write failing tests for story creation paths and audit sweep**

```python
# tests/test_governs_auto_association.py
def test_story_create_in_db_associates_automatically(tmp_path):
    db_file = tmp_path / "state.db"
    init_db(str(db_file))
    conn = sqlite3.connect(str(db_file))
    conn.execute("INSERT OR REPLACE INTO state_identity (product_id, canonical_name) VALUES ('prod-test', 'test')")
    conn.execute("INSERT INTO goals (goal_id, outcome, criterion, product_id, status) VALUES ('goal-alpha', 'User Authentication Flow', 'Login', 'prod-test', 'active')")
    conn.commit()
    conn.close()

    from synlynk.db import cmd_story_create
    story_id = cmd_story_create("Add user login and authentication", db_path=str(db_file))
    
    conn = sqlite3.connect(str(db_file))
    row = conn.execute("SELECT goal_id FROM stories WHERE id=?", (story_id,)).fetchone()
    assert row[0] == "goal-alpha"
    conn.close()

def test_sweep_does_not_insert_foreign_goals(tmp_path):
    db_file = tmp_path / "state.db"
    init_db(str(db_file))
    conn = sqlite3.connect(str(db_file))
    conn.execute("INSERT OR REPLACE INTO state_identity (product_id, canonical_name) VALUES ('prod-empty', 'empty')")
    conn.execute("INSERT INTO stories (id, title, status) VALUES ('story-ghost', 'Generic Story', 'todo')")
    conn.commit()
    conn.close()
    
    from synlynk.governs_cli import cmd_governs_sweep
    cmd_governs_sweep(db_path=str(db_file), dry_run=False)
    
    conn = sqlite3.connect(str(db_file))
    goal_count = conn.execute("SELECT COUNT(*) FROM goals").fetchone()[0]
    assert goal_count == 0  # Must NEVER manufacture fake goals
    conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_governs_auto_association.py -k "test_story_create_in_db_associates_automatically or test_sweep_does_not_insert_foreign_goals" -v`
Expected: FAIL

- [ ] **Step 3: Wire association into story write paths and rewrite sweep**

- In `synlynk/backlog.py:653` and `842`: call `governs_engine.associate_story()` if `goal_id` not supplied.
- In `synlynk/db.py:2832` (`story_insert`) and `2879` (`cmd_story_create`): call `associate_story()`.
- In `synlynk/story_provisioning.py:155`: call `associate_story()`.
- In `synlynk/heal_cycles.py:106`: call `associate_story()`.
- In `synlynk/governs_cli.py`:
  - Delete `INSERT OR IGNORE INTO goals` completely.
  - Implement audit & report logic. When stories are unmapped, mark them `unresolved` in `goal_contributions`.
  - In `--strict` mode, report coverage and unresolved count (report-only, exit 0).

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_governs_auto_association.py tests/test_governs_sweep.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add synlynk/backlog.py synlynk/db.py synlynk/story_provisioning.py synlynk/heal_cycles.py synlynk/governs_cli.py tests/test_governs_auto_association.py tests/test_governs_sweep.py
git commit -m "feat(governs): wire write-time auto-association and convert sweep to audit-only (Spec 3)"
```

---

### Task 4: Edge-First Dual-Pivot Gantt Projection

**Files:**
- Modify: `synlynk/uxcore.py`
- Test: `tests/test_gantt_dual_pivot.py`

**Interfaces:**
- Consumes: `goals`, `goal_contributions`, `roadmap_arcs`, `roadmap_phases`, `stories`
- Produces: `uxcore.get_gantt_data()` with non-zero task attachments, first-class Goal Pivot, synthetic lanes, and Unmapped lane

- [ ] **Step 1: Write failing tests for Gantt edge attachment and dual-pivot projections**

```python
# tests/test_gantt_dual_pivot.py
import pytest
import sqlite3
from synlynk.db import init_db
from synlynk.uxcore import get_gantt_data

def test_contribution_edge_attaches_tasks(tmp_path):
    db_file = tmp_path / "state.db"
    init_db(str(db_file))
    conn = sqlite3.connect(str(db_file))
    conn.execute("INSERT OR REPLACE INTO state_identity (product_id, canonical_name) VALUES ('prod-p', 'p')")
    conn.execute("INSERT INTO goals (goal_id, outcome, criterion, product_id, status) VALUES ('goal-g1', 'Outcome 1', 'Crit', 'prod-p', 'active')")
    conn.execute("INSERT INTO roadmap_arcs (id, arc_name, notes, status) VALUES ('arc-1', 'Arc 1', 'Governed by goal-g1', 'active')")
    conn.execute("INSERT INTO roadmap_phases (id, arc_id, phase_title, status) VALUES ('phase-1', 'arc-1', 'Execution', 'active')")
    conn.execute("INSERT INTO stories (id, title, status, phase) VALUES ('story-s1', 'Story S1', 'todo', 'build')")
    conn.execute("INSERT INTO goal_contributions (goal_id, story_id, link_status) VALUES ('goal-g1', 'story-s1', 'active')")
    conn.commit()
    conn.close()

    data = get_gantt_data(db_path=str(db_file))
    # Must attach story-s1 to phase-1 via goal_contributions edge (Rule 2)
    assert len(data.get("releases", [])) > 0
    release = data["releases"][0]
    total_tasks = sum(len(phase.get("tasks", [])) for phase in release.get("phases", []))
    assert total_tasks == 1  # Was 0 before Spec 3!
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_gantt_dual_pivot.py -v`
Expected: FAIL (total_tasks == 0 because phase_title != 'build' and single story_id empty).

- [ ] **Step 3: Implement edge-first attachment hierarchy in `synlynk/uxcore.py`**

- In `uxcore.get_gantt_data(db_path=...)`:
  - Pass `db_path` through all queries instead of relying on global `_get_db()`.
  - Read `goal_contributions` table.
  - Implement 3-tier attachment ranking:
    1. Direct `roadmap_phases.story_id`.
    2. `goal_contributions` -> `goals` -> `roadmap_arcs`.
    3. Legacy `stories.phase == phase_title` case-folded.
  - Ensure exactly-once placement per story.
  - Build Goal Pivot directly:
    - Scoped active goals.
    - Attached stories.
    - Synthetic "Unscheduled" lane for goals with stories but no arc.
    - "Unmapped" lane for stories with `link_status='unresolved'`.
  - Remove `goal_outcome` string equality matching.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_gantt_dual_pivot.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add synlynk/uxcore.py tests/test_gantt_dual_pivot.py
git commit -m "feat(vizor): edge-first Gantt attachment and first-class goal pivot (Spec 3)"
```

---

### Task 5: Scoped Goals Read & `/w/<slug>/api/goals` Route in Vizor

**Files:**
- Modify: `synlynk/viz.py`
- Modify: `synlynk/templates/vizor/gantt.html`
- Modify: `synlynk/templates/vizor/board.html`
- Test: `tests/test_vizor_goal_scoping.py`

**Interfaces:**
- Consumes: `WorkspaceContext.db_path`, `governs_engine.scoped_goals()`
- Produces: Scoped goal delivery to Vizor frontend; zero leakage across workspace endpoints

- [ ] **Step 1: Write failing tests for scoped goals read and `/w/<slug>/api/goals`**

```python
# tests/test_vizor_goal_scoping.py
import pytest
import sqlite3
from synlynk.db import init_db
from synlynk.viz import collect_data

def test_goals_read_through_scoped_db_path(tmp_path):
    db_a = tmp_path / "a.db"
    db_b = tmp_path / "b.db"
    init_db(str(db_a))
    init_db(str(db_b))
    
    conn_a = sqlite3.connect(str(db_a))
    conn_a.execute("INSERT OR REPLACE INTO state_identity (product_id, canonical_name) VALUES ('prod-a', 'a')")
    conn_a.execute("INSERT INTO goals (goal_id, outcome, criterion, product_id, status) VALUES ('goal-a', 'Goal A', 'Crit', 'prod-a', 'active')")
    conn_a.commit()
    conn_a.close()

    conn_b = sqlite3.connect(str(db_b))
    conn_b.execute("INSERT OR REPLACE INTO state_identity (product_id, canonical_name) VALUES ('prod-b', 'b')")
    conn_b.execute("INSERT INTO goals (goal_id, outcome, criterion, product_id, status) VALUES ('goal-b', 'Goal B', 'Crit', 'prod-b', 'active')")
    conn_b.commit()
    conn_b.close()

    data_b = collect_data(db_path=str(db_b))
    goal_ids_b = [g["goal_id"] for g in data_b.get("goals", [])]
    assert "goal-b" in goal_ids_b
    assert "goal-a" not in goal_ids_b
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_vizor_goal_scoping.py -v`
Expected: FAIL (unscoped `_get_db()` reads host DB or fails when daemon CWD is `/`).

- [ ] **Step 3: Implement scoped goals read and route handler in `synlynk/viz.py`**

- In `synlynk/viz.py`:
  - Replace unscoped `conn = _get_db()` in goal collection with `with _open_state_db(db_path=db_path, read_only=True) as gconn: data["goals"] = governs_engine.scoped_goals(gconn, status="active")`.
  - Add `/w/<slug>/api/goals` endpoint resolving via `WorkspaceContext`.
  - In `gantt.html` and `board.html`: render synthetic lanes for unscheduled goals and Unmapped chip for unresolved stories.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_vizor_goal_scoping.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add synlynk/viz.py synlynk/templates/vizor/gantt.html synlynk/templates/vizor/board.html tests/test_vizor_goal_scoping.py
git commit -m "fix(vizor): scope goals query to workspace db_path and add /w/<slug>/api/goals (Spec 3)"
```

---

### Task 6: Governance Relay Events & Multi-Workspace Integration Matrix

**Files:**
- Modify: `synlynk/events.py`
- Modify: `synlynk/governs_engine.py`
- Modify: `synlynk/templates/vizor/gantt.html`
- Create: `tests/test_governs_relay_events.py`
- Create: `tests/test_governs_multi_workspace.py`

**Interfaces:**
- Consumes: `relay.py` SSE event bus
- Produces: `goal_realigned` and `governs_stage_advanced` events with workspace tenancy filtering

- [ ] **Step 1: Write failing tests for governance relay events and multi-workspace matrix**

```python
# tests/test_governs_relay_events.py
from synlynk.events import EventEnvelope, RELAY_EVENT_TYPES

def test_governance_event_types_registered():
    assert "goal_realigned" in RELAY_EVENT_TYPES
    assert "governs_stage_advanced" in RELAY_EVENT_TYPES

def test_goal_realigned_envelope_construction():
    env = EventEnvelope(
        event_type="goal_realigned",
        payload={
            "story_id": "story-1",
            "product_id": "prod-1",
            "to_goal": "goal-1",
            "reason": "workspace_alias"
        }
    )
    assert env.event_type == "goal_realigned"
    assert env.payload["to_goal"] == "goal-1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_governs_relay_events.py -v`
Expected: FAIL (event types missing from `RELAY_EVENT_TYPES`).

- [ ] **Step 3: Implement event types, emit points, and consume-side tenancy filter**

- In `synlynk/events.py`: add `goal_realigned` and `governs_stage_advanced` to `RELAY_EVENT_TYPES`.
- In `synlynk/governs_engine.py`: emit `goal_realigned` on new or altered story-goal linkage (with `emit=False` batching bypass for bulk reconcile).
- In `synlynk/templates/vizor/gantt.html`: in SSE `onmessage` handler, verify `event.product_id === currentWorkspaceProductId` before applying DOM patch.
- In `tests/test_governs_multi_workspace.py`: implement the 8-row multi-workspace matrix from Spec 3 (M1–M8) verifying Synlynk vs `rxcc` isolation.

- [ ] **Step 4: Run full test matrix and regression suites**

Run: `pytest tests/test_governs_engine_tenancy.py tests/test_governs_auto_association.py tests/test_gantt_dual_pivot.py tests/test_vizor_goal_scoping.py tests/test_governs_relay_events.py tests/test_governs_multi_workspace.py -v`
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add synlynk/events.py synlynk/governs_engine.py synlynk/templates/vizor/gantt.html tests/test_governs_relay_events.py tests/test_governs_multi_workspace.py
git commit -m "feat(relay): emit goal_realigned SSE events and verify multi-workspace isolation (Spec 3)"
```

---

### Task 7: Full Regression Verification, Documentation, and Review Dispatch

**Files:**
- Modify: `project-docs/costs.md`
- Modify: `project-docs/memory.md`
- Modify: `project-docs/todo.md`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Run complete repository test suite**

Run: `pytest tests/test_viz*.py tests/test_governs*.py -q`
Expected: All tests pass.

- [ ] **Step 2: Verify live multi-workspace sweep report**

Run: `synlynk governs sweep --strict --dry-run`
Expected: Clean report, zero mutations.

- [ ] **Step 3: Update documentation and ledger**

Update `memory.md`, `todo.md`, and `CHANGELOG.md` reflecting Spec 3 resolution.

- [ ] **Step 4: Commit**

```bash
git add project-docs/memory.md project-docs/todo.md CHANGELOG.md
git commit -m "docs(vizor): record Spec 3 Living GOVERNS Engine architecture and memory decisions"
```

- [ ] **Step 5: Push branch and create Pull Request**

Run: `gh pr create --fill`

- [ ] **Step 6: Dispatch QA Review and Merge**

Dispatch Codex under role `qa` via:
`synlynk dispatch codex --requires-gh-write --role qa --task-type review`
Verify non-author approval and merge into `main`.
