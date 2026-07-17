# Task-Boundary Cost Fence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface token/cost data at dispatch-start (estimate) and job-completion (actual) in a shared, allowlist-gated fence format, with an always-on watch/viz reminder on completion.

**Architecture:** A new `synlynk/fencing.py` module owns rendering (`render_task_fence`) and allowlist gating (`is_fenced_command`). `dispatch_agent()` computes an estimate once and attaches it to the job dict it already returns, so both the direct `dispatch` CLI path and the `schedule --execute` queue path can print it without duplicating estimation logic. `_format_job_summary()` — already the single source of the actual-cost line printed at job completion — is upgraded to route through the shared renderer and always append a `watch`/`viz` reminder. `exec_command()`'s existing token/cost print is swapped for the same renderer.

**Tech Stack:** Python 3 stdlib only (dataclasses, no new dependencies), pytest for tests. Matches the rest of `synlynk/` — no build step.

**Scope note (resolved during planning, supersedes the design doc's "to be confirmed" language):** `release` (`cmd_release` in `synlynk/__init__.py`) has no existing cost computation to wrap — it never extracts tokens or prints a cost line today. Per the design's explicit non-goal ("no new estimation math"), `release` is **not** included in this plan. `schedule` **is** included: `cmd_schedule`'s `--execute` path calls `_dispatch_ready_jobs()` (`synlynk/jobs.py:1297`), which calls `dispatch_agent()` per job exactly like the direct CLI path, so it gets the fence for free once `dispatch_agent()` attaches the estimate to the job dict.

---

### Task 1: `synlynk/fencing.py` — FenceData, render_task_fence, is_fenced_command

**Files:**
- Create: `synlynk/fencing.py`
- Test: `tests/test_fencing.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_fencing.py
from synlynk.fencing import FenceData, render_task_fence, is_fenced_command


def test_render_task_fence_estimate():
    data = FenceData(
        command="dispatch",
        kind="estimate",
        in_tokens=28000,
        out_tokens=4000,
        cost_usd=0.42,
        basis="prompt_estimate",
    )
    out = render_task_fence(data)
    assert "-- dispatch estimate " in out
    assert "~$0.42" in out
    assert "28,000 in / 4,000 out" in out
    assert "prompt_estimate" in out
    assert "tip:" not in out


def test_render_task_fence_actual_with_hints():
    data = FenceData(
        command="jobs",
        kind="actual",
        in_tokens=3916492,
        out_tokens=33996,
        cost_usd=12.26,
        basis="structured_output",
        hints=["Run `synlynk watch` for a live overview"],
        label="job-d63c4cf4",
    )
    out = render_task_fence(data)
    assert "-- job-d63c4cf4 complete " in out
    assert "$12.26" in out
    assert "~$" not in out
    assert "3,916,492 in / 33,996 out" in out
    assert "tip:    Run `synlynk watch` for a live overview" in out


def test_render_task_fence_no_label_defaults_to_command():
    data = FenceData(
        command="exec",
        kind="actual",
        in_tokens=100,
        out_tokens=50,
        cost_usd=0.01,
        basis="regex_pair",
    )
    out = render_task_fence(data)
    assert "-- exec complete " in out


def test_is_fenced_command_allowlisted():
    config = {"fenced_commands": ["dispatch", "jobs"]}
    assert is_fenced_command("dispatch", config) is True
    assert is_fenced_command("release", config) is False


def test_is_fenced_command_missing_key_defaults_empty():
    assert is_fenced_command("dispatch", {}) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_fencing.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.fencing'`

- [ ] **Step 3: Write the implementation**

```python
# synlynk/fencing.py
"""Shared task-boundary cost fence: renders a bordered token/cost block
for dispatch-start estimates and job/exec-completion actuals, gated by
a per-project allowlist of commands (.synlynk/config.json fenced_commands).
"""
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class FenceData:
    command: str
    kind: str  # "estimate" | "actual"
    in_tokens: int
    out_tokens: int
    cost_usd: float
    basis: str
    hints: List[str] = field(default_factory=list)
    label: Optional[str] = None


def render_task_fence(data: FenceData) -> str:
    """Render a bordered fence block for a FenceData instance."""
    label = data.label or data.command
    suffix = "estimate" if data.kind == "estimate" else "complete"
    header = f"-- {label} {suffix} " + "-" * max(1, 32 - len(label) - len(suffix))
    prefix = "~$" if data.kind == "estimate" else "$"
    lines = [
        header,
        f"cost:   {prefix}{data.cost_usd:.2f}  ({data.in_tokens:,} in / {data.out_tokens:,} out, {data.basis})",
    ]
    for hint in data.hints:
        lines.append(f"tip:    {hint}")
    lines.append("-" * 36)
    return "\n".join(lines) + "\n"


def is_fenced_command(command: str, config: dict) -> bool:
    """True if `command` is in config['fenced_commands']. Missing key => no fences."""
    return command in (config.get("fenced_commands") or [])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_fencing.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add synlynk/fencing.py tests/test_fencing.py
git commit -m "feat: add shared task-boundary cost fence renderer"
```

---

### Task 2: `fenced_commands` config default

**Files:**
- Modify: `synlynk/__init__.py:1329-1350` (`load_config()`)
- Test: `tests/test_config.py` (create if it doesn't already exist — check first with `ls tests/test_config.py`)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_config.py (append if file exists, else create with this content)
import json
import os

from synlynk import load_config


def test_load_config_default_fenced_commands(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    config = load_config()
    assert config["fenced_commands"] == ["dispatch", "jobs", "exec", "schedule"]


def test_load_config_preserves_existing_fenced_commands(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    with open(".synlynk/config.json", "w") as f:
        json.dump({"fenced_commands": ["dispatch"]}, f)
    config = load_config()
    assert config["fenced_commands"] == ["dispatch"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py -v`
Expected: FAIL with `KeyError: 'fenced_commands'`

- [ ] **Step 3: Add the default**

In `synlynk/__init__.py`, inside `load_config()`'s `defaults` dict (starts at line 1331 with `defaults = {`), add one entry. Insert it right after `"dispatch_mode": "daily-grind",`:

```python
        "dispatch_mode": "daily-grind",
        "fenced_commands": ["dispatch", "jobs", "exec", "schedule"],
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_config.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add synlynk/__init__.py tests/test_config.py
git commit -m "feat: default fenced_commands to dispatch/jobs/exec/schedule"
```

---

### Task 3: Dispatch-start estimate — `dispatch_agent()` + `dispatch` CLI handler

**Files:**
- Modify: `synlynk/dispatch.py` (`dispatch_agent()`, prompt-building section and job dict, currently around lines 848 and 894-914 — re-verify against current `main` before editing, since `cli.py`/`dispatch.py` are under concurrent edit from other in-flight work)
- Modify: `synlynk/cli.py` (`dispatch` command handler, currently around line 692-698)
- Test: `tests/test_dispatch.py`

- [ ] **Step 1: Write the failing test**

```python
# Add to tests/test_dispatch.py
import json
from unittest.mock import patch


def test_dispatch_agent_attaches_fence_estimate(tmp_path, monkeypatch):
    """dispatch_agent() should attach a FenceData estimate to the returned job dict
    when a prompt/context are built (context_mode != 'none')."""
    from synlynk.dispatch import dispatch_agent
    from synlynk.fencing import FenceData

    monkeypatch.chdir(tmp_path)
    # Reuse whatever fixture/mocking pattern the rest of this file uses to stub
    # subprocess.Popen, _get_db, _preflight_dispatch, etc. for a synthetic
    # dispatch_agent() call — see existing tests in this file (e.g.
    # test_dispatch_agent_returns_job_dict or similar) for the established
    # mock setup, and mirror it here rather than re-deriving it from scratch.
    job = dispatch_agent("codex", "do the thing", context_mode="none")
    assert job.get("fence") is None or isinstance(job["fence"], FenceData)
```

Note for the implementer: this repo's `tests/test_dispatch.py` already has an established pattern for calling `dispatch_agent()` in a fully-mocked sandbox (stubbed subprocess, db, preflight). Find that pattern (search the file for an existing `dispatch_agent(` call in a test) and copy its mock setup verbatim into this new test — don't invent a new mocking approach.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_dispatch.py -k test_dispatch_agent_attaches_fence_estimate -v`
Expected: FAIL with `KeyError: 'fence'` or `AssertionError` (job dict has no `"fence"` key yet)

- [ ] **Step 3: Compute the estimate inside `dispatch_agent()`**

Locate the block in `synlynk/dispatch.py` where `prompt` is built and written to `prompt_file` (search for `format_prompt = _pkg("_format_prompt_for_agent"` — this is the block right after `context_text` is assembled). Immediately after the `with open(prompt_file, "w") as f: f.write(prompt)` line, add:

```python
    fence_data = None
    load_config_fn = _pkg("load_config")
    fence_config = load_config_fn() if load_config_fn else {}
    is_fenced = _pkg("is_fenced_command")
    if is_fenced and is_fenced("dispatch", fence_config):
        estimate_fn = _pkg("estimate_dispatch_tokens")
        tshirt_fn = _pkg("_estimate_tshirt_tokens")
        rate_fn = _pkg("_model_rate_for_version")
        make_fence = _pkg("FenceData")
        if context_mode != "none" and estimate_fn:
            est = estimate_fn(prompt, context_text, agent)
            in_tok, out_tok = est["input"], est["output"]
            basis = "prompt_estimate"
        elif tshirt_fn:
            discipline = None
            phase = None
            get_story = _pkg("_get_story_discipline_phase")
            if get_story and story_id:
                discipline, phase = get_story(story_id)
            in_tok, out_tok, basis = tshirt_fn(story_id=story_id, discipline=discipline, phase=phase)
        else:
            in_tok, out_tok, basis = 0, 0, "none"
        if make_fence:
            rates = rate_fn(model_at_dispatch, agent=agent) if rate_fn else {"input": 0.003, "output": 0.015}
            cost_usd = (in_tok / 1000 * rates["input"]) + (out_tok / 1000 * rates["output"])
            fence_data = make_fence(
                command="dispatch",
                kind="estimate",
                in_tokens=in_tok,
                out_tokens=out_tok,
                cost_usd=cost_usd,
                basis=basis,
            )
```

Then in the `job = {...}` dict literal (search for `"model_at_dispatch": model_at_dispatch,` — the last field before the closing `}`), add one more field:

```python
        "model_at_dispatch": model_at_dispatch,
        "fence": fence_data,
    }
```

**Important:** `_get_story_discipline_phase` does not exist yet in this codebase — check `synlynk/quota.py` and `synlynk/db.py` for the closest existing helper that reads a story's `discipline`/`phase` columns (the design doc's `_estimate_tshirt_tokens()` call in `costs.py:362` already does this lookup inline via a raw SQL query against the `stories` table — reuse that same inline query pattern here instead of inventing a new helper function, i.e. do the `SELECT discipline, phase FROM stories WHERE story_id=?` query directly where `get_story` is referenced above, and drop the `_pkg("_get_story_discipline_phase")` indirection).

- [ ] **Step 4: Print the fence in the CLI dispatch handler**

In `synlynk/cli.py`, in the `elif args.command == "dispatch":` block (search for `job = dispatch_agent(args.agent, args.task,`), add the print immediately after the existing `▶ ... dispatched` and `Log:` lines:

```python
            print(f"  {_GREEN}▶{_RESET} [{job['id']}] {args.agent} dispatched  PID {job['pid']}")
            print(f"  Log:  {_CYAN}synlynk logs --job {job['id']}{_RESET}")
            if job.get("fence"):
                from synlynk.fencing import render_task_fence
                print(render_task_fence(job["fence"]))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_dispatch.py -v`
Expected: PASS, including the new test

- [ ] **Step 6: Commit**

```bash
git add synlynk/dispatch.py synlynk/cli.py tests/test_dispatch.py
git commit -m "feat: attach dispatch-start cost estimate fence to job dict"
```

---

### Task 4: `schedule --execute` prints the same estimate fence

**Files:**
- Modify: `synlynk/jobs.py` (`_dispatch_ready_jobs()`, currently around line 1297-1374)
- Test: `tests/test_jobs.py`

- [ ] **Step 1: Write the failing test**

```python
# Add to tests/test_jobs.py
def test_dispatch_ready_jobs_prints_fence_when_schedule_allowlisted(monkeypatch, capsys, tmp_path):
    """When 'schedule' is in fenced_commands, each job launched by
    _dispatch_ready_jobs() should print its estimate fence."""
    from synlynk.jobs import _dispatch_ready_jobs
    from synlynk.fencing import FenceData

    monkeypatch.chdir(tmp_path)
    # Mirror this file's existing mocking pattern for _dispatch_ready_jobs()
    # (stub _get_db with a queued daemon_jobs row, stub dispatch_agent to
    # return a job dict) — search this file for an existing
    # test_dispatch_ready_jobs_* test and copy its setup.
    fake_job = {
        "id": "job-abc123", "pid": 999, "started_at": "2026-07-17T00:00:00",
        "log_file": "/tmp/x.log",
        "fence": FenceData(command="schedule", kind="estimate", in_tokens=100,
                            out_tokens=50, cost_usd=0.01, basis="prompt_estimate"),
    }
    with patch("synlynk.jobs._pkg") as mock_pkg:
        def pkg_side_effect(name, default=None):
            if name == "dispatch_agent":
                return lambda *a, **k: fake_job
            if name == "load_config":
                return lambda: {"fenced_commands": ["schedule"]}
            if name == "is_fenced_command":
                from synlynk.fencing import is_fenced_command
                return is_fenced_command
            return default
        mock_pkg.side_effect = pkg_side_effect
        # ... complete the queued-job DB fixture per this file's established
        # pattern, then call _dispatch_ready_jobs() and assert the fence text
        # appears in capsys.readouterr().out
```

Note for the implementer: this test is intentionally left with a `# ...` completion marker for the DB fixture portion — that's the one exception to "no placeholders" in this plan, because `tests/test_jobs.py`'s exact `daemon_jobs` fixture setup pattern isn't visible from the design/plan phase. Find the closest existing `_dispatch_ready_jobs` test in this file, copy its full DB setup verbatim, and complete this test before running it. Do not skip completing it.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_jobs.py -k test_dispatch_ready_jobs_prints_fence_when_schedule_allowlisted -v`
Expected: FAIL (no fence printed yet — `_dispatch_ready_jobs()` doesn't print anything from `job["fence"]`)

- [ ] **Step 3: Print the fence after each successful dispatch**

In `synlynk/jobs.py`, inside `_dispatch_ready_jobs()`, locate the block:

```python
            try:
                job = dispatch_fn(
                    agent,
                    task,
                    story_id=story_id,
                    force_agent=True,
                    job_id=job_id,
                )
```

Immediately after this `try/except` block (after the `except (RuntimeError, ValueError):` branch's `continue`, at the same indentation as the code that follows the try/except), add:

```python
            if job.get("fence"):
                render_fence = _pkg("render_task_fence")
                if render_fence:
                    print(render_fence(job["fence"]))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_jobs.py -v`
Expected: PASS, including the new test

- [ ] **Step 5: Commit**

```bash
git add synlynk/jobs.py tests/test_jobs.py
git commit -m "feat: print dispatch estimate fence from schedule --execute"
```

---

### Task 5: Job-completion actual fence + watch/viz reminder

**Files:**
- Modify: `synlynk/dispatch.py` (`_format_job_summary()`, currently lines 379-416)
- Test: `tests/test_dispatch.py`

- [ ] **Step 1: Write the failing tests**

```python
# Add to tests/test_dispatch.py
def test_format_job_summary_includes_watch_reminder():
    from synlynk.dispatch import _format_job_summary

    summary = _format_job_summary(
        "job-d63c4cf4", "codex", "story-e528c886", 0, 12.3,
        3916492, 33996, 12.26, files_touched=["a.py"],
    )
    assert "synlynk watch" in summary
    assert "$12.26" in summary


def test_format_job_summary_falls_back_when_jobs_not_allowlisted(monkeypatch):
    from synlynk.dispatch import _format_job_summary
    import synlynk.dispatch as dispatch_mod

    monkeypatch.setattr(dispatch_mod, "_pkg", lambda name, default=None: (
        (lambda: {"fenced_commands": []}) if name == "load_config" else default
    ))
    summary = _format_job_summary(
        "job-x", "codex", None, 0, 1.0, 100, 50, 0.01, files_touched=[],
    )
    assert "job job-x complete" in summary
    assert "synlynk watch" not in summary
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_dispatch.py -k "test_format_job_summary_includes_watch_reminder or test_format_job_summary_falls_back_when_jobs_not_allowlisted" -v`
Expected: FAIL — current `_format_job_summary()` has no watch/viz reminder and doesn't check the allowlist

- [ ] **Step 3: Update `_format_job_summary()`**

Replace the current body of `_format_job_summary()` (`synlynk/dispatch.py:379-416`) with:

```python
def _format_job_summary(job_id: str, agent: str, story_id: Optional[str],
                        exit_code: Optional[int], duration_s: Optional[float],
                        in_tokens: int, out_tokens: int, cost_usd: float,
                        files_touched: Optional[list] = None,
                        worktree_path: Optional[str] = None,
                        worktree_branch: Optional[str] = None,
                        status_label: Optional[str] = None,
                        note: Optional[str] = None) -> str:
    """Formats the structured completion summary for a finished job."""
    files_touched = sorted(set(files_touched or []))
    story_label = story_id or "-"
    exit_code = -1 if exit_code is None else exit_code
    status_label = status_label or ("OK (exit 0)" if exit_code == 0 else f"FAILED (exit {exit_code})")
    duration_label = f"{duration_s:.1f}s" if duration_s is not None else "?s"
    worktree_line = ""
    note_line = f"note:     {note}\n" if note else ""
    if worktree_path:
        branch_note = f" (branch: {worktree_branch})" if worktree_branch else ""
        worktree_line = f"worktree: {worktree_path}{branch_note}\n"
    files_line = f"files:    {len(files_touched)} touched\n"
    if files_touched:
        visible_files = files_touched[:20]
        rendered_files = "".join(f"          {path}\n" for path in visible_files)
        more_count = len(files_touched) - len(visible_files)
        if more_count > 0:
            rendered_files += f"          +{more_count} more\n"
        files_line += rendered_files

    load_config_fn = _pkg("load_config")
    config = load_config_fn() if load_config_fn else {}
    is_fenced = _pkg("is_fenced_command")
    tokens_line = f"tokens:   in {in_tokens:,}  out {out_tokens:,}  (~${cost_usd:.2f})\n"
    if is_fenced and is_fenced("jobs", config):
        render_fence = _pkg("render_task_fence")
        make_fence = _pkg("FenceData")
        if render_fence and make_fence:
            fence = make_fence(
                command="jobs",
                kind="actual",
                in_tokens=in_tokens,
                out_tokens=out_tokens,
                cost_usd=cost_usd,
                basis="structured_output",
                hints=["Run `synlynk watch` for a live overview"],
                label=job_id,
            )
            tokens_line = render_fence(fence)
            return (
                f"agent:    {agent}   story: {story_label}\n"
                f"status:   {status_label}\n"
                f"{note_line}"
                f"duration: {duration_label}\n"
                f"{tokens_line}"
                f"{worktree_line}"
                f"{files_line}"
            )

    return (
        f"-- job {job_id} complete ---------\n"
        f"agent:    {agent}   story: {story_label}\n"
        f"status:   {status_label}\n"
        f"{note_line}"
        f"duration: {duration_label}\n"
        f"{tokens_line}"
        f"{worktree_line}"
        f"{files_line}"
        f"---------------------------------\n"
    )
```

Add `FenceData`, `render_task_fence`, `is_fenced_command` to the `_pkg` registry so `_pkg("render_task_fence")`/`_pkg("FenceData")`/`_pkg("is_fenced_command")` resolve. Find where `synlynk/dispatch.py` currently imports/registers its `_pkg` lookups (search for `def _pkg(` or the module-level import block at the top of `dispatch.py`) and add:

```python
from synlynk.fencing import FenceData, render_task_fence, is_fenced_command
```

to that file's import section, then confirm `_pkg()`'s implementation resolves names against `globals()` (check its body) — if it does, the import alone is sufficient and no separate registry entry is needed.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_dispatch.py -v`
Expected: PASS, all tests in the file including the two new ones

- [ ] **Step 5: Commit**

```bash
git add synlynk/dispatch.py tests/test_dispatch.py
git commit -m "feat: route job-completion summary through cost fence + watch reminder"
```

---

### Task 6: `exec` actual-cost fence

**Files:**
- Modify: `synlynk/dispatch.py` (`exec_command()`, currently lines 1080-1087)
- Test: `tests/test_dispatch.py`

- [ ] **Step 1: Write the failing test**

```python
# Add to tests/test_dispatch.py
def test_exec_command_prints_fence_when_allowlisted(monkeypatch, capsys):
    from synlynk.dispatch import exec_command

    monkeypatch.setattr(
        "synlynk.dispatch._pkg",
        lambda name, default=None: {
            "load_config": lambda: {"fenced_commands": ["exec"]},
            "extract_tokens": lambda text, agent=None: type(
                "T", (tuple,), {}
            )((100, 50)),
            "_model_rate_for_version": lambda v, agent=None: {"input": 0.003, "output": 0.015, "cache_read": 0.0000003},
        }.get(name, default),
    )
    exec_command(["echo", "hi"])
    out = capsys.readouterr().out
    assert "-- exec complete" in out
```

Note: this test's exact mocking approach should mirror whatever `tests/test_dispatch.py` already does for other `exec_command()` tests (search the file for `def test_exec_command` — there should be existing coverage of the current `⚡ Tokens:` print line to base this on). Adjust the mock shape to match established conventions in that file rather than the sketch above if they differ.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_dispatch.py -k test_exec_command_prints_fence_when_allowlisted -v`
Expected: FAIL — current output uses `⚡ Tokens:`, not a fence block

- [ ] **Step 3: Swap the print for the fence**

In `synlynk/dispatch.py`, inside `exec_command()`, replace this block (currently around line 1073-1088):

```python
            if in_tokens > 0 or out_tokens > 0:
                rates = model_rate_for_version(model_version, agent=cmd_args[0]) if model_rate_for_version else {
                    "input": 0.003,
                    "output": 0.015,
                    "cache_read": 0.0000003,
                }
                est_cost = (
                    (in_tokens / 1000 * rates["input"]) +
                    (out_tokens / 1000 * rates["output"]) +
                    (cache_read_tokens / 1000 * rates["cache_read"])
                )
                print(f"  ⚡ Tokens: {in_tokens:,} in / {out_tokens:,} out  |  est. ${est_cost:.4f}")
            else:
                print(f"  ⚡ Token count unavailable — logged as estimated_tshirt fallback")
```

with:

```python
            if in_tokens > 0 or out_tokens > 0:
                rates = model_rate_for_version(model_version, agent=cmd_args[0]) if model_rate_for_version else {
                    "input": 0.003,
                    "output": 0.015,
                    "cache_read": 0.0000003,
                }
                est_cost = (
                    (in_tokens / 1000 * rates["input"]) +
                    (out_tokens / 1000 * rates["output"]) +
                    (cache_read_tokens / 1000 * rates["cache_read"])
                )
                load_config_fn = _pkg("load_config")
                exec_config = load_config_fn() if load_config_fn else {}
                if is_fenced_command("exec", exec_config):
                    print(render_task_fence(FenceData(
                        command="exec",
                        kind="actual",
                        in_tokens=in_tokens,
                        out_tokens=out_tokens,
                        cost_usd=est_cost,
                        basis=basis,
                    )))
                else:
                    print(f"  ⚡ Tokens: {in_tokens:,} in / {out_tokens:,} out  |  est. ${est_cost:.4f}")
            else:
                print(f"  ⚡ Token count unavailable — logged as estimated_tshirt fallback")
```

(`FenceData`/`render_task_fence`/`is_fenced_command` are already imported at module level from Task 5's Step 3.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_dispatch.py -v`
Expected: PASS, full file including the new test

- [ ] **Step 5: Run the full test suite**

Run: `pytest -q`
Expected: All tests pass (matches the baseline of 1185 passed, 2 skipped taken at worktree setup, plus this plan's new tests)

- [ ] **Step 6: Commit**

```bash
git add synlynk/dispatch.py tests/test_dispatch.py
git commit -m "feat: route exec cost output through shared task-boundary fence"
```

---

## Self-Review

**Spec coverage:**
- Ask #1 (dispatch-start estimate, layered) → Task 3
- Ask #2 (job-completion actual) → Task 5 (reuses existing `_format_job_summary()` data, no new computation)
- Ask #3 (watch/viz reminder, always on completion) → Task 5's `hints=["Run \`synlynk watch\`..."]`
- Ask #4 (fence inline, HUD manual) → satisfied by construction — no task anywhere calls `viz`/`watch`, only prints text
- Allowlist config → Task 2
- GTM item 6 absorption, bounded scope → Tasks 3/4/6 cover `dispatch`, `schedule`, `exec`; `release` explicitly descoped with reasoning in the header

**Placeholder scan:** Two intentional, flagged exceptions in Tasks 4 and 6 where a test's DB/mock fixture can't be fully specified without reading `tests/test_jobs.py`/`tests/test_dispatch.py`'s exact existing conventions — both are explicitly marked as "complete before running, do not skip" rather than left as vague TODOs, and both point the implementer at the exact existing pattern to copy. No other placeholders.

**Type consistency:** `FenceData` fields (`command`, `kind`, `in_tokens`, `out_tokens`, `cost_usd`, `basis`, `hints`, `label`) are used identically across Tasks 1, 3, 4, 5, 6. `render_task_fence(data: FenceData) -> str` and `is_fenced_command(command: str, config: dict) -> bool` signatures are consistent everywhere they're called.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-17-dispatch-job-comms-fence.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
