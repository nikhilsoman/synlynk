# Design Spec: Universal GOVERNS Enforcement

> Status: Approved Design Spec
> Date: 2026-11-16
> Tracking: Issue #5119, Issue #1990, story-ae619721, goal-eacab0dc
> Author: AGY (Gemini)

---

## 1. Intent & Strategic Context

In the synlynk governance model, every dispatched task and pull request must anchor into the living GOVERNS graph (`goal -> story -> task/PR -> verification -> closeout`). Unanchored ad-hoc executions lead to unindexed orphan jobs (`[unknown] claude dispatched`), loss of cost provenance, degraded TPM sweep observability, and unverified workspace drift.

Under **Goal `goal-eacab0dc`** and **Issue #5119** / **Issue #1990**:
> *"Universal GOVERNS enforcement: every prompt/action in a synlynk-managed workspace belongs to something above it and triggers something below it."*

While a loud warning was introduced on 2026-10-06 (`"GOVERNS linkage missing — dispatch proceeding, but this will hard-fail once #1990 ships"`), the hard-fail enforcement gate remained deferred in observe mode. This design completes and operationalizes the hard-fail gate across dispatch preflight, policy configuration, `pr check`, and TPM/doctor loop goal health.

---

## 2. Current Architecture & Identified Gaps

### 2.1 Dispatch Preflight Soft Warning
In `synlynk/dispatch.py:4296-4297`:
```python
if _task_hint and not linkage_resolvable:
    _emit_missing_governs_linkage_warning()
```
When a task has no `--story`, `--issue`, `--pr`, or prompt-embedded issue/PR reference, it emits a warning to `sentinel.md` and standard error, but allows the dispatch subprocess to proceed.

### 2.2 Policy Enforcement Mode in Observe State
In `.synlynk/policy.json`:
```json
"governs_authority": {
  "require_linked_goal": true,
  "require_linked_goal_mode": "observe"
}
```
Because the mode is set to `"observe"`, `synlynk pr check` and preflight routines treat unlinked GOVERNS violations as non-blocking soft warnings.

### 2.3 Loop Goal Operating Story Invariant
Per the acceptance criteria of `goal-eacab0dc`:
> *"every kind=loop goal has a live loop story; doctor/tpm sweep fail a loop goal with no operating story."*

Currently, `synlynk doctor` checks databases, remotes, and dirty worktrees, but does not assert that active `kind="loop"` goals possess a live, non-terminal story (`status != 'done' and status != 'cancelled'`).

---

## 3. Proposed Architecture & Contract Changes

### 3.1 Preflight Hard-Fail Gate (`synlynk/dispatch.py`)
1. In `preflight_dispatch()`:
   When `_task_hint` is provided and `linkage_resolvable` is `False`:
   Check `gate_mode("governs_authority", "require_linked_goal_mode")`.
   - If mode is `"enforce"`:
     Return:
     ```python
     return {
         "passed": False,
         "sentinel": "GOVERNS_LINKAGE_MISSING",
         "reason": (
             "Dispatch rejected: task is not linked to a GOVERNS story, issue, or PR. "
             "Provide --story <id>, --issue <num>, or --pr <num>."
         ),
     }
     ```
   - If mode is `"observe"`:
     Emit warning via `_emit_missing_governs_linkage_warning()` and continue.
2. In `dispatch_agent()`:
   If `preflight["passed"]` is `False` with sentinel `"GOVERNS_LINKAGE_MISSING"`, immediately fail closed:
   Print error details and raise `RuntimeError(preflight["reason"])` before creating worktrees or launching harness processes.

### 3.2 Policy Promotion (`.synlynk/policy.json`)
Promote `governs_authority.require_linked_goal_mode` from `"observe"` to `"enforce"`:
```json
"governs_authority": {
  "require_linked_goal": true,
  "require_linked_goal_mode": "enforce",
  "note": "100% GOVERNS adherence required per Nikhil's 2026-10-04 hardening — every dispatched job must link a GOVERNS goal/story. Hard-fail enforcement shipped via #1990/#5119."
}
```

### 3.3 PR Check Enforcement (`synlynk/db.py`)
`cmd_pr_check` already calls:
```python
governs_eval = _evaluate_gate(
    conn, pr_number=pr_number, gate="governs_authority",
    mode_key="require_linked_goal_mode",
    verdict=classify_governs_violations(governs_violations),
)
```
When `require_linked_goal_mode` is `"enforce"`, `governs_eval.should_block` evaluates to `True`, blocking `gh pr merge` with `🚫 [PR CHECK BLOCKED] dispatched jobs missing linked GOVERNS story/goal` and exit code 1.

### 3.4 Loop Goal Health Check (`synlynk/doctor.py`)
Add a new check `check_loop_goals_operating_stories(conn)`:
1. Query all active `kind="loop"` goals in the database.
2. For each loop goal, query `stories` for at least one active story (`goal_id = ? AND status NOT IN ('done', 'cancelled')`).
3. If any active loop goal lacks an active story, return a failing doctor check item:
   `"Loop goal '<goal_id>' has no active operating story in stories table."`

---

## 4. Verification & Testing Contracts

1. **Unit Tests (`tests/test_universal_governs_enforcement.py`):**
   - Test that unlinked dispatch preflight fails closed when `require_linked_goal_mode == 'enforce'`.
   - Test that unlinked dispatch preflight soft-warns when `require_linked_goal_mode == 'observe'`.
   - Test that dispatch preflight succeeds when `--story`, `--issue`, or `--pr` is provided.
   - Test that `cmd_pr_check` blocks when unlinked jobs are present under enforce mode.
   - Test that `check_loop_goals_operating_stories` fails when a loop goal has no operating story and passes when one exists.
2. **Regression Testing:**
   - Run `pytest tests/test_dispatch.py tests/test_governs_gate.py tests/test_doctor.py`.
   - Run full verification suite.
