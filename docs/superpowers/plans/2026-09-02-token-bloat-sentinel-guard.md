# Sentinel Token Bloat & Cost Inflation Guard — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement automated detection and alerting for anomalous token-per-file-touched ratios and cost inflation in `synlynk/sentinel.py`, integrate with job reconciliation in `synlynk/jobs.py`, and author unit and regression tests resolving issue #1073.

**Architecture:**  
Add `check_token_bloat()` to `synlynk/sentinel.py` configured with default thresholds (`DEFAULT_TOKEN_BLOAT_ZERO_FILE_THRESHOLD = 500_000`, `DEFAULT_TOKEN_PER_FILE_RATIO_THRESHOLD = 500_000`, `DEFAULT_COST_INFLATION_WARN_THRESHOLD = 3.00`, `DEFAULT_COST_INFLATION_CRITICAL_THRESHOLD = 5.00`). Wire detection into `_reconcile_jobs()` and `_reconcile_daemon_jobs()` in `synlynk/jobs.py` and export in `synlynk/__init__.py`. Provide telemetry scanning when invoked without direct job arguments.

**Tech Stack:** Python 3 (stdlib only), pytest.

---

### Task 1: Implement Detection Guard in `synlynk/sentinel.py`

**Files:**
- Modify: `synlynk/sentinel.py`
- Modify: `synlynk/__init__.py`

- [x] **Step 1: Define threshold constants and `check_token_bloat()`**  
  Implement `check_token_bloat()` with support for zero-files bloat, high token/file ratios, cost inflation tiers (WARN vs CRITICAL), and `.synlynk/telemetry.json` fallback scanning.
- [x] **Step 2: Wire `check_token_bloat()` into `check_sentinel_patterns()`**  
  Ensure execution-time pattern scanning checks telemetry records.
- [x] **Step 3: Export `check_token_bloat` in `synlynk/__init__.py`**  
  Expose function in top-level package namespace.

---

### Task 2: Integrate Guard with Job Reconciliation in `synlynk/jobs.py`

**Files:**
- Modify: `synlynk/jobs.py`

- [x] **Step 1: Hook `check_token_bloat` into `_reconcile_jobs()`**  
  Pass `in_tokens`, `out_tokens`, `cost_usd`, `files_touched`, `job_id`, `agent`, and `sentinel_path` on job completion.
- [x] **Step 2: Hook `check_token_bloat` into `_reconcile_daemon_jobs()`**  
  Ensure daemon job reconciliation evaluates completed jobs against token bloat and cost inflation guards.

---

### Task 3: Unit Tests in `tests/test_sentinel.py` & Regression in `tests/test_agent_cli.py`

**Files:**
- Modify: `tests/test_sentinel.py`
- Modify: `tests/test_agent_cli.py`

- [x] **Step 1: Write unit tests in `tests/test_sentinel.py`**  
  - Test zero-files with high tokens (`job-cf837848` metrics).
  - Test high token-per-file ratio (>1M tok/file across 2 files).
  - Test normal baseline usage (no alerts generated).
  - Test cost inflation warning ($3.50).
  - Test telemetry scanning from `.synlynk/telemetry.json`.
- [x] **Step 2: Add issue #1073 regression test in `tests/test_agent_cli.py`**  
  Implement `test_investigate_rootcause_costtoken_bloat_on_jobcf837848_and_add_costratio_sentinel_guard_1073`.

---

### Task 4: Author Blog Post, Update Index, Memory, and Devlog

**Files:**
- Create: `docs/blog/160-pr1334-token-bloat-sentinel-guard.md`
- Modify: `docs/blog/README.md`
- Modify: `project-docs/memory.md`
- Modify: `project-docs/devlogs/agy.md`

- [x] **Step 1: Write Blog Post 160**  
  Document the root cause of `job-cf837848` ($5.26 / 7.6M tokens on #1068), the context expansion dynamics, and the new Sentinel guard.
- [x] **Step 2: Update Series Index in `docs/blog/README.md`**  
  Add entry 160.
- [x] **Step 3: Update `project-docs/memory.md`**  
  Record design decision and sentinel thresholds with `[@agy]` attribution.
- [x] **Step 4: Update `project-docs/devlogs/agy.md`**  
  Log session execution details.
