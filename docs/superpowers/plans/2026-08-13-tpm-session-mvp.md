# TPM/Session MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Execution routing (this repo's CLAUDE.md):** Claude (PM/reviewer role) never implements. Every task below is a self-contained prompt for `python3 -m synlynk dispatch <agent> --task "..." --force-agent --context-mode full --issue <N> --base main`. Do not open a Claude subagent to write code for this plan.

**Goal:** Give synlynk a durable "work envelope" — sessions, linked to goals and devlog entries, inherited through dispatch and cost tracking, with a checkpoint command and a first TPM nudge — so meaningful work stops evaporating into unattributed job rows.

**Architecture:** One new `sessions` table (SQLite, `synlynk/__init__.py` schema block) is the anchor. A file marker at `.synlynk/active_session.json` tracks "which session is open in this working directory right now" (mirrors the existing `.synlynk/config.json`/`.synlynk/telemetry.json` file-marker convention — no new global state mechanism). `session_id` threads through `dispatch_agent()` → `daemon_jobs.session_id` → `_insert_cost_row()` → `cost_entries.session_id`, the same way `job_id` already threads `context_mode` in the existing `_insert_cost_row` inheritance branch (`synlynk/db.py:952-960`). `devlog_entries` gains `session_id`/`goal_id` columns so `cmd_devlog_append()` can link an entry back to the session and goal it happened under. `session checkpoint` is a new, separate command from the existing GOVERNS `advance_checkpoint()` (per-agent event-subscription pointer, `synlynk/events.py:122`) — to avoid the naming collision, the session-level command is implemented as `cmd_session_checkpoint()` and its CLI verb is `synlynk session checkpoint`, never touching the `subscriptions` table.

**Tech Stack:** Python 3 stdlib, `sqlite3`, existing `synlynk/db.py` self-healing `ALTER TABLE` migration pattern, `argparse` subparsers (`synlynk/cli.py`).

**Scope:** This is the Week 2 slice ("08-17 → 08-30: TPM/session MVP") of the adopted 7-week arc in `docs/strategy/road-to-autonomous-ops.md`, per the approved `docs/superpowers/specs/2026-08-11-autonomous-ops-program-design.md`. It does not touch GitHub Issue/PR mirroring (Week 3), multi-project dogfood (Week 4), or the public preview surface (Week 5) — those need their own plans when their week arrives.

---

## Autonomous execution model (minimal-permission design)

Per explicit instruction: this plan is designed so Nikhil's only required action is **approving this plan document once** (the repo's own Design → Plan → Build gate — `docs/superpowers/plans/` commit — cannot be skipped; it is not this plan's choice to remove). After that:

- Every task is dispatched via `synlynk dispatch <agent> --task "..." --force-agent --context-mode full --issue <N> --base main` by the PM (Claude), never implemented inline.
- Every task's exit criterion includes: tests pass, PR opened, **non-authoring reviewer runs `synlynk pr check` and posts a COMMENT-review approval** (per this repo's GitHub-identity caveat — `gh pr review --approve` fails same-identity, so the sanctioned fallback is a formal COMMENT review with an explicit checklist), **and the reviewer merges**. Nikhil is not in this loop.
- Tasks are ordered as a **strict merge-order stack** (each depends on the previous task's *merged* code, since they touch overlapping files: `synlynk/__init__.py`, `synlynk/db.py`, `synlynk/dispatch.py`, `synlynk/cli.py`). Within that forced sequencing, **harness assignment is rotated** (Codex → Grok → Agy → Codex → Grok → Agy → Codex) so no single agent's quota window absorbs the whole stack.
- No task requires a GitHub write beyond opening its own PR and its own reviewer's PR review/merge — no `--requires-gh-write` routing decision beyond the standard PR flow already covered by existing dispatch defaults.
- Task 7 (full regression run) is the only gate before the whole slice is considered "done" — it does not require a new PR by itself; it is folded into Task 6's PR as its final step.
- **The only thing that comes back to Nikhil**: a single PM summary after Task 6 merges, reporting what shipped, what the first TPM nudge surfaced, and any gaps found — matching "expect every gap to be identified" below.

## Known gaps this slice deliberately does NOT close (surfaced now, not discovered later)

1. **No automatic session-open on dispatch.** `dispatch_agent()` reads `session_id` from `.synlynk/active_session.json` if present, but nothing forces a session to be open before dispatching. A job dispatched with no open session gets `session_id=NULL` and is silently unattributed — Task 6's nudge is designed specifically to surface exactly this gap in `synlynk session status`, but does not prevent it. Closing that gap (a hard pre-dispatch gate) is an explicit Week-3+ candidate, not in scope here.
2. **No cross-session GOVERNS event for session lifecycle.** `session open`/`close` do not emit `events` rows in this slice (only `cron_heartbeat`/`pr_merged`/`review_submitted`/`spec_or_plan_committed` exist as event types today). Adding `session_opened`/`session_closed` events is straightforward but deferred to avoid scope creep on the `events` schema in the same slice that adds `sessions` — flagged for Week 3.
3. **`session checkpoint` reconciliation is read-only/reporting, not corrective.** It reports jobs/costs/devlog entries since the last checkpoint; it does not auto-attribute or auto-fix orphaned rows. That is intentionally out of scope — the base document's Week 3 "GitHub Issue/PR mirror + `external_untriaged` disposition" work is the natural home for corrective reconciliation.
4. **Single active session per working directory, no nesting.** `.synlynk/active_session.json` holds exactly one session id. Concurrent dispatch across two terminals/worktrees pointed at the same repo will race on this file. Acceptable for the MVP (single-operator usage matches current reality); multi-worktree session isolation is a Week 4 dogfood-arc concern.

---

## File Structure

- Modify: `synlynk/__init__.py` — add `sessions` table to the main schema `executescript` block (next to `goals`/`goal_contributions`/`events`).
- Modify: `synlynk/db.py` — add `_ensure_sessions_devlog_columns()` self-heal migration, `cmd_session_open()`, `cmd_session_status()`, `cmd_session_close()`, `cmd_session_checkpoint()`, extend `cmd_devlog_append()` with `session_id`/`goal_id` params, extend `_insert_cost_row()` with `session_id` param + inheritance.
- Modify: `synlynk/dispatch.py` — add `_ensure_daemon_job_session_column()`, extend `dispatch_agent()` with `session_id` param (default: read from active-session marker), thread it into both `daemon_jobs` INSERT/UPDATE branches.
- Modify: `synlynk/cli.py` — add `session` subparser (`open`/`status`/`checkpoint`/`close`), wire to `synlynk/db.py` commands, thread `--session` override flag into the existing `dispatch` subparser.
- Create: `synlynk/session.py` — the active-session marker file read/write helpers (`_active_session_path()`, `_read_active_session()`, `_write_active_session()`, `_clear_active_session()`), kept in their own module so `db.py`/`dispatch.py`/`cli.py` all import from one place instead of duplicating marker-file logic.
- Test: `tests/test_session.py` — new file, covers `synlynk/session.py` marker helpers and `cmd_session_*` commands.
- Test: `tests/test_dispatch_session_threading.py` — new file, covers `session_id` inheritance through `dispatch_agent()` → `daemon_jobs` → `_insert_cost_row()` → `cost_entries`.

---

### Task 1: `sessions` table schema + active-session marker module

**Agent:** Codex (schema + CLI plumbing)
**Files:**
- Modify: `synlynk/__init__.py:960` (insert after `goal_contributions` table, before `events` table)
- Create: `synlynk/session.py`
- Test: `tests/test_session.py`

- [ ] **Step 1: Write the failing test for the marker helpers**

```python
# tests/test_session.py
import json
import os

import pytest


def test_write_and_read_active_session(tmp_path, monkeypatch):
    from synlynk.session import _write_active_session, _read_active_session, _active_session_path

    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)

    _write_active_session("session-abc12345")

    assert os.path.exists(_active_session_path())
    assert _read_active_session() == "session-abc12345"


def test_read_active_session_returns_none_when_absent(tmp_path, monkeypatch):
    from synlynk.session import _read_active_session

    monkeypatch.chdir(tmp_path)
    assert _read_active_session() is None


def test_clear_active_session_removes_marker(tmp_path, monkeypatch):
    from synlynk.session import _write_active_session, _read_active_session, _clear_active_session

    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    _write_active_session("session-abc12345")
    _clear_active_session()

    assert _read_active_session() is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_session.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.session'`

- [ ] **Step 3: Add the `sessions` table to the schema**

Edit `synlynk/__init__.py`, immediately after the `goal_contributions` table block (currently ending at line 965 with the closing `);`) and before `CREATE TABLE IF NOT EXISTS events (`:

```sql
CREATE TABLE IF NOT EXISTS sessions (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id       TEXT NOT NULL UNIQUE,
    title            TEXT NOT NULL,
    goal_id          TEXT REFERENCES goals(goal_id),
    status           TEXT NOT NULL DEFAULT 'open',
    disposition      TEXT,
    opened_at        TEXT NOT NULL,
    closed_at        TEXT,
    last_checkpoint_at TEXT,
    closing_summary  TEXT
);
CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status);
```

- [ ] **Step 4: Write `synlynk/session.py`**

```python
"""Active-session marker file: which session is open in this working directory.

Mirrors the existing .synlynk/config.json / .synlynk/telemetry.json file-marker
convention rather than introducing a new state mechanism. Single active session
per working directory — concurrent dispatch across worktrees races on this file
(documented gap, see plan header).
"""

import json
import os


def _active_session_path() -> str:
    return os.path.join(".synlynk", "active_session.json")


def _read_active_session() -> str:
    """Returns the open session_id, or None if no session is active."""
    path = _active_session_path()
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None
    return data.get("session_id")


def _write_active_session(session_id: str) -> None:
    os.makedirs(".synlynk", exist_ok=True)
    with open(_active_session_path(), "w") as f:
        json.dump({"session_id": session_id}, f)


def _clear_active_session() -> None:
    path = _active_session_path()
    if os.path.exists(path):
        os.remove(path)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python3 -m pytest tests/test_session.py -v`
Expected: PASS (3 passed)

- [ ] **Step 6: Run full suite to confirm no regression from the schema change**

Run: `python3 -m pytest -q`
Expected: all tests pass (the `executescript` addition is additive/idempotent — `CREATE TABLE IF NOT EXISTS` — so existing DBs and fixtures are unaffected)

- [ ] **Step 7: Commit**

```bash
git add synlynk/__init__.py synlynk/session.py tests/test_session.py
git commit -m "feat: add sessions table + active-session marker module"
```

- [ ] **Step 8: Open PR, dispatch non-authoring review, merge**

Open the PR from the dispatch worktree (`gh pr create` inside the dispatch flow). Assign a **non-authoring** reviewer harness to run `synlynk pr check` from that PR's own checked-out branch, post a COMMENT-review approval per the sanctioned fallback, then merge. Do not proceed to Task 2 until this PR is merged to `main` — Task 2 edits `synlynk/__init__.py` and `synlynk/db.py` and will conflict on an unmerged base.

---

### Task 2: `session open` / `session status` / `session close` commands

**Agent:** Grok (infra/CLI)
**Depends on:** Task 1 merged.
**Files:**
- Modify: `synlynk/db.py` (add near `cmd_goal_create`/`cmd_goal_list`, after line 2126)
- Modify: `synlynk/cli.py` (add `session` subparser + dispatch, mirroring the `identity`/`events` subparser pattern at `synlynk/cli.py:414-438` and `synlynk/cli.py:1399-1404`)
- Test: extend `tests/test_session.py`

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_session.py
import sqlite3


def test_cmd_session_open_creates_row_and_marker(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SYNLYNK_DB_PATH", str(tmp_path / "state.db"))
    from synlynk.db import cmd_session_open
    from synlynk.session import _read_active_session
    from synlynk import _get_db

    session_id = cmd_session_open("Investigate flaky Codex GH-write routing")

    assert session_id.startswith("session-")
    assert _read_active_session() == session_id

    conn = _get_db()
    row = conn.execute(
        "SELECT title, status FROM sessions WHERE session_id=?", (session_id,)
    ).fetchone()
    conn.close()
    assert row == ("Investigate flaky Codex GH-write routing", "open")


def test_cmd_session_close_sets_disposition_and_clears_marker(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SYNLYNK_DB_PATH", str(tmp_path / "state.db"))
    from synlynk.db import cmd_session_open, cmd_session_close
    from synlynk.session import _read_active_session
    from synlynk import _get_db

    session_id = cmd_session_open("Ship v0.14.0")
    cmd_session_close(disposition="goal_progress", summary="Shipped GOVERNS event extension")

    assert _read_active_session() is None
    conn = _get_db()
    row = conn.execute(
        "SELECT status, disposition, closing_summary FROM sessions WHERE session_id=?",
        (session_id,),
    ).fetchone()
    conn.close()
    assert row == ("closed", "goal_progress", "Shipped GOVERNS event extension")


def test_cmd_session_close_rejects_invalid_disposition(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SYNLYNK_DB_PATH", str(tmp_path / "state.db"))
    from synlynk.db import cmd_session_open, cmd_session_close

    cmd_session_open("Explore quota routing options")
    with pytest.raises(ValueError):
        cmd_session_close(disposition="not_a_real_disposition")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_session.py -k "cmd_session" -v`
Expected: FAIL with `ImportError: cannot import name 'cmd_session_open' from 'synlynk.db'`

- [ ] **Step 3: Implement the commands in `synlynk/db.py`**

Insert after `cmd_goal_list()` (after the block ending at line 2126 area):

```python
_VALID_SESSION_DISPOSITIONS = {
    "goal_progress", "maintenance", "exploration", "parked", "needs_attribution"
}


def cmd_session_open(title: str, goal_id: str = None) -> str:
    """Opens a new session, writes the active-session marker. Returns session_id."""
    from synlynk import _GREEN, _RESET, _get_db
    from synlynk.session import _write_active_session
    import hashlib as _hashlib
    session_id = "session-" + _hashlib.md5(
        f"{title}{time.time()}".encode()
    ).hexdigest()[:8]
    opened_at = time.strftime("%Y-%m-%dT%H:%M:%S")
    conn = _get_db()
    conn.execute(
        "INSERT INTO sessions (session_id, title, goal_id, status, opened_at) "
        "VALUES (?, ?, ?, 'open', ?)",
        (session_id, title, goal_id, opened_at),
    )
    conn.commit()
    conn.close()
    _write_active_session(session_id)
    print(f"  {_GREEN}✓{_RESET} Session opened: {session_id}  [{title}]")
    return session_id


def cmd_session_status() -> None:
    """Prints the active session (if any), its goal, and evidence counts."""
    from synlynk import _get_db
    from synlynk.session import _read_active_session
    session_id = _read_active_session()
    if not session_id:
        print("  No active session. Run: synlynk session open --title \"...\"")
        return
    conn = _get_db()
    row = conn.execute(
        "SELECT title, goal_id, opened_at, last_checkpoint_at FROM sessions WHERE session_id=?",
        (session_id,),
    ).fetchone()
    if not row:
        conn.close()
        print(f"  Active session marker points to {session_id}, but no matching row exists.")
        return
    title, goal_id, opened_at, last_checkpoint_at = row
    job_count = conn.execute(
        "SELECT COUNT(*) FROM daemon_jobs WHERE session_id=?", (session_id,)
    ).fetchone()[0]
    devlog_count = conn.execute(
        "SELECT COUNT(*) FROM devlog_entries WHERE session_id=?", (session_id,)
    ).fetchone()[0]
    conn.close()
    print(f"  Session: {session_id}  [{title}]")
    print(f"  Goal: {goal_id or '(none linked)'}")
    print(f"  Opened: {opened_at}   Last checkpoint: {last_checkpoint_at or '(never)'}")
    print(f"  Jobs attributed: {job_count}   Devlog entries: {devlog_count}")


def cmd_session_checkpoint() -> None:
    """Reports jobs/costs/devlog entries since the last checkpoint. Read-only."""
    from synlynk import _get_db
    from synlynk.session import _read_active_session
    session_id = _read_active_session()
    if not session_id:
        print("  No active session to checkpoint.")
        return
    conn = _get_db()
    row = conn.execute(
        "SELECT last_checkpoint_at, opened_at FROM sessions WHERE session_id=?", (session_id,)
    ).fetchone()
    if not row:
        conn.close()
        print(f"  Active session marker points to {session_id}, but no matching row exists.")
        return
    since = row[0] or row[1]
    jobs = conn.execute(
        "SELECT job_id, agent, status FROM daemon_jobs "
        "WHERE session_id=? AND enqueued_at>?",
        (session_id, since),
    ).fetchall()
    devlogs = conn.execute(
        "SELECT id, author, entry_date FROM devlog_entries "
        "WHERE session_id=? AND recorded_at>?",
        (session_id, since),
    ).fetchall()
    orphaned_jobs = conn.execute(
        "SELECT COUNT(*) FROM daemon_jobs WHERE session_id IS NULL AND enqueued_at>?",
        (since,),
    ).fetchone()[0]
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    conn.execute(
        "UPDATE sessions SET last_checkpoint_at=? WHERE session_id=?", (now, session_id)
    )
    conn.commit()
    conn.close()
    print(f"  Checkpoint for {session_id} since {since}:")
    print(f"  Jobs attributed to this session: {len(jobs)}")
    for job_id, agent, status in jobs:
        print(f"    - {job_id}  {agent}  {status}")
    print(f"  Devlog entries linked: {len(devlogs)}")
    if orphaned_jobs:
        print(f"  NUDGE: {orphaned_jobs} job(s) dispatched since {since} have no session_id — "
              f"likely dispatched with no session open.")


def cmd_session_close(disposition: str, summary: str = None) -> None:
    """Closes the active session with a disposition. Clears the active-session marker."""
    from synlynk import _GREEN, _RESET, _get_db
    from synlynk.session import _read_active_session, _clear_active_session
    if disposition not in _VALID_SESSION_DISPOSITIONS:
        raise ValueError(
            f"Invalid disposition: {disposition!r}, must be one of {sorted(_VALID_SESSION_DISPOSITIONS)}"
        )
    session_id = _read_active_session()
    if not session_id:
        print("  No active session to close.")
        return
    closed_at = time.strftime("%Y-%m-%dT%H:%M:%S")
    conn = _get_db()
    conn.execute(
        "UPDATE sessions SET status='closed', disposition=?, closed_at=?, closing_summary=? "
        "WHERE session_id=?",
        (disposition, closed_at, summary, session_id),
    )
    conn.commit()
    conn.close()
    _clear_active_session()
    print(f"  {_GREEN}✓{_RESET} Session closed: {session_id}  [{disposition}]")
```

Note: `_VALID_SESSION_DISPOSITIONS` values match the disposition vocabulary already adopted in `docs/strategy/2026-08-10-roadmap-todo-governance.md` (goal_progress / maintenance / exploration / parked / needs_attribution) — do not invent new labels.

- [ ] **Step 4: Wire the CLI subparser in `synlynk/cli.py`**

Insert after the `events` subparser block (after line 438, before `agent_parser = subparsers.add_parser("agent", ...)`):

```python
    session_parser = subparsers.add_parser("session", help="Manage work-envelope sessions")
    session_sub = session_parser.add_subparsers(dest="session_action")
    session_open_parser = session_sub.add_parser("open", help="Open a new session")
    session_open_parser.add_argument("--title", required=True, help="Short description of this session's work")
    session_open_parser.add_argument("--goal", dest="goal_id", default=None, help="Link to an existing goal_id")
    session_sub.add_parser("status", help="Show the active session and its evidence")
    session_sub.add_parser("checkpoint", help="Reconcile jobs/devlog entries since the last checkpoint")
    session_close_parser = session_sub.add_parser("close", help="Close the active session")
    session_close_parser.add_argument(
        "--disposition", required=True,
        choices=["goal_progress", "maintenance", "exploration", "parked", "needs_attribution"],
        help="What this session's work amounted to",
    )
    session_close_parser.add_argument("--summary", default=None, help="One-line closing summary")
```

Add `"session": session_parser,` to the `help_parsers` dict (mirrors the `"events": events_parser,` entry at `synlynk/cli.py:852`).

Add the dispatch block after the `elif args.command == "events":` block (after line 1404, before the `else: parser.print_help()`):

```python
    elif args.command == "session":
        action = getattr(args, "session_action", None)
        from synlynk.db import (
            cmd_session_open, cmd_session_status, cmd_session_checkpoint, cmd_session_close,
        )
        if action == "open":
            cmd_session_open(args.title, goal_id=args.goal_id)
        elif action == "status":
            cmd_session_status()
        elif action == "checkpoint":
            cmd_session_checkpoint()
        elif action == "close":
            cmd_session_close(disposition=args.disposition, summary=args.summary)
        else:
            help_parsers.get("session", parser).print_help()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_session.py -v`
Expected: PASS (all cases including the new `cmd_session_*` tests)

Run: `python3 bin/synlynk.py session open --title "smoke test" && python3 bin/synlynk.py session status && python3 bin/synlynk.py session checkpoint && python3 bin/synlynk.py session close --disposition exploration --summary "smoke test"`
Expected: four command outputs matching the print statements above, no tracebacks

- [ ] **Step 6: Run full suite**

Run: `python3 -m pytest -q`
Expected: all tests pass

- [ ] **Step 7: Commit**

```bash
git add synlynk/db.py synlynk/cli.py tests/test_session.py
git commit -m "feat: add session open/status/checkpoint/close commands"
```

- [ ] **Step 8: Open PR, dispatch non-authoring review, merge.** Do not proceed to Task 3 until merged — Task 3 also edits `synlynk/db.py`.

---

### Task 3: Link `devlog_entries` to session + goal

**Agent:** Agy (content/templates — closest fit for the devlog write-through path, which also touches the flat-file mirror)
**Depends on:** Task 2 merged.
**Files:**
- Modify: `synlynk/db.py:544-553` (`devlog_entries` table), `synlynk/db.py:1784-1797` (`cmd_devlog_append`)
- Test: new `tests/test_devlog_session_linking.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_devlog_session_linking.py
def test_devlog_append_links_session_and_goal(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SYNLYNK_DB_PATH", str(tmp_path / "state.db"))
    from synlynk.db import cmd_devlog_append
    from synlynk import _get_db

    cmd_devlog_append(
        author="nikhil", entry_date="2026-08-17", body="Shipped session MVP",
        session_id="session-abc12345", goal_id="goal-def67890",
    )

    conn = _get_db()
    row = conn.execute(
        "SELECT session_id, goal_id, body FROM devlog_entries WHERE author=?", ("nikhil",)
    ).fetchone()
    conn.close()
    assert row == ("session-abc12345", "goal-def67890", "Shipped session MVP")


def test_devlog_append_session_id_defaults_to_active_session(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SYNLYNK_DB_PATH", str(tmp_path / "state.db"))
    from synlynk.db import cmd_devlog_append, cmd_session_open
    from synlynk import _get_db

    session_id = cmd_session_open("Ship v0.14.0")
    cmd_devlog_append(author="nikhil", entry_date="2026-08-17", body="No explicit session_id passed")

    conn = _get_db()
    row = conn.execute(
        "SELECT session_id FROM devlog_entries WHERE author=?", ("nikhil",)
    ).fetchone()
    conn.close()
    assert row == (session_id,)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_devlog_session_linking.py -v`
Expected: FAIL with `TypeError: cmd_devlog_append() got an unexpected keyword argument 'session_id'`

- [ ] **Step 3: Add columns via self-heal migration**

Add to `synlynk/db.py`, near the other `PRAGMA table_info` self-heal blocks (after the `cost_entries` migration block, before the `roadmap_arcs` `goal_id` block at line 555-560):

```python
    devlog_cols = {row[1] for row in conn.execute("PRAGMA table_info(devlog_entries)")}
    if "session_id" not in devlog_cols:
        try:
            conn.execute("ALTER TABLE devlog_entries ADD COLUMN session_id TEXT REFERENCES sessions(session_id)")
        except sqlite3.OperationalError:
            pass
    if "goal_id" not in devlog_cols:
        try:
            conn.execute("ALTER TABLE devlog_entries ADD COLUMN goal_id TEXT REFERENCES goals(goal_id)")
        except sqlite3.OperationalError:
            pass
```

Also add both columns directly to the `CREATE TABLE IF NOT EXISTS devlog_entries` block (`synlynk/db.py:544-551`) so fresh databases get them without relying on the migration path:

```sql
        CREATE TABLE IF NOT EXISTS devlog_entries (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            author        TEXT NOT NULL,
            entry_date    TEXT NOT NULL,
            session_title TEXT,
            session_id    TEXT REFERENCES sessions(session_id),
            goal_id       TEXT REFERENCES goals(goal_id),
            body          TEXT NOT NULL,
            recorded_at   TEXT DEFAULT (datetime('now'))
        );
```

- [ ] **Step 4: Extend `cmd_devlog_append()`**

Replace `synlynk/db.py:1784-1797`:

```python
def cmd_devlog_append(author: str, entry_date: str, body: str,
                      session_title: str = None, session_id: str = None,
                      goal_id: str = None) -> None:
    """Append a devlog entry to DB and write through to flat file if migrated."""
    from synlynk import _dr_sync, _get_db, _is_migrated
    from synlynk.session import _read_active_session
    if session_id is None:
        session_id = _read_active_session()
    conn = _get_db()
    conn.execute(
        "INSERT INTO devlog_entries (author, entry_date, session_title, session_id, goal_id, body) "
        "VALUES (?,?,?,?,?,?)",
        (author, entry_date, session_title, session_id, goal_id, body)
    )
    conn.commit()
    conn.close()
    if _is_migrated():
        _write_devlog_file(author)
        _dr_sync(f"devlogs/{author}.md")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_devlog_session_linking.py -v`
Expected: PASS (2 passed)

- [ ] **Step 6: Run full suite**

Run: `python3 -m pytest -q`
Expected: all tests pass

- [ ] **Step 7: Commit**

```bash
git add synlynk/db.py tests/test_devlog_session_linking.py
git commit -m "feat: link devlog entries to session and goal"
```

- [ ] **Step 8: Open PR, dispatch non-authoring review, merge.** Do not proceed to Task 4 until merged — Task 4 also edits `synlynk/db.py` (`_insert_cost_row`).

---

### Task 4: Thread `session_id` through `dispatch_agent()` → `daemon_jobs` → `cost_entries`

**Agent:** Codex (refactor/cli-plumbing — this is the dispatch hot path)
**Depends on:** Task 3 merged.
**Files:**
- Modify: `synlynk/dispatch.py:74-94` (`_ensure_daemon_job_context_columns`, add sibling helper), `synlynk/dispatch.py:1837-1849` (`dispatch_agent` signature), `synlynk/dispatch.py:2346-2402` (both `daemon_jobs` write branches)
- Modify: `synlynk/db.py:915-935` (`_insert_cost_row` signature + inheritance), `synlynk/__init__.py:911-947` (`daemon_jobs` table), `synlynk/db.py:511-533` (`cost_entries` table)
- Test: `tests/test_dispatch_session_threading.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_dispatch_session_threading.py
def test_insert_cost_row_inherits_session_id_from_job(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SYNLYNK_DB_PATH", str(tmp_path / "state.db"))
    from synlynk import _get_db
    from synlynk.db import _insert_cost_row

    conn = _get_db()
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, status, enqueued_at, session_id) "
        "VALUES ('job-test1', 'codex', 'do a thing', 'running', '2026-08-17T00:00:00', 'session-abc12345')"
    )
    conn.commit()
    conn.close()

    _insert_cost_row(
        session_date="2026-08-17", agent="codex", model="gpt-5-codex",
        input_tokens=100, output_tokens=50, cache_read_tokens=0,
        cost_source="structured", total_cost_usd=0.01, job_id="job-test1",
    )

    conn = _get_db()
    row = conn.execute(
        "SELECT session_id FROM cost_entries WHERE job_id='job-test1'"
    ).fetchone()
    conn.close()
    assert row == ("session-abc12345",)


def test_dispatch_agent_writes_session_id_to_daemon_jobs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SYNLYNK_DB_PATH", str(tmp_path / "state.db"))
    from synlynk.session import _write_active_session
    from synlynk import _get_db
    import synlynk.dispatch as dispatch_mod

    (tmp_path / ".synlynk").mkdir(exist_ok=True)
    _write_active_session("session-abc12345")

    monkeypatch.setattr(dispatch_mod, "_run_dispatch_subprocess", lambda *a, **k: (0, "job-fixed-id", 12345))

    dispatch_mod.dispatch_agent("codex", "do a thing", job_id="job-fixed-id", skip_preflight=True)

    conn = _get_db()
    row = conn.execute(
        "SELECT session_id FROM daemon_jobs WHERE job_id='job-fixed-id'"
    ).fetchone()
    conn.close()
    assert row == ("session-abc12345",)
```

> Note for the implementing engineer: `test_dispatch_agent_writes_session_id_to_daemon_jobs` stubs the actual subprocess-launch internals — inspect `dispatch_agent()`'s body (`synlynk/dispatch.py:1837` onward) to find the real subprocess-spawn call and monkeypatch that specific function name instead of the placeholder `_run_dispatch_subprocess` shown here if it does not exist under that name; do not leave a mismatched patch target in the committed test.

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_dispatch_session_threading.py -v`
Expected: FAIL — `sqlite3.OperationalError: no such column: session_id` (for the first test) and a dispatch-side failure for the second, since neither `daemon_jobs` nor `cost_entries` has the column yet.

- [ ] **Step 3: Add `session_id` to `daemon_jobs` and `cost_entries` schemas**

Add to `synlynk/__init__.py`'s `daemon_jobs` table (`synlynk/__init__.py:911-947`), inside the column list, before the closing `);`:

```sql
    session_id   TEXT REFERENCES sessions(session_id)
```

Add to `synlynk/db.py`'s `cost_entries` table (`synlynk/db.py:511-533`), before the closing `);`:

```sql
            session_id        TEXT REFERENCES sessions(session_id)
```

- [ ] **Step 4: Add the self-heal helper in `synlynk/dispatch.py`**

Add after `_ensure_daemon_job_context_columns` (after line 94):

```python
def _ensure_daemon_job_session_column(conn) -> None:
    """Add session_id if missing (legacy schemas + unit fixtures). Mirrors
    _ensure_daemon_job_context_columns above — same no-op-on-absence contract.
    """
    try:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(daemon_jobs)").fetchall()}
    except Exception:
        return
    if not cols:
        return
    if "session_id" not in cols:
        try:
            conn.execute("ALTER TABLE daemon_jobs ADD COLUMN session_id TEXT REFERENCES sessions(session_id)")
        except Exception:
            pass
```

- [ ] **Step 5: Extend `dispatch_agent()` signature**

Modify `synlynk/dispatch.py:1837-1849`:

```python
def dispatch_agent(agent: str, task: str, story_id: str = None,
                   force_agent: bool = False,
                   context_mode: str = None,
                   cycle: str = "work",
                   skip_preflight: bool = False,
                   requires_gh_write: bool = False,
                   requires: list = None,
                   grants: list = None,
                   revokes: list = None,
                   job_id: str = None,
                   issue: int = None,
                   base: str = None,
                   scope_paths: list = None,
                   session_id: str = None) -> dict:
    if not task or not task.strip():
        raise ValueError(
            "--task is empty or whitespace-only; refusing to dispatch (see #720)"
        )
    if session_id is None:
        from synlynk.session import _read_active_session
        session_id = _read_active_session()
```

- [ ] **Step 6: Thread `session_id` into both `daemon_jobs` write branches**

Modify `synlynk/dispatch.py:2346-2402`. Add `_ensure_daemon_job_session_column(dconn)` alongside the existing `_ensure_daemon_job_context_columns(dconn)` call (line 2353):

```python
            _ensure_daemon_job_context_columns(dconn)
            _ensure_daemon_job_session_column(dconn)
```

Update the `existing` UPDATE branch (lines 2360-2377):

```python
                dconn.execute(
                    "UPDATE daemon_jobs SET status='running', pid=?, started_at=?, "
                    "log_path=?, agent=?, task=?, story_id=?, "
                    "dispatch_context=COALESCE(dispatch_context, ?), "
                    "context_mode=?, context_bytes=?, "
                    "session_id=COALESCE(session_id, ?) WHERE job_id=?",
                    (
                        proc.pid,
                        job["started_at"],
                        log_file,
                        agent,
                        task,
                        story_id,
                        dispatch_context,
                        context_mode,
                        context_bytes,
                        session_id,
                        job_id,
                    ),
                )
```

Update the INSERT branch (lines 2379-2401):

```python
                dconn.execute(
                    "INSERT OR REPLACE INTO daemon_jobs "
                    "(job_id, agent, task, story_id, status, priority, depends_on, pid, "
                    "enqueued_at, started_at, log_path, dispatch_context, context_mode, context_bytes, session_id) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        job_id,
                        agent,
                        task,
                        story_id,
                        "running",
                        5,
                        "[]",
                        proc.pid,
                        job["started_at"],
                        job["started_at"],
                        log_file,
                        dispatch_context,
                        context_mode,
                        context_bytes,
                        session_id,
                    ),
                )
```

- [ ] **Step 7: Extend `_insert_cost_row()` with session_id inheritance**

Modify `synlynk/db.py:915-960` (signature + inheritance block). Add `session_id: str = None` to the signature (after `context_mode: str = None,` at line 934):

```python
    context_mode: str = None,
    session_id: str = None,
) -> None:
```

In the inheritance block (mirrors the existing `context_mode` inheritance at `synlynk/db.py:952-960`), add immediately after it:

```python
        if session_id is None and job_id is not None:
            try:
                row = conn.execute(
                    "SELECT session_id FROM daemon_jobs WHERE job_id=?",
                    (job_id,),
                ).fetchone()
                if row and row[0]:
                    session_id = row[0]
            except sqlite3.Error:
                pass
```

Add `session_id` to both the UPDATE clause (`... context_mode=COALESCE(?, context_mode) ...` → append `, session_id=COALESCE(?, session_id)`) and the UPDATE params tuple (append `session_id` before `job_id`), and to the INSERT column list/placeholders/params tuple (append `session_id` at the end, matching the pattern of `dispatch_context, context_mode` already there).

- [ ] **Step 8: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_dispatch_session_threading.py -v`
Expected: PASS (2 passed)

- [ ] **Step 9: Run full suite**

Run: `python3 -m pytest -q`
Expected: all tests pass

- [ ] **Step 10: Commit**

```bash
git add synlynk/__init__.py synlynk/dispatch.py synlynk/db.py tests/test_dispatch_session_threading.py
git commit -m "feat: thread session_id through dispatch_agent, daemon_jobs, cost_entries"
```

- [ ] **Step 11: Open PR, dispatch non-authoring review, merge.** Do not proceed to Task 5 until merged.

---

### Task 5: `--session` override flag on `synlynk dispatch`

**Agent:** Grok (CLI plumbing)
**Depends on:** Task 4 merged.
**Files:**
- Modify: `synlynk/cli.py` (locate the existing `dispatch` subparser's `add_argument` calls and the block that calls `dispatch_agent(...)`)
- Test: `tests/test_dispatch_session_threading.py` (extend)

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_dispatch_session_threading.py
def test_dispatch_cli_session_flag_overrides_active_marker(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SYNLYNK_DB_PATH", str(tmp_path / "state.db"))
    from synlynk.session import _write_active_session
    from synlynk import _get_db
    import synlynk.dispatch as dispatch_mod
    from synlynk.cli import main

    (tmp_path / ".synlynk").mkdir(exist_ok=True)
    _write_active_session("session-active0000")
    monkeypatch.setattr(dispatch_mod, "_run_dispatch_subprocess", lambda *a, **k: (0, "job-cli-test", 12345))

    monkeypatch.setattr(
        "sys.argv",
        ["synlynk", "dispatch", "codex", "--task", "do a thing", "--force-agent",
         "--session", "session-override99", "--job-id", "job-cli-test", "--skip-preflight"],
    )
    main()

    conn = _get_db()
    row = conn.execute("SELECT session_id FROM daemon_jobs WHERE job_id='job-cli-test'").fetchone()
    conn.close()
    assert row == ("session-override99",)
```

> Note for the implementing engineer: locate the exact `dispatch` subparser flag names for `--job-id`/`--skip-preflight` in `synlynk/cli.py` before writing this test — use whatever flag names the existing subparser actually defines rather than guessing; if `--job-id` is not an exposed CLI flag today, pass `job_id` via the `dispatch_agent()` call path being tested at the Python level instead of through `sys.argv`.

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_dispatch_session_threading.py -k session_flag -v`
Expected: FAIL with `error: unrecognized arguments: --session session-override99`

- [ ] **Step 3: Add the `--session` flag to the dispatch subparser**

In `synlynk/cli.py`, find the `dispatch` subparser's argument definitions (grep for `dispatch_parser.add_argument` in the file) and add:

```python
    dispatch_parser.add_argument(
        "--session",
        dest="session_id",
        default=None,
        help="Override the active session_id for this dispatch (defaults to .synlynk/active_session.json)",
    )
```

Find the call site that invokes `dispatch_agent(...)` from the `dispatch` command handler and add `session_id=getattr(args, "session_id", None)` to its keyword arguments.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_dispatch_session_threading.py -v`
Expected: PASS (all cases)

- [ ] **Step 5: Run full suite**

Run: `python3 -m pytest -q`
Expected: all tests pass

- [ ] **Step 6: Commit**

```bash
git add synlynk/cli.py tests/test_dispatch_session_threading.py
git commit -m "feat: add --session override flag to synlynk dispatch"
```

- [ ] **Step 7: Open PR, dispatch non-authoring review, merge.** Do not proceed to Task 6 until merged.

---

### Task 6: First durable TPM nudge — unattributed work surfaced in `session status`

**Agent:** Agy (reporting/content)
**Depends on:** Task 5 merged.
**Files:**
- Modify: `synlynk/db.py` (`cmd_session_status`, added in Task 2)
- Test: extend `tests/test_session.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_session.py
def test_session_status_nudges_unattributed_jobs(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SYNLYNK_DB_PATH", str(tmp_path / "state.db"))
    from synlynk.db import cmd_session_open, cmd_session_status
    from synlynk import _get_db

    session_id = cmd_session_open("Ship v0.14.0")
    conn = _get_db()
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, status, enqueued_at, session_id) "
        "VALUES ('job-orphan', 'grok', 'unattributed work', 'completed', '2026-08-17T01:00:00', NULL)"
    )
    conn.commit()
    conn.close()

    capsys.readouterr()
    cmd_session_status()
    out = capsys.readouterr().out

    assert "NUDGE" in out
    assert "1 job" in out or "job-orphan" in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_session.py -k nudge -v`
Expected: FAIL — `AssertionError: assert 'NUDGE' in out` (current `cmd_session_status` prints no nudge)

- [ ] **Step 3: Add the nudge to `cmd_session_status()`**

Extend `cmd_session_status()` (added in Task 2), inserting before the final `print(f"  Jobs attributed: ...")` line:

```python
    unattributed_jobs = conn.execute(
        "SELECT COUNT(*) FROM daemon_jobs WHERE session_id IS NULL"
    ).fetchone()[0]
```

Move this query to before `conn.close()`, then after the existing print statements add:

```python
    if unattributed_jobs:
        print(f"  NUDGE: {unattributed_jobs} job(s) in daemon_jobs have no session_id — "
              f"dispatched with no session open. Run 'synlynk session open' before dispatching, "
              f"or pass --session explicitly.")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_session.py -v`
Expected: PASS (all cases)

- [ ] **Step 5: Run the full regression suite (Task 7's gate, folded in here)**

Run: `python3 -m pytest -q`
Expected: all tests pass, 0 failures. This is the slice-wide regression gate — if anything from Tasks 1-6 regressed, it surfaces here since this is the last task in the merge-order stack.

- [ ] **Step 6: Commit**

```bash
git add synlynk/db.py tests/test_session.py
git commit -m "feat: surface unattributed-job nudge in session status"
```

- [ ] **Step 7: Open PR, dispatch non-authoring review, merge.**

- [ ] **Step 8: PM summary to Nikhil (Claude, not dispatched)** — after this PR merges, Claude posts a single summary covering: what shipped across Tasks 1-6, the count of any unattributed jobs the nudge found in the live `daemon_jobs` table at that point, and the four known gaps listed in this plan's header, framed as Week 3 candidates rather than re-opening this slice.

---

## Self-Review

**1. Spec coverage** — checked against `road-to-autonomous-ops.md`'s Week 2 bullets:
- "activity-envelope schema" → Task 1 (`sessions` table).
- "`session open/status/close`" → Task 2 (+ `checkpoint`, which the base doc's bullet list separately requires as "checkpoint reconciliation").
- "devlog-session-goal linking" → Task 3.
- "checkpoint reconciliation" → Task 2's `cmd_session_checkpoint()`.
- "first durable TPM loop and nudges" → Task 6 (scoped down from "loop" to "nudge surfaced on-demand in `session status`" — see gap #2/#3 in the header; a standing autonomous loop that runs unprompted is explicitly deferred, matching the base doc's own maturity table showing this repo is not yet running unattended loops).

**2. Placeholder scan** — one intentional exception flagged inline rather than hidden: Task 4 Step 1 and Task 5 Step 1 both include an explicit note to the implementing engineer to verify an assumed internal function/flag name against the real file before committing, because the exact subprocess-spawn function name inside `dispatch_agent()`'s ~500-line body and the exact existing `dispatch` subparser flag names were not fully enumerated during planning. This is a "verify one name, don't invent behavior" instruction, not a "figure out what to build" placeholder — the test's behavior and assertions are fully specified either way.

**3. Type consistency** — `session_id` is `TEXT` everywhere (matches `goal_id`'s `TEXT`/hashlib-md5 convention, not the `uuid4().hex[:8]` convention used elsewhere for job/rollback IDs — chosen for consistency with `goals`, the table `sessions` links to most directly). `_VALID_SESSION_DISPOSITIONS` in Task 2 and the `--disposition` `choices=[...]` list in Task 2's CLI wiring use the identical five-value vocabulary; Task 6's nudge language and Task 2's `cmd_session_checkpoint()` nudge language both use the phrase "no session_id" / "no session open" consistently.
