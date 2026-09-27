# Invariant 1: Effect-Verified Completion Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate false-positive agent "success" by enforcing that mutating jobs exit code 0 must have verified non-empty git diffs and passing tests before marking succeeded.

**Architecture:** Extend job status taxonomy, build a pure-Python `verify_effects.py` verification engine inspecting git worktree diffs and GitHub effect timestamps against `base_sha`, integrate into `jobs.py` finalizer and `dispatch.py`, and wire autonomous failover into milestone DAG execution.

**Tech Stack:** Python 3.10+ (stdlib, `git`, `sqlite3`, `pytest`), GitHub CLI (`gh`).

**Spec:** `docs/superpowers/specs/2026-09-27-invariant-1-effect-verified-completion-design.md`

## Global Constraints
- Mutating jobs with zero git diff and zero touched files MUST receive status `completed_without_changes` (never `succeeded`).
- Review/GH-write jobs without verified remote GitHub effects MUST receive `failed_noop_denied`.
- All commits MUST include trailer: `Co-Authored-By: Agy (Gemini) <noreply@antigravity.dev>`.
- 100% of existing test matrix (3,310+ tests) must remain green.

---

### Task 1: Job Status Taxonomy Extension

**Files:**
- Modify: `synlynk/jobs.py:20-60`
- Test: `tests/test_job_status_taxonomy.py`

**Interfaces:**
- Produces: `STATUS_COMPLETED_WITHOUT_CHANGES`, `STATUS_FAILED_NOOP_DENIED`, `STATUS_FAILED_VERIFICATION`, `ALL_JOB_STATUSES`

- [ ] **Step 1: Write the failing test**
Create `tests/test_job_status_taxonomy.py` asserting that new status constants exist, are distinct strings, and are included in `ALL_JOB_STATUSES` and status filtering helper functions.

- [ ] **Step 2: Run test to verify failure**
Run `pytest tests/test_job_status_taxonomy.py` and confirm `ImportError` / `AttributeError`.

- [ ] **Step 3: Implement status constants in `synlynk/jobs.py`**
Add status constants to `synlynk/jobs.py` and update validation regexes and status mapping dictionaries.

- [ ] **Step 4: Run test to verify pass**
Run `pytest tests/test_job_status_taxonomy.py` and confirm 100% pass.

- [ ] **Step 5: Commit changes**
Commit with subject `feat(jobs): add completed_without_changes and failed_noop_denied status constants`.

---

### Task 2: Pure Effect Verification Engine

**Files:**
- Create: `synlynk/verify_effects.py`
- Test: `tests/test_verify_effects.py`

**Interfaces:**
- Produces: `verify_job_effects(worktree_path: str, base_sha: str, task_class: str = "mutating", expected_gh_effect: Optional[str] = None, verification_cmd: Optional[str] = None) -> EffectVerificationResult`

- [ ] **Step 1: Write the failing test**
Create `tests/test_verify_effects.py` testing git diff detection against temporary git repositories (both empty and non-empty diffs), mock GitHub effect checks, and verification test execution.

- [ ] **Step 2: Run test to verify failure**
Run `pytest tests/test_verify_effects.py` and verify `ModuleNotFoundError`.

- [ ] **Step 3: Implement `verify_job_effects` in `synlynk/verify_effects.py`**
Implement diff calculation (`git diff --name-only base_sha..HEAD`), GitHub object verification via `gh` CLI or JSON API responses, and test runner subprocess execution.

- [ ] **Step 4: Run test to verify pass**
Run `pytest tests/test_verify_effects.py` and confirm all tests pass.

- [ ] **Step 5: Commit changes**
Commit with subject `feat(verify): implement verify_job_effects engine for diff and effect verification`.

---

### Task 3: Dispatch & Job Finalizer Integration

**Files:**
- Modify: `synlynk/jobs.py:2100-2250`
- Modify: `synlynk/dispatch.py:3300-3450`
- Test: `tests/test_effect_verified_completion.py`

**Interfaces:**
- Consumes: `verify_job_effects` from `synlynk.verify_effects`
- Produces: Enforced 3-part invariant inside `_finalize_job()` and `dispatch_agent()`

- [ ] **Step 1: Write the failing test**
Create `tests/test_effect_verified_completion.py` simulating exit 0 with empty diff, exit 0 with non-empty diff, and review dispatch without GH writes.

- [ ] **Step 2: Run test to verify failure**
Run `pytest tests/test_effect_verified_completion.py` and verify assertion failures (legacy behavior returns `succeeded`).

- [ ] **Step 3: Integrate `verify_job_effects` into `_finalize_job()` and `dispatch_agent()`**
Call `verify_job_effects()` before stamping job result; set `status = STATUS_COMPLETED_WITHOUT_CHANGES` when diff is empty on a mutating job.

- [ ] **Step 4: Run test to verify pass**
Run `pytest tests/test_effect_verified_completion.py` and confirm 100% pass.

- [ ] **Step 5: Commit changes**
Commit with subject `feat(dispatch): enforce effect-verified completion in job finalizer`.

---

### Task 4: Sentinel Alerting & CLI Status Badging

**Files:**
- Modify: `synlynk/sentinel.py`
- Modify: `synlynk/status.py`
- Modify: `synlynk/viz_views.py`
- Test: `tests/test_sentinel_noop_alert.py`

**Interfaces:**
- Produces: `TASK_NOOP_DENIED` sentinel alerts and amber `[NOOP]` HUD pills.

- [ ] **Step 1: Write the failing test**
Create `tests/test_sentinel_noop_alert.py` verifying that a `completed_without_changes` job generates a high-priority Sentinel alert.

- [ ] **Step 2: Run test to verify failure**
Run `pytest tests/test_sentinel_noop_alert.py` and verify failure.

- [ ] **Step 3: Implement Sentinel alert generation & CLI/Vizor status styling**
Update `sentinel.py` to trigger on no-op completions; update status formatters to style `completed_without_changes` with amber badge `[NOOP]`.

- [ ] **Step 4: Run test to verify pass**
Run `pytest tests/test_sentinel_noop_alert.py` and confirm pass.

- [ ] **Step 5: Commit changes**
Commit with subject `feat(sentinel): add TASK_NOOP_DENIED alerts and UI status formatting`.

---

### Task 5: Autonomous Milestone Failover Integration

**Files:**
- Modify: `synlynk/launch_dag.py`
- Test: `tests/test_milestone_effect_failover.py`

**Interfaces:**
- Produces: Autonomous harness failover when a DAG task completes without changes.

- [ ] **Step 1: Write the failing test**
Create `tests/test_milestone_effect_failover.py` testing that `synlynk run --milestone` detects `completed_without_changes` and automatically dispatches to secondary harness.

- [ ] **Step 2: Run test to verify failure**
Run `pytest tests/test_milestone_effect_failover.py` and verify failure.

- [ ] **Step 3: Implement failover logic in `launch_dag.py`**
Inspect job outcome in DAG runner; if `completed_without_changes`, retry with secondary harness up to retry limit.

- [ ] **Step 4: Run test to verify pass**
Run `pytest tests/test_milestone_effect_failover.py` and confirm pass.

- [ ] **Step 5: Commit changes**
Commit with subject `feat(dag): add autonomous harness failover on noop completion`.
