# Implementation Plan: Remaining P0 Fixes (P0-6 to P0-10)

**Date:** 2026-10-17  
**Spec Reference:** `docs/superpowers/specs/2026-10-17-remaining-p0-tranche-design.md`  
**Parent Epic:** [gh:#2384](https://github.com/nikhilsoman/synlynk/issues/2384)  
**Target:** Dev Preview readiness (31 Oct 2026)  

---

## Tranche 1: Core Engine Hardening (P0-8, P0-6, P0-10)

### Task 1: P0-8 Circuit Breaker Prompt-Cache Blindspot Fix
- **Files:** `synlynk/circuit_breaker.py`, `tests/test_circuit_breaker.py`
- **Issue:** gh:#1937
- **Implementation:**
  1. In `evaluate_job_circuit_breaker()`, decouple billed cost calculation from runaway loop detection.
  2. Compute `raw_cumulative_tokens = raw_in + out_tokens` from `extract_tokens()`.
  3. Evaluate `zero_file_threshold` and `max_tokens` against `raw_cumulative_tokens` (or turn count) instead of the cache-discounted `in_tokens + out_tokens`.
  4. Ensure `cost_usd` still uses `split_billed_tokens` for dollar accounting.
  5. Add regression tests in `tests/test_circuit_breaker.py` proving that a Codex job with 1.2M raw tokens (1.18M cached) and 0 files touched trips `zero_file_threshold`.
- **Verification:** `pytest -q tests/test_circuit_breaker.py` passes (all existing + new tests).

### Task 2: P0-6 Capability Report Discipline Expansion & Seed Filtering
- **Files:** `synlynk/capability_report.py`, `tests/test_capability_report.py`
- **Issues:** gh:#1993, gh:#2332
- **Implementation:**
  1. In `DISCIPLINE_TO_TASK_TYPE`, map all recognized disciplines:
     - `"docs": "content"`
     - `"security": "refactor"`
     - `"devops": "infra"`
     - `"PROG": "implement"`
  2. In `_fetch_rows()`, exclude synthetic seed rows (`agent = 'local'` or `cr.quality = 0.6` or `cr.story_id LIKE 'seed-%'`).
  3. Add `--apply` or `--format=diff` flag to `synlynk capability report` to directly stage proposed routing changes for human review.
  4. Add regression tests in `tests/test_capability_report.py` verifying discipline mapping expansion and synthetic row exclusion.
- **Verification:** `pytest -q tests/test_capability_report.py` passes; `synlynk capability report` reports 0 or significantly fewer skipped rows.

### Task 3: P0-10 Stale-Goal Reconciliation
- **Files:** `project-docs/roadmap.md`, `project-docs/todo.md`
- **Implementation:**
  1. Confirm `goal-5be4eb8b`, `goal-56d4beee`, and `goal-d38e3c83` are recorded as superseded and `goal-d3333441` as done in `roadmap.md`.
  2. Sync any residual references in `project-docs/todo.md`.
- **Verification:** `synlynk doctor` passes; no active goals have past deadlines.

---

## Tranche 2: Packaging, Onboarding & Distribution (P0-9, P0-7)

### Task 4: P0-9 Onboarding Hardening & Worktree Isolation for `heal --magic`
- **Files:** `synlynk/heal.py`, `tests/test_heal.py`
- **Issues:** gh:#1228
- **Implementation:**
  1. Update `run_magic_heal()` to provision an ephemeral isolated worktree (`git worktree add`) instead of modifying the user's checked-out working directory.
  2. Dynamically determine agent commit trailer instead of hardcoding Codex.
  3. Clean up the ephemeral worktree upon test generation/PR creation.
  4. Add automated test verifying `heal --magic --dry-run` and worktree isolation.
- **Verification:** `pytest -q tests/test_heal.py` passes.

### Task 5: P0-7 Distribution: PyPI Workflow & Thin VS Code Client
- **Files:** `.github/workflows/release-pypi.yml`, `clients/vscode/package.json`, `clients/vscode/extension.js`, `README.md`
- **Issues:** gh:#2103
- **Implementation:**
  1. Create lightweight VS Code extension in `clients/vscode/` exposing `synlynk dispatch`, `synlynk jobs`, and `synlynk logs`.
  2. Add `.github/workflows/release-pypi.yml` workflow for PyPI distribution on release tags.
  3. Update `README.md` with standard `pip install synlynk` and VSIX installation guide.
- **Verification:** Extension manifest valid, package build succeeds (`python3 -m build`).
