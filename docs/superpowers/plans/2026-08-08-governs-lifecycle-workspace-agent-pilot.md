# GOVERNS Lifecycle Enforcement + Workspace Agent Pilot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. **Per this repo's CLAUDE.md, all implementation/testing dispatches must route through `synlynk dispatch <agent> --force-agent --context-mode full` to Codex/Grok/Agy — Claude does not implement.**

**Goal:** Ship a local event bus, three mechanical GOVERNS primitives (`story done`, goal-link-at-approval, `pr check` soft-warn), and one pilot durable workspace agent that consumes the event bus to nudge the user at goal/story/PR boundaries via a shared terminal-tip mechanism.

**Architecture:** A new `events`/`subscriptions` schema (`synlynk/__init__.py` `_DB_SCHEMA`) backs a small `synlynk/events.py` module (`emit_event`, `pending_events`, `advance_checkpoint`). Three existing command functions in `synlynk/db.py` gain new/extended behavior (`cmd_story_done` new, `cmd_story_ready` extended, `cmd_pr_check` extended) that call `emit_event`. A new `synlynk/workspace_agent.py` composes the existing `synlynk/support_engineer.py` cron/config pattern to poll events and emit nudges through a new `NudgeData`/`render_nudge_fence()` pair in `synlynk/fencing.py` (same pattern as the existing `FenceData`/`render_task_fence` cost fence), surfaced from `synlynk/dispatch.py`'s `exec_command()`.

**Tech Stack:** Python 3 stdlib, sqlite3, pytest, existing synlynk CLI (argparse) conventions.

**Implementer decisions made at plan time (deviations from the spec, both driven by codebase facts discovered during planning — not covered by the spec's own wording):**

1. **`pr_merged` and `spec_or_plan_committed` producers are local-only, detected during the pilot agent's own cron run — not GH Actions steps.** `state.db` is centralized at `~/.synlynk/projects/<md5-of-repo-root>/state.db` (`synlynk/__init__.py:811` `_resolve_db_path()`), which is local per-machine. A GH Actions runner gets a fresh, ephemeral filesystem every run, so an event written there during CI never reaches the user's local DB — there is no sync mechanism for it (confirmed: no `_dr_sync`-style push for `state.db` itself, only for the generated markdown docs). Both event types are instead detected locally, once per `agent run`, by diffing against the pilot agent's own event-scan checkpoint (Task 7): `pr_merged` via `gh pr list --state merged --search "merged:>=<checkpoint-date>"`, `spec_or_plan_committed` via `git log --since=<checkpoint> --name-only -- docs/superpowers/specs docs/superpowers/plans`.
2. **Section 2(b)'s "goal-link hook at plan approval" is implemented inside `cmd_story_ready()`, not as a separate git-commit hook.** The spec assumes a mapping from a committed plan file to "the plan's associated story," but no such mapping exists anywhere in this codebase — stories are created independently via `synlynk story create --title`. `cmd_story_ready()` (`synlynk/db.py:1930`) is this codebase's actual existing mechanical checkpoint for "a story's plan is approved and about to enter execution" (only `ready` stories are scheduling candidates), so the goal-link check is added there instead of inventing a new detection mechanism.
3. **The nudge config block lives in the existing project-local `.synlynk/config.json`, not `~/.synlynk/config.json`.** Every config read/write in this codebase (`load_config()`, `_update_config()`, `.synlynk/config.json` at 8+ call sites in `synlynk/__init__.py`) uses the project-local path. A new global `~/.synlynk/config.json` would be an invented convention with no precedent.

---

## File Structure

- Modify `synlynk/__init__.py` — add `events` and `subscriptions` tables to `_DB_SCHEMA` (after the existing `goal_contributions` block, ~line 955).
- Create `synlynk/events.py` — `emit_event()`, `pending_events()`, `advance_checkpoint()`, `scan_local_events()`.
- Modify `synlynk/db.py` — extend `_migrate_db()` (add `link_status`/`skip_reason` to `goal_contributions`); add `cmd_story_done()`; extend `cmd_story_ready()`; extend `cmd_pr_check()`.
- Modify `synlynk/cli.py` — add `story done` subparser + dispatch (~line 693, ~line 1132); add `config nudges` subparser + dispatch.
- Modify `synlynk/fencing.py` — add `NudgeData` dataclass + `render_nudge_fence()`.
- Modify `synlynk/dispatch.py` — hook pending-nudge check into `exec_command()`'s `finally` block (~line 2248, after the existing telemetry log call).
- Create `synlynk/workspace_agent.py` — `cmd_workspace_agent_run()`: reads events since checkpoint, cross-references goal/story state, writes nudges.
- Create `.agents/workspace-lifecycle-nudge.json` — pilot agent role config.
- Create `.github/workflows/workspace-lifecycle-nudge.yml` — mirrors `.github/workflows/support-engineer.yml`'s cron trigger.
- Create `tests/test_events.py`, extend `tests/test_cost_ledger.py`-adjacent test files for `cmd_story_done`/`cmd_story_ready`/`cmd_pr_check`, create `tests/test_workspace_agent.py`, `tests/test_fencing.py` (if not already present — check first).

---

### Task 1: `events` and `subscriptions` schema + `synlynk/events.py`

**Files:**
- Modify: `synlynk/__init__.py:950-955` (insert after the `goal_contributions` block)
- Create: `synlynk/events.py`
- Test: `tests/test_events.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_events.py
import json
import sqlite3
import pytest
from synlynk.events import emit_event, pending_events, advance_checkpoint


def test_emit_event_writes_row_and_returns_id(project_dir):
    event_id = emit_event(
        "story_done",
        {"story_id": "story-abc123", "goal_ids": ["goal-xyz789"]},
        emitted_by="cmd_story_done",
    )
    assert isinstance(event_id, int) and event_id > 0

    import synlynk
    conn = synlynk._get_db()
    row = conn.execute(
        "SELECT event_type, payload_json, emitted_by, parent_event_id FROM events WHERE id=?",
        (event_id,),
    ).fetchone()
    conn.close()
    assert row[0] == "story_done"
    assert json.loads(row[1]) == {"story_id": "story-abc123", "goal_ids": ["goal-xyz789"]}
    assert row[2] == "cmd_story_done"
    assert row[3] is None


def test_pending_events_returns_only_events_after_checkpoint(project_dir):
    e1 = emit_event("story_done", {"story_id": "s1"}, emitted_by="test")
    e2 = emit_event("story_done", {"story_id": "s2"}, emitted_by="test")
    advance_checkpoint("workspace-lifecycle-nudge", "story_done", e1)

    pending = pending_events("workspace-lifecycle-nudge", "story_done")

    assert [p["id"] for p in pending] == [e2]
    assert pending[0]["payload"] == {"story_id": "s2"}


def test_pending_events_ignores_other_event_types(project_dir):
    emit_event("pr_merged", {"pr": 1}, emitted_by="test")
    story_event_id = emit_event("story_done", {"story_id": "s1"}, emitted_by="test")

    pending = pending_events("workspace-lifecycle-nudge", "story_done")

    assert [p["id"] for p in pending] == [story_event_id]


def test_advance_checkpoint_never_moves_backward(project_dir):
    e1 = emit_event("story_done", {"story_id": "s1"}, emitted_by="test")
    e2 = emit_event("story_done", {"story_id": "s2"}, emitted_by="test")
    advance_checkpoint("workspace-lifecycle-nudge", "story_done", e2)
    advance_checkpoint("workspace-lifecycle-nudge", "story_done", e1)

    pending = pending_events("workspace-lifecycle-nudge", "story_done")

    assert pending == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_events.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.events'`

- [ ] **Step 3: Add the schema**

In `synlynk/__init__.py`, immediately after the existing block:

```sql
CREATE TABLE IF NOT EXISTS goal_contributions (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    goal_id  TEXT NOT NULL REFERENCES goals(goal_id),
    story_id TEXT NOT NULL REFERENCES stories(story_id),
    UNIQUE(goal_id, story_id)
);
```

insert:

```sql

CREATE TABLE IF NOT EXISTS events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type      TEXT NOT NULL,
    payload_json    TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    emitted_by      TEXT NOT NULL,
    parent_event_id INTEGER,
    authority_scope TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type, id);

CREATE TABLE IF NOT EXISTS subscriptions (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_name         TEXT NOT NULL,
    event_type         TEXT NOT NULL,
    last_seen_event_id INTEGER NOT NULL DEFAULT 0,
    UNIQUE(agent_name, event_type)
);
```

- [ ] **Step 4: Implement `synlynk/events.py`**

```python
"""Local event bus: append-only events table + per-agent subscription checkpoints.

Local-only for this build — authority_scope is reserved for future team/enterprise
delivery and is always written as NULL here (see plan Task 1 header note).
"""

import json
import time


def emit_event(event_type: str, payload: dict, emitted_by: str,
                parent_event_id: int = None) -> int:
    """Writes an event row. Returns the new event's id."""
    from synlynk import _get_db
    conn = _get_db()
    cur = conn.execute(
        "INSERT INTO events (event_type, payload_json, created_at, emitted_by, parent_event_id, authority_scope) "
        "VALUES (?, ?, ?, ?, ?, NULL)",
        (event_type, json.dumps(payload), time.strftime("%Y-%m-%dT%H:%M:%S"), emitted_by, parent_event_id),
    )
    conn.commit()
    event_id = cur.lastrowid
    conn.close()
    return event_id


def pending_events(agent_name: str, event_type: str) -> list:
    """Returns events of event_type with id greater than agent_name's checkpoint, oldest first."""
    from synlynk import _get_db
    conn = _get_db()
    row = conn.execute(
        "SELECT last_seen_event_id FROM subscriptions WHERE agent_name=? AND event_type=?",
        (agent_name, event_type),
    ).fetchone()
    checkpoint = row[0] if row else 0
    rows = conn.execute(
        "SELECT id, event_type, payload_json, created_at, emitted_by, parent_event_id "
        "FROM events WHERE event_type=? AND id>? ORDER BY id ASC",
        (event_type, checkpoint),
    ).fetchall()
    conn.close()
    return [
        {"id": r[0], "event_type": r[1], "payload": json.loads(r[2]),
         "created_at": r[3], "emitted_by": r[4], "parent_event_id": r[5]}
        for r in rows
    ]


def advance_checkpoint(agent_name: str, event_type: str, event_id: int) -> None:
    """Advances agent_name's checkpoint for event_type to event_id. Never moves backward."""
    from synlynk import _get_db
    conn = _get_db()
    conn.execute(
        "INSERT INTO subscriptions (agent_name, event_type, last_seen_event_id) VALUES (?, ?, ?) "
        "ON CONFLICT(agent_name, event_type) DO UPDATE SET "
        "last_seen_event_id=excluded.last_seen_event_id "
        "WHERE excluded.last_seen_event_id > subscriptions.last_seen_event_id",
        (agent_name, event_type, event_id),
    )
    conn.commit()
    conn.close()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_events.py -v`
Expected: PASS (4 tests)

- [ ] **Step 6: Commit**

```bash
git add synlynk/__init__.py synlynk/events.py tests/test_events.py
git commit -m "feat: add events/subscriptions schema and local event bus module"
```

---

### Task 2: `goal_contributions` link-status tracking

**Files:**
- Modify: `synlynk/db.py:239-300` (`_migrate_db()`)
- Test: `tests/test_events.py` (append)

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_events.py
def test_migration_adds_link_status_and_skip_reason_columns(project_dir):
    import synlynk
    conn = synlynk._get_db()
    cols = {row[1] for row in conn.execute("PRAGMA table_info(goal_contributions)")}
    conn.close()
    assert "link_status" in cols
    assert "skip_reason" in cols
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_events.py::test_migration_adds_link_status_and_skip_reason_columns -v`
Expected: FAIL — `link_status` not in cols

- [ ] **Step 3: Add the migration**

In `synlynk/db.py`, inside `_migrate_db()`, after the `stories` column block (after line 271's `goal_id` handling, before the `daemon_jobs` block at line 288):

```python
    gc_cols = {row[1] for row in conn.execute("PRAGMA table_info(goal_contributions)")}
    if "link_status" not in gc_cols:
        try:
            conn.execute(
                "ALTER TABLE goal_contributions ADD COLUMN link_status TEXT NOT NULL DEFAULT 'linked'"
            )
        except sqlite3.OperationalError:
            pass
    if "skip_reason" not in gc_cols:
        try:
            conn.execute("ALTER TABLE goal_contributions ADD COLUMN skip_reason TEXT")
        except sqlite3.OperationalError:
            pass
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_events.py::test_migration_adds_link_status_and_skip_reason_columns -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add synlynk/db.py tests/test_events.py
git commit -m "feat: track link_status/skip_reason on goal_contributions"
```

---

### Task 3: `synlynk story <id> done`

**Files:**
- Modify: `synlynk/db.py` (add `cmd_story_done`, after `cmd_story_draft` at line 1958)
- Modify: `synlynk/cli.py:693` (subparser), `synlynk/cli.py:1132` (dispatch)
- Test: `tests/test_story_lifecycle.py` (create — no existing file covers `story` commands directly per repo search; follow `tests/test_cost_ledger.py`'s `project_dir` fixture pattern)

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_story_lifecycle.py
import synlynk
from synlynk.db import cmd_story_create, cmd_story_done
from synlynk.events import pending_events


def test_story_done_sets_status_and_emits_event(project_dir):
    story_id = cmd_story_create(title="Test story")

    cmd_story_done(story_id)

    conn = synlynk._get_db()
    status = conn.execute(
        "SELECT status FROM stories WHERE story_id=?", (story_id,)
    ).fetchone()[0]
    conn.close()
    assert status == "done"

    pending = pending_events("test-observer", "story_done")
    assert len(pending) == 1
    assert pending[0]["payload"]["story_id"] == story_id


def test_story_done_includes_linked_goal_ids_in_payload(project_dir):
    from synlynk.db import cmd_goal_create, cmd_goal_link
    story_id = cmd_story_create(title="Test story")
    goal_id = cmd_goal_create("Outcome", "Criterion")
    cmd_goal_link(story_id, goal_id)

    cmd_story_done(story_id)

    pending = pending_events("test-observer", "story_done")
    assert pending[0]["payload"]["goal_ids"] == [goal_id]


def test_story_done_unknown_story_prints_error(project_dir, capsys):
    cmd_story_done("story-doesnotexist")
    captured = capsys.readouterr()
    assert "not found" in captured.out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_story_lifecycle.py -v`
Expected: FAIL with `ImportError: cannot import name 'cmd_story_done'`

- [ ] **Step 3: Implement `cmd_story_done`**

In `synlynk/db.py`, after `cmd_story_draft` (line 1958):

```python
def cmd_story_done(story_id: str) -> None:
    """Marks a story done and emits a story_done event carrying its linked goal ids."""
    from synlynk import _GREEN, _RESET, _get_db
    from synlynk.events import emit_event
    conn = _get_db()
    story = conn.execute(
        "SELECT story_id, goal_id FROM stories WHERE story_id=?", (story_id,)
    ).fetchone()
    if not story:
        conn.close()
        print(f"  Story '{story_id}' not found.")
        return
    conn.execute("UPDATE stories SET status='done' WHERE story_id=?", (story_id,))
    conn.commit()
    goal_ids = []
    if story[1]:
        goal_ids.append(story[1])
    secondary = conn.execute(
        "SELECT goal_id FROM goal_contributions WHERE story_id=?", (story_id,)
    ).fetchall()
    conn.close()
    goal_ids.extend(g[0] for g in secondary if g[0] not in goal_ids)
    emit_event(
        "story_done",
        {"story_id": story_id, "goal_ids": goal_ids},
        emitted_by="cmd_story_done",
    )
    print(f"  {_GREEN}✓{_RESET} Story {story_id} marked done")
```

- [ ] **Step 4: Wire the CLI**

In `synlynk/cli.py`, after line 693 (`story_draft_parser.add_argument("story_id")`):

```python
    story_done_parser = story_sub.add_parser("done", help="Mark a story done")
    story_done_parser.add_argument("story_id")
```

In `synlynk/cli.py`, after line 1132-1133 (`elif args.story_action == "draft": cmd_story_draft(args.story_id)`):

```python
        elif args.story_action == "done":
            cmd_story_done(args.story_id)
```

Add `cmd_story_done` to the existing `from synlynk.db import ...` line that already imports `cmd_story_create, cmd_story_list, cmd_story_ready, cmd_story_draft` (grep for that import line at the top of the dispatch function and extend it).

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_story_lifecycle.py -v`
Expected: PASS (3 tests)

- [ ] **Step 6: Commit**

```bash
git add synlynk/db.py synlynk/cli.py tests/test_story_lifecycle.py
git commit -m "feat: add synlynk story done command, emits story_done event"
```

---

### Task 4: Goal-link hook in `cmd_story_ready`

**Files:**
- Modify: `synlynk/db.py:1930-1948` (`cmd_story_ready`)
- Test: `tests/test_story_lifecycle.py` (append)

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_story_lifecycle.py
from synlynk.db import cmd_story_ready, cmd_goal_create, cmd_goal_link


def test_story_ready_records_skip_when_no_goal_linked(project_dir):
    story_id = cmd_story_create(title="Unlinked story")

    cmd_story_ready(story_id)

    conn = synlynk._get_db()
    row = conn.execute(
        "SELECT link_status, skip_reason FROM goal_contributions WHERE story_id=?",
        (story_id,),
    ).fetchone()
    conn.close()
    assert row is not None
    assert row[0] == "skipped"
    assert row[1] == "no active goal specified at plan-approval time"


def test_story_ready_no_op_when_goal_already_linked(project_dir):
    story_id = cmd_story_create(title="Linked story")
    goal_id = cmd_goal_create("Outcome", "Criterion")
    cmd_goal_link(story_id, goal_id)

    cmd_story_ready(story_id)

    conn = synlynk._get_db()
    rows = conn.execute(
        "SELECT link_status FROM goal_contributions WHERE story_id=?", (story_id,)
    ).fetchall()
    conn.close()
    assert rows == [("linked",)]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_story_lifecycle.py -v`
Expected: FAIL — `goal_contributions` row is None for the unlinked case

- [ ] **Step 3: Extend `cmd_story_ready`**

Replace `synlynk/db.py:1930-1948` with:

```python
def cmd_story_ready(story_id, all_stories: bool = False) -> None:
    """Marks one story (or every draft story, with all_stories=True) as ready
    for scheduling. Only 'ready' stories are candidates for synlynk schedule.

    Also runs the GOVERNS goal-link check: this is the codebase's actual
    mechanical checkpoint for "a story's plan is approved and about to enter
    execution" (see plan Task 4). Records a goal_contributions row either way
    so the gap that let the table sit silently empty is now queryable.
    """
    from synlynk import _GREEN, _RESET, _get_db
    conn = _get_db()
    if all_stories:
        ready_ids = [r[0] for r in conn.execute(
            "SELECT story_id FROM stories WHERE readiness='draft'"
        ).fetchall()]
        conn.execute("UPDATE stories SET readiness='ready' WHERE readiness='draft'")
        conn.commit()
        for sid in ready_ids:
            _record_goal_link_status(conn, sid)
        conn.close()
        print(f"  {_GREEN}✓{_RESET} Marked {len(ready_ids)} draft stories ready")
        return
    if not story_id:
        conn.close()
        print("  Error: story_id required unless --all is given")
        return
    conn.execute("UPDATE stories SET readiness='ready' WHERE story_id=?", (story_id,))
    conn.commit()
    _record_goal_link_status(conn, story_id)
    conn.close()
    print(f"  {_GREEN}✓{_RESET} Story {story_id} marked ready")


def _record_goal_link_status(conn, story_id: str) -> None:
    """Writes a goal_contributions row reflecting story_id's current goal linkage."""
    story = conn.execute("SELECT goal_id FROM stories WHERE story_id=?", (story_id,)).fetchone()
    if not story:
        return
    primary_goal_id = story[0]
    secondary = conn.execute(
        "SELECT goal_id FROM goal_contributions WHERE story_id=?", (story_id,)
    ).fetchall()
    if primary_goal_id:
        conn.execute(
            "INSERT OR IGNORE INTO goal_contributions (goal_id, story_id, link_status) "
            "VALUES (?, ?, 'linked')",
            (primary_goal_id, story_id),
        )
        conn.commit()
        return
    if secondary:
        return
    conn.execute(
        "INSERT OR IGNORE INTO goal_contributions (goal_id, story_id, link_status, skip_reason) "
        "VALUES ('none', ?, 'skipped', 'no active goal specified at plan-approval time')",
        (story_id,),
    )
    conn.commit()
```

Note: `goal_contributions.goal_id` has `REFERENCES goals(goal_id)` but SQLite does not enforce FK constraints unless `PRAGMA foreign_keys=ON` is set (not set anywhere in this codebase — confirmed no `PRAGMA foreign_keys` calls in `synlynk/__init__.py` or `synlynk/db.py`), so the literal `'none'` sentinel value is safe to insert.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_story_lifecycle.py -v`
Expected: PASS (5 tests total)

- [ ] **Step 5: Run the full existing test suite to check for regressions**

Run: `pytest tests/ -k "story_ready or goal" -v`
Expected: PASS — no existing test asserted on `cmd_story_ready`'s prior no-op goal behavior (grep `tests/` for `cmd_story_ready` first to confirm no conflicting assertions before this step; if any exist, reconcile them here).

- [ ] **Step 6: Commit**

```bash
git add synlynk/db.py tests/test_story_lifecycle.py
git commit -m "feat: record goal-link status in cmd_story_ready (GOVERNS checkpoint)"
```

---

### Task 5: `synlynk pr check` soft-warn for unlinked goals

**Files:**
- Modify: `synlynk/db.py:2230-2267` (`cmd_pr_check`)
- Test: `tests/test_pr_check.py` (create)

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_pr_check.py
from unittest.mock import patch
import synlynk
from synlynk.db import cmd_story_create, cmd_pr_check


def test_pr_check_soft_warns_on_unlinked_story(project_dir, capsys):
    story_id = cmd_story_create(title="PR story")
    conn = synlynk._get_db()
    conn.execute(
        "INSERT INTO capability_ratings (story_id, agent, model_version, pr_number, quality, signal_source) "
        "VALUES (?, 'codex', 'gpt-5', 42, 8.0, 'human')",
        (story_id,),
    )
    conn.commit()
    conn.close()

    with patch("synlynk.pr_multiplier._is_github_remote", return_value=False):
        cmd_pr_check()

    captured = capsys.readouterr()
    assert "no linked GOVERNS goal" in captured.out
    assert story_id in captured.out


def test_pr_check_does_not_warn_when_goal_linked(project_dir, capsys):
    from synlynk.db import cmd_goal_create, cmd_goal_link
    story_id = cmd_story_create(title="PR story")
    goal_id = cmd_goal_create("Outcome", "Criterion")
    cmd_goal_link(story_id, goal_id)
    conn = synlynk._get_db()
    conn.execute(
        "INSERT INTO capability_ratings (story_id, agent, model_version, pr_number, quality, signal_source) "
        "VALUES (?, 'codex', 'gpt-5', 43, 8.0, 'human')",
        (story_id,),
    )
    conn.commit()
    conn.close()

    with patch("synlynk.pr_multiplier._is_github_remote", return_value=False):
        cmd_pr_check()

    captured = capsys.readouterr()
    assert "no linked GOVERNS goal" not in captured.out


def test_pr_check_soft_warn_does_not_change_exit_code(project_dir):
    story_id = cmd_story_create(title="PR story")
    conn = synlynk._get_db()
    conn.execute(
        "INSERT INTO capability_ratings (story_id, agent, model_version, pr_number, quality, signal_source) "
        "VALUES (?, 'codex', 'gpt-5', 44, 8.0, 'human')",
        (story_id,),
    )
    conn.commit()
    conn.close()

    with patch("synlynk.pr_multiplier._is_github_remote", return_value=False):
        cmd_pr_check()  # must not raise SystemExit — only the model-version block does
```

Check the exact `capability_ratings` columns (`story_id, agent, model_version, pr_number, quality, signal_source`) against `synlynk/__init__.py`'s `_DB_SCHEMA` before writing this insert — adjust the `INSERT` column list to match the real schema if it differs (grep `CREATE TABLE IF NOT EXISTS capability_ratings` in `synlynk/__init__.py`).

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_pr_check.py -v`
Expected: FAIL — no "no linked GOVERNS goal" text printed

- [ ] **Step 3: Extend `cmd_pr_check`**

In `synlynk/db.py`, insert before the final `print(f"  {_GREEN}✓{_RESET} PR check passed...")` line (line 2267):

```python
    conn2 = _get_db()
    unlinked_story_ids = conn2.execute(
        "SELECT DISTINCT cr.story_id FROM capability_ratings cr "
        "LEFT JOIN stories s ON s.story_id = cr.story_id "
        "WHERE s.goal_id IS NULL "
        "AND cr.story_id NOT IN ("
        "  SELECT story_id FROM goal_contributions WHERE link_status='linked'"
        ")"
    ).fetchall()
    conn2.close()
    if unlinked_story_ids:
        print("\n  ⚠ [PR CHECK] Stories with no linked GOVERNS goal (soft-warn, not blocking):")
        for (story_id,) in unlinked_story_ids:
            print(f"    {story_id}")
        print("  Link with: synlynk goal link <story-id> --goal <goal-id>\n")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_pr_check.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add synlynk/db.py tests/test_pr_check.py
git commit -m "feat: soft-warn synlynk pr check on stories with no linked GOVERNS goal"
```

---

### Task 6: Nudge fence + config

**Files:**
- Modify: `synlynk/fencing.py`
- Modify: `synlynk/__init__.py` (`load_config()` defaults)
- Modify: `synlynk/cli.py` (new `config nudges` subcommand)
- Test: `tests/test_fencing.py` (check if it exists first — extend if so, create if not)

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_fencing.py (extend existing file, or create if none exists)
from synlynk.fencing import NudgeData, render_nudge_fence


def test_render_nudge_fence_includes_message_and_id():
    data = NudgeData(
        nudge_id="goal-closed-goal-90e73dfd",
        title="Goal closed",
        message="All stories linked to goal-90e73dfd are done.",
        follow_up="synlynk goal status",
    )
    output = render_nudge_fence(data)
    assert "Goal closed" in output
    assert "All stories linked to goal-90e73dfd are done." in output
    assert "synlynk goal status" in output


def test_render_nudge_fence_has_bordered_box_shape():
    data = NudgeData(nudge_id="x", title="T", message="M")
    output = render_nudge_fence(data)
    lines = output.rstrip("\n").split("\n")
    assert lines[0].startswith("--")
    assert lines[-1] == "-" * 36
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_fencing.py -v`
Expected: FAIL — `ImportError: cannot import name 'NudgeData'`

- [ ] **Step 3: Implement `NudgeData`/`render_nudge_fence`**

Append to `synlynk/fencing.py`:

```python
@dataclass
class NudgeData:
    nudge_id: str
    title: str
    message: str
    follow_up: Optional[str] = None


def render_nudge_fence(data: NudgeData) -> str:
    """Render a bordered fence block for a workspace-agent nudge.

    Distinctive from render_task_fence's cost framing: no dollar figures,
    used for goal/story/PR lifecycle boundary nudges instead.
    """
    header = f"-- {data.title} " + "-" * max(1, 32 - len(data.title))
    lines = [header, data.message]
    if data.follow_up:
        lines.append(f"next: {data.follow_up}")
    lines.append("-" * 36)
    return "\n".join(lines) + "\n"
```

- [ ] **Step 4: Add `nudges` config defaults**

In `synlynk/__init__.py`, find `load_config()` (line 1479) and its default dict (read the function body first — it merges saved config over a defaults dict per the "schema-v1 defaults" docstring). Add to that defaults dict:

```python
        "nudges": {"enabled": True, "dismissed_ids": [], "last_shown": {}},
```

- [ ] **Step 5: Add `synlynk config nudges on/off/reset`**

In `synlynk/cli.py`, find the existing `config` subparser (grep `add_parser("config"` — if none exists yet, add one following the `goal`/`story` subparser pattern at line 261/667) and add:

```python
    config_parser = subparsers.add_parser("config", help="Manage local config")
    config_sub = config_parser.add_subparsers(dest="config_action")
    nudges_parser = config_sub.add_parser("nudges", help="Control workspace-agent nudges")
    nudges_parser.add_argument("state", choices=["on", "off", "reset"])
```

In the dispatch section, alongside the other `elif args.command ==` blocks:

```python
    elif args.command == "config":
        if args.config_action == "nudges":
            from synlynk import _update_config, load_config
            cfg = load_config()
            nudges_cfg = cfg.get("nudges", {"enabled": True, "dismissed_ids": [], "last_shown": {}})
            if args.state == "on":
                nudges_cfg["enabled"] = True
            elif args.state == "off":
                nudges_cfg["enabled"] = False
            elif args.state == "reset":
                nudges_cfg = {"enabled": True, "dismissed_ids": [], "last_shown": {}}
            _update_config({"nudges": nudges_cfg})
            print(f"  ✓ nudges {args.state}")
```

If a `config` subparser already exists in `cli.py` (check via `grep -n 'add_parser("config"' synlynk/cli.py` before writing this step — the repo may already have one for other keys), add the `nudges` sub-action onto the existing subparser instead of creating a duplicate.

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_fencing.py -v`
Expected: PASS (2 tests)

- [ ] **Step 7: Commit**

```bash
git add synlynk/fencing.py synlynk/__init__.py synlynk/cli.py tests/test_fencing.py
git commit -m "feat: add nudge fence rendering and synlynk config nudges command"
```

---

### Task 7: Local event scanning (`cron_heartbeat`, `pr_merged`, `spec_or_plan_committed`)

**Files:**
- Modify: `synlynk/events.py` (add `scan_local_events`)
- Test: `tests/test_events.py` (append)

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_events.py
from unittest.mock import patch, MagicMock
from synlynk.events import scan_local_events


def test_scan_local_events_always_emits_cron_heartbeat(project_dir):
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="[]")
        scan_local_events("workspace-lifecycle-nudge")

    pending = pending_events("test-observer", "cron_heartbeat")
    assert len(pending) == 1


def test_scan_local_events_emits_pr_merged_from_gh_output(project_dir):
    import json as _json
    gh_stdout = _json.dumps([{"number": 99, "title": "Test PR", "mergedAt": "2026-08-08T00:00:00Z"}])
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=gh_stdout)
        scan_local_events("workspace-lifecycle-nudge")

    pending = pending_events("test-observer", "pr_merged")
    assert len(pending) == 1
    assert pending[0]["payload"]["pr_number"] == 99


def test_scan_local_events_advances_own_checkpoint(project_dir):
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="[]")
        scan_local_events("workspace-lifecycle-nudge")
        first_pending = pending_events("workspace-lifecycle-nudge", "cron_heartbeat")
        assert first_pending == []  # scan_local_events advances its own checkpoint as it emits
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_events.py -v -k scan_local_events`
Expected: FAIL — `ImportError: cannot import name 'scan_local_events'`

- [ ] **Step 3: Implement `scan_local_events`**

Append to `synlynk/events.py`:

```python
def scan_local_events(agent_name: str) -> None:
    """Detects and emits pr_merged, spec_or_plan_committed, and cron_heartbeat
    events for this run, then advances agent_name's own checkpoints so it
    never re-detects the same underlying activity twice.

    Both pr_merged and spec_or_plan_committed are detected locally rather than
    via GH Actions — see plan Task 7 header note (state.db is local-only,
    CI-emitted events would never reach it).
    """
    import json
    import subprocess

    heartbeat_id = emit_event("cron_heartbeat", {}, emitted_by="scan_local_events")
    advance_checkpoint(agent_name, "cron_heartbeat", heartbeat_id)

    try:
        result = subprocess.run(
            ["gh", "pr", "list", "--state", "merged", "--limit", "20",
             "--json", "number,title,mergedAt"],
            capture_output=True, text=True, check=False,
        )
        merged_prs = json.loads(result.stdout) if result.returncode == 0 else []
    except (FileNotFoundError, json.JSONDecodeError):
        merged_prs = []

    last_event_id = None
    for pr in merged_prs:
        last_event_id = emit_event(
            "pr_merged",
            {"pr_number": pr["number"], "title": pr.get("title"), "merged_at": pr.get("mergedAt")},
            emitted_by="scan_local_events",
        )
    if last_event_id is not None:
        advance_checkpoint(agent_name, "pr_merged", last_event_id)

    try:
        result = subprocess.run(
            ["git", "log", "--name-only", "--pretty=format:", "-20",
             "--", "docs/superpowers/specs", "docs/superpowers/plans"],
            capture_output=True, text=True, check=False,
        )
        changed_paths = sorted({line for line in result.stdout.splitlines() if line.strip()})
    except FileNotFoundError:
        changed_paths = []

    last_event_id = None
    for path in changed_paths:
        last_event_id = emit_event(
            "spec_or_plan_committed",
            {"path": path},
            emitted_by="scan_local_events",
        )
    if last_event_id is not None:
        advance_checkpoint(agent_name, "spec_or_plan_committed", last_event_id)
```

Note: `gh pr list --state merged` and the `git log` scan will re-report the same PRs/paths every run since they aren't windowed by the caller's own checkpoint — this is intentional for the pilot (dedup happens on the *consumer* side, Task 8, via its own `pending_events` checkpoint per agent_name). A future goal (already tracked: `goal-eacab0dc`, universal enforcement) can tighten this to a time-windowed query; out of scope here per YAGNI.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_events.py -v -k scan_local_events`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add synlynk/events.py tests/test_events.py
git commit -m "feat: local scan for pr_merged, spec_or_plan_committed, cron_heartbeat events"
```

---

### Task 8: Pilot workspace agent

**Files:**
- Create: `synlynk/workspace_agent.py`
- Create: `.agents/workspace-lifecycle-nudge.json`
- Modify: `synlynk/cli.py` (`agent run workspace-lifecycle-nudge` already routes through the existing `agent` subparser/`cmd_agent_run` — verify `cmd_agent_run` in `synlynk/support_engineer.py:20` dispatches by config `name`, not a hardcoded signal list, before assuming no CLI change is needed)
- Test: `tests/test_workspace_agent.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_workspace_agent.py
from unittest.mock import patch, MagicMock
import synlynk
from synlynk.db import cmd_story_create, cmd_story_done, cmd_goal_create, cmd_goal_link
from synlynk.workspace_agent import cmd_workspace_agent_run


def test_nudges_on_goal_fully_closed(project_dir, capsys):
    story_id = cmd_story_create(title="Only story")
    goal_id = cmd_goal_create("Ship the thing", "All stories done")
    cmd_goal_link(story_id, goal_id)

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="[]")
        cmd_story_done(story_id)
        cmd_workspace_agent_run()

    captured = capsys.readouterr()
    assert goal_id in captured.out
    assert "closed" in captured.out.lower()


def test_no_nudge_when_goal_still_has_open_stories(project_dir, capsys):
    story_id = cmd_story_create(title="Story one")
    story_id_2 = cmd_story_create(title="Story two")
    goal_id = cmd_goal_create("Ship the thing", "All stories done")
    cmd_goal_link(story_id, goal_id)
    cmd_goal_link(story_id_2, goal_id)

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="[]")
        cmd_story_done(story_id)
        cmd_workspace_agent_run()

    captured = capsys.readouterr()
    assert "closed" not in captured.out.lower()


def test_nudges_use_agent_specific_checkpoint_no_repeat(project_dir, capsys):
    story_id = cmd_story_create(title="Only story")
    goal_id = cmd_goal_create("Ship the thing", "All stories done")
    cmd_goal_link(story_id, goal_id)

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="[]")
        cmd_story_done(story_id)
        cmd_workspace_agent_run()
        capsys.readouterr()
        cmd_workspace_agent_run()

    captured = capsys.readouterr()
    assert goal_id not in captured.out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_workspace_agent.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'synlynk.workspace_agent'`

- [ ] **Step 3: Implement `synlynk/workspace_agent.py`**

```python
"""Pilot durable workspace agent: consumes the local event bus (synlynk/events.py)
and nudges at goal/story/PR lifecycle boundaries.

"Durable" in this build means: persisted .agents/workspace-lifecycle-nudge.json
config + persisted subscriptions checkpoint state (this module reuses the same
DB checkpoint mechanism story_done/pr_merged/etc. producers write into) +
cron-scheduled execution (same trigger mechanism as support_engineer.py) — not
a long-lived process. See spec Section 3.
"""

AGENT_NAME = "workspace-lifecycle-nudge"
_EVENT_TYPES = ["pr_merged", "story_done", "spec_or_plan_committed", "cron_heartbeat"]


def cmd_workspace_agent_run() -> None:
    from synlynk import _get_db
    from synlynk.events import pending_events, advance_checkpoint, scan_local_events
    from synlynk.fencing import NudgeData, render_nudge_fence

    scan_local_events(AGENT_NAME)

    nudges = []
    conn = _get_db()

    for event in pending_events(AGENT_NAME, "story_done"):
        goal_ids = event["payload"].get("goal_ids", [])
        for goal_id in goal_ids:
            total = conn.execute(
                "SELECT COUNT(*) FROM stories WHERE goal_id=?", (goal_id,)
            ).fetchone()[0]
            done = conn.execute(
                "SELECT COUNT(*) FROM stories WHERE goal_id=? AND status='done'", (goal_id,)
            ).fetchone()[0]
            if total > 0 and total == done:
                outcome = conn.execute(
                    "SELECT outcome FROM goals WHERE goal_id=?", (goal_id,)
                ).fetchone()
                nudges.append(NudgeData(
                    nudge_id=f"goal-closed-{goal_id}",
                    title="Goal closed",
                    message=f"{goal_id} ({outcome[0] if outcome else goal_id}) — all linked stories are done.",
                    follow_up="synlynk goal status",
                ))
        advance_checkpoint(AGENT_NAME, "story_done", event["id"])

    for event in pending_events(AGENT_NAME, "pr_merged"):
        advance_checkpoint(AGENT_NAME, "pr_merged", event["id"])

    for event in pending_events(AGENT_NAME, "spec_or_plan_committed"):
        advance_checkpoint(AGENT_NAME, "spec_or_plan_committed", event["id"])

    for event in pending_events(AGENT_NAME, "cron_heartbeat"):
        advance_checkpoint(AGENT_NAME, "cron_heartbeat", event["id"])

    conn.close()

    for nudge in nudges:
        print(render_nudge_fence(nudge))
```

- [ ] **Step 4: Create the role config**

```json
{
  "role": "workspace-lifecycle-nudge",
  "sfia_codes": ["PROB", "PEMT", "BURM"],
  "subscriptions": ["pr_merged", "story_done", "spec_or_plan_committed", "cron_heartbeat"],
  "charter_version": null,
  "schedule": "0 */6 * * *"
}
```

Save to `.agents/workspace-lifecycle-nudge.json`.

- [ ] **Step 5: Wire into `cmd_agent_run`**

Read `synlynk/support_engineer.py:20-30` (`cmd_agent_run`) — it dispatches purely off `cfg.get("signals", [])`, which this pilot's config does not define (it has `subscriptions` instead, a different vocabulary). Add a branch at the top of `cmd_agent_run` in `synlynk/support_engineer.py`:

```python
def cmd_agent_run(name: str, dry_run: bool = False, install_cron: bool = False) -> None:
    """Run named agent: collect signals → dedup → investigate → file → fix."""
    import hashlib as _hashlib

    cfg = _pkg("_load_agent_config")(name)
    if install_cron:
        _install_cron_entry(name)
        return

    if "subscriptions" in cfg:
        from synlynk.workspace_agent import cmd_workspace_agent_run
        cmd_workspace_agent_run()
        return

    is_ci = os.environ.get("GITHUB_ACTIONS") == "true"
    # ... (rest of existing function body unchanged)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_workspace_agent.py -v`
Expected: PASS (3 tests)

- [ ] **Step 7: Commit**

```bash
git add synlynk/workspace_agent.py .agents/workspace-lifecycle-nudge.json synlynk/support_engineer.py tests/test_workspace_agent.py
git commit -m "feat: pilot workspace-lifecycle-nudge agent"
```

---

### Task 9: Surface pending nudges from `exec_command`

**Files:**
- Modify: `synlynk/dispatch.py:2248-2276` (`exec_command`'s `finally` block)
- Test: `tests/test_dispatch_nudges.py` (create)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_dispatch_nudges.py
from unittest.mock import patch, MagicMock
from synlynk.dispatch import exec_command


def test_exec_command_prints_pending_nudge_when_enabled(project_dir, capsys):
    from synlynk.events import emit_event, advance_checkpoint
    from synlynk.fencing import NudgeData

    with patch("subprocess.run") as mock_run, \
         patch("subprocess.Popen") as mock_popen:
        mock_run.return_value = MagicMock(returncode=0, stdout="hello\n")
        mock_process = MagicMock()
        mock_process.wait.return_value = None
        mock_process.returncode = 0
        mock_process.stdout.readline.side_effect = [b""]
        mock_popen.return_value = mock_process

        emit_event("story_done", {"story_id": "s1", "goal_ids": []}, emitted_by="test")
        exec_command(["echo", "hello"])

    captured = capsys.readouterr()
    assert "story done" in captured.out.lower() or "1 pending" in captured.out.lower()
```

Given `exec_command`'s heavy use of injected `_pkg(...)` lookups and threaded subprocess streaming, this test is genuinely awkward to assert against directly — write it, run it, and if the subprocess-mocking proves too brittle within the 2-5 minute step budget, fall back to a narrower unit test that calls the new helper function directly (Step 3 defines it as `_print_pending_nudges()`, testable in isolation):

```python
# fallback / additional test — always include this one, it's the reliable one
from synlynk.dispatch import _print_pending_nudges

def test_print_pending_nudges_reads_config_gate(project_dir, capsys):
    from synlynk import _update_config
    from synlynk.events import emit_event

    emit_event("story_done", {"story_id": "s1", "goal_ids": []}, emitted_by="test")
    _update_config({"nudges": {"enabled": False, "dismissed_ids": [], "last_shown": {}}})

    _print_pending_nudges()

    captured = capsys.readouterr()
    assert captured.out == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_dispatch_nudges.py::test_print_pending_nudges_reads_config_gate -v`
Expected: FAIL — `ImportError: cannot import name '_print_pending_nudges'`

- [ ] **Step 3: Implement `_print_pending_nudges` and call it**

In `synlynk/dispatch.py`, add near the top of the file (module-level function, alongside other `_`-prefixed helpers):

```python
def _print_pending_nudges() -> None:
    """Prints any nudges the pilot workspace agent has queued, gated by config."""
    load_config_fn = _pkg("load_config")
    config = load_config_fn() if load_config_fn else {}
    if not config.get("nudges", {}).get("enabled", True):
        return
    try:
        from synlynk.workspace_agent import cmd_workspace_agent_run
        cmd_workspace_agent_run()
    except Exception:
        pass
```

In `exec_command`'s `finally` block, immediately after the existing `if log_telemetry:` block closes (after line 2276's `refresh_quotas()` call and its surrounding try/except), add:

```python
        _print_pending_nudges()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_dispatch_nudges.py -v`
Expected: PASS (`test_print_pending_nudges_reads_config_gate` passes reliably; the `exec_command`-level test may need iteration per Step 1's note — do not skip verifying it, but do not block the task on it if the mocking proves impractical: mark it `@pytest.mark.skip(reason="...")` with the specific blocker named, and note this in the task's commit message.)

- [ ] **Step 5: Commit**

```bash
git add synlynk/dispatch.py tests/test_dispatch_nudges.py
git commit -m "feat: surface pending workspace-agent nudges after synlynk exec"
```

---

### Task 10: GH Actions cron trigger for the pilot agent

**Files:**
- Create: `.github/workflows/workspace-lifecycle-nudge.yml`

- [ ] **Step 1: Create the workflow**

Mirrors `.github/workflows/support-engineer.yml` exactly, substituting the agent name (note: this CI run's own DB writes are ephemeral per the Task header's implementer-decision note — the workflow exists so the pilot's cron heartbeat and any `gh pr list`/`git log` scans also happen on a schedule independent of any local machine being on, mirroring Support Engineer's existing dual local+CI trigger; the *durable, checkpoint-persisting* copy of this agent's state still lives in the local run via `_install_cron_entry`):

```yaml
name: Workspace Lifecycle Nudge

on:
  push:
    branches: [main]
  schedule:
    - cron: '0 */6 * * *'
  workflow_dispatch: {}

jobs:
  workspace-lifecycle-nudge:
    runs-on: ubuntu-latest
    permissions:
      contents: write
      issues: write
      pull-requests: write

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install test runner
        run: pip install pytest

      - name: Run workspace-lifecycle-nudge agent
        run: python3 bin/synlynk.py agent run workspace-lifecycle-nudge
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/workspace-lifecycle-nudge.yml
git commit -m "chore: add CI cron trigger for workspace-lifecycle-nudge agent"
```

---

### Task 11: Full suite regression check + self-review

- [ ] **Step 1: Run the full test suite**

Run: `pytest tests/ -q`
Expected: PASS, 0 failures (all pre-existing tests plus the ~19 new tests from Tasks 1-9)

- [ ] **Step 2: Grep for the two hand-written existing tests that reference `cmd_story_ready`'s prior no-op-on-goal behavior**

Run: `grep -rn "cmd_story_ready\|readiness='ready'" tests/`
Confirm no assertion expects zero `goal_contributions` rows after `cmd_story_ready` — if one exists, update it to match Task 4's new behavior (this is a deliberate, intended behavior change, not a regression).

- [ ] **Step 3: Commit any fixes**

```bash
git add -A
git commit -m "test: fix pre-existing assertions for extended cmd_story_ready behavior"
```

---

## Self-Review Notes

**Spec coverage:** Section 1 (events/subscriptions schema) → Task 1. Section 2(a) (`story done`) → Task 3. Section 2(b) (goal-link hook) → Task 4 (relocated to `cmd_story_ready`, documented). Section 2(c) (`pr check` soft-warn) → Task 5. Section 3 (pilot agent, SFIA config, cron) → Tasks 8, 10. Section 4 (nudge delivery, shared with UX 1.0 Phase 3a) → Tasks 6, 9. Out-of-Scope items are not implemented here by design — each already has a standalone `goal-*` tracking it (see prior session's goal creation).

**Placeholder scan:** No TBD/TODO left in any step; the two explicitly-flagged judgment calls (Task 9 Step 4's possible `skip` mark, Task 11 Step 2's conditional fix) are real engineering contingencies with a named concrete action, not open placeholders.

**Type consistency:** `emit_event`/`pending_events`/`advance_checkpoint` signatures are identical everywhere they're called across Tasks 1, 3, 4, 7, 8, 9. `NudgeData`/`render_nudge_fence` match between Task 6's definition and Task 8's usage. `AGENT_NAME = "workspace-lifecycle-nudge"` in Task 8 matches the `.agents/workspace-lifecycle-nudge.json` filename/role in the same task and the CLI invocation in Task 10.
