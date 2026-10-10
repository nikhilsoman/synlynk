# Task 5 Brief: End-to-End Integration, True-Up & Regression Verification (LIVE-19 & LIVE-20)

**Story ID:** `story-b907ad30`  
**Harness:** `claude` | **Role:** `pm`  
**Base Branch:** `fix/agy/live-19-live-20-remediation`  

## Objective
Provide end-to-end integration verification across both LIVE-19 and LIVE-20: verify clean exit code preservation under in-flight token pressure, quad-harness subscription amortization, `synlynk cost true-up` reconciliation against the $90.00 base, and run full suite regression.

## Requirements
1. **End-to-End Test Suite:** Create `tests/test_live19_live20_e2e.py`:
   - Test 1: Full lifecycle test simulating a dispatched worker running with large prompt tokens (>5M/breached limit) that exits 0. Verify job record in `state.db` is `completed` with exit 0, cost entry is written with `mode: 'subscription'`, and Sentinel alert is clean.
   - Test 2: Full lifecycle test for `synlynk cost true-up`: verify monthly variance reconciliation between actual amortized spend and the $90.00 billed base.
   - Test 3: Run `synlynk cost billing` and verify formatted terminal output.
2. **Regression Suite:**
   - Run all 51+ feature tests and ensure 100% pass:
     `pytest tests/test_circuit_breaker_live19.py tests/test_jobs_reconcile_live19.py tests/test_harness_billing_config.py tests/test_costs_dual_ledger_live20.py tests/test_live19_live20_e2e.py`
3. **Docs & Parity:**
   - Run `python3 scripts/generate_command_docs.py` if taxonomy was updated.
   - Verify `git status` is clean.
