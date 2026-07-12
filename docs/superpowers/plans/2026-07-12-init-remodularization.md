# `__init__.py` Re-modularization (Pass 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. This plan is written for a single Codex dispatch job (mirrors the original modularization, `job-421b7f01`) — do not split across multiple agents.

**Goal:** Extract 10 tangled subsystems out of `synlynk/__init__.py` (10,818L) into dedicated modules, fix a duplicate function definition found during investigation, and add a CI guardrail so the file can't silently regrow past 2,500L again.

**Architecture:** Pure move-and-re-export refactor. `synlynk/cli.py` already owns all argparse wiring and imports everything via `from synlynk import X` — no CLI behavior changes. Each new module gets the exact functions/classes listed below, cut verbatim from `__init__.py` (do not retype or reformat moved code — copy-paste to avoid transcription bugs). `__init__.py` re-exports every moved symbol via explicit `from synlynk.newmodule import (...)` blocks at the top, matching the existing pattern used for `probe.py`/`dispatch.py`/`sentinel.py`/`upgrade.py`.

**Tech Stack:** Python 3 stdlib only, pytest, existing `_pkg()` lazy-lookup pattern (see `synlynk/dispatch.py:18-22`) for symbols that still live in `__init__.py` at runtime.

---

## Before you start: known gotchas

1. **Do not run bare `pytest` from repo root** — a stray `worktrees/` directory (leftover from prior dispatch jobs) breaks collection with 279 errors. Always run `python3 -m pytest tests/ -q` (scoped to `tests/`).
2. **Baseline is 975 tests, all passing.** Confirm this before touching anything (Task 0). If your baseline differs, stop and report — don't proceed on a red baseline.
3. **The `_pkg()` decision rule** (used throughout every task below): when moved code references a symbol —
   - If that symbol is *also being moved in this same task* to the same new module → just call it directly, no import needed.
   - If that symbol already lives in an existing separate module (`_constants.py`, `sentinel.py`, `probe.py`, `dispatch.py`, `db.py`, etc.) → add a direct `from synlynk.othermodule import symbol_name` at the top of the new file.
   - If that symbol still lives in `__init__.py` after this task (i.e., it's in the "remains in `__init__.py`" list from the design doc) → do **not** import it directly (circular import — `__init__.py` will import the new module before that symbol is defined). Instead, add the `_pkg()` helper (exact code in Task 1, Step 2) to the new module and call `_pkg("symbol_name")` at the point of use, exactly as `dispatch.py` does.
4. **How to tell which case you're in:** after writing the new module, run `python3 -c "import synlynk"`. A `NameError` or `ImportError` at that point tells you exactly which symbol is missing and from where — fix per the rule above, don't guess ahead of time.

---

### Task 0: Baseline

**Files:** none (verification only)

- [ ] **Step 1: Confirm current branch and create the worktree**

Follow `superpowers:using-git-worktrees` to create a worktree for branch `chore/init-remodularization-pass2` off `main`. All subsequent steps run inside that worktree.

- [ ] **Step 2: Record baseline test count**

Run: `python3 -m pytest tests/ -q 2>&1 | tail -5`
Expected: `975 passed` (or note the actual count if different — record it, this is your target for every subsequent verification step)

- [ ] **Step 3: Record baseline line count**

Run: `wc -l synlynk/__init__.py`
Expected: `10818 synlynk/__init__.py` (or close — repo may have moved slightly since this plan was written)

---

### Task 1: `synlynk/quota.py` (smallest module — do this first to establish the pattern)

**Files:**
- Create: `synlynk/quota.py`
- Modify: `synlynk/__init__.py` (remove moved functions, add re-export import)

- [ ] **Step 1: Identify the exact line ranges to cut**

In `synlynk/__init__.py`, these 6 functions must move (find current line numbers with `grep -n "^def _quota_headroom\|^def _upsert_agent_quota\|^def _project_request_quota_from_config\|^def _read_agent_quota_rows\|^def _quota_status_for_agent\|^def _estimate_story_cost_usd" synlynk/__init__.py` — the design doc's line numbers were current as of 2026-07-12 and may have drifted):
- `_quota_headroom`
- `_upsert_agent_quota`
- `_project_request_quota_from_config`
- `_read_agent_quota_rows`
- `_quota_status_for_agent`
- `_estimate_story_cost_usd`

Each function's range runs from its `def` line to the line immediately before the next top-level `def`/`class` line (blank lines belong to the function being cut, not the next one).

- [ ] **Step 2: Create `synlynk/quota.py` with the `_pkg()` helper and cut functions**

Start the file with:

```python
"""synlynk quota: per-agent quota headroom, upsert, and cost estimation."""

import json
import sys
import time


def _pkg(name: str, default=None):
    package = sys.modules.get("synlynk")
    if package is None:
        return default
    return getattr(package, name, default)
```

Then paste the 6 cut function bodies below that, verbatim, in the order listed in Step 1.

- [ ] **Step 3: Remove the cut functions from `synlynk/__init__.py`**

Delete the exact line ranges identified in Step 1 from `synlynk/__init__.py`.

- [ ] **Step 4: Add the re-export import to `synlynk/__init__.py`**

Add this block near the top, alongside the existing `from synlynk.dispatch import (...)` block:

```python
from synlynk.quota import (
    _estimate_story_cost_usd,
    _project_request_quota_from_config,
    _quota_headroom,
    _quota_status_for_agent,
    _read_agent_quota_rows,
    _upsert_agent_quota,
)
```

- [ ] **Step 5: Check for missing imports**

Run: `python3 -c "import synlynk"`
Expected: no output, exit code 0. If `NameError`/`ImportError`, apply the decision rule from "Before you start" gotcha 3 — add the missing import to `synlynk/quota.py` and re-run this step until clean.

- [ ] **Step 6: Run the full test suite**

Run: `python3 -m pytest tests/ -q 2>&1 | tail -5`
Expected: same pass count as Task 0 Step 2 baseline (975 passed), zero new failures.

- [ ] **Step 7: Commit**

```bash
git add synlynk/quota.py synlynk/__init__.py
git commit -m "refactor: extract quota logic into synlynk/quota.py"
```

---

### Task 2: `synlynk/costs.py`

**Files:**
- Create: `synlynk/costs.py`
- Modify: `synlynk/__init__.py`

- [ ] **Step 1: Cut these 8 functions from `__init__.py`** (find current lines via `grep -n "^def update_costs\|^def extract_tokens\|^def extract_model_version\|^def extract_verifier_meta\|^def _model_rate_for_version\|^def check_budgets\|^def _compute_burn_rate\|^def parse_costs_md\|^class _TokenCounts" synlynk/__init__.py`):
- `class _TokenCounts` (the small class immediately preceding `extract_tokens`)
- `extract_tokens`
- `extract_model_version`
- `extract_verifier_meta`
- `_model_rate_for_version`
- `update_costs`
- `_compute_burn_rate`
- `check_budgets`
- `parse_costs_md`

- [ ] **Step 2: Create `synlynk/costs.py`**

```python
"""synlynk costs: token extraction, cost estimation, and budget checks."""

import json
import os
import re
import sys
import time


def _pkg(name: str, default=None):
    package = sys.modules.get("synlynk")
    if package is None:
        return default
    return getattr(package, name, default)
```

Paste the 9 cut items below (class + 8 functions), verbatim, in the order listed.

- [ ] **Step 3: Remove the cut items from `synlynk/__init__.py`**

- [ ] **Step 4: Add the re-export import**

```python
from synlynk.costs import (
    _TokenCounts,
    _compute_burn_rate,
    _model_rate_for_version,
    check_budgets,
    extract_model_version,
    extract_tokens,
    extract_verifier_meta,
    parse_costs_md,
    update_costs,
)
```

- [ ] **Step 5: Check for missing imports**

Run: `python3 -c "import synlynk"` — fix per the decision rule until clean.

- [ ] **Step 6: Run the full test suite**

Run: `python3 -m pytest tests/ -q 2>&1 | tail -5` — expect baseline pass count, zero new failures.

- [ ] **Step 7: Commit**

```bash
git add synlynk/costs.py synlynk/__init__.py
git commit -m "refactor: extract cost/telemetry logic into synlynk/costs.py"
```

---

### Task 3: `synlynk/doctor.py`

**Files:**
- Create: `synlynk/doctor.py`
- Modify: `synlynk/__init__.py`

- [ ] **Step 1: Cut these items** (find lines via `grep -n "^class HealthCheck\|^def _hc_\|^def cmd_doctor\|^def _doctor_" synlynk/__init__.py`):
- `class HealthCheck`
- `_hc_python_version`
- `_hc_project_init`
- `_hc_docs_dir`
- `_hc_identity_key`
- `_hc_agent_profiles`
- `_hc_instruction_files`
- `_hc_version_current`
- `cmd_doctor`
- `_doctor_fix_menu`
- `_doctor_maybe_escalate`

- [ ] **Step 2: Create `synlynk/doctor.py`**

```python
"""synlynk doctor: installation health checks and TC-1..TC-5 compliance suite."""

import os
import sys


def _pkg(name: str, default=None):
    package = sys.modules.get("synlynk")
    if package is None:
        return default
    return getattr(package, name, default)
```

Paste the cut class + 10 functions below, verbatim, in the order listed. `cmd_doctor` calls `_run_tc1`/`_run_tc2`/`_run_tc3`/`_run_tc4`/`_run_tc5` — add `from synlynk.probe import _run_tc1, _run_tc2, _run_tc3, _run_tc4, _run_tc5` (these already live in `probe.py`, confirmed via existing `__init__.py` import block — direct import, not `_pkg()`).

- [ ] **Step 3: Remove the cut items from `synlynk/__init__.py`**

- [ ] **Step 4: Add the re-export import**

```python
from synlynk.doctor import (
    HealthCheck,
    _doctor_fix_menu,
    _doctor_maybe_escalate,
    _hc_agent_profiles,
    _hc_docs_dir,
    _hc_identity_key,
    _hc_instruction_files,
    _hc_project_init,
    _hc_python_version,
    _hc_version_current,
    cmd_doctor,
)
```

- [ ] **Step 5: Check for missing imports**

Run: `python3 -c "import synlynk"` — fix per the decision rule until clean.

- [ ] **Step 6: Run the full test suite**

Run: `python3 -m pytest tests/ -q 2>&1 | tail -5` — expect baseline pass count, zero new failures.

- [ ] **Step 7: Commit**

```bash
git add synlynk/doctor.py synlynk/__init__.py
git commit -m "refactor: extract doctor/health-check logic into synlynk/doctor.py"
```

---

### Task 4: `synlynk/team.py`

**Files:**
- Create: `synlynk/team.py`
- Modify: `synlynk/__init__.py`

- [ ] **Step 1: Cut these items** (find lines via `grep -n "^def cmd_join\|^def _build_team_digest\|^def cmd_team_status\|^def cmd_decide\|^def _write_decision_record\|^def _run_agent_sync\|^def _sign_capability_rating\|^def _ensure_identity_key\|^def cmd_identity_init\|^def get_username\|^def get_mode" synlynk/__init__.py`):
- `get_username`
- `get_mode`
- `_ensure_identity_key`
- `_sign_capability_rating`
- `_run_agent_sync`
- `_write_decision_record`
- `cmd_decide`
- `_build_team_digest`
- `cmd_join`
- `cmd_team_status`
- `cmd_identity_init`

- [ ] **Step 2: Create `synlynk/team.py`**

```python
"""synlynk team: onboarding (join), team digest, consensus (decide), identity keys."""

import json
import os
import subprocess
import sys
import time


def _pkg(name: str, default=None):
    package = sys.modules.get("synlynk")
    if package is None:
        return default
    return getattr(package, name, default)
```

Paste the 11 cut functions below, verbatim, in the order listed.

- [ ] **Step 3: Remove the cut items from `synlynk/__init__.py`**

- [ ] **Step 4: Add the re-export import**

```python
from synlynk.team import (
    _build_team_digest,
    _ensure_identity_key,
    _run_agent_sync,
    _sign_capability_rating,
    _write_decision_record,
    cmd_decide,
    cmd_identity_init,
    cmd_join,
    cmd_team_status,
    get_mode,
    get_username,
)
```

- [ ] **Step 5: Check for missing imports**

Run: `python3 -c "import synlynk"` — fix per the decision rule until clean.

- [ ] **Step 6: Run the full test suite**

Run: `python3 -m pytest tests/ -q 2>&1 | tail -5` — expect baseline pass count, zero new failures.

- [ ] **Step 7: Commit**

```bash
git add synlynk/team.py synlynk/__init__.py
git commit -m "refactor: extract team/join/decide logic into synlynk/team.py"
```

---

### Task 5: `synlynk/support_engineer.py`

**Files:**
- Create: `synlynk/support_engineer.py`
- Modify: `synlynk/__init__.py`

- [ ] **Step 1: Cut these items** (find lines via `grep -n "^def _collect_\|^def _dedup_findings\|^def _run_investigation\|^def _file_gh_issue\|^def _recommend_handoff_agent\|^def _stalled_job_ids_from_sentinel\|^def _extract_diff\|^def _attempt_fix\|^def cmd_agent_run\|^def _install_cron_entry\|^def cmd_agent_list" synlynk/__init__.py`):
- `_collect_test_suite`
- `_collect_sentinel_alerts`
- `_collect_telemetry_anomaly`
- `_collect_capability_drop`
- `_collect_github_issues`
- `_dedup_findings`
- `_run_investigation`
- `_file_gh_issue`
- `_recommend_handoff_agent`
- `_stalled_job_ids_from_sentinel`
- `_extract_diff`
- `_attempt_fix`
- `cmd_agent_run`
- `_install_cron_entry`
- `cmd_agent_list`

- [ ] **Step 2: Create `synlynk/support_engineer.py`**

```python
"""synlynk support_engineer: Support Engineer archetype — signal collection, investigation, draft fixes."""

import json
import os
import re
import subprocess
import sys
import time


def _pkg(name: str, default=None):
    package = sys.modules.get("synlynk")
    if package is None:
        return default
    return getattr(package, name, default)
```

Paste the 15 cut functions below, verbatim, in the order listed.

- [ ] **Step 3: Remove the cut items from `synlynk/__init__.py`**

- [ ] **Step 4: Add the re-export import**

```python
from synlynk.support_engineer import (
    _attempt_fix,
    _collect_capability_drop,
    _collect_github_issues,
    _collect_sentinel_alerts,
    _collect_telemetry_anomaly,
    _collect_test_suite,
    _dedup_findings,
    _extract_diff,
    _file_gh_issue,
    _install_cron_entry,
    _recommend_handoff_agent,
    _run_investigation,
    _stalled_job_ids_from_sentinel,
    cmd_agent_list,
    cmd_agent_run,
)
```

- [ ] **Step 5: Check for missing imports**

Run: `python3 -c "import synlynk"` — fix per the decision rule until clean.

- [ ] **Step 6: Run the full test suite**

Run: `python3 -m pytest tests/ -q 2>&1 | tail -5` — expect baseline pass count, zero new failures.

- [ ] **Step 7: Commit**

```bash
git add synlynk/support_engineer.py synlynk/__init__.py
git commit -m "refactor: extract Support Engineer archetype logic into synlynk/support_engineer.py"
```

---

### Task 6: `synlynk/context.py` (includes the duplicate-function fix)

**Files:**
- Create: `synlynk/context.py`
- Modify: `synlynk/__init__.py`

- [ ] **Step 1: Diff the two `_generate_context_from_db` definitions before cutting anything**

Run: `grep -n "^def _generate_context_from_db" synlynk/__init__.py`
Expected: two line numbers (were 7909 and 7989 as of 2026-07-12, may have drifted).

Extract both bodies and diff them:
```bash
python3 - <<'PYEOF'
import re
src = open("synlynk/__init__.py").read().splitlines()
starts = [i for i, l in enumerate(src) if l.startswith("def _generate_context_from_db")]
print("defs found at 0-indexed lines:", starts)
PYEOF
```
Manually read both function bodies (use `sed -n '<start>,<start+80>p' synlynk/__init__.py` for each). Compare them.

- **If identical, or the second is a strict superset/fix of the first:** keep only the second (later) definition — it's the one Python actually executes at import time, since the second `def` silently overwrites the first in the module namespace. Discard the first.
- **If they differ in ways where the first does something the second does not:** stop and report the specific difference in the PR description rather than picking one — do not guess or merge them yourself.

- [ ] **Step 2: Cut these items** (find lines via `grep -n "^def generate_context\|^def _generate_context_from_db\|^def _append_vizor_notes\|^def _write_last_devlog_section\|^def _write_recent_devlog_entries\|^def _get_last_devlog_date\|^def _generate_task_context\|^def _relevant_files_for_story\|^def _verify_contract_for_story" synlynk/__init__.py`):
- `_get_last_devlog_date`
- `_write_recent_devlog_entries`
- `_write_last_devlog_section`
- `_generate_task_context`
- `_generate_context_from_db` (the single surviving definition from Step 1 — cut only one copy)
- `_append_vizor_notes`
- `generate_context`
- `_relevant_files_for_story`
- `_verify_contract_for_story`

- [ ] **Step 3: Create `synlynk/context.py`**

```python
"""synlynk context: context.md generation from state.db and flat-file sources."""

import json
import os
import sys
import time


def _pkg(name: str, default=None):
    package = sys.modules.get("synlynk")
    if package is None:
        return default
    return getattr(package, name, default)
```

Paste the 9 cut functions below (the single surviving `_generate_context_from_db`), verbatim, in the order listed.

- [ ] **Step 4: Remove the cut items from `synlynk/__init__.py`** — including deleting **both** copies of `_generate_context_from_db` from `__init__.py` (only one copy moves to `context.py`; neither stays behind).

- [ ] **Step 5: Add the re-export import**

```python
from synlynk.context import (
    _append_vizor_notes,
    _generate_context_from_db,
    _generate_task_context,
    _get_last_devlog_date,
    _relevant_files_for_story,
    _verify_contract_for_story,
    _write_last_devlog_section,
    _write_recent_devlog_entries,
    generate_context,
)
```

- [ ] **Step 6: Check for missing imports**

Run: `python3 -c "import synlynk"` — fix per the decision rule until clean.

- [ ] **Step 7: Run the full test suite**

Run: `python3 -m pytest tests/ -q 2>&1 | tail -5` — expect baseline pass count, zero new failures. Pay particular attention to any test with "context" in its name — run `python3 -m pytest tests/ -k context -v` and confirm all pass, since this task also changed behavior (removed a shadowed duplicate), not just moved code.

- [ ] **Step 8: Commit**

```bash
git add synlynk/context.py synlynk/__init__.py
git commit -m "refactor: extract context generation into synlynk/context.py, fix duplicate _generate_context_from_db"
```

---

### Task 7: `synlynk/jobs.py`

**Files:**
- Create: `synlynk/jobs.py`
- Modify: `synlynk/__init__.py`

- [ ] **Step 1: Cut these items** (find lines via `grep -n "^def _load_jobs\|^def _save_jobs\|^def _inspect_worktree_git_state\|^def _count_dispatch_rework\|^def _extract_micro_rework\|^def _count_tool_calls\|^def _write_capability_rating\|^def _reconcile_jobs\|^def _reconcile_daemon_jobs\|^def _dispatch_ready_jobs\|^def _best_agent_for_story\|^def _capability_candidates_for_story\|^def cmd_jobs\|^def cmd_jobs_handoff" synlynk/__init__.py`):
- `_load_jobs`
- `_save_jobs`
- `_inspect_worktree_git_state`
- `_count_dispatch_rework`
- `_extract_micro_rework`
- `_count_tool_calls`
- `_write_capability_rating`
- `_capability_candidates_for_story`
- `_best_agent_for_story`
- `_reconcile_jobs`
- `_reconcile_daemon_jobs`
- `_dispatch_ready_jobs`
- `cmd_jobs`
- `cmd_jobs_handoff`

- [ ] **Step 2: Create `synlynk/jobs.py`**

```python
"""synlynk jobs: job store, reconciliation (CLI-dispatch and daemon paths), fleet routing."""

import json
import os
import subprocess
import sys
import time


def _pkg(name: str, default=None):
    package = sys.modules.get("synlynk")
    if package is None:
        return default
    return getattr(package, name, default)
```

Paste the 14 cut functions below, verbatim, in the order listed. Note: `_reconcile_jobs` and `_dispatch_ready_jobs` reference sentinel-writing functions already in `sentinel.py` — add `from synlynk.sentinel import _write_sentinel_alert` directly (already extracted, no `_pkg()` needed).

- [ ] **Step 3: Remove the cut items from `synlynk/__init__.py`**

- [ ] **Step 4: Add the re-export import**

```python
from synlynk.jobs import (
    _best_agent_for_story,
    _capability_candidates_for_story,
    _count_dispatch_rework,
    _count_tool_calls,
    _dispatch_ready_jobs,
    _extract_micro_rework,
    _inspect_worktree_git_state,
    _load_jobs,
    _reconcile_daemon_jobs,
    _reconcile_jobs,
    _save_jobs,
    _write_capability_rating,
    cmd_jobs,
    cmd_jobs_handoff,
)
```

- [ ] **Step 5: Check for missing imports**

Run: `python3 -c "import synlynk"` — fix per the decision rule until clean.

- [ ] **Step 6: Run the full test suite**

Run: `python3 -m pytest tests/ -q 2>&1 | tail -5` — expect baseline pass count, zero new failures. This module touches `_reconcile_daemon_jobs`, which is the function at the center of open issue #136 — run `python3 -m pytest tests/ -k "job or daemon" -v` specifically and confirm no behavior changed, only location.

- [ ] **Step 7: Commit**

```bash
git add synlynk/jobs.py synlynk/__init__.py
git commit -m "refactor: extract job store and reconciliation logic into synlynk/jobs.py"
```

---

### Task 8: `synlynk/daemon.py`

**Files:**
- Create: `synlynk/daemon.py`
- Modify: `synlynk/__init__.py`

- [ ] **Step 1: Cut these items** (find lines via `grep -n "^class WatchDaemon\|^def _make_daemon_handler\|^def _daemon_install_service\|^def _daemon_uninstall_service\|^def _make_relay_handler\|^class SynlynkRelay\|^class SynlynkDaemon\|^def cmd_relay_start\|^def cmd_relay_broadcast\|^def check_daemon_health\|^def check_stall" synlynk/__init__.py`):
- `class WatchDaemon`
- `_make_daemon_handler`
- `_daemon_install_service`
- `_daemon_uninstall_service`
- `_make_relay_handler`
- `class SynlynkRelay`
- `class SynlynkDaemon` (subclasses `WatchDaemon` — must come after it in the new file, same relative order as today)
- `cmd_relay_start`
- `cmd_relay_broadcast`
- `check_daemon_health`
- `check_stall`

- [ ] **Step 2: Create `synlynk/daemon.py`**

```python
"""synlynk daemon: background watch daemon, HTTP context server, SSE relay broker."""

import http.server
import json
import os
import socketserver
import subprocess
import sys
import threading
import time


def _pkg(name: str, default=None):
    package = sys.modules.get("synlynk")
    if package is None:
        return default
    return getattr(package, name, default)
```

Paste the cut items below, verbatim, in the order listed (class-before-subclass order preserved).

- [ ] **Step 3: Remove the cut items from `synlynk/__init__.py`**

- [ ] **Step 4: Add the re-export import**

```python
from synlynk.daemon import (
    SynlynkDaemon,
    SynlynkRelay,
    WatchDaemon,
    _daemon_install_service,
    _daemon_uninstall_service,
    _make_daemon_handler,
    _make_relay_handler,
    check_daemon_health,
    check_stall,
    cmd_relay_broadcast,
    cmd_relay_start,
)
```

- [ ] **Step 5: Check for missing imports**

Run: `python3 -c "import synlynk"` — fix per the decision rule until clean.

- [ ] **Step 6: Run the full test suite**

Run: `python3 -m pytest tests/ -q 2>&1 | tail -5` — expect baseline pass count, zero new failures.

- [ ] **Step 7: Commit**

```bash
git add synlynk/daemon.py synlynk/__init__.py
git commit -m "refactor: extract daemon and relay logic into synlynk/daemon.py"
```

---

### Task 9: `synlynk/instructions.py`

**Files:**
- Create: `synlynk/instructions.py`
- Modify: `synlynk/__init__.py`

- [ ] **Step 1: Cut these items** (find lines via `grep -n "^def _build_templates\|^def _build_cursor_mdc\|^def _build_copilot_instructions\|^def _build_windsurf_rules\|^def _write_instruction_file\|^def _find_existing_doc\|^def _write_informed_skeleton\|^def _llm_enrich\|^def _generate_ai_context_files\|^def _extract_synlynk_section\|^def _compute_section_sha\|^def _strip_synlynk_section\|^def _is_evolved_repo\|^def _is_section_covered\|^def _extract_gh_ids\|^def _load_instruction_manifest\|^def _write_instruction_manifest\|^def _check_instruction_drift\|^def cmd_instructions_status\|^def cmd_instructions_diff\|^def cmd_instructions_update\|^def cmd_instructions_ack" synlynk/__init__.py`):
- `_extract_synlynk_section`
- `_compute_section_sha`
- `_write_instruction_file`
- `_find_existing_doc`
- `_write_informed_skeleton`
- `_llm_enrich`
- `_generate_ai_context_files`
- `_build_templates`
- `_build_cursor_mdc`
- `_build_copilot_instructions`
- `_build_windsurf_rules`
- `_strip_synlynk_section`
- `_is_evolved_repo`
- `_is_section_covered`
- `_extract_gh_ids`
- `_load_instruction_manifest`
- `_write_instruction_manifest`
- `_check_instruction_drift`
- `cmd_instructions_status`
- `cmd_instructions_diff`
- `cmd_instructions_update`
- `cmd_instructions_ack`

- [ ] **Step 2: Create `synlynk/instructions.py`**

```python
"""synlynk instructions: CLAUDE.md/GEMINI.md/AGENTS.md/.cursorrules generation and drift detection."""

import hashlib
import json
import os
import re
import sys
import time


def _pkg(name: str, default=None):
    package = sys.modules.get("synlynk")
    if package is None:
        return default
    return getattr(package, name, default)
```

Paste the 22 cut functions below, verbatim, in the order listed.

- [ ] **Step 3: Remove the cut items from `synlynk/__init__.py`**

- [ ] **Step 4: Add the re-export import**

```python
from synlynk.instructions import (
    _build_copilot_instructions,
    _build_cursor_mdc,
    _build_templates,
    _build_windsurf_rules,
    _check_instruction_drift,
    _compute_section_sha,
    _extract_gh_ids,
    _extract_synlynk_section,
    _find_existing_doc,
    _generate_ai_context_files,
    _is_evolved_repo,
    _is_section_covered,
    _llm_enrich,
    _load_instruction_manifest,
    _strip_synlynk_section,
    _write_informed_skeleton,
    _write_instruction_file,
    _write_instruction_manifest,
    cmd_instructions_ack,
    cmd_instructions_diff,
    cmd_instructions_status,
    cmd_instructions_update,
)
```

Note: `_strip_synlynk_section` was also used by `cmd_exit` (which remains in `__init__.py`) — after this move, `cmd_exit` will call it via the re-exported top-level `synlynk._strip_synlynk_section` name, which works automatically since it's imported into `__init__.py`'s namespace. No special handling needed, but include it in your Step 6 test check below.

- [ ] **Step 5: Check for missing imports**

Run: `python3 -c "import synlynk"` — fix per the decision rule until clean.

- [ ] **Step 6: Run the full test suite**

Run: `python3 -m pytest tests/ -q 2>&1 | tail -5` — expect baseline pass count, zero new failures. Also run `python3 -m pytest tests/ -k "exit or instructions" -v` to specifically confirm `cmd_exit`'s use of `_strip_synlynk_section` still works cross-module.

- [ ] **Step 7: Commit**

```bash
git add synlynk/instructions.py synlynk/__init__.py
git commit -m "refactor: extract instruction file generation into synlynk/instructions.py"
```

---

### Task 10: `synlynk/scan.py`

**Files:**
- Create: `synlynk/scan.py`
- Modify: `synlynk/__init__.py`

- [ ] **Step 1: Cut these items** (find lines via `grep -n "^def _static_scan\|^def _infer_industry\|^def find_git_roots\|^def fingerprint_stack\|^def scan_skills\|^def detect_home_harness\|^def parse_context_sections\|^def _scan_stage_\|^def run_workspace_scan\|^def _workspace_config_dir\|^def write_workspace_config\|^def generate_structured_context\|^def _score_source_files\|^def _scan_source_skeleton\|^def _query_repo_file_tree\|^def _scan_full_repo\|^def _check_scan_cache\|^def _format_source_architecture\|^def _scan_repo_for_docs\|^def _load_scan_meta\|^def _save_scan_meta\|^def _extract_symbols\|^def _git_head_sha\|^def cmd_scan" synlynk/__init__.py`):
- `_static_scan`
- `_infer_industry`
- `find_git_roots`
- `fingerprint_stack`
- `scan_skills`
- `detect_home_harness`
- `parse_context_sections`
- `_scan_stage_source`
- `_scan_stage_complexity`
- `_scan_stage_tests`
- `_scan_stage_git`
- `_scan_stage_arch`
- `_scan_stage_stack`
- `run_workspace_scan`
- `_workspace_config_dir`
- `write_workspace_config`
- `generate_structured_context`
- `_score_source_files`
- `_scan_source_skeleton`
- `_query_repo_file_tree`
- `_scan_full_repo`
- `_check_scan_cache`
- `_format_source_architecture`
- `_scan_repo_for_docs`
- `_load_scan_meta`
- `_save_scan_meta`
- `_extract_symbols`
- `_git_head_sha`
- `cmd_scan`

- [ ] **Step 2: Create `synlynk/scan.py`**

```python
"""synlynk scan: language-agnostic repo scanner, stack fingerprinting, source architecture generation."""

import hashlib
import json
import os
import re
import subprocess
import sys
import time


def _pkg(name: str, default=None):
    package = sys.modules.get("synlynk")
    if package is None:
        return default
    return getattr(package, name, default)
```

Paste the 28 cut functions below, verbatim, in the order listed. `cmd_scan` calls into `wizard.py`'s `_run_scan_tui` (extracted in Task 11, which runs after this task) — add `from synlynk.wizard import _run_scan_tui` once Task 11 lands. **For this task, `cmd_scan`'s reference to `_run_scan_tui` will trigger a `NameError` at the Step 4 import check below since `wizard.py` doesn't exist yet — that's expected and fine.** Use the `_pkg()` fallback for it in this task: `run_scan_tui = _pkg("_run_scan_tui")` at the point of use inside `cmd_scan`, and revisit in Task 11 (see Task 11 Step 4) once `wizard.py` exists, converting it to a direct import there.

- [ ] **Step 3: Remove the cut items from `synlynk/__init__.py`**

- [ ] **Step 4: Add the re-export import**

```python
from synlynk.scan import (
    _check_scan_cache,
    _extract_symbols,
    _format_source_architecture,
    _git_head_sha,
    _infer_industry,
    _load_scan_meta,
    _query_repo_file_tree,
    _save_scan_meta,
    _scan_full_repo,
    _scan_repo_for_docs,
    _scan_source_skeleton,
    _scan_stage_arch,
    _scan_stage_complexity,
    _scan_stage_git,
    _scan_stage_source,
    _scan_stage_stack,
    _scan_stage_tests,
    _score_source_files,
    _static_scan,
    _workspace_config_dir,
    cmd_scan,
    detect_home_harness,
    find_git_roots,
    fingerprint_stack,
    generate_structured_context,
    parse_context_sections,
    run_workspace_scan,
    scan_skills,
    write_workspace_config,
)
```

- [ ] **Step 5: Check for missing imports**

Run: `python3 -c "import synlynk"` — fix per the decision rule until clean (expect the `_run_scan_tui` `_pkg()` fallback from Step 2 to make this pass even before Task 11).

- [ ] **Step 6: Run the full test suite**

Run: `python3 -m pytest tests/ -q 2>&1 | tail -5` — expect baseline pass count, zero new failures.

- [ ] **Step 7: Commit**

```bash
git add synlynk/scan.py synlynk/__init__.py
git commit -m "refactor: extract scan pipeline into synlynk/scan.py"
```

---

### Task 11: `synlynk/wizard.py`

**Files:**
- Create: `synlynk/wizard.py`
- Modify: `synlynk/__init__.py`
- Modify: `synlynk/scan.py` (convert the `_pkg()` fallback from Task 10 to a direct import)

- [ ] **Step 1: Cut these items** (find lines via `grep -n "^def _wiz_\|^def _kbhit\|^def _card_summary\|^def _render_one_card\|^def _render_expanded_card\|^def _render_scan_cards\|^def _run_scan_tui\|^def _launch_screen_\|^def wizard_init\|^def cmd_launch_ftue" synlynk/__init__.py`):
- `_wiz_clear`
- `_wiz_read_key`
- `_kbhit`
- `_card_summary`
- `_render_one_card`
- `_render_expanded_card`
- `_render_scan_cards`
- `_run_scan_tui`
- `_wiz_header`
- `_wiz_prompt`
- `_wiz_screen_landing`
- `_wiz_screen_harness`
- `_wiz_screen_topology`
- `_wiz_screen_workspace_name_pick`
- `_wiz_screen_workspace_confirm`
- `_wiz_screen_skills`
- `_wiz_screen_agents`
- `_wiz_screen_roles`
- `_wiz_screen_launch`
- `_launch_screen_cycles`
- `_launch_screen_preview`
- `_launch_screen_tasks`
- `wizard_init`
- `cmd_launch_ftue`

- [ ] **Step 2: Create `synlynk/wizard.py`**

```python
"""synlynk wizard: FTUE 8-screen onboarding TUI (synlynk init --wizard) and launch task picker."""

import os
import select
import sys
import termios
import time
import tty


def _pkg(name: str, default=None):
    package = sys.modules.get("synlynk")
    if package is None:
        return default
    return getattr(package, name, default)
```

Paste the 24 cut functions below, verbatim, in the order listed.

- [ ] **Step 3: Remove the cut items from `synlynk/__init__.py`**

- [ ] **Step 4: Add the re-export import to `__init__.py`, and fix the Task 10 `_pkg()` fallback in `scan.py`**

In `synlynk/__init__.py`:
```python
from synlynk.wizard import (
    _card_summary,
    _kbhit,
    _launch_screen_cycles,
    _launch_screen_preview,
    _launch_screen_tasks,
    _render_expanded_card,
    _render_one_card,
    _render_scan_cards,
    _run_scan_tui,
    _wiz_clear,
    _wiz_header,
    _wiz_prompt,
    _wiz_read_key,
    _wiz_screen_agents,
    _wiz_screen_harness,
    _wiz_screen_landing,
    _wiz_screen_launch,
    _wiz_screen_roles,
    _wiz_screen_skills,
    _wiz_screen_topology,
    _wiz_screen_workspace_confirm,
    _wiz_screen_workspace_name_pick,
    cmd_launch_ftue,
    wizard_init,
)
```

In `synlynk/scan.py`, find the `_pkg("_run_scan_tui")` fallback added in Task 10 Step 2 and replace it: add `from synlynk.wizard import _run_scan_tui` at the top of `scan.py` alongside the other imports, and change the call site in `cmd_scan` from `run_scan_tui = _pkg("_run_scan_tui")` back to calling `_run_scan_tui` directly.

- [ ] **Step 5: Check for missing imports**

Run: `python3 -c "import synlynk"` — fix per the decision rule until clean.

- [ ] **Step 6: Run the full test suite**

Run: `python3 -m pytest tests/ -q 2>&1 | tail -5` — expect baseline pass count, zero new failures. Also run `python3 -m pytest tests/ -k "wizard or ftue or scan" -v` to specifically verify the `scan.py` ↔ `wizard.py` cross-module call works.

- [ ] **Step 7: Commit**

```bash
git add synlynk/wizard.py synlynk/scan.py synlynk/__init__.py
git commit -m "refactor: extract FTUE wizard TUI into synlynk/wizard.py, fix scan.py cross-import"
```

---

### Task 12: CI guardrail against regrowth

**Files:**
- Modify: the test workflow file (find it first — do not assume the name)

- [ ] **Step 1: Find the CI workflow that runs the test suite**

Run: `ls .github/workflows/` and `grep -l "pytest" .github/workflows/*.yml`

- [ ] **Step 2: Add a line-count check step**

In the workflow file found in Step 1, add a new step after the checkout step and before (or alongside) the test-running step:

```yaml
      - name: Guard against __init__.py regrowth
        run: |
          LINES=$(wc -l < synlynk/__init__.py)
          echo "synlynk/__init__.py is ${LINES} lines"
          if [ "$LINES" -gt 2500 ]; then
            echo "::error::synlynk/__init__.py is ${LINES} lines (limit 2500). New code belongs in a module, not __init__.py. See docs/superpowers/specs/2026-07-12-init-remodularization-design.md."
            exit 1
          fi
```

Match the existing YAML indentation style in that file (inspect a neighboring step first).

- [ ] **Step 3: Verify the guardrail fires correctly**

Run this locally to simulate a regression:
```bash
python3 -c "
with open('synlynk/__init__.py', 'a') as f:
    f.write('\n' * 3000)
"
LINES=$(wc -l < synlynk/__init__.py)
echo "Simulated size: $LINES"
if [ "$LINES" -gt 2500 ]; then echo "GUARD WOULD FIRE (correct)"; else echo "GUARD WOULD NOT FIRE (wrong — investigate)"; fi
git checkout -- synlynk/__init__.py
```
Expected: `GUARD WOULD FIRE (correct)`, and the file is restored by the final `git checkout`.

- [ ] **Step 4: Verify current (post-extraction) size passes the guard**

Run: `wc -l synlynk/__init__.py`
Expected: under 2,500 (should be roughly 1,900–2,200 per the design doc's estimate — record the actual number for the final report).

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/
git commit -m "ci: guard against synlynk/__init__.py regrowth past 2500 lines"
```

---

### Task 13: Final verification and cleanup

**Files:**
- Modify: `synlynk/__init__.py` (remove now-unused top-level imports, if any)

- [ ] **Step 1: Check for unused imports left behind in `__init__.py`**

Run: `python3 -m pyflakes synlynk/__init__.py 2>&1 | grep "imported but unused"`

If pyflakes isn't installed: `pip install pyflakes` first, or use `python3 -We -c "import ast, sys; ..."` — simplest path is just installing pyflakes, it's a stdlib-adjacent single-purpose linter.

For each unused import reported, remove that specific import line from `__init__.py`. Do not remove anything not flagged.

- [ ] **Step 2: Full suite one more time**

Run: `python3 -m pytest tests/ -q 2>&1 | tail -5`
Expected: same pass count as the Task 0 baseline, zero failures.

- [ ] **Step 3: Confirm final line counts for the PR description**

Run:
```bash
wc -l synlynk/__init__.py synlynk/wizard.py synlynk/scan.py synlynk/instructions.py synlynk/daemon.py synlynk/jobs.py synlynk/quota.py synlynk/context.py synlynk/costs.py synlynk/support_engineer.py synlynk/doctor.py
```
Record this table for the PR description — it's the direct evidence the extraction worked.

- [ ] **Step 4: Commit any cleanup from Step 1**

```bash
git add synlynk/__init__.py
git commit -m "chore: remove unused imports left behind by re-modularization"
```

(Skip this commit if Step 1 found nothing to remove.)

- [ ] **Step 5: Push and open the PR**

```bash
git push -u origin chore/init-remodularization-pass2
gh pr create --repo nikhilsoman/synlynk --title "refactor: __init__.py re-modularization pass 2 (10 modules extracted)" --body "$(cat <<'EOF'
## Summary
- Extracted 10 subsystems out of synlynk/__init__.py into dedicated modules (wizard.py, scan.py, instructions.py, daemon.py, jobs.py, quota.py, context.py, costs.py, support_engineer.py, doctor.py) — pure move-and-re-export, no CLI-facing behavior change
- Fixed a duplicate _generate_context_from_db definition found during investigation (second copy was silently shadowing the first)
- Added a CI guardrail: build fails if synlynk/__init__.py exceeds 2500 lines, to prevent the regrowth that happened after the first modularization pass (2026-07-01, commit 222f7da)

## Design
docs/superpowers/specs/2026-07-12-init-remodularization-design.md

## Test plan
- [x] Full test suite passes with the same count as baseline at every commit in this branch (975 tests)
- [x] python3 -c "import synlynk" succeeds with no missing-import errors
- [x] CI guardrail verified to fire on simulated regrowth and pass on actual post-extraction size
EOF
)"
```

---

## Notes for the dispatched agent

- This plan is long because the file is large — but each task is mechanically identical (cut → paste → re-export → verify → commit). Don't skip the verification step between tasks; catching a missing import in the task that broke it is far cheaper than debugging it three tasks later.
- If any task's test suite run shows failures, stop and diagnose before moving to the next task. Do not proceed with a red suite.
- Task order matters only for Task 10 → Task 11 (the `_run_scan_tui` cross-reference). All other tasks are independent and could be reordered if needed, but do them in the listed order for consistency with this plan.
