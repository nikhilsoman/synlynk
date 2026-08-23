# Ticket-Driven Approval Auto-Resume Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make a resolved `[APPROVAL]` GitHub ticket actually unblock the story `synlynk tpm sweep` parked for it, and stop the sweep from re-filing a duplicate ticket for a story that already has one open.

**Architecture:** A new `approval_tickets` table (`story_id`, `action`, `issue_url`, `status`) is the single source of truth linking a story+action pair to its ticket and resolution state. `check_authority()` in `synlynk/policy.py` is not touched — it stays pure and policy-only. All new statefulness lives in `synlynk/tpm_sweep.py` (which consults the table only when `check_authority()` already said `requires_approval=True`) and `synlynk/events.py` (which writes resolution state back to the table at the exact point it already detects a resolved ticket).

**Tech Stack:** Python 3 stdlib only, SQLite via `synlynk/__init__.py`'s `_get_db()`/`_DB_SCHEMA` convention, `gh` CLI subprocess calls (already wrapped by `approval_gate.py` and `events.py`), existing `pytest` suite.

---

### Task 1: `approval_tickets` table schema

**Files:**
- Modify: `synlynk/__init__.py:1051-1068` (the `_DB_SCHEMA` string, `events` table + index, immediately before `subscriptions`)
- Test: `tests/test_events.py`

No separate migration function is needed here — `_migrate_db()` (`synlynk/db.py:371-379`) runs `conn.executescript(_DB_SCHEMA)` on every DB connection open, and `_DB_SCHEMA` uses `CREATE TABLE IF NOT EXISTS` throughout. A migration function (like `_run_harness_rename_migration()`) is only needed when *renaming or altering* an existing table's columns — adding a brand-new table is handled automatically by the executescript re-run. Confirmed by reading `_migrate_db()` directly: `_run_harness_rename_migration(conn)` runs first (for renames only), then `conn.executescript(_DB_SCHEMA)` (for additive schema changes) runs unconditionally.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_events.py — add near the top, after the existing imports
def test_approval_tickets_table_exists(project_dir):
    import synlynk
    conn = synlynk._get_db()
    cols = {row[1] for row in conn.execute("PRAGMA table_info(approval_tickets)")}
    conn.close()
    assert cols == {
        "id", "story_id", "action", "issue_url", "status",
        "opened_at", "resolved_at", "consumed_at",
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_events.py::test_approval_tickets_table_exists -v`
Expected: FAIL — `cols == set()` (table does not exist)

- [ ] **Step 3: Add the table to `_DB_SCHEMA`**

In `synlynk/__init__.py`, the current text around line 1051-1068 reads:

```python
    created_at      TEXT NOT NULL,
    emitted_by      TEXT NOT NULL,
    parent_event_id INTEGER,
    authority_scope TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type, id);

CREATE TABLE IF NOT EXISTS subscriptions (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    harness_name         TEXT NOT NULL,
    event_type         TEXT NOT NULL,
    last_seen_event_id INTEGER NOT NULL DEFAULT 0,
    UNIQUE(harness_name, event_type)
);
```

Insert a new table between the `idx_events_type` index and the `subscriptions` table:

```python
    created_at      TEXT NOT NULL,
    emitted_by      TEXT NOT NULL,
    parent_event_id INTEGER,
    authority_scope TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type, id);

CREATE TABLE IF NOT EXISTS approval_tickets (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    story_id      TEXT NOT NULL,
    action        TEXT NOT NULL,
    issue_url     TEXT NOT NULL UNIQUE,
    status        TEXT NOT NULL DEFAULT 'open',
    opened_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at   TIMESTAMP,
    consumed_at   TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_approval_tickets_story_action ON approval_tickets(story_id, action, status);

CREATE TABLE IF NOT EXISTS subscriptions (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    harness_name         TEXT NOT NULL,
    event_type         TEXT NOT NULL,
    last_seen_event_id INTEGER NOT NULL DEFAULT 0,
    UNIQUE(harness_name, event_type)
);
```

`status` has no `CHECK` constraint (`open`/`resolved`/`consumed` are enforced in Python, matching how `daemon_jobs.status` and `stories.readiness` are handled elsewhere in this schema — no CHECK constraints anywhere in `_DB_SCHEMA`). The index supports the exact lookup Task 3 needs: "find a ticket for this `(story_id, action)` in a given `status`".

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_events.py::test_approval_tickets_table_exists -v`
Expected: PASS

- [ ] **Step 5: Run full suite to confirm no regression from the schema change**

Run: `pytest -q -x --timeout=600`
Expected: all pass (pre-existing baseline was green before this change)

- [ ] **Step 6: Commit**

```bash
git add synlynk/__init__.py tests/test_events.py
git commit -m "feat(db): add approval_tickets table for ticket-driven auto-resume"
```

- [ ] **Step 7: Open PR, dispatch non-authoring review, merge.** Do not proceed to Task 2 until merged — Task 2 assumes this table exists.

---

### Task 2: DB helper functions in `synlynk/db.py`

**Files:**
- Modify: `synlynk/db.py` (add new functions near `cmd_story_done`, which uses the identical open/execute/commit/close style these should match)
- Test: `tests/test_db.py`

The existing helper style in this file (see `cmd_story_draft`, `cmd_story_done` at `synlynk/db.py:2478-2515`) is: import `_get_db` locally inside the function, open a connection, run the query, `commit()`, `close()`, return early on missing rows. Match this exactly — no context managers, no new connection-handling pattern.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_db.py — add at the end of the file
def test_find_ticket_returns_none_when_absent(project_dir):
    from synlynk.db import _find_ticket
    assert _find_ticket("story-x", "task_dispatch:implement", "open") is None


def test_insert_ticket_then_find_by_status(project_dir):
    from synlynk.db import _find_ticket, _insert_ticket
    _insert_ticket("story-x", "task_dispatch:implement", "https://github.com/o/r/issues/1")
    ticket = _find_ticket("story-x", "task_dispatch:implement", "open")
    assert ticket is not None
    assert ticket["issue_url"] == "https://github.com/o/r/issues/1"
    assert ticket["status"] == "open"
    # wrong status returns nothing
    assert _find_ticket("story-x", "task_dispatch:implement", "resolved") is None


def test_insert_ticket_duplicate_issue_url_raises(project_dir):
    import sqlite3
    from synlynk.db import _insert_ticket
    _insert_ticket("story-x", "task_dispatch:implement", "https://github.com/o/r/issues/2")
    with __import__("pytest").raises(sqlite3.IntegrityError):
        _insert_ticket("story-y", "task_dispatch:implement", "https://github.com/o/r/issues/2")


def test_mark_ticket_consumed_updates_status_and_timestamp(project_dir):
    from synlynk.db import _find_ticket, _insert_ticket, _mark_ticket_consumed
    _insert_ticket("story-x", "task_dispatch:implement", "https://github.com/o/r/issues/3")
    ticket = _find_ticket("story-x", "task_dispatch:implement", "open")
    _mark_ticket_consumed(ticket["id"])
    assert _find_ticket("story-x", "task_dispatch:implement", "open") is None
    assert _find_ticket("story-x", "task_dispatch:implement", "consumed") is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_db.py::test_find_ticket_returns_none_when_absent -v`
Expected: FAIL with `ImportError: cannot import name '_find_ticket'`

- [ ] **Step 3: Implement the three helpers in `synlynk/db.py`**

Add immediately after `cmd_story_done` (after the line `print(f"  {_GREEN}✓{_RESET} Story {story_id} marked done")`, before `def cmd_goal_create`):

```python
def _find_ticket(story_id: str, action: str, status: str) -> dict | None:
    """Returns the approval_tickets row matching (story_id, action, status), or None."""
    from synlynk import _get_db
    conn = _get_db()
    row = conn.execute(
        "SELECT id, story_id, action, issue_url, status, opened_at, resolved_at, consumed_at "
        "FROM approval_tickets WHERE story_id=? AND action=? AND status=? "
        "ORDER BY id DESC LIMIT 1",
        (story_id, action, status),
    ).fetchone()
    conn.close()
    if not row:
        return None
    return {
        "id": row[0], "story_id": row[1], "action": row[2], "issue_url": row[3],
        "status": row[4], "opened_at": row[5], "resolved_at": row[6], "consumed_at": row[7],
    }


def _insert_ticket(story_id: str, action: str, issue_url: str) -> None:
    """Records a newly filed approval ticket as 'open'."""
    from synlynk import _get_db
    conn = _get_db()
    conn.execute(
        "INSERT INTO approval_tickets (story_id, action, issue_url, status) "
        "VALUES (?, ?, ?, 'open')",
        (story_id, action, issue_url),
    )
    conn.commit()
    conn.close()


def _mark_ticket_consumed(ticket_id: int) -> None:
    """Marks a resolved ticket as consumed so it cannot unblock a story twice."""
    from synlynk import _get_db
    conn = _get_db()
    conn.execute(
        "UPDATE approval_tickets SET status='consumed', consumed_at=CURRENT_TIMESTAMP WHERE id=?",
        (ticket_id,),
    )
    conn.commit()
    conn.close()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_db.py::test_find_ticket_returns_none_when_absent tests/test_db.py::test_insert_ticket_then_find_by_status tests/test_db.py::test_insert_ticket_duplicate_issue_url_raises tests/test_db.py::test_mark_ticket_consumed_updates_status_and_timestamp -v`
Expected: 4 passed

- [ ] **Step 5: Run full suite**

Run: `pytest -q -x --timeout=600`
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add synlynk/db.py tests/test_db.py
git commit -m "feat(db): add approval_tickets find/insert/consume helpers"
```

- [ ] **Step 7: Open PR, dispatch non-authoring review, merge.** Do not proceed to Task 3 until merged.

---

### Task 3: Wire ticket-check logic into `run_sweep_pass()`

**Files:**
- Modify: `synlynk/tpm_sweep.py:32-76` (the whole file — shown in full below)
- Test: `tests/test_tpm_sweep.py`

Current full file content (read directly this session, not paraphrased):

```python
"""Run one policy-gated autonomous TPM sweep pass."""
from __future__ import annotations

import os
from typing import Dict

from synlynk.approval_gate import raise_approval_ticket
from synlynk.dispatch import dispatch_agent
from synlynk.events import emit_awaiting_approval
from synlynk.policy import check_authority


def _ready_stories() -> list:
    from synlynk.db import _get_db

    conn = _get_db()
    try:
        rows = conn.execute(
            "SELECT story_id, title, role FROM stories WHERE readiness='ready' "
            "AND NOT EXISTS (SELECT 1 FROM daemon_jobs dj "
            "WHERE dj.story_id=stories.story_id "
            "AND dj.status IN ('queued','running','done'))"
        ).fetchall()
        return [
            {"story_id": row[0], "title": row[1], "role": row[2] or "dev"}
            for row in rows
        ]
    finally:
        conn.close()


def run_sweep_pass(assignee: str = "nikhilsoman") -> Dict[str, int]:
    """Dispatch each ready, undispatched story after checking policy authority."""
    summary = {"advanced": 0, "parked": 0, "failed": 0}
    repo_path = os.getcwd()

    for story in _ready_stories():
        authority = check_authority(
            "task_dispatch:implement",
            role=story["role"],
            repo_path=repo_path,
        )
        if not authority.allowed:
            summary["failed"] += 1
            continue

        if authority.requires_approval:
            emit_awaiting_approval(
                story["story_id"],
                "task_dispatch:implement",
                authority.reason,
            )
            raise_approval_ticket(
                story_id=story["story_id"],
                action="task_dispatch:implement",
                reason=authority.reason,
                assignee=assignee,
                context=f"Story: {story['title']}",
            )
            summary["parked"] += 1
            continue

        try:
            dispatch_agent(
                "codex",
                story["title"],
                story_id=story["story_id"],
                task_type="implement",
                context_mode="full",
                role=story["role"],
            )
            summary["advanced"] += 1
        except Exception:
            summary["failed"] += 1

    return summary
```

(`_ready_stories()`'s `'done'` exclusion already reflects PR #1135/#1133 — no change needed there.)

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_tpm_sweep.py`, after the existing `test_run_sweep_pass_parks_story_requiring_approval`:

```python
def test_run_sweep_pass_reuses_open_ticket_without_refiling(isolated_db, project_dir):
    from synlynk.db import _find_ticket
    story_id = cmd_story_create(title="release story", story_id="story-3")
    cmd_story_ready(story_id)
    with patch("synlynk.tpm_sweep.check_authority") as mock_auth, \
            patch("synlynk.tpm_sweep.raise_approval_ticket") as mock_ticket, \
            patch("synlynk.tpm_sweep.emit_awaiting_approval") as mock_event:
        mock_auth.return_value = MagicMock(
            allowed=True, requires_approval=True, reason="named_release"
        )
        mock_ticket.return_value = "https://github.com/x/y/issues/5"
        # First pass: files a ticket
        summary1 = run_sweep_pass()
        # Second pass: same story, same open ticket already recorded
        summary2 = run_sweep_pass()
    assert summary1["parked"] == 1
    assert summary2["parked"] == 1
    assert mock_ticket.call_count == 1  # not re-filed on the second pass
    ticket = _find_ticket(story_id, "task_dispatch:implement", "open")
    assert ticket is not None


def test_run_sweep_pass_dispatches_and_consumes_resolved_ticket(isolated_db, project_dir):
    from synlynk.db import _find_ticket, _insert_ticket
    story_id = cmd_story_create(title="release story", story_id="story-4")
    cmd_story_ready(story_id)
    _insert_ticket(story_id, "task_dispatch:implement", "https://github.com/x/y/issues/6")
    conn = synlynk._get_db()
    conn.execute(
        "UPDATE approval_tickets SET status='resolved' WHERE story_id=?", (story_id,)
    )
    conn.commit()
    conn.close()
    with patch("synlynk.tpm_sweep.check_authority") as mock_auth, \
            patch("synlynk.tpm_sweep.raise_approval_ticket") as mock_ticket, \
            patch("synlynk.tpm_sweep.dispatch_agent") as mock_dispatch:
        mock_auth.return_value = MagicMock(
            allowed=True, requires_approval=True, reason="named_release"
        )
        mock_dispatch.return_value = {"id": "job-2", "agent": "codex"}
        summary = run_sweep_pass()
    assert summary["advanced"] == 1
    assert summary["parked"] == 0
    mock_ticket.assert_not_called()
    assert _find_ticket(story_id, "task_dispatch:implement", "resolved") is None
    assert _find_ticket(story_id, "task_dispatch:implement", "consumed") is not None
```

`tests/test_tpm_sweep.py` needs `import synlynk` added at the top (it currently imports `cmd_story_create`/`cmd_story_ready` and `run_sweep_pass` directly but not the `synlynk` package itself, which the new second test needs for `synlynk._get_db()` — check the existing `_story_with_job` helper at the bottom of the file, which already does `conn = synlynk._get_db()`, confirming `import synlynk` is already present in the file).

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_tpm_sweep.py::test_run_sweep_pass_reuses_open_ticket_without_refiling tests/test_tpm_sweep.py::test_run_sweep_pass_dispatches_and_consumes_resolved_ticket -v`
Expected: FAIL — `mock_ticket.call_count == 1` fails (currently called twice, once per pass) and the resolved/consumed test fails because nothing marks it consumed or dispatches around it

- [ ] **Step 3: Implement the three-branch ticket-check logic**

Replace the `if authority.requires_approval:` block in `synlynk/tpm_sweep.py` (and add the needed import) as follows.

Change the import block at the top from:

```python
from synlynk.approval_gate import raise_approval_ticket
from synlynk.dispatch import dispatch_agent
from synlynk.events import emit_awaiting_approval
from synlynk.policy import check_authority
```

to:

```python
from synlynk.approval_gate import raise_approval_ticket
from synlynk.db import _find_ticket, _insert_ticket, _mark_ticket_consumed
from synlynk.dispatch import dispatch_agent
from synlynk.events import emit_awaiting_approval
from synlynk.policy import check_authority
```

Replace this block in `run_sweep_pass()`:

```python
        if authority.requires_approval:
            emit_awaiting_approval(
                story["story_id"],
                "task_dispatch:implement",
                authority.reason,
            )
            raise_approval_ticket(
                story_id=story["story_id"],
                action="task_dispatch:implement",
                reason=authority.reason,
                assignee=assignee,
                context=f"Story: {story['title']}",
            )
            summary["parked"] += 1
            continue
```

with:

```python
        if authority.requires_approval:
            action = "task_dispatch:implement"
            resolved_ticket = _find_ticket(story["story_id"], action, "resolved")
            if resolved_ticket:
                _mark_ticket_consumed(resolved_ticket["id"])
                # fall through to dispatch below, same as an allowed authority
            else:
                if not _find_ticket(story["story_id"], action, "open"):
                    emit_awaiting_approval(
                        story["story_id"],
                        action,
                        authority.reason,
                    )
                    issue_url = raise_approval_ticket(
                        story_id=story["story_id"],
                        action=action,
                        reason=authority.reason,
                        assignee=assignee,
                        context=f"Story: {story['title']}",
                    )
                    if issue_url:
                        _insert_ticket(story["story_id"], action, issue_url)
                summary["parked"] += 1
                continue
```

The `try`/`except` `dispatch_agent(...)` block immediately below is unchanged — the resolved-ticket branch simply falls through into it, exactly like the `authority.allowed` (no approval needed) path already does.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_tpm_sweep.py -v`
Expected: all pass (6 tests: the original 4 plus the 2 new ones)

- [ ] **Step 5: Run full suite**

Run: `pytest -q -x --timeout=600`
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add synlynk/tpm_sweep.py tests/test_tpm_sweep.py
git commit -m "feat(tpm_sweep): consume resolved approval tickets, skip re-filing open ones"
```

- [ ] **Step 7: Open PR, dispatch non-authoring review, merge.** Do not proceed to Task 4 until merged.

---

### Task 4: Write resolution state back in `_scan_approval_tickets()`

**Files:**
- Modify: `synlynk/events.py:156-202`
- Test: `tests/test_events.py`

Current full function (read directly this session):

```python
def _scan_approval_tickets() -> int | None:
    """Poll approval issues and emit approval_resolved for newly resolved tickets.

    An issue is resolved when it is closed or has a comment beginning with
    ``approve``. Returns the id of the last event emitted, or None if none were
    emitted.
    """
    import subprocess

    try:
        result = subprocess.run(
            [
                "gh",
                "issue",
                "list",
                "--search",
                "[APPROVAL] in:title",
                "--state",
                "all",
                "--json",
                "url,state,comments",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        issues = json.loads(result.stdout) if result.returncode == 0 else []
    except (FileNotFoundError, json.JSONDecodeError, StopIteration):
        issues = []

    already = _existing_approval_resolved_keys()
    last_event_id = None
    for issue in issues:
        if issue["url"] in already:
            continue
        resolved = issue["state"] == "CLOSED" or any(
            comment.get("body", "").strip().lower().startswith("approve")
            for comment in issue.get("comments", [])
        )
        if resolved:
            last_event_id = emit_event(
                "approval_resolved",
                {"issue_url": issue["url"]},
                emitted_by="_scan_approval_tickets",
            )
            already.add(issue["url"])
    return last_event_id
```

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_events.py`:

```python
def test_scan_approval_tickets_marks_row_resolved_on_issue_closed(project_dir):
    from unittest.mock import patch, MagicMock
    from synlynk.db import _find_ticket, _insert_ticket
    from synlynk.events import _scan_approval_tickets

    _insert_ticket("story-a", "task_dispatch:implement", "https://github.com/o/r/issues/10")
    gh_stdout = json.dumps([
        {"url": "https://github.com/o/r/issues/10", "state": "CLOSED", "comments": []}
    ])
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=gh_stdout)
        _scan_approval_tickets()

    ticket = _find_ticket("story-a", "task_dispatch:implement", "resolved")
    assert ticket is not None
    assert ticket["resolved_at"] is not None


def test_scan_approval_tickets_marks_row_resolved_on_approve_comment(project_dir):
    from unittest.mock import patch, MagicMock
    from synlynk.db import _find_ticket, _insert_ticket
    from synlynk.events import _scan_approval_tickets

    _insert_ticket("story-b", "task_dispatch:implement", "https://github.com/o/r/issues/11")
    gh_stdout = json.dumps([{
        "url": "https://github.com/o/r/issues/11",
        "state": "OPEN",
        "comments": [{"body": "approve, go ahead"}],
    }])
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=gh_stdout)
        _scan_approval_tickets()

    assert _find_ticket("story-b", "task_dispatch:implement", "resolved") is not None


def test_scan_approval_tickets_no_op_on_rescan_of_already_resolved(project_dir):
    from unittest.mock import patch, MagicMock
    from synlynk.db import _find_ticket, _insert_ticket
    from synlynk.events import _scan_approval_tickets

    _insert_ticket("story-c", "task_dispatch:implement", "https://github.com/o/r/issues/12")
    gh_stdout = json.dumps([
        {"url": "https://github.com/o/r/issues/12", "state": "CLOSED", "comments": []}
    ])
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=gh_stdout)
        _scan_approval_tickets()  # first scan resolves it
        first_resolved_at = _find_ticket("story-c", "task_dispatch:implement", "resolved")["resolved_at"]
        _scan_approval_tickets()  # second scan should not touch it again

    ticket = _find_ticket("story-c", "task_dispatch:implement", "resolved")
    assert ticket is not None
    assert ticket["resolved_at"] == first_resolved_at
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_events.py::test_scan_approval_tickets_marks_row_resolved_on_issue_closed -v`
Expected: FAIL — `_find_ticket(...)` returns `None` (nothing writes to `approval_tickets` yet)

- [ ] **Step 3: Add the table write at the point of resolution detection**

In `synlynk/events.py`, change the `if resolved:` block inside `_scan_approval_tickets()` from:

```python
        if resolved:
            last_event_id = emit_event(
                "approval_resolved",
                {"issue_url": issue["url"]},
                emitted_by="_scan_approval_tickets",
            )
            already.add(issue["url"])
```

to:

```python
        if resolved:
            from synlynk import _get_db
            conn = _get_db()
            conn.execute(
                "UPDATE approval_tickets SET status='resolved', resolved_at=CURRENT_TIMESTAMP "
                "WHERE issue_url=? AND status='open'",
                (issue["url"],),
            )
            conn.commit()
            conn.close()
            last_event_id = emit_event(
                "approval_resolved",
                {"issue_url": issue["url"]},
                emitted_by="_scan_approval_tickets",
            )
            already.add(issue["url"])
```

The `AND status='open'` guard makes the `UPDATE` itself idempotent (a rescan of an already-`resolved` row is a no-op), on top of the existing `_existing_approval_resolved_keys()` de-dup that already prevents `already.add(issue["url"])` entries from reaching this branch twice within realistic use — the `WHERE status='open'` clause is the one that matters for the third test above, since that test calls `_scan_approval_tickets()` twice directly and the second call would otherwise re-run the `UPDATE` (harmlessly, but the test should assert it doesn't need to for correctness — the SQL-level guard is the actual protection, not test iteration count).

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_events.py -v -k approval_tickets`
Expected: 3 passed (plus the Task 1 `test_approval_tickets_table_exists`, so 4 with `-k approval` if run together — run `-k approval` instead of `-k approval_tickets` to catch all four)

- [ ] **Step 5: Run full suite**

Run: `pytest -q -x --timeout=600`
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add synlynk/events.py tests/test_events.py
git commit -m "feat(events): write approval_tickets resolution state on ticket scan"
```

- [ ] **Step 7: Open PR, dispatch non-authoring review, merge.** Do not proceed to Task 5 until merged — Task 5 is Claude-direct dogfood verification and needs all of Tasks 1-4 merged to `main` first.

---

### Task 5: Live dogfood verification (Claude-direct, not dispatched)

Per project CLAUDE.md, this is PM/deploy work — run these steps directly, do not dispatch to Codex/Grok/Agy. This mirrors the v0.16.0 CHANGELOG's Task 13 dogfood pattern exactly: a temporary, documented, fully-reverted test-only policy rule, with every claim cross-checked directly rather than trusted from `tpm sweep`'s own printed summary.

- [ ] **Step 1: Pull `main` after Tasks 1-4 have merged, confirm clean baseline**

```bash
cd /Users/nikhilsoman/dev/synlynk
git checkout main -q && git pull -q
pytest -q -x --timeout=600
```
Expected: all pass.

- [ ] **Step 2: Add a temporary test-only approval rule for `task_dispatch:` actions**

Confirmed by reading `synlynk/policy.py` directly: `_matches_approval_rule()` only ever
returns non-`None` for `action == "release_cut"` (rule `named_release`) or
`action in ("roadmap_edit", "goal_create")` (rule `roadmap_authority_change`) —
`task_dispatch:*` actions have no matching branch at all, and the
`security_sensitive_paths:` branch explicitly `continue`s past dispatch actions. This
matches the v0.16.0 CHANGELOG's own note: *"`task_dispatch:` has no default rule that
can trip `requires_approval`."* A `.synlynk/policy.json` data-only edit cannot produce
`requires_approval=True` for a `task_dispatch:implement` action — the matcher itself has
no branch for it. The v0.16.0 dogfood's pause path must have used a temporary code edit
to `_matches_approval_rule()`, not a policy-data-only change; do the same here.

In `synlynk/policy.py`, temporarily add a branch to `_matches_approval_rule()`:

```python
def _matches_approval_rule(action: str, policy: Dict[str, Any]) -> Optional[str]:
    for rule in policy.get("approval_required_for", []):
        if rule == "named_release" and action == "release_cut":
            return rule
        if rule == "roadmap_authority_change" and action in ("roadmap_edit", "goal_create"):
            return rule
        if rule == "task_dispatch_demo" and action == "task_dispatch:implement":  # TEMPORARY — dogfood only, revert in Step 7
            return rule
        if rule.startswith("security_sensitive_paths:") and action.startswith("task_dispatch:"):
            continue  # path-based rules are checked by callers that know the changed files, not here
    return None
```

Then add `"task_dispatch_demo"` to `.synlynk/policy.json`'s `approval_required_for` list
(create the key if absent — it currently has no such list in this repo's overrides, per
`python3 -m json.tool .synlynk/policy.json`, so it inherits an empty/absent list from
workspace defaults). Commit both changes together with a message stating they are
temporary and will be reverted at the end of this task (Step 7).

- [ ] **Step 3: Create a demo story and run the sweep to park it**

```bash
python3 -m synlynk story create --title "ticket-auto-resume dogfood demo" --story-id story-autoresume-demo
python3 -m synlynk story ready story-autoresume-demo
python3 -m synlynk tpm sweep
```
Expected output: the story is parked (not dispatched). Confirm directly:
```bash
python3 -c "
from synlynk.db import _find_ticket
t = _find_ticket('story-autoresume-demo', 'task_dispatch:implement', 'open')
print(t)
"
```
Expected: a ticket row with `status='open'` and a real `issue_url`.

- [ ] **Step 4: Run the sweep again without resolving — confirm no duplicate ticket**

```bash
python3 -m synlynk tpm sweep
gh issue list --search "[APPROVAL] in:title story-autoresume-demo" --state all --json number,title
```
Expected: exactly one `[APPROVAL] task_dispatch:implement — story-autoresume-demo` issue, not two.

- [ ] **Step 5: Resolve the ticket and confirm `approval_resolved` fires**

```bash
gh issue comment <issue-number-from-step-3> --body "approve"
python3 -c "
from synlynk.events import scan_local_events
scan_local_events('dogfood-verification')
"
python3 -m synlynk events tail --type approval_resolved
```
Expected: a fresh `approval_resolved` event referencing the demo issue's URL.

- [ ] **Step 6: Run the sweep a third time — confirm it dispatches instead of re-parking**

```bash
python3 -m synlynk tpm sweep
python3 -m synlynk jobs --all | grep story-autoresume-demo
```
Expected: a `daemon_jobs` row for `story-autoresume-demo` in `queued`/`running`, not another park. Confirm the ticket was consumed, not left resolved:
```bash
python3 -c "
from synlynk.db import _find_ticket
print(_find_ticket('story-autoresume-demo', 'task_dispatch:implement', 'consumed'))
"
```
Expected: a row with `status='consumed'` and a non-null `consumed_at`.

- [ ] **Step 7: Revert the temporary policy rule/code and clean up the demo story/job/worktree**

```bash
git diff .synlynk/policy.json synlynk/policy.py  # confirm only the Step 2 temporary changes are present
git checkout .synlynk/policy.json synlynk/policy.py
pytest -q -x --timeout=600  # confirm the revert leaves a clean, still-passing baseline
python3 -m synlynk story draft story-autoresume-demo  # park it out of readiness
```
Follow the Worktree Hygiene Protocol for any worktree/branch the dispatched demo job created (`git worktree list --porcelain`, confirm via job status/PR state before removing).

- [ ] **Step 8: Write up the dogfood result in the CHANGELOG's next release section (or a new one, per Named Release Policy) and in `project-docs/devlogs/nikhilsoman.md`**

Follow the same evidence-citing style as the v0.16.0 CHANGELOG entry — cite the specific issue number, event id, and job id observed in Steps 3-6, not a paraphrase of "it worked."
