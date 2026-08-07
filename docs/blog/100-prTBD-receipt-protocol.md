---
title: "The Receipt Protocol — Detection-Only Delivery Confirmation for Dispatched Tasks"
date: 2026-08-07
series: "Building the OS for Multi-Agent Development"
post: 100
pr: "TBD"
status: open
---

## The Broader Goal at the End of the Previous PR

Issue #720 identified three deferred sub-projects growing out of the dispatch fail-closed
work (design doc: `docs/superpowers/specs/2026-08-07-dispatch-fail-closed-task-validation-design.md`).
Sub-project 1 — fail-closed empty-task validation — shipped in PR #759: `synlynk dispatch`
now refuses to send an empty or whitespace-only task string to an agent, closing a class of
silent no-op dispatches. That left two deferred pieces: a receipt protocol confirming an
agent actually *received* the task text it was dispatched, and (still outstanding) a third
sub-project not covered by this PR.

The gap sub-project 1 didn't close: fail-closed validation only guards against Synlynk
sending nothing. It says nothing about whether the agent's own CLI harness actually
delivered that non-empty task to the model before doing work — a truncated prompt pipe, a
CLI flag mismatch, or a race in headless invocation could all still result in an agent
starting "work" against a task it never actually read.

## Strategic Shifts in This PR (if any)

None. This PR is exactly the sub-project 2 scope described in #720 and the approved design
spec (`docs/superpowers/specs/2026-08-07-receipt-protocol-design.md`): cross-CLI
`task_received` confirmation between Synlynk and each headless harness, with digest matching
and a new `task_delivery_failed` job status. No scope was added or cut during implementation.

## What This PR Shipped

The core mechanism is deliberately dumb: **detection-only, no protocol negotiation with the
agent CLI**. Synlynk prepends a fixed instruction to every dispatched prompt asking the agent
to print `SYNLYNK_TASK_RECEIVED: <task_sha256>` as its literal first line of output, then
Synlynk greps for that line in the captured log after the fact. No handshake, no blocking
wait, no changes to any agent CLI's own protocol — just an echo Synlynk can verify or fail to
find.

Seven tasks landed, each dispatched independently to Codex or Agy via `synlynk dispatch
<agent> --task "..." --force-agent --context-mode full --base chore/receipt-protocol-design`,
verified against its own diff and test run before merging locally into the feature branch
(consolidating into this one PR rather than the per-task auto-opened PRs, which were closed
as superseded):

1. **`_render_task_receipt_instruction(task_sha256)`** in `synlynk/dispatch.py` — builds the
   prompt-injection text; wired into `_format_prompt_for_agent()` for all three prompt-shape
   branches (Claude, Codex, generic) so it's agent-agnostic by construction.
2. **`_check_task_receipt(log_text, task_sha256)`** in `synlynk/jobs.py` — classifies a job's
   captured log into `ok` (marker is the literal first non-blank line), `late` (marker present
   but not first), `mismatch` (a receipt marker is first but the digest is wrong), or `absent`.
3. **`_classify_task_delivery(receipt_status, has_corroborating_activity)`** — the
   false-positive guard. A receipt failure alone doesn't hard-fail a job: if the job's
   worktree shows real git activity (`has_activity` or `remote_has_activity`), the job is
   downgraded to a non-blocking WARN instead of `task_delivery_failed`. This mirrors the
   existing `permission_denied` false-positive lesson from job-b88e0f92 — a status label
   should never override direct evidence of real, correctly-scoped work.
4. **Waitpid-reaped reconciliation wiring** — the classification is applied in the
   `if waitpid_reaped:` branch of `_reconcile_jobs()`, setting `job["status"] =
   "task_delivery_failed"` on hard failure or writing a `TASK_RECEIPT_WARN` sentinel alert on
   soft failure.
5. **Dead-pid reconciliation wiring** — the structurally parallel edit in the `except
   ProcessLookupError:` branch, since a job whose process died before Synlynk could reap it
   needs the same classification applied independently (different code path, same log-based
   evidence).
6. **`live_agent_receipt_check()` in `synlynk/fleet.py`** — a new Tier-2 `selftest --matrix`
   cell (`live_receipt:<agent>`) that runs one real headless CLI turn per Core-4 agent
   (Claude, Codex, Grok, Agy) with a fixed test digest and checks compliance live, not just in
   unit tests against captured logs. Wired into `run_matrix_live()`'s existing budget-loop
   pattern (mirroring the `live_agent_smoke` cell's `mock=True` stub and `spent`/`budget_usd`
   accounting rather than introducing a divergent loop shape).
7. **README documentation** — a short paragraph after the existing fail-closed guard section
   explaining the receipt marker, the `task_delivery_failed` status, and the WARN
   corroboration fallback.

Test coverage: 80 tests across `tests/test_dispatch.py` and `tests/test_jobs.py` covering the
receipt-detection state machine (ok/late/mismatch/absent/none), the corroboration
classification (hard-fail/warn/clean), and both reconciliation branches (waitpid-reaped and
dead-pid) with a real local-git-repo fixture for the activity-corroboration case; plus 4 new
tests in `tests/test_fleet_operability.py` for the live matrix cell. Full combined suite: 108
passing.

Two operational lessons surfaced during execution, both resolved without losing work: a
`permission_denied` status on the dead-pid-branch task (job-70a6ef9a) and again on the
selftest-matrix task (job-47fe2f30) turned out to be false positives — direct inspection of
each job's worktree diff and a live test run confirmed correctly-scoped, spec-matching
commits in both cases, consistent with the repo's standing "never trust `synlynk jobs` status
alone" memory. Separately, a merge/push cycle for one task silently no-op'd because the Bash
tool's working directory had persisted inside a job's own worktree from a prior `cd` — caught
immediately via `git log origin/<branch> --oneline -1` disagreeing with the expected tip, and
recovered by re-verifying `pwd`/`git branch --show-current` before retrying the merge.

## Brainstorm Visuals Used

None — this sub-project's design was scoped directly in the #720 spec and design doc from a
prior brainstorming session; no new visual companion session was run for this PR.

## What This Achieved on the Path to Autonomy

A dispatched job's completion status can now distinguish "the agent did the work" from "the
agent's CLI never actually saw the task" — without that distinction, a silently-dropped
prompt looks identical to a successful no-op job, which is exactly the kind of failure mode
autonomous dispatch loops can't self-correct from if nothing flags it. The WARN corroboration
guard keeps this from becoming a new source of false-positive noise: a missing receipt marker
next to a real, verifiable commit is a signal worth surfacing, not a reason to discard
correct work.

## Strategic Note: The Goal at the End of This PR

Sub-project 2 of #720 is complete. Sub-project 3 (not yet scoped in this PR) remains
outstanding per the original #720 breakdown — the next PM pass should confirm what it covers
and whether it's still needed given the receipt protocol and fail-closed guard now both
shipped. Separately, the `selftest --matrix` receipt cell adds real (budgeted) API cost per
run across all four Core-4 agents — worth watching in `project-docs/costs.md` once this ships
and starts running against CI or scheduled selftest invocations.
