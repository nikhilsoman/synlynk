# Harness-Internal-Timeout Detection & Stall-Check Generalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tag dispatched jobs that die from the `agy` CLI's own internal ~500-600s response timeout with a distinct `HARNESS_INTERNAL_TIMEOUT` sentinel alert (instead of being indistinguishable from a genuine task failure), and generalize `_check_job_stall()` so it can catch a job whose log has gone stale, not just one whose log is still completely empty.

**Architecture:** Part 1 adds a new phrase-list constant (`HARNESS_TIMEOUT_PATTERNS`, mirroring the existing `QUOTA_PATTERNS` convention) and one new detection block inside `_reconcile_jobs()`'s dead-process branch. Part 2 replaces `_check_job_stall()`'s `os.path.getsize(log_file) > 0` early-exit with an `os.path.getmtime()`-based staleness check, reusing the existing `stall_timeout_minutes` config value — no new config knob. Part 2 also requires updating two pre-existing tests whose empty-log-file fixtures relied on the old `started_at`-based gating and would otherwise silently break under the new mtime-based gating.

**Tech Stack:** Python 3 stdlib (`os.path.getmtime`, `os.utime`), pytest (existing `tests/test_agy_dispatch_fix.py` and `tests/test_synlynk.py` conventions).

**Tracks:** [#162](https://github.com/nikhilsoman/synlynk/issues/162). Full design: `docs/superpowers/specs/2026-07-11-harness-timeout-detection-design.md`.

---

### Task 1: Detect and tag the harness-internal-timeout signature

**Files:**
- Modify: `synlynk/_constants.py` (new constant, alongside `QUOTA_PATTERNS`)
- Modify: `synlynk/__init__.py` (`_reconcile_jobs()`, `except ProcessLookupError:` branch)
- Test: `tests/test_agy_dispatch_fix.py`

Current code at `synlynk/_constants.py:9-13`:

```python
QUOTA_PATTERNS = [
    "rate limit", "quota exceeded", "resource exhausted", "billing",
    "insufficient_quota", "too many requests", "RESOURCE_EXHAUSTED",
]
```

- [ ] **Step 1: Add `HARNESS_TIMEOUT_PATTERNS` constant**

Edit `synlynk/_constants.py`. Immediately after the `QUOTA_PATTERNS` list (line 13), add:

```python

HARNESS_TIMEOUT_PATTERNS = [
    "timeout waiting for response",
]
```

- [ ] **Step 2: Write the failing test — harness-timeout tagging on job reconciliation**

Read `tests/test_agy_dispatch_fix.py`'s existing `_dispatch_git_worktree_job` helper and the test immediately preceding the stall tests (`test_dispatch_gitstateverified_job_reconciliation_missing_exit_clean_worktree_remains_failed`, lines 495-508) for the exact fixture/mocking pattern this test follows — it dispatches a job via `_dispatch_git_worktree_job(monkeypatch)`, which already sets up a `git_worktree_repo` fixture, mocks `os.kill` to raise `ProcessLookupError` (dead process), and calls `sl._reconcile_jobs()`.

Add to `tests/test_agy_dispatch_fix.py`, immediately after `test_dispatch_gitstateverified_job_reconciliation_missing_exit_clean_worktree_remains_failed` (after line 508, before the stall tests):

```python
def test_dispatch_gitstateverified_job_reconciliation_tags_harness_internal_timeout(git_worktree_repo, monkeypatch, capsys):
    import synlynk as sl

    job = _dispatch_git_worktree_job(monkeypatch)
    with open(job["log_file"], "a") as f:
        f.write("some output\nError: timeout waiting for response\n")

    sl._reconcile_jobs()
    jobs = sl._load_jobs()
    reconciled = next(j for j in jobs if j["id"] == job["id"])

    assert reconciled["status"] == "failed"
    sentinel_content = open(".synlynk/sentinel.md").read()
    assert "HARNESS_INTERNAL_TIMEOUT" in sentinel_content
    assert job["id"] in sentinel_content
    assert "timeout waiting for response" in sentinel_content
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python3 -m pytest tests/test_agy_dispatch_fix.py::test_dispatch_gitstateverified_job_reconciliation_tags_harness_internal_timeout -v`

Expected: FAIL — `assert "HARNESS_INTERNAL_TIMEOUT" in sentinel_content` fails, since no such alert is written today.

- [ ] **Step 4: Implement the fix**

Read `synlynk/__init__.py` around `_reconcile_jobs()`'s `except ProcessLookupError:` branch (~lines 3198-3236) to find the exact line where `log_text` is read (~lines 3230-3232, right before `_extract_micro_rework`/`_write_capability_rating` are called). It reads roughly as:

```python
                log_text = ""
                if job.get("log_file") and os.path.exists(job["log_file"]):
                    with open(job["log_file"]) as f:
                        log_text = f.read()
```

Immediately after that block (still inside the `except ProcessLookupError:` branch, before the `_extract_micro_rework`/`_write_capability_rating` calls), add:

```python
                if job.get("status") != "completed":
                    log_text_lower = log_text.lower()
                    for phrase in HARNESS_TIMEOUT_PATTERNS:
                        if phrase in log_text_lower:
                            _write_sentinel_alert(
                                "CRITICAL", "HARNESS_INTERNAL_TIMEOUT",
                                f"Job {job.get('id')} on agent '{job.get('agent')}' died from an "
                                f"internal harness timeout (matched \"{phrase}\"), not a task "
                                "failure. Consider retrying.",
                                sentinel_path,
                            )
                            break
```

`HARNESS_TIMEOUT_PATTERNS` must be imported. Find the existing import of `QUOTA_PATTERNS` (or wherever `_constants` names are imported) at the top of `synlynk/__init__.py` and add `HARNESS_TIMEOUT_PATTERNS` to the same import line/block.

`_write_sentinel_alert` is already imported into `synlynk/__init__.py` (confirmed present) — no new import needed for it. Confirm the local variable name `sentinel_path` matches what's already in scope in that branch (it's used by the existing `STALL_NO_OUTPUT`/`HANDOFF_PENDING` alert calls elsewhere in this file — use the same name already in scope at this point in `_reconcile_jobs()`).

- [ ] **Step 5: Run test to verify it passes**

Run: `python3 -m pytest tests/test_agy_dispatch_fix.py::test_dispatch_gitstateverified_job_reconciliation_tags_harness_internal_timeout -v`

Expected: PASS

- [ ] **Step 6: Run the full test file to confirm no regressions**

Run: `python3 -m pytest tests/test_agy_dispatch_fix.py -v`

Expected: All pass (no pre-existing failures in this file).

- [ ] **Step 7: Commit**

```bash
git add synlynk/_constants.py synlynk/__init__.py tests/test_agy_dispatch_fix.py
git commit -m "feat(dispatch): tag jobs killed by agy's internal timeout with HARNESS_INTERNAL_TIMEOUT

Three independent rxcc Agy dispatch failures all died with the
identical 'Error: timeout waiting for response' at unrelated task
stages (~500-600s), pointing to a fixed-duration timeout inside the
agy binary itself. _reconcile_jobs() previously marked these jobs
'failed' identically to a genuine task failure, with no signal
distinguishing 'harness gave up on itself' from 'agent failed the
task'. Mirrors the existing QUOTA_PATTERNS detection convention.

Refs #162"
```

### Task 2: Generalize `_check_job_stall` from \"log is empty\" to \"log stopped advancing\"

**Files:**
- Modify: `synlynk/dispatch.py:191-262` (`_check_job_stall`)
- Modify (fixture fix, not behavior): `tests/test_agy_dispatch_fix.py` (two pre-existing tests)
- Test: `tests/test_agy_dispatch_fix.py` (two new tests)

Current code at `synlynk/dispatch.py:191-262`:

```python
def _check_job_stall(job: dict, config: dict, sentinel_path: str) -> bool:
    """Returns True if job was stalled and killed."""
    if job.get("status") != "running":
        return False
    log_file = job.get("log_file", "")
    if not log_file or not os.path.exists(log_file):
        return False
    if os.path.getsize(log_file) > 0:
        return False

    agent = job.get("agent", "")
    global_timeout = config.get("stall_timeout_minutes", 30)
    timeout = config.get("agents", {}).get(agent, {}).get("stall_timeout_minutes", global_timeout)

    started_val = job.get("started_at")
    if isinstance(started_val, str):
        try:
            import datetime as _dt
            started_ts = _dt.datetime.strptime(started_val, "%Y-%m-%dT%H:%M:%S").timestamp()
        except Exception:
            started_ts = time.time()
    elif isinstance(started_val, (int, float)):
        started_ts = started_val
    else:
        started_ts = time.time()

    elapsed_minutes = (time.time() - started_ts) / 60
    if elapsed_minutes < timeout:
        return False

    inspect_worktree_git_state = _pkg("_inspect_worktree_git_state")
    git_state = inspect_worktree_git_state(job.get("worktree_path")) if inspect_worktree_git_state else None
    if git_state and git_state.get("has_activity"):
        worktree_path = job.get("worktree_path")
        commit_count = git_state.get("commits_ahead", 0)
        dirty = git_state.get("dirty", False)
        parts = []
        if commit_count:
            parts.append(f"{commit_count} commit(s)")
        if dirty:
            parts.append("uncommitted changes")
        details = " and ".join(parts) if parts else "git activity"
        print(
            f"  Stall check extended for job {job.get('id')}: git activity detected in "
            f"{worktree_path} ({details})."
        )
        return False

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
        "CRITICAL", "STALL_NO_OUTPUT",
        f"Job {job.get('id')} on agent '{agent}' stalled with zero output after {timeout}min. Process killed.",
        sentinel_path,
    )
    write_alert(
        "WARN", "HANDOFF_PENDING",
        f"Job {job.get('id')} on agent '{agent}' is awaiting handoff to another agent.",
        sentinel_path,
    )
    return True
```

- [ ] **Step 1: Write the failing tests — stale non-empty log is caught, fresh non-empty log is not**

Add to `tests/test_agy_dispatch_fix.py`, immediately after `test_dispatch_gitstateverified_job_stall_clean_worktree_still_kills` (after line 561):

```python
def test_dispatch_gitstateverified_job_stall_stale_nonempty_log_still_kills(git_worktree_repo, monkeypatch, tmp_path):
    import time
    import signal
    import synlynk as sl

    job = _dispatch_git_worktree_job(monkeypatch)
    log_file = tmp_path / f"{job['id']}.log"
    log_file.write_text("some output\n")
    old_time = time.time() - 7200
    os.utime(log_file, (old_time, old_time))
    job["log_file"] = str(log_file)
    job["started_at"] = old_time

    killed = []

    def fake_kill(pid, sig):
        killed.append((pid, sig))

    monkeypatch.setattr(sl.os, "kill", fake_kill)

    result = sl._check_job_stall(job, {"stall_timeout_minutes": 30}, ".synlynk/sentinel.md")

    assert result is True
    assert job["status"] == "failed"
    assert killed == [(job["pid"], signal.SIGKILL)]


def test_dispatch_gitstateverified_job_stall_fresh_nonempty_log_not_killed(git_worktree_repo, monkeypatch, tmp_path):
    import time
    import synlynk as sl

    job = _dispatch_git_worktree_job(monkeypatch)
    log_file = tmp_path / f"{job['id']}.log"
    log_file.write_text("some output\n")
    job["log_file"] = str(log_file)
    job["started_at"] = time.time() - 7200

    killed = []

    def fake_kill(pid, sig):
        killed.append((pid, sig))

    monkeypatch.setattr(sl.os, "kill", fake_kill)

    result = sl._check_job_stall(job, {"stall_timeout_minutes": 30}, ".synlynk/sentinel.md")

    assert result is False
    assert job["status"] == "running"
    assert killed == []
```

`import os` is already present at the top of `tests/test_agy_dispatch_fix.py` (used elsewhere in the file, e.g. `os.makedirs`) — no new import needed for `os.utime`.

- [ ] **Step 2: Run new tests to verify they fail**

Run: `python3 -m pytest tests/test_agy_dispatch_fix.py::test_dispatch_gitstateverified_job_stall_stale_nonempty_log_still_kills tests/test_agy_dispatch_fix.py::test_dispatch_gitstateverified_job_stall_fresh_nonempty_log_not_killed -v`

Expected: `test_..._stale_nonempty_log_still_kills` FAILS (`assert result is True` fails — current code's `os.path.getsize(log_file) > 0: return False` bails out immediately since the log has content, so `result` is currently `False`). `test_..._fresh_nonempty_log_not_killed` PASSES already (it asserts `False`, which the current code already returns for a non-empty log) — this is expected; it's a regression guard for after the rewrite, not a new-behavior test.

- [ ] **Step 3: Implement the mtime-based staleness rewrite**

Edit `synlynk/dispatch.py`. Replace the full `_check_job_stall` function body (lines 191-262 as shown above) with:

```python
def _check_job_stall(job: dict, config: dict, sentinel_path: str) -> bool:
    """Returns True if job was stalled and killed."""
    if job.get("status") != "running":
        return False
    log_file = job.get("log_file", "")
    if not log_file or not os.path.exists(log_file):
        return False

    agent = job.get("agent", "")
    global_timeout = config.get("stall_timeout_minutes", 30)
    timeout = config.get("agents", {}).get(agent, {}).get("stall_timeout_minutes", global_timeout)

    stale_minutes = (time.time() - os.path.getmtime(log_file)) / 60
    if stale_minutes < timeout:
        return False

    inspect_worktree_git_state = _pkg("_inspect_worktree_git_state")
    git_state = inspect_worktree_git_state(job.get("worktree_path")) if inspect_worktree_git_state else None
    if git_state and git_state.get("has_activity"):
        worktree_path = job.get("worktree_path")
        commit_count = git_state.get("commits_ahead", 0)
        dirty = git_state.get("dirty", False)
        parts = []
        if commit_count:
            parts.append(f"{commit_count} commit(s)")
        if dirty:
            parts.append("uncommitted changes")
        details = " and ".join(parts) if parts else "git activity"
        print(
            f"  Stall check extended for job {job.get('id')}: git activity detected in "
            f"{worktree_path} ({details})."
        )
        return False

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
        "CRITICAL", "STALL_NO_OUTPUT",
        f"Job {job.get('id')} on agent '{agent}' stalled with zero output after {timeout}min. Process killed.",
        sentinel_path,
    )
    write_alert(
        "WARN", "HANDOFF_PENDING",
        f"Job {job.get('id')} on agent '{agent}' is awaiting handoff to another agent.",
        sentinel_path,
    )
    return True
```

The only changes: the `os.path.getsize(log_file) > 0: return False` line is removed; the `agent`/`global_timeout`/`timeout` computation is unchanged but now runs before the staleness gate; the `started_val`/`started_ts`/`elapsed_minutes` block is removed entirely and replaced by `stale_minutes = (time.time() - os.path.getmtime(log_file)) / 60`. Everything from `inspect_worktree_git_state = _pkg(...)` onward is byte-for-byte identical to the original.

- [ ] **Step 4: Run the two new tests to verify they now pass**

Run: `python3 -m pytest tests/test_agy_dispatch_fix.py::test_dispatch_gitstateverified_job_stall_stale_nonempty_log_still_kills tests/test_agy_dispatch_fix.py::test_dispatch_gitstateverified_job_stall_fresh_nonempty_log_not_killed -v`

Expected: Both PASS.

- [ ] **Step 5: Run the two pre-existing stall tests — confirm the expected regression**

Run: `python3 -m pytest tests/test_agy_dispatch_fix.py::test_dispatch_gitstateverified_job_stall_git_activity_defers_kill tests/test_agy_dispatch_fix.py::test_dispatch_gitstateverified_job_stall_clean_worktree_still_kills -v`

Expected: `test_dispatch_gitstateverified_job_stall_clean_worktree_still_kills` FAILS (`assert result is True` fails). Both tests create an **empty** log file at test-run time (fresh mtime, "just now") while setting `job["started_at"]` to 2 hours in the past to simulate an old job. Under the old `started_at`-gated logic this correctly simulated staleness; under the new mtime-based logic, the freshly-created empty log's mtime is "just now," so `stale_minutes ≈ 0 < 30`, and the function now returns `False` before ever reaching the kill logic — a fixture bug, not a design flaw, since these tests no longer exercise the scenario they were written to test (a job whose log has gone stale). `test_dispatch_gitstateverified_job_stall_git_activity_defers_kill` may still incidentally pass (both old and new logic return `False`, just via different gates), but its fixture has the same staleness bug and must be fixed for the same reason — do not skip it.

- [ ] **Step 6: Fix the two pre-existing tests' fixtures to set log-file mtime into the past**

Edit `tests/test_agy_dispatch_fix.py`. In `test_dispatch_gitstateverified_job_stall_git_activity_defers_kill` (around line 511-536), after the log file is created, add an `os.utime()` call setting its mtime to match the existing `started_at` staleness (2 hours ago):

Replace:

```python
    log_file = tmp_path / f"{job['id']}.log"
    with open(log_file, "wb"):
        pass
    job["log_file"] = str(log_file)
    job["started_at"] = time.time() - 7200
```

with:

```python
    log_file = tmp_path / f"{job['id']}.log"
    with open(log_file, "wb"):
        pass
    old_time = time.time() - 7200
    os.utime(log_file, (old_time, old_time))
    job["log_file"] = str(log_file)
    job["started_at"] = old_time
```

In `test_dispatch_gitstateverified_job_stall_clean_worktree_still_kills` (around line 538-561), apply the identical change:

Replace:

```python
    log_file = tmp_path / f"{job['id']}.log"
    with open(log_file, "wb"):
        pass
    job["log_file"] = str(log_file)
    job["started_at"] = time.time() - 7200
```

with:

```python
    log_file = tmp_path / f"{job['id']}.log"
    with open(log_file, "wb"):
        pass
    old_time = time.time() - 7200
    os.utime(log_file, (old_time, old_time))
    job["log_file"] = str(log_file)
    job["started_at"] = old_time
```

`job["started_at"]` is kept (unused by the new `_check_job_stall` logic, but other code paths such as `_reconcile_jobs()` may still read it, and removing it is out of scope for this fix — only the mtime addition is required).

- [ ] **Step 7: Run the two pre-existing tests again to confirm they pass**

Run: `python3 -m pytest tests/test_agy_dispatch_fix.py::test_dispatch_gitstateverified_job_stall_git_activity_defers_kill tests/test_agy_dispatch_fix.py::test_dispatch_gitstateverified_job_stall_clean_worktree_still_kills -v`

Expected: Both PASS.

- [ ] **Step 8: Confirm `tests/test_synlynk.py::test_stall_detection_writes_handoff_pending` still passes unmodified**

This test (`tests/test_synlynk.py:442-464`) uses `config={"stall_timeout_minutes": 0}` and writes an empty log file via `log_file.write_text("")` (fresh mtime at test-run time), with `job["started_at"]` set to ~99999s in the past. Under the new logic: `stale_minutes = (time.time() - os.path.getmtime(log_file)) / 60` evaluates to a small positive number just above 0 (log file was just written), and `timeout` is `0`. The gate `stale_minutes < timeout` is `<small positive> < 0`, which is `False`, so the function does *not* return early — it proceeds through the rest of the stall-kill logic exactly as it did before, and the test's `assert result is True` still holds. No code change needed for this test, but run it explicitly to confirm:

Run: `python3 -m pytest tests/test_synlynk.py::test_stall_detection_writes_handoff_pending -v`

Expected: PASS (no changes required to this test or to production code beyond what Step 3 already did).

- [ ] **Step 9: Run the full test suite**

Run: `python3 -m pytest tests/ -q`

Expected: All tests pass except the known pre-existing baseline failures (unrelated to this change, confirmed present on `main` independent of any dispatch-related work): `test_packaging.py::test_detect_install_type_pip`, `test_detect_install_type_script`, `test_detect_install_type_unknown`, `test_synlynk.py::test_run_tc4_skips_flag_only_command_templates`, `test_upgrade_auto_installs_new_version`.

- [ ] **Step 10: Commit**

```bash
git add synlynk/dispatch.py tests/test_agy_dispatch_fix.py
git commit -m "fix(dispatch): generalize stall check from 'log empty' to 'log stale'

_check_job_stall's os.path.getsize(log_file) > 0 early-exit made the
entire stall-kill path unreachable for any job that had ever written
a single byte of output — which describes nearly every real dispatched
job within seconds of starting. Replaced with an mtime-staleness check
reusing the existing stall_timeout_minutes config value, so a job that
produces early output and then genuinely hangs is now caught, not just
one that never produces any output at all.

Also fixes two pre-existing tests whose empty-log fixtures relied on
started_at-based staleness (removed by this change) rather than the
log file's own mtime — updated to set mtime via os.utime() so they
continue to exercise the intended 'job has been stale for 2 hours'
scenario under the new gating logic.

Refs #162"
```

---

## Notes for the implementing agent

- Task 1 and Task 2 are independent — Task 1 touches `_constants.py` and `__init__.py`; Task 2 touches `dispatch.py`. Either can be implemented first, but do them as separate commits (as shown) so the harness-timeout detection and the stall-check generalization remain independently revertable.
- Do not add a new config knob for Part 2 — `stall_timeout_minutes` (global and per-agent) is reused exactly as it exists today.
- Do not change the git-activity extension guard, the `SIGKILL` call, or the `STALL_NO_OUTPUT`/`HANDOFF_PENDING` alert text in `_check_job_stall` — only the staleness *gating condition* at the top of the function changes.
- Do not touch `check_sentinel_patterns()` in `synlynk/sentinel.py` — the `HARNESS_INTERNAL_TIMEOUT` detection is specific to the job-reconciliation path (`_reconcile_jobs()`), not the foreground `exec` command's pattern scanning, per the design doc.
- If `_pkg(...)` (used for `_inspect_worktree_git_state` and `_write_sentinel_alert` lookups in `_check_job_stall`) is unfamiliar, do not change its usage — it is an existing indirection in this file for resolving names from the parent package at call time, unrelated to this fix.
