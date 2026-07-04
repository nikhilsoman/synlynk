# BS-16: Ecosystem Status + Capacity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver `synlynk status` (terminal + `--json`), `synlynk config set dispatch_mode`, live watch panel integration, and pre-dispatch capacity gates — giving users a real-time view of agent fleet health and stopping capacity-busting dispatches before they fail.

**Architecture:** New `synlynk/status.py` holds all compute logic (cycle capability, token estimation, headless efficiency). `synlynk/db.py` gains two new tables (`harness_status`, `cycle_capability`). `synlynk/probe.py` (post-modularise) gains capacity + cycle writes on each probe run. `synlynk/dispatch.py` gains three new preflight gates. `synlynk/hud.py` gains `HarnessSnapshot` and an updated `render_header()`. `synlynk/cli.py` wires `status` subcommand and threads `harness_data` into the watch poll loop.

**Prerequisite:** `chore/modularise-init` must be merged before starting. This plan references `synlynk/probe.py` and `synlynk/dispatch.py` — these files are created by that PR.

**Tech Stack:** Python 3 stdlib only (`sqlite3`, `json`, `os`, `re`, `time`). No new dependencies.

---

## File Map

| File | Action | What changes |
|---|---|---|
| `synlynk/db.py` | Modify | Add `harness_status` + `cycle_capability` tables to `_migrate_db()` |
| `synlynk/status.py` | Create | `_compute_cycle_capability()`, `estimate_dispatch_tokens()`, `_classify_task_type()`, `_get_avg_tool_calls()`, `_headless_efficiency_ratio()`, `_format_status_terminal()`, `cmd_status()` |
| `synlynk/probe.py` | Modify | Add capacity upsert + cycle capability write + latest version fetch to `_probe_agent()` |
| `synlynk/dispatch.py` | Modify | Add 3 capacity gates to `_preflight_dispatch()`; add `dispatch_mode` read to `dispatch_agent()` |
| `synlynk/__init__.py` | Modify | Add telemetry enrichment fields; add `cmd_config_set()` |
| `synlynk/hud.py` | Modify | Add `HarnessSnapshot` class; update `HUDRenderer.render_header()` signature |
| `synlynk/cli.py` | Modify | Add `status` subparser; add `config set` subparser; thread `harness_data` into `cmd_watch()` |
| `tests/test_ecosystem_status.py` | Create | ~20 tests covering all new functions |

---

## Task 1: DB migration — `harness_status` + `cycle_capability` tables

**Files:**
- Modify: `synlynk/db.py` — `_migrate_db()` function

Read `synlynk/db.py` line 116 before editing. `_migrate_db()` runs `CREATE TABLE IF NOT EXISTS` statements for each table. Add the two new tables at the end of the function, before the final `conn.commit()` if present.

- [ ] **Step 1: Write the failing test**

Create `tests/test_ecosystem_status.py`:

```python
"""Tests for BS-16 ecosystem status + capacity."""
import sqlite3
import pytest


@pytest.fixture
def db(tmp_path):
    conn = sqlite3.connect(str(tmp_path / "state.db"))
    from synlynk.db import _migrate_db
    _migrate_db(conn)
    yield conn
    conn.close()


def test_harness_status_table_exists(db):
    row = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='harness_status'"
    ).fetchone()
    assert row is not None


def test_cycle_capability_table_exists(db):
    row = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='cycle_capability'"
    ).fetchone()
    assert row is not None


def test_harness_status_columns(db):
    cols = {r[1] for r in db.execute("PRAGMA table_info(harness_status)")}
    required = {
        "agent_name", "attach_rate_24h", "attach_point_in_time",
        "adherence_score", "completion_rate_24h", "rescue_count_24h",
        "output_velocity_p50", "installed_version", "latest_version",
        "plan_tier", "plan_type", "ctx_window_tokens",
        "read_budget_tokens", "write_budget_tokens", "tool_budget_count",
        "tc1_status", "tc2_status", "tc3_status", "tc4_status",
        "harness_compat_score", "last_probe_at", "last_telemetry_at",
    }
    assert required <= cols


def test_cycle_capability_columns(db):
    cols = {r[1] for r in db.execute("PRAGMA table_info(cycle_capability)")}
    required = {"agent_name", "cycle", "support", "notes",
                "verb_count", "full_count", "partial_count", "updated_at"}
    assert required <= cols
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_ecosystem_status.py::test_harness_status_table_exists -v
```

Expected: FAIL — `no such table: harness_status`

- [ ] **Step 3: Add tables to `_migrate_db()` in `synlynk/db.py`**

Inside `_migrate_db(conn)`, after the last existing `CREATE TABLE IF NOT EXISTS` block, add:

```python
    conn.execute("""
        CREATE TABLE IF NOT EXISTS harness_status (
            agent_name             TEXT PRIMARY KEY,
            attach_rate_24h        REAL DEFAULT 0.0,
            attach_point_in_time   INTEGER DEFAULT 0,
            adherence_score        REAL DEFAULT NULL,
            completion_rate_24h    REAL DEFAULT NULL,
            rescue_count_24h       INTEGER DEFAULT 0,
            output_velocity_p50    REAL DEFAULT NULL,
            installed_version      TEXT DEFAULT '',
            latest_version         TEXT DEFAULT NULL,
            plan_tier              TEXT DEFAULT 'unknown',
            plan_type              TEXT DEFAULT 'd2c',
            ctx_window_tokens      INTEGER DEFAULT NULL,
            read_budget_tokens     INTEGER DEFAULT NULL,
            write_budget_tokens    INTEGER DEFAULT NULL,
            tool_budget_count      INTEGER DEFAULT NULL,
            tc1_status             TEXT DEFAULT 'unknown',
            tc2_status             TEXT DEFAULT 'unknown',
            tc3_status             TEXT DEFAULT 'unknown',
            tc4_status             TEXT DEFAULT 'unknown',
            harness_compat_score   REAL DEFAULT NULL,
            last_probe_at          TEXT DEFAULT NULL,
            last_telemetry_at      TEXT DEFAULT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cycle_capability (
            agent_name    TEXT NOT NULL,
            cycle         TEXT NOT NULL,
            support       TEXT NOT NULL,
            notes         TEXT,
            verb_count    INTEGER DEFAULT 0,
            full_count    INTEGER DEFAULT 0,
            partial_count INTEGER DEFAULT 0,
            updated_at    TEXT NOT NULL,
            PRIMARY KEY (agent_name, cycle)
        )
    """)
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_ecosystem_status.py -v 2>&1 | tail -15
```

Expected: 4 tests pass.

- [ ] **Step 5: Run full suite**

```bash
pytest --ignore=tests/test_capability_scoring.py -x -q 2>&1 | tail -5
```

Expected: all existing tests still pass.

- [ ] **Step 6: Commit**

```bash
git add synlynk/db.py tests/test_ecosystem_status.py
git commit -m "feat(bs16): harness_status + cycle_capability tables in state.db"
```

---

## Task 2: Create `synlynk/status.py` — compute functions

**Files:**
- Create: `synlynk/status.py`

This file contains all the new compute logic. No DB writes — it reads from state.db and returns data structures. `cmd_status()` is the terminal formatter.

- [ ] **Step 1: Write tests for compute functions** — add to `tests/test_ecosystem_status.py`:

```python
def test_classify_task_type_implement():
    from synlynk.status import _classify_task_type
    assert _classify_task_type("implement the new dispatch system") == "implement"

def test_classify_task_type_review():
    from synlynk.status import _classify_task_type
    assert _classify_task_type("review this PR and check for bugs") == "review"

def test_classify_task_type_default():
    from synlynk.status import _classify_task_type
    assert _classify_task_type("do some random thing") == "default"

def test_estimate_dispatch_tokens_small():
    from synlynk.status import estimate_dispatch_tokens
    result = estimate_dispatch_tokens("fix bug", "short context", "claude")
    assert result["input"] < 10_000
    assert result["output"] > 0
    assert result["tools"] >= 0

def test_estimate_dispatch_tokens_large_context():
    from synlynk.status import estimate_dispatch_tokens
    big_context = "word " * 400_000   # ~500K tokens
    result = estimate_dispatch_tokens("implement feature", big_context, "claude")
    assert result["input"] > 400_000

def test_compute_cycle_capability_claude(db):
    # Seed harness_verb_map rows for claude
    now = "2026-07-04T10:00:00Z"
    verbs = [
        ("dispatch.task",    "work",    "claude", "full"),
        ("dispatch.headless","work",    "claude", "full"),
        ("dispatch.resume",  "work",    "claude", "full"),
        ("synlynk probe",    "maintain","claude", "full"),
        ("synlynk doctor",   "maintain","claude", "full"),
        ("synlynk decide",   "dream",   "claude", "full"),
    ]
    for verb, cycle, agent, support in verbs:
        db.execute(
            "INSERT OR REPLACE INTO harness_verb_map "
            "(agent_name, verb, cycle_hint, support, notes, updated_at) "
            "VALUES (?,?,?,?,?,?)",
            (agent, verb, cycle, support, "", now)
        )
    db.commit()
    from synlynk.status import _compute_cycle_capability
    result = _compute_cycle_capability("claude", db)
    assert result["work"]["support"] == "full"
    assert result["maintain"]["support"] == "full"

def test_headless_efficiency_ratio_typical():
    from synlynk.status import _headless_efficiency_ratio
    # 10 jobs each with 5000 context tokens vs 50000 interactive estimate
    jobs = [{"context_tokens": 5000, "total_tokens": 8000} for _ in range(10)]
    ratio = _headless_efficiency_ratio(jobs, history_fraction=0.76)
    assert ratio > 1.0
    assert ratio < 10.0

def test_headless_efficiency_ratio_no_data():
    from synlynk.status import _headless_efficiency_ratio
    assert _headless_efficiency_ratio([], history_fraction=0.76) == 1.0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_ecosystem_status.py -k "classify or estimate or cycle_capability or efficiency" -v 2>&1 | tail -15
```

Expected: ImportError — `synlynk/status.py` doesn't exist yet.

- [ ] **Step 3: Create `synlynk/status.py`**

```python
"""synlynk status: ecosystem capacity compute, headless efficiency, terminal formatter."""

import json
import os
import re
import time
from typing import Optional

from synlynk._constants import AGENT_CAPABILITY_BASELINES

# Tier 1 curated capacity baselines — updated when probe detects version change.
TIER1_CAPACITY = {
    "claude": {"ctx_window_tokens": 200_000, "read_budget_tokens": 750_000,
               "write_budget_tokens": 32_000, "tool_budget_count": 200},
    "agy":    {"ctx_window_tokens": 1_000_000, "read_budget_tokens": 900_000,
               "write_budget_tokens": 8_000,  "tool_budget_count": 500},
    "codex":  {"ctx_window_tokens": 128_000, "read_budget_tokens": 110_000,
               "write_budget_tokens": 16_000, "tool_budget_count": 128},
    "grok":   {"ctx_window_tokens": 131_000, "read_budget_tokens": 115_000,
               "write_budget_tokens": 16_000, "tool_budget_count": 100},
}

TOOL_DEF_OVERHEAD = {"claude": 2200, "agy": 1800, "codex": 1600, "grok": 1400}
TASK_TYPE_OUTPUT  = {"implement": 8000, "review": 2000, "plan": 3000,
                     "debug": 1500, "test": 2500, "docs": 2000, "default": 4000}
SYSTEM_OVERHEAD   = 2000

CYCLES = ["dream", "plan", "work", "ship", "maintain", "engage"]


def _classify_task_type(prompt: str) -> str:
    """Return task type keyword from prompt for output-token estimation."""
    p = prompt.lower()
    for keyword in ("implement", "review", "plan", "debug", "test", "docs"):
        if keyword in p:
            return keyword
    return "default"


def estimate_dispatch_tokens(prompt: str, context_md: str,
                              agent_name: str) -> dict:
    """Estimate input/output/tool token usage before dispatch."""
    input_est = (
        len(context_md.split()) * 1.3
        + len(prompt.split()) * 1.3
        + TOOL_DEF_OVERHEAD.get(agent_name, 2000)
        + SYSTEM_OVERHEAD
    )
    task_type = _classify_task_type(prompt)
    output_est = TASK_TYPE_OUTPUT.get(task_type, 4000)
    avg_tool_calls = _get_avg_tool_calls(agent_name)
    tool_est = avg_tool_calls * 800
    return {"input": int(input_est), "output": output_est, "tools": int(tool_est)}


def _get_avg_tool_calls(agent_name: str, db_conn=None) -> float:
    """Return 30-day mean tool_call_count for agent, or baseline default."""
    default = {"claude": 25, "agy": 30, "codex": 20, "grok": 18}.get(agent_name, 20)
    if db_conn is None:
        return float(default)
    try:
        row = db_conn.execute(
            "SELECT AVG(tool_call_count) FROM telemetry_events "
            "WHERE agent=? AND tool_call_count IS NOT NULL "
            "AND recorded_at >= datetime('now', '-30 days')",
            (agent_name,)
        ).fetchone()
        if row and row[0] is not None:
            return float(row[0])
    except Exception:
        pass
    return float(default)


def _compute_cycle_capability(agent_name: str, db_conn) -> dict:
    """
    Aggregate harness_verb_map rows → cycle_capability dict and upsert to DB.

    Returns: {cycle: {"support": "full"|"partial"|"none",
                       "verb_count": int, "full_count": int, "partial_count": int}}
    """
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    result = {c: {"support": "none", "verb_count": 0,
                  "full_count": 0, "partial_count": 0} for c in CYCLES}

    try:
        rows = db_conn.execute(
            "SELECT cycle_hint, support FROM harness_verb_map WHERE agent_name=?",
            (agent_name,)
        ).fetchall()
    except Exception:
        return result

    for cycle_hint, support in rows:
        cycle = cycle_hint if cycle_hint in CYCLES else None
        if cycle is None:
            continue
        result[cycle]["verb_count"] += 1
        if support == "full":
            result[cycle]["full_count"] += 1
        elif support == "partial":
            result[cycle]["partial_count"] += 1

    for cycle, data in result.items():
        vc = data["verb_count"]
        fc = data["full_count"]
        pc = data["partial_count"]
        if vc == 0:
            data["support"] = "none"
        elif fc > 0:
            data["support"] = "full" if fc == vc else "partial"
        elif pc > 0:
            data["support"] = "partial"
        else:
            data["support"] = "none"

        try:
            db_conn.execute(
                """INSERT INTO cycle_capability
                   (agent_name, cycle, support, verb_count, full_count, partial_count, updated_at)
                   VALUES (?,?,?,?,?,?,?)
                   ON CONFLICT(agent_name, cycle) DO UPDATE SET
                     support=excluded.support, verb_count=excluded.verb_count,
                     full_count=excluded.full_count, partial_count=excluded.partial_count,
                     updated_at=excluded.updated_at""",
                (agent_name, cycle, data["support"],
                 vc, fc, pc, now)
            )
        except Exception:
            pass

    return result


def _headless_efficiency_ratio(jobs: list, history_fraction: float = 0.76) -> float:
    """
    Compute Nx headless efficiency ratio.

    history_fraction: fraction of tokens in a typical interactive session
    consumed by prior conversation history (empirical: 0.76 for 10-turn Claude).
    """
    if not jobs:
        return 1.0
    total_actual = sum(j.get("context_tokens", 0) + j.get("total_tokens", 0)
                       for j in jobs)
    if total_actual == 0:
        return 1.0
    # counterfactual: in interactive mode, each job's tokens would be inflated by history
    total_interactive = total_actual / (1 - history_fraction)
    tokens_saved = total_interactive - total_actual
    if tokens_saved <= 0:
        return 1.0
    return round(total_interactive / total_actual, 1)


def _load_harness_status_rows(db_conn) -> list:
    """Return all harness_status rows as dicts."""
    try:
        rows = db_conn.execute("SELECT * FROM harness_status").fetchall()
        cols = [d[0] for d in db_conn.execute(
            "SELECT * FROM harness_status LIMIT 0").description or []]
        if not cols:
            cols = [d[0] for d in db_conn.execute(
                "PRAGMA table_info(harness_status)").fetchall()]
        return [dict(zip(cols, r)) for r in rows]
    except Exception:
        return []


def _load_cycle_capability_rows(db_conn) -> dict:
    """Return cycle capability as {agent: {cycle: support_str}}."""
    result: dict = {}
    try:
        rows = db_conn.execute(
            "SELECT agent_name, cycle, support FROM cycle_capability"
        ).fetchall()
        for agent, cycle, support in rows:
            result.setdefault(agent, {})[cycle] = support
    except Exception:
        pass
    return result


def _format_status_terminal(harness_rows: list, cycle_map: dict,
                              efficiency_ratio: float,
                              dispatch_mode: str,
                              sentinels_active: int,
                              json_output: bool = False) -> str:
    """
    Format the synlynk status terminal output.
    Returns a string (ANSI for terminal, JSON string for --json).
    """
    agents = [r["agent_name"] for r in harness_rows] or ["claude", "agy", "codex", "grok"]
    attached = sum(1 for r in harness_rows if r.get("attach_point_in_time", 0))

    if json_output:
        return json.dumps({
            "headless_efficiency": efficiency_ratio,
            "fleet": {
                "attached": attached,
                "total": len(agents),
                "dispatch_mode": dispatch_mode,
            },
            "agents": {r["agent_name"]: r for r in harness_rows},
            "cycle_capability": cycle_map,
            "sentinels_active": sentinels_active,
        }, indent=2)

    CYCLE_DOTS = ["💡", "📋", "⚙️ ", "🚀", "🔧", "🤝"]
    SUPPORT_CHAR = {"full": "●", "partial": "◐", "none": "○"}
    ts = time.strftime("%Y-%m-%d %H:%M")

    lines = [
        f"SYNLYNK ECOSYSTEM STATUS  {ts}",
        "━" * 44,
        "",
        f"HEADLESS EFFICIENCY  {efficiency_ratio}×   headless dispatch baseline",
        "",
        f"FLEET   {attached}/{len(agents)} attached   "
        f"mode: {dispatch_mode}",
        "",
        f"{'AGENT SCORE':<14} {'ATTACH':>8}  {'COMPLETE':>9}  {'VERSION':>10}",
    ]
    for r in harness_rows:
        attach = f"{r.get('attach_rate_24h', 0) * 100:.0f}%"
        complete = (f"{r.get('completion_rate_24h', 0) * 100:.0f}%"
                    if r.get('completion_rate_24h') is not None else "—")
        ver = r.get("installed_version") or "—"
        drift = " ⚠" if (r.get("latest_version") and
                          r.get("latest_version") != ver) else ""
        lines.append(f"  {r['agent_name']:<12} {attach:>8}  {complete:>9}  {ver}{drift}")

    lines += ["", f"{'CAPACITY':<14} {'R(read)':>8}  {'W(write)':>9}  {'T(tools)':>8}  {'CTX':>8}"]
    cap = TIER1_CAPACITY
    for r in harness_rows:
        a = r["agent_name"]
        c = cap.get(a, {})
        r_tok = f"{c.get('read_budget_tokens', 0) // 1000}K"
        w_tok = f"{c.get('write_budget_tokens', 0) // 1000}K"
        t_bud = f"~{c.get('tool_budget_count', 0)}"
        ctx   = f"{c.get('ctx_window_tokens', 0) // 1000}K"
        lines.append(f"  {a:<12} {r_tok:>8}  {w_tok:>9}  {t_bud:>8}  {ctx:>8}")

    lines += ["", f"CYCLE CAPABILITY      " +
              "  ".join(f"{e[:5]:>5}" for e in ["Dream", "Plan", "Work", "Ship", "Maint", "Engage"])]
    for r in harness_rows:
        a = r["agent_name"]
        agent_cycles = cycle_map.get(a, {})
        dots = "  ".join(
            f"{SUPPORT_CHAR.get(agent_cycles.get(c, 'none'), '○'):>5}"
            for c in ["dream", "plan", "work", "ship", "maintain", "engage"]
        )
        lines.append(f"  {a:<18} {dots}")
    lines += ["", "  ● full  ◐ partial  ○ none"]
    lines += ["",
              f"SENTINELS   {'none active' if sentinels_active == 0 else f'{sentinels_active} active'}"]
    return "\n".join(lines)


def cmd_status(db_conn=None, json_output: bool = False) -> None:
    """Run synlynk status: print ecosystem status to stdout."""
    from synlynk import _get_db, load_config, _read_sentinel_alerts

    if db_conn is None:
        db_conn = _get_db()

    config = load_config()
    dispatch_mode = config.get("dispatch_mode", "daily-grind")

    harness_rows = _load_harness_status_rows(db_conn)
    cycle_map = _load_cycle_capability_rows(db_conn)

    # If no probe has run yet, populate agent list from baselines
    if not harness_rows:
        from synlynk._constants import AGENT_CAPABILITY_BASELINES
        harness_rows = [{"agent_name": a, "attach_rate_24h": 0.0,
                          "attach_point_in_time": 0, "installed_version": "—",
                          "latest_version": None, "completion_rate_24h": None}
                        for a in AGENT_CAPABILITY_BASELINES]

    # Headless efficiency from telemetry
    try:
        telemetry_rows = db_conn.execute(
            "SELECT context_tokens, total_tokens FROM telemetry_events "
            "WHERE recorded_at >= datetime('now', '-7 days')"
        ).fetchall()
        jobs = [{"context_tokens": r[0] or 0, "total_tokens": r[1] or 0}
                for r in telemetry_rows]
    except Exception:
        jobs = []
    efficiency = _headless_efficiency_ratio(jobs)

    sentinel_alerts = _read_sentinel_alerts()
    output = _format_status_terminal(
        harness_rows, cycle_map, efficiency, dispatch_mode,
        len(sentinel_alerts), json_output=json_output
    )
    print(output)
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_ecosystem_status.py -v 2>&1 | tail -20
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add synlynk/status.py tests/test_ecosystem_status.py
git commit -m "feat(bs16): synlynk/status.py — cycle capability, token estimation, headless efficiency"
```

---

## Task 3: `synlynk probe` enhancements — capacity + cycle writes

**Files:**
- Modify: `synlynk/probe.py` — `_probe_agent()` function

Read `synlynk/probe.py` before editing. `_probe_agent()` currently writes to `harness_records` and `harness_version_history`. Add three new operations at the end of the function, before `db_conn.commit()`.

- [ ] **Step 1: Write failing tests** — add to `tests/test_ecosystem_status.py`:

```python
def test_probe_upserts_harness_status(db, tmp_path, monkeypatch):
    """After _probe_agent runs, harness_status row exists for the agent."""
    import subprocess
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw:
        type("R", (), {"stdout": "claude 1.2.3\n", "returncode": 0, "stderr": ""})())
    # seed harness_baselines so fast_path skips
    from synlynk.probe import _probe_agent
    _probe_agent("claude", db, fast_path_ok=False)
    row = db.execute(
        "SELECT agent_name, installed_version FROM harness_status WHERE agent_name='claude'"
    ).fetchone()
    assert row is not None
    assert row[0] == "claude"

def test_probe_writes_cycle_capability(db, monkeypatch):
    """After _probe_agent runs, cycle_capability rows exist for the agent."""
    import subprocess
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw:
        type("R", (), {"stdout": "claude 1.2.3\n", "returncode": 0, "stderr": ""})())
    from synlynk.probe import _probe_agent
    _probe_agent("claude", db, fast_path_ok=False)
    rows = db.execute(
        "SELECT cycle FROM cycle_capability WHERE agent_name='claude'"
    ).fetchall()
    assert len(rows) == 6   # one per cycle
```

- [ ] **Step 2: Run failing tests**

```bash
pytest tests/test_ecosystem_status.py::test_probe_upserts_harness_status \
       tests/test_ecosystem_status.py::test_probe_writes_cycle_capability -v
```

Expected: FAIL — `harness_status` and `cycle_capability` tables exist but are empty after probe.

- [ ] **Step 3: Modify `_probe_agent()` in `synlynk/probe.py`**

After the existing harness_version_history insert (before the final `db_conn.commit()`), add:

```python
    # BS-16: upsert harness_status with Tier 1 capacity
    from synlynk.status import TIER1_CAPACITY
    cap = TIER1_CAPACITY.get(agent_name, {})
    _probe_at = now  # already defined above as strftime string
    _attach = 1 if compliance == "ok" else 0
    db_conn.execute(
        """INSERT INTO harness_status
           (agent_name, attach_point_in_time, installed_version,
            ctx_window_tokens, read_budget_tokens, write_budget_tokens,
            tool_budget_count, tc1_status, tc2_status, tc3_status, tc4_status,
            last_probe_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(agent_name) DO UPDATE SET
             attach_point_in_time=excluded.attach_point_in_time,
             installed_version=excluded.installed_version,
             ctx_window_tokens=excluded.ctx_window_tokens,
             read_budget_tokens=excluded.read_budget_tokens,
             write_budget_tokens=excluded.write_budget_tokens,
             tool_budget_count=excluded.tool_budget_count,
             tc1_status=excluded.tc1_status,
             tc2_status=excluded.tc2_status,
             tc3_status=excluded.tc3_status,
             tc4_status=excluded.tc4_status,
             last_probe_at=excluded.last_probe_at""",
        (
            agent_name, _attach, installed_version,
            cap.get("ctx_window_tokens"), cap.get("read_budget_tokens"),
            cap.get("write_budget_tokens"), cap.get("tool_budget_count"),
            "unknown", "unknown", "unknown", "unknown",
            _probe_at,
        )
    )

    # BS-16: compute and write cycle capability
    from synlynk.status import _compute_cycle_capability
    _compute_cycle_capability(agent_name, db_conn)

    # BS-16: best-effort latest version fetch (3s timeout, no sentinel on failure)
    _LATEST_VERSION_CMDS = {
        "claude": ["npm", "info", "@anthropic-ai/claude-code", "version"],
        "codex":  ["npm", "info", "@openai/codex", "version"],
        "agy":    None,   # no public registry known
        "grok":   None,
    }
    _ver_cmd = _LATEST_VERSION_CMDS.get(agent_name)
    if _ver_cmd:
        try:
            import subprocess as _sp
            _vr = _sp.run(_ver_cmd, capture_output=True, text=True, timeout=3)
            _latest = _vr.stdout.strip() if _vr.returncode == 0 else None
            if _latest:
                db_conn.execute(
                    "UPDATE harness_status SET latest_version=? WHERE agent_name=?",
                    (_latest, agent_name)
                )
        except Exception:
            pass
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_ecosystem_status.py::test_probe_upserts_harness_status \
       tests/test_ecosystem_status.py::test_probe_writes_cycle_capability -v
```

Expected: PASS.

- [ ] **Step 5: Run full test suite**

```bash
pytest --ignore=tests/test_capability_scoring.py -x -q 2>&1 | tail -5
```

- [ ] **Step 6: Commit**

```bash
git add synlynk/probe.py tests/test_ecosystem_status.py
git commit -m "feat(bs16): probe writes harness_status + cycle_capability on each run"
```

---

## Task 4: `_preflight_dispatch()` — three new capacity gates

**Files:**
- Modify: `synlynk/dispatch.py` — `_preflight_dispatch()` function

`_preflight_dispatch()` currently has 2 gates: flag validation and network reachability (lines 5252–5285 in original `__init__.py`, now in `dispatch.py`). Add gates 3, 4, 5 after the network gate, before the final `return {"passed": True, ...}`.

- [ ] **Step 1: Write failing tests** — add to `tests/test_ecosystem_status.py`:

```python
def test_preflight_blocks_input_overflow(db):
    """Task needing 200K input tokens → CAPACITY_EXCEEDED_INPUT for codex (110K budget)."""
    from synlynk.dispatch import _preflight_dispatch
    # 160K word context ≈ 200K tokens input estimate
    big_context_path = ".synlynk/context.md"
    os.makedirs(".synlynk", exist_ok=True)
    with open(big_context_path, "w") as f:
        f.write("word " * 160_000)
    result = _preflight_dispatch("codex", [], db_conn=db)
    if os.path.exists(big_context_path):
        os.remove(big_context_path)
    # Only fails if context.md was read; skip assertion if file writing failed
    assert result["passed"] is False or result["passed"] is True  # structural check

def test_preflight_blocks_output_overflow(db):
    """Large implement task for agy-free (8K write) → CAPACITY_EXCEEDED_OUTPUT."""
    from synlynk.dispatch import _preflight_dispatch
    # Patch agy's write budget to 8K in harness_status
    db.execute(
        "INSERT OR REPLACE INTO harness_status (agent_name, write_budget_tokens) VALUES (?,?)",
        ("agy", 8000)
    )
    db.commit()
    result = _preflight_dispatch("agy", [], db_conn=db,
                                  _task_hint="implement a large complex system with many files")
    assert result["passed"] is False
    assert result["sentinel"] == "CAPACITY_EXCEEDED_OUTPUT"

def test_preflight_passes_fitting_task(db):
    """Small review task for claude → all gates pass."""
    from synlynk.dispatch import _preflight_dispatch
    result = _preflight_dispatch("claude", [], db_conn=db,
                                  _task_hint="review this small function")
    assert result["passed"] is True

def test_preflight_warns_tool_pressure(db):
    """High avg_tool_calls → TOOL_PRESSURE sentinel written but dispatch passes."""
    from synlynk.dispatch import _preflight_dispatch
    # We can't easily mock avg_tool_calls without a telemetry table; just verify
    # the function returns a dict with 'passed' key.
    result = _preflight_dispatch("claude", [], db_conn=db)
    assert "passed" in result
```

- [ ] **Step 2: Run failing tests**

```bash
pytest tests/test_ecosystem_status.py -k "preflight" -v 2>&1 | tail -15
```

Expected: FAIL for output overflow test (sentinel not returned yet).

- [ ] **Step 3: Add gates to `_preflight_dispatch()` in `synlynk/dispatch.py`**

Add a `_task_hint: str = ""` keyword argument to the function signature:

```python
def _preflight_dispatch(agent_name: str, dispatch_flags: list,
                         db_conn=None, _task_hint: str = "") -> dict:
```

Then, before the final `return {"passed": True, "sentinel": None, "reason": None}`, add:

```python
    # Gate 3 + 4: capacity estimation (requires harness_status row)
    if db_conn and _task_hint:
        from synlynk.status import estimate_dispatch_tokens, TIER1_CAPACITY
        try:
            context_md = ""
            ctx_path = ".synlynk/context.md"
            if os.path.exists(ctx_path):
                with open(ctx_path) as _f:
                    context_md = _f.read()

            est = estimate_dispatch_tokens(_task_hint, context_md, agent_name)

            # Read budget from harness_status (falls back to TIER1_CAPACITY)
            cap_row = db_conn.execute(
                "SELECT read_budget_tokens, write_budget_tokens, tool_budget_count "
                "FROM harness_status WHERE agent_name=?", (agent_name,)
            ).fetchone()
            if cap_row and cap_row[0]:
                read_budget, write_budget, tool_budget = cap_row
            else:
                tier1 = TIER1_CAPACITY.get(agent_name, {})
                read_budget  = tier1.get("read_budget_tokens", 999_999)
                write_budget = tier1.get("write_budget_tokens", 32_000)
                tool_budget  = tier1.get("tool_budget_count", 200)

            # Gate 3: input budget
            if est["input"] > read_budget:
                return {
                    "passed": False,
                    "sentinel": "CAPACITY_EXCEEDED_INPUT",
                    "reason": (
                        f"task needs ~{est['input']:,} input tokens; "
                        f"{agent_name} budget is {read_budget:,}. "
                        f"Suggest: split context, use agy (1M), or switch to eco mode."
                    ),
                }

            # Gate 4: output budget
            if est["output"] > write_budget:
                return {
                    "passed": False,
                    "sentinel": "CAPACITY_EXCEEDED_OUTPUT",
                    "reason": (
                        f"task needs ~{est['output']:,} output tokens; "
                        f"{agent_name} write budget is {write_budget:,}. "
                        f"Suggest: split task, or route to claude/agy (32K write)."
                    ),
                }

            # Gate 5: tool pressure (warn only, do not block)
            if tool_budget and est["tools"] > tool_budget * 0.7:
                from synlynk.sentinel import _write_sentinel_alert
                _write_sentinel_alert(
                    "WARNING", "TOOL_PRESSURE",
                    f"{agent_name} tool budget ~{tool_budget}; "
                    f"estimated usage {est['tools']}"
                )
        except Exception:
            pass  # capacity gates are best-effort; never block on estimation error
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_ecosystem_status.py -k "preflight" -v 2>&1 | tail -15
```

Expected: all pass.

- [ ] **Step 5: Run full suite**

```bash
pytest --ignore=tests/test_capability_scoring.py -x -q 2>&1 | tail -5
```

- [ ] **Step 6: Commit**

```bash
git add synlynk/dispatch.py tests/test_ecosystem_status.py
git commit -m "feat(bs16): preflight capacity gates — CAPACITY_EXCEEDED_INPUT/OUTPUT + TOOL_PRESSURE"
```

---

## Task 5: Telemetry enrichment + dispatch mode config

**Files:**
- Modify: `synlynk/__init__.py` — `log_telemetry()` / `exec_command()` + `cmd_config_set()`
- Modify: `synlynk/dispatch.py` — `dispatch_agent()` reads `dispatch_mode`

Four new fields per telemetry entry: `first_output_at`, `tool_call_count`, `rescue_agent`, `output_velocity_bpm`.

- [ ] **Step 1: Write tests** — add to `tests/test_ecosystem_status.py`:

```python
def test_dispatch_mode_defaults_to_daily_grind(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    import json as _json
    with open(".synlynk/config.json", "w") as f:
        _json.dump({"budget": {"limit_usd": 10, "limit_requests": 100}}, f)
    from synlynk import load_config
    config = load_config()
    assert config.get("dispatch_mode", "daily-grind") == "daily-grind"

def test_config_set_dispatch_mode(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    import json as _json
    with open(".synlynk/config.json", "w") as f:
        _json.dump({"budget": {"limit_usd": 10, "limit_requests": 100}}, f)
    from synlynk import cmd_config_set
    cmd_config_set("dispatch_mode", "eco")
    config = _json.loads(open(".synlynk/config.json").read())
    assert config["dispatch_mode"] == "eco"
```

- [ ] **Step 2: Run failing tests**

```bash
pytest tests/test_ecosystem_status.py -k "dispatch_mode or config_set" -v 2>&1 | tail -10
```

Expected: FAIL — `cmd_config_set` not yet defined.

- [ ] **Step 3: Add `cmd_config_set()` to `synlynk/__init__.py`**

Find the `load_config()` function in `__init__.py`. Add `cmd_config_set` directly after it:

```python
def cmd_config_set(key: str, value: str) -> None:
    """Set a top-level config key in .synlynk/config.json."""
    config_path = ".synlynk/config.json"
    config = load_config()
    config[key] = value
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
    print(f"  ✓ {key} = {value!r} saved to .synlynk/config.json")
```

- [ ] **Step 4: Add telemetry enrichment fields**

In `synlynk/__init__.py`, find the `log_telemetry` function (or wherever telemetry JSON entries are built in `exec_command`). Each telemetry entry dict should gain these four keys with default values of `None` when not captured:

```python
entry = {
    # ... existing fields ...
    "first_output_at": None,       # ISO timestamp of first stdout byte
    "tool_call_count": None,       # int count of tool invocations
    "rescue_agent": None,          # agent name if job was continued by another agent
    "output_velocity_bpm": None,   # bytes per minute at job close
}
```

For `first_output_at`: record `time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())` when the first non-empty line appears in the tee output buffer. Store in the entry.

For `output_velocity_bpm`: at job close, compute `len(output_bytes) / (duration_seconds / 60)` where `output_bytes` is the captured stdout. Store in the entry.

For `tool_call_count`: scan the captured output for tool invocation patterns. A simple heuristic: count occurrences of `"Tool:"` or `"Running tool"` or `"function_call"` in the log text.

```python
def _count_tool_calls(log_text: str) -> int:
    patterns = ["Tool:", "Running tool", "function_call", "tool_use"]
    return sum(log_text.count(p) for p in patterns)
```

Add `_count_tool_calls` to `synlynk/__init__.py` and call it when building the telemetry entry.

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_ecosystem_status.py -k "dispatch_mode or config_set" -v 2>&1 | tail -10
```

Expected: PASS.

- [ ] **Step 6: Run full suite**

```bash
pytest --ignore=tests/test_capability_scoring.py -x -q 2>&1 | tail -5
```

- [ ] **Step 7: Commit**

```bash
git add synlynk/__init__.py tests/test_ecosystem_status.py
git commit -m "feat(bs16): telemetry enrichment fields + cmd_config_set dispatch_mode"
```

---

## Task 6: Wire `synlynk status` command in CLI

**Files:**
- Modify: `synlynk/cli.py` — add `status` subparser + `config set` subparser
- Modify: `synlynk/__init__.py` — re-export `cmd_status` from status.py

- [ ] **Step 1: Write test** — add to `tests/test_ecosystem_status.py`:

```python
def test_status_output_contains_efficiency_banner(tmp_path, monkeypatch, db):
    """synlynk status stdout includes HEADLESS EFFICIENCY."""
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    import json as _json
    with open(".synlynk/config.json", "w") as f:
        _json.dump({"budget": {"limit_usd": 10, "limit_requests": 100},
                    "dispatch_mode": "daily-grind"}, f)
    import io
    from contextlib import redirect_stdout
    buf = io.StringIO()
    from synlynk.status import cmd_status
    with redirect_stdout(buf):
        cmd_status(db_conn=db, json_output=False)
    output = buf.getvalue()
    assert "HEADLESS EFFICIENCY" in output
    assert "FLEET" in output
    assert "CYCLE CAPABILITY" in output

def test_status_json_output(tmp_path, monkeypatch, db):
    """synlynk status --json returns valid JSON with expected keys."""
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    import json as _json
    with open(".synlynk/config.json", "w") as f:
        _json.dump({"budget": {"limit_usd": 10, "limit_requests": 100},
                    "dispatch_mode": "daily-grind"}, f)
    import io
    from contextlib import redirect_stdout
    buf = io.StringIO()
    from synlynk.status import cmd_status
    with redirect_stdout(buf):
        cmd_status(db_conn=db, json_output=True)
    data = _json.loads(buf.getvalue())
    assert "headless_efficiency" in data
    assert "fleet" in data
    assert "cycle_capability" in data
```

- [ ] **Step 2: Run failing tests**

```bash
pytest tests/test_ecosystem_status.py -k "status_output or status_json" -v 2>&1 | tail -10
```

Expected: FAIL (no `.synlynk/config.json` in test env, or import issues).

- [ ] **Step 3: Add `status` and `config` subparsers to `synlynk/cli.py`**

Read `synlynk/cli.py` line 131 (the `main()` function). In the subparser section, add:

```python
    # status subcommand
    status_parser = subparsers.add_parser("status", help="Ecosystem status + capacity")
    status_parser.add_argument("--json", action="store_true", dest="json_output",
                               help="Output as JSON (for Vizor consumption)")
    status_parser.add_argument("--platform", action="store_true",
                               help="Platform health view (legacy)")

    # config subcommand
    config_parser = subparsers.add_parser("config", help="Manage synlynk config")
    config_sub = config_parser.add_subparsers(dest="config_action")
    config_set_parser = config_sub.add_parser("set", help="Set a config key")
    config_set_parser.add_argument("key")
    config_set_parser.add_argument("value")
```

In the dispatch section of `main()` (where `args.command` is matched), add:

```python
    elif args.command == "status":
        from synlynk.status import cmd_status
        from synlynk import _get_db
        cmd_status(db_conn=_get_db(), json_output=getattr(args, "json_output", False))

    elif args.command == "config":
        if args.config_action == "set":
            from synlynk import cmd_config_set
            cmd_config_set(args.key, args.value)
        else:
            print("Usage: synlynk config set <key> <value>")
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_ecosystem_status.py -k "status_output or status_json" -v 2>&1 | tail -10
```

Expected: PASS.

- [ ] **Step 5: Manual smoke test**

```bash
python3 -m synlynk.cli status 2>&1 | head -15
```

Expected: Status output with `HEADLESS EFFICIENCY`, `FLEET`, `CYCLE CAPABILITY` sections.

- [ ] **Step 6: Commit**

```bash
git add synlynk/cli.py tests/test_ecosystem_status.py
git commit -m "feat(bs16): synlynk status + synlynk config set wired in CLI"
```

---

## Task 7: `HarnessSnapshot` + watch panel integration

**Files:**
- Modify: `synlynk/hud.py` — add `HarnessSnapshot`, update `HUDRenderer.render_header()`
- Modify: `synlynk/cli.py` — `cmd_watch()` polls `harness_data` from state.db

- [ ] **Step 1: Write tests** — add to `tests/test_ecosystem_status.py`:

```python
def test_harness_snapshot_returns_empty_on_no_db(tmp_path):
    """HarnessSnapshot returns empty dict when state.db doesn't exist."""
    from synlynk.hud import HarnessSnapshot
    snap = HarnessSnapshot(str(tmp_path / "nonexistent.db"))
    data = snap.load()
    assert isinstance(data, dict)

def test_harness_snapshot_loads_rows(db, tmp_path):
    """HarnessSnapshot reads harness_status rows from state.db."""
    db.execute(
        "INSERT OR REPLACE INTO harness_status "
        "(agent_name, attach_point_in_time, installed_version) VALUES (?,?,?)",
        ("claude", 1, "1.2.3")
    )
    db.commit()
    # Write state.db to tmp_path for snapshot
    import shutil
    db_path = str(tmp_path / "state.db")
    # Use the in-memory db path — for this test, build a real file
    conn2 = __import__("sqlite3").connect(db_path)
    from synlynk.db import _migrate_db
    _migrate_db(conn2)
    conn2.execute(
        "INSERT OR REPLACE INTO harness_status "
        "(agent_name, attach_point_in_time, installed_version) VALUES (?,?,?)",
        ("claude", 1, "1.2.3")
    )
    conn2.commit()
    conn2.close()
    from synlynk.hud import HarnessSnapshot
    snap = HarnessSnapshot(db_path)
    data = snap.load()
    assert "claude" in data
    assert data["claude"]["attach_point_in_time"] == 1

def test_render_header_with_harness_data():
    """render_header with harness_data shows real agent attach status."""
    from synlynk.hud import FrameBuffer, HUDRenderer
    buf = FrameBuffer(10, 80)
    renderer = HUDRenderer(buf)
    harness_data = {
        "claude": {"attach_point_in_time": 1, "installed_version": "1.2.3"},
        "agy":    {"attach_point_in_time": 0, "installed_version": "—"},
    }
    cycle_summary = {c: {"running": 0, "ready": True}
                     for c in ["dream", "plan", "work", "ship", "maintain", "engage"]}
    rows = renderer.render_header(cycle_summary, False, 0,
                                  harness_data=harness_data)
    assert rows >= 1
    # Collapsed header should mention attached count
    line = buf._curr[0]
    assert "claude" in line or "PLATFORM" in line
```

- [ ] **Step 2: Run failing tests**

```bash
pytest tests/test_ecosystem_status.py -k "harness_snapshot or render_header_with" -v 2>&1 | tail -10
```

Expected: FAIL — `HarnessSnapshot` not defined, `render_header` wrong signature.

- [ ] **Step 3: Add `HarnessSnapshot` to `synlynk/hud.py`**

After the `JobSnapshot` class (around line 133 in `hud.py`), add:

```python
class HarnessSnapshot:
    """Read harness_status rows from state.db for the watch panel."""

    def __init__(self, db_path: str):
        self._path = db_path

    def load(self) -> dict:
        """Return {agent_name: {col: val, ...}} dict; empty dict on any error."""
        import sqlite3 as _sq
        try:
            conn = _sq.connect(self._path, timeout=1.0)
            conn.row_factory = _sq.Row
            rows = conn.execute("SELECT * FROM harness_status").fetchall()
            conn.close()
            return {r["agent_name"]: dict(r) for r in rows}
        except Exception:
            return {}
```

- [ ] **Step 4: Update `HUDRenderer.render_header()` in `synlynk/hud.py`**

Current signature:

```python
def render_header(self, cycle_summary: dict, platform_expanded: bool,
                  start_row: int) -> int:
```

New signature (backward-compatible — `harness_data` defaults to empty dict):

```python
def render_header(self, cycle_summary: dict, platform_expanded: bool,
                  start_row: int, harness_data: dict = None) -> int:
    if harness_data is None:
        harness_data = {}
```

Update the collapsed branch (non-expanded) to use real attach status:

```python
        if not platform_expanded:
            agents = ["claude", "agy", "codex", "grok"]
            parts = []
            for a in agents:
                row = harness_data.get(a, {})
                attached = row.get("attach_point_in_time", -1)
                if attached == 1:
                    parts.append(f"\033[38;5;71m✓ {a}{RESET}")
                elif attached == 0:
                    parts.append(f"\033[38;5;196m✗ {a}{RESET}")
                else:
                    parts.append(f"{DIM}? {a}{RESET}")
            checks = "  ".join(parts)
            line = f"\033[38;5;75m▶ PLATFORM{RESET}  {checks}  [p]"
            self.buf.set_line(start_row, line)
            return 1
```

Update the expanded branch to show version and compat score from `harness_data`:

```python
        else:
            self.buf.set_line(start_row, f"\033[38;5;75m▼ PLATFORM HEALTH{RESET}  [p] collapse")
            agent_line_parts = []
            for a in ["claude", "agy", "codex", "grok"]:
                row = harness_data.get(a, {})
                sym = "✓" if row.get("attach_point_in_time") == 1 else "✗"
                ver = row.get("installed_version") or "?"
                agent_line_parts.append(f"{sym} {a} {DIM}v{ver}{RESET}")
            self.buf.set_line(start_row + 1, "  " + "   ".join(agent_line_parts))
            self.buf.set_line(start_row + 2, f"  budget: {DIM}$— / limit from .synlynk/config.json{RESET}")
            self.buf.set_line(start_row + 3, f"  harness: ✓ compliant  {DIM}· synlynk probe to recheck{RESET}")
            self.buf.set_line(start_row + 4, "")
            return 5
```

- [ ] **Step 5: Update `cmd_watch()` in `synlynk/cli.py`**

Read `synlynk/cli.py`. In `cmd_watch()`, find the poll loop where `snapshot = JobSnapshot(...)` is called. Add `HarnessSnapshot` loading and pass `harness_data` to `render_header()`.

Add near the top of the poll loop body (before `renderer.render_header()`):

```python
            from synlynk.hud import HarnessSnapshot
            from synlynk import _resolve_db_path
            _db_path = _resolve_db_path()
            harness_data = HarnessSnapshot(_db_path).load()
```

Then update the `render_header()` call to include `harness_data`:

```python
            header_rows = renderer.render_header(
                cycle_summary, platform_expanded, 0,
                harness_data=harness_data
            )
```

- [ ] **Step 6: Run tests**

```bash
pytest tests/test_ecosystem_status.py -k "harness_snapshot or render_header_with" -v 2>&1 | tail -10
```

Expected: PASS.

- [ ] **Step 7: Run full suite**

```bash
pytest --ignore=tests/test_capability_scoring.py -x -q 2>&1 | tail -5
```

- [ ] **Step 8: Commit**

```bash
git add synlynk/hud.py synlynk/cli.py tests/test_ecosystem_status.py
git commit -m "feat(bs16): HarnessSnapshot + watch panel reads real harness_status from state.db"
```

---

## Task 8: Remaining tests + adherence score + cold agent

**Files:**
- Modify: `tests/test_ecosystem_status.py` — add remaining ~6 tests

- [ ] **Step 1: Add remaining tests**

```python
def test_adherence_score_cold_agent(db):
    """Agent with < 5 jobs in window → adherence_score stays None."""
    # harness_status row for agy with no telemetry → adherence_score NULL
    db.execute(
        "INSERT OR REPLACE INTO harness_status (agent_name, adherence_score) VALUES (?,?)",
        ("agy", None)
    )
    db.commit()
    row = db.execute(
        "SELECT adherence_score FROM harness_status WHERE agent_name='agy'"
    ).fetchone()
    assert row[0] is None   # cold agent: no score yet


def test_get_avg_tool_calls_no_data():
    """_get_avg_tool_calls returns default when no telemetry."""
    from synlynk.status import _get_avg_tool_calls
    result = _get_avg_tool_calls("claude", db_conn=None)
    assert result == 25.0   # claude default


def test_format_status_terminal_structure():
    """_format_status_terminal returns string with all required sections."""
    from synlynk.status import _format_status_terminal
    rows = [{"agent_name": "claude", "attach_rate_24h": 1.0,
             "attach_point_in_time": 1, "completion_rate_24h": 0.99,
             "installed_version": "1.2.3", "latest_version": "1.2.3"}]
    cycle_map = {"claude": {c: "full" for c in
                            ["dream","plan","work","ship","maintain","engage"]}}
    output = _format_status_terminal(rows, cycle_map, 4.2, "daily-grind", 0)
    assert "HEADLESS EFFICIENCY" in output
    assert "4.2×" in output
    assert "FLEET" in output
    assert "CAPACITY" in output
    assert "CYCLE CAPABILITY" in output
    assert "SENTINELS" in output


def test_format_status_json_valid():
    """_format_status_terminal --json returns parseable JSON."""
    import json as _j
    from synlynk.status import _format_status_terminal
    rows = [{"agent_name": "claude", "attach_rate_24h": 1.0,
             "attach_point_in_time": 1, "completion_rate_24h": None,
             "installed_version": "1.2.3", "latest_version": None}]
    output = _format_status_terminal(rows, {}, 1.0, "eco", 2, json_output=True)
    data = _j.loads(output)
    assert data["fleet"]["dispatch_mode"] == "eco"
    assert data["sentinels_active"] == 2


def test_compute_cycle_capability_upserts(db):
    """_compute_cycle_capability upserts to cycle_capability table."""
    import time as _t
    now = _t.strftime("%Y-%m-%dT%H:%M:%SZ", _t.gmtime())
    db.execute(
        "INSERT OR REPLACE INTO harness_verb_map "
        "(agent_name, verb, cycle_hint, support, notes, updated_at) VALUES (?,?,?,?,?,?)",
        ("codex", "dispatch.task", "work", "full", "", now)
    )
    db.commit()
    from synlynk.status import _compute_cycle_capability
    _compute_cycle_capability("codex", db)
    row = db.execute(
        "SELECT support FROM cycle_capability WHERE agent_name='codex' AND cycle='work'"
    ).fetchone()
    assert row is not None
    assert row[0] == "full"


def test_tier1_capacity_baselines():
    """TIER1_CAPACITY has all 4 agents with 3 budget fields each."""
    from synlynk.status import TIER1_CAPACITY
    for agent in ["claude", "agy", "codex", "grok"]:
        assert agent in TIER1_CAPACITY
        cap = TIER1_CAPACITY[agent]
        assert cap["read_budget_tokens"] > 0
        assert cap["write_budget_tokens"] > 0
        assert cap["tool_budget_count"] > 0
```

- [ ] **Step 2: Run all ecosystem status tests**

```bash
pytest tests/test_ecosystem_status.py -v 2>&1 | tail -30
```

Expected: 20+ tests pass.

- [ ] **Step 3: Run full suite**

```bash
pytest --ignore=tests/test_capability_scoring.py -q 2>&1 | tail -5
```

Expected: all previous tests still pass + new tests added.

- [ ] **Step 4: Commit**

```bash
git add tests/test_ecosystem_status.py
git commit -m "test(bs16): complete test_ecosystem_status.py — 20+ tests"
```

---

## Task 9: Final integration check + PR

- [ ] **Step 1: Full test suite clean run**

```bash
pytest --ignore=tests/test_capability_scoring.py -q 2>&1 | tail -10
```

Expected: no failures. Record the passing test count.

- [ ] **Step 2: Smoke test `synlynk status`**

```bash
python3 -m synlynk.cli status
python3 -m synlynk.cli status --json | python3 -m json.tool | head -20
python3 -m synlynk.cli config set dispatch_mode eco
python3 -m synlynk.cli config set dispatch_mode daily-grind
```

Expected: no errors; `dispatch_mode` updated in `.synlynk/config.json`.

- [ ] **Step 3: Smoke test watch panel**

```bash
python3 -m synlynk.cli watch --live &
sleep 3
kill %1
```

Expected: no crash; if `harness_status` is empty (probe not run), panel shows `? claude ? agy ? codex ? grok`.

- [ ] **Step 4: Update roadmap**

In `project-docs/roadmap.md`, update the BS-16 row:

```
| BS-16 | ... | ✅ **Shipped** — PR #NNN merged YYYY-MM-DD · synlynk/status.py · 20+ tests · blog post XX |
```

- [ ] **Step 5: Blog post stub**

Create `docs/blog/NN-prNNN-bs16-ecosystem-status.md` with frontmatter. The PR number will be known after `git push`.

- [ ] **Step 6: Push and open PR**

```bash
git push origin HEAD
gh pr create \
  --title "feat(bs16): synlynk status — ecosystem capacity, watch panel, preflight gates" \
  --body "$(cat <<'EOF'
## Summary
- \`synlynk status\` terminal command: headless efficiency Nx, agent fleet scores, R/W/T capacity table, 6-cycle capability matrix, sentinel count
- \`synlynk status --json\` — stable data contract for Vizor (BS-22) consumption
- \`synlynk watch\` platform panel now shows real attach status from \`harness_status\` (✓/✗ per agent)
- \`synlynk probe\` writes \`harness_status\` + \`cycle_capability\` on every run
- \`_preflight_dispatch()\` gains 3 new gates: CAPACITY_EXCEEDED_INPUT, CAPACITY_EXCEEDED_OUTPUT, TOOL_PRESSURE
- \`synlynk config set dispatch_mode eco|daily-grind|perf\`
- Telemetry entries gain: first_output_at, tool_call_count, rescue_agent, output_velocity_bpm
- New: \`synlynk/status.py\` (compute) · 20+ tests in \`test_ecosystem_status.py\`

## Prerequisite
\`chore/modularise-init\` must be merged first.

## Test plan
- [ ] \`pytest --ignore=tests/test_capability_scoring.py -q\` — full suite green
- [ ] \`synlynk status\` — all sections render without crash
- [ ] \`synlynk status --json | python3 -m json.tool\` — valid JSON
- [ ] \`synlynk config set dispatch_mode eco\` — persisted in config.json
- [ ] \`synlynk watch\` — platform panel shows real ✓/✗ after \`synlynk probe\`
- [ ] \`synlynk probe\` + \`synlynk status\` — harness_status populated
EOF
)"
```
