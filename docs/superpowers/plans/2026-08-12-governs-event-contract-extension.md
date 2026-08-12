# GOVERNS Event-Contract Extension Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add two new GOVERNS event types (`job_terminal`, `review_submitted`) to the existing local event bus, plus a read-only `synlynk events tail` CLI command to observe all six wired event types, per `docs/superpowers/specs/2026-08-12-governs-event-contract-extension-design.md`.

**Architecture:** `job_terminal` is emitted synchronously from the two settlement call sites already inside `_reconcile_daemon_jobs()` (`synlynk/jobs.py`), immediately after each existing `_ensure_daemon_job_cost_entry()` call, reusing that call's own return value for `cost_recorded`. `review_submitted` is scan-detected: `scan_local_events()` (`synlynk/events.py`) already fetches the last 20 merged PRs for the `pr_merged` event — a new per-PR `gh pr view --json reviews` call is added inside that same loop, with dedup against already-emitted `review_submitted` event payloads (no monotonic checkpoint is usable for reviews, so dedup is by `(reviewer_login, submitted_at)` content match, not by id). `synlynk events tail` is a new read-only CLI command that queries the existing `events` table directly — no new table, no subscriber, no checkpoint advance.

**Tech Stack:** Python 3 stdlib only (sqlite3, json, subprocess, argparse). No new dependencies.

**Design correction carried into this plan:** the spec's `review_submitted` section states the dedup key is `(pr_number, reviewer_login, submitted_at)`, but its payload example omits `submitted_at`. This plan adds `submitted_at` to the payload (sourced from `gh pr view --json reviews`' `submittedAt` field per review) so the dedup key the spec describes is actually computable from stored event payloads. This is an additive field, not a scope change — it doesn't touch any other part of the spec.

---

## File Structure

| File | Responsibility |
|---|---|
| `synlynk/jobs.py` | Modify `_reconcile_daemon_jobs()` to emit `job_terminal` at both settlement call sites. Add `from synlynk.events import emit_event` import. |
| `synlynk/events.py` | Add `_reviewer_role_from_login()`, `_existing_review_submitted_keys()`, `_scan_pr_reviews_for_pr()` helpers and wire them into `scan_local_events()`. Add `cmd_events_tail()`. |
| `synlynk/cli.py` | Add `events` subparser with `tail` subcommand; wire dispatch to `cmd_events_tail`; import `cmd_events_tail` from `synlynk.events`. |
| `tests/test_jobs.py` | Add tests for `job_terminal` emission (both `cost_recorded=True` and `cost_recorded=False` branches). |
| `tests/test_events.py` | Add tests for `review_submitted` emission (role derivation, null role, no-duplicate-on-rescan) and `cmd_events_tail` (`--type` filter, `--limit`/ordering). Update one existing test's subprocess mock from `return_value` to `side_effect` (see Task 2). |

No schema changes — `events` table already exists (`synlynk/__init__.py:966`).

---

### Task 1: `job_terminal` event emission in `_reconcile_daemon_jobs()`

**Files:**
- Modify: `synlynk/jobs.py:14-16` (imports), `synlynk/jobs.py:2052-2058` (SELECT + row unpack), `synlynk/jobs.py:2125-2128` (preferred-summary settlement path), `synlynk/jobs.py:2221-2223` (guaranteed settlement path)
- Test: `tests/test_jobs.py`

Two settlement paths in `_reconcile_daemon_jobs()` call `_ensure_daemon_job_cost_entry()`: the "preferred existing summary" path (ends in `continue`, around line 2125) and the normal GTV path's final guarantee call (around line 2221, which always runs once GTV has resolved `status`). A `job_terminal` event must be emitted at both, immediately after each `_ensure_daemon_job_cost_entry()` call, using that call's own boolean return value as `cost_recorded`.

The current SELECT query doesn't fetch `dispatch_context`, which the payload needs. Add it to the query and the row-unpacking loop variable list.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_jobs.py` (after `test_ensure_daemon_job_cost_entry_skips_when_present`, i.e. end of file):

```python
def test_reconcile_daemon_jobs_emits_job_terminal_cost_recorded_true(project_dir, monkeypatch):
    import synlynk as sl
    import synlynk.jobs as jobs_mod
    from synlynk.events import pending_events

    job_id = "job-terminal-true"
    conn = sl._get_db()
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, status, pid, enqueued_at, started_at, dispatch_context) "
        "VALUES (?,'codex','t','running',999999,'2026-08-12T00:00:00','2026-08-12T00:00:00','headless')",
        (job_id,),
    )
    conn.commit()

    monkeypatch.setattr(jobs_mod, "_pid_is_alive", lambda pid: False)
    monkeypatch.setattr(sl, "extract_tokens", lambda log_text, agent=None: (0, 0))
    monkeypatch.setattr(sl, "extract_model_version", lambda log_text, agent=None: "unknown")
    monkeypatch.setattr(sl, "update_costs", lambda *a, **k: None)
    monkeypatch.setattr(sl, "_write_job_summary", lambda *a, **k: None)

    sl._reconcile_daemon_jobs()

    events = pending_events("test-observer", "job_terminal")
    matching = [e for e in events if e["payload"]["job_id"] == job_id]
    assert len(matching) == 1
    payload = matching[0]["payload"]
    assert payload["status"] in ("done", "failed_unverified", "timed_out", "failed")
    assert payload["cost_recorded"] is True
    assert payload["dispatch_context"] == "headless"


def test_reconcile_daemon_jobs_emits_job_terminal_cost_recorded_false_when_row_exists(project_dir, monkeypatch):
    import synlynk as sl
    import synlynk.jobs as jobs_mod
    from synlynk.db import _insert_cost_row
    from synlynk.events import pending_events

    job_id = "job-terminal-false"
    conn = sl._get_db()
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, status, pid, enqueued_at, started_at, dispatch_context) "
        "VALUES (?,'codex','t','running',999999,'2026-08-12T00:00:00','2026-08-12T00:00:00','home')",
        (job_id,),
    )
    conn.commit()
    _insert_cost_row(
        session_date="2026-08-12", agent="codex", model="t",
        input_tokens=1, output_tokens=1, cache_read_tokens=0,
        cost_source="actual", total_cost_usd=0.01, job_id=job_id,
    )

    monkeypatch.setattr(jobs_mod, "_pid_is_alive", lambda pid: False)
    monkeypatch.setattr(sl, "extract_tokens", lambda log_text, agent=None: (0, 0))
    monkeypatch.setattr(sl, "extract_model_version", lambda log_text, agent=None: "unknown")
    monkeypatch.setattr(sl, "update_costs", lambda *a, **k: None)
    monkeypatch.setattr(sl, "_write_job_summary", lambda *a, **k: None)

    sl._reconcile_daemon_jobs()

    events = pending_events("test-observer2", "job_terminal")
    matching = [e for e in events if e["payload"]["job_id"] == job_id]
    assert len(matching) == 1
    payload = matching[0]["payload"]
    assert payload["cost_recorded"] is False
    assert payload["dispatch_context"] == "home"


def test_reconcile_daemon_jobs_emits_job_terminal_on_preferred_summary_path(project_dir, monkeypatch):
    import synlynk as sl
    import synlynk.jobs as jobs_mod
    from synlynk.events import pending_events

    job_id = "job-terminal-preferred"
    conn = sl._get_db()
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, status, pid, enqueued_at, started_at, dispatch_context) "
        "VALUES (?,'agy','t','running',NULL,'2026-08-12T00:00:00','2026-08-12T00:00:00','headless')",
        (job_id,),
    )
    conn.commit()

    monkeypatch.setattr(
        jobs_mod, "_existing_terminal_summary_truth",
        lambda job_id: ("done", 0),
    )

    sl._reconcile_daemon_jobs()

    events = pending_events("test-observer3", "job_terminal")
    matching = [e for e in events if e["payload"]["job_id"] == job_id]
    assert len(matching) == 1
    payload = matching[0]["payload"]
    assert payload["status"] == "done"
    assert payload["cost_recorded"] is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_jobs.py -k job_terminal -v`
Expected: FAIL — `pending_events` returns no matching events (event never emitted), or `ImportError` if `pending_events` isn't importable yet in this context (it already is; the failure is the missing emission).

- [ ] **Step 3: Add the import**

In `synlynk/jobs.py`, after the existing `from synlynk.fleet import terminal_status_for_unknown_exit` line (line 16), add:

```python
from synlynk.events import emit_event
```

- [ ] **Step 4: Extend the SELECT query and row unpacking**

In `synlynk/jobs.py`, inside `_reconcile_daemon_jobs()`, change:

```python
    rows = conn.execute(
        "SELECT job_id, agent, story_id, task, pid, started_at, completed_at, log_path "
        "FROM daemon_jobs WHERE status='running'"
    ).fetchall()
```

to:

```python
    rows = conn.execute(
        "SELECT job_id, agent, story_id, task, pid, started_at, completed_at, log_path, dispatch_context "
        "FROM daemon_jobs WHERE status='running'"
    ).fetchall()
```

And change the `for` loop signature from:

```python
        for job_id, agent, story_id, task, pid, started_at, completed_at, log_path in rows:
```

to:

```python
        for job_id, agent, story_id, task, pid, started_at, completed_at, log_path, dispatch_context in rows:
```

- [ ] **Step 5: Emit `job_terminal` on the preferred-summary settlement path**

In `synlynk/jobs.py`, find this block (currently ending the `if preferred is not None:` branch):

```python
                    _ensure_daemon_job_cost_entry(
                        job_id, agent, story_id, log_text_pref, conn=conn
                    )
                    continue
```

Change it to:

```python
                    cost_recorded = _ensure_daemon_job_cost_entry(
                        job_id, agent, story_id, log_text_pref, conn=conn
                    )
                    emit_event(
                        "job_terminal",
                        {
                            "job_id": job_id,
                            "status": status,
                            "cost_recorded": cost_recorded,
                            "dispatch_context": dispatch_context,
                        },
                        emitted_by="_reconcile_daemon_jobs",
                    )
                    continue
```

- [ ] **Step 6: Emit `job_terminal` on the guaranteed settlement path**

In `synlynk/jobs.py`, find this block:

```python
                # Guarantee a row even if update_costs no-op'd (unmigrated flat-file path).
                _ensure_daemon_job_cost_entry(
                    job_id, agent, story_id, log_text, conn=conn
                )
```

Change it to:

```python
                # Guarantee a row even if update_costs no-op'd (unmigrated flat-file path).
                cost_recorded = _ensure_daemon_job_cost_entry(
                    job_id, agent, story_id, log_text, conn=conn
                )
                emit_event(
                    "job_terminal",
                    {
                        "job_id": job_id,
                        "status": status,
                        "cost_recorded": cost_recorded,
                        "dispatch_context": dispatch_context,
                    },
                    emitted_by="_reconcile_daemon_jobs",
                )
```

Leave the `_ensure_daemon_job_cost_entry` call inside the `except Exception as exc:` block just above (around line 2217) unchanged — it is a defensive retry, and the guaranteed call added in this step already runs unconditionally right after it, so a `job_terminal` event is still emitted exactly once per settled job on this path.

- [ ] **Step 7: Run tests to verify they pass**

Run: `pytest tests/test_jobs.py -k job_terminal -v`
Expected: PASS (3 tests)

- [ ] **Step 8: Run the full jobs test file to check for regressions**

Run: `pytest tests/test_jobs.py -v`
Expected: PASS, no regressions from the SELECT/loop-signature change.

- [ ] **Step 9: Commit**

```bash
git add synlynk/jobs.py tests/test_jobs.py
git commit -m "feat: emit job_terminal GOVERNS event on daemon job settlement"
```

---

### Task 2: `review_submitted` event emission in `scan_local_events()`

**Files:**
- Modify: `synlynk/events.py`
- Test: `tests/test_events.py`

**Files:**
- Modify: `synlynk/events.py`
- Test: `tests/test_events.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_events.py` (end of file):

```python
def test_scan_local_events_emits_review_submitted_with_role_derived_from_bot_login(project_dir):
    from unittest.mock import patch, MagicMock

    pr_list_stdout = json.dumps([{"number": 919, "title": "Test PR", "mergedAt": "2026-08-12T00:00:00Z"}])
    reviews_stdout = json.dumps({
        "reviews": [
            {"author": {"login": "synlynk-vdowrx-qa[bot]"}, "state": "COMMENTED", "submittedAt": "2026-08-12T01:00:00Z"},
        ]
    })
    git_log_stdout = ""

    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=pr_list_stdout),
            MagicMock(returncode=0, stdout=reviews_stdout),
            MagicMock(returncode=0, stdout=git_log_stdout),
        ]
        scan_local_events("workspace-lifecycle-nudge")

    pending = pending_events("test-observer", "review_submitted")
    assert len(pending) == 1
    payload = pending[0]["payload"]
    assert payload["pr_number"] == 919
    assert payload["reviewer_login"] == "synlynk-vdowrx-qa[bot]"
    assert payload["reviewer_role"] == "qa"
    assert payload["verdict"] == "COMMENTED"
    assert payload["submitted_at"] == "2026-08-12T01:00:00Z"


def test_scan_local_events_review_submitted_role_null_for_non_matching_login(project_dir):
    from unittest.mock import patch, MagicMock

    pr_list_stdout = json.dumps([{"number": 920, "title": "Test PR 2", "mergedAt": "2026-08-12T00:00:00Z"}])
    reviews_stdout = json.dumps({
        "reviews": [
            {"author": {"login": "some-human"}, "state": "APPROVED", "submittedAt": "2026-08-12T02:00:00Z"},
        ]
    })

    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=pr_list_stdout),
            MagicMock(returncode=0, stdout=reviews_stdout),
            MagicMock(returncode=0, stdout=""),
        ]
        scan_local_events("workspace-lifecycle-nudge")

    pending = pending_events("test-observer", "review_submitted")
    assert len(pending) == 1
    assert pending[0]["payload"]["reviewer_role"] is None


def test_scan_local_events_review_submitted_no_duplicate_on_rescan(project_dir):
    from unittest.mock import patch, MagicMock

    pr_list_stdout = json.dumps([{"number": 921, "title": "Test PR 3", "mergedAt": "2026-08-12T00:00:00Z"}])
    reviews_stdout = json.dumps({
        "reviews": [
            {"author": {"login": "synlynk-vdowrx-dev[bot]"}, "state": "APPROVED", "submittedAt": "2026-08-12T03:00:00Z"},
        ]
    })

    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=pr_list_stdout),
            MagicMock(returncode=0, stdout=reviews_stdout),
            MagicMock(returncode=0, stdout=""),
        ]
        scan_local_events("workspace-lifecycle-nudge")

    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=pr_list_stdout),
            MagicMock(returncode=0, stdout=reviews_stdout),
            MagicMock(returncode=0, stdout=""),
        ]
        scan_local_events("workspace-lifecycle-nudge")

    pending = pending_events("test-observer2", "review_submitted")
    assert len(pending) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_events.py -k review_submitted -v`
Expected: FAIL — no `review_submitted` events are emitted yet.

- [ ] **Step 3: Add the role-derivation and dedup helpers**

In `synlynk/events.py`, add near the top of the file, after the `import time` line:

```python
import re

_ROLE_LOGIN_RE = re.compile(r"^synlynk-[a-z0-9]+-([a-z]+)\[bot\]$")


def _reviewer_role_from_login(login):
    """Derives the role slug from a synlynk-<repo-slug>-<role>[bot] GitHub App login."""
    if not login:
        return None
    match = _ROLE_LOGIN_RE.match(login)
    return match.group(1) if match else None


def _existing_review_submitted_keys(pr_number):
    """Returns the set of (reviewer_login, submitted_at) already emitted for pr_number."""
    from synlynk import _get_db
    conn = _get_db()
    rows = conn.execute(
        "SELECT payload_json FROM events WHERE event_type='review_submitted'"
    ).fetchall()
    conn.close()
    keys = set()
    for (payload_json,) in rows:
        try:
            payload = json.loads(payload_json)
        except (TypeError, ValueError):
            continue
        if payload.get("pr_number") == pr_number:
            keys.add((payload.get("reviewer_login"), payload.get("submitted_at")))
    return keys


def _scan_pr_reviews(pr_number):
    """Fetches reviews for pr_number via gh, emits review_submitted for any not yet recorded.

    Returns the id of the last event emitted, or None if none were emitted.
    """
    import subprocess

    try:
        result = subprocess.run(
            ["gh", "pr", "view", str(pr_number), "--json", "reviews"],
            capture_output=True,
            text=True,
            check=False,
        )
        parsed = json.loads(result.stdout) if result.returncode == 0 else {}
        reviews = parsed.get("reviews", []) if isinstance(parsed, dict) else []
    except (FileNotFoundError, json.JSONDecodeError):
        reviews = []

    existing_keys = _existing_review_submitted_keys(pr_number)
    last_event_id = None
    for review in reviews:
        login = (review.get("author") or {}).get("login")
        submitted_at = review.get("submittedAt")
        key = (login, submitted_at)
        if key in existing_keys:
            continue
        last_event_id = emit_event(
            "review_submitted",
            {
                "pr_number": pr_number,
                "reviewer_login": login,
                "reviewer_role": _reviewer_role_from_login(login),
                "verdict": review.get("state"),
                "submitted_at": submitted_at,
            },
            emitted_by="scan_local_events",
        )
        existing_keys.add(key)
    return last_event_id
```

- [ ] **Step 4: Wire the review scan into `scan_local_events()`**

In `synlynk/events.py`, find the `pr_merged` loop:

```python
    last_event_id = None
    for pr in merged_prs:
        last_event_id = emit_event(
            "pr_merged",
            {
                "pr_number": pr["number"],
                "title": pr.get("title"),
                "merged_at": pr.get("mergedAt"),
            },
            emitted_by="scan_local_events",
        )
    if last_event_id is not None:
        advance_checkpoint(agent_name, "pr_merged", last_event_id)
```

Change it to:

```python
    last_event_id = None
    last_review_event_id = None
    for pr in merged_prs:
        last_event_id = emit_event(
            "pr_merged",
            {
                "pr_number": pr["number"],
                "title": pr.get("title"),
                "merged_at": pr.get("mergedAt"),
            },
            emitted_by="scan_local_events",
        )
        review_event_id = _scan_pr_reviews(pr["number"])
        if review_event_id is not None:
            last_review_event_id = review_event_id
    if last_event_id is not None:
        advance_checkpoint(agent_name, "pr_merged", last_event_id)
    if last_review_event_id is not None:
        advance_checkpoint(agent_name, "review_submitted", last_review_event_id)
```

- [ ] **Step 5: Update the existing test that shares one subprocess mock across all three calls**

`scan_local_events` now issues three `subprocess.run` calls when there is at least one merged PR: `gh pr list`, `gh pr view` (once per PR), then `git log`. The existing `test_scan_local_events_emits_pr_merged_from_gh_output` test mocks `subprocess.run` with a single `return_value`, which after this change would hand the merged-PR-list JSON to the `gh pr view` call too (harmlessly absorbed by the `isinstance(parsed, dict)` guard added in Step 3) and to the `git log` call (harmlessly produces nonsense "changed paths" that the test doesn't assert on). To keep the mock accurate rather than relying on the guard, change it to `side_effect`.

In `tests/test_events.py`, change:

```python
def test_scan_local_events_emits_pr_merged_from_gh_output(project_dir):
    from unittest.mock import patch, MagicMock

    gh_stdout = json.dumps([{"number": 99, "title": "Test PR", "mergedAt": "2026-08-08T00:00:00Z"}])
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=gh_stdout)
        scan_local_events("workspace-lifecycle-nudge")
    pending = pending_events("test-observer", "pr_merged")
    assert len(pending) == 1
    assert pending[0]["payload"]["pr_number"] == 99
```

to:

```python
def test_scan_local_events_emits_pr_merged_from_gh_output(project_dir):
    from unittest.mock import patch, MagicMock

    gh_stdout = json.dumps([{"number": 99, "title": "Test PR", "mergedAt": "2026-08-08T00:00:00Z"}])
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=gh_stdout),
            MagicMock(returncode=0, stdout=json.dumps({"reviews": []})),
            MagicMock(returncode=0, stdout=""),
        ]
        scan_local_events("workspace-lifecycle-nudge")
    pending = pending_events("test-observer", "pr_merged")
    assert len(pending) == 1
    assert pending[0]["payload"]["pr_number"] == 99
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_events.py -v`
Expected: PASS, including the updated `test_scan_local_events_emits_pr_merged_from_gh_output` and the three new `review_submitted` tests.

- [ ] **Step 7: Commit**

```bash
git add synlynk/events.py tests/test_events.py
git commit -m "feat: emit review_submitted GOVERNS event from PR review scan"
```

---

### Task 3: `synlynk events tail` CLI command

**Files:**
- Modify: `synlynk/events.py` (add `cmd_events_tail`)
- Modify: `synlynk/cli.py` (add `events` subparser + dispatch + import)
- Test: `tests/test_events.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_events.py` (end of file):

```python
def test_cmd_events_tail_filters_by_type(project_dir, capsys):
    from synlynk.events import cmd_events_tail

    emit_event("pr_merged", {"pr_number": 1}, emitted_by="test")
    emit_event("job_terminal", {"job_id": "job-a", "status": "done"}, emitted_by="test")
    emit_event("job_terminal", {"job_id": "job-b", "status": "failed"}, emitted_by="test")

    cmd_events_tail(event_type="job_terminal", limit=20)

    out = capsys.readouterr().out
    assert "job-a" in out
    assert "job-b" in out
    assert "pr_merged" not in out


def test_cmd_events_tail_respects_limit_and_orders_newest_first(project_dir, capsys):
    from synlynk.events import cmd_events_tail

    for i in range(5):
        emit_event("cron_heartbeat", {"tick": i}, emitted_by="test")

    cmd_events_tail(event_type="cron_heartbeat", limit=2)

    out = capsys.readouterr().out
    lines = [l for l in out.splitlines() if l.strip()]
    assert len(lines) == 2
    # Newest first: tick 4 appears before tick 3.
    assert out.index('"tick": 4') < out.index('"tick": 3')


def test_cmd_events_tail_with_no_type_shows_all_types(project_dir, capsys):
    from synlynk.events import cmd_events_tail

    emit_event("pr_merged", {"pr_number": 1}, emitted_by="test")
    emit_event("job_terminal", {"job_id": "job-a", "status": "done"}, emitted_by="test")

    cmd_events_tail(event_type=None, limit=20)

    out = capsys.readouterr().out
    assert "pr_merged" in out
    assert "job_terminal" in out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_events.py -k cmd_events_tail -v`
Expected: FAIL with `ImportError: cannot import name 'cmd_events_tail'`

- [ ] **Step 3: Implement `cmd_events_tail`**

In `synlynk/events.py`, add at the end of the file:

```python
def cmd_events_tail(event_type: str = None, limit: int = 20) -> None:
    """Prints the most recent GOVERNS events, newest first. Read-only diagnostic."""
    from synlynk import _get_db
    conn = _get_db()
    if event_type:
        rows = conn.execute(
            "SELECT id, created_at, event_type, emitted_by, payload_json "
            "FROM events WHERE event_type=? ORDER BY id DESC LIMIT ?",
            (event_type, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, created_at, event_type, emitted_by, payload_json "
            "FROM events ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    conn.close()
    for event_id, created_at, etype, emitted_by, payload_json in rows:
        try:
            payload = json.loads(payload_json)
            summary = json.dumps(payload, separators=(", ", ": "))
        except (TypeError, ValueError):
            summary = payload_json or ""
        print(f"{event_id}  {created_at}  {etype}  {emitted_by}  {summary}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_events.py -k cmd_events_tail -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Add the `events tail` subparser**

In `synlynk/cli.py`, find the `identity` parser block (around line 413-421):

```python
    identity_parser = subparsers.add_parser("identity", help="Manage synlynk agent identity")
    identity_sub = identity_parser.add_subparsers(dest="identity_action")
    identity_init_parser = identity_sub.add_parser("init", help="Create local Ed25519 identity key")
    identity_init_parser.add_argument(
        "--role",
        default=None,
        help="Provision a GitHub App for a specific role",
    )
    identity_sub.add_parser("list", help="List provisioned role identities")
```

Immediately after it, add:

```python
    events_parser = subparsers.add_parser("events", help="Inspect the GOVERNS event bus")
    events_sub = events_parser.add_subparsers(dest="events_action")
    events_tail_parser = events_sub.add_parser("tail", help="Print recent GOVERNS events, newest first")
    events_tail_parser.add_argument(
        "--type",
        dest="event_type",
        default=None,
        help="Filter to one event type (e.g. job_terminal, review_submitted, pr_merged)",
    )
    events_tail_parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum number of events to show (default 20)",
    )
```

- [ ] **Step 6: Wire the dispatch**

In `synlynk/cli.py`, find the `identity` dispatch block (around line 1368-1379):

```python
    elif args.command == "identity":
        action = getattr(args, "identity_action", None)
        if action == "init" or action is None:
            role = getattr(args, "role", None)
            if role:
                cmd_identity_init_role(role)
            else:
                cmd_identity_init()
        elif action == "list":
            cmd_identity_list()
        else:
            help_parsers.get("identity", parser).print_help()
```

Immediately after it (still before the final `else: parser.print_help()`), add:

```python
    elif args.command == "events":
        action = getattr(args, "events_action", None)
        if action == "tail":
            cmd_events_tail(event_type=args.event_type, limit=args.limit)
        else:
            help_parsers.get("events", parser).print_help()
```

- [ ] **Step 7: Import `cmd_events_tail` into `cli.py`**

In `synlynk/cli.py`, find where `cmd_identity_list` is imported from `synlynk` (in the large `from synlynk import (...)` block, around line 158/198). `cmd_events_tail` lives in `synlynk/events.py`, which — unlike `team.py` — is not re-exported through `synlynk/__init__.py` (confirmed: no `from synlynk.events import ...` exists there; `synlynk/events.py`'s functions are imported directly by consumers such as `synlynk/workspace_agent.py`). Add a direct import instead, next to the other direct-module imports such as `from synlynk.status import cmd_status as cmd_ecosystem_status` (around line 208):

```python
    from synlynk.events import cmd_events_tail
```

- [ ] **Step 8: Manually verify the CLI wiring**

Run: `python3 bin/synlynk.py events tail --help`
Expected: prints usage showing `--type` and `--limit` options, exit code 0.

Run (from a project with `.synlynk/state.db` present, e.g. this repo's worktree):
```bash
python3 bin/synlynk.py events tail --limit 5
```
Expected: prints up to 5 most recent events (or nothing if the `events` table is empty), no traceback.

- [ ] **Step 9: Run the full test suite**

Run: `pytest -v`
Expected: PASS, no regressions across the whole suite.

- [ ] **Step 10: Commit**

```bash
git add synlynk/events.py synlynk/cli.py tests/test_events.py
git commit -m "feat: add synlynk events tail CLI command"
```

---

## Self-Review

**Spec coverage:**
- `job_terminal` emission point + payload + idempotency (spec §1) → Task 1. ✅
- `review_submitted` emission point + payload + dedup + scope limitation (spec §2) → Task 2. ✅
- `synlynk events tail` CLI surface (spec §New CLI surface) → Task 3. ✅
- No schema changes, no `subscriptions`/`workspace_agent.py` changes (spec §Data flow summary) → confirmed: no task touches `subscriptions`, `advance_checkpoint` beyond the two new event types' own checkpoints, or `workspace_agent.py`. ✅
- Testing section's three bullets → Task 1 Steps 1-2 (job_terminal, both branches + preferred-path variant), Task 2 Steps 1-2 (review_submitted, role derivation + null + no-duplicate), Task 3 Steps 1-2 (events tail, --type + --limit/ordering). ✅

**Placeholder scan:** No TBD/TODO markers; every step has complete, runnable code.

**Type consistency:** `emit_event(event_type, payload, emitted_by, parent_event_id=None)` signature (from `synlynk/events.py:11`) used identically in Tasks 1 and 2. `pending_events(agent_name, event_type)` used identically across all three tasks' tests. `cmd_events_tail(event_type=None, limit=20)` signature in Task 3 Step 3 matches its call sites in Task 3 Step 6 (`cmd_events_tail(event_type=args.event_type, limit=args.limit)`) and its tests (Step 1).

---

## Dispatch Instructions (per this repo's CLAUDE.md role split)

Claude (PM/review/deploy only) does not implement. Each task above is dispatched as a single Codex job — the three tasks are sequential and touch overlapping files (`synlynk/events.py` in both Task 2 and Task 3), so dispatch them one at a time, in order, from the worktree:

```bash
cd /Users/nikhilsoman/dev/synlynk/.claude/worktrees/chore+governs-event-contract-extension-design
python3 bin/synlynk.py dispatch codex --task "Implement Task 1 (job_terminal event emission) from docs/superpowers/plans/2026-08-12-governs-event-contract-extension.md — follow the steps exactly, TDD order (write failing tests first), commit at the end of the task." --force-agent --context-mode full
```

Repeat for Task 2 and Task 3 after the prior task's PR is reviewed and merged (or after its commit is verified in-branch, if working sequentially on one branch without intermediate PRs). No `--requires-gh-write` flag needed — this is code/test-only work with no GitHub write actions.

After each dispatch: Claude performs spec-compliance review (does the diff match this plan's task exactly?) then code-quality review, per `superpowers:subagent-driven-development`'s two-stage review — both stages can be done by Claude directly or via the Agent tool, per this repo's role split (Claude retains the review role).
