# `_reconcile_terminal_jobs_json` Retry-Gate Wiring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the already-shipped `_gh_write_verification_retry_pending` and `_unpushed_branch_retry_pending` gates into `_reconcile_terminal_jobs_json`, so the `jobs.json`→`daemon_jobs` CLI bridge defers terminal settlement on an inconclusive check instead of locking in a false-negative status.

**Architecture:** `_reconcile_terminal_jobs_json` (`synlynk/jobs.py:3713-3783`) currently settles every terminal `jobs.json` event unconditionally via `_settle_daemon_job_terminal`, even when `_verify_daemon_terminal_status` returned `"unknown"`, and never calls `_guard_unpushed_branch` at all. This plan extends its per-job SQL `SELECT` to also read `worktree_path`/`worktree_branch`, computes a `git_state` dict the same way the main poll loop does (`_daemon_job_worktree_path` + `_worktree_git_state_inspector()`), and inserts both retry-pending checks — `continue`-ing (leaving the row `status='running'`) whenever either gate signals the check is still inconclusive. No new column, status value, or terminal writer.

**Tech Stack:** Python 3 stdlib, sqlite3, pytest.

**Spec:** `docs/superpowers/specs/2026-10-11-reconcile-terminal-jobs-retry-gate-design.md` (commit `1b26107c`).

---

## Setup

At execution time, create an isolated worktree via `superpowers:using-git-worktrees` for branch `fix/claude/reconcile-terminal-jobs-retry-gate`, off `origin/main`. Do **not** stack this on the current worktree's branch (`fix/claude/job-truth-verified-evidence-2158`) — that branch is an unrelated, separately in-flight fix, and this project's Git Workflow requires one feature per branch.

## File Structure

- Modify: `synlynk/jobs.py:3713-3783` (`_reconcile_terminal_jobs_json`) — the only production code change.
- Test: `tests/test_jobs.py` — add new test functions near the existing `_guard_unpushed_branch`/`_unpushed_branch_retry_pending` tests (around line 2219, immediately after `test_unpushed_branch_retry_pending_true_only_while_retrying_below_cap`) and near the existing `_reconcile_daemon_jobs` defer/cap tests (around line 2934, immediately after `test_reconcile_daemon_jobs_settles_unpushed_branch_after_retry_cap`).

---

### Task 1: Extend the bridge's SQL query and unpack the new columns

**Files:**
- Modify: `synlynk/jobs.py:3742-3750`

- [ ] **Step 1: Read the current code to confirm line numbers haven't drifted**

Run: `grep -n "SELECT requires_gh_write, gh_write_target" synlynk/jobs.py`
Expected: one match inside `_reconcile_terminal_jobs_json`, around line 3744.

- [ ] **Step 2: Replace the SELECT and unpacking**

Find this exact block (`synlynk/jobs.py:3742-3750`):

```python
        row = conn.execute(
            "SELECT requires_gh_write, gh_write_target, gh_write_author, gh_write_expect "
            "FROM daemon_jobs WHERE job_id=? AND status='running'",
            (job_id,),
        ).fetchone()
        if not row:
            continue
        requires_gh_write, target, author, expect = row
```

Replace with:

```python
        row = conn.execute(
            "SELECT requires_gh_write, gh_write_target, gh_write_author, gh_write_expect, "
            "worktree_path, worktree_branch "
            "FROM daemon_jobs WHERE job_id=? AND status='running'",
            (job_id,),
        ).fetchone()
        if not row:
            continue
        requires_gh_write, target, author, expect, worktree_path, worktree_branch = row
```

- [ ] **Step 3: Commit**

```bash
git add synlynk/jobs.py
git commit -m "refactor: select worktree_path/branch in _reconcile_terminal_jobs_json"
```

No test yet — this step alone changes no behavior (the new columns are unused until Task 2). Confirm the module still imports cleanly:

Run: `python3 -c "import synlynk.jobs"`
Expected: no output, exit code 0.

---

### Task 2: Insert the unpushed-branch retry gate

**Files:**
- Modify: `synlynk/jobs.py` (immediately after the code from Task 1, before the existing `if requires_gh_write:` block)

- [ ] **Step 1: Write the failing test (bridge defers on inconclusive unpushed-branch check)**

Add to `tests/test_jobs.py`, immediately after `test_reconcile_daemon_jobs_settles_unpushed_branch_after_retry_cap` (around line 2934):

```python
def test_reconcile_terminal_jobs_json_defers_on_inconclusive_unpushed_branch_check(project_dir, monkeypatch):
    import synlynk as sl
    import synlynk.jobs as jobs_mod

    job_id = "job-bridge-unpushed-defer"
    wt = project_dir / "worktrees" / job_id
    log = wt / ".synlynk" / "logs" / f"{job_id}.log"
    log.parent.mkdir(parents=True)
    log.write_text("agent did work\n")

    conn = sl._get_db()
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, status, pid, enqueued_at, "
        "started_at, log_path, worktree_path, worktree_branch) VALUES "
        "(?, 'codex', 'implement thing', 'running', 999999, "
        "'2026-10-04T09:00:00', '2026-10-04T09:00:00', ?, ?, ?)",
        (job_id, str(log), str(wt), f"fix/{job_id}"),
    )
    conn.commit()
    conn.close()

    sl._save_jobs([{
        "id": job_id,
        "agent": "codex",
        "status": "completed",
        "task": "implement thing",
        "started_at": "2026-10-04T09:00:00",
        "ended_at": "2026-10-04T09:05:00",
        "exit_code": 0,
        "requires_gh_write": False,
    }])

    monkeypatch.setattr(
        jobs_mod, "_worktree_git_state_inspector",
        lambda: lambda path, branch=None, started_at=None: {
            "has_activity": True, "commits_ahead": 1, "base_commit": "base-sha", "dirty": False,
        },
    )
    monkeypatch.setattr(jobs_mod, "local_commits_pushed", lambda *a, **k: False)
    monkeypatch.setattr(jobs_mod, "github_branch_effect_verified", lambda *a, **k: None)

    conn = sl._get_db()
    repaired = jobs_mod._reconcile_terminal_jobs_json(conn)
    conn.close()

    assert repaired == 0

    conn = sl._get_db()
    row = conn.execute(
        "SELECT status, unpushed_branch_check_attempts FROM daemon_jobs WHERE job_id=?",
        (job_id,),
    ).fetchone()
    conn.close()
    assert row == ("running", 1)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_jobs.py::test_reconcile_terminal_jobs_json_defers_on_inconclusive_unpushed_branch_check -v`
Expected: FAIL — `repaired == 0` assertion fails (currently returns `1`, since the bridge settles unconditionally today), or the status assertion fails (row settles to `"done"` instead of staying `"running"`).

- [ ] **Step 3: Implement the minimal code**

Immediately after the code block from Task 1 (still inside the `for job_id, (job, status) in terminal_jobs.items():` loop, before the existing `if requires_gh_write:` line), insert:

```python
        preferred_path = worktree_path or _daemon_job_worktree_path(job_id, job.get("log_path"))
        preferred_branch = worktree_branch or job.get("worktree_branch")
        preferred_state = None
        if preferred_path:
            try:
                preferred_state = _worktree_git_state_inspector()(
                    preferred_path, preferred_branch, job.get("started_at")
                )
            except Exception:
                preferred_state = None
        pre_guard_status = status
        status = _guard_unpushed_branch(
            conn, job_id, status, preferred_path, preferred_branch, preferred_state,
            job.get("started_at"),
        )
        if _unpushed_branch_retry_pending(conn, job_id, pre_guard_status, status):
            conn.commit()
            continue
```

So the full loop body now reads (for orientation — only the new block above is added; everything from `if requires_gh_write:` onward is unchanged from Task 1):

```python
    for job_id, (job, status) in terminal_jobs.items():
        row = conn.execute(
            "SELECT requires_gh_write, gh_write_target, gh_write_author, gh_write_expect, "
            "worktree_path, worktree_branch "
            "FROM daemon_jobs WHERE job_id=? AND status='running'",
            (job_id,),
        ).fetchone()
        if not row:
            continue
        requires_gh_write, target, author, expect, worktree_path, worktree_branch = row
        preferred_path = worktree_path or _daemon_job_worktree_path(job_id, job.get("log_path"))
        preferred_branch = worktree_branch or job.get("worktree_branch")
        preferred_state = None
        if preferred_path:
            try:
                preferred_state = _worktree_git_state_inspector()(
                    preferred_path, preferred_branch, job.get("started_at")
                )
            except Exception:
                preferred_state = None
        pre_guard_status = status
        status = _guard_unpushed_branch(
            conn, job_id, status, preferred_path, preferred_branch, preferred_state,
            job.get("started_at"),
        )
        if _unpushed_branch_retry_pending(conn, job_id, pre_guard_status, status):
            conn.commit()
            continue
        if requires_gh_write:
            status, verified = _verify_daemon_terminal_status(
                conn,
                job_id,
                requires_gh_write,
                target or job.get("gh_write_target"),
                status,
                job.get("started_at"),
                author or job.get("gh_write_author"),
                expect or job.get("gh_write_expect"),
                worktree_branch=job.get("worktree_branch"),
            )
        else:
            verified = None
        exit_code = job.get("exit_code")
        completed_at = job.get("ended_at") or time.strftime("%Y-%m-%dT%H:%M:%S")
        if _settle_daemon_job_terminal(
            conn, job_id, status, exit_code, completed_at, only_running=True
        ):
            repaired += 1
            emit_event(
                "job_terminal",
                {
                    "job_id": job_id,
                    "status": status,
                    "gh_write_verified": verified,
                    "source": "jobs.json",
                },
                emitted_by="_reconcile_terminal_jobs_json",
            )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_jobs.py::test_reconcile_terminal_jobs_json_defers_on_inconclusive_unpushed_branch_check -v`
Expected: PASS

- [ ] **Step 5: Write the failing test (bridge settles after retry cap exhausted)**

Add immediately after the previous test:

```python
def test_reconcile_terminal_jobs_json_settles_unpushed_branch_after_retry_cap(project_dir, monkeypatch):
    import synlynk as sl
    import synlynk.jobs as jobs_mod

    job_id = "job-bridge-unpushed-cap"
    wt = project_dir / "worktrees" / job_id
    log = wt / ".synlynk" / "logs" / f"{job_id}.log"
    log.parent.mkdir(parents=True)
    log.write_text("agent did work\n")

    conn = sl._get_db()
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, status, pid, enqueued_at, "
        "started_at, log_path, worktree_path, worktree_branch, unpushed_branch_check_attempts) VALUES "
        "(?, 'codex', 'implement thing', 'running', 999999, "
        "'2026-10-04T09:00:00', '2026-10-04T09:00:00', ?, ?, ?, 3)",
        (job_id, str(log), str(wt), f"fix/{job_id}"),
    )
    conn.commit()
    conn.close()

    sl._save_jobs([{
        "id": job_id,
        "agent": "codex",
        "status": "completed",
        "task": "implement thing",
        "started_at": "2026-10-04T09:00:00",
        "ended_at": "2026-10-04T09:05:00",
        "exit_code": 0,
        "requires_gh_write": False,
    }])

    monkeypatch.setattr(
        jobs_mod, "_worktree_git_state_inspector",
        lambda: lambda path, branch=None, started_at=None: {
            "has_activity": True, "commits_ahead": 1, "base_commit": "base-sha", "dirty": False,
        },
    )
    monkeypatch.setattr(jobs_mod, "local_commits_pushed", lambda *a, **k: False)
    monkeypatch.setattr(jobs_mod, "github_branch_effect_verified", lambda *a, **k: None)

    conn = sl._get_db()
    repaired = jobs_mod._reconcile_terminal_jobs_json(conn)
    conn.close()

    assert repaired == 1

    conn = sl._get_db()
    row = conn.execute(
        "SELECT status, gh_write_verified, unpushed_branch_check_attempts FROM daemon_jobs WHERE job_id=?",
        (job_id,),
    ).fetchone()
    conn.close()
    assert row == (jobs_mod.STATUS_UNPUSHED_BRANCH, "false", 3)
```

- [ ] **Step 6: Run test to verify it fails, then passes**

Run: `pytest tests/test_jobs.py::test_reconcile_terminal_jobs_json_settles_unpushed_branch_after_retry_cap -v`
Expected: FAILs before Step 3's code exists on a fresh checkout (it won't, since Step 3 is already applied from this same task) — since Task 2's code is already in place from Step 3 above, this test should PASS immediately. Run it to confirm PASS.

- [ ] **Step 7: Commit**

```bash
git add synlynk/jobs.py tests/test_jobs.py
git commit -m "fix: defer bridge settlement on inconclusive unpushed-branch check"
```

---

### Task 3: Insert the GH-write verification retry gate

**Files:**
- Modify: `synlynk/jobs.py` (inside the existing `if requires_gh_write:` block added in Task 2's reproduction)

- [ ] **Step 1: Write the failing test (bridge defers on unknown GH-write verification)**

Add to `tests/test_jobs.py` immediately after the Task 2 tests:

```python
def test_reconcile_terminal_jobs_json_defers_on_unknown_gh_write_verification(project_dir, monkeypatch):
    import synlynk as sl
    import synlynk.jobs as jobs_mod

    job_id = "job-bridge-ghwrite-defer"

    conn = sl._get_db()
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, status, pid, enqueued_at, "
        "started_at, requires_gh_write, gh_write_target, gh_write_author, gh_write_expect, "
        "gh_write_verification_attempts) VALUES "
        "(?, 'codex', 'review pr', 'running', 999999, "
        "'2026-10-04T09:00:00', '2026-10-04T09:00:00', 1, 'pr:123', 'codex', 'review_posted', 0)",
        (job_id,),
    )
    conn.commit()
    conn.close()

    sl._save_jobs([{
        "id": job_id,
        "agent": "codex",
        "status": "completed",
        "task": "review pr",
        "started_at": "2026-10-04T09:00:00",
        "ended_at": "2026-10-04T09:05:00",
        "exit_code": 0,
        "requires_gh_write": True,
        "gh_write_target": "pr:123",
        "gh_write_author": "codex",
        "gh_write_expect": "review_posted",
    }])

    monkeypatch.setattr(
        jobs_mod, "_verify_daemon_terminal_status",
        lambda *a, **k: (a[4], "unknown"),
    )

    conn = sl._get_db()
    repaired = jobs_mod._reconcile_terminal_jobs_json(conn)
    conn.close()

    assert repaired == 0

    conn = sl._get_db()
    row = conn.execute(
        "SELECT status FROM daemon_jobs WHERE job_id=?", (job_id,),
    ).fetchone()
    conn.close()
    assert row == ("running",)
```

Note: `_verify_daemon_terminal_status`'s 5th positional argument (index 4) is `status` — confirm this against its signature (`conn, job_id, requires_gh_write, gh_write_target, status, started_at, gh_write_author, gh_write_expect, worktree_branch=None`) before relying on it; the lambda above echoes the `status` argument back unchanged alongside `"unknown"`.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_jobs.py::test_reconcile_terminal_jobs_json_defers_on_unknown_gh_write_verification -v`
Expected: FAIL — `repaired == 0` fails (currently `1`) or the status assertion fails (currently settles to `"done"`).

- [ ] **Step 3: Implement the minimal code**

Inside the `if requires_gh_write:` block (added in Task 1, untouched until now), add the retry-pending check immediately after the `_verify_daemon_terminal_status` call:

Find:

```python
        if requires_gh_write:
            status, verified = _verify_daemon_terminal_status(
                conn,
                job_id,
                requires_gh_write,
                target or job.get("gh_write_target"),
                status,
                job.get("started_at"),
                author or job.get("gh_write_author"),
                expect or job.get("gh_write_expect"),
                worktree_branch=job.get("worktree_branch"),
            )
        else:
            verified = None
```

Replace with:

```python
        if requires_gh_write:
            status, verified = _verify_daemon_terminal_status(
                conn,
                job_id,
                requires_gh_write,
                target or job.get("gh_write_target"),
                status,
                job.get("started_at"),
                author or job.get("gh_write_author"),
                expect or job.get("gh_write_expect"),
                worktree_branch=preferred_branch,
            )
            if _gh_write_verification_retry_pending(conn, job_id, requires_gh_write, verified):
                conn.commit()
                continue
        else:
            verified = None
```

Note this also changes `worktree_branch=job.get("worktree_branch")` to `worktree_branch=preferred_branch`, using the value resolved in Task 2's step — the same resolved-with-fallback value, consistent with the main poll loop passing `preferred_branch` at its equivalent call site.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_jobs.py::test_reconcile_terminal_jobs_json_defers_on_unknown_gh_write_verification -v`
Expected: PASS

- [ ] **Step 5: Write the test for the resolved-verification follow-up call**

Add immediately after:

```python
def test_reconcile_terminal_jobs_json_settles_once_gh_write_verification_resolves(project_dir, monkeypatch):
    import synlynk as sl
    import synlynk.jobs as jobs_mod

    job_id = "job-bridge-ghwrite-resolved"

    conn = sl._get_db()
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, status, pid, enqueued_at, "
        "started_at, requires_gh_write, gh_write_target, gh_write_author, gh_write_expect, "
        "gh_write_verification_attempts) VALUES "
        "(?, 'codex', 'review pr', 'running', 999999, "
        "'2026-10-04T09:00:00', '2026-10-04T09:00:00', 1, 'pr:123', 'codex', 'review_posted', 3)",
        (job_id,),
    )
    conn.commit()
    conn.close()

    sl._save_jobs([{
        "id": job_id,
        "agent": "codex",
        "status": "completed",
        "task": "review pr",
        "started_at": "2026-10-04T09:00:00",
        "ended_at": "2026-10-04T09:05:00",
        "exit_code": 0,
        "requires_gh_write": True,
        "gh_write_target": "pr:123",
        "gh_write_author": "codex",
        "gh_write_expect": "review_posted",
    }])

    monkeypatch.setattr(
        jobs_mod, "_verify_daemon_terminal_status",
        lambda *a, **k: (a[4], "true"),
    )

    conn = sl._get_db()
    repaired = jobs_mod._reconcile_terminal_jobs_json(conn)
    conn.close()

    assert repaired == 1

    conn = sl._get_db()
    row = conn.execute(
        "SELECT status FROM daemon_jobs WHERE job_id=?", (job_id,),
    ).fetchone()
    conn.close()
    assert row == ("done",)
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/test_jobs.py::test_reconcile_terminal_jobs_json_settles_once_gh_write_verification_resolves -v`
Expected: PASS (code already in place from Step 3)

- [ ] **Step 7: Commit**

```bash
git add synlynk/jobs.py tests/test_jobs.py
git commit -m "fix: defer bridge settlement on unknown gh-write verification"
```

---

### Task 4: Regression test for the job-26b6196d shape via the bridge path

**Files:**
- Test: `tests/test_jobs.py`

- [ ] **Step 1: Write the regression test**

Add immediately after the Task 3 tests:

```python
def test_reconcile_terminal_jobs_json_recovers_from_inconclusive_check_once_push_confirmed(project_dir, monkeypatch):
    """Reproduces job-26b6196d's shape (gh:#2130) specifically on the CLI-bridge path:
    a real merge that hits a momentarily inconclusive GitHub check must not be
    permanently misclassified as unpushed_branch on the first bridge pass."""
    import synlynk as sl
    import synlynk.jobs as jobs_mod

    job_id = "job-bridge-recovers"
    wt = project_dir / "worktrees" / job_id
    log = wt / ".synlynk" / "logs" / f"{job_id}.log"
    log.parent.mkdir(parents=True)
    log.write_text("agent did work\n")

    conn = sl._get_db()
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, status, pid, enqueued_at, "
        "started_at, log_path, worktree_path, worktree_branch) VALUES "
        "(?, 'codex', 'implement thing', 'running', 999999, "
        "'2026-10-04T09:00:00', '2026-10-04T09:00:00', ?, ?, ?)",
        (job_id, str(log), str(wt), f"fix/{job_id}"),
    )
    conn.commit()
    conn.close()

    sl._save_jobs([{
        "id": job_id,
        "agent": "codex",
        "status": "completed",
        "task": "implement thing",
        "started_at": "2026-10-04T09:00:00",
        "ended_at": "2026-10-04T09:05:00",
        "exit_code": 0,
        "requires_gh_write": False,
    }])

    monkeypatch.setattr(
        jobs_mod, "_worktree_git_state_inspector",
        lambda: lambda path, branch=None, started_at=None: {
            "has_activity": True, "commits_ahead": 1, "base_commit": "base-sha", "dirty": False,
        },
    )
    monkeypatch.setattr(jobs_mod, "local_commits_pushed", lambda *a, **k: False)
    monkeypatch.setattr(jobs_mod, "github_branch_effect_verified", lambda *a, **k: None)

    # First bridge pass: inconclusive check -> must defer, not misclassify.
    conn = sl._get_db()
    repaired_first = jobs_mod._reconcile_terminal_jobs_json(conn)
    conn.close()
    assert repaired_first == 0

    conn = sl._get_db()
    row = conn.execute(
        "SELECT status FROM daemon_jobs WHERE job_id=?", (job_id,),
    ).fetchone()
    conn.close()
    assert row == ("running",)

    # GitHub now confirms the merge (the real-world recovery in job-26b6196d).
    monkeypatch.setattr(jobs_mod, "github_branch_effect_verified", lambda *a, **k: True)

    conn = sl._get_db()
    repaired_second = jobs_mod._reconcile_terminal_jobs_json(conn)
    conn.close()
    assert repaired_second == 1

    conn = sl._get_db()
    row = conn.execute(
        "SELECT status FROM daemon_jobs WHERE job_id=?", (job_id,),
    ).fetchone()
    conn.close()
    assert row == ("done",)
```

- [ ] **Step 2: Run test to verify it passes**

Run: `pytest tests/test_jobs.py::test_reconcile_terminal_jobs_json_recovers_from_inconclusive_check_once_push_confirmed -v`
Expected: PASS (code from Tasks 2-3 already handles both passes correctly)

- [ ] **Step 3: Commit**

```bash
git add tests/test_jobs.py
git commit -m "test: regression coverage for job-26b6196d shape on the bridge path"
```

- [ ] **Step 4: Write the cross-call-site parity test (2026-10-11 decide panel addition)**

The 2026-10-11 validation panel (`claude,agy,codex`) approved this plan on the condition that Task 4 also prove `_reconcile_terminal_jobs_json` can't silently drift from `_reconcile_daemon_jobs`'s behavior for identical job state, since both call the same two gate functions independently. Add immediately after the previous test:

```python
def test_reconcile_terminal_jobs_json_matches_reconcile_daemon_jobs_defer_decision(project_dir, monkeypatch):
    """Cross-call-site parity (2026-10-11 decide panel condition): for identical
    inconclusive job state, the bridge (_reconcile_terminal_jobs_json) and the main
    poll loop (_reconcile_daemon_jobs) must reach the same defer decision, since both
    call _guard_unpushed_branch/_unpushed_branch_retry_pending independently."""
    import synlynk as sl
    import synlynk.jobs as jobs_mod

    def make_job(job_id):
        wt = project_dir / "worktrees" / job_id
        log = wt / ".synlynk" / "logs" / f"{job_id}.log"
        log.parent.mkdir(parents=True)
        log.write_text("agent did work\n")
        conn = sl._get_db()
        conn.execute(
            "INSERT INTO daemon_jobs (job_id, agent, task, status, pid, enqueued_at, "
            "started_at, log_path, worktree_path, worktree_branch) VALUES "
            "(?, 'codex', 'implement thing', 'running', 999999, "
            "'2026-10-04T09:00:00', '2026-10-04T09:00:00', ?, ?, ?)",
            (job_id, str(log), str(wt), f"fix/{job_id}"),
        )
        conn.commit()
        conn.close()
        return wt

    monkeypatch.setattr(
        jobs_mod, "_worktree_git_state_inspector",
        lambda: lambda path, branch=None, started_at=None: {
            "has_activity": True, "commits_ahead": 1, "base_commit": "base-sha", "dirty": False,
        },
    )
    monkeypatch.setattr(jobs_mod, "local_commits_pushed", lambda *a, **k: False)
    monkeypatch.setattr(jobs_mod, "github_branch_effect_verified", lambda *a, **k: None)

    # Bridge path.
    bridge_job_id = "job-parity-bridge"
    make_job(bridge_job_id)
    sl._save_jobs([{
        "id": bridge_job_id, "agent": "codex", "status": "completed",
        "task": "implement thing", "started_at": "2026-10-04T09:00:00",
        "ended_at": "2026-10-04T09:05:00", "exit_code": 0, "requires_gh_write": False,
    }])
    conn = sl._get_db()
    bridge_repaired = jobs_mod._reconcile_terminal_jobs_json(conn)
    conn.close()

    # Daemon poll-loop path, identical job state.
    daemon_job_id = "job-parity-daemon"
    make_job(daemon_job_id)
    conn = sl._get_db()
    daemon_repaired = jobs_mod._reconcile_daemon_jobs(conn)
    conn.close()

    conn = sl._get_db()
    bridge_row = conn.execute(
        "SELECT status FROM daemon_jobs WHERE job_id=?", (bridge_job_id,),
    ).fetchone()
    daemon_row = conn.execute(
        "SELECT status FROM daemon_jobs WHERE job_id=?", (daemon_job_id,),
    ).fetchone()
    conn.close()

    assert bridge_row == ("running",), "bridge must defer on inconclusive check, not settle"
    assert bridge_row == daemon_row, (
        "bridge and daemon poll loop must reach the same defer decision for identical "
        f"job state; got bridge={bridge_row} daemon={daemon_row}"
    )
    assert bridge_repaired == 0 and daemon_repaired == 0
```

Note: `_reconcile_daemon_jobs` processes real `daemon_jobs` rows directly and does not require a matching `jobs.json` entry the way the bridge does — confirm its signature/call convention against the existing tests at `tests/test_jobs.py` around line 2934 before relying on this test as written; adjust the daemon-path setup to match if it needs additional fixture state (e.g. a `started_at` old enough to be poll-loop-eligible).

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_jobs.py::test_reconcile_terminal_jobs_json_matches_reconcile_daemon_jobs_defer_decision -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add tests/test_jobs.py
git commit -m "test: cross-call-site parity between bridge and daemon poll loop"
```

---

### Task 5: Full suite verification

**Files:** none (verification only)

- [ ] **Step 1: Run the full test suite**

Run: `pytest -q`
Expected: all tests pass, including every test added in Tasks 2-4 and every pre-existing test in `tests/test_jobs.py`, `tests/test_jobs_gh_write_provisional.py`, `tests/test_jobs_reconcile_live19.py`, `tests/test_gh_write_guard.py`, `tests/test_verify_effects.py`, and `tests/test_db_migration.py` unchanged in outcome (no prior-passing test starts failing, no prior-failing test is newly masked).

- [ ] **Step 2: Confirm no behavior change outside the touched function**

Run: `git diff origin/main -- synlynk/ | grep '^+++\|^---'`
Expected: only `synlynk/jobs.py` listed as modified in production code (tests files are expected to differ too, listed separately).

- [ ] **Step 3: Commit if anything is outstanding**

```bash
git status --short
```

If clean, nothing further to commit — proceed to execution handoff.

---

## Acceptance Criteria (2026-10-11 decide panel addition)

Before this plan is considered done, confirm all of the following — the `claude,agy,codex` validation panel made these explicit conditions of approval, not just the written tests above:

1. **Both gates execute, and can defer, strictly before any terminal write.** Trace the final code: `_guard_unpushed_branch`/`_unpushed_branch_retry_pending` (Task 2) and `_gh_write_verification_retry_pending` (Task 3) must both sit before the `_settle_daemon_job_terminal` call. Confirm by reading the merged diff's control flow directly, not just by the tests passing.
2. **A defer from one gate cannot be bypassed via the other gate or the bridge's fallback path.** E.g., a job with `requires_gh_write=False` and an inconclusive unpushed-branch check must still defer (Task 2's gate alone is sufficient to block settlement) — the `if requires_gh_write:` branch being skipped must not be read as "nothing left to check." Verify this is true of the code as merged, not only the specific test fixtures that happen to exercise it.
3. **`worktree_path`/`worktree_branch` are proven populated at the bridge from real `daemon_jobs` data, not just supplied by test mocks.** Task 1's `SELECT` extension must be exercised against a real inserted row (every test in Tasks 2-4 already does this via direct `INSERT INTO daemon_jobs`), and the fallback (`_daemon_job_worktree_path`) path should also get at least one test case where the column is NULL and the fallback resolves it — add this as part of Task 2 if no existing test covers the NULL-column case.

If any of these three don't hold once Tasks 1-4 are implemented, treat it as a plan gap to fix before Task 5, not a nitpick to defer.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-10-11-reconcile-terminal-jobs-retry-gate.md`.

**Per this project's Default Agent Role policy (CLAUDE.md), actual implementation of this plan should be dispatched via `synlynk dispatch` to Agy/Grok/Codex rather than implemented by Claude directly.** Link the dispatch to `story-25872226` / `goal-bde24050` for 100% GOVERNS adherence. Recommended target harness: Codex or Grok, per this project's "Prefer Codex/Grok over Agy" feedback memory (Agy has repeatedly hit response timeouts on comparable jobs).

Two execution options once dispatched:

**1. Subagent-Driven (recommended)** — fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
