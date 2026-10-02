# Task 1 Brief: Circuit Breaker Clean-Exit Preservation & Ceiling Calibration (LIVE-19)

**Story ID:** `story-abc3923f`  
**Harness:** `agy` | **Role:** `implement`  
**Base Branch:** `fix/agy/live-19-live-20-remediation`  

## Objective
Fix the fatal bug in `synlynk/circuit_breaker.py::evaluate_job_circuit_breaker()` where jobs that breached limits but already exited naturally on their own are stamped `STATUS_CIRCUIT_BREAKER_TRIPPED` with `exit_code: -9` and a CRITICAL Sentinel alert is posted, even though `_kill_process_tree()` failed to kill the process because it was already terminated.

## Requirements
1. **TDD:** Create `tests/test_circuit_breaker_live19.py`:
   - Test 1: When a job breaches token/cost limits but `_kill_process_tree()` returns `(False, "...")` (e.g. process not running), `evaluate_job_circuit_breaker()` must:
     - NOT stamp `job["status"] = STATUS_CIRCUIT_BREAKER_TRIPPED`
     - NOT overwrite `job["exit_code"] = -9`
     - NOT write a CRITICAL Sentinel alert
     - Return `CircuitBreakerResult(tripped=False, process_killed=False, ...)`
   - Test 2: When a job breaches token/cost limits and `_kill_process_tree()` returns `(True, "SIGTERM")` (process was alive and killed):
     - MUST stamp `job["status"] = STATUS_CIRCUIT_BREAKER_TRIPPED`
     - MUST set `job["exit_code"] = -9`
     - MUST write CRITICAL Sentinel alert
     - Return `CircuitBreakerResult(tripped=True, process_killed=True, ...)`
   - Test 3: Verify new ceiling defaults:
     - `DEFAULT_MAX_JOB_COST_USD = 15.00`
     - `DEFAULT_MAX_JOB_TOKENS = 5_000_000`
     - `DEFAULT_ZERO_FILE_TOKEN_THRESHOLD = 500_000`
     - Tier overrides:
       - `fast`: `max_job_tokens: 500_000`, `max_job_cost_usd: 2.00`
       - `pro`: `max_job_tokens: 3_000_000`, `max_job_cost_usd: 10.00`
       - `reasoning`: `max_job_tokens: 5_000_000`, `max_job_cost_usd: 15.00`
2. **Implementation in `synlynk/circuit_breaker.py`:**
   - In `evaluate_job_circuit_breaker()`:
     ```python
     killed, kill_method = _kill_process_tree(...)
     if not killed:
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
   - Calibrate defaults as specified above.
3. **Verification:**
   - Run `pytest tests/test_circuit_breaker_live19.py tests/test_circuit_breaker.py` and ensure 100% pass.
