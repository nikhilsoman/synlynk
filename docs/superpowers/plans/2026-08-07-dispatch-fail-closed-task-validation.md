# Dispatch Fail-Closed Task Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reject empty/whitespace `--task` before any dispatch side effect, and make the effective dispatch inspectable both before (`dispatch --dry-run`) and after (`jobs --summary` extension) it happens.

**Architecture:** A single fail-closed guard at the top of `dispatch_agent()` in `synlynk/dispatch.py` protects every caller. A new pure function `_render_dispatch_preview()` computes the same task/context digest data used by `--dry-run` and by the post-completion job summary, so the two views can never drift apart. `_format_job_summary()`/`_write_job_summary()` gain two optional kwargs (`task_sha256`, `task_preview`) threaded through from the task text already available at each of the 4 call sites in `synlynk/jobs.py`.

**Tech Stack:** Python 3 stdlib only (`hashlib`, `argparse`), pytest, existing `synlynk/dispatch.py` / `synlynk/cli.py` / `synlynk/jobs.py` modules.

**Reference spec:** `docs/superpowers/specs/2026-08-07-dispatch-fail-closed-task-validation-design.md`

---

### Task 1: Fail-closed empty-task guard in `dispatch_agent()`

**Files:**
- Modify: `synlynk/dispatch.py:1573` (start of `dispatch_agent()`)
- Test: `tests/test_dispatch.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_dispatch.py` (near the other `dispatch_agent` tests, after `test_dispatch_agent_requires_gh_write_false_is_noop`):

```python
def test_dispatch_agent_rejects_empty_task(project_dir, monkeypatch):
    import synlynk as sl
    import synlynk.dispatch as dispatch_mod

    called = {"worktree": False}
    monkeypatch.setattr(
        dispatch_mod, "_create_job_worktree",
        lambda *a, **kw: called.__setitem__("worktree", True) or {"path": "/tmp/x", "base_branch": "main", "base_sha": "abc"}
    )

    with pytest.raises(ValueError, match=r"empty or whitespace-only"):
        sl.dispatch_agent("claude", "", context_mode="none")

    assert called["worktree"] is False


def test_dispatch_agent_rejects_whitespace_only_task(project_dir, monkeypatch):
    import synlynk as sl

    with pytest.raises(ValueError, match=r"empty or whitespace-only"):
        sl.dispatch_agent("claude", "   \n\t  ", context_mode="none")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_dispatch.py::test_dispatch_agent_rejects_empty_task tests/test_dispatch.py::test_dispatch_agent_rejects_whitespace_only_task -v`
Expected: Both FAIL — no `ValueError` is currently raised; execution proceeds until it hits an unrelated error or returns a job dict.

- [ ] **Step 3: Add the guard**

In `synlynk/dispatch.py`, the current opening of `dispatch_agent()` reads (line 1573-1585):

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
    baselines_map = _pkg("AGENT_CAPABILITY_BASELINES", AGENT_CAPABILITY_BASELINES)
```

Change it to:

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
    if not task or not task.strip():
        raise ValueError(
            "--task is empty or whitespace-only; refusing to dispatch (see #720)"
        )
    baselines_map = _pkg("AGENT_CAPABILITY_BASELINES", AGENT_CAPABILITY_BASELINES)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_dispatch.py::test_dispatch_agent_rejects_empty_task tests/test_dispatch.py::test_dispatch_agent_rejects_whitespace_only_task -v`
Expected: Both PASS.

- [ ] **Step 5: Run the full dispatch test file to check for regressions**

Run: `pytest tests/test_dispatch.py -v`
Expected: All pass (no prior test calls `dispatch_agent` with an empty/whitespace task).

- [ ] **Step 6: Commit**

```bash
git add synlynk/dispatch.py tests/test_dispatch.py
git commit -m "fix: reject empty/whitespace --task before any dispatch side effect (#720)"
```

---

### Task 2: `_render_dispatch_preview()` pure function

**Files:**
- Modify: `synlynk/dispatch.py` (add `import hashlib` at top; add new function near `_format_job_summary`, e.g. directly above it at line 644)
- Test: `tests/test_dispatch.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_dispatch.py`:

```python
def test_render_dispatch_preview_includes_task_digest_and_no_context_file(tmp_path, monkeypatch):
    from synlynk.dispatch import _render_dispatch_preview
    import hashlib

    monkeypatch.chdir(tmp_path)
    task = "Fix issue #720 fail-closed on empty tasks"

    preview = _render_dispatch_preview("claude", task, "task")

    expected_digest = hashlib.sha256(task.encode("utf-8")).hexdigest()
    assert preview["agent"] == "claude"
    assert preview["task"] == task
    assert preview["task_len"] == len(task)
    assert preview["task_sha256"] == expected_digest
    assert preview["context_mode"] == "task"
    assert preview["context_digest"] is None
    assert preview["context_bytes"] is None


def test_render_dispatch_preview_includes_context_digest_when_context_md_exists(tmp_path, monkeypatch):
    from synlynk.dispatch import _render_dispatch_preview
    import hashlib

    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    context_bytes = b"# Context\nactive tasks here\n"
    (tmp_path / ".synlynk" / "context.md").write_bytes(context_bytes)

    preview = _render_dispatch_preview("claude", "some task", "full")

    assert preview["context_digest"] == hashlib.sha256(context_bytes).hexdigest()
    assert preview["context_bytes"] == len(context_bytes)


def test_render_dispatch_preview_skips_context_when_mode_none(tmp_path, monkeypatch):
    from synlynk.dispatch import _render_dispatch_preview

    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / ".synlynk" / "context.md").write_bytes(b"unused")

    preview = _render_dispatch_preview("claude", "some task", "none")

    assert preview["context_digest"] is None
    assert preview["context_bytes"] is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_dispatch.py::test_render_dispatch_preview_includes_task_digest_and_no_context_file -v`
Expected: FAIL with `ImportError: cannot import name '_render_dispatch_preview'`.

- [ ] **Step 3: Add `import hashlib` to the top-level imports**

In `synlynk/dispatch.py`, current top of file (lines 1-14):

```python
"""synlynk dispatch: preflight gates, agent dispatch, exec wrapper."""

import json
import os
import re
import shutil
from dataclasses import asdict
import select
import signal
import subprocess
import sys
import threading
import time
from typing import Optional, Tuple
```

Change to:

```python
"""synlynk dispatch: preflight gates, agent dispatch, exec wrapper."""

import hashlib
import json
import os
import re
import shutil
from dataclasses import asdict
import select
import signal
import subprocess
import sys
import threading
import time
from typing import Optional, Tuple
```

- [ ] **Step 4: Implement `_render_dispatch_preview()`**

Insert directly above `_job_summary_path` (currently at line 623) in `synlynk/dispatch.py`:

```python
def _render_dispatch_preview(agent: str, task: str, context_mode: str) -> dict:
    """Computes the task/context digest data shown by `dispatch --dry-run` and
    stored in the post-completion job summary. Pure function — no side effects
    beyond reading `.synlynk/context.md` if it already exists (never generates it).
    """
    task_sha256 = hashlib.sha256(task.encode("utf-8")).hexdigest()
    context_digest = None
    context_bytes = None
    if context_mode != "none":
        context_path = os.path.join(".synlynk", "context.md")
        if os.path.exists(context_path):
            try:
                with open(context_path, "rb") as f:
                    content = f.read()
                context_digest = hashlib.sha256(content).hexdigest()
                context_bytes = len(content)
            except OSError:
                pass
    return {
        "agent": agent,
        "task": task,
        "task_len": len(task),
        "task_sha256": task_sha256,
        "context_mode": context_mode,
        "context_digest": context_digest,
        "context_bytes": context_bytes,
    }
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_dispatch.py::test_render_dispatch_preview_includes_task_digest_and_no_context_file tests/test_dispatch.py::test_render_dispatch_preview_includes_context_digest_when_context_md_exists tests/test_dispatch.py::test_render_dispatch_preview_skips_context_when_mode_none -v`
Expected: All 3 PASS.

- [ ] **Step 6: Commit**

```bash
git add synlynk/dispatch.py tests/test_dispatch.py
git commit -m "feat: add _render_dispatch_preview() pure function for dispatch inspectability (#720)"
```

---

### Task 3: `dispatch --dry-run` CLI flag

**Files:**
- Modify: `synlynk/cli.py:557` (add argparse flag after `--base`)
- Modify: `synlynk/cli.py:982-1008` (`elif args.command == "dispatch":` handler)
- Test: `tests/test_dispatch.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_dispatch.py`:

```python
def test_cli_dispatch_dry_run_prints_preview_and_creates_no_job(project_dir, monkeypatch, capsys):
    import synlynk as sl
    import synlynk.cli as cli_mod

    called = {"dispatch_agent": False}
    monkeypatch.setattr(sl, "dispatch_agent", lambda *a, **kw: called.__setitem__("dispatch_agent", True))
    monkeypatch.setattr(
        "sys.argv",
        ["synlynk", "dispatch", "claude", "--task", "Fix issue #720", "--dry-run"],
    )

    cli_mod.main()

    captured = capsys.readouterr()
    assert called["dispatch_agent"] is False
    assert "agent:" in captured.out
    assert "claude" in captured.out
    assert "task_sha256:" in captured.out
    assert "no job, worktree, or cost entry created" in captured.out


def test_cli_dispatch_dry_run_empty_task_fails_closed_before_preview(project_dir, monkeypatch, capsys):
    import synlynk as sl
    import synlynk.cli as cli_mod

    called = {"dispatch_agent": False}
    monkeypatch.setattr(sl, "dispatch_agent", lambda *a, **kw: called.__setitem__("dispatch_agent", True))
    monkeypatch.setattr(
        "sys.argv",
        ["synlynk", "dispatch", "claude", "--task", "   ", "--dry-run"],
    )

    with pytest.raises(SystemExit) as exc_info:
        cli_mod.main()

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "empty or whitespace-only" in captured.out
    assert "task_sha256:" not in captured.out
    assert called["dispatch_agent"] is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_dispatch.py::test_cli_dispatch_dry_run_prints_preview_and_creates_no_job tests/test_dispatch.py::test_cli_dispatch_dry_run_empty_task_fails_closed_before_preview -v`
Expected: Both FAIL — argparse rejects the unrecognized `--dry-run` flag with a usage error / `SystemExit(2)`.

- [ ] **Step 3: Add the `--dry-run` argparse flag**

In `synlynk/cli.py`, current block (lines 553-556):

```python
    dispatch_parser.add_argument(
        "--base", default=None,
        help="Explicit base branch/ref to anchor the job worktree to (overrides auto-stacking)"
    )
```

Change to (add the new argument immediately after):

```python
    dispatch_parser.add_argument(
        "--base", default=None,
        help="Explicit base branch/ref to anchor the job worktree to (overrides auto-stacking)"
    )
    dispatch_parser.add_argument(
        "--dry-run", action="store_true", dest="dry_run",
        help="Print what would be dispatched (task digest, context digest) without creating a job, worktree, or cost entry (see #720)"
    )
```

- [ ] **Step 4: Wire `--dry-run` into the CLI handler**

In `synlynk/cli.py`, current handler (lines 982-1008):

```python
    elif args.command == "dispatch":
        try:
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
            if isinstance(job, dict) and job.get("status") == "blocked" and not job.get("pid"):
                print(f"Error: {job.get('reason')}")
                remediation = job.get("remediation")
                if remediation:
                    print(f"  {remediation}")
                sys.exit(1)
            print(f"  {_GREEN}▶{_RESET} [{job['id']}] {args.agent} dispatched  PID {job['pid']}")
            print(f"  Log:  {_CYAN}synlynk logs --job {job['id']}{_RESET}")
            if job.get("fence"):
                from synlynk.fencing import render_task_fence

                print(render_task_fence(job["fence"]))
        except ValueError as e:
            print(f"Error: {e}")
            sys.exit(1)
```

Change to:

```python
    elif args.command == "dispatch":
        try:
            if getattr(args, "dry_run", False):
                from synlynk.dispatch import _render_dispatch_preview

                task = args.task
                if not task or not task.strip():
                    raise ValueError(
                        "--task is empty or whitespace-only; refusing to dispatch (see #720)"
                    )
                context_mode = getattr(args, "context_mode", "task")
                preview = _render_dispatch_preview(args.agent, task, context_mode)
                print()
                print(f"agent:        {preview['agent']}")
                print(f"task ({preview['task_len']} chars):")
                print(f"  {preview['task']}")
                print(f"task_sha256:  {preview['task_sha256']}")
                print(f"context_mode: {preview['context_mode']}")
                if preview["context_digest"] is not None:
                    print(f"context.md:   sha256={preview['context_digest']}  ({preview['context_bytes']:,} bytes)")
                requires_gh_write = getattr(args, "requires_gh_write", False)
                print(f"capabilities: requires_gh_write={'true' if requires_gh_write else 'false'}")
                print()
                print("(dry run — no job, worktree, or cost entry created)")
                return
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
            if isinstance(job, dict) and job.get("status") == "blocked" and not job.get("pid"):
                print(f"Error: {job.get('reason')}")
                remediation = job.get("remediation")
                if remediation:
                    print(f"  {remediation}")
                sys.exit(1)
            print(f"  {_GREEN}▶{_RESET} [{job['id']}] {args.agent} dispatched  PID {job['pid']}")
            print(f"  Log:  {_CYAN}synlynk logs --job {job['id']}{_RESET}")
            if job.get("fence"):
                from synlynk.fencing import render_task_fence

                print(render_task_fence(job["fence"]))
        except ValueError as e:
            print(f"Error: {e}")
            sys.exit(1)
```

Note: the CLI handler runs inside a function whose surrounding structure already supports a bare `return` for other subcommands elsewhere in this file (this is the standard `elif args.command == ...: ...` dispatch inside `main()`) — confirm this by checking that other branches in the same `if/elif` chain use plain `return`/fallthrough rather than always calling `sys.exit()`. If `main()` in this codebase does not tolerate a bare `return` mid-chain (e.g. it's the last statement of the function body and other branches rely on falling through to a shared tail), replace `return` with `pass` and skip the rest of the `try` block by wrapping the real-dispatch call in an `else:` clause instead. Verify by running the test in the next step — a bare `return` inside `main()`'s dispatch branch is the simplest form and is expected to work since this `elif` branch is not followed by any shared cleanup code in `main()`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_dispatch.py::test_cli_dispatch_dry_run_prints_preview_and_creates_no_job tests/test_dispatch.py::test_cli_dispatch_dry_run_empty_task_fails_closed_before_preview -v`
Expected: Both PASS. If the `return` in Step 4 causes `main()` to skip required cleanup that other tests depend on, the second test's `SystemExit` assertion or the first test's captured-output assertions will reveal it — fix per the note in Step 4.

- [ ] **Step 6: Run the full dispatch and cli test files to check for regressions**

Run: `pytest tests/test_dispatch.py tests/test_cli.py -v`
Expected: All pass (adding a new flag with `action="store_true"` defaulting to `False` must not change behavior for any existing dispatch invocation that omits `--dry-run`).

- [ ] **Step 7: Commit**

```bash
git add synlynk/cli.py tests/test_dispatch.py
git commit -m "feat: add synlynk dispatch --dry-run flag (#720)"
```

---

### Task 4: `task_sha256`/`task_preview` in job summaries

**Files:**
- Modify: `synlynk/dispatch.py:644` (`_format_job_summary`) and `synlynk/dispatch.py:726` (`_write_job_summary`)
- Modify: `synlynk/jobs.py` at all 4 `_write_job_summary(` call sites (lines ~1073, ~1188, ~1370, ~1495)
- Test: `tests/test_dispatch.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_dispatch.py`:

```python
def test_format_job_summary_includes_task_sha256_and_preview_when_present():
    summary = _format_job_summary(
        "job-abc",
        "codex",
        "story-1",
        0,
        12.5,
        100,
        200,
        0.01,
        files_touched=["a.py"],
        task_sha256="a3f9c2e1b8d4",
        task_preview="Fix issue #720 fail-closed on empty tasks",
    )

    assert "task_sha256: a3f9c2e1b8d4" in summary
    assert "task:     Fix issue #720 fail-closed on empty tasks" in summary


def test_format_job_summary_omits_task_fields_when_absent():
    summary = _format_job_summary(
        "job-abc",
        "codex",
        "story-1",
        0,
        12.5,
        100,
        200,
        0.01,
        files_touched=["a.py"],
    )

    assert "task_sha256:" not in summary
    assert "task:     " not in summary
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_dispatch.py::test_format_job_summary_includes_task_sha256_and_preview_when_present tests/test_dispatch.py::test_format_job_summary_omits_task_fields_when_absent -v`
Expected: First test FAILS with `TypeError: _format_job_summary() got an unexpected keyword argument 'task_sha256'`. Second test currently PASSES already (no-op assertion) — that's fine, it locks in the no-fields-by-default behavior going forward.

- [ ] **Step 3: Add the two kwargs to `_format_job_summary()`**

Current signature and body relevant lines (644-676) in `synlynk/dispatch.py`:

```python
def _format_job_summary(job_id: str, agent: str, story_id: Optional[str],
                        exit_code: Optional[int], duration_s: Optional[float],
                        in_tokens: int, out_tokens: int, cost_usd: float,
                        files_touched: Optional[list] = None,
                        worktree_path: Optional[str] = None,
                        worktree_branch: Optional[str] = None,
                        status_label: Optional[str] = None,
                        note: Optional[str] = None,
                        base_branch: Optional[str] = None,
                        base_sha: Optional[str] = None,
                        suite_result: Optional[dict] = None) -> str:
    """Formats the structured completion summary for a finished job."""
    files_touched = sorted(set(files_touched or []))
    story_label = story_id or "-"
    exit_code = -1 if exit_code is None else exit_code
    status_label = status_label or ("OK (exit 0)" if exit_code == 0 else f"FAILED (exit {exit_code})")
    duration_label = f"{duration_s:.1f}s" if duration_s is not None else "?s"
    worktree_line = ""
    note_line = f"note:     {note}\n" if note else ""
    base_line = ""
```

Change the signature and add two new formatted lines:

```python
def _format_job_summary(job_id: str, agent: str, story_id: Optional[str],
                        exit_code: Optional[int], duration_s: Optional[float],
                        in_tokens: int, out_tokens: int, cost_usd: float,
                        files_touched: Optional[list] = None,
                        worktree_path: Optional[str] = None,
                        worktree_branch: Optional[str] = None,
                        status_label: Optional[str] = None,
                        note: Optional[str] = None,
                        base_branch: Optional[str] = None,
                        base_sha: Optional[str] = None,
                        suite_result: Optional[dict] = None,
                        task_sha256: Optional[str] = None,
                        task_preview: Optional[str] = None) -> str:
    """Formats the structured completion summary for a finished job."""
    files_touched = sorted(set(files_touched or []))
    story_label = story_id or "-"
    exit_code = -1 if exit_code is None else exit_code
    status_label = status_label or ("OK (exit 0)" if exit_code == 0 else f"FAILED (exit {exit_code})")
    duration_label = f"{duration_s:.1f}s" if duration_s is not None else "?s"
    worktree_line = ""
    note_line = f"note:     {note}\n" if note else ""
    task_line = f"task:     {task_preview}\n" if task_preview else ""
    task_sha_line = f"task_sha256: {task_sha256}\n" if task_sha256 else ""
    base_line = ""
```

Now thread `task_line` and `task_sha_line` into both return blocks. Current tail of the function (lines 685-723):

```python
    load_config_fn = _pkg("load_config")
    config = load_config_fn() if load_config_fn else {}
    if is_fenced_command("jobs", config):
        fence = FenceData(
            command="jobs",
            kind="actual",
            in_tokens=in_tokens,
            out_tokens=out_tokens,
            cost_usd=cost_usd,
            basis="structured_output",
            hints=["Run \"synlynk watch\" for a live overview"],
            label=job_id,
        )
        return (
            f"-- job {job_id} complete ---------\n"
            f"agent:    {agent}   story: {story_label}\n"
            f"status:   {status_label}\n"
            f"{note_line}"
            f"{base_line}"
            f"{suite_line}"
            f"duration: {duration_label}\n"
            f"{render_task_fence(fence)}"
            f"{worktree_line}"
            f"{files_line}"
            f"---------------------------------\n"
        )
    return (
        f"-- job {job_id} complete ---------\n"
        f"agent:    {agent}   story: {story_label}\n"
        f"status:   {status_label}\n"
        f"{note_line}"
        f"{base_line}"
        f"{suite_line}"
        f"duration: {duration_label}\n"
        f"tokens:   in {in_tokens:,}  out {out_tokens:,}  (~${cost_usd:.2f})\n"
        f"{worktree_line}"
        f"{files_line}"
        f"---------------------------------\n"
    )
```

Change to (add `{task_line}{task_sha_line}` after `{files_line}` in both returns):

```python
    load_config_fn = _pkg("load_config")
    config = load_config_fn() if load_config_fn else {}
    if is_fenced_command("jobs", config):
        fence = FenceData(
            command="jobs",
            kind="actual",
            in_tokens=in_tokens,
            out_tokens=out_tokens,
            cost_usd=cost_usd,
            basis="structured_output",
            hints=["Run \"synlynk watch\" for a live overview"],
            label=job_id,
        )
        return (
            f"-- job {job_id} complete ---------\n"
            f"agent:    {agent}   story: {story_label}\n"
            f"status:   {status_label}\n"
            f"{note_line}"
            f"{base_line}"
            f"{suite_line}"
            f"duration: {duration_label}\n"
            f"{render_task_fence(fence)}"
            f"{worktree_line}"
            f"{files_line}"
            f"{task_line}"
            f"{task_sha_line}"
            f"---------------------------------\n"
        )
    return (
        f"-- job {job_id} complete ---------\n"
        f"agent:    {agent}   story: {story_label}\n"
        f"status:   {status_label}\n"
        f"{note_line}"
        f"{base_line}"
        f"{suite_line}"
        f"duration: {duration_label}\n"
        f"tokens:   in {in_tokens:,}  out {out_tokens:,}  (~${cost_usd:.2f})\n"
        f"{worktree_line}"
        f"{files_line}"
        f"{task_line}"
        f"{task_sha_line}"
        f"---------------------------------\n"
    )
```

- [ ] **Step 4: Add the two kwargs to `_write_job_summary()`**

Current (lines 726-745):

```python
def _write_job_summary(job_id: str, agent: str, story_id: Optional[str],
                       exit_code: Optional[int], duration_s: Optional[float],
                       in_tokens: int, out_tokens: int, cost_usd: float,
                       files_touched: Optional[list],
                       worktree_path: Optional[str] = None,
                       worktree_branch: Optional[str] = None,
                       status_label: Optional[str] = None,
                       note: Optional[str] = None,
                       base_branch: Optional[str] = None,
                       base_sha: Optional[str] = None,
                       suite_result: Optional[dict] = None) -> str:
    """Writes a structured completion summary for a job and returns the text."""
    os.makedirs(".synlynk/logs", exist_ok=True)
    summary = _format_job_summary(
        job_id, agent, story_id, exit_code, duration_s, in_tokens, out_tokens,
        cost_usd, files_touched, worktree_path=worktree_path, worktree_branch=worktree_branch,
        status_label=status_label, note=note, base_branch=base_branch, base_sha=base_sha,
        suite_result=suite_result
    )
```

Change to:

```python
def _write_job_summary(job_id: str, agent: str, story_id: Optional[str],
                       exit_code: Optional[int], duration_s: Optional[float],
                       in_tokens: int, out_tokens: int, cost_usd: float,
                       files_touched: Optional[list],
                       worktree_path: Optional[str] = None,
                       worktree_branch: Optional[str] = None,
                       status_label: Optional[str] = None,
                       note: Optional[str] = None,
                       base_branch: Optional[str] = None,
                       base_sha: Optional[str] = None,
                       suite_result: Optional[dict] = None,
                       task_sha256: Optional[str] = None,
                       task_preview: Optional[str] = None) -> str:
    """Writes a structured completion summary for a job and returns the text."""
    os.makedirs(".synlynk/logs", exist_ok=True)
    summary = _format_job_summary(
        job_id, agent, story_id, exit_code, duration_s, in_tokens, out_tokens,
        cost_usd, files_touched, worktree_path=worktree_path, worktree_branch=worktree_branch,
        status_label=status_label, note=note, base_branch=base_branch, base_sha=base_sha,
        suite_result=suite_result, task_sha256=task_sha256, task_preview=task_preview
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_dispatch.py::test_format_job_summary_includes_task_sha256_and_preview_when_present tests/test_dispatch.py::test_format_job_summary_omits_task_fields_when_absent -v`
Expected: Both PASS.

- [ ] **Step 6: Run the full dispatch test file to check for regressions**

Run: `pytest tests/test_dispatch.py -v`
Expected: All pass — the two new kwargs are optional and default to `None`/no-op, so every existing call site and test is unaffected.

- [ ] **Step 7: Commit**

```bash
git add synlynk/dispatch.py tests/test_dispatch.py
git commit -m "feat: thread task_sha256/task_preview kwargs through job summary formatting (#720)"
```

---

### Task 5: Populate `task_sha256`/`task_preview` at all 4 `jobs.py` call sites

**Files:**
- Modify: `synlynk/jobs.py` (add a small helper + update 4 call sites)
- Test: `tests/test_jobs.py`

- [ ] **Step 1: Add a shared preview-string helper**

In `synlynk/jobs.py`, near the top of the file, add (after the existing imports — check the top of the file for the current import block and add `import hashlib` if not already present, plus the helper function before its first use around line 1030):

```python
def _task_sha256_and_preview(task: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """Computes the sha256 digest and a truncated single-line preview of a job's
    task text, for embedding in the job completion summary (see #720). Returns
    (None, None) if no task text is available.
    """
    if not task:
        return None, None
    digest = hashlib.sha256(task.encode("utf-8")).hexdigest()
    collapsed = " ".join(task.split())
    preview = collapsed[:200]
    return digest, preview
```

Check whether `hashlib` and `Tuple` (from `typing`) are already imported at the top of `synlynk/jobs.py`:

Run: `grep -n "^import hashlib\|from typing import" synlynk/jobs.py`

If `hashlib` is missing, add `import hashlib` alongside the other stdlib imports at the top of the file. If `Tuple` is not imported from `typing`, either add it to the existing `from typing import ...` line, or simplify the helper's return type annotation to drop `Tuple` and just omit the type hint (functionally equivalent, avoids adding an import) — use whichever keeps the diff smaller given what's already imported.

- [ ] **Step 2: Write the failing tests**

Add to `tests/test_jobs.py` (check existing test file structure first with `grep -n "^def test_\|^import\|^from" tests/test_jobs.py | head -20` to match the existing import/fixture style before writing):

```python
def test_task_sha256_and_preview_returns_digest_and_collapsed_preview():
    from synlynk.jobs import _task_sha256_and_preview
    import hashlib

    task = "Fix issue #720\nfail-closed   on empty tasks"
    digest, preview = _task_sha256_and_preview(task)

    assert digest == hashlib.sha256(task.encode("utf-8")).hexdigest()
    assert preview == "Fix issue #720 fail-closed on empty tasks"


def test_task_sha256_and_preview_truncates_long_task_to_200_chars():
    from synlynk.jobs import _task_sha256_and_preview

    task = "x" * 500
    _digest, preview = _task_sha256_and_preview(task)

    assert len(preview) == 200


def test_task_sha256_and_preview_returns_none_for_empty_task():
    from synlynk.jobs import _task_sha256_and_preview

    digest, preview = _task_sha256_and_preview(None)

    assert digest is None
    assert preview is None
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_jobs.py::test_task_sha256_and_preview_returns_digest_and_collapsed_preview tests/test_jobs.py::test_task_sha256_and_preview_truncates_long_task_to_200_chars tests/test_jobs.py::test_task_sha256_and_preview_returns_none_for_empty_task -v`
Expected: All FAIL with `ImportError`.

- [ ] **Step 4: Implement the helper per Step 1, run tests to verify they pass**

Run: `pytest tests/test_jobs.py::test_task_sha256_and_preview_returns_digest_and_collapsed_preview tests/test_jobs.py::test_task_sha256_and_preview_truncates_long_task_to_200_chars tests/test_jobs.py::test_task_sha256_and_preview_returns_none_for_empty_task -v`
Expected: All PASS.

- [ ] **Step 5: Wire the helper into call site 1 (~line 1073)**

Current call (from `synlynk/jobs.py` lines 1073-1091 as read during planning):

```python
        summary = _pkg("_write_job_summary")(
            job.get("id", ""),
            job.get("agent", ""),
            job.get("story_id"),
            job.get("exit_code"),
            duration_s,
            in_tokens,
            out_tokens,
            cost_usd,
            _pkg("_worktree_files_touched")(job.get("worktree_path")),
            job.get("worktree_path"),
            job.get("worktree_branch"),
            base_branch=job.get("base_branch"),
            base_sha=job.get("base_sha"),
            suite_result=job.get("suite_result"),
        )
        print(summary, end="")
```

Change to:

```python
        _task_sha256, _task_preview = _task_sha256_and_preview(job.get("task"))
        summary = _pkg("_write_job_summary")(
            job.get("id", ""),
            job.get("agent", ""),
            job.get("story_id"),
            job.get("exit_code"),
            duration_s,
            in_tokens,
            out_tokens,
            cost_usd,
            _pkg("_worktree_files_touched")(job.get("worktree_path")),
            job.get("worktree_path"),
            job.get("worktree_branch"),
            base_branch=job.get("base_branch"),
            base_sha=job.get("base_sha"),
            suite_result=job.get("suite_result"),
            task_sha256=_task_sha256,
            task_preview=_task_preview,
        )
        print(summary, end="")
```

- [ ] **Step 6: Wire the helper into call site 2 (~line 1188)**

Read the exact current surrounding code first:

Run: `sed -n '1170,1210p' synlynk/jobs.py`

Find the `_pkg("_write_job_summary")(...)` call in that range (it includes `status_label=summary_status, note=summary_note` per the plan's research notes). Add `_task_sha256, _task_preview = _task_sha256_and_preview(job.get("task"))` as a new line immediately before that call, and add `task_sha256=_task_sha256, task_preview=_task_preview,` as two new keyword arguments to the call, following the exact same pattern as Step 5. Preserve every existing argument and kwarg unchanged.

- [ ] **Step 7: Wire the helper into call site 3 (~line 1370)**

Read the exact current surrounding code first:

Run: `sed -n '1350,1392p' synlynk/jobs.py`

Find the `_pkg("_write_job_summary")(...)` call in that range (it includes `ambiguous_exit`/`git_state`-derived `status_label=`/`note=` kwargs per the plan's research notes). Apply the identical change pattern as Step 5/6: compute `_task_sha256, _task_preview = _task_sha256_and_preview(job.get("task"))` immediately before the call, add `task_sha256=_task_sha256, task_preview=_task_preview,` to the call's kwargs, preserve everything else unchanged.

- [ ] **Step 8: Wire the helper into call site 4 (line 1495)**

Current call (confirmed at lines 1495-1498):

```python
                _pkg("_write_job_summary")(
                    job_id, agent, story_id, exit_code, duration_s, in_tokens,
                    out_tokens, cost_usd, [], status_label=summary_status, note=summary_note
                )
```

This call site is inside a loop/branch where the local variable is `job_id`/`agent`/`story_id` rather than a `job` dict — check the ~30 lines above line 1495 (already read during planning, this is inside a function iterating rows from a DB query rather than a `job` dict) for a variable holding the task text (likely a `task` column pulled from the same query row, or `row["task"]`/`row.get("task")`). Confirm the exact variable name:

Run: `sed -n '1440,1499p' synlynk/jobs.py`

Once confirmed, change:

```python
                _pkg("_write_job_summary")(
                    job_id, agent, story_id, exit_code, duration_s, in_tokens,
                    out_tokens, cost_usd, [], status_label=summary_status, note=summary_note
                )
```

to (substituting the actual task-text variable name found above for `<task_var>`):

```python
                _task_sha256, _task_preview = _task_sha256_and_preview(<task_var>)
                _pkg("_write_job_summary")(
                    job_id, agent, story_id, exit_code, duration_s, in_tokens,
                    out_tokens, cost_usd, [], status_label=summary_status, note=summary_note,
                    task_sha256=_task_sha256, task_preview=_task_preview,
                )
```

If no task-text variable is in scope at this call site (i.e. the row query never selected a `task` column), pass `task_sha256=None, task_preview=None` explicitly is unnecessary (they already default to `None`) — in that case, skip modifying this call site and leave a one-line comment above it noting why:

```python
                # task_sha256/task_preview omitted here: no task text in scope at
                # this call site (see #720 plan Task 5, call site 4)
                _pkg("_write_job_summary")(
                    job_id, agent, story_id, exit_code, duration_s, in_tokens,
                    out_tokens, cost_usd, [], status_label=summary_status, note=summary_note
                )
```

- [ ] **Step 9: Run the full jobs and dispatch test suites**

Run: `pytest tests/test_jobs.py tests/test_dispatch.py -v`
Expected: All pass. If any existing test asserts an exact positional-argument count or exact summary text for `_write_job_summary`/`_format_job_summary`, it must still pass since the new kwargs are optional and additive.

- [ ] **Step 10: Commit**

```bash
git add synlynk/jobs.py tests/test_jobs.py
git commit -m "feat: populate task_sha256/task_preview in job completion summaries (#720)"
```

---

### Task 6: `jobs --summary <id>` end-to-end test

**Files:**
- Test: `tests/test_jobs.py`

- [ ] **Step 1: Write an end-to-end test exercising the real `jobs --summary` path**

Check how existing tests in `tests/test_jobs.py` exercise the `--summary` flag end-to-end:

Run: `grep -n "\-\-summary\|def cmd_jobs\|_job_summary_path" tests/test_jobs.py synlynk/jobs.py synlynk/cli.py | head -30`

Using whatever fixture/pattern those existing tests use to create a completed job row with a known `task` value, add:

```python
def test_jobs_summary_includes_task_sha256_matching_local_computation(project_dir, monkeypatch, capsys):
    import hashlib
    from synlynk.dispatch import _job_summary_path

    task_text = "Fix issue #720 fail-closed on empty tasks"
    expected_digest = hashlib.sha256(task_text.encode("utf-8")).hexdigest()

    # NOTE: adapt this section to however the existing tests in this file
    # construct a completed job + reconcile it into a summary file — follow
    # the exact fixture/helper pattern already used by neighboring tests in
    # tests/test_jobs.py rather than reinventing job/DB setup here.
    job_id = "job-720test"
    # ... construct and reconcile a completed job with task=task_text ...

    with open(_job_summary_path(job_id)) as f:
        summary_text = f.read()

    assert f"task_sha256: {expected_digest}" in summary_text
    assert "task:     Fix issue #720 fail-closed on empty tasks" in summary_text
```

- [ ] **Step 2: Fill in the job-construction section using the existing test file's own fixture pattern**

Read the neighboring reconciliation tests found in Step 1's grep output in full, and replace the `# NOTE:` placeholder block with the same setup pattern (e.g. inserting a row into `daemon_jobs` with the target `task` value, then calling whichever reconciliation function those tests call — likely `_pkg("_reconcile_jobs")` or similar, per the earlier research noting `_write_job_summary` call sites live inside job-reconciliation code in `synlynk/jobs.py`). This step must not be skipped or left as the placeholder shown in Step 1 — the placeholder exists only to show intent; the committed test must contain real, executable setup code matching the surrounding file's conventions.

- [ ] **Step 3: Run the test**

Run: `pytest tests/test_jobs.py::test_jobs_summary_includes_task_sha256_matching_local_computation -v`
Expected: PASS.

- [ ] **Step 4: Run the full suite**

Run: `pytest -q`
Expected: all tests pass (matches the full-suite baseline of 1667 passed, 2 deselected established after PR #748).

- [ ] **Step 5: Commit**

```bash
git add tests/test_jobs.py
git commit -m "test: verify jobs --summary reports task_sha256 matching local computation (#720)"
```

---

### Task 7: README documentation

**Files:**
- Modify: `README.md:73-76`

- [ ] **Step 1: Add the doc note**

Current (`README.md` lines 73-76):

```markdown
5. **Dispatch a task to an agent in the background:**
   ```bash
   synlynk dispatch claude --task "refactor auth module"
   ```
```

Change to:

```markdown
5. **Dispatch a task to an agent in the background:**
   ```bash
   synlynk dispatch claude --task "refactor auth module"
   ```
   `--task` must be a non-empty string — `dispatch_agent()` fails closed on an
   empty or whitespace-only task before creating any job, worktree, or cost
   entry (see [#720](https://github.com/nikhilsoman/synlynk/issues/720)). If
   `--task` is built from a shell variable in automation, don't interpolate it
   unchecked — an unset variable silently expands to an empty string. Sanity-check
   what a dispatch would actually send with `--dry-run` first:
   ```bash
   synlynk dispatch claude --task "$TASK_VAR" --dry-run
   ```
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: document --dry-run and fail-closed --task validation (#720)"
```

---

## Self-Review Notes

**Spec coverage:**
1. Reject empty/whitespace `--task` before any side effect — Task 1. ✓
2. `dispatch --dry-run` inspectability before dispatch — Task 3. ✓
3. `jobs --summary <id>` inspectability after dispatch — Tasks 4-6. ✓
4. Document safe caller construction — Task 7. ✓
5. Digest computation rule (raw string for digest, `.strip()` only for emptiness check) — Task 1 uses `.strip()` only in the guard condition, never on `task` itself; Task 2's `_render_dispatch_preview` and Task 5's `_task_sha256_and_preview` both hash the raw, unstripped string. ✓

**Placeholder scan:** Task 6 contains an intentional two-step placeholder-then-fill pattern (Step 1 shows the assertion shape, Step 2 requires reading the neighboring test file and filling in real setup code) because the exact job/DB construction helper used by existing `tests/test_jobs.py` reconciliation tests was not read in full during planning — this is flagged explicitly as a required, non-skippable step rather than left silently vague, and the surrounding file's real code must be consulted before writing it. All other tasks contain complete, copy-pasteable code with no placeholders.

**Type/signature consistency:** `_format_job_summary()` and `_write_job_summary()` both gain the same two new trailing optional kwargs (`task_sha256: Optional[str] = None`, `task_preview: Optional[str] = None`) in Task 4, called consistently by name (not positionally) everywhere in Task 5, matching the existing codebase convention of passing `status_label=`/`note=`/`base_branch=` etc. by keyword at every call site.
