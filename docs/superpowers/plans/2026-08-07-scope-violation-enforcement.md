# Scope Violation Enforcement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enforce declared dispatch scope so a design-only/docs-only job that drifts into
out-of-scope file changes is marked `SCOPE_VIOLATION` instead of being silently finalized,
pushed, and turned into a PR — closing #720 requirement 4, tracked as the second of three
sub-projects under #769.

**Architecture:** A new repeatable `--scope-paths` CLI flag threads a plain `scope_paths` list
into the job dict at dispatch time (no schema change — jobs persist as a JSON list via
`_load_jobs()`/`_save_jobs()`). At reconciliation, `_inspect_worktree_git_state()` gains a
`changed_files` field; a new `_check_scope_compliance()` helper compares those files against the
declared globs with `fnmatch`. Both `jobs`-table reconciliation call sites check compliance
before calling `_finalize_completed_worktree_job()`/`_apply_dispatch_gate()` — on violation they
set `job["status"] = "SCOPE_VIOLATION"` and skip both calls entirely, leaving the worktree
untouched. A compliant scope-declared job still finalizes normally (commit + push unconditional),
but `_finalize_completed_worktree_job()` gains a guard that skips `_maybe_open_worktree_pr()`
unless `job.get("requires_gh_write")` is set, so a design-only job doesn't silently open a PR.

**Tech Stack:** Python 3 stdlib only (`fnmatch`, `subprocess`, `json`) — no new dependencies.

---

### Task 1: `--scope-paths` CLI flag and `dispatch_agent()` threading

**Files:**
- Modify: `synlynk/cli.py:561-568` (dispatch_parser argument block, right after `--revoke`)
- Modify: `synlynk/cli.py:1014-1023` (`dispatch_agent(...)` call)
- Modify: `synlynk/dispatch.py:1610-1621` (`dispatch_agent()` signature)
- Modify: `synlynk/dispatch.py:1985-2016` (job dict construction)
- Test: `tests/test_dispatch.py`

- [ ] **Step 1: Write the failing test**

First check the exact test file used for `dispatch_agent()` unit tests:

```bash
grep -n "^def test_dispatch_agent" tests/test_dispatch.py | head -5
```

Add this test to `tests/test_dispatch.py` (match the existing `dispatch_agent()` test fixture
style already in that file — mock `subprocess.Popen`, `_pkg("_load_jobs")`/`_pkg("_save_jobs")`,
and any worktree-setup helpers the existing tests already mock; do not re-derive those mocks from
scratch, copy the pattern from the nearest existing `test_dispatch_agent_*` test in the file):

```python
def test_dispatch_agent_stores_scope_paths_and_requires_gh_write_on_job(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import synlynk.dispatch as dispatch_mod

    saved = {}

    def fake_save_jobs(jobs):
        saved["jobs"] = jobs

    monkeypatch.setattr(dispatch_mod, "_pkg", lambda name, default=None: {
        "_load_jobs": lambda: [],
        "_save_jobs": fake_save_jobs,
    }.get(name, default))

    class FakeProc:
        pid = 12345

    monkeypatch.setattr(dispatch_mod.subprocess, "Popen", lambda *a, **kw: FakeProc())
    monkeypatch.setattr(dispatch_mod, "_permissions_to_flags", lambda agent, perms: [])
    monkeypatch.setattr(dispatch_mod, "_resolve_dispatch_permissions", lambda *a, **kw: [])

    job = dispatch_mod.dispatch_agent(
        "codex", "write a spec only",
        scope_paths=["docs/superpowers/specs/**"],
        requires_gh_write=False,
        skip_preflight=True,
    )

    assert job["scope_paths"] == ["docs/superpowers/specs/**"]
    assert job["requires_gh_write"] is False
```

If mocking the full `dispatch_agent()` call graph turns out to need more fixtures than shown
above (it has many side effects: worktree creation, fencing, cost estimation), find the nearest
existing passing test for `dispatch_agent()` in `tests/test_dispatch.py` and copy its exact mock
set, only changing the assertions to check `job["scope_paths"]`/`job["requires_gh_write"]`.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_dispatch.py::test_dispatch_agent_stores_scope_paths_and_requires_gh_write_on_job -v`
Expected: FAIL with `TypeError: dispatch_agent() got an unexpected keyword argument 'scope_paths'`

- [ ] **Step 3: Add the CLI flag**

In `synlynk/cli.py`, immediately after the existing `--revoke` argument (around line 568), add:

```python
    dispatch_parser.add_argument(
        "--scope-paths", action="append", default=[],
        dest="scope_paths",
        help="Restrict this dispatch to only touching files matching this glob (repeatable, "
             "e.g. --scope-paths 'docs/superpowers/specs/**'). Declaring this denies automatic "
             "PR creation by default unless --requires-gh-write is also set. See #769.",
    )
```

- [ ] **Step 4: Thread the flag through the `dispatch_agent()` call in cli.py**

In `synlynk/cli.py`, the existing `dispatch_agent(...)` call (around line 1014) reads:

```python
            job = dispatch_agent(args.agent, args.task, story_id=args.story_id,
                                 force_agent=getattr(args, "force_agent", False),
                                 requires_gh_write=getattr(args, "requires_gh_write", False),
                                 requires=getattr(args, "requires", []),
                                 context_mode=getattr(args, "context_mode", "task"),
                                 skip_preflight=getattr(args, "skip_preflight", False),
                                 base=getattr(args, "base", None),
                                 grants=getattr(args, "grant", []),
                                 revokes=getattr(args, "revoke", []),
                                 issue=getattr(args, "issue", None))
```

Add `scope_paths=getattr(args, "scope_paths", [])` as a new keyword argument:

```python
            job = dispatch_agent(args.agent, args.task, story_id=args.story_id,
                                 force_agent=getattr(args, "force_agent", False),
                                 requires_gh_write=getattr(args, "requires_gh_write", False),
                                 requires=getattr(args, "requires", []),
                                 context_mode=getattr(args, "context_mode", "task"),
                                 skip_preflight=getattr(args, "skip_preflight", False),
                                 base=getattr(args, "base", None),
                                 grants=getattr(args, "grant", []),
                                 revokes=getattr(args, "revoke", []),
                                 issue=getattr(args, "issue", None),
                                 scope_paths=getattr(args, "scope_paths", []))
```

- [ ] **Step 5: Add `scope_paths` parameter to `dispatch_agent()`**

In `synlynk/dispatch.py`, the signature at line 1610 reads:

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
                   base: str = None) -> dict:
```

Add `scope_paths: list = None` as a new parameter:

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
                   scope_paths: list = None) -> dict:
```

- [ ] **Step 6: Store `scope_paths`/`requires_gh_write` on the job dict**

In `synlynk/dispatch.py`, the job dict construction (around line 1985) reads:

```python
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
    }
```

Add `"scope_paths"` and `"requires_gh_write"` keys:

```python
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
    }
```

- [ ] **Step 7: Run test to verify it passes**

Run: `pytest tests/test_dispatch.py::test_dispatch_agent_stores_scope_paths_and_requires_gh_write_on_job -v`
Expected: PASS

- [ ] **Step 8: Run the full dispatch test suite to check for regressions**

Run: `pytest tests/test_dispatch.py -v`
Expected: all tests pass (existing `dispatch_agent()` callers all use keyword args or omit
`scope_paths` entirely, so the new parameter defaulting to `None` must not break any existing
call site)

- [ ] **Step 9: Commit**

```bash
git add synlynk/cli.py synlynk/dispatch.py tests/test_dispatch.py
git commit -m "feat: add --scope-paths dispatch flag, thread into job record"
```

---

### Task 2: `changed_files` field on `_inspect_worktree_git_state()`

**Files:**
- Modify: `synlynk/jobs.py:614-679` (`_inspect_worktree_git_state()`)
- Test: `tests/test_jobs.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_jobs.py`, following the `fake_run`-monkeypatching style already used by
`test_maybe_open_worktree_pr_uses_resolved_base_branch` in that file:

```python
def test_inspect_worktree_git_state_includes_changed_files_from_diff_and_status(tmp_path, monkeypatch):
    import subprocess
    import synlynk.jobs as jobs_mod

    worktree_path = tmp_path / "repo"
    worktree_path.mkdir()
    prefix = ["git", "-C", str(worktree_path)]

    def fake_run(cmd, **kwargs):
        cmd = list(cmd)
        if cmd == prefix + ["status", "--short"]:
            return subprocess.CompletedProcess(cmd, 0, stdout=" M synlynk/jobs.py\n", stderr="")
        if cmd == prefix + ["rev-list", "--count", "deadbeef..HEAD"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="1\n", stderr="")
        if cmd == prefix + ["diff", "--name-only", "deadbeef..HEAD"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="docs/superpowers/specs/foo.md\n", stderr="")
        raise AssertionError(f"unexpected command: {cmd}")

    monkeypatch.setattr(jobs_mod.subprocess, "run", fake_run)
    monkeypatch.setattr(
        jobs_mod, "_pkg",
        lambda name, default=None: (
            lambda wt: {"base_commit": "deadbeef", "base_ref": "origin/main"}
        ) if name == "_resolve_worktree_base_commit" else default,
    )

    git_state = jobs_mod._inspect_worktree_git_state(str(worktree_path), "feat/x", "2026-08-07T00:00:00")

    assert git_state["changed_files"] == ["docs/superpowers/specs/foo.md", "synlynk/jobs.py"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_jobs.py::test_inspect_worktree_git_state_includes_changed_files_from_diff_and_status -v`
Expected: FAIL with `KeyError: 'changed_files'`

- [ ] **Step 3: Implement `changed_files` collection**

In `synlynk/jobs.py`, `_inspect_worktree_git_state()` (lines 614-679) currently ends with:

```python
    return {
        "worktree_path": worktree_path,
        "dirty": dirty,
        "commits_ahead": commits_ahead,
        "base_ref": base_ref,
        "base_commit": base_commit,
        "has_activity": dirty or commits_ahead > 0,
        "remote_ref": remote_branch_ref,
        "remote_commit_count": remote_branch_commit_count,
        "remote_files_touched": remote_branch_files_touched,
        "remote_has_activity": remote_branch_has_activity,
    }
```

Insert changed-file collection immediately before that `return`, and add the key to the dict:

```python
    changed_files = []
    if base_commit:
        try:
            diff_result = subprocess.run(
                ["git", "-C", worktree_path, "diff", "--name-only", f"{base_commit}..HEAD"],
                capture_output=True,
                text=True,
                check=False,
            )
        except Exception:
            diff_result = None
        if diff_result is not None and diff_result.returncode == 0:
            changed_files.extend(p for p in (diff_result.stdout or "").splitlines() if p)
    if dirty:
        changed_files.extend(_collect_worktree_status_paths(worktree_path))

    return {
        "worktree_path": worktree_path,
        "dirty": dirty,
        "commits_ahead": commits_ahead,
        "base_ref": base_ref,
        "base_commit": base_commit,
        "has_activity": dirty or commits_ahead > 0,
        "remote_ref": remote_branch_ref,
        "remote_commit_count": remote_branch_commit_count,
        "remote_files_touched": remote_branch_files_touched,
        "remote_has_activity": remote_branch_has_activity,
        "changed_files": sorted(set(changed_files)),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_jobs.py::test_inspect_worktree_git_state_includes_changed_files_from_diff_and_status -v`
Expected: PASS

- [ ] **Step 5: Run the full jobs test suite to check for regressions**

Run: `pytest tests/test_jobs.py tests/test_synlynk.py -v -k "inspect_worktree or git_state"`
Expected: all pass — this touches a widely-used helper, so also run the full suite:

Run: `pytest tests/test_jobs.py tests/test_synlynk.py -v`
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add synlynk/jobs.py tests/test_jobs.py
git commit -m "feat: add changed_files field to _inspect_worktree_git_state()"
```

---

### Task 3: `_check_scope_compliance()` helper

**Files:**
- Modify: `synlynk/jobs.py` (add near `_job_has_real_work_landed`, line 79 — new function
  immediately after it, i.e. starting at line 84)
- Test: `tests/test_jobs.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_jobs.py`:

```python
def test_check_scope_compliance_all_files_match_single_glob():
    from synlynk.jobs import _check_scope_compliance

    assert _check_scope_compliance(
        ["docs/superpowers/specs/foo.md", "docs/superpowers/specs/bar.md"],
        ["docs/superpowers/specs/*"],
    ) is True


def test_check_scope_compliance_files_match_any_of_several_globs():
    from synlynk.jobs import _check_scope_compliance

    assert _check_scope_compliance(
        ["docs/superpowers/specs/foo.md", "docs/blog/README.md"],
        ["docs/superpowers/specs/*", "docs/blog/*"],
    ) is True


def test_check_scope_compliance_file_matching_no_glob_is_violation():
    from synlynk.jobs import _check_scope_compliance

    assert _check_scope_compliance(
        ["docs/superpowers/specs/foo.md", "synlynk/jobs.py"],
        ["docs/superpowers/specs/*"],
    ) is False


def test_check_scope_compliance_empty_scope_paths_is_always_compliant():
    from synlynk.jobs import _check_scope_compliance

    assert _check_scope_compliance(["synlynk/jobs.py"], []) is True
    assert _check_scope_compliance(["synlynk/jobs.py"], None) is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_jobs.py -v -k test_check_scope_compliance`
Expected: FAIL with `ImportError: cannot import name '_check_scope_compliance'`

- [ ] **Step 3: Implement `_check_scope_compliance()`**

In `synlynk/jobs.py`, add `import fnmatch` to the existing import block at the top of the file
(alongside the existing `import hashlib`, `import json`, etc. at lines 3-11):

```python
import fnmatch
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
from typing import Optional
```

Then add the new function immediately after `_job_has_real_work_landed()` (line 79-83):

```python
def _check_scope_compliance(changed_files: list, scope_paths: list) -> bool:
    """True if every changed file matches at least one declared scope glob.

    An empty scope_paths list means no scope was declared -- always compliant (no-op).
    """
    if not scope_paths:
        return True
    for path in changed_files or []:
        if not any(fnmatch.fnmatch(path, pattern) for pattern in scope_paths):
            return False
    return True
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_jobs.py -v -k test_check_scope_compliance`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add synlynk/jobs.py tests/test_jobs.py
git commit -m "feat: add _check_scope_compliance() helper"
```

---

### Task 4: Wire `SCOPE_VIOLATION` into both `jobs`-table reconciliation call sites

**Files:**
- Modify: `synlynk/jobs.py:1197-1201` (waitpid-reaped branch)
- Modify: `synlynk/jobs.py:1382-1386` (dead-pid branch)
- Modify: `synlynk/jobs.py:1691` (`_render_legacy_jobs()` completed-count filter)
- Test: `tests/test_synlynk.py`

- [ ] **Step 1: Write the failing test — violation blocks finalize**

Add to `tests/test_synlynk.py`, following the `fake_run` + `_inspect_worktree_git_state`
monkeypatch style used by `test_reconcile_auto_finalizes_dirty_worktree_excluding_generated_files`
in that file (read that test first for the exact job dict shape / log file setup it uses, then
mirror it):

```python
def test_reconcile_marks_scope_violation_when_change_outside_declared_scope(project_dir, monkeypatch, capsys):
    import synlynk as sl
    import synlynk.jobs as jobs_mod

    log_path = ".synlynk/logs/job-scope-bad.log"
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with open(log_path, "w") as f:
        f.write("Input tokens: 10\nOutput tokens: 5\n")
    with open(log_path + ".exit", "w") as f:
        f.write("0")

    worktree_path = os.path.join(os.getcwd(), "worktrees", "job-scope-bad")
    os.makedirs(worktree_path, exist_ok=True)

    sl._save_jobs([{
        "id": "job-scope-bad",
        "agent": "codex",
        "story_id": "story-scope",
        "task": "write only the design doc",
        "pid": 99999999,
        "log_file": log_path,
        "worktree_path": worktree_path,
        "worktree_branch": "dispatch/codex/job-scope-bad",
        "started_at": "2026-08-07T01:00:00",
        "ended_at": None,
        "status": "running",
        "exit_code": None,
        "scope_paths": ["docs/superpowers/specs/**"],
        "requires_gh_write": False,
    }])

    monkeypatch.setattr(sl.os, "kill", lambda *a, **kw: (_ for _ in ()).throw(ProcessLookupError()))
    monkeypatch.setattr(sl, "_inspect_worktree_git_state", lambda *a, **kw: {
        "has_activity": True,
        "remote_has_activity": False,
        "dirty": True,
        "commits_ahead": 0,
        "changed_files": ["synlynk/jobs.py"],
    })

    finalize_calls = []
    monkeypatch.setattr(jobs_mod, "_finalize_completed_worktree_job", lambda *a, **kw: finalize_calls.append(a))

    sl._reconcile_jobs()

    job = sl._load_jobs()[0]
    assert job["status"] == "SCOPE_VIOLATION"
    assert job["scope_violation_files"] == ["synlynk/jobs.py"]
    assert finalize_calls == []

    captured = capsys.readouterr()
    assert "SCOPE_VIOLATION" in captured.out
    assert "synlynk/jobs.py" in captured.out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_synlynk.py::test_reconcile_marks_scope_violation_when_change_outside_declared_scope -v`
Expected: FAIL — `job["status"]` is `"completed"`, not `"SCOPE_VIOLATION"`, because nothing checks
`scope_paths` yet.

- [ ] **Step 3: Wire the check into the waitpid-reaped branch**

In `synlynk/jobs.py`, the waitpid-reaped branch currently reads (around line 1197-1201):

```python
            if job.get("status") == "unknown":
                summary_status = terminal_status_for_unknown_exit()
            if job.get("status") == "completed":
                _finalize_completed_worktree_job(job, git_state)
                _apply_dispatch_gate(job)
```

Replace the `if job.get("status") == "completed":` block with a scope check. This also sets
`summary_status`/`summary_note` (the variables already fed into the `_write_job_summary(...,
status_label=summary_status, note=summary_note, ...)` call a few lines below at line 1215-1216)
so `jobs --summary <id>` surfaces the violation and the out-of-scope file list without any change
to `_write_job_summary()` itself:

```python
            if job.get("status") == "unknown":
                summary_status = terminal_status_for_unknown_exit()
            if job.get("status") == "completed":
                scope_paths = job.get("scope_paths") or []
                if scope_paths and git_state and not _check_scope_compliance(
                    git_state.get("changed_files", []), scope_paths
                ):
                    job["status"] = "SCOPE_VIOLATION"
                    job["scope_violation_files"] = [
                        p for p in git_state.get("changed_files", [])
                        if not any(fnmatch.fnmatch(p, pat) for pat in scope_paths)
                    ]
                    summary_status = "SCOPE_VIOLATION"
                    summary_note = (
                        f"declared scope {scope_paths} but changed files outside it: "
                        f"{job['scope_violation_files']} — finalize/push/PR skipped, "
                        f"worktree left intact for inspection"
                    )
                else:
                    _finalize_completed_worktree_job(job, git_state)
                    _apply_dispatch_gate(job)
```

- [ ] **Step 4: Wire the check into the dead-pid branch**

In `synlynk/jobs.py`, the dead-pid branch currently reads (around line 1382-1386):

```python
            if job.get("status") == "completed":
                _finalize_completed_worktree_job(job, git_state)
                _apply_dispatch_gate(job)
```

Replace it with the same scope check (this branch already has `summary_status`/`summary_note`
in scope from the preceding ambiguous-exit handling at lines 1360-1383, which the scope check
now overrides on violation exactly as in Step 3):

```python
            if job.get("status") == "completed":
                scope_paths = job.get("scope_paths") or []
                if scope_paths and git_state and not _check_scope_compliance(
                    git_state.get("changed_files", []), scope_paths
                ):
                    job["status"] = "SCOPE_VIOLATION"
                    job["scope_violation_files"] = [
                        p for p in git_state.get("changed_files", [])
                        if not any(fnmatch.fnmatch(p, pat) for pat in scope_paths)
                    ]
                    summary_status = "SCOPE_VIOLATION"
                    summary_note = (
                        f"declared scope {scope_paths} but changed files outside it: "
                        f"{job['scope_violation_files']} — finalize/push/PR skipped, "
                        f"worktree left intact for inspection"
                    )
                else:
                    _finalize_completed_worktree_job(job, git_state)
                    _apply_dispatch_gate(job)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_synlynk.py::test_reconcile_marks_scope_violation_when_change_outside_declared_scope -v`
Expected: PASS

- [ ] **Step 6: Write the failing test — compliant scope-only change still finalizes**

Add to `tests/test_synlynk.py`:

```python
def test_reconcile_finalizes_normally_when_change_is_within_declared_scope(project_dir, monkeypatch):
    import synlynk as sl
    import synlynk.jobs as jobs_mod

    log_path = ".synlynk/logs/job-scope-good.log"
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with open(log_path, "w") as f:
        f.write("Input tokens: 10\nOutput tokens: 5\n")
    with open(log_path + ".exit", "w") as f:
        f.write("0")

    worktree_path = os.path.join(os.getcwd(), "worktrees", "job-scope-good")
    os.makedirs(worktree_path, exist_ok=True)

    sl._save_jobs([{
        "id": "job-scope-good",
        "agent": "codex",
        "story_id": "story-scope-good",
        "task": "write only the design doc",
        "pid": 99999999,
        "log_file": log_path,
        "worktree_path": worktree_path,
        "worktree_branch": "dispatch/codex/job-scope-good",
        "started_at": "2026-08-07T01:00:00",
        "ended_at": None,
        "status": "running",
        "exit_code": None,
        "scope_paths": ["docs/superpowers/specs/**"],
        "requires_gh_write": False,
    }])

    monkeypatch.setattr(sl.os, "kill", lambda *a, **kw: (_ for _ in ()).throw(ProcessLookupError()))
    monkeypatch.setattr(sl, "_inspect_worktree_git_state", lambda *a, **kw: {
        "has_activity": True,
        "remote_has_activity": False,
        "dirty": True,
        "commits_ahead": 0,
        "changed_files": ["docs/superpowers/specs/2026-08-07-foo-design.md"],
    })

    finalize_calls = []
    monkeypatch.setattr(jobs_mod, "_finalize_completed_worktree_job", lambda *a, **kw: finalize_calls.append(a))
    monkeypatch.setattr(jobs_mod, "_apply_dispatch_gate", lambda *a, **kw: None)

    sl._reconcile_jobs()

    job = sl._load_jobs()[0]
    assert job["status"] == "completed"
    assert len(finalize_calls) == 1
```

- [ ] **Step 7: Run test to verify it passes**

Run: `pytest tests/test_synlynk.py::test_reconcile_finalizes_normally_when_change_is_within_declared_scope -v`
Expected: PASS (this exercises the `else` branch added in Steps 3-4, which was already
implemented — no new production code needed for this step, it's a regression guard)

- [ ] **Step 8: Update the completed-count filter in `_render_legacy_jobs()`**

In `synlynk/jobs.py`, `_render_legacy_jobs()` (around line 1691) currently reads:

```python
            completed = len([j for j in jobs if j["status"] in ("completed", "failed", "failed_unverified", "permission_denied")])
```

Add `"SCOPE_VIOLATION"` to the tuple so scope-violated jobs count as done rather than appearing
to hang:

```python
            completed = len([j for j in jobs if j["status"] in ("completed", "failed", "failed_unverified", "permission_denied", "SCOPE_VIOLATION")])
```

- [ ] **Step 9: Run the full jobs/synlynk test suite to check for regressions**

Run: `pytest tests/test_jobs.py tests/test_synlynk.py -v`
Expected: all pass

- [ ] **Step 10: Commit**

```bash
git add synlynk/jobs.py tests/test_synlynk.py
git commit -m "feat: wire SCOPE_VIOLATION into jobs-table reconciliation call sites"
```

---

### Task 5: Skip automatic PR creation for scope-declared jobs without `--requires-gh-write`

**Files:**
- Modify: `synlynk/jobs.py:512-527` (`_finalize_completed_worktree_job()`)
- Test: `tests/test_synlynk.py`

- [ ] **Step 1: Write the failing test — PR skipped by default**

Add to `tests/test_synlynk.py`, mirroring `test_finalize_uses_default_dispatch_branch_when_unchanged`
in the same file (same `fake_run` pattern), but asserting `gh pr create` is never called:

```python
def test_finalize_skips_pr_creation_for_scope_declared_job_without_requires_gh_write(tmp_path, monkeypatch):
    import subprocess
    import synlynk as sl
    import synlynk.jobs as jobs_mod

    worktree_path = tmp_path / "worktrees" / "job-scope-nopr"
    worktree_path.mkdir(parents=True)
    branch = "dispatch/codex/job-scope-nopr"
    job = {
        "id": "job-scope-nopr",
        "agent": "codex",
        "task": "write only the design doc",
        "worktree_path": str(worktree_path),
        "worktree_branch": branch,
        "scope_paths": ["docs/superpowers/specs/**"],
        "requires_gh_write": False,
    }
    calls = []

    def fake_run(cmd, **kwargs):
        cmd = list(cmd)
        calls.append(cmd)
        prefix = ["git", "-C", str(worktree_path)]
        if cmd[:5] == prefix + ["branch", "--show-current"]:
            return subprocess.CompletedProcess(cmd, 0, stdout=f"{branch}\n", stderr="")
        if cmd[:6] == prefix + ["diff", "--cached", "--quiet"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        if cmd[:5] == prefix + ["rev-list", "--count"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="1\n", stderr="")
        if cmd[:4] == prefix + ["push"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="pushed\n", stderr="")
        raise AssertionError(f"unexpected command: {cmd}")

    monkeypatch.setattr(jobs_mod.subprocess, "run", fake_run)
    monkeypatch.setattr(sl, "detect_remote_owner_repo", lambda: ("test-org", "test-repo"))

    jobs_mod._finalize_completed_worktree_job(
        job,
        {"has_activity": True, "remote_has_activity": False, "dirty": False, "commits_ahead": 1},
    )

    push_cmd = next(cmd for cmd in calls if cmd[:4] == ["git", "-C", str(worktree_path), "push"])
    assert branch in push_cmd
    assert not any(cmd[:3] == ["gh", "pr", "create"] for cmd in calls)
    assert not any(cmd[:3] == ["gh", "pr", "list"] for cmd in calls)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_synlynk.py::test_finalize_skips_pr_creation_for_scope_declared_job_without_requires_gh_write -v`
Expected: FAIL with `AssertionError: unexpected command: ['gh', 'pr', 'list', ...]` (the fake_run
raises because the test doesn't stub `gh pr list`/`gh pr create`, since it expects them never to
be called — today they're called unconditionally)

- [ ] **Step 3: Add the skip guard**

In `synlynk/jobs.py`, `_finalize_completed_worktree_job()` currently ends with (lines 512-527):

```python
    if created_commit or git_state.get("remote_has_activity") or git_state.get("commits_ahead", 0):
        _push_worktree_branch_if_needed(
            worktree_path,
            worktree_branch,
            git_state,
            force_push=created_commit or git_state.get("commits_ahead", 0) > 0,
        )
        pr_number = _maybe_open_worktree_pr(job, worktree_path, worktree_branch)
        if pr_number is not None:
            conn = _pkg("_get_db")()
            conn.execute(
                "UPDATE capability_ratings SET pr_number=? WHERE story_id=?",
                (pr_number, job.get("story_id", "")),
            )
            conn.commit()
            conn.close()
```

Replace the `_maybe_open_worktree_pr` call with a guarded version:

```python
    if created_commit or git_state.get("remote_has_activity") or git_state.get("commits_ahead", 0):
        _push_worktree_branch_if_needed(
            worktree_path,
            worktree_branch,
            git_state,
            force_push=created_commit or git_state.get("commits_ahead", 0) > 0,
        )
        if job.get("scope_paths") and not job.get("requires_gh_write"):
            print(
                f"  ⚠ scope-declared job {job.get('id', '')}: skipping automatic PR creation "
                f"(pass --requires-gh-write to allow)"
            )
        else:
            pr_number = _maybe_open_worktree_pr(job, worktree_path, worktree_branch)
            if pr_number is not None:
                conn = _pkg("_get_db")()
                conn.execute(
                    "UPDATE capability_ratings SET pr_number=? WHERE story_id=?",
                    (pr_number, job.get("story_id", "")),
                )
                conn.commit()
                conn.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_synlynk.py::test_finalize_skips_pr_creation_for_scope_declared_job_without_requires_gh_write -v`
Expected: PASS

- [ ] **Step 5: Write the failing test — PR still opens when `--requires-gh-write` was passed**

Add to `tests/test_synlynk.py`:

```python
def test_finalize_still_opens_pr_for_scope_declared_job_with_requires_gh_write(tmp_path, monkeypatch):
    import subprocess
    import synlynk as sl
    import synlynk.jobs as jobs_mod

    worktree_path = tmp_path / "worktrees" / "job-scope-withpr"
    worktree_path.mkdir(parents=True)
    branch = "dispatch/codex/job-scope-withpr"
    job = {
        "id": "job-scope-withpr",
        "agent": "codex",
        "task": "write the design doc and open the PR",
        "worktree_path": str(worktree_path),
        "worktree_branch": branch,
        "scope_paths": ["docs/superpowers/specs/**"],
        "requires_gh_write": True,
    }
    calls = []

    def fake_run(cmd, **kwargs):
        cmd = list(cmd)
        calls.append(cmd)
        prefix = ["git", "-C", str(worktree_path)]
        if cmd[:5] == prefix + ["branch", "--show-current"]:
            return subprocess.CompletedProcess(cmd, 0, stdout=f"{branch}\n", stderr="")
        if cmd[:6] == prefix + ["diff", "--cached", "--quiet"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        if cmd[:5] == prefix + ["rev-list", "--count"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="1\n", stderr="")
        if cmd[:4] == prefix + ["push"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="pushed\n", stderr="")
        if cmd[:3] == ["gh", "pr", "list"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="[]\n", stderr="")
        if cmd[:3] == ["gh", "pr", "create"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="https://github.com/test/repo/pull/11\n", stderr="")
        raise AssertionError(f"unexpected command: {cmd}")

    monkeypatch.setattr(jobs_mod.subprocess, "run", fake_run)
    monkeypatch.setattr(sl, "detect_remote_owner_repo", lambda: ("test-org", "test-repo"))

    jobs_mod._finalize_completed_worktree_job(
        job,
        {"has_activity": True, "remote_has_activity": False, "dirty": False, "commits_ahead": 1},
    )

    assert any(cmd[:3] == ["gh", "pr", "create"] for cmd in calls)
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/test_synlynk.py::test_finalize_still_opens_pr_for_scope_declared_job_with_requires_gh_write -v`
Expected: PASS (exercises the `else` branch added in Step 3 — no new production code needed)

- [ ] **Step 7: Run the full jobs/synlynk test suite to check for regressions**

Run: `pytest tests/test_jobs.py tests/test_synlynk.py -v`
Expected: all pass

- [ ] **Step 8: Commit**

```bash
git add synlynk/jobs.py tests/test_synlynk.py
git commit -m "feat: skip automatic PR creation for scope-declared jobs without --requires-gh-write"
```

---

### Task 6: README documentation

**Files:**
- Modify: `README.md` (dispatch flags section — find with `grep -n "requires-gh-write" README.md`
  and add `--scope-paths` documentation immediately after it; also find the `jobs --summary`
  output-format section with `grep -n "jobs --summary" README.md`)

- [ ] **Step 1: Locate the existing dispatch flags documentation**

Run: `grep -n "\-\-requires-gh-write\|\-\-grant\|\-\-revoke" README.md`

- [ ] **Step 2: Add `--scope-paths` documentation**

Immediately after the existing `--requires-gh-write`/`--grant`/`--revoke` documentation block
found in Step 1, add a paragraph (match the surrounding Markdown style — heading level, bullet
vs. prose — exactly as used by the neighboring flags):

```markdown
- `--scope-paths <glob>` (repeatable): restrict this dispatch to only touching files matching
  the given glob (e.g. `--scope-paths 'docs/superpowers/specs/**'`). At reconciliation, if the
  job's actual changed files don't all match a declared glob, the job is marked
  `SCOPE_VIOLATION` instead of being finalized, pushed, or turned into a PR — the worktree is
  left untouched for inspection. Declaring `--scope-paths` also skips automatic PR creation for
  a compliant job unless `--requires-gh-write` is also passed; `git push` of the job's own
  branch is not affected either way. See #769.
```

- [ ] **Step 3: Locate the `jobs --summary` output documentation**

Run: `grep -n "jobs --summary\|scope_violation" README.md`

- [ ] **Step 4: Document `scope_violation_files`**

In the same section, add a note that a `SCOPE_VIOLATION` job's summary/job record includes a
`scope_violation_files` field listing the out-of-scope paths that triggered the violation.

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "docs: document --scope-paths flag and SCOPE_VIOLATION status"
```

---

### Task 7: Final full-suite regression check

**Files:** none (verification only)

- [ ] **Step 1: Run the complete test suite**

Run: `pytest tests/ -v`
Expected: all tests pass, including every test added in Tasks 1-5 and every pre-existing test
(no regressions in `dispatch_agent()`, `_inspect_worktree_git_state()`, `_finalize_completed_worktree_job()`,
or the `jobs`-table reconciliation call sites)

- [ ] **Step 2: Grep for leftover TODO/placeholder markers**

Run: `git diff main --stat` then `git diff main | grep -n "TODO\|FIXME\|XXX"`
Expected: no output (nothing left unfinished)

- [ ] **Step 3: Commit if any cleanup was needed**

Only if Step 2 found something to fix:

```bash
git add -A
git commit -m "chore: cleanup before scope-violation-enforcement PR"
```
