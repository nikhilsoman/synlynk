# Job-Status Truth Reconciliation & Oracle False-Negatives Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate false-negative job status labels (`TASK_DELIVERY_FAILED`, `FAILED_NOOP_DENIED`, `unknown_contract`) for review, merge, and GH-write dispatches that produce genuine remote effects without local git diffs.

**Architecture:** Exempt zero-diff review/merge tasks from local git-diff corroboration requirements on missing receipts; parse job transcripts for positive GitHub outcome receipts; introduce provisional `pending_verification` status before terminal settle; and expand the `job_truth` contract vocabulary to include compound review/merge actions.

**Tech Stack:** Python 3.10+, SQLite, Pytest, GitHub CLI (`gh`).

**Spec:** `docs/superpowers/specs/2026-10-17-job-status-truth-reconciliation-design.md`

## Global Constraints
- Preserve backward-compatibility for non-GH-write mutating tasks (Invariant 1: exit 0 + diff > 0 required).
- Do not commit directly to main; work in task-scoped branch and verify cleanly with pytest.
- Maintain documentation integrity and preserve existing comments.

---

### Task 1: Zero-Diff Exemption & Transcript Evidence Extraction

**Files:**
- Modify: `synlynk/jobs.py:590-675`
- Modify: `synlynk/verify_effects.py:155-220`
- Test: `tests/test_jobs.py`, `tests/test_verify_effects.py`

**Interfaces:**
- Produces: `_extract_transcript_gh_evidence(log_text: str) -> dict[str, Any]`
- Modifies: `_task_delivery_has_corroborating_activity(job: Optional[dict], git_state, log_text: Optional[str] = None) -> bool`

- [ ] **Step 1: Write failing test in `tests/test_verify_effects.py` for review task with zero diff and absent receipt**
```python
def test_review_task_with_zero_diff_and_absent_receipt_succeeds_with_transcript_evidence():
    from synlynk.verify_effects import verify_job_effects
    log = "Review completed.\nApproved pull request #2306\n"
    res = verify_job_effects(
        worktree_path=None,
        task_class="review",
        expected_gh_effect="review_posted",
        exit_code=0,
        structured_telemetry={"available": False},
        gh_verify_kwargs={"log_text": log},
    )
    assert res.status != "task_delivery_failed"
    assert res.status != "failed_noop_denied"
```

- [ ] **Step 2: Run test to verify it fails**
Run: `pytest tests/test_verify_effects.py -k test_review_task_with_zero_diff`

- [ ] **Step 3: Implement `_extract_transcript_gh_evidence` and update `_task_delivery_has_corroborating_activity`**
In `synlynk/jobs.py` and `synlynk/verify_effects.py`:
- Add transcript parsing for positive GitHub merge/review patterns.
- Allow zero diff if task class is review/gh_write and transcript evidence or remote check confirms activity.

- [ ] **Step 4: Verify test passes**
Run: `pytest tests/test_verify_effects.py -k test_review_task_with_zero_diff`

---

### Task 2: Provisional Pending Status on Unverified GH Writes

**Files:**
- Modify: `synlynk/jobs.py:2014-2750`
- Test: `tests/test_jobs.py`

- [ ] **Step 1: Write failing test for unverified GH-write not settling to failure prematurely**
```python
def test_reconcile_jobs_unlocked_holds_pending_verification_for_unverified_gh_write(tmp_path):
    from synlynk.jobs import _reconcile_jobs_unlocked, STATUS_PENDING_VERIFICATION
    ...
```

- [ ] **Step 2: Implement provisional status in `_reconcile_jobs_unlocked`**
Hold `status = "pending_verification"` when `requires_gh_write=True` and no definitive check has completed.

- [ ] **Step 3: Verify tests pass**
Run: `pytest tests/test_jobs.py -k test_reconcile_jobs_unlocked`

---

### Task 3: Expand Contract Kinds & Evidence Overrides in `job_truth.py`

**Files:**
- Modify: `synlynk/job_truth.py:130-245`
- Test: `tests/test_job_truth.py`

- [ ] **Step 1: Write failing test in `tests/test_job_truth.py` for `review/merge` operation**
```python
def test_ensure_effect_contract_supports_review_merge():
    from synlynk.job_truth import build_github_effect_contract
    c = build_github_effect_contract("job-123", operation="review/merge", target="2306")
    assert c["kind"] == "github_pr_merge"
```

- [ ] **Step 2: Add `"review/merge"`, `"squash_merge"`, `"review_and_merge"` to `build_github_effect_contract`**
Update `synlynk/job_truth.py:130-140`.

- [ ] **Step 3: Allow verified remote evidence to override unknown contract**
In `decide_job_outcome()`, prioritize confirmed remote evidence over fallback `unknown_contract`.

- [ ] **Step 4: Run test to verify passes**
Run: `pytest tests/test_job_truth.py`

---

### Task 4: Full Verification & Integration Test

- [ ] **Step 1: Run complete test suite for affected modules**
Run: `pytest tests/test_jobs.py tests/test_verify_effects.py tests/test_job_truth.py -q`

- [ ] **Step 2: Verify zero false-negatives across all 3 test files**
