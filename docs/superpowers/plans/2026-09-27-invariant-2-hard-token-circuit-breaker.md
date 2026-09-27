# Invariant 2: Hard In-Flight Token Circuit Breakers & Runaway Worker Killer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Actively monitor running agent processes in real-time and terminate runaway workers exceeding token/cost limits before financial or quota bleeding occurs.

**Architecture:** Build `synlynk/circuit_breaker.py` to sample active in-flight job logs, compute live tokens and costs against `models.json`, check PID validity, send `SIGTERM`/`SIGKILL`, stamp `circuit_breaker_tripped` status, trigger Sentinel alerts, and wire autonomous failover into milestone DAG execution.

**Tech Stack:** Python 3.10+ (stdlib, `os`, `signal`, `sqlite3`, `pytest`).

**Spec:** `docs/superpowers/specs/2026-09-27-invariant-2-hard-token-circuit-breaker-design.md`

## Global Constraints
- In-flight evaluation must never crash reconciliation or daemon loops on missing or unreadable log files.
- Active process termination must verify PID identity before signaling to prevent PID recycling accidents.
- All commits MUST include trailer: `Co-Authored-By: Agy (Gemini) <noreply@antigravity.dev>`.
- 100% of existing test matrix (3,336+ tests) must remain green.

---

### Task 1: Extend Job Status Taxonomy with `STATUS_CIRCUIT_BREAKER_TRIPPED`

**Files:**
- Modify: `synlynk/jobs.py`
- Modify: `tests/test_job_status_taxonomy.py`

**Interfaces:**
- Produces: `STATUS_CIRCUIT_BREAKER_TRIPPED = "circuit_breaker_tripped"`, included in `TERMINAL_JOB_STATUSES` and `ALL_JOB_STATUSES`.

- [ ] **Step 1: Write the failing test**
Update `tests/test_job_status_taxonomy.py` asserting that `STATUS_CIRCUIT_BREAKER_TRIPPED` exists, is in `TERMINAL_JOB_STATUSES`, and `is_terminal_status("circuit_breaker_tripped")` returns `True`.

- [ ] **Step 2: Run test to verify failure**
Run `pytest tests/test_job_status_taxonomy.py` and confirm `ImportError` / `AssertionError`.

- [ ] **Step 3: Implement status constant in `synlynk/jobs.py`**
Add `STATUS_CIRCUIT_BREAKER_TRIPPED` to `synlynk/jobs.py` and include in status collections.

- [ ] **Step 4: Run test to verify pass**
Run `pytest tests/test_job_status_taxonomy.py` and confirm 100% pass.

- [ ] **Step 5: Commit changes**
Commit with subject `feat(jobs): add circuit_breaker_tripped status constant`.

---

### Task 2: In-Flight Circuit Breaker Module (`synlynk/circuit_breaker.py`)

**Files:**
- Create: `synlynk/circuit_breaker.py`
- Test: `tests/test_circuit_breaker.py`

**Interfaces:**
- Produces: `evaluate_job_circuit_breaker(job: dict, config: Optional[dict] = None, sentinel_path: Optional[str] = None) -> CircuitBreakerResult`

- [ ] **Step 1: Write the failing test**
Create `tests/test_circuit_breaker.py` testing token limit breach, cost limit breach, zero-file threshold, process termination (`SIGTERM`/`SIGKILL`), and Sentinel alert generation.

- [ ] **Step 2: Run test to verify failure**
Run `pytest tests/test_circuit_breaker.py` and verify `ModuleNotFoundError`.

- [ ] **Step 3: Implement `synlynk/circuit_breaker.py`**
Implement live log parsing (`extract_tokens`), cost estimation against model rates, configurable threshold evaluation, safe PID identity checks, process termination escalation (`SIGTERM` $\to$ `SIGKILL`), and `TOKEN_CIRCUIT_BREAKER_TRIPPED` Sentinel alerting.

- [ ] **Step 4: Run test to verify pass**
Run `pytest tests/test_circuit_breaker.py` and confirm all tests pass.

- [ ] **Step 5: Commit changes**
Commit with subject `feat(circuit-breaker): implement in-flight token and cost circuit breaker engine`.

---

### Task 3: Integration into Reconciliation & Active Job Loops

**Files:**
- Modify: `synlynk/jobs.py`
- Modify: `synlynk/daemon.py`
- Test: `tests/test_reconcile_circuit_breaker.py`

**Interfaces:**
- Consumes: `evaluate_job_circuit_breaker` from `synlynk.circuit_breaker`
- Produces: Active running job termination on every reconciliation tick.

- [ ] **Step 1: Write the failing test**
Create `tests/test_reconcile_circuit_breaker.py` simulating an active running job emitting runaway tokens, and asserting `_reconcile_jobs()` terminates the PID and marks status `circuit_breaker_tripped`.

- [ ] **Step 2: Run test to verify failure**
Run `pytest tests/test_reconcile_circuit_breaker.py` and verify assertion failure.

- [ ] **Step 3: Wire `evaluate_job_circuit_breaker` into `_reconcile_jobs_unlocked()`**
Call `evaluate_job_circuit_breaker()` in `_reconcile_jobs_unlocked()` for every `running` job prior to PID liveness / stall checks.

- [ ] **Step 4: Run test to verify pass**
Run `pytest tests/test_reconcile_circuit_breaker.py` and confirm 100% pass.

- [ ] **Step 5: Commit changes**
Commit with subject `feat(jobs): wire active circuit breaker into reconciliation loop`.

---

### Task 4: Autonomous Milestone DAG Failover on Circuit Breaker Trip

**Files:**
- Modify: `synlynk/launch_dag.py`
- Test: `tests/test_milestone_circuit_breaker_failover.py`

**Interfaces:**
- Produces: Autonomous harness failover in `LaunchDAG.handle_job_outcome()` when `circuit_breaker_tripped` occurs.

- [ ] **Step 1: Write the failing test**
Create `tests/test_milestone_circuit_breaker_failover.py` asserting that `LaunchDAG.handle_job_outcome(node_id, STATUS_CIRCUIT_BREAKER_TRIPPED)` fails over to secondary harness if retries remain.

- [ ] **Step 2: Run test to verify failure**
Run `pytest tests/test_milestone_circuit_breaker_failover.py` and verify failure.

- [ ] **Step 3: Update `LaunchDAG.handle_job_outcome()` in `synlynk/launch_dag.py`**
Handle `STATUS_CIRCUIT_BREAKER_TRIPPED` in `handle_job_outcome()`.

- [ ] **Step 4: Run test to verify pass**
Run `pytest tests/test_milestone_circuit_breaker_failover.py` and confirm pass.

- [ ] **Step 5: Commit changes**
Commit with subject `feat(dag): add autonomous failover on circuit breaker trip`.

---

### Task 5: Vizor Status Badging & CSS Styling

**Files:**
- Modify: `synlynk/viz.py`
- Test: `tests/test_viz_circuit_breaker.py`

**Interfaces:**
- Produces: `.status-chip.circuit-breaker` (`⚡ BREAKER`) badge in Vizor HUD.

- [ ] **Step 1: Write the failing test**
Create `tests/test_viz_circuit_breaker.py` asserting `generate_overview_html` renders `.status-chip.circuit-breaker` for `circuit_breaker_tripped` jobs.

- [ ] **Step 2: Run test to verify failure**
Run `pytest tests/test_viz_circuit_breaker.py` and verify failure.

- [ ] **Step 3: Implement status badge and CSS in `synlynk/viz.py`**
Update badge mappings and CSS in `synlynk/viz.py`.

- [ ] **Step 4: Run test to verify pass**
Run `pytest tests/test_viz_circuit_breaker.py` and confirm pass.

- [ ] **Step 5: Commit changes**
Commit with subject `feat(viz): add circuit breaker status badging and styling`.
