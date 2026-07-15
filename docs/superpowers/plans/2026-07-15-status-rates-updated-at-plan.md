# synlynk status: Surface rates_updated_at Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `synlynk status` (terminal and `--json`) surface `rates_updated_at` from `.synlynk/model_rates.json`, so a stale or never-updated rate table is visible instead of silent — closing epic #210's final remaining scope.

**Architecture:** `synlynk/status.py`'s `cmd_status()` calls the existing `synlynk.costs._load_model_rates()` loader once and threads the resulting `rates_updated_at` value through a new keyword parameter on `_format_status_terminal()`, which renders it as a `RATES` line in terminal output and a top-level key in JSON output.

**Tech Stack:** Python 3, sqlite3, pytest. No new dependencies.

---

### Task 1: Surface rates_updated_at in cmd_status and _format_status_terminal

**Files:**
- Modify: `synlynk/status.py:282-372`
- Test: `tests/test_ecosystem_status.py`

- [ ] **Step 1: Write the failing terminal-output test (date present)**

Add to `tests/test_ecosystem_status.py`, immediately after the existing `test_format_status_terminal_structure` function (around line 161):

```python
def test_format_status_terminal_shows_rates_updated_date():
    from synlynk.status import _format_status_terminal

    rows = [{"agent_name": "claude", "attach_rate_24h": 1.0, "attach_point_in_time": 1, "completion_rate_24h": 0.99, "installed_version": "1.2.3", "latest_version": "1.2.3"}]
    cycle_map = {"claude": {c: "full" for c in ["dream", "plan", "work", "ship", "maintain", "engage"]}}
    output = _format_status_terminal(rows, cycle_map, 4.2, "daily-grind", 0, rates_updated_at="2026-07-13")
    assert "RATES   updated 2026-07-13" in output
```

- [ ] **Step 2: Write the failing terminal-output test (no date, warning path)**

Add immediately after Step 1's test:

```python
def test_format_status_terminal_shows_rates_never_updated_warning():
    from synlynk.status import _format_status_terminal

    rows = [{"agent_name": "claude", "attach_rate_24h": 1.0, "attach_point_in_time": 1, "completion_rate_24h": 0.99, "installed_version": "1.2.3", "latest_version": "1.2.3"}]
    cycle_map = {"claude": {c: "full" for c in ["dream", "plan", "work", "ship", "maintain", "engage"]}}
    output = _format_status_terminal(rows, cycle_map, 4.2, "daily-grind", 0)
    assert "RATES   never updated ⚠ (hardcoded defaults)" in output
```

- [ ] **Step 3: Write the failing JSON-output test**

Add immediately after the existing `test_format_status_json_valid` function (around line 174):

```python
def test_format_status_json_includes_rates_updated_at():
    from synlynk.status import _format_status_terminal
    import json

    rows = [{"agent_name": "claude", "attach_rate_24h": 1.0, "attach_point_in_time": 1, "completion_rate_24h": None, "installed_version": "1.2.3", "latest_version": None}]
    output = _format_status_terminal(rows, {}, 1.0, "eco", 2, json_output=True, rates_updated_at="2026-07-13")
    data = json.loads(output)
    assert data["rates_updated_at"] == "2026-07-13"
```

- [ ] **Step 4: Write the failing cmd_status integration tests**

Add immediately after the existing `test_cmd_status_json_output` function (around line 208):

```python
def test_cmd_status_json_output_reads_rates_from_file(tmp_path, monkeypatch, db):
    from synlynk.status import cmd_status

    monkeypatch.chdir(tmp_path)
    _write_config(tmp_path)
    os.makedirs(tmp_path / ".synlynk", exist_ok=True)
    (tmp_path / ".synlynk" / "model_rates.json").write_text(
        _json.dumps({
            "rates_updated_at": "2026-07-13",
            "unit": "usd_per_1k_tokens",
            "models": {},
            "default": {"input": 0.003, "output": 0.015, "cache_read": 0.0000003},
            "billing_mode": {"default": "subscription", "local": "actual"},
        })
    )
    db.execute(
        "INSERT OR REPLACE INTO harness_status (agent_name, attach_point_in_time, installed_version) VALUES (?,?,?)",
        ("claude", 1, "1.2.3"),
    )
    db.commit()
    buf = io.StringIO()
    with redirect_stdout(buf):
        cmd_status(db_conn=db, json_output=True)
    data = json.loads(buf.getvalue())
    assert data["rates_updated_at"] == "2026-07-13"


def test_cmd_status_json_output_rates_null_when_no_file(tmp_path, monkeypatch, db):
    from synlynk.status import cmd_status

    monkeypatch.chdir(tmp_path)
    _write_config(tmp_path)
    db.execute(
        "INSERT OR REPLACE INTO harness_status (agent_name, attach_point_in_time, installed_version) VALUES (?,?,?)",
        ("claude", 1, "1.2.3"),
    )
    db.commit()
    buf = io.StringIO()
    with redirect_stdout(buf):
        cmd_status(db_conn=db, json_output=True)
    data = json.loads(buf.getvalue())
    assert data["rates_updated_at"] is None
```

- [ ] **Step 5: Run the new tests to verify they fail**

Run: `python3 -m pytest tests/test_ecosystem_status.py -k "rates" -v`

Expected: 5 FAILED — `_format_status_terminal() got an unexpected keyword argument 'rates_updated_at'` for the first three, and `KeyError: 'rates_updated_at'` for the last two (since `cmd_status`/`_format_status_terminal` don't produce that key yet).

- [ ] **Step 6: Add the `_format_rates_line` helper and extend `_format_status_terminal`'s signature**

In `synlynk/status.py`, the current function starts at line 282:

```python
def _format_status_terminal(
    harness_rows: list,
    cycle_map: dict,
    efficiency_ratio: float,
    dispatch_mode: str,
    sentinels_active: int,
    json_output: bool = False,
) -> str:
```

Replace with:

```python
def _format_rates_line(rates_updated_at: Optional[str]) -> str:
    if rates_updated_at:
        return f"RATES   updated {rates_updated_at}"
    return "RATES   never updated ⚠ (hardcoded defaults)"


def _format_status_terminal(
    harness_rows: list,
    cycle_map: dict,
    efficiency_ratio: float,
    dispatch_mode: str,
    sentinels_active: int,
    json_output: bool = False,
    rates_updated_at: Optional[str] = None,
) -> str:
```

`Optional` is already imported at the top of `synlynk/status.py` (line 9: `from typing import Any, Optional`) — no new import needed.

- [ ] **Step 7: Add `rates_updated_at` to the JSON payload**

In the same function, the `if json_output:` block currently reads (around line 294-307):

```python
    if json_output:
        payload = {
            "headless_efficiency": efficiency_ratio,
            "fleet": {
                "attached": attached,
                "total": len(agents),
                "dispatch_mode": dispatch_mode,
            },
            "agents": {r["agent_name"]: r for r in harness_rows},
            "cycle_capability": cycle_map,
            "capacity": TIER1_CAPACITY,
            "sentinels_active": sentinels_active,
        }
        return json.dumps(payload, indent=2)
```

Add one key to `payload`:

```python
    if json_output:
        payload = {
            "headless_efficiency": efficiency_ratio,
            "fleet": {
                "attached": attached,
                "total": len(agents),
                "dispatch_mode": dispatch_mode,
            },
            "agents": {r["agent_name"]: r for r in harness_rows},
            "cycle_capability": cycle_map,
            "capacity": TIER1_CAPACITY,
            "sentinels_active": sentinels_active,
            "rates_updated_at": rates_updated_at,
        }
        return json.dumps(payload, indent=2)
```

- [ ] **Step 8: Insert the RATES line into terminal output**

In the same function, the `lines` list currently reads (around line 311-321):

```python
    lines = [
        f"SYNLYNK ECOSYSTEM STATUS  {ts}",
        "━" * 44,
        "",
        f"HEADLESS EFFICIENCY  {efficiency_ratio}×   headless dispatch baseline",
        "",
        f"FLEET   {attached}/{len(agents)} attached   mode: {dispatch_mode}",
        "BUDGET  limit tracked via .synlynk/config.json",
        "",
        f"{'AGENT SCORE':<14} {'ATTACH':>8}  {'COMPLETE':>9}  {'VERSION':>10}",
    ]
```

Insert one line after `"BUDGET  limit tracked via .synlynk/config.json"`:

```python
    lines = [
        f"SYNLYNK ECOSYSTEM STATUS  {ts}",
        "━" * 44,
        "",
        f"HEADLESS EFFICIENCY  {efficiency_ratio}×   headless dispatch baseline",
        "",
        f"FLEET   {attached}/{len(agents)} attached   mode: {dispatch_mode}",
        "BUDGET  limit tracked via .synlynk/config.json",
        _format_rates_line(rates_updated_at),
        "",
        f"{'AGENT SCORE':<14} {'ATTACH':>8}  {'COMPLETE':>9}  {'VERSION':>10}",
    ]
```

- [ ] **Step 9: Wire `cmd_status()` to load rates and pass them through**

`cmd_status()` currently reads (around line 350-372):

```python
def cmd_status(db_conn=None, json_output: bool = False) -> str:
    """Print ecosystem status for the current workspace."""
    from synlynk import _get_db, _read_sentinel_alerts, load_config

    if db_conn is None:
        db_conn = _get_db()

    config = load_config()
    dispatch_mode = config.get("dispatch_mode", "daily-grind")
    harness_rows = _load_harness_status_rows(db_conn)
    cycle_map = _load_cycle_capability_rows(db_conn)
    efficiency = _headless_efficiency_ratio(_load_exec_jobs_from_telemetry())
    sentinels_active = len(_read_sentinel_alerts())
    output = _format_status_terminal(
        harness_rows,
        cycle_map,
        efficiency,
        dispatch_mode,
        sentinels_active,
        json_output=json_output,
    )
    print(output)
```

Replace with:

```python
def cmd_status(db_conn=None, json_output: bool = False) -> str:
    """Print ecosystem status for the current workspace."""
    from synlynk import _get_db, _read_sentinel_alerts, load_config
    from synlynk.costs import _load_model_rates

    if db_conn is None:
        db_conn = _get_db()

    config = load_config()
    dispatch_mode = config.get("dispatch_mode", "daily-grind")
    harness_rows = _load_harness_status_rows(db_conn)
    cycle_map = _load_cycle_capability_rows(db_conn)
    efficiency = _headless_efficiency_ratio(_load_exec_jobs_from_telemetry())
    sentinels_active = len(_read_sentinel_alerts())
    rates_updated_at = _load_model_rates().get("rates_updated_at")
    output = _format_status_terminal(
        harness_rows,
        cycle_map,
        efficiency,
        dispatch_mode,
        sentinels_active,
        json_output=json_output,
        rates_updated_at=rates_updated_at,
    )
    print(output)
```

- [ ] **Step 10: Run the new tests to verify they pass**

Run: `python3 -m pytest tests/test_ecosystem_status.py -k "rates" -v`

Expected: 5 PASSED.

- [ ] **Step 11: Run the full ecosystem status and cost ledger test files to check for regressions**

Run: `python3 -m pytest tests/test_ecosystem_status.py tests/test_status.py tests/test_cost_ledger.py -v`

Expected: all PASSED, 0 failures. (The two pre-existing tests `test_format_status_terminal_structure` and `test_format_status_json_valid` call `_format_status_terminal` without the new `rates_updated_at` kwarg — they must still pass since it defaults to `None`.)

- [ ] **Step 12: Commit**

```bash
git add synlynk/status.py tests/test_ecosystem_status.py
git commit -m "feat(status): surface rates_updated_at in terminal and JSON output"
```

---

### Task 2: Final regression and review — Claude, not dispatched

This task is performed directly by Claude (PM/reviewer role), not dispatched to an agent — it is a verification pass over Task 1's dispatched output, mirroring the precedent set in PR #258's Task 3.

- [ ] **Step 1: Run the full relevant test suite**

Run: `python3 -m pytest tests/test_ecosystem_status.py tests/test_status.py tests/test_cost_ledger.py -v`

Expected: all PASSED, 0 failures.

- [ ] **Step 2: Run the full project test suite to catch any file-outside-scope regression**

Run: `python3 -m pytest tests/ -q`

Expected: same pass/skip counts as the pre-Task-1 baseline (1135 passed, 2 skipped, per the baseline captured when this worktree was created from `main` at commit `c25cbc2`) — i.e. zero new failures anywhere in the suite, not just the two files touched. This step exists because PR #258 shipped a regression in a file neither task's dispatch touched (`tests/test_vizor_efficiency.py`'s own separate `make_test_db()` fixture) that only surfaced when the *full* suite ran; running the full suite here catches that class of gap for #259 as well.

- [ ] **Step 3: Manual smoke test of terminal and JSON output**

Run this inline Python script to confirm both output modes render the new line/key with a real (non-mocked) `_load_model_rates()` call:

```bash
python3 -c "
import io, json, os, tempfile
from contextlib import redirect_stdout

tmp = tempfile.mkdtemp()
os.chdir(tmp)
os.makedirs('.synlynk', exist_ok=True)
with open('.synlynk/config.json', 'w') as f:
    json.dump({'budget': {'limit_usd': 10, 'limit_requests': 100}, 'dispatch_mode': 'daily-grind'}, f)

import sqlite3
from synlynk.db import _migrate_db
conn = sqlite3.connect(':memory:')
_migrate_db(conn)

from synlynk.status import cmd_status

buf = io.StringIO()
with redirect_stdout(buf):
    cmd_status(db_conn=conn, json_output=False)
terminal_out = buf.getvalue()
assert 'RATES   never updated' in terminal_out, terminal_out
print('terminal OK')

buf2 = io.StringIO()
with redirect_stdout(buf2):
    cmd_status(db_conn=conn, json_output=True)
data = json.loads(buf2.getvalue())
assert data['rates_updated_at'] is None
print('json OK')
"
```

Expected output: `terminal OK` then `json OK`, no traceback.

- [ ] **Step 4: Grep audit for other direct callers of `_format_status_terminal`**

Run: `grep -rn "_format_status_terminal(" synlynk/ tests/`

Expected: only the definition site, the one call site inside `cmd_status()`, and the test call sites already covered in Task 1 — confirming no other caller needs updating for the new parameter.
