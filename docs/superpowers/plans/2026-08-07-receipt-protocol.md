# Receipt Protocol for Synlynk Dispatch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a cross-CLI task receipt marker that dispatched agents echo as their first output line, and a post-hoc `TASK_DELIVERY_FAILED` job classification with a false-positive corroboration guard, per the approved design at `docs/superpowers/specs/2026-08-07-receipt-protocol-design.md`.

**Architecture:** `dispatch_agent()` computes a `task_sha256` digest and injects a receipt instruction into every agent's prompt via `_format_prompt_for_agent()` (`synlynk/dispatch.py`). Reconciliation (`synlynk/jobs.py`) reads the resulting log post-hoc, classifies receipt compliance with a new pure function `_check_task_receipt()`, and combines that with git activity via `_classify_task_delivery()` to decide between a hard `task_delivery_failed` status (no marker, no corroborating work) or a non-blocking WARN note (no marker, but real work landed). `selftest --matrix` (`synlynk/fleet.py`) gets one live compliance cell per agent.

**Tech Stack:** Python 3 stdlib only (`hashlib`, existing `subprocess`-based reconciliation loop). No new dependencies.

---

### Task 1: Receipt instruction + prompt injection

**Files:**
- Modify: `synlynk/dispatch.py:811-841` (`_format_prompt_for_agent`)
- Modify: `synlynk/dispatch.py:1610-1621` (`dispatch_agent` signature area — task_sha256 computed before the `format_prompt(...)` call around line 1873)
- Test: `tests/test_dispatch.py`

- [ ] **Step 1: Write the failing test for the instruction renderer**

Add to `tests/test_dispatch.py`:

```python
def test_render_task_receipt_instruction_contains_marker_and_digest():
    import synlynk.dispatch as dispatch_mod

    instruction = dispatch_mod._render_task_receipt_instruction("abc123")

    assert "SYNLYNK_TASK_RECEIVED: abc123" in instruction
    assert "very first output" in instruction


def test_format_prompt_for_agent_prepends_receipt_instruction_for_all_agents():
    import synlynk.dispatch as dispatch_mod

    for agent in ("claude", "codex", "agy", "grok"):
        prompt = dispatch_mod._format_prompt_for_agent(
            agent, "context", "story-1", "do the thing", "", "",
            task_sha256="deadbeef",
        )
        assert prompt.startswith("## Task Receipt (required)")
        assert "SYNLYNK_TASK_RECEIVED: deadbeef" in prompt
        assert "do the thing" in prompt
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_dispatch.py -k "receipt_instruction" -v`
Expected: FAIL with `AttributeError: module 'synlynk.dispatch' has no attribute '_render_task_receipt_instruction'` (and the second test fails with `TypeError: _format_prompt_for_agent() got an unexpected keyword argument 'task_sha256'`)

- [ ] **Step 3: Add `_render_task_receipt_instruction()` and thread `task_sha256` through `_format_prompt_for_agent()`**

In `synlynk/dispatch.py`, immediately above `def _format_prompt_for_agent(`, add:

```python
def _render_task_receipt_instruction(task_sha256: Optional[str]) -> str:
    """Returns a prompt-prepend block instructing the agent to echo the
    task digest as its literal first output line (see #720 receipt protocol)."""
    if not task_sha256:
        return ""
    return (
        "## Task Receipt (required)\n"
        "Before doing anything else, print this exact line as your very "
        "first output:\n"
        f"SYNLYNK_TASK_RECEIVED: {task_sha256}\n"
        "Then proceed with the task below.\n\n"
    )
```

Then change the `_format_prompt_for_agent` signature and prepend the instruction to every branch's return value:

```python
def _format_prompt_for_agent(agent: str, context_text: str, story_id: str,
                              task: str, file_section: str, verify_section: str,
                              cwd_hint: Optional[str] = None,
                              task_sha256: Optional[str] = None) -> str:
    """Returns a prompt formatted for the agent's preferred input style."""
    receipt_instruction = _render_task_receipt_instruction(task_sha256)
    story_ref = f"\n\n## Story / Task Reference\nStory ID: {story_id}" if story_id else ""
    if agent == "codex":
        sentences = [s.strip() for s in re.split(r"[.!?]", task) if s.strip()]
        criteria = "\n".join(f"- {s}" for s in sentences) if sentences else f"- {task}"
        return (
            f"{receipt_instruction}"
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
        f"{context_text}"
        f"{story_ref}"
        f"{file_section}"
        f"\n\n## Your Task\n{task}"
        f"{verify_section}\n"
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_dispatch.py -k "receipt_instruction" -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Thread `task_sha256` from `dispatch_agent()` into the `format_prompt(...)` call**

In `synlynk/dispatch.py`, find the `format_prompt(...)` call inside `dispatch_agent()` (currently around line 1873-1886):

```python
    format_prompt = _pkg("_format_prompt_for_agent", _format_prompt_for_agent)
    try:
        prompt = format_prompt(
            agent,
            context_text,
            story_id or "",
            task,
            file_section,
            verify_section,
            cwd_hint=worktree_path,
        )
    except TypeError:
        prompt = format_prompt(agent, context_text, story_id or "", task, file_section, verify_section)
```

Replace with:

```python
    task_sha256_for_receipt = hashlib.sha256(task.encode("utf-8")).hexdigest()
    format_prompt = _pkg("_format_prompt_for_agent", _format_prompt_for_agent)
    try:
        prompt = format_prompt(
            agent,
            context_text,
            story_id or "",
            task,
            file_section,
            verify_section,
            cwd_hint=worktree_path,
            task_sha256=task_sha256_for_receipt,
        )
    except TypeError:
        prompt = format_prompt(agent, context_text, story_id or "", task, file_section, verify_section)
```

The `except TypeError` fallback already exists to tolerate test doubles that monkeypatch `_format_prompt_for_agent` with a narrower signature — keep it as-is; it will simply skip the receipt instruction for those doubles, which is fine since they don't exercise this feature.

- [ ] **Step 6: Add a test confirming `dispatch_agent()` writes the receipt instruction into the prompt file**

Find the existing test in `tests/test_dispatch.py` that dispatches a job and inspects `prompt_file` contents (search for `prompt_file` or `.prompt` in the file to find the pattern) and add a sibling test:

```python
def test_dispatch_agent_writes_receipt_instruction_to_prompt_file(tmp_path, monkeypatch):
    import hashlib
    monkeypatch.chdir(tmp_path)
    import synlynk.dispatch as dispatch_mod

    monkeypatch.setattr(dispatch_mod, "_create_job_worktree", lambda *a, **kw: (str(tmp_path), "dispatch/test/job-x"))
    monkeypatch.setattr(dispatch_mod, "generate_context", lambda *a, **kw: "context")
    monkeypatch.setattr(dispatch_mod.subprocess, "Popen", lambda *a, **kw: type("P", (), {"pid": 99999999})())

    task = "implement the receipt protocol"
    expected_digest = hashlib.sha256(task.encode("utf-8")).hexdigest()

    dispatch_mod.dispatch_agent("claude", task, force_agent=True, skip_preflight=True)

    prompt_files = list(tmp_path.glob(".synlynk/jobs/*/prompt*")) or list(tmp_path.glob("**/*.prompt"))
    assert prompt_files, "expected a prompt file to be written"
    prompt_text = prompt_files[0].read_text()
    assert f"SYNLYNK_TASK_RECEIVED: {expected_digest}" in prompt_text
```

If the glob pattern above doesn't match this codebase's actual prompt-file path (check by running the test and reading the failure, or `grep -n "prompt_file =" synlynk/dispatch.py`), fix the glob to match the real path — do not skip this assertion.

- [ ] **Step 7: Run the full dispatch test file**

Run: `pytest tests/test_dispatch.py -v`
Expected: all tests PASS

- [ ] **Step 8: Commit**

```bash
git add synlynk/dispatch.py tests/test_dispatch.py
git commit -m "feat: inject task receipt marker instruction into dispatch prompts (#720)"
```

---

### Task 2: `_check_task_receipt()` detection function

**Files:**
- Modify: `synlynk/jobs.py` (add new function near `_log_has_permission_denied_signature`, currently around line 86-90)
- Test: `tests/test_jobs.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_jobs.py`:

```python
def test_check_task_receipt_ok_when_marker_is_first_line():
    import synlynk.jobs as jobs_mod

    log_text = "SYNLYNK_TASK_RECEIVED: abc123\nsome work happened\n"
    assert jobs_mod._check_task_receipt(log_text, "abc123") == "ok"


def test_check_task_receipt_late_when_marker_present_but_not_first():
    import synlynk.jobs as jobs_mod

    log_text = "starting work\nSYNLYNK_TASK_RECEIVED: abc123\nmore work\n"
    assert jobs_mod._check_task_receipt(log_text, "abc123") == "late"


def test_check_task_receipt_mismatch_when_first_line_wrong_digest():
    import synlynk.jobs as jobs_mod

    log_text = "SYNLYNK_TASK_RECEIVED: wrongdigest\nsome work\n"
    assert jobs_mod._check_task_receipt(log_text, "abc123") == "mismatch"


def test_check_task_receipt_absent_when_no_marker_anywhere():
    import synlynk.jobs as jobs_mod

    log_text = "just did the work with no marker at all\n"
    assert jobs_mod._check_task_receipt(log_text, "abc123") == "absent"


def test_check_task_receipt_returns_none_for_empty_log_or_digest():
    import synlynk.jobs as jobs_mod

    assert jobs_mod._check_task_receipt("", "abc123") is None
    assert jobs_mod._check_task_receipt("some log", None) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_jobs.py -k "check_task_receipt" -v`
Expected: FAIL with `AttributeError: module 'synlynk.jobs' has no attribute '_check_task_receipt'`

- [ ] **Step 3: Implement `_check_task_receipt()`**

In `synlynk/jobs.py`, add near `_log_has_permission_denied_signature` (around line 86-90):

```python
_TASK_RECEIPT_MARKER_PREFIX = "SYNLYNK_TASK_RECEIVED:"


def _check_task_receipt(log_text: str, task_sha256: Optional[str]) -> Optional[str]:
    """Classifies task-receipt marker compliance in a job's log.

    Returns one of 'ok', 'late', 'mismatch', 'absent', or None when the
    check does not apply (empty log or no digest to check against).
    """
    if not log_text or not task_sha256:
        return None
    lines = [ln.strip() for ln in log_text.splitlines() if ln.strip()]
    if not lines:
        return "absent"
    expected = f"{_TASK_RECEIPT_MARKER_PREFIX} {task_sha256}"
    if lines[0] == expected:
        return "ok"
    if expected in lines[1:]:
        return "late"
    if lines[0].startswith(_TASK_RECEIPT_MARKER_PREFIX):
        return "mismatch"
    return "absent"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_jobs.py -k "check_task_receipt" -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add synlynk/jobs.py tests/test_jobs.py
git commit -m "feat: add _check_task_receipt() marker classifier (#720)"
```

---

### Task 3: `_classify_task_delivery()` corroboration guard

**Files:**
- Modify: `synlynk/jobs.py` (add new function directly below `_check_task_receipt()` from Task 2)
- Test: `tests/test_jobs.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_jobs.py`:

```python
def test_classify_task_delivery_hard_fail_when_no_marker_and_no_activity():
    import synlynk.jobs as jobs_mod

    result = jobs_mod._classify_task_delivery("absent", has_corroborating_activity=False)
    assert result == {"hard_fail": True, "warn": False}


def test_classify_task_delivery_warn_when_no_marker_but_activity_present():
    import synlynk.jobs as jobs_mod

    result = jobs_mod._classify_task_delivery("mismatch", has_corroborating_activity=True)
    assert result == {"hard_fail": False, "warn": True}


def test_classify_task_delivery_clean_when_receipt_ok():
    import synlynk.jobs as jobs_mod

    result = jobs_mod._classify_task_delivery("ok", has_corroborating_activity=False)
    assert result == {"hard_fail": False, "warn": False}


def test_classify_task_delivery_clean_when_receipt_status_none():
    import synlynk.jobs as jobs_mod

    result = jobs_mod._classify_task_delivery(None, has_corroborating_activity=False)
    assert result == {"hard_fail": False, "warn": False}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_jobs.py -k "classify_task_delivery" -v`
Expected: FAIL with `AttributeError: module 'synlynk.jobs' has no attribute '_classify_task_delivery'`

- [ ] **Step 3: Implement `_classify_task_delivery()`**

In `synlynk/jobs.py`, directly below `_check_task_receipt()`:

```python
def _classify_task_delivery(receipt_status: Optional[str], has_corroborating_activity: bool) -> dict:
    """Combines a receipt-check result with git-activity evidence.

    'hard_fail' means no real work is visible to corroborate a bad/missing
    receipt marker — safe to mark the job task_delivery_failed and skip
    auto-finalize. 'warn' means the receipt check failed but real work
    landed anyway — do not block the job, just annotate it (see the
    job-b88e0f92 false-positive this guard was designed to avoid).
    """
    if receipt_status not in ("late", "mismatch", "absent"):
        return {"hard_fail": False, "warn": False}
    if has_corroborating_activity:
        return {"hard_fail": False, "warn": True}
    return {"hard_fail": True, "warn": False}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_jobs.py -k "classify_task_delivery" -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add synlynk/jobs.py tests/test_jobs.py
git commit -m "feat: add _classify_task_delivery() false-positive corroboration guard (#720)"
```

---

### Task 4: Wire classification into the waitpid-reaped reconciliation block

**Files:**
- Modify: `synlynk/jobs.py` (the `waitpid_reaped` branch inside `_reconcile_jobs()`, currently spanning roughly lines 1121-1225 — locate by the comment-free block starting `if waitpid_reaped:` and ending at the `continue` after the `print(summary, end="")` call that follows the `_write_job_summary(...)` invocation with `base_branch=job.get("base_branch")`)
- Test: `tests/test_jobs.py`

This task and Task 5 both touch `_reconcile_jobs()`, which has two near-duplicate branches (one for jobs reaped via `os.waitpid`, one for jobs whose PID is already gone and detected via `ProcessLookupError` on `os.kill`). Do this task first; Task 5 mirrors the same change in the second branch.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_jobs.py`. This test exercises the `waitpid_reaped` branch, which requires `os.waitpid` to return a non-zero pid (simulating a reaped child). Use `monkeypatch.setattr(synlynk.os, "waitpid", ...)`:

```python
def test_reconcile_jobs_marks_task_delivery_failed_when_marker_absent_and_no_activity(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    import synlynk

    log_path = tmp_path / ".synlynk" / "logs" / "job-noreceipt.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("did some stuff without printing the receipt marker\n")
    (log_path.parent / "job-noreceipt.log.exit").write_text("0")

    synlynk._save_jobs([
        {
            "id": "job-noreceipt",
            "agent": "claude",
            "story_id": "story-noreceipt",
            "task": "implement the thing",
            "pid": 99999999,
            "log_file": str(log_path),
            "started_at": "2026-08-07T18:00:00",
            "ended_at": None,
            "status": "running",
            "exit_code": None,
        }
    ])

    monkeypatch.setattr(synlynk.os, "waitpid", lambda pid, opts: (pid, 0))

    synlynk._reconcile_jobs()
    out = capsys.readouterr().out

    jobs = synlynk._load_jobs()
    reconciled = next(job for job in jobs if job["id"] == "job-noreceipt")

    assert reconciled["status"] == "task_delivery_failed"
    assert "TASK_DELIVERY_FAILED" in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_jobs.py -k "task_delivery_failed_when_marker_absent" -v`
Expected: FAIL — `reconciled["status"]` is `"completed"`, not `"task_delivery_failed"`

- [ ] **Step 3: Wire the classifier into the waitpid-reaped branch**

In `synlynk/jobs.py`, find this existing code inside the `if waitpid_reaped:` block:

```python
            permission_denied = False
            if waitpid_exit_code == 0:
                job["status"] = "completed"
                job["exit_code"] = 0
            elif waitpid_exit_code is not None:
                job["status"] = "failed"
                job["exit_code"] = waitpid_exit_code
            else:
                job["status"] = "unknown"
                job["exit_code"] = None
            if job.get("status") != "completed" and git_state and git_state.get("remote_has_activity") and not git_state.get("has_activity"):
                job["status"] = "completed"
                job["exit_code"] = 0
            if log_text:
                permission_denied = _log_has_permission_denied_signature(log_text)
                if permission_denied:
                    job["status"] = "permission_denied"
```

Immediately after that block (still before the `HARNESS_TIMEOUT_PATTERNS` loop that follows), add:

```python
            task_delivery = {"hard_fail": False, "warn": False}
            if log_text and not permission_denied:
                task_sha256_for_receipt = None
                if job.get("task"):
                    task_sha256_for_receipt = hashlib.sha256(job["task"].encode("utf-8")).hexdigest()
                receipt_status = _check_task_receipt(log_text, task_sha256_for_receipt)
                has_corroborating_activity = bool(
                    git_state and (git_state.get("has_activity") or git_state.get("remote_has_activity"))
                )
                task_delivery = _classify_task_delivery(receipt_status, has_corroborating_activity)
                if task_delivery["hard_fail"]:
                    job["status"] = "task_delivery_failed"
```

`import hashlib` is already present at the top of `synlynk/jobs.py` — confirm with `grep -n "^import hashlib" synlynk/jobs.py`; if it is not there, add it (Task 5 in the prior #720 plan added it for `_task_sha256_and_preview`, so it should already exist).

Next, find the existing summary-status block:

```python
            summary_status = None
            summary_note = None
            if permission_denied:
                summary_status = "PERMISSION_DENIED (headless auto-denied)"
                summary_note = (
                    "headless permission auto-denial detected from log contents "
                    "(response empty, num_turns <= 1, or explicit no-output marker)"
                )
            if job.get("status") == "unknown":
                summary_status = terminal_status_for_unknown_exit()
            if job.get("status") == "completed":
                _finalize_completed_worktree_job(job, git_state)
                _apply_dispatch_gate(job)
```

Replace with:

```python
            summary_status = None
            summary_note = None
            if permission_denied:
                summary_status = "PERMISSION_DENIED (headless auto-denied)"
                summary_note = (
                    "headless permission auto-denial detected from log contents "
                    "(response empty, num_turns <= 1, or explicit no-output marker)"
                )
            elif task_delivery["hard_fail"]:
                summary_status = "TASK_DELIVERY_FAILED"
                summary_note = (
                    f"task receipt check failed ({receipt_status}); no corroborating "
                    "git activity found in worktree (see #720 receipt protocol)"
                )
            elif task_delivery["warn"]:
                summary_note = (
                    f"⚠ task-receipt: {receipt_status}, but real work detected in "
                    "the worktree — not blocking (see #720 receipt protocol)"
                )
                _write_sentinel_alert(
                    "WARN",
                    "TASK_RECEIPT_WARN",
                    f"Job {job.get('id')} on agent '{job.get('agent')}' skipped/mismatched the "
                    f"task receipt marker ({receipt_status}) but real work landed in its worktree — "
                    "not blocking, flagging for review.",
                    sentinel_path,
                )
            if job.get("status") == "unknown":
                summary_status = terminal_status_for_unknown_exit()
            if job.get("status") == "completed":
                _finalize_completed_worktree_job(job, git_state)
                _apply_dispatch_gate(job)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_jobs.py -k "task_delivery_failed_when_marker_absent" -v`
Expected: PASS

- [ ] **Step 5: Run the full reconciliation test file to check for regressions**

Run: `pytest tests/test_jobs.py -v`
Expected: all tests PASS (this confirms the `permission_denied` and plain-completion paths still behave as before — `task_delivery` only overrides status when `permission_denied` is `False`)

- [ ] **Step 6: Commit**

```bash
git add synlynk/jobs.py tests/test_jobs.py
git commit -m "feat: classify TASK_DELIVERY_FAILED in waitpid-reaped reconciliation (#720)"
```

---

### Task 5: Wire classification into the dead-pid reconciliation block

**Files:**
- Modify: `synlynk/jobs.py` (the `ProcessLookupError` branch inside `_reconcile_jobs()`, currently spanning roughly lines 1226-1408 — locate by `except ProcessLookupError:` and ending at the `print(summary, end="")` call that follows it)
- Test: `tests/test_jobs.py`

This mirrors Task 4 for the second reconciliation branch (the one exercised by `monkeypatch.setattr(synlynk.os, "kill", ...)`, which is the pattern the existing `test_reconcile_jobs_marks_permission_denied_headless_auto_denial` and `test_reconcile_jobs_summary_includes_task_sha256_matching_local_computation` tests already use).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_jobs.py`:

```python
def test_reconcile_jobs_dead_pid_marks_task_delivery_failed_when_marker_absent(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    import synlynk

    log_path = tmp_path / ".synlynk" / "logs" / "job-deadpid-noreceipt.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("worked on it, no receipt marker anywhere\n")
    (log_path.parent / "job-deadpid-noreceipt.log.exit").write_text("0")

    synlynk._save_jobs([
        {
            "id": "job-deadpid-noreceipt",
            "agent": "grok",
            "story_id": "story-deadpid",
            "task": "wire the canvas renderer",
            "pid": 99999999,
            "log_file": str(log_path),
            "started_at": "2026-08-07T19:00:00",
            "ended_at": None,
            "status": "running",
            "exit_code": None,
        }
    ])

    monkeypatch.setattr(synlynk.os, "kill", lambda *a, **kw: (_ for _ in ()).throw(ProcessLookupError()))

    synlynk._reconcile_jobs()
    out = capsys.readouterr().out

    jobs = synlynk._load_jobs()
    reconciled = next(job for job in jobs if job["id"] == "job-deadpid-noreceipt")

    assert reconciled["status"] == "task_delivery_failed"
    assert "TASK_DELIVERY_FAILED" in out


def test_reconcile_jobs_dead_pid_warns_but_does_not_fail_when_activity_present(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    import subprocess
    import synlynk

    worktree = tmp_path / "wt"
    worktree.mkdir()
    subprocess.run(["git", "init", "-q", str(worktree)], check=True)
    subprocess.run(["git", "-C", str(worktree), "config", "user.email", "t@t.com"], check=True)
    subprocess.run(["git", "-C", str(worktree), "config", "user.name", "t"], check=True)
    (worktree / "README.md").write_text("hello")
    subprocess.run(["git", "-C", str(worktree), "add", "."], check=True)
    subprocess.run(["git", "-C", str(worktree), "commit", "-q", "-m", "init"], check=True)
    (worktree / "feature.py").write_text("x = 1\n")
    subprocess.run(["git", "-C", str(worktree), "add", "."], check=True)
    subprocess.run(["git", "-C", str(worktree), "commit", "-q", "-m", "real work"], check=True)

    log_path = tmp_path / ".synlynk" / "logs" / "job-deadpid-warn.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("did real work but forgot the receipt marker\n")
    (log_path.parent / "job-deadpid-warn.log.exit").write_text("0")

    synlynk._save_jobs([
        {
            "id": "job-deadpid-warn",
            "agent": "grok",
            "story_id": "story-warn",
            "task": "wire the canvas renderer",
            "pid": 99999999,
            "log_file": str(log_path),
            "worktree_path": str(worktree),
            "worktree_branch": "dispatch/grok/job-deadpid-warn",
            "started_at": "2026-08-07T19:00:00",
            "ended_at": None,
            "status": "running",
            "exit_code": None,
        }
    ])

    monkeypatch.setattr(synlynk.os, "kill", lambda *a, **kw: (_ for _ in ()).throw(ProcessLookupError()))

    synlynk._reconcile_jobs()
    out = capsys.readouterr().out

    jobs = synlynk._load_jobs()
    reconciled = next(job for job in jobs if job["id"] == "job-deadpid-warn")

    assert reconciled["status"] != "task_delivery_failed"
    assert "task-receipt" in out
```

Note: `test_reconcile_jobs_dead_pid_warns_but_does_not_fail_when_activity_present` depends on `_resolve_worktree_base_commit()` and `_finalize_completed_worktree_job()`/`_apply_dispatch_gate()` behaving reasonably against a bare local repo with no remote. If either raises because there's no configured `base_branch`/remote, check `_finalize_completed_worktree_job()`'s handling of a missing base branch (it should no-op gracefully — read the function before assuming this test needs adjustment) and adapt the test setup (e.g. add `"base_branch": None` explicitly, which is already the default from `job.get(...)`) rather than weakening the assertion.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_jobs.py -k "dead_pid_marks_task_delivery_failed or dead_pid_warns_but_does_not_fail" -v`
Expected: FAIL — both jobs currently reconcile to `"completed"` with no receipt handling

- [ ] **Step 3: Wire the classifier into the dead-pid branch**

In `synlynk/jobs.py`, find this existing code inside the `except ProcessLookupError:` block:

```python
            permission_denied = False
            job["ended_at"] = now
            changed = True

            if log_file and os.path.exists(log_file):
                with open(log_file) as f:
                    log_text = f.read()
                permission_denied = _log_has_permission_denied_signature(log_text)
                if permission_denied:
                    job["status"] = "permission_denied"
                if job.get("status") != "completed":
```

Replace the `if permission_denied: job["status"] = "permission_denied"` two lines with:

```python
                permission_denied = _log_has_permission_denied_signature(log_text)
                if permission_denied:
                    job["status"] = "permission_denied"
                task_delivery = {"hard_fail": False, "warn": False}
                receipt_status = None
                if not permission_denied:
                    task_sha256_for_receipt = None
                    if job.get("task"):
                        task_sha256_for_receipt = hashlib.sha256(job["task"].encode("utf-8")).hexdigest()
                    receipt_status = _check_task_receipt(log_text, task_sha256_for_receipt)
                    has_corroborating_activity = bool(
                        git_state and (git_state.get("has_activity") or git_state.get("remote_has_activity"))
                    )
                    task_delivery = _classify_task_delivery(receipt_status, has_corroborating_activity)
                    if task_delivery["hard_fail"]:
                        job["status"] = "task_delivery_failed"
                if job.get("status") != "completed":
```

(The `if job.get("status") != "completed":` line that follows is the existing `HARNESS_TIMEOUT_PATTERNS` loop guard — leave it and everything after it in that inner block unchanged.)

Then find the existing summary block further down:

```python
            summary_note = None
            summary_status = None
            summary_files_touched = _pkg("_worktree_files_touched")(job.get("worktree_path"))
            if permission_denied:
                summary_status = "PERMISSION_DENIED (headless auto-denied)"
                summary_note = (
                    "headless permission auto-denial detected from log contents "
                    "(response empty, num_turns <= 1, or explicit no-output marker)"
                )
            if git_state and git_state.get("remote_has_activity") and not git_state.get("has_activity"):
```

Replace the `if permission_denied:` block with:

```python
            summary_note = None
            summary_status = None
            summary_files_touched = _pkg("_worktree_files_touched")(job.get("worktree_path"))
            if permission_denied:
                summary_status = "PERMISSION_DENIED (headless auto-denied)"
                summary_note = (
                    "headless permission auto-denial detected from log contents "
                    "(response empty, num_turns <= 1, or explicit no-output marker)"
                )
            elif task_delivery["hard_fail"]:
                summary_status = "TASK_DELIVERY_FAILED"
                summary_note = (
                    f"task receipt check failed ({receipt_status}); no corroborating "
                    "git activity found in worktree (see #720 receipt protocol)"
                )
            elif task_delivery["warn"]:
                summary_note = (
                    f"⚠ task-receipt: {receipt_status}, but real work detected in "
                    "the worktree — not blocking (see #720 receipt protocol)"
                )
                _write_sentinel_alert(
                    "WARN",
                    "TASK_RECEIPT_WARN",
                    f"Job {job.get('id')} on agent '{job.get('agent')}' skipped/mismatched the "
                    f"task receipt marker ({receipt_status}) but real work landed in its worktree — "
                    "not blocking, flagging for review.",
                    sentinel_path,
                )
            if git_state and git_state.get("remote_has_activity") and not git_state.get("has_activity"):
```

Do not touch the `elif reclassified_failed_unverified:` / `elif ambiguous_exit and git_state:` / `elif job.get("status") == "unknown":` branches that follow — they remain reachable exactly as before, since they're separate `elif`s off the same `if git_state and git_state.get("remote_has_activity")...` chain, not the block being edited here.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_jobs.py -k "dead_pid_marks_task_delivery_failed or dead_pid_warns_but_does_not_fail" -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Run the full reconciliation test file to check for regressions**

Run: `pytest tests/test_jobs.py -v`
Expected: all tests PASS, including the pre-existing `test_reconcile_jobs_marks_permission_denied_headless_auto_denial` and `test_reconcile_jobs_summary_includes_task_sha256_matching_local_computation`

- [ ] **Step 6: Commit**

```bash
git add synlynk/jobs.py tests/test_jobs.py
git commit -m "feat: classify TASK_DELIVERY_FAILED in dead-pid reconciliation (#720)"
```

---

### Task 6: `selftest --matrix` receipt-compliance cell

**Files:**
- Modify: `synlynk/fleet.py` (add a new function `live_agent_receipt_check()` near `live_agent_smoke()`, currently around line 354-388; wire it into `run_matrix_live()`, currently around line 445+)
- Test: `tests/test_fleet.py` (create if it does not already cover `fleet.py` — check with `ls tests/test_fleet.py` first; if a fleet test file already exists, add to it instead of creating a new one)

- [ ] **Step 1: Confirm the existing test file location**

Run: `ls tests/test_fleet.py 2>/dev/null || grep -rl "run_matrix_live\|live_agent_smoke" tests/`

Use whatever file already imports/tests `synlynk.fleet` as the target for the new tests below. If none exists, create `tests/test_fleet.py`.

- [ ] **Step 2: Write the failing tests**

Add to the target test file (adjust the import path if `synlynk.fleet` is imported differently elsewhere in that file — match the existing convention):

```python
def test_live_agent_receipt_check_green_when_marker_is_first_line(monkeypatch):
    import synlynk.fleet as fleet_mod

    class FakeProc:
        returncode = 0
        stdout = "SYNLYNK_TASK_RECEIVED: abc123\nok done\n"
        stderr = ""

    monkeypatch.setattr(fleet_mod.shutil, "which", lambda cli: "/usr/bin/fake-cli")
    monkeypatch.setattr(fleet_mod.subprocess, "run", lambda *a, **kw: FakeProc())

    result = fleet_mod.live_agent_receipt_check("claude", task_sha256="abc123")

    assert result.status == "green"


def test_live_agent_receipt_check_red_when_marker_missing(monkeypatch):
    import synlynk.fleet as fleet_mod

    class FakeProc:
        returncode = 0
        stdout = "did some stuff, no marker\n"
        stderr = ""

    monkeypatch.setattr(fleet_mod.shutil, "which", lambda cli: "/usr/bin/fake-cli")
    monkeypatch.setattr(fleet_mod.subprocess, "run", lambda *a, **kw: FakeProc())

    result = fleet_mod.live_agent_receipt_check("claude", task_sha256="abc123")

    assert result.status == "red"


def test_live_agent_receipt_check_red_when_marker_not_first_line(monkeypatch):
    import synlynk.fleet as fleet_mod

    class FakeProc:
        returncode = 0
        stdout = "starting up\nSYNLYNK_TASK_RECEIVED: abc123\n"
        stderr = ""

    monkeypatch.setattr(fleet_mod.shutil, "which", lambda cli: "/usr/bin/fake-cli")
    monkeypatch.setattr(fleet_mod.subprocess, "run", lambda *a, **kw: FakeProc())

    result = fleet_mod.live_agent_receipt_check("claude", task_sha256="abc123")

    assert result.status == "red"


def test_run_matrix_live_includes_receipt_cell_per_agent_in_mock_mode():
    import synlynk.fleet as fleet_mod

    results = fleet_mod.run_matrix_live(mock=True)

    receipt_cells = [r for r in results if r.cell.startswith("live_receipt:")]
    assert len(receipt_cells) == 4
    assert all(r.status == "green" for r in receipt_cells)
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest <target-test-file> -k "receipt_check or run_matrix_live_includes_receipt" -v`
Expected: FAIL with `AttributeError: module 'synlynk.fleet' has no attribute 'live_agent_receipt_check'`

- [ ] **Step 4: Implement `live_agent_receipt_check()`**

In `synlynk/fleet.py`, directly below `live_agent_smoke()` (after its closing `return MatrixCellResult(...)` around line 431-438), add:

```python
def live_agent_receipt_check(home: str, task_sha256: str, *, timeout_s: int = _LIVE_SMOKE_TIMEOUT_S) -> MatrixCellResult:
    """Runs one real headless CLI turn for *home* and checks receipt-marker
    compliance: the CLI must echo SYNLYNK_TASK_RECEIVED: <digest> as its
    literal first output line (see #720 receipt protocol)."""
    from synlynk.jobs import _check_task_receipt
    from synlynk.dispatch import _render_task_receipt_instruction

    baseline = AGENT_CAPABILITY_BASELINES.get(home) or {}
    cli = baseline.get("cli", home)
    cell = f"live_receipt:{home}"
    if shutil.which(cli) is None:
        return MatrixCellResult(
            home=home, cell=cell, tier=2, status="red",
            detail=f"{cli} not on PATH", cost_usd=0.0,
        )

    prompt = _render_task_receipt_instruction(task_sha256) + _LIVE_SMOKE_PROMPT
    ni = list(baseline.get("non_interactive_flags") or [])
    prompt_via_arg = baseline.get("prompt_via_arg", False)
    prompt_flag = baseline.get("prompt_flag")

    try:
        if home == "claude":
            cmd = [cli, "--print", prompt]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s)
        elif home == "codex":
            cmd = [cli, "exec", "-", "-s", "workspace-write"]
            proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=timeout_s)
        elif prompt_via_arg and prompt_flag:
            cmd = [cli] + ni + [prompt_flag, prompt]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s)
        else:
            cmd = [cli] + ni
            proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=timeout_s)
    except subprocess.TimeoutExpired:
        return MatrixCellResult(
            home=home, cell=cell, tier=2, status="red",
            detail=f"timeout after {timeout_s}s", cost_usd=_LIVE_SMOKE_COST_USD,
        )
    except OSError as exc:
        return MatrixCellResult(
            home=home, cell=cell, tier=2, status="red",
            detail=f"spawn failed: {exc}", cost_usd=0.0,
        )

    receipt_status = _check_task_receipt(proc.stdout or "", task_sha256)
    ok = proc.returncode == 0 and receipt_status == "ok"
    return MatrixCellResult(
        home=home, cell=cell, tier=2,
        status="green" if ok else "red",
        detail=f"exit={proc.returncode} receipt={receipt_status}",
        cost_usd=_LIVE_SMOKE_COST_USD if proc.returncode == 0 else 0.05,
    )
```

- [ ] **Step 5: Wire it into `run_matrix_live()`**

In `synlynk/fleet.py`, find `run_matrix_live()` (around line 445-480). Locate the loop that calls `live_agent_smoke` (or `dispatch_fn`) per Core-4 agent and appends the result to `results`, and the `mock=True` branch that stubs zero-cost green results. Add a second pass, mirroring the existing structure, that also calls `live_agent_receipt_check` per agent with a fixed test digest (e.g. `hashlib.sha256(b"synlynk matrix receipt check").hexdigest()`), respecting the same `budget_usd` accounting and `mock=True` stub behavior already used for the smoke cells. Read the surrounding ~40 lines of `run_matrix_live()` before editing so the new cells reuse the same budget-tracking variable (`spent`) and mock-stub pattern rather than duplicating divergent logic.

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest <target-test-file> -k "receipt_check or run_matrix_live_includes_receipt" -v`
Expected: PASS (4 tests)

- [ ] **Step 7: Run the full test suite for this file**

Run: `pytest <target-test-file> -v`
Expected: all tests PASS

- [ ] **Step 8: Commit**

```bash
git add synlynk/fleet.py tests/test_fleet.py
git commit -m "feat: add live receipt-compliance matrix cell per agent (#720)"
```

Do not run a bare `pytest` at the repo root — the repo root contains many stale nested `worktrees/job-*` directories from unrelated past dispatches that pytest's default collection sweeps in, causing unrelated collection errors. Always scope test runs to the specific file(s) under test, e.g. `pytest tests/test_dispatch.py tests/test_jobs.py tests/test_fleet.py -q`.

---

### Task 7: README documentation

**Files:**
- Modify: `README.md` (add a short section after the existing dispatch fail-closed guard documentation added by #720 sub-project 1 — search for "fail-closed" or "#720" to find that section)

- [ ] **Step 1: Add documentation**

Add this block directly after the existing `--task` fail-closed guard paragraph in `README.md`:

```markdown
Every dispatched agent is also asked to echo a receipt marker
(`SYNLYNK_TASK_RECEIVED: <task_sha256>`) as its literal first line of
output, confirming it received the exact task text before doing any
work. If a job's log is missing this marker (or prints it late, or with
the wrong digest) and no corroborating git activity shows up in its
worktree, Synlynk marks the job `task_delivery_failed` and skips
auto-finalize/push for that worktree — the files stay in place for
audit. If real work *did* land despite a missing/late marker, the job
is not blocked; it's flagged with a non-blocking WARN note instead
(see #720).
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: document task receipt protocol and TASK_DELIVERY_FAILED (#720)"
```

---

## Plan Self-Review Notes

- **Spec coverage:** §1 (marker + injection) → Task 1. §2 (detection + classification) → Tasks 2, 4, 5. §3 (WARN corroboration) → Tasks 3, 4, 5. §4 (data flow) → covered by Tasks 1-5 collectively. §5 (rollout scope, all 4 agents) → Task 1's prompt injection is agent-agnostic by construction; Task 6 explicitly tests all 4. §6 (testing incl. `selftest --matrix`) → Task 6.
- **Placeholder scan:** none found; Task 6 Step 5 intentionally asks the implementer to read ~40 lines of existing code before wiring rather than embedding a full untested rewrite of `run_matrix_live()`'s budget-loop, since that loop's exact current shape wasn't fully captured during planning — this is a scoped judgment call, not a placeholder, and Step 6-7 verify the result with real tests either way.
- **Type consistency:** `_check_task_receipt()` (Task 2) and `_classify_task_delivery()` (Task 3) signatures are used identically in Tasks 4, 5, and 6 (via `live_agent_receipt_check`'s import).
