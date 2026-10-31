# Verification Report: `synlynk pr check <pr#>` Positional-Arg Syntax Fix (#713) vs Review-Dispatch Reliability (#714)

- **Date:** 2026-10-21
- **Task Reference:** `story-a3cb163f`
- **Related PRs & Issues:** #712, #713, #714, #929, #932, #1166, #1279, #1432
- **Author:** Agy (Gemini)

---

## 1. Executive Summary

| Verification Target | Assessment | Notes |
| :--- | :--- | :--- |
| Did #713 resolve the review-dispatch reliability findings in #714? | **NO** | #713 and #714 are orthogonal issues. #713 was merged on 2026-08-04, while #714 occurred 9 days later on 2026-08-13. |
| Status of #714 | **CLOSED** | Formally closed in v0.13.1 via RCA PR #929 (`docs/rca/2026-08-13-dispatched-pr-review-cancellation-714.md`). |
| Underlying Failure Modes in #714 | **RESOLVED** | Resolved subsequently by PR #1279 (Grok headless permissions) and PR #1432 (HEAD-SHA commit-pulls fallback for dispatch branches). |
| Residual Gaps | **DOCUMENTED** | 2 residual gaps identified regarding positional argument intolerance and sandboxed PR resolution. |

---

## 2. Chronological & Structural Divergence

### PR #713: The Positional Syntax Fix (2026-08-04)
- **Originating Bug (#712):** The generated `PR Review Discipline` SOP in directive files (`AGENTS.md`, `CLAUDE.md`, `GEMINI.md`) instructed agents:
  ```text
  2. The reviewer must run `synlynk pr check <pr#>`.
  ```
  However, `synlynk/cli.py` defined `pr check` with no positional argument (only `--pr <number>`). When reviewers or agents executed `synlynk pr check 711`, argparse raised `SystemExit: unrecognized arguments: 711`.
- **Shipped Change (commit `902f3804` in PR #713):**
  - Updated `synlynk/probe.py` (`_PR_REVIEW_SOP`, `_repair_pr_review_sop`, and `_repair_sops_only`) to replace the broken command string with:
    ```text
    2. From within the PR's own checked-out worktree/branch, the reviewer must run `synlynk pr check` so it can auto-detect the PR via git/gh context.
    ```
  - Added test `test_pr_review_discipline_instructions_say_synlynk_pr_check_without_pr_number` in `tests/test_agent_quota_tracking.py` explicitly asserting that `parser.parse_args(["pr", "check", "711"])` raises `SystemExit`.
  - **Critical Note:** PR #713 did *not* make `synlynk pr check` accept a positional argument, nor did it modify dispatch execution mechanics. It only updated the SOP instructions to match the zero-argument parser contract.

### Issue #714: Review-Dispatch Reliability Findings (2026-08-13)
Nine days after PR #713 landed, review dispatches across the fleet suffered severe reliability failures:
1. **Grok Headless Cancellation:** Headless Grok review dispatches aborted with `stopReason: "cancelled"` after 4 to 6 active review turns.
2. **Agy Timeouts & Worktree Drift:** Agy review dispatches failed with internal harness timeouts (`timeout waiting for response`) or missing scratch-worktrees.
3. **Dispatch Branch Auto-Detection Mismatch:** Review jobs check out `dispatch/<harness>/job-<id>`, which has no PR of its own. Running `synlynk pr check` with zero arguments failed because `gh pr view` cannot detect the associated PR from a dispatch job branch.
4. **Initial RCA (PR #929, v0.13.1):** `docs/rca/2026-08-13-dispatched-pr-review-cancellation-714.md` investigated whether synlynk's 30-minute idle-output stall killer was responsible. It proved conclusively that the stall killer did not kill these jobs, ruling out synlynk dispatch stall thresholds, but leaving the upstream cause of `stopReason: "cancelled"` open.

---

## 3. What Actually Resolved the #714 Findings

The review-dispatch reliability issues discovered in #714 were resolved through separate, targeted engineering interventions:

1. **Grok Compound Command Auto-Cancellation (PR #1279, 2026-08-30):**
   - Reverse-engineering the Grok binary (`crates/codegen/xai-grok-workspace/src/permission/manager/bash_grants.rs`, `exec_risk.rs`) proved that `--permission-mode dontAsk` caused Grok's internal bash AST classifier to auto-cancel compound shell commands without prompting the operator.
   - PR #1279 resolved this across #714, #880, #1038, and #1166 (LIVE-8) by emitting `--always-approve` whenever `run:shell` or `run:tests` is granted.
2. **Dispatch Worktree PR Auto-Detection (#1432):**
   - Implemented `_current_pr_number_from_head_sha()` in `synlynk/pr_multiplier.py` to query `repos/{owner}/{repo}/commits/{sha}/pulls` when `gh pr view` fails on `dispatch/...` branches.
   - Added explicit `--pr <number>` flag documentation for review dispatch job branches.
3. **Failure Classification Hardening:**
   - Separated harness internal timeouts (`HARNESS_INTERNAL_TIMEOUT`) from synlynk idle log kills (`STALL_NO_OUTPUT`).

---

## 4. Residual Gaps

While issue #714 is closed and its failure modes are resolved, two residual gaps remain in the CLI and workflow contract:

### Residual Gap 1: Positional Argument Intolerance in `synlynk pr check`
- **Description:** `synlynk pr check` strictly requires `--pr <number>` and rejects positional arguments (e.g. `synlynk pr check 711`).
- **Impact:** Human operators and newly initialized agent sessions frequently attempt `synlynk pr check 711` out of CLI intuition. While guarded by `test_pr_review_discipline_instructions_say_synlynk_pr_check_without_pr_number`, supporting an optional positional argument (`nargs="?"`) that falls back to `--pr` would improve ergonomic resilience.

### Residual Gap 2: Sandboxed PR Auto-Detection in Dispatch Branches
- **Description:** On dispatch job branches (`dispatch/<harness>/job-<id>`), `_current_pr_number()` falls back to `gh api repos/{owner}/{repo}/commits/{sha}/pulls`. In sandboxed execution environments where network access to `api.github.com` is denied, auto-detection fails with exit code 1 unless `--pr <number>` is passed explicitly.
- **Remediation Recommendation:** Dispatch templates for review jobs should inject `--pr <target_pr_number>` directly into the review job's prompt instructions to prevent sandbox network dependency during the QA gate check.

---

## 5. Conclusion & Closeout

- PR #713 did **not** resolve the review-dispatch reliability findings in #714.
- Issue #714 was closed by RCA PR #929 and definitively mitigated by PR #1279 and PR #1432.
- No further code changes to `_PR_REVIEW_SOP` are required at this time; residual ergonomics are documented above.
