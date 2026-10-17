# Job-Status Truth Reconciliation & Oracle False-Negatives Design

Date: 2026-10-17  
Status: Approved (by Nikhil Soman, 2026-10-17)  
Related: gh:#2130, gh:#2136, gh:#2137, gh:#2309, `docs/rca/2026-10-08-LIVE-22-job-status-split-brain.md`

---

## 1. Motivation

Across recent dispatch batches (e.g. 2026-10-08 LIVE-22 and 2026-10-14 gh:#2309), dispatched review and merge jobs repeatedly completed real, verified GitHub work (PRs approved, PRs merged, issues closed), yet synlynk reported them as `TASK_DELIVERY_FAILED`, `FAILED_NOOP_DENIED`, or `unknown_contract`. In the gh:#2309 batch, 5 out of 6 dispatches exhibited false-negative terminal status verdicts.

This erodes operator trust, corrupts dispatch-wave telemetry, forces manual out-of-band `gh pr view` cross-checks, and risks re-running already-completed work.

---

## 2. Root Cause Analysis

Investigation of `synlynk/jobs.py`, `synlynk/verify_effects.py`, and `synlynk/job_truth.py` identified four structural flaws:

1. **Receipt & Diff Bias Against Zero-Diff Tasks:**
   Review and merge tasks naturally produce zero local git diffs in their worktrees. When a harness log does not start with the strict `SYNLYNK_TASK_RECEIVED: <hash>` line (common in headless review dispatches), `_check_task_receipt()` classifies the receipt as `absent`. Because git activity is zero and `gh_write_verified` is not yet populated, `_classify_task_delivery()` declares `hard_fail: True`, marking the job as `TASK_DELIVERY_FAILED`.

2. **Split-Brain & Permanent One-Shot Settlement:**
   `.synlynk/jobs.json` is classified immediately upon process exit via local heuristics in `_reconcile_jobs_unlocked()`. `daemon_jobs` in `state.db` is updated by the daemon via `_reconcile_terminal_jobs_json()`, which only touches rows in `running` status. If verification encounters a transient network error or returns `unknown`, `_settle_daemon_job_terminal()` freezes the legacy failure verdict permanently.

3. **Transcript Evidence Disconnect:**
   Dispatched review jobs often run `gh pr view` or `gh pr merge` and print the outcome in stdout. However, the classifier ignores the transcript evidence, relying entirely on post-hoc out-of-band queries.

4. **Oracle Contract Narrowness:**
   In `synlynk/job_truth.py`, `ensure_effect_contract()` maps operations to contracts using a narrow set of keywords (`review`, `comment`, `pr`, `merge`, `issue`). Combined operations like `review/merge` or `squash_merge` fall back to `legacy_unknown_contract`. In `decide_job_outcome()`, missing optional predicates cause `verified_remote` to evaluate to `False`, forcing an `unknown_contract` verdict.

---

## 3. Design Specification (Two-Stage Hybrid)

### 3.1 Zero-Diff Task Delivery Exemption
In `synlynk/jobs.py`, update `_task_delivery_has_corroborating_activity()`:
- If `task_class` or `task_type` is in `("review", "gh_write", "github_write", "merge")`, or `requires_gh_write` is True, do not treat zero git diffs as a lack of corroboration.
- When receipt status is `absent`, classify as `warn: True, hard_fail: False` for review/GH-write jobs.

### 3.2 Transcript Evidence Extraction
In `synlynk/jobs.py` and `synlynk/verify_effects.py`:
- Add `_extract_transcript_gh_evidence(log_text: str) -> dict`:
  - Scrapes log output for positive GitHub actions:
    - PR merge confirmation: `Squash and merge pull request #<N>`, `Merged #<N>`, or `gh pr merge ... --squash` success.
    - PR review approval: `Approved pull request #<N>`, `gh pr review ... --approve` success.
    - PR creation: `https://github.com/.../pull/<N>` URL output.
- If transcript evidence confirms the expected action and process exit code is 0, treat it as corroborating remote evidence immediately.

### 3.3 Provisional Pending Status & Bounded Retry
In `synlynk/jobs.py`:
- For jobs with `requires_gh_write=True`, `_reconcile_jobs_unlocked()` must not write terminal `TASK_DELIVERY_FAILED` while GitHub verification is pending.
- Status is held as `STATUS_PENDING_VERIFICATION` (`pending_verification`) until the daemon's verified check runs.
- In `_settle_daemon_job_terminal()`, if verification returns `unknown` or transient error, retry up to `_UNPUSHED_BRANCH_VERIFICATION_RETRY_CAP = 3` before settling terminal status.

### 3.4 Oracle Contract Expansion
In `synlynk/job_truth.py`:
- Expand `kinds` in `build_github_effect_contract()` to support:
  - `"review/merge"` -> `"github_pr_merge"`
  - `"squash_merge"` -> `"github_pr_merge"`
  - `"review_and_merge"` -> `"github_pr_merge"`
- In `decide_job_outcome()`, when positive remote evidence is present (via direct API or transcript receipt), do not allow `unknown_contract` to override verified remote work.

---

## 4. Test & Verification Plan

1. **Unit Tests:**
   - `test_review_job_without_local_diff_does_not_hard_fail_on_absent_receipt`
   - `test_extract_transcript_gh_evidence_detects_merge_and_review`
   - `test_provisional_status_set_for_unverified_gh_write_job`
   - `test_oracle_decide_job_outcome_accepts_review_merge_contract`
2. **Integration Verification:**
   - Simulate a review/merge job with 0 diff and absent receipt marker; verify status resolves to `completed` / `succeeded`.
   - Verify `synlynk jobs --all` reflects `completed` without requiring manual `gh pr view`.
