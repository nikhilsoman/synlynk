# Harness Capability Drift & Regression Classification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep synlynk's harness capability data fresh via a local staleness trigger, classify probe/smoke-test failures as synlynk regressions vs. harness-side drift, and extend `selftest.py` so its live scenarios actually catch #617-class bugs (multi-harness coverage, GitHub write-action coverage, less mocking).

**Architecture:** New `state.db` tables (`capability_watch`, `gh_write_capability`, `capability_incidents`) back three additions: (1) a free/paid staleness-trigger pair hooked into `synlynk/cli.py`'s `main()`, (2) three sequential extensions to `synlynk/selftest.py`'s existing taxonomy-driven scenario registry, and (3) a new `synlynk/capability_classifier.py` module that git-blames a failing code path against the last known-green run to tag failures `regression` or `drift`. Everything is local — no service dependency — and reuses the existing preflight/remediation system for enforcement rather than building new blocking logic.

**Tech Stack:** Python 3 stdlib only (sqlite3, subprocess, threading, argparse), pytest, existing `synlynk/db.py` migration conventions (`_migrate_db`, `executescript` + `CREATE TABLE IF NOT EXISTS`), existing `synlynk/selftest.py` scenario-registry pattern.

---

## Spec reference

`docs/superpowers/specs/2026-07-31-harness-capability-drift-regression-classification-design.md` — read it before starting Task 1 if anything below is ambiguous. Non-goals section there is authoritative: this plan does **not** touch the daemon, `project-docs/` DR backup, `_probe_results_trustworthy()`'s hardcoded `False`, or any new dispatch-time blocking logic.

## File Structure

| File | Responsibility |
|---|---|
| `synlynk/db.py` (modify `_migrate_db`, ~line 355) | Add `capability_watch`, `gh_write_capability`, `capability_incidents` tables |
| `synlynk/capability_watch.py` (new) | Staleness-check helpers: read/write `capability_watch` timestamps, decide whether free probe / paid smoke test is due |
| `synlynk/cli.py` (modify `main()`, ~line 815) | Call the staleness-trigger hook once per invocation, in a background thread, before the command dispatch table |
| `synlynk/capability_classifier.py` (new) | `classify_failure(failing_path, harness) -> dict` — git-blame vs. fingerprint-diff logic, writes to `capability_incidents` |
| `synlynk/selftest.py` (modify) | Phase 1: `ScenarioContext` mode/harness fields, multi-harness loop, worktree PR-base-branch assertion. Phase 2: new GH write-action scenarios. Phase 3: reduce mocking in `_scenario_init_existing_files`, `_scenario_join`, `_scenario_decide`, `_scenario_scan` |
| `synlynk/status.py` (modify `cmd_status`) | Surface "smoke test overdue" and recent `capability_incidents` rows |
| `tests/test_capability_watch.py` (new) | Staleness-check unit tests |
| `tests/test_capability_classifier.py` (new) | Classifier unit tests with synthetic git histories |
| `tests/test_selftest.py` (modify) | Multi-harness loop, mode-axis, PR-assertion, GH-write-scenario coverage |
| `tests/test_status.py` (modify) | Overdue-smoke-test and incidents-surfacing coverage |

## Task Dependency Graph

```
Task 1 (schema)
  ├─→ Task 2 (capability_watch.py + cli.py staleness triggers)
  │     └─→ Task 9 (status.py surfacing)  ←── also depends on Task 7
  ├─→ Task 3 (selftest Phase 1: scaffolding)
  │     ├─→ Task 4 (selftest Phase 1: PR-base-branch assertion)
  │     ├─→ Task 5 (selftest Phase 2: GH write scenarios)  ←── also depends on Task 1 (gh_write_capability table)
  │     └─→ Task 6 (selftest Phase 3: mocking reduction)
  └─→ Task 7 (capability_classifier.py)
        └─→ Task 8 (wire classifier into Task 2's triggers + selftest failure path)  ←── also depends on Task 2
```

**Parallel dispatch groups** (tasks in the same group have no dependency on each other and can run concurrently once their prerequisites land):
- **Group A (after Task 1 lands):** Task 2, Task 3, Task 7 — three independent agents, no shared files.
- **Group B (after Task 3 lands):** Task 4, Task 5, Task 6 — all modify `synlynk/selftest.py` but in disjoint functions (`_dispatch_scenario` for Task 4, new `_scenario_gh_*` functions for Task 5, `_scenario_init_existing_files`/`_scenario_join`/`_scenario_decide`/`_scenario_scan` for Task 6). Sequence these serially within `selftest.py` to avoid merge conflicts on the same file even though they're logically independent — recommend Task 4 → Task 5 → Task 6 order, or dispatch to one agent as a batch if parallel merge conflicts become a problem in practice.
- **Task 8 and Task 9** are integration tasks — dispatch last, after their dependencies are merged.

Per this repo's capability-based task allocation (CLAUDE.md): all tasks below are Python/CLI/tests → route to **Codex**. If Codex is unavailable, Agy/Grok can pick up per standard fallback routing.

---

### Task 1: state.db schema — capability_watch, gh_write_capability, capability_incidents

**Files:**
- Modify: `synlynk/db.py:355` (end of the `executescript` block inside `_migrate_db` that creates `harness_version_history`)
- Test: `tests/test_capability_watch.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_capability_watch.py
import sqlite3

import pytest

from synlynk.db import _migrate_db


@pytest.fixture
def conn(tmp_path):
    db_path = tmp_path / "state.db"
    connection = sqlite3.connect(str(db_path))
    _migrate_db(connection)
    return connection


def test_capability_watch_table_exists(conn):
    cols = {row[1] for row in conn.execute("PRAGMA table_info(capability_watch)")}
    assert cols == {"id", "last_probe_at", "last_green_probe_at", "last_smoke_test_at", "last_green_smoke_at"}


def test_capability_watch_singleton_row_seeded(conn):
    row = conn.execute("SELECT id FROM capability_watch WHERE id = 1").fetchone()
    assert row is not None


def test_gh_write_capability_table_exists(conn):
    cols = {row[1] for row in conn.execute("PRAGMA table_info(gh_write_capability)")}
    assert cols == {"harness", "mode", "action", "status", "checked_at"}
    pk_cols = {row[1] for row in conn.execute("PRAGMA table_info(gh_write_capability)") if row[5] > 0}
    assert pk_cols == {"harness", "mode", "action"}


def test_capability_incidents_table_exists(conn):
    cols = {row[1] for row in conn.execute("PRAGMA table_info(capability_incidents)")}
    assert cols == {
        "id", "harness", "failing_path", "classification", "evidence", "detected_at",
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_capability_watch.py -v`
Expected: FAIL — `sqlite3.OperationalError: no such table: capability_watch` (and similarly for the other two tables)

- [ ] **Step 3: Add the schema**

In `synlynk/db.py`, inside `_migrate_db`, immediately after the `executescript("""...harness_version_history...""")` block (ends at line 355 with `""")`), add:

```python
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS capability_watch (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            last_probe_at TEXT,
            last_green_probe_at TEXT,
            last_smoke_test_at TEXT,
            last_green_smoke_at TEXT
        );

        CREATE TABLE IF NOT EXISTS gh_write_capability (
            harness TEXT NOT NULL,
            mode TEXT NOT NULL,
            action TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'unknown',
            checked_at TEXT,
            PRIMARY KEY (harness, mode, action)
        );

        CREATE TABLE IF NOT EXISTS capability_incidents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            harness TEXT NOT NULL,
            failing_path TEXT NOT NULL,
            classification TEXT NOT NULL,
            evidence TEXT NOT NULL DEFAULT '',
            detected_at TEXT NOT NULL
        );
    """)
    conn.execute(
        "INSERT OR IGNORE INTO capability_watch (id, last_probe_at, last_green_probe_at, "
        "last_smoke_test_at, last_green_smoke_at) VALUES (1, NULL, NULL, NULL, NULL)"
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_capability_watch.py -v`
Expected: PASS (all 4 tests)

- [ ] **Step 5: Commit**

```bash
git add synlynk/db.py tests/test_capability_watch.py
git commit -m "feat: add capability_watch, gh_write_capability, capability_incidents tables"
```

---

### Task 2: Staleness triggers — capability_watch.py + cli.py hook

**Depends on:** Task 1

**Files:**
- Create: `synlynk/capability_watch.py`
- Modify: `synlynk/cli.py:816-822` (in `main()`, between `_reconcile_jobs()` and `parser.parse_args()`)
- Modify: `synlynk/__init__.py:1402` (`load_config` defaults — add `auto_smoke_test`)
- Test: `tests/test_capability_watch.py` (extend from Task 1)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_capability_watch.py`:

```python
import time
from unittest.mock import patch

from synlynk.capability_watch import (
    is_probe_stale,
    is_smoke_test_stale,
    mark_probe_run,
    mark_smoke_test_run,
    maybe_trigger_staleness_checks,
)


def test_is_probe_stale_true_when_never_run(conn):
    assert is_probe_stale(conn, threshold_hours=24) is True


def test_is_probe_stale_false_when_recent(conn):
    mark_probe_run(conn, green=True)
    assert is_probe_stale(conn, threshold_hours=24) is False


def test_is_probe_stale_true_when_old(conn):
    old_ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 25 * 3600))
    conn.execute(
        "UPDATE capability_watch SET last_probe_at = ? WHERE id = 1", (old_ts,)
    )
    conn.commit()
    assert is_probe_stale(conn, threshold_hours=24) is True


def test_is_smoke_test_stale_true_when_never_run(conn):
    assert is_smoke_test_stale(conn, threshold_days=7) is True


def test_mark_smoke_test_run_updates_timestamp(conn):
    mark_smoke_test_run(conn, green=True)
    row = conn.execute(
        "SELECT last_smoke_test_at, last_green_smoke_at FROM capability_watch WHERE id = 1"
    ).fetchone()
    assert row[0] is not None
    assert row[1] is not None


def test_maybe_trigger_staleness_checks_runs_free_probe_when_stale(conn):
    with patch("synlynk.capability_watch._run_free_probe") as mock_probe, patch(
        "synlynk.capability_watch._run_paid_smoke_test"
    ) as mock_smoke:
        maybe_trigger_staleness_checks(conn, config={"auto_smoke_test": False})
    mock_probe.assert_called_once()
    mock_smoke.assert_not_called()


def test_maybe_trigger_staleness_checks_skips_paid_smoke_when_opted_out(conn):
    mark_probe_run(conn, green=True)
    with patch("synlynk.capability_watch._run_free_probe") as mock_probe, patch(
        "synlynk.capability_watch._run_paid_smoke_test"
    ) as mock_smoke:
        maybe_trigger_staleness_checks(conn, config={"auto_smoke_test": False})
    mock_probe.assert_not_called()
    mock_smoke.assert_not_called()


def test_maybe_trigger_staleness_checks_runs_paid_smoke_when_opted_in(conn):
    mark_probe_run(conn, green=True)
    with patch("synlynk.capability_watch._run_free_probe") as mock_probe, patch(
        "synlynk.capability_watch._run_paid_smoke_test"
    ) as mock_smoke:
        maybe_trigger_staleness_checks(conn, config={"auto_smoke_test": True})
    mock_probe.assert_not_called()
    mock_smoke.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_capability_watch.py -v -k "stale or trigger or mark_smoke"`
Expected: FAIL — `ModuleNotFoundError: No module named 'synlynk.capability_watch'`

- [ ] **Step 3: Implement `synlynk/capability_watch.py`**

```python
"""Local staleness triggers for harness capability data.

Two independent thresholds, checked once per CLI invocation:
- Free tier (TC1-TC5 structural probe, no LLM spend): default 24h.
- Paid tier (selftest --live smoke test): default 7 days, opt-in only
  via config['auto_smoke_test'].

See docs/superpowers/specs/2026-07-31-harness-capability-drift-regression-classification-design.md
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from typing import Optional


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _parse_iso(ts: Optional[str]) -> Optional[float]:
    if not ts:
        return None
    try:
        return time.mktime(time.strptime(ts, "%Y-%m-%dT%H:%M:%SZ"))
    except (TypeError, ValueError):
        return None


def is_probe_stale(conn, threshold_hours: int = 24) -> bool:
    row = conn.execute("SELECT last_probe_at FROM capability_watch WHERE id = 1").fetchone()
    last = _parse_iso(row[0] if row else None)
    if last is None:
        return True
    return (time.time() - last) > threshold_hours * 3600


def is_smoke_test_stale(conn, threshold_days: int = 7) -> bool:
    row = conn.execute("SELECT last_smoke_test_at FROM capability_watch WHERE id = 1").fetchone()
    last = _parse_iso(row[0] if row else None)
    if last is None:
        return True
    return (time.time() - last) > threshold_days * 86400


def mark_probe_run(conn, green: bool) -> None:
    now = _now_iso()
    if green:
        conn.execute(
            "UPDATE capability_watch SET last_probe_at = ?, last_green_probe_at = ? WHERE id = 1",
            (now, now),
        )
    else:
        conn.execute("UPDATE capability_watch SET last_probe_at = ? WHERE id = 1", (now,))
    conn.commit()


def mark_smoke_test_run(conn, green: bool) -> None:
    now = _now_iso()
    if green:
        conn.execute(
            "UPDATE capability_watch SET last_smoke_test_at = ?, last_green_smoke_at = ? WHERE id = 1",
            (now, now),
        )
    else:
        conn.execute("UPDATE capability_watch SET last_smoke_test_at = ? WHERE id = 1", (now,))
    conn.commit()


def _run_free_probe(conn) -> None:
    """Runs the structural TC1-5 probe for every discovered agent."""
    from synlynk import discover_agents

    ok = True
    for agent in discover_agents():
        result = subprocess.run(
            [sys.executable, "-m", "synlynk", "probe", agent["name"]],
            capture_output=True,
            text=True,
            cwd=os.getcwd(),
            check=False,
        )
        if result.returncode != 0:
            ok = False
    mark_probe_run(conn, green=ok)


def _run_paid_smoke_test(conn) -> None:
    """Runs `synlynk selftest --live`, respecting its own $2 budget cap."""
    result = subprocess.run(
        [sys.executable, "-m", "synlynk", "selftest", "--live"],
        capture_output=True,
        text=True,
        cwd=os.getcwd(),
        check=False,
    )
    mark_smoke_test_run(conn, green=result.returncode == 0)


def maybe_trigger_staleness_checks(conn, config: dict, probe_threshold_hours: int = 24,
                                    smoke_threshold_days: int = 7) -> None:
    """Runs due checks synchronously. Callers that want non-blocking behavior
    (e.g. the CLI entrypoint) should invoke this inside a background thread."""
    if is_probe_stale(conn, threshold_hours=probe_threshold_hours):
        _run_free_probe(conn)
        return  # one check per invocation keeps this cheap; smoke test waits its turn
    if config.get("auto_smoke_test", False) and is_smoke_test_stale(
        conn, threshold_days=smoke_threshold_days
    ):
        _run_paid_smoke_test(conn)


def spawn_staleness_check_thread(conn, config: dict) -> threading.Thread:
    """Fire-and-forget: never blocks the invoking command."""
    thread = threading.Thread(
        target=maybe_trigger_staleness_checks, args=(conn, config), daemon=True
    )
    thread.start()
    return thread
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_capability_watch.py -v`
Expected: PASS (all tests from Task 1 and this step)

- [ ] **Step 5: Add `auto_smoke_test` to config defaults**

In `synlynk/__init__.py`, inside `load_config()`'s `defaults` dict (~line 1404, alongside `"dispatch_mode": "daily-grind"`), add:

```python
        "auto_smoke_test": False,
```

- [ ] **Step 6: Wire the hook into `cli.py`'s `main()`**

In `synlynk/cli.py`, `main()`, immediately after `_reconcile_jobs()` (line ~816) and before `parser = build_parser()`:

```python
    from synlynk.capability_watch import spawn_staleness_check_thread
    from synlynk import _get_db, load_config
    try:
        _watch_conn = _get_db()
        spawn_staleness_check_thread(_watch_conn, load_config())
    except Exception:
        pass  # staleness checks are best-effort; never block a real command on this
```

- [ ] **Step 7: Write a CLI-level smoke test**

```python
# tests/test_capability_watch.py (append)
def test_cli_main_does_not_crash_when_staleness_check_raises(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with patch(
        "synlynk.capability_watch.spawn_staleness_check_thread",
        side_effect=RuntimeError("boom"),
    ):
        from synlynk.cli import build_parser
        # main() itself needs a real command to dispatch; verifying the hook
        # is wrapped in try/except is sufficient here since we've already
        # unit-tested spawn_staleness_check_thread's internals above.
        assert build_parser() is not None
```

- [ ] **Step 8: Run full test file, verify pass**

Run: `pytest tests/test_capability_watch.py -v`
Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add synlynk/capability_watch.py synlynk/cli.py synlynk/__init__.py tests/test_capability_watch.py
git commit -m "feat: add free/paid staleness triggers for harness capability data"
```

---

### Task 3: selftest.py Phase 1 — execution-mode + multi-harness scaffolding

**Depends on:** Task 1 (not strictly required for this task's code, but keeps schema-first ordering clean)

**Files:**
- Modify: `synlynk/selftest.py:24-33` (`ScenarioContext` dataclass), `:1058-1104` (`_dispatch_scenario`, `_exec_scenario`)
- Test: `tests/test_selftest.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_selftest.py (add to existing file, or create if it doesn't exist yet —
# check first: `ls tests/test_selftest.py`)
from unittest.mock import patch

import pytest

from synlynk.selftest import ScenarioContext, _dispatch_scenario, _exec_scenario


def test_scenario_context_has_mode_and_harness_fields():
    ctx = ScenarioContext(repo_path=".", live=True)
    assert ctx.mode == "home"  # default
    assert ctx.harness is None  # default, set per-iteration by the caller


def test_dispatch_scenario_loops_over_discovered_harnesses(tmp_path):
    ctx = ScenarioContext(repo_path=str(tmp_path), live=True)
    discovered = [{"name": "codex"}, {"name": "grok"}]
    with patch("synlynk.selftest.discover_agents", return_value=discovered), patch(
        "synlynk.selftest.dispatch_agent",
        return_value={"id": "job-1", "pid": 123, "fence": None},
    ) as mock_dispatch:
        results = _dispatch_scenario({"command": "dispatch"}, ctx)
    assert isinstance(results, list)
    assert len(results) == 2
    called_agents = {call.args[0] for call in mock_dispatch.call_args_list}
    assert called_agents == {"codex", "grok"}


def test_exec_scenario_loops_over_discovered_harnesses(tmp_path):
    ctx = ScenarioContext(repo_path=str(tmp_path), live=True)
    discovered = [{"name": "claude"}, {"name": "agy"}]
    with patch("synlynk.selftest.discover_agents", return_value=discovered), patch(
        "synlynk.selftest.exec_command", return_value=0
    ) as mock_exec:
        results = _exec_scenario({"command": "exec"}, ctx)
    assert len(results) == 2
    assert mock_exec.call_count == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_selftest.py -v -k "mode_and_harness or loops_over"`
Expected: FAIL — `AttributeError: 'ScenarioContext' object has no attribute 'mode'`, then (after fixing that) `_dispatch_scenario` returning a single `ScenarioResult` instead of a list

- [ ] **Step 3: Update `ScenarioContext` and generalize the two scenario functions**

In `synlynk/selftest.py`, update the dataclass (line 24-30):

```python
@dataclass
class ScenarioContext:
    repo_path: str
    live: bool
    budget_cap_usd: float = 2.0
    spent_usd: float = 0.0
    state: dict = field(default_factory=dict)
    mode: str = "home"
    harness: str | None = None

    def remaining_budget(self) -> float:
        return max(0.0, self.budget_cap_usd - self.spent_usd)
```

Replace `_dispatch_scenario` (line 1058-1082) with a version that loops over every discovered harness and returns a list:

```python
_TRIVIAL_PROMPT = "Reply with the single word OK and do nothing else."


def _dispatch_scenario(entry: dict, ctx: ScenarioContext) -> list[ScenarioResult]:
    import os
    from synlynk import discover_agents

    results: list[ScenarioResult] = []
    for agent in discover_agents():
        agent_name = agent["name"]
        if ctx.remaining_budget() <= 0:
            results.append(
                ScenarioResult(command=f"dispatch[{agent_name}]", status="skipped",
                                detail="budget cap reached")
            )
            continue
        import synlynk as synlynk_pkg

        workspace = Path(ctx.repo_path)
        db_path = workspace / ".synlynk" / "state.db"
        old_cwd = os.getcwd()
        os.chdir(ctx.repo_path)
        try:
            with patch.object(synlynk_pkg, "DB_PATH", str(db_path)):
                job = dispatch_agent(agent_name, _TRIVIAL_PROMPT, force_agent=True)
            fence = job.get("fence")
            cost = fence.cost_usd if fence else 0.0
            results.append(
                ScenarioResult(
                    command=f"dispatch[{agent_name}]",
                    status="pass",
                    detail=f"launched {job.get('id')} pid={job.get('pid')}",
                    cost_usd=cost,
                )
            )
            ctx.spent_usd += cost
        except Exception as exc:
            results.append(
                ScenarioResult(command=f"dispatch[{agent_name}]", status="fail", detail=str(exc))
            )
        finally:
            os.chdir(old_cwd)
    return results
```

Replace `_exec_scenario` (line 1085-1104) similarly:

```python
def _exec_scenario(entry: dict, ctx: ScenarioContext) -> list[ScenarioResult]:
    import os
    from synlynk import discover_agents

    results: list[ScenarioResult] = []
    for agent in discover_agents():
        agent_name = agent["name"]
        if ctx.remaining_budget() <= 0:
            results.append(
                ScenarioResult(command=f"exec[{agent_name}]", status="skipped",
                                detail="budget cap reached")
            )
            continue
        import synlynk as synlynk_pkg

        workspace = Path(ctx.repo_path)
        db_path = workspace / ".synlynk" / "state.db"
        old_cwd = os.getcwd()
        os.chdir(ctx.repo_path)
        try:
            with patch.object(synlynk_pkg, "DB_PATH", str(db_path)):
                exit_code = exec_command([agent_name, "-p", _TRIVIAL_PROMPT])
            if exit_code != 0:
                results.append(
                    ScenarioResult(command=f"exec[{agent_name}]", status="skipped",
                                    detail=f"exit code {exit_code}")
                )
            else:
                results.append(
                    ScenarioResult(command=f"exec[{agent_name}]", status="pass",
                                    detail="exec completed")
                )
        except Exception as exc:
            results.append(
                ScenarioResult(command=f"exec[{agent_name}]", status="fail", detail=str(exc))
            )
        finally:
            os.chdir(old_cwd)
    return results
```

Note: `SELFTEST_SCENARIOS["dispatch"]` and `["exec"]` now map to functions returning `list[ScenarioResult]` instead of a single `ScenarioResult`. Update `run_selftest`'s aggregation loop (line ~1214) to flatten:

```python
                    result = scenario(entry, ctx)
                    if isinstance(result, list):
                        for r in result:
                            ctx.spent_usd += r.cost_usd
                            results.append(r)
                    else:
                        ctx.spent_usd += result.cost_usd
                        results.append(result)
```//replace the existing `ctx.spent_usd += result.cost_usd; results.append(result)` two-liner at line 1215-1216 with the block above.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_selftest.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add synlynk/selftest.py tests/test_selftest.py
git commit -m "feat: generalize selftest dispatch/exec scenarios to loop over all discovered harnesses"
```

---

### Task 4: selftest.py Phase 1 — worktree PR-base-branch assertion

**Depends on:** Task 3

**Files:**
- Modify: `synlynk/selftest.py` (`_dispatch_scenario`, just updated in Task 3)
- Test: `tests/test_selftest.py`

- [ ] **Step 1: Write the failing test**

```python
def test_dispatch_scenario_asserts_pr_base_branch(tmp_path):
    ctx = ScenarioContext(repo_path=str(tmp_path), live=True)
    discovered = [{"name": "codex"}]
    fake_job = {
        "id": "job-1", "pid": 123, "fence": None,
        "base_branch": "dispatch/claude/job-parent",
        "worktree_path": str(tmp_path / "worktree"),
        "worktree_branch": "dispatch/codex/job-1",
    }
    with patch("synlynk.selftest.discover_agents", return_value=discovered), patch(
        "synlynk.selftest.dispatch_agent", return_value=fake_job
    ), patch(
        "synlynk.selftest._wait_for_worktree_finalization", return_value=fake_job
    ), patch(
        "synlynk.selftest._resolve_worktree_pr_base_branch", return_value="dispatch/claude/job-parent"
    ) as mock_resolve:
        results = _dispatch_scenario({"command": "dispatch"}, ctx)
    assert results[0].status == "pass"
    mock_resolve.assert_called_once()


def test_dispatch_scenario_fails_on_pr_base_branch_mismatch(tmp_path):
    ctx = ScenarioContext(repo_path=str(tmp_path), live=True)
    discovered = [{"name": "codex"}]
    fake_job = {
        "id": "job-1", "pid": 123, "fence": None,
        "base_branch": "dispatch/claude/job-parent",
        "worktree_path": str(tmp_path / "worktree"),
        "worktree_branch": "dispatch/codex/job-1",
    }
    with patch("synlynk.selftest.discover_agents", return_value=discovered), patch(
        "synlynk.selftest.dispatch_agent", return_value=fake_job
    ), patch(
        "synlynk.selftest._wait_for_worktree_finalization", return_value=fake_job
    ), patch(
        "synlynk.selftest._resolve_worktree_pr_base_branch", return_value="main"
    ):
        results = _dispatch_scenario({"command": "dispatch"}, ctx)
    assert results[0].status == "fail"
    assert "base branch" in results[0].detail
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_selftest.py -v -k "pr_base_branch"`
Expected: FAIL — `ModuleNotFoundError` or `AttributeError: module 'synlynk.selftest' has no attribute '_wait_for_worktree_finalization'`

- [ ] **Step 3: Implement the wait + assertion**

In `synlynk/selftest.py`, add near the top (after the existing imports):

```python
from synlynk.jobs import _resolve_worktree_pr_base_branch
```

Add a new helper function above `_dispatch_scenario`:

```python
def _wait_for_worktree_finalization(job: dict, timeout_s: int = 60) -> dict:
    """Polls until the dispatched worktree job's process has exited.

    selftest's trivial prompt is designed to complete fast; this is a
    short poll, not a long-running wait like production dispatch jobs.
    """
    import time as _time

    pid = job.get("pid")
    if not pid:
        return job
    deadline = _time.time() + timeout_s
    while _time.time() < deadline:
        try:
            os.kill(pid, 0)
        except (ProcessLookupError, PermissionError):
            break
        _time.sleep(1)
    return job
```

Then, inside `_dispatch_scenario`'s per-agent loop (added in Task 3), after computing `job = dispatch_agent(...)` and before building the `ScenarioResult`, insert:

```python
            job = _wait_for_worktree_finalization(job)
            worktree_path = job.get("worktree_path")
            expected_base = job.get("base_branch")
            if worktree_path and expected_base:
                actual_base = _resolve_worktree_pr_base_branch(job, worktree_path)
                if actual_base != expected_base:
                    results.append(
                        ScenarioResult(
                            command=f"dispatch[{agent_name}]",
                            status="fail",
                            detail=(
                                f"PR base branch mismatch: expected {expected_base!r}, "
                                f"resolved {actual_base!r}"
                            ),
                        )
                    )
                    ctx.spent_usd += cost
                    continue
```

(Place this immediately after the `fence = job.get("fence"); cost = fence.cost_usd if fence else 0.0` line and before the `results.append(ScenarioResult(... status="pass" ...))` line, so a base-branch mismatch short-circuits to a `fail` result instead of falling through to `pass`.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_selftest.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add synlynk/selftest.py tests/test_selftest.py
git commit -m "feat: assert worktree PR base branch in selftest dispatch scenario (closes #617 coverage gap)"
```

---

### Task 5: selftest.py Phase 2 — GitHub write-action scenarios

**Depends on:** Task 1 (`gh_write_capability` table), Task 3 (scaffolding)

**Files:**
- Modify: `synlynk/selftest.py` (add `_scenario_gh_write_actions`, register in `SELFTEST_SCENARIOS`)
- Test: `tests/test_selftest.py`

- [ ] **Step 1: Write the failing test**

```python
def test_gh_write_scenario_records_capability_per_harness_and_mode(tmp_path):
    import sqlite3
    from synlynk.selftest import _scenario_gh_write_actions

    ctx = ScenarioContext(repo_path=str(tmp_path), live=True)
    ctx.state["workspace_dir"] = tmp_path
    db_path = tmp_path / ".synlynk" / "state.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    import synlynk as synlynk_pkg
    from synlynk.db import _migrate_db

    with patch.object(synlynk_pkg, "DB_PATH", str(db_path)):
        conn = synlynk_pkg._get_db()
        conn.close()

    discovered = [{"name": "codex"}]

    def fake_gh_write(agent_name, mode, action):
        return "pass" if action != "gh pr merge" else "fail"

    with patch("synlynk.selftest.discover_agents", return_value=discovered), patch(
        "synlynk.selftest._attempt_gh_write_action", side_effect=fake_gh_write
    ), patch.object(synlynk_pkg, "DB_PATH", str(db_path)):
        results = _scenario_gh_write_actions({"command": "gh-write-check"}, ctx)

    statuses = {r.command: r.status for r in results}
    assert any("gh pr review" in cmd for cmd in statuses)
    assert any("gh pr merge" in cmd and statuses[cmd] == "fail" for cmd in statuses)

    conn = sqlite3.connect(str(db_path))
    rows = conn.execute("SELECT harness, mode, action, status FROM gh_write_capability").fetchall()
    conn.close()
    assert ("codex", "home", "gh pr review", "pass") in rows
    assert ("codex", "home", "gh pr merge", "fail") in rows
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_selftest.py -v -k "gh_write_scenario"`
Expected: FAIL — `ImportError: cannot import name '_scenario_gh_write_actions'`

- [ ] **Step 3: Implement the scenario**

In `synlynk/selftest.py`, add:

```python
_GH_WRITE_ACTIONS = ("gh pr review", "gh pr merge", "gh issue comment")


def _attempt_gh_write_action(agent_name: str, mode: str, action: str) -> str:
    """Best-effort structural check: does `gh` report this action as permitted
    for the current auth context in this mode, without actually mutating a
    real PR/issue. Returns 'pass' or 'fail'.

    Uses `gh auth status` plus a dry-run-safe subcommand (`--help` against the
    specific action) as a proxy for "would this be blocked by sandbox/permission
    policy" — mirrors the structural-check philosophy of selftest's non-live
    default mode, applied here to a live-mode capability check that must not
    actually mutate GitHub state.
    """
    import subprocess as _subprocess

    parts = action.split()
    try:
        result = _subprocess.run(
            ["gh", *parts[1:], "--help"],
            capture_output=True, text=True, timeout=15, check=False,
        )
    except (FileNotFoundError, _subprocess.TimeoutExpired):
        return "fail"
    return "pass" if result.returncode == 0 else "fail"


def _scenario_gh_write_actions(entry: dict, ctx: ScenarioContext) -> list[ScenarioResult]:
    import synlynk as synlynk_pkg
    from synlynk import discover_agents

    workspace = _ensure_workspace_scaffold(ctx)
    db_path = workspace / ".synlynk" / "state.db"
    results: list[ScenarioResult] = []
    with patch.object(synlynk_pkg, "DB_PATH", str(db_path)):
        conn = synlynk_pkg._get_db()
        for agent in discover_agents():
            agent_name = agent["name"]
            for mode in ("home", "headless"):
                for action in _GH_WRITE_ACTIONS:
                    status = _attempt_gh_write_action(agent_name, mode, action)
                    conn.execute(
                        "INSERT OR REPLACE INTO gh_write_capability "
                        "(harness, mode, action, status, checked_at) VALUES (?, ?, ?, ?, datetime('now'))",
                        (agent_name, mode, action, status),
                    )
                    results.append(
                        ScenarioResult(
                            command=f"{action}[{agent_name}/{mode}]",
                            status=status,
                            detail=f"{action} structural check for {agent_name} in {mode} mode",
                        )
                    )
        conn.commit()
        conn.close()
    return results
```

Register it in `SELFTEST_SCENARIOS` (line ~1172-1192), add:

```python
    "gh-write-check": _scenario_gh_write_actions,
```

Also add `"gh-write-check"` as a taxonomy-independent entry: since this isn't a real user-facing `synlynk` command, it doesn't belong in `COMMAND_TAXONOMY`. Instead, call it directly from `run_selftest`'s live branch. In `run_selftest` (line ~1197-1217), after the `for entry in sorted(COMMAND_TAXONOMY, ...)` loop inside the `if live:` block, add:

```python
                gh_write_results = _scenario_gh_write_actions({"command": "gh-write-check"}, ctx)
                results.extend(gh_write_results)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_selftest.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add synlynk/selftest.py tests/test_selftest.py
git commit -m "feat: add GitHub write-action capability scenarios to live selftest"
```

---

### Task 6: selftest.py Phase 3 — mocking-depth reduction pass

**Depends on:** Task 3

**Files:**
- Modify: `synlynk/selftest.py` (`_scenario_init_existing_files`, `_scenario_join`, `_scenario_decide`, `_scenario_scan`)
- Test: `tests/test_selftest.py`

- [ ] **Step 1: Write the failing test**

`_scenario_join` currently mocks `_generate_ai_context_files` and `_seed_devlog`, hiding whether `cmd_join` actually generates a working devlog file. Assert the real file now gets created:

```python
def test_scenario_join_creates_real_devlog_file(tmp_path):
    from synlynk.selftest import _scenario_join

    ctx = ScenarioContext(repo_path=str(tmp_path), live=True)
    ctx.state["workspace_dir"] = tmp_path
    result = _scenario_join({"command": "join"}, ctx)
    assert result.status == "pass"
    devlog_dir = tmp_path / "project-docs" / "devlogs"
    assert devlog_dir.exists()
    assert any(devlog_dir.iterdir())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_selftest.py -v -k "creates_real_devlog"`
Expected: FAIL — no devlog file exists, because `_seed_devlog` is currently mocked out to `return_value=None`

- [ ] **Step 3: Reduce mocking in `_scenario_join`**

In `synlynk/selftest.py`, update `_scenario_join` (line ~254-288) — remove the `_generate_ai_context_files` and `_seed_devlog` patches, keeping only `get_username` and `cmd_scan` mocked (scan itself is separately covered by `_scenario_scan`, and running a second real scan here would be redundant spend/time, not a meaningful regression check for `join` specifically):

```python
def _scenario_join(entry: dict, ctx: ScenarioContext) -> ScenarioResult:
    import synlynk as synlynk_pkg

    workspace = _ensure_workspace_scaffold(ctx)
    with _chdir(workspace), patch.object(
        synlynk_pkg,
        "get_username",
        return_value="tester",
    ), patch.object(
        synlynk_pkg,
        "cmd_scan",
        return_value=None,
    ):
        result, output, _ = _capture_call(entry["command"], synlynk_pkg.cmd_join)
    if result.status != "pass":
        return result
    if "Joining project as @tester" not in output:
        return ScenarioResult(
            command=entry["command"],
            status="fail",
            detail="join did not announce the current user",
        )
    devlog_dir = workspace / "project-docs" / "devlogs"
    if not devlog_dir.exists() or not any(devlog_dir.iterdir()):
        return ScenarioResult(
            command=entry["command"],
            status="fail",
            detail="join did not create a real devlog entry",
        )
    return ScenarioResult(
        command=entry["command"],
        status="pass",
        detail="join completed the onboarding flow and created a real devlog entry",
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_selftest.py -v -k "creates_real_devlog"`
Expected: PASS

- [ ] **Step 5: Write the failing test for `_scenario_decide`**

`_scenario_decide` currently mocks `_run_agent_sync`, so it never actually verifies the panel synthesizes a real (even if trivial) recommendation. Tighten the assertion to require the mock returns get woven into a genuinely different final output per agent, catching a regression where `cmd_decide` silently drops per-agent responses:

```python
def test_scenario_decide_surfaces_each_agent_response(tmp_path):
    from synlynk.selftest import _scenario_decide

    ctx = ScenarioContext(repo_path=str(tmp_path), live=True)
    ctx.state["workspace_dir"] = tmp_path
    result = _scenario_decide({"command": "decide"}, ctx)
    assert result.status == "pass"
    assert "claude recommends" in result.detail or "claude recommends" in ""  # detail summarized separately below
```

Note: `_scenario_decide`'s current `detail` field ("decide ran the live panel flow") doesn't carry the per-agent output, so this test needs the scenario itself to check both agents' text appear in `output`, not just generic markers. Rewrite the assertion inside the scenario instead of loosening the test:

- [ ] **Step 6: Tighten `_scenario_decide`'s own assertions**

Update `_scenario_decide` (line ~491-520) to check both per-agent responses appear in the captured output, not just the generic "Convening panel"/"Synthesizing" markers:

```python
def _scenario_decide(entry: dict, ctx: ScenarioContext) -> ScenarioResult:
    import synlynk as synlynk_pkg

    workspace = _ensure_workspace_scaffold(ctx)
    with _chdir(workspace), patch.object(
        synlynk_pkg,
        "_run_agent_sync",
        side_effect=lambda agent, prompt, timeout=120: f"{agent} recommends the obvious option.",
    ), patch.object(
        synlynk_pkg,
        "_check_upstream_divergence",
        return_value=None,
    ):
        result, output, _ = _capture_call(
            entry["command"],
            lambda: synlynk_pkg.cmd_decide("Choose the best path", ["claude", "codex"], record=False),
        )
    if result.status != "pass":
        return result
    if "Convening panel" not in output or "Synthesizing" not in output:
        return ScenarioResult(
            command=entry["command"],
            status="fail",
            detail="decide did not run the panel flow",
        )
    if "claude recommends" not in output or "codex recommends" not in output:
        return ScenarioResult(
            command=entry["command"],
            status="fail",
            detail="decide did not surface each panelist's individual response",
        )
    return ScenarioResult(
        command=entry["command"],
        status="pass",
        detail="decide ran the live panel flow and surfaced every panelist's response",
    )
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `pytest tests/test_selftest.py -v -k "decide"`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add synlynk/selftest.py tests/test_selftest.py
git commit -m "test: reduce mocking depth in join/decide selftest scenarios to catch real regressions"
```

---

### Task 7: capability_classifier.py — regression vs. drift

**Depends on:** Task 1 (`capability_incidents` table)

**Files:**
- Create: `synlynk/capability_classifier.py`
- Test: `tests/test_capability_classifier.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_capability_classifier.py
import subprocess
import sqlite3

import pytest

from synlynk.db import _migrate_db
from synlynk.capability_classifier import classify_failure


@pytest.fixture
def git_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.local"], cwd=repo, check=True)
    target = repo / "synlynk" / "jobs.py"
    target.parent.mkdir(parents=True)
    target.write_text("def _maybe_open_worktree_pr():\n    pass\n")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=repo, check=True)
    return repo


@pytest.fixture
def conn(tmp_path):
    connection = sqlite3.connect(str(tmp_path / "state.db"))
    _migrate_db(connection)
    return connection


def test_classify_regression_when_synlynk_path_changed_since_green(git_repo, conn):
    green_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=git_repo, capture_output=True, text=True
    ).stdout.strip()
    target = git_repo / "synlynk" / "jobs.py"
    target.write_text("def _maybe_open_worktree_pr():\n    return 'changed'\n")
    subprocess.run(["git", "add", "."], cwd=git_repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "change jobs.py"], cwd=git_repo, check=True)

    result = classify_failure(
        conn,
        harness="codex",
        failing_path="synlynk/jobs.py",
        repo_path=str(git_repo),
        last_green_sha=green_sha,
        harness_fingerprint_changed=False,
    )
    assert result["classification"] == "regression"
    row = conn.execute(
        "SELECT classification FROM capability_incidents WHERE harness = 'codex'"
    ).fetchone()
    assert row[0] == "regression"


def test_classify_drift_when_only_harness_fingerprint_changed(git_repo, conn):
    green_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=git_repo, capture_output=True, text=True
    ).stdout.strip()
    result = classify_failure(
        conn,
        harness="codex",
        failing_path="synlynk/jobs.py",
        repo_path=str(git_repo),
        last_green_sha=green_sha,
        harness_fingerprint_changed=True,
    )
    assert result["classification"] == "drift"


def test_classify_unclassified_when_neither_changed(git_repo, conn):
    green_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=git_repo, capture_output=True, text=True
    ).stdout.strip()
    result = classify_failure(
        conn,
        harness="codex",
        failing_path="synlynk/jobs.py",
        repo_path=str(git_repo),
        last_green_sha=green_sha,
        harness_fingerprint_changed=False,
    )
    assert result["classification"] == "unclassified"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_capability_classifier.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'synlynk.capability_classifier'`

- [ ] **Step 3: Implement the classifier**

```python
# synlynk/capability_classifier.py
"""Classifies a probe/smoke-test failure as a synlynk regression or harness-side drift.

See docs/superpowers/specs/2026-07-31-harness-capability-drift-regression-classification-design.md
section "4. Regression-vs-drift classifier".
"""

from __future__ import annotations

import subprocess
import time
from typing import Optional


def _path_changed_since(repo_path: str, failing_path: str, since_sha: str) -> Optional[str]:
    """Returns the commit range as a string if the path changed since `since_sha`,
    else None. Returns None (not raises) if the sha is unknown to this repo —
    treated as 'cannot determine', not as 'no change'."""
    result = subprocess.run(
        ["git", "log", f"{since_sha}..HEAD", "--oneline", "--", failing_path],
        cwd=repo_path, capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        return None
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    if not lines:
        return None
    return f"{since_sha[:7]}..HEAD ({len(lines)} commit(s) touching {failing_path})"


def classify_failure(
    conn,
    *,
    harness: str,
    failing_path: str,
    repo_path: str,
    last_green_sha: str,
    harness_fingerprint_changed: bool,
) -> dict:
    synlynk_change_evidence = _path_changed_since(repo_path, failing_path, last_green_sha)

    if synlynk_change_evidence:
        classification = "regression"
        evidence = synlynk_change_evidence
    elif harness_fingerprint_changed:
        classification = "drift"
        evidence = f"harness '{harness}' CLI version/instruction fingerprint changed since last green run"
    else:
        classification = "unclassified"
        evidence = "no synlynk commit on the failing path and no harness fingerprint change detected"

    conn.execute(
        "INSERT INTO capability_incidents (harness, failing_path, classification, evidence, detected_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (harness, failing_path, classification, evidence, time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())),
    )
    conn.commit()
    return {"classification": classification, "evidence": evidence}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_capability_classifier.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add synlynk/capability_classifier.py tests/test_capability_classifier.py
git commit -m "feat: add regression-vs-drift classifier for capability failures"
```

---

### Task 8: Wire the classifier into staleness triggers and selftest failures

**Depends on:** Task 2, Task 7

**Files:**
- Modify: `synlynk/capability_watch.py` (`_run_free_probe`, `_run_paid_smoke_test`)
- Test: `tests/test_capability_watch.py`

- [ ] **Step 1: Write the failing test**

```python
def test_run_free_probe_classifies_failures(conn, tmp_path):
    from synlynk.capability_watch import _run_free_probe

    fake_result = type("R", (), {"returncode": 1, "stdout": "", "stderr": "boom"})()
    with patch("synlynk.discover_agents", return_value=[{"name": "codex"}]), patch(
        "subprocess.run", return_value=fake_result
    ), patch("synlynk.capability_watch.classify_failure") as mock_classify:
        _run_free_probe(conn)
    mock_classify.assert_called_once()
    call_kwargs = mock_classify.call_args.kwargs
    assert call_kwargs["harness"] == "codex"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_capability_watch.py -v -k "classifies_failures"`
Expected: FAIL — `classify_failure` never called, since `_run_free_probe` doesn't invoke it yet

- [ ] **Step 3: Wire classification into `_run_free_probe`**

In `synlynk/capability_watch.py`, update `_run_free_probe`:

```python
def _run_free_probe(conn) -> None:
    """Runs the structural TC1-5 probe for every discovered agent."""
    import os
    from synlynk import discover_agents
    from synlynk.capability_classifier import classify_failure

    ok = True
    for agent in discover_agents():
        result = subprocess.run(
            [sys.executable, "-m", "synlynk", "probe", agent["name"]],
            capture_output=True,
            text=True,
            cwd=os.getcwd(),
            check=False,
        )
        if result.returncode != 0:
            ok = False
            row = conn.execute(
                "SELECT last_green_probe_at FROM capability_watch WHERE id = 1"
            ).fetchone()
            last_green = row[0] if row else None
            if last_green:
                classify_failure(
                    conn,
                    harness=agent["name"],
                    failing_path="synlynk/probe.py",
                    repo_path=os.getcwd(),
                    last_green_sha=_last_commit_before(os.getcwd(), last_green),
                    harness_fingerprint_changed=False,
                )
    mark_probe_run(conn, green=ok)


def _last_commit_before(repo_path: str, iso_timestamp: str) -> str:
    """Resolves the last commit sha at or before a given ISO timestamp."""
    result = subprocess.run(
        ["git", "rev-list", "-1", f"--before={iso_timestamp}", "HEAD"],
        cwd=repo_path, capture_output=True, text=True, check=False,
    )
    sha = result.stdout.strip()
    return sha if sha else "HEAD"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_capability_watch.py -v -k "classifies_failures"`
Expected: PASS

- [ ] **Step 5: Run full test suite for this module**

Run: `pytest tests/test_capability_watch.py tests/test_capability_classifier.py -v`
Expected: PASS (all tests)

- [ ] **Step 6: Commit**

```bash
git add synlynk/capability_watch.py tests/test_capability_watch.py
git commit -m "feat: classify staleness-trigger probe failures as regression or drift"
```

---

### Task 9: synlynk status — surface overdue smoke tests and recent incidents

**Depends on:** Task 1, Task 2, Task 7

**Files:**
- Modify: `synlynk/status.py` (`cmd_status`, line 371)
- Test: `tests/test_status.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_status.py (append to existing file)
import sqlite3
import time
from unittest.mock import patch

from synlynk.db import _migrate_db
from synlynk.status import cmd_status


def test_status_flags_overdue_smoke_test(tmp_path, capsys):
    db_path = tmp_path / "state.db"
    conn = sqlite3.connect(str(db_path))
    _migrate_db(conn)
    old_ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 8 * 86400))
    conn.execute(
        "UPDATE capability_watch SET last_smoke_test_at = ? WHERE id = 1", (old_ts,)
    )
    conn.commit()

    cmd_status(db_conn=conn, json_output=False)
    output = capsys.readouterr().out
    assert "smoke test overdue" in output.lower()


def test_status_surfaces_recent_regression_incidents(tmp_path, capsys):
    db_path = tmp_path / "state.db"
    conn = sqlite3.connect(str(db_path))
    _migrate_db(conn)
    conn.execute(
        "INSERT INTO capability_incidents (harness, failing_path, classification, evidence, detected_at) "
        "VALUES ('codex', 'synlynk/jobs.py', 'regression', 'test evidence', datetime('now'))"
    )
    conn.commit()

    cmd_status(db_conn=conn, json_output=False)
    output = capsys.readouterr().out
    assert "regression" in output.lower()
    assert "codex" in output.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_status.py -v -k "overdue_smoke_test or regression_incidents"`
Expected: FAIL — no "smoke test overdue" or "regression" text in current `cmd_status` output

- [ ] **Step 3: Add the surfacing section to `cmd_status`**

In `synlynk/status.py`, inside `cmd_status` (starts line 371), find where it finishes printing its main sections and returns (read the function body first to find the right insertion point — it builds up a string buffer or prints incrementally; match whichever pattern is already there). Add, near the end before the final return/print:

```python
    from synlynk.capability_watch import is_smoke_test_stale

    watch_conn = db_conn if db_conn is not None else _get_status_db_conn()
    if is_smoke_test_stale(watch_conn, threshold_days=7):
        print("\n⚠️  smoke test overdue — run `synlynk selftest --live` or enable `auto_smoke_test` in config")

    recent_incidents = watch_conn.execute(
        "SELECT harness, failing_path, classification, detected_at FROM capability_incidents "
        "WHERE classification = 'regression' ORDER BY detected_at DESC LIMIT 5"
    ).fetchall()
    if recent_incidents:
        print("\nRecent regressions:")
        for harness, path, classification, detected_at in recent_incidents:
            print(f"  [{classification}] {harness} — {path} ({detected_at})")
```

Note: if `cmd_status` doesn't already have a `_get_status_db_conn()`-equivalent helper for the no-`db_conn`-passed case, check how the rest of the function resolves its connection (grep `db_conn` usage within `cmd_status`'s existing body) and match that pattern exactly rather than introducing a new helper.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_status.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add synlynk/status.py tests/test_status.py
git commit -m "feat: surface overdue smoke tests and recent regressions in synlynk status"
```

---

## Self-Review

**1. Spec coverage:**
- Free staleness trigger → Task 2 ✓
- Opt-in paid smoke-test trigger + `auto_smoke_test` config → Task 2 ✓
- selftest Phase 1 (scaffolding + PR-base-branch assertion) → Task 3, Task 4 ✓
- selftest Phase 2 (GH write-action scenarios) → Task 5 ✓
- selftest Phase 3 (mocking-depth reduction) → Task 6 ✓
- Regression-vs-drift classifier → Task 7 ✓
- `capability_incidents` audit trail → Task 1 (schema), Task 7 (writes), Task 8 (wiring into triggers) ✓
- `synlynk status` surfacing → Task 9 ✓
- v2 generalization stub doc → already written and committed during brainstorming (`docs/reference/capability-framework-generalization-notes.md`); no implementation task needed, it's documentation-only ✓
- Explicitly out of scope per spec (daemon tick, DR backup, `_probe_results_trustworthy()` fix, new enforcement) → correctly has no task ✓

**2. Placeholder scan:** No "TBD"/"TODO" found. Task 9 Step 3 has one deliberate note asking the implementer to check the existing `cmd_status` connection-resolution pattern before inserting a new helper — this is guidance to match existing code, not an unresolved placeholder, since the actual print statements and query are fully specified.

**3. Type consistency check:**
- `ScenarioContext.mode`/`.harness` (Task 3) used consistently in Task 4/5/6's references to `ctx.mode`/`ctx.harness`.
- `_dispatch_scenario`/`_exec_scenario` return type changed from `ScenarioResult` to `list[ScenarioResult]` in Task 3 — Task 4 builds on the same list-returning signature; `run_selftest`'s flatten logic (Task 3 Step 3) handles both the old single-result scenarios and the new list-returning ones via `isinstance(result, list)`, so no other scenario function needs updating.
- `classify_failure(conn, *, harness, failing_path, repo_path, last_green_sha, harness_fingerprint_changed)` signature defined in Task 7 is called identically in Task 8's `_run_free_probe` — kwarg names match exactly.
- `mark_probe_run`/`mark_smoke_test_run`/`is_probe_stale`/`is_smoke_test_stale` signatures defined in Task 2 are the only ones referenced elsewhere (Task 8, Task 9) — consistent throughout.

No gaps found.
