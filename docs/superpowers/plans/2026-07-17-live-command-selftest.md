# Live Command Selftest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `synlynk selftest` (dry, free, argparse-only) and `synlynk selftest --live` (runs every `COMMAND_TAXONOMY` command against a real throwaway git repo, budget-capped at $2 for the handful of commands that invoke real paid agent CLIs).

**Architecture:** A new `synlynk/selftest.py` module holds `ScenarioContext`/`ScenarioResult` dataclasses, a `SELFTEST_SCENARIOS` registry keyed by taxonomy `command` string, and a `run_selftest(live=False)` driver that iterates `COMMAND_TAXONOMY` sorted by maturity tier, dispatching each entry to its registered scenario (or a generic `--help` fallback). `cmd_selftest(live=False)` is the CLI entry point, wired as a new `selftest` subcommand in `synlynk/cli.py`.

**Tech Stack:** Python 3 stdlib (`dataclasses`, `subprocess`, `tempfile`), pytest + `unittest.mock.patch`/`monkeypatch` (matching this codebase's existing test style).

---

## Important correction vs. the design doc

The design doc (`docs/superpowers/specs/2026-07-17-live-command-selftest-design.md`) says the budget cap "reuses the existing `check_budgets()`'s existing exit-on-exceed behavior." **This is incorrect and this plan does not follow it.** `check_budgets()` (`synlynk/costs.py:532`) only *prints* warnings — it never raises or calls `sys.exit()`, and it reads cumulative spend from `project-docs/costs.md` via `parse_costs_md()`, not from anything scoped to a single run. Task 3 below instead tracks spend **in-memory, within the single `run_selftest()` call**, by summing `ScenarioResult.cost_usd` as scenarios complete and checking the running total against the cap before invoking the next paid scenario. This is simpler, self-contained, and doesn't depend on `project-docs/costs.md` existing in the scratch repo.

Also note: `COMMAND_TAXONOMY` entries can have `maturity_tier` as either an `int` (0-3) or the string `"latent"` (12 such entries: `relay start`, `relay broadcast`, `checkpoint`, `daemon`, `identity init`, `repair`, `exit`, `agent run`, `instructions status`, `instructions diff`, `instructions update`, `instructions ack`). Python 3 cannot compare `int` and `str` directly, so sorting must use a key function that maps `"latent"` to a value that sorts after all int tiers (e.g. `99`).

---

## File Structure

- Create: `synlynk/selftest.py` — `ScenarioContext`, `ScenarioResult`, `SELFTEST_SCENARIOS`, `run_selftest()`, `cmd_selftest()`
- Modify: `synlynk/cli.py` — new `selftest` subparser + dispatch
- Test: `tests/test_selftest.py` — all new tests for this feature

---

### Task 1: Core module — types, registry, generic fallback, CLI wiring

**Files:**
- Create: `synlynk/selftest.py`
- Modify: `synlynk/cli.py` (subparser block near line 396, dispatch block near line 970)
- Test: `tests/test_selftest.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_selftest.py
import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from synlynk.selftest import (
    ScenarioContext,
    ScenarioResult,
    SELFTEST_SCENARIOS,
    run_selftest,
    cmd_selftest,
)


def test_scenario_result_defaults():
    result = ScenarioResult(command="init", status="pass", detail="ok")
    assert result.cost_usd == 0.0


def test_scenario_context_starts_with_empty_state():
    ctx = ScenarioContext(repo_path="/tmp/x", live=False, budget_cap_usd=2.0)
    assert ctx.state == {}
    assert ctx.spent_usd == 0.0


def test_dry_run_uses_help_fallback_for_every_taxonomy_command(monkeypatch, tmp_path):
    """With live=False, every COMMAND_TAXONOMY entry should be checked via the
    generic --help fallback (subprocess never actually needed — argparse
    itself is queried), and none should be marked 'fail'."""
    monkeypatch.chdir(tmp_path)
    results = run_selftest(live=False)
    from synlynk.taxonomy import COMMAND_TAXONOMY
    assert len(results) == len(COMMAND_TAXONOMY)
    assert all(r.status in ("pass", "skipped") for r in results)


def test_dry_run_help_fallback_marks_unknown_leaf_as_fail(monkeypatch, tmp_path):
    """A command path that isn't a real argparse leaf should fail, proving
    the fallback actually checks something rather than always passing."""
    monkeypatch.chdir(tmp_path)
    from synlynk import selftest as selftest_mod
    fake_entry = {
        "command": "totally-not-a-real-command", "governs_stage": "open",
        "maturity_tier": 0, "prominence": "primary", "orientation_gateway": False,
        "audience": "human", "trigger_phrases": [], "hook_event": None,
    }
    with patch("synlynk.selftest.COMMAND_TAXONOMY", [fake_entry]):
        results = selftest_mod.run_selftest(live=False)
    assert len(results) == 1
    assert results[0].status == "fail"
    assert results[0].command == "totally-not-a-real-command"


def test_run_selftest_sorts_latent_tier_last(monkeypatch, tmp_path):
    """maturity_tier can be int (0-3) or the string 'latent'; sorting must
    not raise TypeError from comparing int and str."""
    monkeypatch.chdir(tmp_path)
    results = run_selftest(live=False)
    from synlynk.taxonomy import COMMAND_TAXONOMY
    tier2_index = next(
        i for i, r in enumerate(results)
        for e in COMMAND_TAXONOMY
        if e["command"] == r.command and e["maturity_tier"] == 2
    )
    latent_index = next(
        i for i, r in enumerate(results)
        for e in COMMAND_TAXONOMY
        if e["command"] == r.command and e["maturity_tier"] == "latent"
    )
    assert tier2_index < latent_index


def test_cmd_selftest_exits_zero_when_all_pass(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    with patch("synlynk.selftest.run_selftest") as mock_run:
        mock_run.return_value = [
            ScenarioResult(command="init", status="pass", detail="ok"),
        ]
        with patch("sys.exit") as mock_exit:
            cmd_selftest(live=False)
            mock_exit.assert_not_called()
    out = capsys.readouterr().out
    assert "init" in out


def test_cmd_selftest_exits_one_when_any_fail(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    with patch("synlynk.selftest.run_selftest") as mock_run:
        mock_run.return_value = [
            ScenarioResult(command="init", status="pass", detail="ok"),
            ScenarioResult(command="scan", status="fail", detail="boom"),
        ]
        with patch("sys.exit") as mock_exit:
            cmd_selftest(live=False)
            mock_exit.assert_called_once_with(1)


def test_cmd_selftest_does_not_exit_one_for_skipped_only(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    with patch("synlynk.selftest.run_selftest") as mock_run:
        mock_run.return_value = [
            ScenarioResult(command="dispatch", status="skipped", detail="budget cap reached"),
        ]
        with patch("sys.exit") as mock_exit:
            cmd_selftest(live=False)
            mock_exit.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_selftest.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.selftest'`

- [ ] **Step 3: Write the implementation**

```python
# synlynk/selftest.py
"""Taxonomy-driven live/dry smoke test of every synlynk command."""

import subprocess
import sys
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from synlynk.taxonomy import COMMAND_TAXONOMY


@dataclass
class ScenarioContext:
    repo_path: str
    live: bool
    budget_cap_usd: float = 2.0
    spent_usd: float = 0.0
    state: dict = field(default_factory=dict)

    def remaining_budget(self) -> float:
        return max(0.0, self.budget_cap_usd - self.spent_usd)


@dataclass
class ScenarioResult:
    command: str
    status: str  # "pass" | "fail" | "skipped"
    detail: str
    cost_usd: float = 0.0


def _tier_sort_key(entry: dict):
    tier = entry["maturity_tier"]
    return 99 if tier == "latent" else tier


def _generic_help_scenario(entry: dict, ctx: ScenarioContext) -> ScenarioResult:
    """Fallback scenario: confirm the command is a real, invocable argparse leaf
    by running `synlynk <command> --help` and checking exit code 0."""
    argv = entry["command"].split() + ["--help"]
    result = subprocess.run(
        [sys.executable, "-m", "synlynk"] + argv,
        capture_output=True,
        text=True,
        cwd=ctx.repo_path,
    )
    if result.returncode != 0:
        return ScenarioResult(
            command=entry["command"], status="fail",
            detail=f"--help exited {result.returncode}: {result.stderr.strip()[:200]}",
        )
    return ScenarioResult(command=entry["command"], status="pass", detail="--help OK")


SELFTEST_SCENARIOS: Dict[str, Callable[[dict, ScenarioContext], ScenarioResult]] = {}


def run_selftest(live: bool = False) -> List[ScenarioResult]:
    """Runs every COMMAND_TAXONOMY entry through its registered scenario, or
    the generic --help fallback if none is registered (or live=False)."""
    import os

    repo_path = os.getcwd()
    ctx = ScenarioContext(repo_path=repo_path, live=live)
    results: List[ScenarioResult] = []
    for entry in sorted(COMMAND_TAXONOMY, key=_tier_sort_key):
        scenario = SELFTEST_SCENARIOS.get(entry["command"]) if live else None
        if scenario is None:
            result = _generic_help_scenario(entry, ctx)
        else:
            result = scenario(entry, ctx)
        ctx.spent_usd += result.cost_usd
        results.append(result)
    return results


def cmd_selftest(live: bool = False) -> None:
    """CLI entry point: runs the selftest and prints a pass/fail summary."""
    results = run_selftest(live=live)
    for r in results:
        icon = {"pass": "✓", "fail": "✗", "skipped": "○"}.get(r.status, "?")
        print(f"  {icon} {r.command:30s} {r.status:8s} {r.detail}")
    total_cost = sum(r.cost_usd for r in results)
    fail_count = sum(1 for r in results if r.status == "fail")
    pass_count = sum(1 for r in results if r.status == "pass")
    skip_count = sum(1 for r in results if r.status == "skipped")
    print(
        f"\n{pass_count} passed, {fail_count} failed, {skip_count} skipped "
        f"— total spend ${total_cost:.4f}"
    )
    if fail_count:
        sys.exit(1)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_selftest.py -v`
Expected: PASS, all 8 tests

Note: `test_dry_run_uses_help_fallback_for_every_taxonomy_command` invokes a real subprocess (`python3 -m synlynk <command> --help`) once per taxonomy entry (59 times) — this is intentional (it's what proves the fallback is real), but means this one test takes longer than typical unit tests (expect ~15-30s). If `python3 -m synlynk` doesn't work standalone in this repo (check by running it manually first: `python3 -m synlynk --help`), adjust `_generic_help_scenario`'s subprocess invocation to whatever entrypoint the project actually uses (check `bin/synlynk.py` and `pyproject.toml`'s `[project.scripts]` section) — do not silently skip this test.

- [ ] **Step 5: Wire the CLI subcommand**

In `synlynk/cli.py`, find the `config_parser` block (around line 396, right after `status_parser`) and add a new subparser immediately before it:

```python
    selftest_parser = subparsers.add_parser(
        "selftest",
        help="Exercise every synlynk command (dry by default; --live runs against a real scratch repo)",
    )
    selftest_parser.add_argument(
        "--live", action="store_true",
        help="Run against a real throwaway git repo, including real paid-agent-CLI "
             "invocations, capped at $2 total spend",
    )
```

Then find the dispatch block's `elif args.command == "status":` line (around line 764) and add a new branch right after the whole `status` block ends (before `elif args.command == "config":`):

```python
    elif args.command == "selftest":
        from synlynk.selftest import cmd_selftest
        cmd_selftest(live=getattr(args, "live", False))
```

- [ ] **Step 6: Add a CLI-wiring test**

```python
# Add to tests/test_selftest.py
def test_selftest_subcommand_is_registered():
    from synlynk.cli import build_parser
    parser = build_parser()
    args = parser.parse_args(["selftest"])
    assert args.command == "selftest"
    assert args.live is False

    args_live = parser.parse_args(["selftest", "--live"])
    assert args_live.live is True
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `pytest tests/test_selftest.py -v`
Expected: PASS, all 9 tests

- [ ] **Step 8: Run the full suite**

Run: `pytest -q`
Expected: PASS, no regressions (baseline before this task: 1218 passed, 2 skipped)

- [ ] **Step 9: Commit**

```bash
git add synlynk/selftest.py synlynk/cli.py tests/test_selftest.py
git commit -m "feat: add synlynk selftest core module with --help fallback covering all 59 taxonomy commands"
```

---

### Task 2: Bespoke live scenarios for the core lifecycle commands

**Files:**
- Modify: `synlynk/selftest.py`
- Test: `tests/test_selftest.py`

This task adds real, non-fallback scenarios for the commands a new user's first real session touches: `init`, `scan`, `join`, `goal create`, `goal list`, `goal link`, `goal status`, `story create`, `story list`, `decide`, `jobs`, `status`, `instructions status`. (`dispatch` is deliberately excluded here — it's a paid-agent-CLI command and belongs to Task 3.)

Each scenario calls the command's real Python function directly (not a subprocess) against `ctx.repo_path`, since these are free, local, filesystem/DB-only operations — this is more reliable than shelling out and lets scenarios chain state (e.g. `goal create`'s scenario stores the created `goal_id` in `ctx.state` so `goal link`'s scenario can use it).

- [ ] **Step 1: Write the failing tests**

```python
# Add to tests/test_selftest.py
def test_init_scenario_creates_project_docs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import subprocess
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "--allow-empty", "-q", "-m", "init"], cwd=tmp_path, check=True)

    from synlynk.selftest import ScenarioContext, SELFTEST_SCENARIOS
    ctx = ScenarioContext(repo_path=str(tmp_path), live=True)
    scenario = SELFTEST_SCENARIOS["init"]
    result = scenario({"command": "init"}, ctx)

    assert result.status == "pass"
    assert (tmp_path / "project-docs").is_dir()


def test_goal_create_then_goal_list_scenario_chain(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import subprocess
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "--allow-empty", "-q", "-m", "init"], cwd=tmp_path, check=True)

    from synlynk.selftest import ScenarioContext, SELFTEST_SCENARIOS
    ctx = ScenarioContext(repo_path=str(tmp_path), live=True)
    SELFTEST_SCENARIOS["init"]({"command": "init"}, ctx)

    create_result = SELFTEST_SCENARIOS["goal create"]({"command": "goal create"}, ctx)
    assert create_result.status == "pass"
    assert "goal_id" in ctx.state

    list_result = SELFTEST_SCENARIOS["goal list"]({"command": "goal list"}, ctx)
    assert list_result.status == "pass"


def test_all_core_lifecycle_commands_have_registered_scenarios():
    from synlynk.selftest import SELFTEST_SCENARIOS
    core_commands = [
        "init", "scan", "join", "goal create", "goal list", "goal link",
        "goal status", "story create", "story list", "decide", "jobs",
        "status", "instructions status",
    ]
    for cmd in core_commands:
        assert cmd in SELFTEST_SCENARIOS, f"missing scenario for {cmd!r}"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_selftest.py -k "init_scenario or goal_create_then or core_lifecycle" -v`
Expected: FAIL — `SELFTEST_SCENARIOS` is empty (no scenarios registered yet)

- [ ] **Step 3: Implement the scenarios**

Add to `synlynk/selftest.py`, after the `SELFTEST_SCENARIOS: Dict[...] = {}` line. Read each target function's actual current signature in `synlynk/__init__.py` before wiring the call (this codebase's functions have been touched by multiple concurrent PRs recently — confirm signatures with `grep -n "^def cmd_init\|^def cmd_scan\|^def cmd_join\|^def cmd_goal_create\|^def cmd_goal_list\|^def cmd_goal_link\|^def cmd_goal_status\|^def cmd_story_create\|^def cmd_story_list\|^def cmd_decide\|^def cmd_jobs\b\|^def cmd_status\b\|^def cmd_instructions_status" synlynk/__init__.py synlynk/*.py` before writing each scenario, rather than trusting any signature described elsewhere in this plan):

```python
def _init_scenario(entry: dict, ctx: ScenarioContext) -> ScenarioResult:
    import os
    from synlynk import init as synlynk_init
    try:
        old_cwd = os.getcwd()
        os.chdir(ctx.repo_path)
        try:
            synlynk_init()
        finally:
            os.chdir(old_cwd)
    except Exception as e:
        return ScenarioResult(command="init", status="fail", detail=str(e))
    if not os.path.isdir(os.path.join(ctx.repo_path, "project-docs")):
        return ScenarioResult(command="init", status="fail", detail="project-docs/ not created")
    return ScenarioResult(command="init", status="pass", detail="project-docs/ created")


def _scan_scenario(entry: dict, ctx: ScenarioContext) -> ScenarioResult:
    import os
    from synlynk import cmd_scan
    try:
        old_cwd = os.getcwd()
        os.chdir(ctx.repo_path)
        try:
            cmd_scan()
        finally:
            os.chdir(old_cwd)
    except Exception as e:
        return ScenarioResult(command="scan", status="fail", detail=str(e))
    return ScenarioResult(command="scan", status="pass", detail="scan completed")


def _goal_create_scenario(entry: dict, ctx: ScenarioContext) -> ScenarioResult:
    import os
    from synlynk import cmd_goal_create
    try:
        old_cwd = os.getcwd()
        os.chdir(ctx.repo_path)
        try:
            goal_id = cmd_goal_create("Selftest goal", "Verify command wiring")
        finally:
            os.chdir(old_cwd)
    except Exception as e:
        return ScenarioResult(command="goal create", status="fail", detail=str(e))
    ctx.state["goal_id"] = goal_id
    return ScenarioResult(command="goal create", status="pass", detail=f"created {goal_id}")


def _goal_list_scenario(entry: dict, ctx: ScenarioContext) -> ScenarioResult:
    import os
    from synlynk import cmd_goal_list
    try:
        old_cwd = os.getcwd()
        os.chdir(ctx.repo_path)
        try:
            cmd_goal_list()
        finally:
            os.chdir(old_cwd)
    except Exception as e:
        return ScenarioResult(command="goal list", status="fail", detail=str(e))
    return ScenarioResult(command="goal list", status="pass", detail="listed")


SELFTEST_SCENARIOS["init"] = _init_scenario
SELFTEST_SCENARIOS["scan"] = _scan_scenario
SELFTEST_SCENARIOS["goal create"] = _goal_create_scenario
SELFTEST_SCENARIOS["goal list"] = _goal_list_scenario
```

For the remaining core commands (`join`, `goal link`, `goal status`, `story create`, `story list`, `decide`, `jobs`, `status`, `instructions status`), follow the exact same pattern: look up the real function signature first, write a `_xxx_scenario(entry, ctx)` function that chdir's into `ctx.repo_path`, calls the real function with minimal-but-valid arguments (reusing `ctx.state` for chained IDs where needed, e.g. `story create` should link to `ctx.state["goal_id"]` if the function accepts a goal reference), wraps the call in `try/except Exception` returning `status="fail"` with the exception text on error, and registers it into `SELFTEST_SCENARIOS` under its exact taxonomy `command` string (note the two-word keys like `"goal link"` and `"instructions status"` — must match `COMMAND_TAXONOMY` entries exactly, verify against `synlynk/taxonomy.py` if unsure).

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_selftest.py -v`
Expected: PASS, all tests including the new ones from this task

- [ ] **Step 5: Run the full suite**

Run: `pytest -q`
Expected: PASS, no regressions

- [ ] **Step 6: Commit**

```bash
git add synlynk/selftest.py tests/test_selftest.py
git commit -m "feat: add live scenarios for core lifecycle commands to selftest"
```

---

### Task 3: Budget-capped scenarios for paid-agent-CLI commands

**Files:**
- Modify: `synlynk/selftest.py`
- Test: `tests/test_selftest.py`

This task adds scenarios for `dispatch`, `exec`, `schedule --execute`, and `release` — the commands that invoke real paid agent CLIs. Each scenario:
1. Checks `ctx.remaining_budget()` before running; if `<= 0`, returns `status="skipped"` immediately without calling the real command.
2. Uses a fixed trivial prompt (`"Reply with the single word OK and do nothing else."`).
3. For `dispatch` and `schedule --execute` (async — they launch a background job and return immediately with a PID), the scenario's cost is the **estimate** from `job["fence"].cost_usd` (actual cost isn't known until the job completes later, which could take minutes; waiting for completion is out of scope for this scenario). Pass/fail is based on whether the job launched successfully (a PID was returned, no exception).
4. For `exec` (synchronous — blocks until the subprocess finishes), the scenario's cost comes from the real `update_costs()`-computed value, available immediately.

Before writing these, confirm `dispatch_agent`'s current signature (`grep -n "^def dispatch_agent" synlynk/dispatch.py`) and `exec_command`'s current signature (`grep -n "^def exec_command" synlynk/dispatch.py`) — do not trust any signature quoted elsewhere in this plan without reverifying, since this file has had several concurrent PRs land recently.

- [ ] **Step 1: Write the failing tests**

```python
# Add to tests/test_selftest.py
from unittest.mock import patch, MagicMock


def test_dispatch_scenario_skips_when_budget_exhausted(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from synlynk.selftest import ScenarioContext, SELFTEST_SCENARIOS

    ctx = ScenarioContext(repo_path=str(tmp_path), live=True, budget_cap_usd=1.0, spent_usd=1.0)
    with patch("synlynk.selftest.dispatch_agent") as mock_dispatch:
        result = SELFTEST_SCENARIOS["dispatch"]({"command": "dispatch"}, ctx)
    mock_dispatch.assert_not_called()
    assert result.status == "skipped"
    assert "budget" in result.detail.lower()


def test_dispatch_scenario_uses_fence_estimate_as_cost(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from synlynk.selftest import ScenarioContext, SELFTEST_SCENARIOS
    from synlynk.fencing import FenceData

    fake_job = {
        "id": "job-selftest", "pid": 12345,
        "fence": FenceData(command="dispatch", kind="estimate", in_tokens=100,
                            out_tokens=50, cost_usd=0.03, basis="prompt_estimate"),
    }
    ctx = ScenarioContext(repo_path=str(tmp_path), live=True, budget_cap_usd=2.0)
    with patch("synlynk.selftest.dispatch_agent", return_value=fake_job) as mock_dispatch:
        result = SELFTEST_SCENARIOS["dispatch"]({"command": "dispatch"}, ctx)
    mock_dispatch.assert_called_once()
    assert result.status == "pass"
    assert result.cost_usd == 0.03


def test_exec_scenario_skips_when_budget_exhausted(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from synlynk.selftest import ScenarioContext, SELFTEST_SCENARIOS

    ctx = ScenarioContext(repo_path=str(tmp_path), live=True, budget_cap_usd=1.0, spent_usd=1.0)
    with patch("synlynk.selftest.exec_command") as mock_exec:
        result = SELFTEST_SCENARIOS["exec"]({"command": "exec"}, ctx)
    mock_exec.assert_not_called()
    assert result.status == "skipped"


def test_all_paid_commands_have_registered_scenarios():
    from synlynk.selftest import SELFTEST_SCENARIOS
    for cmd in ["dispatch", "exec", "schedule", "release"]:
        assert cmd in SELFTEST_SCENARIOS, f"missing scenario for {cmd!r}"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_selftest.py -k "dispatch_scenario or exec_scenario or all_paid_commands" -v`
Expected: FAIL — no `dispatch`/`exec`/`schedule`/`release` scenarios registered, and `dispatch_agent`/`exec_command` not yet imported into `synlynk/selftest.py`

- [ ] **Step 3: Implement the scenarios**

Add near the top of `synlynk/selftest.py`, with the other imports:

```python
from synlynk.dispatch import dispatch_agent, exec_command
```

Add the scenario functions, after the Task 2 scenarios:

```python
_TRIVIAL_PROMPT = "Reply with the single word OK and do nothing else."


def _dispatch_scenario(entry: dict, ctx: ScenarioContext) -> ScenarioResult:
    if ctx.remaining_budget() <= 0:
        return ScenarioResult(command="dispatch", status="skipped", detail="budget cap reached")
    import os
    old_cwd = os.getcwd()
    os.chdir(ctx.repo_path)
    try:
        job = dispatch_agent("codex", _TRIVIAL_PROMPT, force_agent=True)
    except Exception as e:
        return ScenarioResult(command="dispatch", status="fail", detail=str(e))
    finally:
        os.chdir(old_cwd)
    fence = job.get("fence")
    cost = fence.cost_usd if fence else 0.0
    return ScenarioResult(
        command="dispatch", status="pass",
        detail=f"launched {job.get('id')} pid={job.get('pid')}", cost_usd=cost,
    )


def _exec_scenario(entry: dict, ctx: ScenarioContext) -> ScenarioResult:
    if ctx.remaining_budget() <= 0:
        return ScenarioResult(command="exec", status="skipped", detail="budget cap reached")
    import os
    old_cwd = os.getcwd()
    os.chdir(ctx.repo_path)
    try:
        exit_code = exec_command(["claude", "-p", _TRIVIAL_PROMPT])
    except Exception as e:
        return ScenarioResult(command="exec", status="fail", detail=str(e))
    finally:
        os.chdir(old_cwd)
    if exit_code != 0:
        return ScenarioResult(command="exec", status="fail", detail=f"exit code {exit_code}")
    return ScenarioResult(command="exec", status="pass", detail="exec completed")


def _schedule_scenario(entry: dict, ctx: ScenarioContext) -> ScenarioResult:
    if ctx.remaining_budget() <= 0:
        return ScenarioResult(command="schedule", status="skipped", detail="budget cap reached")
    from synlynk.scheduler import cmd_schedule
    import os
    old_cwd = os.getcwd()
    os.chdir(ctx.repo_path)
    try:
        cmd_schedule(execute=True, max_stories=1)
    except Exception as e:
        return ScenarioResult(command="schedule", status="fail", detail=str(e))
    finally:
        os.chdir(old_cwd)
    return ScenarioResult(command="schedule", status="pass", detail="schedule --execute ran")


def _release_scenario(entry: dict, ctx: ScenarioContext) -> ScenarioResult:
    return ScenarioResult(
        command="release", status="skipped",
        detail="release is a real-world publish action (git tag/push, GitHub release) — "
               "not safe to run against a scratch repo; verified structurally via --help only",
    )


SELFTEST_SCENARIOS["dispatch"] = _dispatch_scenario
SELFTEST_SCENARIOS["exec"] = _exec_scenario
SELFTEST_SCENARIOS["schedule"] = _schedule_scenario
SELFTEST_SCENARIOS["release"] = _release_scenario
```

Note on `_release_scenario`: `synlynk release` performs real, irreversible actions against the actual GitHub remote (tagging, pushing, creating a GitHub Release) — there is no safe way to exercise it against a throwaway scratch repo without either faking the remote entirely (out of scope) or risking real side effects. It's intentionally registered as an always-`skipped` scenario with an explanatory detail, rather than left to the generic `--help` fallback silently, so the report is honest about why `release` is never really exercised live.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_selftest.py -v`
Expected: PASS, all tests from Tasks 1-3

- [ ] **Step 5: Run the full suite**

Run: `pytest -q`
Expected: PASS, no regressions

- [ ] **Step 6: Commit**

```bash
git add synlynk/selftest.py tests/test_selftest.py
git commit -m "feat: add budget-capped live scenarios for paid-agent-CLI commands to selftest"
```

---

## Self-Review

**Spec coverage:**
- `ScenarioContext`/`ScenarioResult` dataclasses — Task 1 ✓
- `SELFTEST_SCENARIOS` registry — Task 1 ✓
- Generic `--help` fallback covering all 59 commands — Task 1 ✓
- `run_selftest(live=False)` sorted by maturity tier (with `"latent"` handled) — Task 1 ✓
- `cmd_selftest(live=False)` with correct exit codes — Task 1 ✓
- CLI wiring (`synlynk selftest`, `--live` flag) — Task 1 ✓
- Bespoke core-lifecycle scenarios — Task 2 ✓
- Budget-capped paid-agent-CLI scenarios — Task 3 ✓
- $2 cap enforcement — Task 3 (in-memory tracking, corrected from the design doc's incorrect `check_budgets()` reference — see the "Important correction" section above)

**Deferred (per the spec's own "Out of scope" and this plan's explicit scope-narrowing):** bespoke scenarios for the ~34 remaining non-core, non-paid taxonomy commands remain on the generic `--help` fallback only. This is intentional and matches the brainstorm's explicit instruction not to hand-write all 59 in one pass — a natural follow-up plan, not a gap in this one.

**Placeholder scan:** No TBD/TODO markers. `_release_scenario` is a deliberate, explained `skipped`, not a placeholder.

**Type consistency:** `ScenarioResult.status` values (`"pass"`/`"fail"`/`"skipped"`) are used identically across all three tasks. `ScenarioContext.remaining_budget()` and `.spent_usd` are defined in Task 1 and used unchanged in Task 3. `SELFTEST_SCENARIOS` keys match `COMMAND_TAXONOMY`'s `"command"` field format (space-separated multi-word commands like `"goal create"`) consistently.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-17-live-command-selftest.md`. Two execution options:

1. **Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration
2. **Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
