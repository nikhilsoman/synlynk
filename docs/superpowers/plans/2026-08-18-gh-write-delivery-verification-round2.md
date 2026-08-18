# GH-Write Delivery Verification, Round 2 (#659 + #860) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend `gh_write_verified()` to detect PR review/comment writes (not just issue/PR close-merge), thread the required `since`/`expect_author`/`expect` metadata from dispatch through to both terminal-status call sites, and make the existing CLI-routing (non-MCP) mitigation apply to every dispatched agent, not just Codex.

**Architecture:** `synlynk/gh_verify.py` gains a `_LIST_EXPECT_FIELD` branch that checks `reviews`/`comments` list entries against a time floor and optional author match, reusing `events.py`'s bot-login role-parsing convention. `synlynk/dispatch.py` threads a new `gh_write_target_kind` param through `dispatch_agent()` to build `pr:<N>` targets, resolves the dispatching role's bot login into `gh_write_author`, and stores `gh_write_expect` alongside the existing `gh_write_target`/`requires_gh_write` fields (both on the flat-file job dict and the `daemon_jobs` sqlite table, mirroring the existing dual-persistence pattern). Both terminal-status call sites (`_check_job_stall` in `dispatch.py`, `_apply_gh_write_verification`/`_reconcile_daemon_jobs` in `jobs.py`) pass the new fields through instead of hardcoding `expect="closed"`. `_format_prompt_for_agent()`'s CLI-routing instruction moves from the Codex-only branch to a shared variable spliced into every agent's returned prompt.

**Tech Stack:** Python 3.8+ stdlib (`datetime`, `sqlite3`, `subprocess`, `ast`/`inspect` for the existing regression guard), pytest, `gh` CLI (mocked via `monkeypatch.setattr(subprocess, "run", ...)` in tests, per the existing `tests/test_gh_verify.py` pattern).

---

## File Structure

- Modify: `synlynk/gh_verify.py` — extend `gh_write_verified()`, add `_parse_iso8601`, add `_LIST_EXPECT_FIELD`.
- Modify: `synlynk/db.py` — add `gh_write_author`/`gh_write_expect` columns to the `_migrate_db` idempotent `ALTER TABLE` block.
- Modify: `synlynk/dispatch.py` — `_ensure_daemon_job_gh_write_columns` (legacy/unit-fixture path), `_resolve_dispatch_gh_bot_login` (new helper), `dispatch_agent()` signature + target/author/expect construction + job dict + INSERT/UPDATE, `_check_job_stall`, `_format_prompt_for_agent`.
- Modify: `synlynk/jobs.py` — `_apply_gh_write_verification` signature, `_reconcile_daemon_jobs` SELECT + both call sites.
- Test: `tests/test_gh_verify.py` — new cases for `review_posted`/`comment_posted` + `_parse_iso8601`.
- Test: `tests/test_dispatch_github_identity.py` — new cases for `gh_write_target_kind`, `gh_write_author` resolution.
- Test: `tests/test_dispatch.py` — new cases for `_format_prompt_for_agent` cross-agent instruction presence.
- Test: new `tests/test_gh_write_call_site_threading.py` — `_check_job_stall` / `_apply_gh_write_verification` pass-through behavior.
- No change needed: `tests/test_gh_write_guard.py` (regression guard) — must keep passing unchanged; no new terminal-status-deciding function is introduced.

---

### Task 1: `gh_verify.py` — `_parse_iso8601` helper (TDD)

**Files:**
- Modify: `synlynk/gh_verify.py`
- Test: `tests/test_gh_verify.py`

`gh`'s JSON timestamps (`submittedAt`, `createdAt`) use a `Z` suffix (e.g. `2026-08-18T10:00:00Z`). `datetime.fromisoformat` only accepts `Z` natively from Python 3.11+; this repo's CI matrix includes 3.8/3.10/3.12 (confirmed via `.github/workflows` test matrix), so a manual `Z` → `+00:00` normalization is required.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_gh_verify.py`:

```python
from synlynk.gh_verify import _parse_iso8601


def test_parse_iso8601_handles_z_suffix():
    dt = _parse_iso8601("2026-08-18T10:00:00Z")
    assert dt is not None
    assert dt.year == 2026 and dt.month == 8 and dt.day == 18
    assert dt.hour == 10


def test_parse_iso8601_handles_offset_suffix():
    dt = _parse_iso8601("2026-08-18T10:00:00+00:00")
    assert dt is not None
    assert dt.hour == 10


def test_parse_iso8601_returns_none_for_garbage():
    assert _parse_iso8601("not-a-timestamp") is None


def test_parse_iso8601_returns_none_for_none():
    assert _parse_iso8601(None) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_gh_verify.py -k parse_iso8601 -v`
Expected: FAIL with `ImportError: cannot import name '_parse_iso8601'`

- [ ] **Step 3: Implement `_parse_iso8601`**

In `synlynk/gh_verify.py`, add near the top (after the existing imports):

```python
from datetime import datetime
```

Add the helper function after the `_EXPECT_FIELD` dict:

```python
def _parse_iso8601(value: Optional[str]):
    """Parses an ISO8601 timestamp, normalizing a trailing 'Z' for Python <3.11.

    Returns None (not an exception) for missing/malformed input — callers
    treat an unparseable timestamp as "unknown", same contract as the rest
    of this module.
    """
    if not value:
        return None
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        return datetime.fromisoformat(normalized)
    except (ValueError, TypeError):
        return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_gh_verify.py -k parse_iso8601 -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add synlynk/gh_verify.py tests/test_gh_verify.py
git commit -m "feat: add _parse_iso8601 helper to gh_verify (#659, #860)"
```

---

### Task 2: `gh_verify.py` — extend `gh_write_verified()` with `review_posted`/`comment_posted` (TDD)

**Files:**
- Modify: `synlynk/gh_verify.py`
- Test: `tests/test_gh_verify.py`

Depends on Task 1 (`_parse_iso8601`).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_gh_verify.py`:

```python
def test_gh_write_verified_review_posted_true_after_since_no_author_filter(monkeypatch):
    def fake_run(cmd, **kwargs):
        assert cmd[:3] == ["gh", "pr", "view"]
        return subprocess.CompletedProcess(
            cmd, 0,
            stdout='{"reviews":[{"author":{"login":"someone[bot]"},'
                   '"submittedAt":"2026-08-18T11:00:00Z","state":"APPROVED"}]}',
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = gh_write_verified(
        "pr:1038", expect="review_posted", since="2026-08-18T10:00:00Z"
    )
    assert result is True


def test_gh_write_verified_review_posted_false_when_only_stale_entry(monkeypatch):
    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(
            cmd, 0,
            stdout='{"reviews":[{"author":{"login":"someone[bot]"},'
                   '"submittedAt":"2026-08-18T09:00:00Z","state":"APPROVED"}]}',
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = gh_write_verified(
        "pr:1038", expect="review_posted", since="2026-08-18T10:00:00Z"
    )
    assert result is False


def test_gh_write_verified_review_posted_true_with_matching_author(monkeypatch):
    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(
            cmd, 0,
            stdout='{"reviews":[{"author":{"login":"synlynk-synlynk-dev[bot]"},'
                   '"submittedAt":"2026-08-18T11:00:00Z","state":"APPROVED"}]}',
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = gh_write_verified(
        "pr:1038", expect="review_posted", since="2026-08-18T10:00:00Z",
        expect_author="synlynk-synlynk-dev[bot]",
    )
    assert result is True


def test_gh_write_verified_review_posted_false_when_author_mismatch(monkeypatch):
    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(
            cmd, 0,
            stdout='{"reviews":[{"author":{"login":"someone-else[bot]"},'
                   '"submittedAt":"2026-08-18T11:00:00Z","state":"APPROVED"}]}',
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = gh_write_verified(
        "pr:1038", expect="review_posted", since="2026-08-18T10:00:00Z",
        expect_author="synlynk-synlynk-dev[bot]",
    )
    assert result is False


def test_gh_write_verified_review_posted_none_when_since_omitted(monkeypatch):
    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 0, stdout='{"reviews":[]}', stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert gh_write_verified("pr:1038", expect="review_posted") is None


def test_gh_write_verified_comment_posted_true_after_since(monkeypatch):
    def fake_run(cmd, **kwargs):
        assert cmd[:3] == ["gh", "pr", "view"]
        return subprocess.CompletedProcess(
            cmd, 0,
            stdout='{"comments":[{"author":{"login":"someone[bot]"},'
                   '"createdAt":"2026-08-18T11:00:00Z"}]}',
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = gh_write_verified(
        "pr:1038", expect="comment_posted", since="2026-08-18T10:00:00Z"
    )
    assert result is True


def test_gh_write_verified_closed_behavior_unchanged_after_extension(monkeypatch):
    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 0, stdout='{"state":"CLOSED"}', stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert gh_write_verified("issue:701", expect="closed") is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_gh_verify.py -k "review_posted or comment_posted or unchanged_after_extension" -v`
Expected: FAIL — `review_posted`/`comment_posted` return `None` unconditionally (unsupported `expect` value) instead of the asserted values.

- [ ] **Step 3: Implement the extension**

Replace the full contents of `synlynk/gh_verify.py` with:

```python
"""Delivery-of-effect verification for --requires-gh-write jobs."""
import json
import re
import subprocess
from datetime import datetime
from typing import Optional


_TARGET_RE = re.compile(r"^(issue|pr):(\d+)$")
_EXPECT_FIELD = {
    "closed": ("state", "CLOSED"),
    "merged": ("state", "MERGED"),
}
_LIST_EXPECT_FIELD = {
    "review_posted": "reviews",
    "comment_posted": "comments",
}


def _parse_iso8601(value: Optional[str]):
    """Parses an ISO8601 timestamp, normalizing a trailing 'Z' for Python <3.11.

    Returns None (not an exception) for missing/malformed input — callers
    treat an unparseable timestamp as "unknown", same contract as the rest
    of this module.
    """
    if not value:
        return None
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        return datetime.fromisoformat(normalized)
    except (ValueError, TypeError):
        return None


def gh_write_verified(
    target: Optional[str],
    expect: str,
    timeout: int = 10,
    since: Optional[str] = None,
    expect_author: Optional[str] = None,
) -> Optional[bool]:
    """Return whether a declared GitHub target reached the expected state, or None if unknown.

    `expect="closed"`/`"merged"` check a scalar `state` field (original #701 behavior).
    `expect="review_posted"`/`"comment_posted"` check whether a `reviews`/`comments`
    list entry exists at or after `since`, optionally matching `expect_author`'s login.
    `since` is required for the two list-based expect values — without a time floor,
    a write from days earlier would false-positive every later job on the same PR.
    """
    if not target:
        return None
    match = _TARGET_RE.match(target)
    if not match:
        return None
    kind, number = match.groups()
    subcommand = "issue" if kind == "issue" else "pr"

    if expect in _EXPECT_FIELD:
        field, expected_value = _EXPECT_FIELD[expect]
        cmd = ["gh", subcommand, "view", number, "--json", field]
    elif expect in _LIST_EXPECT_FIELD:
        if not since:
            return None
        field = _LIST_EXPECT_FIELD[expect]
        cmd = ["gh", subcommand, "view", number, "--json", field]
    else:
        return None

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None
    if result.returncode != 0:
        return None
    try:
        payload = json.loads(result.stdout)
    except (json.JSONDecodeError, ValueError):
        return None

    if expect in _EXPECT_FIELD:
        actual = payload.get(field)
        return None if actual is None else actual == expected_value

    entries = payload.get(field)
    if entries is None:
        return None
    since_dt = _parse_iso8601(since)
    if since_dt is None:
        return None
    for entry in entries:
        entry_time = entry.get("submittedAt") or entry.get("createdAt")
        entry_dt = _parse_iso8601(entry_time)
        if entry_dt is None or entry_dt < since_dt:
            continue
        if expect_author and (entry.get("author") or {}).get("login") != expect_author:
            continue
        return True
    return False
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_gh_verify.py -v`
Expected: PASS (all tests in the file, including the pre-existing ones from #701)

- [ ] **Step 5: Commit**

```bash
git add synlynk/gh_verify.py tests/test_gh_verify.py
git commit -m "feat: gh_write_verified supports review_posted/comment_posted (#659, #860)"
```

---

### Task 3: `db.py` — add `gh_write_author`/`gh_write_expect` columns

**Files:**
- Modify: `synlynk/db.py:342-356` (the `_migrate_db` idempotent `ALTER TABLE` block)
- Modify: `synlynk/dispatch.py:178-196` (`_ensure_daemon_job_gh_write_columns`, the legacy/unit-fixture path used at dispatch time)
- Test: `tests/test_db_migrate.py` if it exists, else a focused inline check in Task 4's tests

No task depends on this beyond needing the columns to exist before Task 4 writes to them — this is schema-only, no behavior.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_migrate.py` (existing file — confirmed present in this repo):

```python
def test_migrate_adds_gh_write_author_and_expect_columns(tmp_path):
    import sqlite3
    from synlynk.db import _migrate_db

    db_path = tmp_path / "state.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE daemon_jobs (job_id TEXT PRIMARY KEY, agent TEXT, task TEXT, "
        "story_id TEXT, status TEXT, priority INTEGER, depends_on TEXT, pid INTEGER, "
        "enqueued_at TEXT, started_at TEXT, log_path TEXT)"
    )
    conn.execute("CREATE TABLE cost_entries (session_id TEXT)")
    conn.commit()
    _migrate_db(conn)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(daemon_jobs)")}
    assert "gh_write_author" in cols
    assert "gh_write_expect" in cols
    conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_migrate.py::test_migrate_adds_gh_write_author_and_expect_columns -v`
Expected: FAIL — `AssertionError: 'gh_write_author' not in cols`

- [ ] **Step 3: Implement the migration**

In `synlynk/db.py`, immediately after the existing block ending at line 356 (`if "gh_write_verified" not in daemon_job_cols: ...`), insert:

```python
    if "gh_write_author" not in daemon_job_cols:
        try:
            conn.execute("ALTER TABLE daemon_jobs ADD COLUMN gh_write_author TEXT")
        except sqlite3.OperationalError:
            pass
    if "gh_write_expect" not in daemon_job_cols:
        try:
            conn.execute("ALTER TABLE daemon_jobs ADD COLUMN gh_write_expect TEXT DEFAULT 'closed'")
        except sqlite3.OperationalError:
            pass
```

In `synlynk/dispatch.py`, update `_ensure_daemon_job_gh_write_columns` (currently lines 178-196) so its `definitions` dict also covers the two new columns — this function runs the same idempotent-ALTER pattern for legacy/unit-test schemas that don't go through `_migrate_db`:

```python
def _ensure_daemon_job_gh_write_columns(conn) -> None:
    """Add Task 0 gh-write columns for legacy/unit-test daemon schemas."""
    try:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(daemon_jobs)").fetchall()}
    except Exception:
        return
    if not cols:
        return
    definitions = {
        "requires_gh_write": "INTEGER NOT NULL DEFAULT 0",
        "gh_write_target": "TEXT",
        "gh_write_verified": "TEXT",
        "gh_write_author": "TEXT",
        "gh_write_expect": "TEXT DEFAULT 'closed'",
    }
    for name, definition in definitions.items():
        if name not in cols:
            try:
                conn.execute(f"ALTER TABLE daemon_jobs ADD COLUMN {name} {definition}")
            except Exception:
                pass
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_migrate.py::test_migrate_adds_gh_write_author_and_expect_columns -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add synlynk/db.py synlynk/dispatch.py tests/test_migrate.py
git commit -m "feat: add gh_write_author/gh_write_expect columns to daemon_jobs (#659, #860)"
```

---

### Task 4: `dispatch.py` — `gh_write_target_kind` param, bot-login resolution, job dict + DB persistence

**Files:**
- Modify: `synlynk/dispatch.py` — `_resolve_dispatch_gh_bot_login` (new function, near `_resolve_dispatch_gh_token` at line 229), `dispatch_agent()` signature (line 2050) and target/job-dict construction (lines 2535-2664)
- Test: `tests/test_dispatch_github_identity.py`

Depends on Task 3 (columns must exist before the INSERT/UPDATE reference them).

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_dispatch_github_identity.py`:

```python
import json
import os


def test_resolve_dispatch_gh_bot_login_from_role_app_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/github_apps")
    with open(".synlynk/github_apps/dev.json", "w") as f:
        json.dump({"role": "dev", "app_slug": "synlynk-synlynk-dev",
                   "installation_id": "123"}, f)

    from synlynk.dispatch import _resolve_dispatch_gh_bot_login

    assert _resolve_dispatch_gh_bot_login("dev") == "synlynk-synlynk-dev[bot]"


def test_resolve_dispatch_gh_bot_login_none_when_no_app_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from synlynk.dispatch import _resolve_dispatch_gh_bot_login

    assert _resolve_dispatch_gh_bot_login("dev") is None


def test_dispatch_agent_builds_pr_target_when_kind_pr(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import synlynk.dispatch as dispatch_mod

    monkeypatch.setattr(dispatch_mod, "_build_subprocess_env", lambda *a, **k: {})

    class FakeProc:
        pid = 4242

    monkeypatch.setattr(
        dispatch_mod.subprocess, "Popen", lambda *a, **k: FakeProc()
    )
    monkeypatch.setattr(dispatch_mod, "_pkg", lambda name, default=None: default)

    job = dispatch_mod.dispatch_agent(
        "codex", "review PR 1038", force_agent=True, requires_gh_write=True,
        issue=1038, gh_write_target_kind="pr", job_id="job-test-pr-target",
        task_type="review",
    )
    assert job["gh_write_target"] == "pr:1038"


def test_dispatch_agent_defaults_to_issue_target(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import synlynk.dispatch as dispatch_mod

    monkeypatch.setattr(dispatch_mod, "_build_subprocess_env", lambda *a, **k: {})

    class FakeProc:
        pid = 4243

    monkeypatch.setattr(
        dispatch_mod.subprocess, "Popen", lambda *a, **k: FakeProc()
    )
    monkeypatch.setattr(dispatch_mod, "_pkg", lambda name, default=None: default)

    job = dispatch_mod.dispatch_agent(
        "codex", "close issue 701", force_agent=True, requires_gh_write=True,
        issue=701, job_id="job-test-issue-target",
    )
    assert job["gh_write_target"] == "issue:701"
```

**Note for implementer:** these tests reach into `dispatch_agent()`'s full body, which has many dependencies (`_pkg`, worktree setup, cost estimation) beyond what's shown. Read the full current body of `dispatch_agent()` (`synlynk/dispatch.py:2050-2683`) before writing these tests — if the existing test file `tests/test_dispatch_github_identity.py` already has a working fixture/monkeypatch pattern for calling `dispatch_agent()` end-to-end (it tests `_build_subprocess_env`/token resolution today per Task 2 context, so it likely does), reuse that exact pattern rather than the sketch above. The sketch establishes intent (assert on `job["gh_write_target"]`); adapt the mocking to match what the file's existing tests already do successfully.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_dispatch_github_identity.py -k "bot_login or pr_target or issue_target" -v`
Expected: FAIL — `_resolve_dispatch_gh_bot_login` doesn't exist yet; `gh_write_target_kind` isn't an accepted kwarg yet.

- [ ] **Step 3: Implement `_resolve_dispatch_gh_bot_login`**

In `synlynk/dispatch.py`, add immediately after `_resolve_dispatch_gh_token` (after line 256):

```python
def _resolve_dispatch_gh_bot_login(role: str) -> Optional[str]:
    """Resolve the GitHub App bot login (e.g. 'synlynk-synlynk-dev[bot]') for a role.

    Mirrors _resolve_dispatch_gh_token's lookup order (role-specific App, then
    the synlynk-bot catch-all) but returns the bot login derived from
    app_slug instead of minting a token. Returns None if no App is
    provisioned for either candidate — same "no guess" contract as the rest
    of the gh-write verification path.
    """
    for candidate_role in (role, "synlynk-bot"):
        json_path = os.path.join(".synlynk", "github_apps", f"{candidate_role}.json")
        if not os.path.exists(json_path):
            continue
        try:
            with open(json_path) as fh:
                app_config = json.load(fh)
        except (OSError, json.JSONDecodeError):
            continue
        app_slug = app_config.get("app_slug")
        if not app_slug:
            continue
        return app_slug if app_slug.endswith("[bot]") else f"{app_slug}[bot]"
    return None
```

- [ ] **Step 4: Thread `gh_write_target_kind` through `dispatch_agent()`**

In `synlynk/dispatch.py`, update the `dispatch_agent` signature (currently starting at line 2050):

```python
def dispatch_agent(agent: str, task: str, story_id: str = None,
                   agent_id: str = None,
                   force_agent: bool = False,
                   context_mode: str = None,
                   cycle: str = "work",
                   skip_preflight: bool = False,
                   requires_gh_write: bool = False,
                   static_baseline: bool = False,
                   task_type: str = None,
                   requires: list = None,
                   grants: list = None,
                   revokes: list = None,
                   job_id: str = None,
                   issue: int = None,
                   base: str = None,
                   scope_paths: list = None,
                   session_id: str = None,
                   gh_write_target_kind: str = "issue") -> dict:
```

Replace the target/job-dict/persistence block (currently lines 2535-2664) with:

```python
    proc_env = _build_subprocess_env(agent, overrides, requires_gh_write, story_id, agent_role=resolved_agent_role)
    gh_write_target_value = None
    gh_write_author_value = None
    gh_write_expect_value = "closed"
    if requires_gh_write and issue is not None:
        target_kind = "pr" if gh_write_target_kind == "pr" else "issue"
        gh_write_target_value = f"{target_kind}:{issue}"
        role_for_author = resolved_agent_role or _role_for_story(story_id) or "dev"
        gh_write_author_value = _resolve_dispatch_gh_bot_login(role_for_author)
        if task_type == "review":
            gh_write_expect_value = "review_posted"

    proc = subprocess.Popen(
        ["sh", "-c", shell_cmd],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        cwd=worktree_path,
        env=proc_env,
    )

    job = {
        "id": job_id,
        "agent": agent,
        "story_id": story_id or "",
        "task": task,
        "cycle": cycle,
        "pid": proc.pid,
        "log_file": log_file,
        "prompt_file": prompt_file,
        "context_file": context_file if context_mode != "none" else "",
        "context_mode": context_mode,
        "context_bytes": context_bytes,
        "worktree_path": worktree_path,
        "worktree_branch": worktree_branch,
        "base_branch": base_branch,
        "base_sha": base_sha,
        "suite_result": None,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "ended_at": None,
        "status": "running",
        "exit_code": None,
        "dispatch_mode": dispatch_mode,
        "dispatch_rework": _pkg("_count_dispatch_rework")(story_id or "") if _pkg("_count_dispatch_rework") else 0,
        "micro_rework": 0,
        "retry_count": 0,
        "model_at_dispatch": model_at_dispatch,
        "fence": fence_data,
        "scope_paths": scope_paths or [],
        "requires_gh_write": requires_gh_write,
        "gh_write_target": gh_write_target_value,
        "gh_write_author": gh_write_author_value,
        "gh_write_expect": gh_write_expect_value,
        "task_type": task_type or "",
        "agent_id": agent_id or "",
        "resolved_agent_role": resolved_agent_role or "",
    }
```

Then update the DB persistence block immediately following (the `_ensure_daemon_job_gh_write_columns` call and the `existing`/INSERT branches). The `UPDATE` branch (re-running an already-queued job) gains two more `COALESCE`d columns; the `INSERT OR REPLACE` branch gains two more plain columns:

```python
            existing = dconn.execute(
                "SELECT 1 FROM daemon_jobs WHERE job_id=?", (job_id,)
            ).fetchone()
            if existing:
                # Preserve priority/depends_on/enqueued_at from the queue row.
                dispatch_context = _dispatch_context()
                dconn.execute(
                    "UPDATE daemon_jobs SET status='running', pid=?, started_at=?, "
                    "log_path=?, agent=?, task=?, story_id=?, "
                    "dispatch_context=COALESCE(dispatch_context, ?), "
                    "context_mode=?, context_bytes=?, "
                    "session_id=COALESCE(session_id, ?), "
                    "agent_id=COALESCE(agent_id, ?), "
                    "gh_write_author=COALESCE(gh_write_author, ?), "
                    "gh_write_expect=COALESCE(gh_write_expect, ?) WHERE job_id=?",
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
                        agent_id,
                        gh_write_author_value,
                        gh_write_expect_value,
                        job_id,
                    ),
                )
            else:
                dispatch_context = _dispatch_context()
                dconn.execute(
                    "INSERT OR REPLACE INTO daemon_jobs "
                    "(job_id, agent, task, story_id, status, priority, depends_on, pid, "
                    "enqueued_at, started_at, log_path, dispatch_context, context_mode, context_bytes, session_id, "
                    "agent_id, requires_gh_write, gh_write_target, gh_write_author, gh_write_expect) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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
                        agent_id,
                        1 if requires_gh_write else 0,
                        gh_write_target_value,
                        gh_write_author_value,
                        gh_write_expect_value,
                    ),
                )
            dconn.commit()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_dispatch_github_identity.py -v`
Expected: PASS (all tests in the file, including pre-existing ones)

- [ ] **Step 6: Run the full dispatch test suite for regressions**

Run: `pytest tests/test_dispatch.py tests/test_dispatch_cycle.py tests/test_dispatch_session_threading.py tests/test_resolve_dispatch_harness.py -v`
Expected: PASS — no signature-change regressions (all new params are keyword-only-by-default via trailing position with defaults, so existing positional/keyword call sites are unaffected).

- [ ] **Step 7: Commit**

```bash
git add synlynk/dispatch.py tests/test_dispatch_github_identity.py
git commit -m "feat: thread gh_write_target_kind/author/expect through dispatch_agent (#659, #860)"
```

---

### Task 5: `_check_job_stall` and `_apply_gh_write_verification` — pass `since`/`expect_author`/`expect` through

**Files:**
- Modify: `synlynk/dispatch.py:599-634` (`_check_job_stall`)
- Modify: `synlynk/jobs.py:2084-2098` (`_apply_gh_write_verification`), `synlynk/jobs.py:2101-2220` (`_reconcile_daemon_jobs` SELECT + both call sites)
- Test: new `tests/test_gh_write_call_site_threading.py`

Depends on Tasks 1, 2 (new `gh_write_verified` signature), 3 (columns), 4 (fields populated at dispatch time).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_gh_write_call_site_threading.py`:

```python
"""Verifies since/expect_author/expect thread correctly through the two
terminal-status call sites that consult gh_write_verified (#659, #860)."""
import synlynk.dispatch as dispatch_mod
import synlynk.jobs as jobs_mod


def test_check_job_stall_passes_since_and_expect_author_and_expect(monkeypatch, tmp_path):
    log_file = tmp_path / "job.log"
    log_file.write_text("running...")
    import os
    old_time = os.path.getmtime(log_file) - 6000  # stale beyond default 90 min review timeout
    os.utime(log_file, (old_time, old_time))

    captured = {}

    def fake_verified(target, expect, timeout=10, since=None, expect_author=None):
        captured["target"] = target
        captured["expect"] = expect
        captured["since"] = since
        captured["expect_author"] = expect_author
        return True  # verified delivered -> stall check should NOT kill

    monkeypatch.setattr(dispatch_mod, "gh_write_verified", fake_verified)

    job = {
        "status": "running",
        "log_file": str(log_file),
        "agent": "grok",
        "task_type": "review",
        "requires_gh_write": True,
        "gh_write_target": "pr:1038",
        "gh_write_author": "synlynk-synlynk-dev[bot]",
        "gh_write_expect": "review_posted",
        "started_at": "2026-08-18T10:00:00",
        "id": "job-test-stall",
    }
    killed = dispatch_mod._check_job_stall(job, {}, str(tmp_path / "sentinel.md"))

    assert killed is False
    assert captured["target"] == "pr:1038"
    assert captured["expect"] == "review_posted"
    assert captured["since"] == "2026-08-18T10:00:00"
    assert captured["expect_author"] == "synlynk-synlynk-dev[bot]"


def test_apply_gh_write_verification_uses_data_driven_expect(monkeypatch):
    captured = {}

    def fake_verified(target, expect, timeout=10, since=None, expect_author=None):
        captured["expect"] = expect
        captured["since"] = since
        captured["expect_author"] = expect_author
        return False  # not delivered

    monkeypatch.setattr(jobs_mod, "gh_write_verified", fake_verified)

    class FakeConn:
        def execute(self, *a, **k):
            return None

    status, verified_str = jobs_mod._apply_gh_write_verification(
        FakeConn(), "job-test-apply", True, "pr:1038", "done",
        since="2026-08-18T10:00:00", expect_author="synlynk-synlynk-dev[bot]",
        expect="review_posted",
    )

    assert captured["expect"] == "review_posted"
    assert captured["since"] == "2026-08-18T10:00:00"
    assert status == "succeeded_gh_write_failed"
    assert verified_str == "false"


def test_apply_gh_write_verification_defaults_expect_to_closed(monkeypatch):
    captured = {}

    def fake_verified(target, expect, timeout=10, since=None, expect_author=None):
        captured["expect"] = expect
        return True

    monkeypatch.setattr(jobs_mod, "gh_write_verified", fake_verified)

    class FakeConn:
        def execute(self, *a, **k):
            return None

    status, verified_str = jobs_mod._apply_gh_write_verification(
        FakeConn(), "job-test-default", True, "issue:701", "done",
    )

    assert captured["expect"] == "closed"
    assert status == "done"
    assert verified_str == "true"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_gh_write_call_site_threading.py -v`
Expected: FAIL — `_check_job_stall` still calls `gh_write_verified(target, expect="closed")` with no `since`/`expect_author`; `_apply_gh_write_verification` doesn't accept `since`/`expect_author`/`expect` kwargs yet.

- [ ] **Step 3: Update `_check_job_stall`**

In `synlynk/dispatch.py`, replace lines 618-623:

```python
    if job.get("requires_gh_write"):
        target = job.get("gh_write_target")
        verified = gh_write_verified(target, expect="closed")
        job["gh_write_verified"] = (
            "true" if verified is True else ("false" if verified is False else "unknown")
        )
```

with:

```python
    if job.get("requires_gh_write"):
        target = job.get("gh_write_target")
        expect = job.get("gh_write_expect") or "closed"
        verified = gh_write_verified(
            target,
            expect=expect,
            since=job.get("started_at"),
            expect_author=job.get("gh_write_author"),
        )
        job["gh_write_verified"] = (
            "true" if verified is True else ("false" if verified is False else "unknown")
        )
```

- [ ] **Step 4: Update `_apply_gh_write_verification` signature and body**

In `synlynk/jobs.py`, replace lines 2084-2098:

```python
def _apply_gh_write_verification(
    conn, job_id: str, requires_gh_write, gh_write_target: Optional[str], status: str
) -> tuple:
    """Consult GitHub state for a --requires-gh-write job and return status/outcome."""
    if not requires_gh_write:
        return status, None
    verified = gh_write_verified(gh_write_target, expect="closed")
    verified_str = "true" if verified is True else ("false" if verified is False else "unknown")
    if verified is False and status in ("done", "failed_unverified"):
        status = "succeeded_gh_write_failed"
    conn.execute(
        "UPDATE daemon_jobs SET gh_write_verified=? WHERE job_id=?",
        (verified_str, job_id),
    )
    return status, verified_str
```

with:

```python
def _apply_gh_write_verification(
    conn, job_id: str, requires_gh_write, gh_write_target: Optional[str], status: str,
    since: Optional[str] = None, expect_author: Optional[str] = None,
    expect: str = "closed",
) -> tuple:
    """Consult GitHub state for a --requires-gh-write job and return status/outcome."""
    if not requires_gh_write:
        return status, None
    verified = gh_write_verified(
        gh_write_target, expect=expect, since=since, expect_author=expect_author,
    )
    verified_str = "true" if verified is True else ("false" if verified is False else "unknown")
    if verified is False and status in ("done", "failed_unverified"):
        status = "succeeded_gh_write_failed"
    conn.execute(
        "UPDATE daemon_jobs SET gh_write_verified=? WHERE job_id=?",
        (verified_str, job_id),
    )
    return status, verified_str
```

- [ ] **Step 5: Thread the new fields through `_reconcile_daemon_jobs`**

In `synlynk/jobs.py`, update the SELECT (currently lines 2108-2116):

```python
    rows = conn.execute(
        "SELECT job_id, agent, story_id, task, pid, started_at, completed_at, log_path, "
        "dispatch_context, requires_gh_write, gh_write_target "
        "FROM daemon_jobs WHERE status='running'"
    ).fetchall()
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    try:
        for (job_id, agent, story_id, task, pid, started_at, completed_at, log_path,
             dispatch_context, requires_gh_write, gh_write_target) in rows:
```

to:

```python
    rows = conn.execute(
        "SELECT job_id, agent, story_id, task, pid, started_at, completed_at, log_path, "
        "dispatch_context, requires_gh_write, gh_write_target, gh_write_author, gh_write_expect "
        "FROM daemon_jobs WHERE status='running'"
    ).fetchall()
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    try:
        for (job_id, agent, story_id, task, pid, started_at, completed_at, log_path,
             dispatch_context, requires_gh_write, gh_write_target, gh_write_author,
             gh_write_expect) in rows:
```

Then update both call sites of `_apply_gh_write_verification` in the same function (currently lines 2161-2163 and 2216-2218) from:

```python
                    status, gh_write_verified_str = _apply_gh_write_verification(
                        conn, job_id, requires_gh_write, gh_write_target, status
                    )
```

to:

```python
                    status, gh_write_verified_str = _apply_gh_write_verification(
                        conn, job_id, requires_gh_write, gh_write_target, status,
                        since=started_at, expect_author=gh_write_author,
                        expect=gh_write_expect or "closed",
                    )
```

(Apply this same replacement at both of the two occurrences — the `preferred is not None` branch and the ground-truth-verification branch below it.)

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_gh_write_call_site_threading.py -v`
Expected: PASS (3 tests)

- [ ] **Step 7: Run the regression guard and jobs/dispatch suites**

Run: `pytest tests/test_gh_write_guard.py tests/jobs -v 2>/dev/null || pytest tests/test_gh_write_guard.py tests/ -k jobs -v`

If no `tests/jobs` directory exists, instead run:

Run: `pytest tests/test_gh_write_guard.py -v && pytest tests/ -k "reconcile or daemon_job" -v`
Expected: PASS — the regression guard still finds `gh_write_verified` (or the extended call site) referenced in both `_check_job_stall` and `_reconcile_daemon_jobs`'s source (it does an AST-name-reference check, not a signature check, so the added kwargs don't break it).

- [ ] **Step 8: Commit**

```bash
git add synlynk/dispatch.py synlynk/jobs.py tests/test_gh_write_call_site_threading.py
git commit -m "feat: thread since/expect_author/expect through gh-write terminal-status checks (#659, #860)"
```

---

### Task 6: `_format_prompt_for_agent` — CLI-routing instruction for every agent

**Files:**
- Modify: `synlynk/dispatch.py:1069-1118`
- Test: `tests/test_dispatch.py`

Independent of Tasks 1-5 — can be done in parallel conceptually, executed here in sequence per the plan's task order.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_dispatch.py`:

```python
from synlynk.dispatch import _format_prompt_for_agent


def test_gh_write_instruction_present_for_grok_when_required():
    prompt = _format_prompt_for_agent(
        "grok", "context", "story-1", "review PR 1038", "", "",
        requires_gh_write=True,
    )
    assert "GitHub Write Instructions" in prompt
    assert "Do not use MCP GitHub tools" in prompt


def test_gh_write_instruction_present_for_agy_when_required():
    prompt = _format_prompt_for_agent(
        "agy", "context", "story-1", "review PR 1038", "", "",
        requires_gh_write=True,
    )
    assert "GitHub Write Instructions" in prompt


def test_gh_write_instruction_present_for_codex_when_required():
    prompt = _format_prompt_for_agent(
        "codex", "context", "story-1", "review PR 1038", "", "",
        requires_gh_write=True,
    )
    assert "GitHub Write Instructions" in prompt


def test_gh_write_instruction_absent_when_not_required():
    for agent in ("codex", "agy", "grok"):
        prompt = _format_prompt_for_agent(
            agent, "context", "story-1", "some task", "", "",
            requires_gh_write=False,
        )
        assert "GitHub Write Instructions" not in prompt
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_dispatch.py -k gh_write_instruction -v`
Expected: FAIL for `grok` and `agy` cases (`"GitHub Write Instructions" not in prompt`); PASS already for `codex` and the absent case.

- [ ] **Step 3: Implement the shared instruction**

Replace `_format_prompt_for_agent` (currently lines 1069-1118) with:

```python
def _format_prompt_for_agent(agent: str, context_text: str, story_id: str,
                              task: str, file_section: str, verify_section: str,
                              cwd_hint: Optional[str] = None,
                              task_sha256: Optional[str] = None,
                              *, requires_gh_write: bool = False) -> str:
    """Returns a prompt formatted for the agent's preferred input style."""
    receipt_instruction = _render_task_receipt_instruction(task_sha256)
    story_ref = f"\n\n## Story / Task Reference\nStory ID: {story_id}" if story_id else ""
    gh_write_instruction = ""
    if requires_gh_write:
        gh_write_instruction = (
            "## GitHub Write Instructions\n"
            "For any PR review or issue/PR comment in this task, use the `gh` "
            "CLI directly via the shell — e.g. `gh pr review <N> --approve "
            "--body '...'` (or `--request-changes`/`--comment`) and `gh pr "
            "comment <N> --body '...'`. Do not use MCP GitHub tools for these "
            "writes; they have a confirmed failure history for this workflow.\n\n"
        )
    if agent == "codex":
        sentences = [s.strip() for s in re.split(r"[.!?]", task) if s.strip()]
        criteria = "\n".join(f"- {s}" for s in sentences) if sentences else f"- {task}"
        return (
            f"{receipt_instruction}"
            f"{gh_write_instruction}"
            f"## Task Criteria\n{criteria}\n"
            f"{file_section}\n"
            f"{verify_section}\n"
            f"## Context\n{context_text}"
            f"{story_ref}\n"
        )
    if agent == "agy":
        working_dir = cwd_hint or os.getcwd()
        return (
            f"{receipt_instruction}"
            f"{gh_write_instruction}"
            f"## Working Directory\n{working_dir}\n"
            f"All file edits MUST be in this directory.\n\n"
            f"Task: {task}\n"
            f"{story_ref}\n"
            f"{file_section}\n"
            f"{verify_section}\n"
            f"Context summary:\n{context_text}"
        )
    return (
        f"{receipt_instruction}"
        f"{gh_write_instruction}"
        f"{context_text}"
        f"{story_ref}"
        f"{file_section}"
        f"\n\n## Your Task\n{task}"
        f"{verify_section}\n"
    )
```

(Confirmed via `grep -n '"grok"' synlynk/dispatch.py` during research: no `agent == "grok"` branch exists in `_format_prompt_for_agent` — Grok falls through to the generic `return` at the end, which now includes `gh_write_instruction`.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_dispatch.py -k gh_write_instruction -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add synlynk/dispatch.py tests/test_dispatch.py
git commit -m "fix: CLI-routing gh-write instruction now applies to all agents, not just codex (#659)"
```

---

### Task 7: `task_type="review"` consistency audit

**Files:**
- No source changes expected unless the grep below turns up a gap — this is a due-diligence check, not a redesign (per the spec's Architecture section 4).

- [ ] **Step 1: Grep every dispatch call site for review-type tasks**

Run: `grep -rn "task_type=.review." synlynk/ bin/`

- [ ] **Step 2: Grep every PR-review-shaped dispatch call site regardless of task_type**

Run: `grep -rln "pull_request_review_write\|pr review\|non-authoring review\|PR Review Discipline" synlynk/ bin/ docs/superpowers/plans/ | head -20`

For each file found by Step 2 that dispatches a review task (via `dispatch_agent(...)` or `synlynk dispatch` invocation text), cross-check it appears in Step 1's results too. A review-dispatch call site missing `task_type="review"` gets the generic 30-minute stall timeout instead of the 90-minute `review_stall_timeout_minutes` — worth flagging even though it's not the root cause of the `#659`/`#860` recurrence (independently confirmed to be an in-agent `stopReason:"cancelled"`, not a stall-timeout kill).

- [ ] **Step 3: Report findings**

If Step 1/2 cross-check finds no gaps: note this in the PR description ("audited: all review-type dispatch call sites correctly pass `task_type=\"review\"`, no action needed") — no commit needed for this task.

If a gap is found: add `task_type="review"` to that call site as a one-line fix, with its own focused commit:

```bash
git add <file-with-gap>
git commit -m "fix: add missing task_type=review to <call site> (stall-timeout audit, #659)"
```

---

### Task 8: Full-suite verification

**Files:** None — verification only.

- [ ] **Step 1: Run the full test suite**

Run: `pytest tests/ -x -q`
Expected: PASS, 0 failures.

- [ ] **Step 2: Run the regression guard explicitly**

Run: `pytest tests/test_gh_write_guard.py -v`
Expected: PASS — confirms no new terminal-status-deciding function was introduced outside the two already-tracked (`_check_job_stall`, `_reconcile_daemon_jobs`).

- [ ] **Step 3: Run the gh_verify and dispatch suites explicitly one more time**

Run: `pytest tests/test_gh_verify.py tests/test_dispatch.py tests/test_dispatch_github_identity.py tests/test_gh_write_call_site_threading.py tests/test_migrate.py -v`
Expected: PASS, all green.

No commit for this task — it's a verification gate before handing off to `finishing-a-development-branch`.

---

### Task 9: Housekeeping — close #935/#701, retitle #426 (separate `--requires-gh-write` dispatch)

**Files:** None in this repo's source tree — GitHub issue writes only.

This task is deliberately **not** bundled into the code PR from Tasks 1-8. Per the spec's Architecture section 5, it runs only after the code above ships and is independently verified end-to-end (a fresh `--requires-gh-write` review dispatch confirms `gh_write_verified` correctly resolves `review_posted` against a real outcome) — this task should not be started until that verification has happened in a real dispatch, not just in unit tests.

- [ ] **Step 1: Dispatch the housekeeping task to Grok (or Agy if Grok is unavailable, per standing memory preferring Codex/Grok over Agy — Codex is excluded here since this requires GitHub writes)**

Run from the repo root (not this worktree — this is a GitHub-write-only task with no code changes, so it does not need its own worktree):

```bash
python3 bin/synlynk.py dispatch grok --task "Close GitHub issues #935 and #701 in nikhilsoman/synlynk, citing the PR that shipped 'GH-Write Delivery Verification, Round 2' (docs/superpowers/specs/2026-08-18-gh-write-delivery-verification-round2-design.md) and the verification job that confirmed gh_write_verified resolves review_posted correctly. Retitle issue #426 to reflect the actual 2026-08-09 retirement decision recorded in project-docs/decisions/2026-08-09-should-synlynk-retire-its-standing-githu.md (decision dec-d90d14ad) rather than its stale 'only Grok can do gh-write' framing -- read that decision file first to get the retitle wording right. Add a comment to #659 and #860 referencing #865 (Codex sandbox egress to api.github.com, deliberately deferred, tracked separately, not solved by this work) as a known-related open question. Do NOT close #659 or #860 themselves -- per the original disposition precedent they stay open until a full release cycle passes with no recurrence; only close #935, #701, and retitle #426." --requires-gh-write --force-agent --task-type review
```

- [ ] **Step 2: Verify the writes landed**

Run: `gh issue view 935 --repo nikhilsoman/synlynk --json state` and `gh issue view 701 --repo nikhilsoman/synlynk --json state`
Expected: both `"state": "CLOSED"`.

Run: `gh issue view 426 --repo nikhilsoman/synlynk --json title`
Expected: title no longer contains the stale "route gh-write to Grok by default" framing.

Do not trust the dispatched job's self-reported exit status alone for this verification (per this design's own thesis, and per standing memory "never trust `synlynk jobs` status alone") — the `gh issue view` checks above are the ground truth.

---

## Self-Review Notes

- **Spec coverage:** Architecture sections 1-5 map to Tasks 1-2 (§1), Tasks 3-5 (§2 + data model), Task 6 (§3), Task 7 (§4), Task 9 (§5). Testing section's itemized list is covered by Tasks 1, 2, 4, 5, 6, 8. Non-goals are respected — no task touches MCP internals, the events table, or `#865`.
- **Type consistency:** `gh_write_verified(target, expect, timeout=10, since=None, expect_author=None)` signature is identical across Tasks 2, 5, and the call sites in Task 5 — confirmed no drift between `dispatch.py`'s and `jobs.py`'s imports (`from synlynk.gh_verify import gh_write_verified`, unchanged import path). `_apply_gh_write_verification`'s new `since`/`expect_author`/`expect` kwargs default to `None`/`None`/`"closed"` so all pre-existing call sites (if any outside `jobs.py` — none found in research) remain valid without modification.
- **Placeholder scan:** no TBD/TODO; every code step shows complete, copy-pasteable code including full function bodies where replaced, not diffs-by-description.
