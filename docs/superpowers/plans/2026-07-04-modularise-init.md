# `__init__.py` Modularisation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract upgrade, sentinel, probe, and dispatch logic from `synlynk/__init__.py` (11,268L) into four dedicated modules, reducing the monolith to ~5,000L and making BS-16 reviewable.

**Architecture:** Create `synlynk/_constants.py` for shared data, then extract one module at a time (`upgrade.py`, `sentinel.py`, `probe.py`, `dispatch.py`). Each module imports from `_constants` and stdlib only — no cross-module imports except sentinel ← probe ← dispatch (one direction). `__init__.py` re-exports everything via `from synlynk.X import *`-style lines so all existing `from synlynk import Y` test imports continue to work unchanged.

**Tech Stack:** Python 3 stdlib only. No new dependencies.

---

## File Map

| File | Action | Contents after |
|---|---|---|
| `synlynk/_constants.py` | Create | `VERSION`, `QUOTA_PATTERNS`, `AGENT_CAPABILITY_BASELINES`, `_INSTALL_SCRIPT_URL` |
| `synlynk/upgrade.py` | Create | `_detect_install_type`, `_ver_tuple`, `_run_upgrade`, `_get_pipx_source`, `_warn_stale_script_install`, `upgrade` |
| `synlynk/sentinel.py` | Create | `_write_sentinel_alert`, `_read_sentinel_alerts`, `_check_costs_freshness`, `_extract_compliance_tags`, `_extract_auto_signals`, `check_sentinel_patterns`, `sentinel_list`, `sentinel_clear`, `log_telemetry_event` |
| `synlynk/probe.py` | Create | `_compute_capability_hash`, `_scan_command_palette`, `_build_fence_content`, `_upsert_harness_fence`, `_write_scan_fences`, `_build_fence_body_from_record`, `_probe_agent`, `_run_tc1`, `_run_tc2`, `_run_tc3`, `_run_tc4`, `cmd_probe`, `_fence_exists`, `_probe_model_version` |
| `synlynk/dispatch.py` | Create | `_spawn_with_pty_fallback`, `_is_interactive`, `_inject_grok_rules`, `_tee_process`, `_check_pre_exec_gate`, `_format_prompt_for_agent`, `_warn_context_size`, `_check_job_stall`, `_job_summary_path`, `_format_job_summary`, `_write_job_summary`, `_preflight_dispatch`, `dispatch_agent`, `exec_command` |
| `synlynk/__init__.py` | Modify | Remove moved functions; add re-export block at top |
| `tests/test_modularise.py` | Create | Import verification tests |

---

## Task 1: Extract `synlynk/_constants.py`

**Files:**
- Create: `synlynk/_constants.py`
- Modify: `synlynk/__init__.py` (lines 15, 1480, 7774, 11029)

- [ ] **Step 1: Verify the baseline test suite passes before touching anything**

```bash
cd /path/to/synlynk
pytest --ignore=tests/test_capability_scoring.py -x -q 2>&1 | tail -5
```

Expected: all tests pass (791 at last count).

- [ ] **Step 2: Create `synlynk/_constants.py`**

```python
"""Shared constants used across synlynk modules."""

VERSION = "0.10.0"

_INSTALL_SCRIPT_URL = (
    "https://raw.githubusercontent.com/nikhilsoman/synlynk/main/install.sh"
)

QUOTA_PATTERNS = [
    "rate limit",
    "quota exceeded",
    "too many requests",
    "429",
    "you've reached your limit",
    "usage limit reached",
    "context window",
]

AGENT_CAPABILITY_BASELINES: dict = {}  # populated below — copy verbatim from __init__.py L1480
```

Copy `AGENT_CAPABILITY_BASELINES` dict verbatim from `synlynk/__init__.py` starting at line 1480. Copy `_INSTALL_SCRIPT_URL` from line 11029. Copy `QUOTA_PATTERNS` from line 7774.

- [ ] **Step 3: Update `__init__.py` — replace the constant definitions with imports**

At line 15 in `__init__.py`, replace:

```python
VERSION = "0.10.0"
```

with:

```python
from synlynk._constants import (
    VERSION,
    _INSTALL_SCRIPT_URL,
    QUOTA_PATTERNS,
    AGENT_CAPABILITY_BASELINES,
)
```

Then delete the original `AGENT_CAPABILITY_BASELINES` dict block (L1480–~1630), `QUOTA_PATTERNS` list (L7774–7796), and `_INSTALL_SCRIPT_URL` string (L11029–11032) from `__init__.py`. The constants are now only in `_constants.py`.

- [ ] **Step 4: Run tests**

```bash
pytest --ignore=tests/test_capability_scoring.py -x -q 2>&1 | tail -10
```

Expected: same pass count as Step 1. Fix any `NameError` for missing constants — they should now resolve via the import.

- [ ] **Step 5: Commit**

```bash
git add synlynk/_constants.py synlynk/__init__.py
git commit -m "refactor: extract shared constants → synlynk/_constants.py"
```

---

## Task 2: Extract `synlynk/upgrade.py`

**Files:**
- Create: `synlynk/upgrade.py`
- Modify: `synlynk/__init__.py`
- Test: `tests/test_upgrade.py` (already exists — runs these functions)

The upgrade functions live at `__init__.py` lines 11034–11168. They depend only on stdlib (`os`, `subprocess`, `json`, `urllib.request`) and the constants (`VERSION`, `_INSTALL_SCRIPT_URL`).

- [ ] **Step 1: Create `synlynk/upgrade.py`**

```python
"""synlynk upgrade: install-type detection and version upgrade logic."""

import os
import subprocess
import json
import urllib.request

from synlynk._constants import VERSION, _INSTALL_SCRIPT_URL


def _detect_install_type() -> str:
    ...  # copy verbatim from __init__.py L11034


def _ver_tuple(v: str) -> tuple:
    ...  # copy verbatim from __init__.py L11056


def _get_pipx_source() -> str:
    ...  # copy verbatim from __init__.py L11104


def _run_upgrade(latest: str) -> None:
    ...  # copy verbatim from __init__.py L11063


def _warn_stale_script_install() -> None:
    ...  # copy verbatim from __init__.py L11118


def upgrade() -> None:
    ...  # copy verbatim from __init__.py L11134
```

Copy each function body **verbatim** from `__init__.py`. The functions reference `VERSION` and `_INSTALL_SCRIPT_URL` — these are imported from `_constants` above.

- [ ] **Step 2: Add re-export to `__init__.py` and remove originals**

Add near the top of `__init__.py` (after the existing `from synlynk._constants import ...` line):

```python
from synlynk.upgrade import (
    _detect_install_type,
    _ver_tuple,
    _get_pipx_source,
    _run_upgrade,
    _warn_stale_script_install,
    upgrade,
)
```

Then delete the function bodies from `__init__.py` lines 11034–11168.

- [ ] **Step 3: Run upgrade tests**

```bash
pytest tests/test_upgrade.py -v 2>&1 | tail -20
```

Expected: all upgrade tests pass.

- [ ] **Step 4: Run full suite**

```bash
pytest --ignore=tests/test_capability_scoring.py -x -q 2>&1 | tail -5
```

Expected: same pass count as Task 1 Step 4.

- [ ] **Step 5: Commit**

```bash
git add synlynk/upgrade.py synlynk/__init__.py
git commit -m "refactor: extract upgrade logic → synlynk/upgrade.py"
```

---

## Task 3: Extract `synlynk/sentinel.py`

**Files:**
- Create: `synlynk/sentinel.py`
- Modify: `synlynk/__init__.py`

Sentinel functions live at `__init__.py` lines 7492–7928. They depend on stdlib and `QUOTA_PATTERNS`.

**Do NOT move** `check_daemon_health` (L7880) or `check_stall` (L7893) — they reference `WatchDaemon` which stays in `__init__.py`.

- [ ] **Step 1: Create `synlynk/sentinel.py`**

```python
"""synlynk sentinel: alert writing, pattern detection, telemetry events."""

import os
import json
import time
import re
from typing import Optional

from synlynk._constants import QUOTA_PATTERNS


def log_telemetry_event(event: dict) -> None:
    ...  # copy verbatim from __init__.py L7492


def _check_costs_freshness() -> None:
    ...  # copy verbatim from __init__.py L7510


def _write_sentinel_alert(severity: str, code: str, message: str,
                           sentinel_path: Optional[str] = None) -> None:
    ...  # copy verbatim from __init__.py L7518


def _read_sentinel_alerts(severity: Optional[str] = None) -> list:
    ...  # copy verbatim from __init__.py L7539


def _extract_compliance_tags(output_text: str) -> dict:
    ...  # copy verbatim from __init__.py L7781


def _extract_auto_signals(log_text: str, started_at: str = None,
                           ended_at: str = None, exit_code: int = None) -> dict:
    ...  # copy verbatim from __init__.py L7638


def check_sentinel_patterns(output_text: str = "", exit_code: int = 0,
                             cmd: str = "") -> None:
    ...  # copy verbatim from __init__.py L7811
    # NOTE: this function calls _write_sentinel_alert (local) and
    # _extract_compliance_tags (local) — both defined above, no import needed.


def sentinel_list() -> None:
    ...  # copy verbatim from __init__.py L7917


def sentinel_clear(severity: Optional[str] = None, code: Optional[str] = None) -> None:
    ...  # copy verbatim from __init__.py L7928
```

- [ ] **Step 2: Add re-export to `__init__.py` and remove originals**

Add to `__init__.py` re-export block:

```python
from synlynk.sentinel import (
    log_telemetry_event,
    _check_costs_freshness,
    _write_sentinel_alert,
    _read_sentinel_alerts,
    _extract_compliance_tags,
    _extract_auto_signals,
    check_sentinel_patterns,
    sentinel_list,
    sentinel_clear,
)
```

Delete the function bodies from `__init__.py` (L7492–7510, L7518–7538, L7539–7558, L7781–7810, L7638–7688, L7811–7878, L7917–7928, L7928–7963). **Keep** `check_daemon_health` (L7880) and `check_stall` (L7893) in `__init__.py`.

- [ ] **Step 3: Run full suite**

```bash
pytest --ignore=tests/test_capability_scoring.py -x -q 2>&1 | tail -5
```

Expected: same pass count. Fix any `NameError` — sentinel functions calling each other must reference local (same-module) names, not `synlynk.*`.

- [ ] **Step 4: Commit**

```bash
git add synlynk/sentinel.py synlynk/__init__.py
git commit -m "refactor: extract sentinel + telemetry → synlynk/sentinel.py"
```

---

## Task 4: Extract `synlynk/probe.py`

**Files:**
- Create: `synlynk/probe.py`
- Modify: `synlynk/__init__.py`
- Test: `tests/test_harness_compatibility.py`

Probe functions live at `__init__.py` lines 750–1205 and 1827–1899. They depend on `AGENT_CAPABILITY_BASELINES`, sentinel functions, and stdlib.

- [ ] **Step 1: Create `synlynk/probe.py`**

```python
"""synlynk probe: agent capability probing, fence management, TC compliance."""

import os
import json
import subprocess
import hashlib
import time
import re
from typing import Optional

from synlynk._constants import AGENT_CAPABILITY_BASELINES
from synlynk.sentinel import _write_sentinel_alert


def _compute_capability_hash(headless_contract: dict, dispatch_flags) -> str:
    ...  # copy verbatim from __init__.py L750


def _scan_command_palette(agent_name: str, harness_name: str,
                           cli_version: str, db_conn) -> list:
    ...  # copy verbatim from __init__.py L761


def _build_fence_content(harness_version: str, body: str) -> str:
    ...  # copy verbatim from __init__.py L824


def _upsert_harness_fence(file_path: str, harness_version: str, body: str) -> None:
    ...  # copy verbatim from __init__.py L834


def _write_scan_fences(results: dict, root: str = ".") -> list:
    ...  # copy verbatim from __init__.py L853


def _build_fence_body_from_record(agent_name: str, db_conn=None) -> str:
    ...  # copy verbatim from __init__.py L950


def _probe_agent(agent_name: str, db_conn, fast_path_ok: bool = True) -> dict:
    ...  # copy verbatim from __init__.py L992


def _run_tc1(agent_name: str, timeout: int = 5) -> dict:
    ...  # copy verbatim from __init__.py L1102


def _run_tc2(agent_name: str, flags_spec: dict) -> dict:
    ...  # copy verbatim from __init__.py L1136


def _run_tc3(endpoints: list) -> dict:
    ...  # copy verbatim from __init__.py L1157


def _run_tc4(agent_name: str, db_conn) -> dict:
    ...  # copy verbatim from __init__.py L1172


def _fence_exists(file_path: str) -> bool:
    ...  # copy verbatim from __init__.py L1206


def cmd_probe(agent: str = None) -> None:
    ...  # copy verbatim from __init__.py L1194


def _probe_model_version(agent_name: str, cli: str) -> str:
    ...  # copy verbatim from __init__.py L1827
```

**Important:** `_probe_agent` calls `_write_sentinel_alert` (imported from sentinel), `_compute_capability_hash`, `_scan_command_palette`, `_build_fence_body_from_record`, `_upsert_harness_fence` (all local). `cmd_probe` calls `_probe_agent` and `_run_tc1`–`_run_tc4` (all local). Ensure no remaining references to `synlynk._write_sentinel_alert` — use the local import.

- [ ] **Step 2: Add re-export to `__init__.py` and remove originals**

```python
from synlynk.probe import (
    _compute_capability_hash,
    _scan_command_palette,
    _build_fence_content,
    _upsert_harness_fence,
    _write_scan_fences,
    _build_fence_body_from_record,
    _probe_agent,
    _run_tc1,
    _run_tc2,
    _run_tc3,
    _run_tc4,
    _fence_exists,
    cmd_probe,
    _probe_model_version,
)
```

Delete the function bodies from `__init__.py` (L750–1205, L1827–1899).

- [ ] **Step 3: Run harness tests**

```bash
pytest tests/test_harness_compatibility.py -v 2>&1 | tail -20
```

Expected: all pass.

- [ ] **Step 4: Run full suite**

```bash
pytest --ignore=tests/test_capability_scoring.py -x -q 2>&1 | tail -5
```

Expected: same pass count.

- [ ] **Step 5: Commit**

```bash
git add synlynk/probe.py synlynk/__init__.py
git commit -m "refactor: extract probe + harness logic → synlynk/probe.py"
```

---

## Task 5: Extract `synlynk/dispatch.py`

**Files:**
- Create: `synlynk/dispatch.py`
- Modify: `synlynk/__init__.py`
- Test: `tests/test_synlynk.py`, `tests/test_jobs.py`

Dispatch functions are spread across `__init__.py`. Lines to move: L1779 (`_spawn_with_pty_fallback`), L3126–3230 (job helpers), L5127–5488 (format + preflight + dispatch_agent + cmd_jobs), L7727–7810 (exec helpers), L11170+ (`exec_command`).

**Do NOT move:** `_reconcile_jobs` (L3218), `_reconcile_daemon_jobs` (L3329), `_dispatch_ready_jobs` (L3402), `_check_agent_functional` (L3502), `_best_agent_for_story` (L3086) — these reference `WatchDaemon`/`SynlynkDaemon` which stays in `__init__.py`.

- [ ] **Step 1: Create `synlynk/dispatch.py`**

```python
"""synlynk dispatch: preflight gates, agent dispatch, exec wrapper."""

import os
import json
import subprocess
import threading
import time
import select
import signal
import re
from typing import Optional

from synlynk._constants import AGENT_CAPABILITY_BASELINES
from synlynk.sentinel import _write_sentinel_alert


def _spawn_with_pty_fallback(cmd, env, cwd):
    ...  # copy verbatim from __init__.py L1779


def _is_interactive(cmd_args: list) -> bool:
    ...  # copy verbatim from __init__.py L7727


def _inject_grok_rules(cmd_args: list) -> list:
    ...  # copy verbatim from __init__.py L7735


def _tee_process(process, buffer: list) -> None:
    ...  # copy verbatim from __init__.py L7749


def _check_pre_exec_gate(force: bool = False) -> bool:
    ...  # copy verbatim from __init__.py L7758


def _check_job_stall(job: dict, config: dict, sentinel_path: str) -> bool:
    ...  # copy verbatim from __init__.py L3126


def _job_summary_path(job_id: str) -> str:
    ...  # copy verbatim from __init__.py L3177


def _format_job_summary(job_id: str, agent: str, story_id: Optional[str],
                         task: str, exit_code: int, duration: float,
                         log_path: str) -> str:
    ...  # copy verbatim from __init__.py L3181


def _write_job_summary(job_id: str, agent: str, story_id: Optional[str],
                        task: str, exit_code: int, duration: float,
                        log_path: str) -> None:
    ...  # copy verbatim from __init__.py L3203


def _format_prompt_for_agent(agent: str, context_text: str, story_id: str,
                              task: str, model: str = None) -> str:
    ...  # copy verbatim from __init__.py L5127


def _warn_context_size(context_text: str) -> None:
    ...  # copy verbatim from __init__.py L5175


def _preflight_dispatch(agent_name: str, dispatch_flags: list,
                         db_conn=None) -> dict:
    ...  # copy verbatim from __init__.py L5183


def dispatch_agent(agent: str, task: str, story_id: str = None,
                   force_agent: bool = False,
                   context_mode: str = None,
                   cycle: str = "work") -> dict:
    ...  # copy verbatim from __init__.py L5288


def exec_command(cmd_args: list, force: bool = False) -> int:
    ...  # copy verbatim from __init__.py L11170
```

**Watch for:** `dispatch_agent` and `exec_command` call many other functions still in `__init__.py` (`generate_context`, `_load_jobs`, `_save_jobs`, `update_costs`, `extract_tokens`, `check_sentinel_patterns`, etc.). These calls should resolve through the `from synlynk import X` re-export chain — do NOT move those callee functions. If you see `NameError` for a function called inside `dispatch_agent` or `exec_command`, add a lazy import at the top of the calling function body: `from synlynk import missing_fn`.

- [ ] **Step 2: Add re-export to `__init__.py` and remove originals**

```python
from synlynk.dispatch import (
    _spawn_with_pty_fallback,
    _is_interactive,
    _inject_grok_rules,
    _tee_process,
    _check_pre_exec_gate,
    _check_job_stall,
    _job_summary_path,
    _format_job_summary,
    _write_job_summary,
    _format_prompt_for_agent,
    _warn_context_size,
    _preflight_dispatch,
    dispatch_agent,
    exec_command,
)
```

Delete the function bodies from `__init__.py` at the lines identified above.

- [ ] **Step 3: Run dispatch + job tests**

```bash
pytest tests/test_synlynk.py tests/test_jobs.py -v 2>&1 | tail -30
```

Expected: all pass.

- [ ] **Step 4: Run full suite**

```bash
pytest --ignore=tests/test_capability_scoring.py -x -q 2>&1 | tail -5
```

Expected: same pass count as Task 1 Step 1.

- [ ] **Step 5: Commit**

```bash
git add synlynk/dispatch.py synlynk/__init__.py
git commit -m "refactor: extract dispatch + exec logic → synlynk/dispatch.py"
```

---

## Task 6: Import verification tests + final line count check

**Files:**
- Create: `tests/test_modularise.py`

- [ ] **Step 1: Write import verification tests**

```python
"""Verify that all extracted symbols are still importable from synlynk directly."""


def test_upgrade_symbols_importable():
    from synlynk import (
        _detect_install_type, _ver_tuple, _run_upgrade,
        _get_pipx_source, _warn_stale_script_install, upgrade,
    )
    assert callable(upgrade)
    assert callable(_detect_install_type)


def test_sentinel_symbols_importable():
    from synlynk import (
        _write_sentinel_alert, _read_sentinel_alerts,
        check_sentinel_patterns, sentinel_list, sentinel_clear,
        log_telemetry_event,
    )
    assert callable(_write_sentinel_alert)
    assert callable(check_sentinel_patterns)


def test_probe_symbols_importable():
    from synlynk import (
        _probe_agent, cmd_probe, _run_tc1, _run_tc2, _run_tc3, _run_tc4,
        _compute_capability_hash, _build_fence_content, _upsert_harness_fence,
        _fence_exists,
    )
    assert callable(_probe_agent)
    assert callable(cmd_probe)


def test_dispatch_symbols_importable():
    from synlynk import (
        _preflight_dispatch, dispatch_agent, exec_command,
        _spawn_with_pty_fallback, _check_job_stall,
        _format_prompt_for_agent, _warn_context_size,
    )
    assert callable(_preflight_dispatch)
    assert callable(dispatch_agent)
    assert callable(exec_command)


def test_constants_importable():
    from synlynk import VERSION, AGENT_CAPABILITY_BASELINES, QUOTA_PATTERNS
    assert isinstance(VERSION, str)
    assert "claude" in AGENT_CAPABILITY_BASELINES
    assert isinstance(QUOTA_PATTERNS, list)


def test_ver_tuple_ordering():
    from synlynk import _ver_tuple
    assert _ver_tuple("0.11.0") > _ver_tuple("0.10.0")
    assert _ver_tuple("1.0.0") > _ver_tuple("0.11.0")
    assert _ver_tuple("0.10.1") > _ver_tuple("0.10.0")
```

- [ ] **Step 2: Run modularise tests**

```bash
pytest tests/test_modularise.py -v
```

Expected: 6 tests pass.

- [ ] **Step 3: Check final line counts**

```bash
wc -l synlynk/__init__.py synlynk/_constants.py synlynk/upgrade.py synlynk/sentinel.py synlynk/probe.py synlynk/dispatch.py
```

Expected: `__init__.py` under 6,000L (down from 11,268L).

- [ ] **Step 4: Run full suite one final time**

```bash
pytest --ignore=tests/test_capability_scoring.py -q 2>&1 | tail -5
```

Expected: same or higher pass count as starting baseline.

- [ ] **Step 5: Commit and push PR**

```bash
git add tests/test_modularise.py
git commit -m "test: import verification for modularised synlynk modules"
git push origin HEAD
```

Open PR: `chore/modularise-init` → `main`.
PR body must include before/after `wc -l` output.
