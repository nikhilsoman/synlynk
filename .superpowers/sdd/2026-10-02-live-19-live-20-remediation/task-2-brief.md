# Task 2 Brief: Jobs Reconciliation Observer-Effect Elimination (LIVE-19)

**Story ID:** `story-6f88ef62`  
**Harness:** `codex` | **Role:** `implement`  
**Base Branch:** `fix/agy/live-19-live-20-remediation`  

## Objective
Eliminate the observer-effect race in `synlynk/jobs.py` where calling read-only CLI commands (`synlynk jobs`, `synlynk status`) or daemon reconciliation forces a still-finishing or just-finished worker into `STATUS_CIRCUIT_BREAKER_TRIPPED` without checking if the process was actually killed.

## Requirements
1. **TDD:** Create `tests/test_jobs_reconcile_live19.py`:
   - Test 1: In `_reconcile_jobs_unlocked()` (CLI path), mock `evaluate_job_circuit_breaker` to return `CircuitBreakerResult(tripped=False, process_killed=False, reason="...")` on a process that exited with exit code 0. Verify the job's terminal status is preserved as `completed` with `exit_code: 0`.
   - Test 2: In `_reconcile_daemon_jobs()`, mock `evaluate_job_circuit_breaker` to return `CircuitBreakerResult(tripped=False, process_killed=False, reason="...")` on an already-exited process. Verify daemon reconciliation reaps the natural exit status via `os.waitpid` and settles as `completed` / exit 0.
   - Test 3: Verify that when `cb_res.tripped is True and cb_res.process_killed is True`, both reconciliation paths settle the job as `circuit_breaker_tripped` / exit -9.
2. **Implementation in `synlynk/jobs.py`:**
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
3. **Verification:**
   - Run `pytest tests/test_jobs_reconcile_live19.py tests/test_jobs.py` and ensure 100% pass.
