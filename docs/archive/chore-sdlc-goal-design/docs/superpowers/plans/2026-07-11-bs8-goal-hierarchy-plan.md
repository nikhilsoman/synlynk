# BS-8: Goal Hierarchy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a first-class `Business Goal` layer to synlynk's `state.db`, sitting above `roadmap_arcs`/`stories`, with a `synlynk goal` CLI and context-injection so active Goals surface in every dispatch.

**Architecture:** Two new tables (`goals`, `goal_contributions`), a nullable `goal_id` FK added to `stories` and `roadmap_arcs` via the existing idempotent `_migrate_db()` ALTER-TABLE pattern, four new `cmd_goal_*` functions in `synlynk/db.py` following the existing `cmd_story_create`/`cmd_story_list` pattern, a `goal` subparser in `synlynk/cli.py`, and one new section injected at the top of `_generate_context_from_db()`.

**Tech Stack:** Python 3 stdlib, sqlite3, pytest. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-07-11-business-goal-sdlc-model-design.md`, Part 1.

---

## Task 1: Schema — `goals` and `goal_contributions` tables

**Files:**
- Modify: `synlynk/__init__.py:669` (end of `_DB_SCHEMA`, before the closing `"""`)
- Test: `tests/test_goals.py` (new)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_goals.py
import sqlite3
from synlynk import _get_db


def test_goals_table_created():
    conn = _get_db()
    cols = {row[1] for row in conn.execute("PRAGMA table_info(goals)")}
    assert cols == {"id", "goal_id", "outcome", "criterion", "deadline", "status", "created_at"}
    conn.close()


def test_goal_contributions_table_created():
    conn = _get_db()
    cols = {row[1] for row in conn.execute("PRAGMA table_info(goal_contributions)")}
    assert cols == {"id", "goal_id", "story_id"}
    conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_goals.py -v`
Expected: FAIL — `sqlite3.OperationalError: no such table: goals`

- [ ] **Step 3: Add the tables to `_DB_SCHEMA`**

In `synlynk/__init__.py`, immediately before the closing `"""` of `_DB_SCHEMA` (currently line 669, right after the `daemon_jobs` index):

```python
CREATE TABLE IF NOT EXISTS goals (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    goal_id     TEXT NOT NULL UNIQUE,
    outcome     TEXT NOT NULL,
    criterion   TEXT NOT NULL,
    deadline    TEXT,
    status      TEXT NOT NULL DEFAULT 'active',
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS goal_contributions (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    goal_id  TEXT NOT NULL REFERENCES goals(goal_id),
    story_id TEXT NOT NULL REFERENCES stories(story_id),
    UNIQUE(goal_id, story_id)
);
"""
```

(Keep the existing trailing `"""` — just insert the two `CREATE TABLE` blocks above it.)

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_goals.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add synlynk/__init__.py tests/test_goals.py
git commit -m "feat(db): add goals and goal_contributions tables"
```

---

## Task 2: Schema — `goal_id` FK on `stories` and `roadmap_arcs`

**Files:**
- Modify: `synlynk/db.py:119-144` (`_migrate_db`, alongside the existing `story_cols` ALTER block)
- Test: `tests/test_goals.py`

- [ ] **Step 1: Write the failing test**

```python
def test_stories_and_arcs_have_goal_id_column():
    conn = _get_db()
    story_cols = {row[1] for row in conn.execute("PRAGMA table_info(stories)")}
    arc_cols = {row[1] for row in conn.execute("PRAGMA table_info(roadmap_arcs)")}
    assert "goal_id" in story_cols
    assert "goal_id" in arc_cols
    conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_goals.py::test_stories_and_arcs_have_goal_id_column -v`
Expected: FAIL — `assert "goal_id" in story_cols`

- [ ] **Step 3: Add the ALTER TABLE migrations**

In `synlynk/db.py`, `_migrate_db()`, immediately after the existing `story_cols` block (which currently ends at line 129 with the `status` column ALTER):

```python
    if "goal_id" not in story_cols:
        conn.execute("ALTER TABLE stories ADD COLUMN goal_id TEXT REFERENCES goals(goal_id)")
    arc_cols = {row[1] for row in conn.execute("PRAGMA table_info(roadmap_arcs)")}
    if "goal_id" not in arc_cols:
        conn.execute("ALTER TABLE roadmap_arcs ADD COLUMN goal_id TEXT REFERENCES goals(goal_id)")
```

Note: `_migrate_db()` runs `conn.executescript(_DB_SCHEMA)` at its top (line 122), so by the time this code runs, the `goals` table from Task 1 already exists — the FK reference is valid at ALTER time.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_goals.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add synlynk/db.py tests/test_goals.py
git commit -m "feat(db): add nullable goal_id FK to stories and roadmap_arcs"
```

---

## Task 3: `cmd_goal_create` and `cmd_goal_list`

**Files:**
- Modify: `synlynk/db.py` (add functions after `cmd_story_list`, currently ending line 876)
- Test: `tests/test_goals.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_goal_create_returns_goal_id_and_persists():
    from synlynk.db import cmd_goal_create
    goal_id = cmd_goal_create(
        outcome="Ship agent role split to v0.10.0",
        criterion="synlynk dispatch routes 100% of implementation work to non-Claude agents",
        deadline="2026-09-01",
    )
    assert goal_id.startswith("goal-")
    conn = _get_db()
    row = conn.execute(
        "SELECT outcome, criterion, deadline, status FROM goals WHERE goal_id=?", (goal_id,)
    ).fetchone()
    conn.close()
    assert row == (
        "Ship agent role split to v0.10.0",
        "synlynk dispatch routes 100% of implementation work to non-Claude agents",
        "2026-09-01",
        "active",
    )


def test_goal_list_prints_active_goals(capsys):
    from synlynk.db import cmd_goal_create, cmd_goal_list
    cmd_goal_create(outcome="Outcome A", criterion="Criterion A")
    cmd_goal_list()
    captured = capsys.readouterr()
    assert "Outcome A" in captured.out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_goals.py -v`
Expected: FAIL — `ImportError: cannot import name 'cmd_goal_create'`

- [ ] **Step 3: Implement both functions**

In `synlynk/db.py`, directly after `cmd_story_list()` (currently ends line 876):

```python
def cmd_goal_create(outcome: str, criterion: str, deadline: str = None) -> str:
    """Creates a Business Goal record in state.db. Returns the generated goal_id."""
    from synlynk import _GREEN, _RESET, _get_db
    import hashlib as _hashlib
    goal_id = "goal-" + _hashlib.md5(
        f"{outcome}{time.time()}".encode()
    ).hexdigest()[:8]
    conn = _get_db()
    conn.execute(
        "INSERT INTO goals (goal_id, outcome, criterion, deadline) VALUES (?, ?, ?, ?)",
        (goal_id, outcome, criterion, deadline)
    )
    conn.commit()
    conn.close()
    print(f"  {_GREEN}✓{_RESET} Goal created: {goal_id}  [{outcome}]")
    return goal_id

def cmd_goal_list() -> None:
    """Prints all active goals in state.db."""
    from synlynk import _get_db
    conn = _get_db()
    rows = conn.execute(
        "SELECT goal_id, outcome, criterion, deadline, status "
        "FROM goals WHERE status='active' ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    if not rows:
        print("  No active goals. Use: synlynk goal create --outcome '...' --criterion '...'")
        return
    print(f"\n  {'ID':<12} {'Outcome':<40} {'Deadline':<12}")
    print("  " + "-" * 80)
    for r in rows:
        deadline = r[3] or "ongoing"
        print(f"  {r[0]:<12} {(r[1] or '')[:39]:<40} {deadline:<12}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_goals.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add synlynk/db.py tests/test_goals.py
git commit -m "feat(goal): add cmd_goal_create and cmd_goal_list"
```

---

## Task 4: `cmd_goal_link` (primary + secondary)

**Files:**
- Modify: `synlynk/db.py`
- Test: `tests/test_goals.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_goal_link_sets_primary_goal_id_on_story():
    from synlynk.db import cmd_goal_create, cmd_story_create, cmd_goal_link
    goal_id = cmd_goal_create(outcome="O", criterion="C")
    story_id = cmd_story_create(title="Do the thing")
    cmd_goal_link(story_id, goal_id)
    conn = _get_db()
    row = conn.execute("SELECT goal_id FROM stories WHERE story_id=?", (story_id,)).fetchone()
    conn.close()
    assert row[0] == goal_id


def test_goal_link_secondary_writes_contribution_not_primary():
    from synlynk.db import cmd_goal_create, cmd_story_create, cmd_goal_link
    goal_a = cmd_goal_create(outcome="A", criterion="C")
    goal_b = cmd_goal_create(outcome="B", criterion="C")
    story_id = cmd_story_create(title="Cross-cutting work")
    cmd_goal_link(story_id, goal_a)
    cmd_goal_link(story_id, goal_b, secondary=True)
    conn = _get_db()
    primary = conn.execute("SELECT goal_id FROM stories WHERE story_id=?", (story_id,)).fetchone()[0]
    contributions = conn.execute(
        "SELECT goal_id FROM goal_contributions WHERE story_id=?", (story_id,)
    ).fetchall()
    conn.close()
    assert primary == goal_a
    assert contributions == [(goal_b,)]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_goals.py -v`
Expected: FAIL — `ImportError: cannot import name 'cmd_goal_link'`

- [ ] **Step 3: Implement `cmd_goal_link`**

In `synlynk/db.py`, directly after `cmd_goal_list()`:

```python
def cmd_goal_link(story_id: str, goal_id: str, secondary: bool = False) -> None:
    """Links a story to a goal. Primary (default) sets stories.goal_id;
    secondary inserts a goal_contributions row for cross-cutting traceability."""
    from synlynk import _GREEN, _RESET, _get_db
    conn = _get_db()
    story = conn.execute("SELECT story_id FROM stories WHERE story_id=?", (story_id,)).fetchone()
    goal = conn.execute("SELECT goal_id FROM goals WHERE goal_id=?", (goal_id,)).fetchone()
    if not story:
        conn.close()
        print(f"  Story '{story_id}' not found.")
        return
    if not goal:
        conn.close()
        print(f"  Goal '{goal_id}' not found.")
        return
    if secondary:
        conn.execute(
            "INSERT OR IGNORE INTO goal_contributions (goal_id, story_id) VALUES (?, ?)",
            (goal_id, story_id)
        )
        print(f"  {_GREEN}✓{_RESET} {story_id} linked to {goal_id} (secondary)")
    else:
        conn.execute("UPDATE stories SET goal_id=? WHERE story_id=?", (goal_id, story_id))
        print(f"  {_GREEN}✓{_RESET} {story_id} linked to {goal_id} (primary)")
    conn.commit()
    conn.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_goals.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add synlynk/db.py tests/test_goals.py
git commit -m "feat(goal): add cmd_goal_link for primary and secondary contributions"
```

---

## Task 5: `cmd_goal_status` rollup

**Files:**
- Modify: `synlynk/db.py`
- Test: `tests/test_goals.py`

- [ ] **Step 1: Write the failing test**

```python
def test_goal_status_reports_story_counts(capsys):
    from synlynk.db import cmd_goal_create, cmd_story_create, cmd_goal_link, cmd_goal_status
    from synlynk import _get_db
    goal_id = cmd_goal_create(outcome="Ship it", criterion="All stories done")
    s1 = cmd_story_create(title="Story one")
    s2 = cmd_story_create(title="Story two")
    cmd_goal_link(s1, goal_id)
    cmd_goal_link(s2, goal_id)
    conn = _get_db()
    conn.execute("UPDATE stories SET status='done' WHERE story_id=?", (s1,))
    conn.commit()
    conn.close()
    cmd_goal_status()
    captured = capsys.readouterr()
    assert "Ship it" in captured.out
    assert "1/2" in captured.out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_goals.py::test_goal_status_reports_story_counts -v`
Expected: FAIL — `ImportError: cannot import name 'cmd_goal_status'`

- [ ] **Step 3: Implement `cmd_goal_status`**

In `synlynk/db.py`, directly after `cmd_goal_link()`:

```python
def cmd_goal_status() -> None:
    """Prints a rollup of each active goal: story completion, linked arcs, deadline."""
    from synlynk import _get_db
    conn = _get_db()
    goals = conn.execute(
        "SELECT goal_id, outcome, deadline FROM goals WHERE status='active' ORDER BY created_at DESC"
    ).fetchall()
    if not goals:
        conn.close()
        print("  No active goals.")
        return
    print()
    for goal_id, outcome, deadline in goals:
        total = conn.execute(
            "SELECT COUNT(*) FROM stories WHERE goal_id=?", (goal_id,)
        ).fetchone()[0]
        done = conn.execute(
            "SELECT COUNT(*) FROM stories WHERE goal_id=? AND status='done'", (goal_id,)
        ).fetchone()[0]
        arcs = conn.execute(
            "SELECT version FROM roadmap_arcs WHERE goal_id=?", (goal_id,)
        ).fetchall()
        deadline_s = deadline or "ongoing"
        arc_s = ", ".join(a[0] for a in arcs) if arcs else "—"
        print(f"  {goal_id}  {outcome}")
        print(f"    Stories: {done}/{total} done   Deadline: {deadline_s}   Arcs: {arc_s}\n")
    conn.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_goals.py -v`
Expected: PASS (8 tests)

- [ ] **Step 5: Commit**

```bash
git add synlynk/db.py tests/test_goals.py
git commit -m "feat(goal): add cmd_goal_status rollup"
```

---

## Task 6: `synlynk goal` CLI subcommand

**Files:**
- Modify: `synlynk/cli.py` (parser: insert after the `decide_parser` block, currently lines 232-243; dispatch: insert after the `elif args.command == "decide":` block, currently lines 719-721)
- Test: `tests/test_goals.py`

- [ ] **Step 1: Write the failing test**

```python
def test_cli_goal_create_and_list(capsys, monkeypatch):
    import sys
    from synlynk.cli import main
    monkeypatch.setattr(
        sys, "argv",
        ["synlynk", "goal", "create", "--outcome", "Ship BS-8", "--criterion", "goals table exists"]
    )
    main()
    captured = capsys.readouterr()
    assert "Goal created: goal-" in captured.out

    monkeypatch.setattr(sys, "argv", ["synlynk", "goal", "list"])
    main()
    captured = capsys.readouterr()
    assert "Ship BS-8" in captured.out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_goals.py::test_cli_goal_create_and_list -v`
Expected: FAIL — `error: argument command: invalid choice: 'goal'`

- [ ] **Step 3: Add the `goal_parser` block**

In `synlynk/cli.py`, immediately after the `decide_parser` block (currently ends line 243, right before `scan_parser = subparsers.add_parser(...)` at line 245):

```python
    goal_parser = subparsers.add_parser("goal", help="Manage Business Goals")
    goal_sub = goal_parser.add_subparsers(dest="goal_action")
    goal_create_parser = goal_sub.add_parser("create", help="Create a Business Goal")
    goal_create_parser.add_argument("--outcome", required=True)
    goal_create_parser.add_argument("--criterion", required=True)
    goal_create_parser.add_argument("--deadline", default=None)
    goal_sub.add_parser("list", help="List active goals")
    goal_link_parser = goal_sub.add_parser("link", help="Link a story to a goal")
    goal_link_parser.add_argument("story_id")
    goal_link_parser.add_argument("--goal", required=True, dest="goal_id")
    goal_link_parser.add_argument("--secondary", action="store_true")
    goal_sub.add_parser("status", help="Show goal completion rollup")
```

- [ ] **Step 4: Add the dispatch block**

In `synlynk/cli.py`, immediately after the `elif args.command == "decide":` block (currently ends line 721, right before `elif args.command == "scan":` at line 722):

```python
    elif args.command == "goal":
        from synlynk.db import cmd_goal_create, cmd_goal_list, cmd_goal_link, cmd_goal_status
        action = getattr(args, "goal_action", None)
        if action == "create":
            cmd_goal_create(args.outcome, args.criterion, deadline=args.deadline)
        elif action == "list":
            cmd_goal_list()
        elif action == "link":
            cmd_goal_link(args.story_id, args.goal_id, secondary=args.secondary)
        elif action == "status" or action is None:
            cmd_goal_status()
        else:
            goal_parser.print_help()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_goals.py -v`
Expected: PASS (9 tests)

- [ ] **Step 6: Commit**

```bash
git add synlynk/cli.py tests/test_goals.py
git commit -m "feat(cli): add synlynk goal create/list/link/status"
```

---

## Task 7: Context injection — active Goal surfaces in every dispatch

**Files:**
- Modify: `synlynk/__init__.py:7435-7478` (`_generate_context_from_db`, the active/shadowing definition — see note below)
- Test: `tests/test_goals.py`

**Note:** `_generate_context_from_db` is defined twice in `synlynk/__init__.py` (lines 7355 and 7435). Python keeps only the second definition; the first is dead code. Edit the **second** definition (line 7435). Do not also edit the first — leave that as-is, it is out of scope for this plan.

- [ ] **Step 1: Write the failing test**

```python
def test_context_from_db_includes_active_goal(tmp_path, monkeypatch):
    from synlynk.db import cmd_goal_create
    from synlynk import _generate_context_from_db
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    cmd_goal_create(
        outcome="Ship BS-8",
        criterion="goals table exists and CLI works",
        deadline="2026-09-01",
    )
    context = _generate_context_from_db(out_path=str(tmp_path / ".synlynk" / "context.md"))
    assert "## Active Goal" in context
    assert "Ship BS-8" in context
    assert "goals table exists and CLI works" in context
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_goals.py::test_context_from_db_includes_active_goal -v`
Expected: FAIL — `assert "## Active Goal" in context`

- [ ] **Step 3: Add the Goal query and section**

In `synlynk/__init__.py`, inside the second `_generate_context_from_db` (line 7435), add the query alongside the existing `top_story`/`recent_devlogs`/`memory_sections` queries (after line 7444, before `conn.close()` at line 7452):

```python
    active_goal = conn.execute(
        "SELECT goal_id, outcome, criterion, deadline FROM goals "
        "WHERE status='active' ORDER BY created_at DESC LIMIT 1"
    ).fetchone()
```

Then, in the `with open(context_file, "w") as out:` block, add the section right after the `Generated:` line (after line 7458, before the `if top_story:` block):

```python
        if active_goal:
            goal_id, outcome, criterion, deadline = active_goal
            deadline_s = deadline or "ongoing"
            out.write("## Active Goal\n")
            out.write(f"- [{goal_id}] {outcome}\n")
            out.write(f"  Success criterion: {criterion}  ·  Deadline: {deadline_s}\n\n---\n\n")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_goals.py -v`
Expected: PASS (10 tests)

- [ ] **Step 5: Run the full test suite to confirm no regressions**

Run: `pytest tests/ -v`
Expected: PASS (all tests, including pre-existing `test_synlynk.py` context-generation tests)

- [ ] **Step 6: Commit**

```bash
git add synlynk/__init__.py tests/test_goals.py
git commit -m "feat(context): inject active Business Goal into dispatch context"
```

---

## Self-Review Notes

- **Spec coverage:** Part 1's seven sub-sections are covered — Goal shape (Task 1/3), Goal-vs-Dream nesting via `goal_id` FK + `goal_contributions` (Task 2/4), data model (Task 1/2), and context injection (Task 7) are all implemented. Review cadence (`synlynk goals status` rollup) is Task 5/6. Dispatch ordering (three-factor score) and the `init`/`migrate`/`scan`/Vizor rollout mechanics are **out of scope for this plan** — they belong to the companion GOVERNS rollout plan (`2026-07-11-governs-stage-rollout-plan.md`) and a follow-up dispatch-scoring plan, since BS-8 here is scoped strictly to the data model + CLI + context injection per the spec's "Open Items."
- **Live Issues (`goal_id = NULL` + `lane: maintenance` tag):** the nullable FK from Task 2 already satisfies this — no `lane` column exists yet on `stories`; adding one is not required by this plan since `goal_id IS NULL` alone is sufficient to exclude a story from goal rollups (Task 5's query already only counts stories with a non-null matching `goal_id`). Flagging this as a deliberate YAGNI cut, not an oversight.
- **Placeholder scan:** none found — every step has real code.
- **Type consistency:** `cmd_goal_create(outcome, criterion, deadline=None) -> str` is used identically in Tasks 3, 4, 5, 6, 7.
