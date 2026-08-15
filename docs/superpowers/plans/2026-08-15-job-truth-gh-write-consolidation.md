# Job-Truth / GH-Write Consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend synlynk's ground-truth-verification (GTV) principle — already applied to git-worktree state — to GitHub API "delivery-of-effect" state, so a `--requires-gh-write` job's terminal status (both the pre-exit stall-kill decision and post-exit reconciliation) is never decided from a local proxy signal (exit code, log mtime, self-reported success) alone.

**Architecture:** A single shared helper, `gh_write_verified(target, expect, using_identity="orchestrator")`, queries the GitHub API via the orchestrator's own `gh` CLI identity (never the sandboxed job's, which may have a stripped/isolated `GH_CONFIG_DIR` per `--requires-gh-write` fail-closed semantics) for the declared target's actual state, and returns `True` / `False` / `None` (unknown — target undeclared or API unreachable). Both `_check_job_stall` (synlynk/dispatch.py) and `_reconcile_daemon_jobs` (synlynk/jobs.py) call it before falling through to their existing proxy-signal logic. Because neither the `daemon_jobs` sqlite table nor the flat-file `jobs` list currently persists a gh-write *target* (issue/PR number) — only `requires_gh_write: bool` exists, and only on the flat-file side — a foundational schema/persistence task (Task 0) lands first.

**Tech Stack:** Python 3 stdlib, `subprocess` (`gh` CLI), sqlite3 (`synlynk/db.py` migration pattern), pytest with `monkeypatch`/`capsys`.

---

## Foundational note: the schema gap

The spec's action items assume `--requires-gh-write` jobs are queryable-by-target at reconciliation time. They are not:

- `daemon_jobs` (sqlite, used by `_reconcile_daemon_jobs`) has **no** `requires_gh_write` column at all (confirmed via `PRAGMA table_info(daemon_jobs)` inspection and the `SELECT` at `synlynk/jobs.py:2049`).
- The flat-file `jobs` list (used by `_check_job_stall` via `_reconcile_jobs`) **does** store `requires_gh_write` (`synlynk/dispatch.py` job-dict construction) but has no target field (issue/PR number).
- `dispatch_agent()` already accepts `issue: int = None` (`synlynk/dispatch.py:1859`) but never persists it anywhere.

Task 0 closes this gap before Task 1's shared helper can be wired to real call sites.

---

### Task 0: Persist `requires_gh_write` and gh-write target on both job-tracking mechanisms

**Files:**
- Modify: `synlynk/db.py:301-336` (daemon_jobs migration block)
- Modify: `synlynk/dispatch.py` (dispatch_agent's daemon_jobs INSERT, ~line 2412-2434; flat-file job dict, ~line 2340-2360)
- Test: `tests/test_dispatch.py`

- [ ] **Step 1: Write the failing test for the daemon_jobs schema migration**

```python
def test_daemon_jobs_migration_adds_requires_gh_write_and_gh_write_target(project_dir):
    from synlynk.db import _get_db
    conn = _get_db()
    cols = {row[1] for row in conn.execute("PRAGMA table_info(daemon_jobs)")}
    assert "requires_gh_write" in cols
    assert "gh_write_target" in cols
    conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_dispatch.py::test_daemon_jobs_migration_adds_requires_gh_write_and_gh_write_target -v`
Expected: FAIL — `assert "requires_gh_write" in cols` raises `AssertionError`

- [ ] **Step 3: Add the migration in `synlynk/db.py`**

Insert immediately after the existing `session_id` column block (after `synlynk/db.py:336`, following the exact same `PRAGMA table_info` guard pattern used for every other `daemon_jobs` column):

```python
    if "requires_gh_write" not in daemon_job_cols:
        try:
            conn.execute("ALTER TABLE daemon_jobs ADD COLUMN requires_gh_write INTEGER NOT NULL DEFAULT 0")
        except sqlite3.OperationalError:
            pass
    if "gh_write_target" not in daemon_job_cols:
        try:
            conn.execute("ALTER TABLE daemon_jobs ADD COLUMN gh_write_target TEXT")
        except sqlite3.OperationalError:
            pass
    if "gh_write_verified" not in daemon_job_cols:
        try:
            conn.execute("ALTER TABLE daemon_jobs ADD COLUMN gh_write_verified TEXT")
        except sqlite3.OperationalError:
            pass
```

`gh_write_target` stores a string like `"issue:701"` or `"pr:964"` (declared shape below in Task 1). `gh_write_verified` stores `"true"` / `"false"` / `"unknown"` / `NULL` (not-applicable — job didn't declare `--requires-gh-write`). Using `TEXT` tri-state instead of `INTEGER` avoids conflating "verified false" with "not applicable."

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_dispatch.py::test_daemon_jobs_migration_adds_requires_gh_write_and_gh_write_target -v`
Expected: PASS

- [ ] **Step 5: Write the failing test for daemon_jobs INSERT persisting the new fields**

```python
def test_dispatch_agent_persists_requires_gh_write_and_target_on_daemon_jobs(project_dir, monkeypatch):
    from synlynk.dispatch import dispatch_agent
    from synlynk.db import _get_db
    _stub_subprocess_success(monkeypatch)  # existing test helper in this file for a no-op agent run
    dispatch_agent("codex", "close stale issues", force_agent=True, requires_gh_write=True, issue=701)
    conn = _get_db()
    row = conn.execute(
        "SELECT requires_gh_write, gh_write_target FROM daemon_jobs ORDER BY enqueued_at DESC LIMIT 1"
    ).fetchone()
    conn.close()
    assert row[0] == 1
    assert row[1] == "issue:701"
```

(If `_stub_subprocess_success` doesn't exist under that name, use whichever existing fixture in `tests/test_dispatch.py` other `dispatch_agent(...)`-calling tests near line 929-994 use to stub the subprocess — match their pattern exactly rather than inventing a new one.)

- [ ] **Step 6: Run test to verify it fails**

Run: `pytest tests/test_dispatch.py::test_dispatch_agent_persists_requires_gh_write_and_target_on_daemon_jobs -v`
Expected: FAIL — `row[0]` is `None`/`0` unconditionally, `gh_write_target` column doesn't get populated (KeyError or None mismatch)

- [ ] **Step 7: Wire the fields into `dispatch_agent`'s daemon_jobs INSERT**

In `synlynk/dispatch.py`, find the `daemon_jobs` INSERT (~line 2412-2434, the `"INSERT OR REPLACE INTO daemon_jobs (job_id, agent, task, story_id, status, priority, depends_on, pid, enqueued_at, started_at, log_path, dispatch_context, context_mode, context_bytes, session_id) VALUES (...)"` statement). Add `requires_gh_write, gh_write_target` as two more columns/params:

```python
    gh_write_target_value = None
    if requires_gh_write and issue is not None:
        gh_write_target_value = f"issue:{issue}"

    conn.execute(
        "INSERT OR REPLACE INTO daemon_jobs "
        "(job_id, agent, task, story_id, status, priority, depends_on, pid, enqueued_at, "
        "started_at, log_path, dispatch_context, context_mode, context_bytes, session_id, "
        "requires_gh_write, gh_write_target) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            job_id, agent, task, story_id, "queued", priority, depends_on_json, pid,
            enqueued_at, started_at, log_path, dispatch_context, context_mode,
            context_bytes, session_id,
            1 if requires_gh_write else 0, gh_write_target_value,
        ),
    )
```

Adjust exactly to match the real parameter list/order already present at that call site — the above shows the two new columns appended at the end; preserve every existing column and value in its current position.

Also add `"requires_gh_write": requires_gh_write, "gh_write_target": gh_write_target_value` to the flat-file job dict construction (~line 2340-2360, alongside the existing `"requires_gh_write": requires_gh_write, "task_type": task_type or ""` entry) so `_check_job_stall` (Task 1) can read the target from the same dict it already reads `requires_gh_write` from.

- [ ] **Step 8: Run test to verify it passes**

Run: `pytest tests/test_dispatch.py::test_dispatch_agent_persists_requires_gh_write_and_target_on_daemon_jobs -v`
Expected: PASS

- [ ] **Step 9: Run full dispatch + db test files to check no regressions**

Run: `pytest tests/test_dispatch.py tests/test_synlynk.py -v -k "daemon_jobs or requires_gh_write"`
Expected: all PASS

- [ ] **Step 10: Commit**

```bash
git add synlynk/db.py synlynk/dispatch.py tests/test_dispatch.py
git commit -m "feat: persist requires_gh_write + gh_write_target on daemon_jobs and flat-file jobs"
```

**Dispatch routing:** Codex (`code`/`refactor`/`cli-plumbing` capability, per this repo's routing table).

---

### Task 1: Shared `gh_write_verified` helper + wire into both call sites

**Files:**
- Create: `synlynk/gh_verify.py`
- Modify: `synlynk/dispatch.py:517-583` (`_check_job_stall`)
- Modify: `synlynk/jobs.py:2049` (`_reconcile_daemon_jobs`, both terminal-status branches)
- Test: `tests/test_gh_verify.py`
- Test: `tests/test_dispatch.py`
- Test: `tests/test_jobs.py`

**Prerequisite:** Task 0 must be merged (adds `requires_gh_write`/`gh_write_target` columns and flat-file fields this task reads).

- [ ] **Step 1: Write the failing unit tests for `gh_write_verified` (true/false/unknown)**

```python
# tests/test_gh_verify.py
import subprocess
from synlynk.gh_verify import gh_write_verified


def test_gh_write_verified_true_when_issue_closed(monkeypatch):
    def fake_run(cmd, **kwargs):
        assert cmd[:3] == ["gh", "issue", "view"]
        return subprocess.CompletedProcess(cmd, 0, stdout='{"state":"CLOSED"}', stderr="")
    monkeypatch.setattr(subprocess, "run", fake_run)
    assert gh_write_verified("issue:701", expect="closed") is True


def test_gh_write_verified_false_when_issue_still_open(monkeypatch):
    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 0, stdout='{"state":"OPEN"}', stderr="")
    monkeypatch.setattr(subprocess, "run", fake_run)
    assert gh_write_verified("issue:701", expect="closed") is False


def test_gh_write_verified_true_when_pr_merged(monkeypatch):
    def fake_run(cmd, **kwargs):
        assert cmd[:3] == ["gh", "pr", "view"]
        return subprocess.CompletedProcess(cmd, 0, stdout='{"state":"MERGED"}', stderr="")
    monkeypatch.setattr(subprocess, "run", fake_run)
    assert gh_write_verified("pr:964", expect="merged") is True


def test_gh_write_verified_unknown_when_target_none():
    assert gh_write_verified(None, expect="closed") is None


def test_gh_write_verified_unknown_when_gh_cli_errors(monkeypatch):
    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="gh: not found")
    monkeypatch.setattr(subprocess, "run", fake_run)
    assert gh_write_verified("issue:701", expect="closed") is None


def test_gh_write_verified_unknown_when_gh_cli_times_out(monkeypatch):
    def fake_run(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, kwargs.get("timeout", 5))
    monkeypatch.setattr(subprocess, "run", fake_run)
    assert gh_write_verified("issue:701", expect="closed") is None


def test_gh_write_verified_rejects_malformed_target():
    assert gh_write_verified("not-a-valid-target", expect="closed") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_gh_verify.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'synlynk.gh_verify'`

- [ ] **Step 3: Implement `synlynk/gh_verify.py`**

```python
"""Delivery-of-effect verification for --requires-gh-write jobs.

Ground-truth-verification (GTV) principle applied to GitHub API state: a
job's declared gh-write effect (closing an issue, merging a PR, posting a
review) is only trusted once confirmed against the GitHub API using the
orchestrator's own `gh` identity — never the sandboxed job's, which may run
under an isolated/stripped GH_CONFIG_DIR per --requires-gh-write fail-closed
semantics (synlynk/dispatch.py dispatch_agent reroute logic).
"""
import json
import re
import subprocess
from typing import Optional

_TARGET_RE = re.compile(r"^(issue|pr):(\d+)$")

_EXPECT_FIELD = {
    "closed": ("state", "CLOSED"),
    "merged": ("state", "MERGED"),
}


def gh_write_verified(target: Optional[str], expect: str, timeout: int = 10) -> Optional[bool]:
    """Returns True/False if the target's GitHub state matches `expect`, else None (unknown).

    `target` is "issue:<N>" or "pr:<N>". `expect` is "closed" or "merged".
    None means: no target declared, gh CLI unavailable, API error, or timeout —
    callers MUST treat None as "cannot verify," never as False.
    """
    if not target:
        return None
    match = _TARGET_RE.match(target)
    if not match:
        return None
    kind, number = match.group(1), match.group(2)
    if expect not in _EXPECT_FIELD:
        return None
    field, expected_value = _EXPECT_FIELD[expect]

    subcommand = "issue" if kind == "issue" else "pr"
    cmd = ["gh", subcommand, "view", number, "--json", field]
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
    actual = payload.get(field)
    if actual is None:
        return None
    return actual == expected_value
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_gh_verify.py -v`
Expected: PASS (7 passed)

- [ ] **Step 5: Write the failing test for `_check_job_stall`'s new gh-write escape hatch**

```python
# tests/test_dispatch.py
def test_check_job_stall_extends_timeout_when_gh_write_verified_true(project_dir, monkeypatch, tmp_path):
    from synlynk import dispatch as dispatch_mod
    log_file = tmp_path / "job.log"
    log_file.write_text("working...")
    old_mtime = _time.time() - 3600  # 60 min stale, past any default timeout
    os.utime(log_file, (old_mtime, old_mtime))
    job = {
        "id": "job-abc123", "status": "running", "log_file": str(log_file),
        "agent": "grok", "pid": 999999,
        "requires_gh_write": True, "gh_write_target": "issue:701",
    }
    monkeypatch.setattr(dispatch_mod, "gh_write_verified", lambda target, expect, **kw: True)
    stalled = dispatch_mod._check_job_stall(job, {"stall_timeout_minutes": 30}, str(tmp_path / "sentinel.md"))
    assert stalled is False
    assert job["status"] == "running"


def test_check_job_stall_kills_when_gh_write_verified_false(project_dir, monkeypatch, tmp_path):
    from synlynk import dispatch as dispatch_mod
    log_file = tmp_path / "job.log"
    log_file.write_text("working...")
    old_mtime = _time.time() - 3600
    os.utime(log_file, (old_mtime, old_mtime))
    job = {
        "id": "job-abc123", "status": "running", "log_file": str(log_file),
        "agent": "grok", "pid": None,
        "requires_gh_write": True, "gh_write_target": "issue:701",
    }
    monkeypatch.setattr(dispatch_mod, "gh_write_verified", lambda target, expect, **kw: False)
    monkeypatch.setattr(dispatch_mod, "_inspect_worktree_git_state", lambda *a, **kw: None)
    stalled = dispatch_mod._check_job_stall(job, {"stall_timeout_minutes": 30}, str(tmp_path / "sentinel.md"))
    assert stalled is True
    assert job["status"] == "failed"
    assert job.get("gh_write_verified") == "false"


def test_check_job_stall_falls_through_to_git_state_when_gh_write_unknown(project_dir, monkeypatch, tmp_path):
    from synlynk import dispatch as dispatch_mod
    log_file = tmp_path / "job.log"
    log_file.write_text("working...")
    old_mtime = _time.time() - 3600
    os.utime(log_file, (old_mtime, old_mtime))
    job = {
        "id": "job-abc123", "status": "running", "log_file": str(log_file),
        "agent": "grok", "pid": None,
        "requires_gh_write": True, "gh_write_target": "issue:701",
        "worktree_path": "/tmp/fake-wt", "worktree_branch": "dispatch/grok/job-abc123",
        "started_at": "2026-08-15T00:00:00",
    }
    monkeypatch.setattr(dispatch_mod, "gh_write_verified", lambda target, expect, **kw: None)
    monkeypatch.setattr(
        dispatch_mod, "_inspect_worktree_git_state",
        lambda *a, **kw: {"has_activity": True, "commits_ahead": 1, "dirty": False},
    )
    stalled = dispatch_mod._check_job_stall(job, {"stall_timeout_minutes": 30}, str(tmp_path / "sentinel.md"))
    assert stalled is False
```

Add `import time as _time` and `import os` at the top of `tests/test_dispatch.py` if not already present (check existing imports first — likely already there given other tests use `os`/timing).

- [ ] **Step 6: Run tests to verify they fail**

Run: `pytest tests/test_dispatch.py -v -k "gh_write_verified"`
Expected: FAIL — `_check_job_stall` has no gh-write escape hatch; `gh_write_verified` isn't imported into `dispatch_mod`'s namespace so `monkeypatch.setattr` raises `AttributeError`

- [ ] **Step 7: Add the gh-write escape hatch to `_check_job_stall`**

In `synlynk/dispatch.py`, add the import near the top of the file (alongside other `synlynk.*` imports):

```python
from synlynk.gh_verify import gh_write_verified
```

Then in `_check_job_stall` (synlynk/dispatch.py:517), insert the new check **before** the existing `_inspect_worktree_git_state` escape hatch (right after the `stale_minutes < timeout` early return, i.e. right after this existing block):

```python
    stale_minutes = (time.time() - os.path.getmtime(log_file)) / 60
    if stale_minutes < timeout:
        return False

    if job.get("requires_gh_write"):
        target = job.get("gh_write_target")
        verified = gh_write_verified(target, expect="closed")
        job["gh_write_verified"] = "true" if verified is True else ("false" if verified is False else "unknown")
        if verified is True:
            print(
                f"  Stall check extended for job {job.get('id')}: gh-write target {target} "
                f"verified delivered (ground truth)."
            )
            return False
        if verified is False:
            # Confirmed not delivered — fall through to kill below, skip the git-state
            # escape hatch entirely (spec: "only fall through ... if there's no gh-write
            # target declared"). A job that failed to deliver its GitHub effect should not
            # be kept alive just because it also touched local files.
            pid = job.get("pid")
            if pid:
                try:
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            job["status"] = "failed"
            job["exit_code"] = -1
            job["ended_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            write_alert = _pkg("_write_sentinel_alert", _write_sentinel_alert)
            write_alert(
                "CRITICAL", "STALL_GH_WRITE_UNVERIFIED",
                f"Job {job.get('id')} on agent '{job.get('agent', '')}' stalled and its "
                f"declared gh-write target {target} was confirmed NOT delivered. Process killed.",
                sentinel_path,
            )
            return True
        # verified is None (unknown) — fall through to existing git-state check below.

    inspect_worktree_git_state = _pkg("_inspect_worktree_git_state")
```

This makes `gh_write_verified is True` extend the timeout (ground truth confirms delivery, keep waiting/trust it), `is False` kill immediately without consulting the git-state escape hatch (ground truth confirms non-delivery — local git activity doesn't matter, the effect that was promised didn't happen), and `is None` fall through unchanged to the pre-existing git-state logic.

- [ ] **Step 8: Run tests to verify they pass**

Run: `pytest tests/test_dispatch.py -v -k "gh_write_verified or check_job_stall"`
Expected: all PASS, including the 3 new tests and every pre-existing `_check_job_stall` test (e.g. `test_check_job_stall_uses_review_timeout_without_changing_default` at line 706)

- [ ] **Step 9: Write the failing test for `_reconcile_daemon_jobs`'s terminal-status gh-write check**

```python
# tests/test_jobs.py
def test_reconcile_daemon_jobs_sets_succeeded_gh_write_failed_when_verified_false(project_dir, monkeypatch):
    import synlynk.jobs as jobs_mod
    conn = jobs_mod._get_db()
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, story_id, task, status, pid, enqueued_at, "
        "started_at, log_path, requires_gh_write, gh_write_target) "
        "VALUES ('job-ghw1', 'grok', 'story-1', 'close issue 701', 'running', 999999, "
        "'2026-08-15T00:00:00', '2026-08-15T00:00:00', NULL, 1, 'issue:701')"
    )
    conn.commit()
    conn.close()
    monkeypatch.setattr(jobs_mod, "_pid_is_alive", lambda pid: False)
    monkeypatch.setattr(jobs_mod, "gh_write_verified", lambda target, expect, **kw: False)
    jobs_mod._reconcile_daemon_jobs()
    conn = jobs_mod._get_db()
    row = conn.execute(
        "SELECT status, gh_write_verified FROM daemon_jobs WHERE job_id='job-ghw1'"
    ).fetchone()
    conn.close()
    assert row[0] == "succeeded_gh_write_failed"
    assert row[1] == "false"


def test_reconcile_daemon_jobs_leaves_status_unchanged_when_gh_write_verified_true(project_dir, monkeypatch):
    import synlynk.jobs as jobs_mod
    conn = jobs_mod._get_db()
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, story_id, task, status, pid, enqueued_at, "
        "started_at, log_path, requires_gh_write, gh_write_target) "
        "VALUES ('job-ghw2', 'grok', 'story-1', 'close issue 701', 'running', 999999, "
        "'2026-08-15T00:00:00', '2026-08-15T00:00:00', NULL, 1, 'issue:701')"
    )
    conn.commit()
    conn.close()
    monkeypatch.setattr(jobs_mod, "_pid_is_alive", lambda pid: False)
    monkeypatch.setattr(jobs_mod, "gh_write_verified", lambda target, expect, **kw: True)
    jobs_mod._reconcile_daemon_jobs()
    conn = jobs_mod._get_db()
    row = conn.execute(
        "SELECT status, gh_write_verified FROM daemon_jobs WHERE job_id='job-ghw2'"
    ).fetchone()
    conn.close()
    assert row[0] != "succeeded_gh_write_failed"
    assert row[1] == "true"


def test_reconcile_daemon_jobs_gh_write_verified_null_when_not_requires_gh_write(project_dir, monkeypatch):
    import synlynk.jobs as jobs_mod
    conn = jobs_mod._get_db()
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, story_id, task, status, pid, enqueued_at, "
        "started_at, log_path, requires_gh_write, gh_write_target) "
        "VALUES ('job-ghw3', 'codex', 'story-1', 'refactor thing', 'running', 999999, "
        "'2026-08-15T00:00:00', '2026-08-15T00:00:00', NULL, 0, NULL)"
    )
    conn.commit()
    conn.close()
    monkeypatch.setattr(jobs_mod, "_pid_is_alive", lambda pid: False)
    jobs_mod._reconcile_daemon_jobs()
    conn = jobs_mod._get_db()
    row = conn.execute(
        "SELECT gh_write_verified FROM daemon_jobs WHERE job_id='job-ghw3'"
    ).fetchone()
    conn.close()
    assert row[0] is None
```

Note: match whatever process-liveness/exit-detection stubbing pattern the existing tests around `test_reconcile_daemon_jobs_gtv_uses_files_not_empty_summary` (`tests/test_jobs.py:1223`) already use — if they stub `os.waitpid` instead of `_pid_is_alive`, mirror that instead so the exit-detection branch this test exercises is consistent with the rest of the suite.

- [ ] **Step 10: Run tests to verify they fail**

Run: `pytest tests/test_jobs.py -v -k "gh_write"`
Expected: FAIL — `gh_write_verified` not imported into `jobs_mod`, `succeeded_gh_write_failed` status never set, `gh_write_verified` column never written

- [ ] **Step 11: Wire the check into `_reconcile_daemon_jobs`**

In `synlynk/jobs.py`, add the import near the top:

```python
from synlynk.gh_verify import gh_write_verified
```

Update the SELECT at `synlynk/jobs.py:2049` to include the two new columns:

```python
    rows = conn.execute(
        "SELECT job_id, agent, story_id, task, pid, started_at, completed_at, log_path, "
        "dispatch_context, requires_gh_write, gh_write_target "
        "FROM daemon_jobs WHERE status='running'"
    ).fetchall()
```

Update the unpacking in the `for` loop:

```python
        for (job_id, agent, story_id, task, pid, started_at, completed_at, log_path,
             dispatch_context, requires_gh_write, gh_write_target) in rows:
```

Add a small helper used at both terminal-status branches (place it directly above `_reconcile_daemon_jobs`, right after `_gtv_status_for_daemon_exit`):

```python
def _apply_gh_write_verification(conn, job_id: str, requires_gh_write, gh_write_target: Optional[str], status: str) -> tuple:
    """Consults gh_write_verified for a --requires-gh-write job; returns (status, verified_str).

    verified_str is one of "true"/"false"/"unknown", or None if the job never
    declared --requires-gh-write (not-applicable, distinct from "unknown").
    """
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

Call it at the **first** terminal-status branch (the `preferred is not None` path, right after `status, exit_code = preferred` and before the `UPDATE daemon_jobs SET status=...` a few lines below):

```python
                if preferred is not None:
                    status, exit_code = preferred
                    status, _ = _apply_gh_write_verification(
                        conn, job_id, requires_gh_write, gh_write_target, status
                    )
                    conn.execute(
                        "UPDATE daemon_jobs SET status=?, exit_code=?, completed_at=? "
                        "WHERE job_id=? AND status='running'",
                        (status, exit_code, now, job_id),
                    )
```

And at the **second** terminal-status branch (the main GTV path, right after `status, exit_code, summary_status, summary_note = _gtv_status_for_daemon_exit(...)`):

```python
                status, exit_code, summary_status, summary_note = _gtv_status_for_daemon_exit(
                    exit_code, git_state
                )
                status, _ = _apply_gh_write_verification(
                    conn, job_id, requires_gh_write, gh_write_target, status
                )
```

Both `emit_event("job_terminal", {...})` call sites (one per branch) should include the verification outcome in the payload — add `"gh_write_verified": verified_str` (capture the second return value from `_apply_gh_write_verification` under a per-branch local, e.g. `status, gh_write_verified_str = _apply_gh_write_verification(...)`, then reference `gh_write_verified_str` in that branch's `emit_event(...)` payload dict).

- [ ] **Step 12: Run tests to verify they pass**

Run: `pytest tests/test_jobs.py -v -k "gh_write or reconcile_daemon_jobs"`
Expected: all PASS, including the 3 new tests and every pre-existing `_reconcile_daemon_jobs` test (e.g. the 3 `emit_event`-checking tests at `tests/test_jobs.py:1398-1465+`)

- [ ] **Step 13: Run the full test suite**

Run: `pytest tests/ -x -q`
Expected: all pass (baseline was 1937 passed, 2 skipped per this worktree's last full run — expect that count plus the ~13 new tests added across Tasks 0-1)

- [ ] **Step 14: Commit**

```bash
git add synlynk/gh_verify.py synlynk/dispatch.py synlynk/jobs.py tests/test_gh_verify.py tests/test_dispatch.py tests/test_jobs.py
git commit -m "feat: shared gh_write_verified GTV check wired into stall-kill and terminal reconciliation"
```

**Dispatch routing:** Codex.

---

### Task 2: Surface `gh_write_verified` in `synlynk jobs`/`synlynk logs` output

**Files:**
- Modify: `synlynk/jobs.py:2384` (`cmd_jobs`, the `_render()` inner function, SELECT + header + row formatting)
- Test: `tests/test_jobs.py`

**Prerequisite:** Task 1 (the column must exist and be populated).

- [ ] **Step 1: Write the failing test**

```python
def test_cmd_jobs_shows_gh_write_column_when_present(project_dir, capsys):
    import synlynk.jobs as jobs_mod
    conn = jobs_mod._get_db()
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, story_id, task, status, enqueued_at, "
        "exit_code, requires_gh_write, gh_write_verified) "
        "VALUES ('job-ghw9', 'grok', 'story-1', 'close issues', 'succeeded_gh_write_failed', "
        "'2026-08-15T00:00:00', 0, 1, 'false')"
    )
    conn.commit()
    conn.close()
    jobs_mod.cmd_jobs(all_jobs=True)
    out = capsys.readouterr().out
    assert "GH-WRITE" in out
    assert "job-ghw9" in out
    assert "✗" in out or "false" in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_jobs.py::test_cmd_jobs_shows_gh_write_column_when_present -v`
Expected: FAIL — no `GH-WRITE` column header, `requires_gh_write`/`gh_write_verified` not selected

- [ ] **Step 3: Extend `_render()`'s SELECT, header, and row formatting**

In `synlynk/jobs.py`, inside `cmd_jobs`'s nested `_render()` function (~synlynk/jobs.py:2384+), update the primary SELECT (the one with `context_mode`):

```python
            rows = conn.execute(
                "SELECT job_id, agent, story_id, status, enqueued_at, exit_code, "
                "context_mode, requires_gh_write, gh_write_verified "
                "FROM daemon_jobs ORDER BY enqueued_at DESC LIMIT 50"
            ).fetchall()
```

Leave the `except Exception:` fallback SELECT (the 6-column legacy one) untouched — it already handles pre-migration databases gracefully, and the row-unpacking code below already branches on `len(row) >= 7`. Extend that branching to handle the 9-column case:

```python
            if len(row) >= 9:
                (job_id, agent, story_id, status, enqueued_at, exit_code,
                 ctx_mode, requires_gh_write, gh_write_verified_val) = row[:9]
            elif len(row) >= 7:
                job_id, agent, story_id, status, enqueued_at, exit_code, ctx_mode = row[:7]
                requires_gh_write, gh_write_verified_val = None, None
            else:
                job_id, agent, story_id, status, enqueued_at, exit_code = row[:6]
                ctx_mode = None
                requires_gh_write, gh_write_verified_val = None, None
```

Update the header line to add a `GH-WRITE` column:

```python
        header = (
            f"{'ID':14}  {'AGENT':8}  {'STORY':12}  {'STATUS':10}  "
            f"{'CTX':6}  {'AGE':8}  {'EXIT':4}  GH-WRITE"
        )
```

And the per-row print, computing a display glyph:

```python
            if not requires_gh_write:
                gh_write_display = "—"
            elif gh_write_verified_val == "true":
                gh_write_display = "✓"
            elif gh_write_verified_val == "false":
                gh_write_display = "✗"
            else:
                gh_write_display = "?"
            print(
                f"  {job_id:14}  {agent:8}  {sid:12}  "
                f"{color}{status:10}{_RESET}  {ctx:6}  {age:8}  {exit_str:4}  {gh_write_display}"
            )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_jobs.py::test_cmd_jobs_shows_gh_write_column_when_present -v`
Expected: PASS (adjust the test's `"✗" in out or "false" in out` assertion to just `"✗" in out` once you confirm the glyph renders — keep whichever the implementation actually prints)

- [ ] **Step 5: Run the jobs test file fully**

Run: `pytest tests/test_jobs.py -v`
Expected: all pass, including pre-existing `cmd_jobs`-adjacent tests (search `tests/test_jobs.py` for `def test_cmd_jobs` to confirm none broke on the header/column-count change)

- [ ] **Step 6: Commit**

```bash
git add synlynk/jobs.py tests/test_jobs.py
git commit -m "feat: surface gh_write_verified in synlynk jobs output"
```

**Dispatch routing:** Codex.

---

### Task 3: CI/test guard — every `--requires-gh-write` terminal-status path must consult or document-skip the check

**Files:**
- Create: `tests/test_gh_write_guard.py`

**Prerequisite:** Task 1 landed (the two real call sites exist to be asserted against).

This is a **regression-protection meta-test**: it inspects source, not runtime behavior, so a future PR that adds a 5th terminal-status-deciding code path (or removes the call from an existing one) fails CI immediately instead of silently reintroducing the bug class the spec identified 4 independent instances of.

- [ ] **Step 1: Write the guard test**

```python
# tests/test_gh_write_guard.py
"""Regression guard for the job-truth/gh-write consolidation spec (#701).

Asserts every known terminal-status-deciding code path for a
--requires-gh-write job calls gh_write_verified (or is in the explicit,
reviewed allowlist of documented exceptions). This is a static-source check,
not a runtime behavior check — its job is to fail loudly when a new
terminal-status code path is added without wiring the GTV check, the exact
failure mode #331/#579/#935/#659 each independently exhibited.
"""
import ast
import inspect

import synlynk.dispatch as dispatch_mod
import synlynk.jobs as jobs_mod

# Functions known to decide a job's terminal ("did this succeed") status.
# Any new function added to this pattern-space must be added here explicitly —
# that's the point: the addition should be a deliberate, reviewed decision.
_TERMINAL_STATUS_FUNCTIONS = [
    (dispatch_mod, "_check_job_stall"),
    (jobs_mod, "_reconcile_daemon_jobs"),
]

# Functions explicitly reviewed and confirmed NOT to need gh_write_verified
# (e.g. legacy _reconcile_jobs delegates to _check_job_stall rather than
# deciding terminal status itself). Document the reason inline.
_DOCUMENTED_EXCEPTIONS = {
    # _reconcile_jobs (synlynk/jobs.py) delegates the stall-kill decision to
    # _check_job_stall via _pkg("_check_job_stall")(...) — it does not decide
    # terminal status itself, so it is exempt rather than needing its own call.
}


def _source_calls_name(func, name: str) -> bool:
    source = inspect.getsource(func)
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == name:
            return True
        if isinstance(node, ast.Attribute) and node.attr == name:
            return True
    return False


def test_all_terminal_status_functions_consult_gh_write_verified():
    missing = []
    for module, func_name in _TERMINAL_STATUS_FUNCTIONS:
        if func_name in _DOCUMENTED_EXCEPTIONS:
            continue
        func = getattr(module, func_name)
        if not _source_calls_name(func, "gh_write_verified") and not _source_calls_name(
            func, "_apply_gh_write_verification"
        ):
            missing.append(f"{module.__name__}.{func_name}")
    assert not missing, (
        f"The following terminal-status-deciding functions do not consult "
        f"gh_write_verified for --requires-gh-write jobs: {missing}. "
        f"Either wire in the check, or add a documented, reviewed exception "
        f"to _DOCUMENTED_EXCEPTIONS in this test file with a reason."
    )


def test_guard_itself_fails_when_a_function_skips_the_check():
    """Proves the guard's detection actually works (not a tautology)."""
    def fake_terminal_status_decider(job):
        # Deliberately does NOT call gh_write_verified.
        if job.get("status") == "running":
            return "failed"
        return job.get("status")

    assert not _source_calls_name(fake_terminal_status_decider, "gh_write_verified")
```

- [ ] **Step 2: Run to verify the guard passes against the real (Task 1-modified) codebase**

Run: `pytest tests/test_gh_write_guard.py -v`
Expected: PASS — both `_check_job_stall` and `_reconcile_daemon_jobs` now call `gh_write_verified`/`_apply_gh_write_verification` per Task 1

- [ ] **Step 3: Prove the guard actually catches a regression (manual verification, not committed)**

Temporarily comment out the `if job.get("requires_gh_write"):` block added in Task 1 Step 7 (`synlynk/dispatch.py`), rerun `pytest tests/test_gh_write_guard.py::test_all_terminal_status_functions_consult_gh_write_verified -v`, confirm it now FAILS with the expected assertion message naming `synlynk.dispatch._check_job_stall`. Then revert the temporary edit (`git checkout -- synlynk/dispatch.py`) before continuing — this step is a manual sanity check on the guard's own effectiveness, not a permanent code change.

- [ ] **Step 4: Commit**

```bash
git add tests/test_gh_write_guard.py
git commit -m "test: add regression guard asserting terminal-status paths consult gh_write_verified"
```

**Dispatch routing:** Codex.

---

### Task 4: TC-7 preflight — Agy allow-rules check before routing gh-write tasks to Agy

**Files:**
- Modify: `synlynk/doctor.py` (new `_run_tc7` function + `cmd_doctor()` wiring, following the exact TC-6 pattern at ~synlynk/doctor.py:790 and the orchestration block at ~synlynk/doctor.py:500-620)
- Modify: `synlynk/dispatch.py` (the `requires_gh_write` reroute logic, ~line 1892-1920, to call TC-7 before routing to Agy)
- Test: `tests/test_synlynk.py` (matching where TC-5/TC-6 unit tests already live)
- Test: `tests/test_dispatch.py`

- [ ] **Step 1: Write the failing unit tests for `_run_tc7`**

```python
# tests/test_synlynk.py
def test_run_tc7_passes_when_all_gh_write_allow_rules_present(tmp_path):
    from synlynk.doctor import _run_tc7
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(json.dumps({
        "allowRules": [
            "command(gh pr review)", "command(gh pr comment)", "command(gh pr merge)",
        ]
    }))
    result = _run_tc7(settings_path=str(settings_path))
    assert result["passed"] is True
    assert result["missing"] == []


def test_run_tc7_reports_missing_allow_rules(tmp_path):
    from synlynk.doctor import _run_tc7
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(json.dumps({"allowRules": ["command(gh pr review)"]}))
    result = _run_tc7(settings_path=str(settings_path))
    assert result["passed"] is False
    assert "command(gh pr comment)" in result["missing"]
    assert "command(gh pr merge)" in result["missing"]


def test_run_tc7_missing_settings_file_reports_all_rules_missing(tmp_path):
    from synlynk.doctor import _run_tc7
    result = _run_tc7(settings_path=str(tmp_path / "does-not-exist.json"))
    assert result["passed"] is False
    assert len(result["missing"]) == 3
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_synlynk.py -v -k "run_tc7"`
Expected: FAIL — `ImportError: cannot import name '_run_tc7'`

- [ ] **Step 3: Implement `_run_tc7` in `synlynk/doctor.py`**

Add directly after `_run_tc6` (synlynk/doctor.py, after line ~830), matching its docstring/return-shape style:

```python
_TC7_REQUIRED_ALLOW_RULES = [
    "command(gh pr review)",
    "command(gh pr comment)",
    "command(gh pr merge)",
]


def _run_tc7(settings_path: str = None) -> dict:
    """TC-7: Agy (Gemini antigravity-cli) gh-write allow-rules preflight.

    Routing a --requires-gh-write task to Agy without these scoped allow-rules
    already present in its local settings produces a silent no-op or an
    interactive permission prompt Agy cannot answer headless (#426). This
    check must run BEFORE routing, not after — the failure mode it prevents
    is discovering the gap only once the dispatched job has already burned
    its quota.
    """
    if settings_path is None:
        settings_path = os.path.expanduser("~/.gemini/antigravity-cli/settings.json")
    if not os.path.exists(settings_path):
        return {"passed": False, "missing": list(_TC7_REQUIRED_ALLOW_RULES), "error": "settings file not found"}
    try:
        with open(settings_path) as f:
            settings = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        return {"passed": False, "missing": list(_TC7_REQUIRED_ALLOW_RULES), "error": str(exc)}
    present = set(settings.get("allowRules", []))
    missing = [rule for rule in _TC7_REQUIRED_ALLOW_RULES if rule not in present]
    return {"passed": not missing, "missing": missing, "error": ""}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_synlynk.py -v -k "run_tc7"`
Expected: PASS

- [ ] **Step 5: Wire TC-7 into `cmd_doctor()`'s orchestration block**

In `synlynk/doctor.py`'s `cmd_doctor()` (~line 500-620), following the exact TC-6 print/harness_records pattern, add a TC-7 block after the TC-6 block:

```python
    tc7_result = _run_tc7()
    tc7_status = "✓" if tc7_result["passed"] else "✗"
    print(f"    TC-7 agy-gh-write-preflight: {tc7_status}")
    if not tc7_result["passed"]:
        for rule in tc7_result["missing"]:
            print(f"      missing allow-rule: {rule}")
```

Match this against the real surrounding code at that line range exactly — mirror whatever variable naming (`hard_tcs_passed` aggregation, `harness_records` INSERT columns) TC-6 participates in, adding TC-7 alongside it rather than as a special case.

- [ ] **Step 6: Write the failing test for dispatch-time routing enforcement**

```python
# tests/test_dispatch.py
def test_dispatch_agent_requires_gh_write_blocks_agy_when_tc7_fails(project_dir, monkeypatch, capsys):
    from synlynk import dispatch as dispatch_mod
    monkeypatch.setattr(dispatch_mod, "_run_tc7", lambda: {"passed": False, "missing": ["command(gh pr merge)"], "error": ""})
    with pytest.raises(SystemExit):
        dispatch_mod.dispatch_agent("agy", "review PR 964", force_agent=True, requires_gh_write=True)
    out = capsys.readouterr().out
    assert "TC-7" in out or "allow-rule" in out


def test_dispatch_agent_requires_gh_write_allows_agy_when_tc7_passes(project_dir, monkeypatch):
    from synlynk import dispatch as dispatch_mod
    monkeypatch.setattr(dispatch_mod, "_run_tc7", lambda: {"passed": True, "missing": [], "error": ""})
    _stub_subprocess_success(monkeypatch)
    result = dispatch_mod.dispatch_agent("agy", "review PR 964", force_agent=True, requires_gh_write=True)
    assert result is not None
```

(Match `_stub_subprocess_success` to whichever real fixture name is used elsewhere in this file, as in Task 0 Step 5.)

- [ ] **Step 7: Run tests to verify they fail**

Run: `pytest tests/test_dispatch.py -v -k "tc7"`
Expected: FAIL — `dispatch_agent` never imports or calls `_run_tc7`

- [ ] **Step 8: Wire the TC-7 preflight into `dispatch_agent`'s reroute logic**

In `synlynk/dispatch.py`, add the import:

```python
from synlynk.doctor import _run_tc7
```

In `dispatch_agent` (~line 1892-1920, the `requires_gh_write` reroute block), before allowing dispatch to proceed with `agent == "agy"` under `--requires-gh-write` (whether routed there originally or via reroute), insert:

```python
    if requires_gh_write and agent == "agy":
        tc7_result = _run_tc7()
        if not tc7_result["passed"]:
            print(
                f"  ✗ TC-7 preflight failed: Agy is missing required gh-write allow-rules: "
                f"{', '.join(tc7_result['missing'])}"
            )
            print(
                "    Configure ~/.gemini/antigravity-cli/settings.json with these allowRules, "
                "or dispatch to a different agent (Codex/Grok)."
            )
            raise SystemExit(1)
```

Place this check at the point in the function where `agent` has already been resolved to its final value (post-reroute, post-`--force-agent` override) but before the subprocess is actually spawned — match the existing code structure at that point exactly (read the surrounding ~30 lines before inserting to find the right spot, since the summary's line estimate may drift slightly after Task 0/1's edits).

- [ ] **Step 9: Run tests to verify they pass**

Run: `pytest tests/test_dispatch.py -v -k "tc7"`
Expected: PASS

- [ ] **Step 10: Run full dispatch + doctor test files**

Run: `pytest tests/test_dispatch.py tests/test_synlynk.py -v`
Expected: all pass, no regressions in pre-existing `requires_gh_write` reroute tests (lines 929-994)

- [ ] **Step 11: Commit**

```bash
git add synlynk/doctor.py synlynk/dispatch.py tests/test_synlynk.py tests/test_dispatch.py
git commit -m "feat: TC-7 Agy gh-write allow-rules preflight, enforced before routing"
```

**Dispatch routing:** Codex.

---

### Task 5: Route Codex's PR-review gh-write step through `gh` CLI instead of MCP tools

**Files:**
- Modify: whichever file constructs Codex's review-task prompt/tooling config — locate via `grep -rn "add_review_to_pr\|add_comment_to_issue" synlynk/` before starting (not yet located in this plan's research; the implementer must find it first, it is expected to be in `synlynk/dispatch.py` or a prompt-template constant near where review tasks are dispatched)
- Test: matching test file for whichever module is found

**Prerequisite:** none (independent of Tasks 0-4).

- [ ] **Step 1: Locate the MCP tool references**

```bash
grep -rn "add_review_to_pr\|add_comment_to_issue" synlynk/ docs/
```

Read every file this returns in full before making changes — the spec's action item 5 states these MCP tools have a 4/4 confirmed failure rate for Codex's PR-review write step, so the fix is to change the *instructions Codex is given* (a prompt template, task-description constant, or config value), not application logic. If the references turn out to live in a prompt string embedded in `dispatch_agent()`'s review-task-type branch, edit that string directly.

- [ ] **Step 2: Write the failing test asserting the CLI form is used**

The exact test depends on what Step 1 finds. If it's a prompt-template string constant, e.g. `REVIEW_TASK_INSTRUCTIONS` in `synlynk/dispatch.py`:

```python
def test_review_task_instructions_use_gh_cli_not_mcp_tools():
    from synlynk.dispatch import REVIEW_TASK_INSTRUCTIONS  # adjust name to what Step 1 finds
    assert "add_review_to_pr" not in REVIEW_TASK_INSTRUCTIONS
    assert "add_comment_to_issue" not in REVIEW_TASK_INSTRUCTIONS
    assert "gh pr review" in REVIEW_TASK_INSTRUCTIONS
    assert "gh pr comment" in REVIEW_TASK_INSTRUCTIONS
```

If instead it's a runtime code path building an MCP tool call, write a test asserting `subprocess.run(["gh", "pr", "review", ...])` (or `"gh pr comment"`) is invoked and no MCP client method is called, following whatever mocking pattern the surrounding test file already uses for subprocess assertions.

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest <located-test-file> -v -k "review_task_instructions or gh_cli"`
Expected: FAIL against current MCP-tool-referencing content

- [ ] **Step 4: Replace the MCP tool references with `gh` CLI instructions/calls**

If a prompt string: replace instructions like "use the `add_review_to_pr` tool to submit your review" with "run `gh pr review <N> --approve --body '...'` (or `--request-changes`/`--comment`) via the shell to submit your review; run `gh pr comment <N> --body '...'` for standalone comments — do NOT use any MCP GitHub tool for this step."

If a runtime code path: replace the MCP client call with `subprocess.run(["gh", "pr", "review", str(pr_number), "--approve", "--body", body], ...)` (or the appropriate review-decision flag), matching this repo's existing subprocess-invocation conventions (e.g. `capture_output=True, text=True, timeout=...` as seen in `synlynk/worktree.py:174`'s `gh auth status` call).

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest <located-test-file> -v -k "review_task_instructions or gh_cli"`
Expected: PASS

- [ ] **Step 6: Run the full file's test suite for regressions**

Run: `pytest <located-test-file> -v`
Expected: all pass

- [ ] **Step 7: Commit**

```bash
git add <modified-file> <test-file>
git commit -m "fix: route Codex PR-review gh-write through gh CLI instead of MCP tools (#701)"
```

**Dispatch routing:** Codex (code/CLI-plumbing task, despite touching prompt text — this is still an implementation change to how a dispatched task is instructed, not a GitHub-issue-only write).

---

### Task 6: Close #331 and #579; confirm/add reconciliation parity regression test

**Files:**
- Test: `tests/test_jobs.py` (parity test between `_reconcile_daemon_jobs` and legacy `_reconcile_jobs`, if not already present)

**Prerequisite:** none — independent of code tasks, but should reference Task 1's PR once merged for the close comment's evidence trail.

- [ ] **Step 1: Search for an existing parity test**

```bash
grep -n "def test.*parity\|def test.*reconcile.*legacy\|def test.*reconcile.*daemon.*match" tests/test_jobs.py
```

- [ ] **Step 2: If none exists, write it**

```python
def test_reconcile_daemon_jobs_and_reconcile_jobs_agree_on_terminal_status(project_dir, monkeypatch, tmp_path):
    """Parity regression test for #331/#579: both reconciliation mechanisms
    must reach the same terminal status for equivalent job evidence (real
    git activity, non-zero exit) — this is the scenario where they
    historically diverged (daemon path GTV'd, legacy path didn't)."""
    import synlynk.jobs as jobs_mod

    git_state = {"has_activity": True, "commits_ahead": 2, "dirty": False, "changed_files": ["a.py"]}
    monkeypatch.setattr(jobs_mod, "_inspect_worktree_git_state", lambda *a, **kw: git_state)
    monkeypatch.setattr(jobs_mod, "_daemon_job_worktree_path", lambda *a, **kw: "/tmp/fake-wt")
    monkeypatch.setattr(jobs_mod, "_pid_is_alive", lambda pid: False)

    conn = jobs_mod._get_db()
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, story_id, task, status, pid, enqueued_at, "
        "started_at, log_path) VALUES ('job-parity1', 'codex', 'story-1', 'implement thing', "
        "'running', 999999, '2026-08-15T00:00:00', '2026-08-15T00:00:00', NULL)"
    )
    conn.commit()
    conn.close()
    jobs_mod._reconcile_daemon_jobs()
    conn = jobs_mod._get_db()
    daemon_status = conn.execute(
        "SELECT status FROM daemon_jobs WHERE job_id='job-parity1'"
    ).fetchone()[0]
    conn.close()

    from synlynk import dispatch as dispatch_mod
    legacy_job = {
        "id": "job-parity1-legacy", "status": "running", "agent": "codex",
        "log_file": str(tmp_path / "job.log"), "pid": None,
        "worktree_path": "/tmp/fake-wt", "worktree_branch": "dispatch/codex/job-parity1-legacy",
        "started_at": "2026-08-15T00:00:00",
    }
    (tmp_path / "job.log").write_text("output")
    import os as _os
    old_mtime = __import__("time").time() - 3600
    _os.utime(tmp_path / "job.log", (old_mtime, old_mtime))
    monkeypatch.setattr(dispatch_mod, "_inspect_worktree_git_state", lambda *a, **kw: git_state)
    stalled = dispatch_mod._check_job_stall(legacy_job, {"stall_timeout_minutes": 30}, str(tmp_path / "sentinel.md"))

    # Both mechanisms see real git activity (has_activity=True) — neither should
    # discard the job as a bare failure/unknown; the daemon path GTVs it into a
    # non-"unknown", non-bare-"failed" status, and the legacy path extends the
    # timeout rather than killing (returns False = not stalled).
    assert daemon_status not in ("unknown", "failed")
    assert stalled is False
```

- [ ] **Step 3: Run to verify it passes against current code**

Run: `pytest tests/test_jobs.py::test_reconcile_daemon_jobs_and_reconcile_jobs_agree_on_terminal_status -v`
Expected: PASS (both mechanisms already apply GTV correctly per the spec's finding that #331/#579's fixes are real and present — this test documents/locks in that parity rather than fixing new behavior)

- [ ] **Step 4: Commit the test if newly added**

```bash
git add tests/test_jobs.py
git commit -m "test: lock in reconcile_daemon_jobs / check_job_stall GTV parity (#331, #579)"
```

- [ ] **Step 5: Close #331 and #579 on GitHub**

This step is a GitHub-issue-only write — dispatch it separately from the code task above (it has no code dependency and can run anytime). Dispatch prompt for Grok (default per this repo's GH-write routing rule; Agy documented fallback if Grok fails per memory `feedback_grok_auth_agy_fallback`):

> Task: Close GitHub issues #331 and #579 in this repo. Both were fixed by PR #867 (ground-truth verification for `_reconcile_daemon_jobs`, applying git-worktree-state evidence instead of trusting bare exit codes). Post a closing comment on each referencing PR #867 and noting that `tests/test_jobs.py::test_reconcile_daemon_jobs_and_reconcile_jobs_agree_on_terminal_status` (added in the job-truth/gh-write consolidation PR) now locks in the parity between `_reconcile_daemon_jobs` and legacy `_reconcile_jobs` that these issues originally reported as broken. Use `gh issue close 331 --comment "..."` and `gh issue close 579 --comment "..."` (per this repo's Task 5 finding, prefer direct `gh` CLI over any MCP issue-write tool). Requires `--requires-gh-write`.

Command: `python3 bin/synlynk.py dispatch grok --task "<above>" --force-agent --requires-gh-write --context-mode full`

**Dispatch routing:** Test/parity-lock task → Codex. Issue-close task → Grok (`--requires-gh-write`), Agy fallback.

---

### Task 7: Retitle/refocus #426 onto the routing-precondition gap

**Files:** none (GitHub-issue-only, no code).

**Prerequisite:** Task 4 (TC-7) should ideally be merged first so the retitled issue can reference the actual fix, but this can also run independently and be updated with the PR link after the fact — not a hard blocker.

- [ ] **Step 1: Dispatch the retitle/refocus task**

Dispatch prompt for Grok:

> Task: Retitle and refocus GitHub issue #426 in this repo. Its current framing is "Agy cannot do gh-write headless" — investigation (documented in `docs/superpowers/specs/2026-08-15-job-truth-gh-write-consolidation-design.md`, section on issue dispositions) found this framing is stale: Agy CAN complete `gh pr review`/`gh pr comment`/`gh pr merge` headless once its local `~/.gemini/antigravity-cli/settings.json` has the required scoped `command(gh pr review)` etc. allow-rules configured — the actual gap is that synlynk never verified that precondition before routing a gh-write task to Agy, so failures looked like "Agy can't do this" when the real issue was "nobody checked first." Retitle the issue to reflect this (e.g. "Verify Agy gh-write allow-rules before routing, don't assume capability or incapability") and post a comment explaining the reframing, linking to the TC-7 preflight check (added in `synlynk/doctor.py` `_run_tc7`, this repo's job-truth/gh-write consolidation work, closing PR reference: <fill in Task 4's PR number/link once merged>) as the actual fix. Do not close the issue — TC-7 addresses detection/prevention, but the issue's new framing (routing-precondition verification) is the durable tracking artifact for this class of gap. Use `gh issue edit 426 --title "..."` and `gh issue comment 426 --body "..."`. Requires `--requires-gh-write`.

Command: `python3 bin/synlynk.py dispatch grok --task "<above>" --force-agent --requires-gh-write --context-mode full`

**Dispatch routing:** Grok (`--requires-gh-write`), Agy fallback.

---

### Task 8: Final independent verification; close #935 and #701

**Files:** none (verification + GitHub writes).

**Prerequisite:** Tasks 1-5 merged to the branch's base (or to `main`, depending on merge strategy chosen at execution time).

This task is performed by Claude directly — dispatching a fresh reviewer job and inspecting its outcome is PM/review work per this repo's role split, not implementation.

- [ ] **Step 1: Dispatch a fresh reviewer job (not code inspection or self-report)**

```bash
python3 bin/synlynk.py dispatch codex --task "Review the job-truth/gh-write consolidation implementation on branch chore/job-truth-gh-write-consolidation (or its merged state on main, whichever is current). Verify independently — do not trust the implementer's self-report or commit messages alone: (1) run 'pytest tests/test_gh_verify.py tests/test_gh_write_guard.py tests/test_dispatch.py tests/test_jobs.py tests/test_synlynk.py -v' and confirm all pass; (2) manually trigger the test_gh_write_guard.py regression check against a deliberately-broken copy of _check_job_stall (comment out its gh_write_verified block) and confirm the guard test fails as designed; (3) run 'synlynk doctor' and confirm TC-7 appears in output; (4) grep for 'add_review_to_pr\|add_comment_to_issue' across synlynk/ and confirm zero remaining references. Report PASS/FAIL for each of the 4 checks with actual command output, not summaries." --force-agent --context-mode full
```

- [ ] **Step 2: Inspect the reviewer job's actual log output**

```bash
synlynk logs --job <job-id-from-step-1>
```

Do not accept a "looks good" summary — confirm the 4 checks in the dispatch prompt each show real command output with the expected result, per this repo's memory (`feedback.md`: "verify PR fixes via direct test run not CI/description").

- [ ] **Step 3: If all 4 checks pass, close #935 and #701 together**

Dispatch to Grok (issue-only write, `--requires-gh-write`):

> Task: Close GitHub issues #935 and #701 in this repo together. Both are resolved by the job-truth/gh-write consolidation work: #701 was the original consolidation request; #935 was the `_check_job_stall` review-timeout failure mode identified as structurally distinct from #331/#579 (not a recurrence) during investigation, now fixed by the shared `gh_write_verified` GTV check wired into `_check_job_stall`'s escape hatch. Post a single comment on each citing: the implementation PR (<fill in from Task 1-5's actual merged PR number/link>), the independent verification job (<job-id from Task 8 Step 1>) and its 4/4 PASS result, and the regression guard test `tests/test_gh_write_guard.py` that prevents this bug class from recurring on a 5th code path. Use `gh issue close 935 --comment "..."` and `gh issue close 701 --comment "..."`.

Command: `python3 bin/synlynk.py dispatch grok --task "<above>" --force-agent --requires-gh-write --context-mode full`

- [ ] **Step 4: If any check fails, do not close the issues**

Instead: file the failure as a new finding (issue comment on #701, not closure), identify which of Tasks 1-5 needs rework, and re-dispatch that task's fix before re-attempting Step 1's verification job.

**Dispatch routing:** Verification (Steps 1-2) → Claude directly. Issue closure (Step 3) → Grok (`--requires-gh-write`), Agy fallback.

---

## Sequencing Summary

| Task | Depends on | Parallelizable with |
|---|---|---|
| 0 (schema) | — | — (must land first) |
| 1 (shared helper + call sites) | 0 | — |
| 2 (jobs/logs surfacing) | 1 | 4, 5 |
| 3 (CI guard) | 1 | 2, 4, 5 |
| 4 (TC-7 preflight) | — | 0, 1, 2, 3, 5 |
| 5 (Codex CLI routing) | — | 0, 1, 2, 3, 4 |
| 6 (parity test + close #331/#579) | — (test) / 1 (issue close references it) | everything |
| 7 (retitle #426) | — (ideally after 4 merges) | everything |
| 8 (final verify + close #935/#701) | 1, 2, 3, 4, 5 merged | — (final gate) |

Tasks 0→1→2/3 form the tightly-coupled sequential cluster (same files, same shared helper). Tasks 4 and 5 touch entirely different files (`synlynk/doctor.py` + dispatch routing logic vs. wherever Task 5's prompt/tooling config lives) and have no shared state with 0-3 — dispatch them in parallel with the 0-3 cluster. Tasks 6 and 7 are GitHub-issue-only and can run at any point, though their comment text reads better once the code tasks they cite have actually merged. Task 8 is the hard final gate.
