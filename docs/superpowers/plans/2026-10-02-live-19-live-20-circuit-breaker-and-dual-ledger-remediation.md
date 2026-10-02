# Implementation Plan: LIVE-19 & LIVE-20 Remediation

**Title:** Circuit Breaker Clean-Exit Preservation (LIVE-19) & Quad-Harness Subscription Dual-Ledger Amortization (LIVE-20)  
**Spec Reference:** `docs/superpowers/specs/2026-10-02-live-19-live-20-circuit-breaker-and-dual-ledger-remediation-design.md`  
**Date:** 2026-10-02  
**Branch:** `fix/agy/live-19-live-20-remediation`  

---

## 1. Overview & Strategy

This plan resolves two active Sev-2 issues in `synlynk`:
1. **LIVE-19 (#1896):** Prevent circuit-breaker false-negatives when worker processes exit cleanly on their own before or during evaluation; eliminate the CLI reconciliation observer effect; tune token and cost ceilings.
2. **LIVE-20 (#1897):** Wire Nikhil's quad-harness subscription billing arrangement ($90/mo total) into `.synlynk/config.json`, update `synlynk/db.py::_generate_costs_md()` to render dual-ledger savings, and add `synlynk cost billing`.

Following synlynk's **Capability-Based Task Allocation**:
- **Task 1 (Agy):** Circuit Breaker Clean-Exit Preservation & Ceiling Calibration (`synlynk/circuit_breaker.py`).
- **Task 2 (Codex):** Jobs Reconciliation Observer-Effect Elimination (`synlynk/jobs.py`).
- **Task 3 (Codex):** Quad-Harness Subscription Configuration & `harness_billing` Seed (`.synlynk/config.json`, `synlynk/__init__.py`).
- **Task 4 (Agy):** Dual-Ledger Markdown Generation & Monthly Amortization Rollup (`synlynk/db.py`, `synlynk/costs.py`, `synlynk/cli.py`).
- **Task 5 (Claude):** End-to-End Integration, True-Up & Full Regression Verification (`tests/test_live19_live20_e2e.py`).

---

## 2. Tasks Breakdown

### Task 1: Circuit Breaker Clean-Exit Preservation & Ceiling Calibration (LIVE-19)
- **Role:** `implement` | **Harness:** `agy` | **Story ID:** `story-live19-task-1`
- **Files:** `synlynk/circuit_breaker.py`, `tests/test_circuit_breaker_live19.py`
- **Actions:**
  1. Write failing tests in `tests/test_circuit_breaker_live19.py`:
     - Test that when limits are exceeded but `_kill_process_tree` returns `killed=False` (process already exited), `evaluate_job_circuit_breaker()` returns `tripped=False`, `process_killed=False`, does NOT overwrite `job["status"]` or `job["exit_code"] = -9`, and does NOT write a CRITICAL Sentinel alert.
     - Test that when limits are exceeded and `_kill_process_tree` returns `killed=True`, `evaluate_job_circuit_breaker()` returns `tripped=True`, `process_killed=True`, stamps status, and writes the Sentinel alert.
     - Test updated ceiling defaults ($15.00 / 5,000,000 tokens) and tier overrides (`fast`: $2.00 / 500k, `pro`: $10.00 / 3M, `reasoning`: $15.00 / 5M).
  2. Implement fix in `synlynk/circuit_breaker.py`:
     - In `evaluate_job_circuit_breaker()`:
       ```python
       killed, kill_method = _kill_process_tree(...)
       if not killed:
           # Process was already dead/exited; do NOT stamp tripped or exit -9
           log_telemetry_event({
               "type": "circuit_breaker_post_exit_warning",
               "job_id": job.get("id"),
               "agent": job.get("agent"),
               "tokens": total_tokens,
               "cost_usd": cost_usd,
               "reason": reason,
           })
           return CircuitBreakerResult(
               tripped=False,
               reason=reason,
               in_tokens=in_tokens,
               out_tokens=out_tokens,
               total_tokens=total_tokens,
               cost_usd=cost_usd,
               process_killed=False,
               kill_method=kill_method,
           )
       ```
     - Update defaults and tier overrides in `synlynk/circuit_breaker.py`.
  3. Verify all tests pass in `tests/test_circuit_breaker_live19.py` and regression tests pass in `tests/test_circuit_breaker.py`.

---

### Task 2: Jobs Reconciliation Observer-Effect Elimination (LIVE-19)
- **Role:** `implement` | **Harness:** `codex` | **Story ID:** `story-live19-task-2`
- **Files:** `synlynk/jobs.py`, `tests/test_jobs_reconcile_live19.py`
- **Actions:**
  1. Write failing tests in `tests/test_jobs_reconcile_live19.py`:
     - Test `_reconcile_jobs_unlocked()` on a job whose process finished with exit 0 and breached limit: verify status remains `completed` with exit code 0.
     - Test `_reconcile_daemon_jobs()` on the same scenario: verify status remains `completed` with exit code 0.
  2. Update `synlynk/jobs.py`:
     - In `_reconcile_jobs_unlocked()` (~line 1794):
       ```python
       if cb_res.tripped and cb_res.process_killed:
           # Truly terminated by circuit breaker
           ...
           changed = True
           continue
       ```
     - In `_reconcile_daemon_jobs()` (~line 3616):
       ```python
       if cb_res.tripped and cb_res.process_killed:
           # Truly terminated by circuit breaker
           ...
           continue
       ```
  3. Verify tests pass in `tests/test_jobs_reconcile_live19.py` and `tests/test_jobs.py`.

---

### Task 3: Quad-Harness Subscription Configuration & `harness_billing` Seed (LIVE-20)
- **Role:** `implement` | **Harness:** `codex` | **Story ID:** `story-live20-task-3`
- **Files:** `.synlynk/config.json`, `synlynk/__init__.py`, `tests/test_harness_billing_config.py`
- **Actions:**
  1. Populate `.synlynk/config.json` with confirmed quad-harness subscriptions:
     - `claude`: `monthly_base_fee_usd: 20.0`, `mode: subscription`
     - `codex`: `monthly_base_fee_usd: 20.0`, `mode: subscription`
     - `agy`: `monthly_base_fee_usd: 20.0`, `mode: subscription`
     - `grok`: `monthly_base_fee_usd: 30.0`, `mode: subscription`
     - All with `projected_monthly_tokens: 10000000`, `allow_extra_usage: false`.
  2. In `synlynk/__init__.py`: update `_default_config()` to ensure `harness_billing` is initialized with these defaults when bootstrap occurs.
  3. In `tests/test_harness_billing_config.py`: verify `_payment_model_config_for_agent()` resolves all 4 harnesses to `mode: "subscription"` and extracts correct base fees.

---

### Task 4: Dual-Ledger Markdown Generation & Monthly Amortization Rollup (LIVE-20)
- **Role:** `implement` | **Harness:** `agy` | **Story ID:** `story-live20-task-4`
- **Files:** `synlynk/db.py`, `synlynk/costs.py`, `synlynk/cli.py`, `tests/test_costs_dual_ledger_live20.py`
- **Actions:**
  1. Write failing tests in `tests/test_costs_dual_ledger_live20.py`:
     - Test `_generate_costs_md()` produces table where subscription rows format `Cost` as `$X.XXXX [sub] (API: $Y.YYYY)`.
     - Test `parse_costs_md()` cleanly parses `$X.XXXX` without crashing or miscalculating.
     - Test that `## Subscription Amortization & Dual-Ledger Summary` section appears at the end of `costs.md` with monthly subscription totals and savings.
     - Test `synlynk cost billing` CLI command displays the 4 configured subscription plans and fees.
  2. Implement changes:
     - In `synlynk/db.py::_generate_costs_md()`:
       - Query selects `session_date, agent, model, input_tokens, output_tokens, total_cost_usd, cost_source, story_id, notes, api_equivalent_usd, actual_usd, payment_mode`.
       - Render `Cost` cell with dual-ledger format when mode is `subscription`.
       - Render summary table at the bottom calculating total subscription base ($90.00), total actual amortized, total API equivalent, and net savings.
     - In `synlynk/costs.py` & `synlynk/cli.py`:
       - Add `cmd_cost_billing(args)` printing active harness billing matrix.
       - Register `synlynk cost billing` in parser.
  3. Verify all tests pass in `tests/test_costs_dual_ledger_live20.py` and `tests/test_payment_models.py`.

---

### Task 5: End-to-End Integration, True-Up & Regression Verification
- **Role:** `pm / review` | **Harness:** `claude` | **Story ID:** `story-live19-live20-task-5`
- **Files:** `tests/test_live19_live20_e2e.py`
- **Actions:**
  1. Create end-to-end integration test `tests/test_live19_live20_e2e.py`:
     - Simulate dispatched job crossing limit and exiting 0 -> status verified `completed`, exit 0, cost logged with subscription mode.
     - Run `synlynk cost true-up` and verify monthly variance calculations against $90.00 base.
     - Verify `synlynk cost billing` output matches configured quad-harness structure.
  2. Run full regression test suite (all 51+ tests).

---

## 3. Review Checkpoints & Gate Authority

- Task 1 & 2 Completion Check: Confirm circuit breaker tests pass and exit-0 preservation is verified.
- Task 3 & 4 Completion Check: Confirm `costs.md` renders dual ledger and `parse_costs_md()` does not regress.
- Task 5 Completion Check: Full regression green; PR opened and QA reviewed per PR Review Discipline.
