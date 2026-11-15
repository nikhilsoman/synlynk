# Implementation Plan: Universal GOVERNS Enforcement

> Status: Approved Implementation Plan
> Date: 2026-11-16
> Tracking: Issue #5119, Issue #1990, story-ae619721, goal-eacab0dc
> Author: AGY (Gemini)

---

## Proposed Execution Order

- [ ] Task 1: Add preflight hard-fail logic in `synlynk/dispatch.py` conditioned on `require_linked_goal_mode`
- [ ] Task 2: Implement loop goal operating story check in `synlynk/doctor.py`
- [ ] Task 3: Promote `require_linked_goal_mode` to `"enforce"` in `.synlynk/policy.json`
- [ ] Task 4: Author comprehensive unit tests in `tests/test_universal_governs_enforcement.py`
- [ ] Task 5: Run full verification suite and verify clean test passage

---

## Detailed Task Breakdown

### Task 1: Preflight Gate Enforcement in `synlynk/dispatch.py`
- In `preflight_dispatch()`:
  When `_task_hint and not linkage_resolvable`:
  Import `gate_mode` from `synlynk.policy_gates`.
  If `gate_mode("governs_authority", "require_linked_goal_mode") == "enforce"`:
    Return `{"passed": False, "sentinel": "GOVERNS_LINKAGE_MISSING", "reason": "Dispatch rejected: task is not linked to a GOVERNS story, issue, or PR. Link with --story <id>, --issue <num>, or --pr <num>."}`
  Else:
    Call `_emit_missing_governs_linkage_warning()`.

### Task 2: Loop Goal Operating Story Doctor Check in `synlynk/doctor.py`
- In `synlynk/doctor.py`:
  Add `check_loop_goals_operating_stories(conn, fix=False) -> list[DoctorFinding]`:
  Query `SELECT goal_id, outcome FROM goals WHERE kind='loop' AND status='active'`.
  For each goal:
    Check `SELECT COUNT(*) FROM stories WHERE goal_id=? AND status NOT IN ('done', 'cancelled')`.
    If count == 0:
      Emit doctor finding alerting that the loop goal has no active operating story.
  Register this check in the doctor diagnostics runner.

### Task 3: Policy Promotion in `.synlynk/policy.json`
- In `.synlynk/policy.json`:
  Update `governs_authority.require_linked_goal_mode` to `"enforce"`.

### Task 4: Tests in `tests/test_universal_governs_enforcement.py`
- Test cases:
  1. `test_dispatch_preflight_blocks_when_linkage_missing_in_enforce_mode`: asserts `preflight_dispatch` returns `passed=False` with sentinel `GOVERNS_LINKAGE_MISSING`.
  2. `test_dispatch_preflight_warns_when_linkage_missing_in_observe_mode`: asserts `preflight_dispatch` passes with warning in observe mode.
  3. `test_dispatch_preflight_passes_with_story_or_issue_or_pr`: asserts `preflight_dispatch` passes when linked.
  4. `test_doctor_detects_loop_goal_without_active_story`: asserts doctor check detects unstaffed loop goals.
  5. `test_doctor_passes_when_loop_goal_has_active_story`: asserts doctor check passes when staffed.

### Task 5: Verification
- Execute `pytest tests/test_universal_governs_enforcement.py tests/test_dispatch.py tests/test_doctor.py -v`.
