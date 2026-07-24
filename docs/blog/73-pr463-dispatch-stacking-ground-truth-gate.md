---
title: "PR #463 — Dispatch Stacking + Ground-Truth Merge Gate"
date: 2026-07-23
series: "Building the OS for Multi-Agent Development"
post: 73
pr: "#463"
merged: 2026-07-23
---

## The Broader Goal at the End of the Previous PR

v0.13.0 ("Discoverability & Accounting", tag'd 2026-07-22 off PR #442) had just shipped the measurement and cost-visibility cluster — `synlynk status --json` as Vizor's data contract, payment-model-aware cost accounting, capability-sweep taxonomy. The dispatch mechanism itself — `synlynk dispatch <agent>` spawning Codex/Gemini/Grok jobs in isolated git worktrees — was functionally stable but had a known, unaddressed failure mode: every job branched fresh off `origin/main` regardless of what feature branch it was actually being dispatched *for*. That meant reviewers merging a sequence of task commits into a long-lived feature branch hit add/add conflicts on every file a prior task had already touched, requiring manual `--ours`/`--theirs` reconciliation each time. Job completion summaries were also not trustworthy — `synlynk jobs` self-reported status had produced false `PERMISSION_DENIED` verdicts on fully correct, committed work more than once.

## Strategic Shifts in This PR

None — this PR is the direct, previously-scoped fix for a problem identified and speced in the prior session: `docs/superpowers/specs/2026-07-22-dispatch-stacking-ground-truth-gate-design.md`. It's explicitly Phase 1 of that design; Phase 2 (footprint locking, DAG-based wave scheduling) stays out of scope per the spec's own Rollout section. What did shift, informally, was priority: partway through building this exact feature, the same misreporting pattern this PR's gate mechanism is meant to guard against recurred three more times during dispatch of the PR's own tasks — which is what prompted filing issue #461 mid-session to track it as a standing investigation rather than treating each instance as a one-off.

## What This PR Shipped

Nine tasks, each dispatched as its own `synlynk dispatch codex` job and ground-truth verified (`git log` / `git diff --stat` inside the job's own worktree, never the self-reported completion summary) before being cherry-picked onto the feature branch:

- **Base resolution** (`synlynk/dispatch.py`): dispatch now auto-detects the current non-main branch as the job's base, gated by a new `dispatch.stacking` config value (`"auto"` / `"always"` / `"never"`), with an explicit `--base` CLI override for cases where auto-detection picks the wrong branch.
- **Tip-SHA anchoring**: `_create_job_worktree` resolves the chosen base to its exact tip commit SHA at creation time and records both `base_branch` and `base_sha` on the job dict — the anchor a job worktree is created from is now an immutable fact recorded once, not re-derived later.
- **Ground-truth suite gate**: a new `dispatch.gate_suite_cmd` config field lets the harness run the real test suite inside the job's worktree after the job process exits, independent of anything the job itself reports. `suite_result` (parsed pass/fail counts) is persisted on the job record; any job with `suite_result.failed > 0` is forced to `needs_fix` status — it can no longer land as silently `completed` just because the underlying CLI process exited 0.
- **STALE_BASE detection**: before a job is considered merge-eligible, a `git merge-base --is-ancestor` check confirms the base branch hasn't advanced past the SHA the job was anchored to. A stale base surfaces as a distinct status recommending re-dispatch rather than a forced merge.
- **Summary surface**: `synlynk jobs` and `synlynk logs` output now render `base:` and `suite:` lines wherever those fields are present, across all four call sites that build job summaries.
- **Integration tests**: one test simulates two sequential dispatched jobs against a real temp-repo feature branch and asserts the second job's `base_sha` matches the branch tip *after* the first job's merge, and that the merge produces zero conflicts. A second test exercises `_apply_dispatch_gate` end-to-end against a worktree seeded with a deliberately failing test, asserting the job downgrades to `needs_fix` with a populated `suite_result` — no mocking of the gate function itself, so the parsing and status-downgrade wiring is proven against a real pytest run.

Test suite: 1345 passed, 2 skipped, green after every task, both inside each job's own worktree and on the parent branch after merge. Squashed to `de86676` on 2026-07-23.

## Brainstorm Visuals Used

None — this design was scoped through a text-only brainstorming session (per the spec at `docs/superpowers/specs/2026-07-22-dispatch-stacking-ground-truth-gate-design.md`); no visual companion was used.

## What This Achieved on the Path to Autonomy

This is a load-bearing fix for the multi-agent dispatch loop itself, not a feature built on top of it. Stacked dispatch branches remove the structural cause of add/add merge conflicts for any plan executed as a sequence of dispatched tasks — which is the default execution mode for essentially all Python/CLI/test work in this repo per the locked capability-based task allocation. The ground-truth suite gate converts "job self-reports done" from an assumption into a checked fact: a job can no longer reach `completed` status while leaving the test suite red, closing off exactly the kind of silent regression that a prior job (defensive `None`-handling work, discovered necessary but wrongly rejected by a reviewer without full test-suite visibility) had exposed as a review-time blind spot. Ironically, this feature was itself built using the dispatch mechanism it improves — 9 Codex jobs dispatched under the *old*, pre-fix stacking behavior, which is exactly why the ground-truth verification discipline mattered so much building it: three of those nine jobs were misreported by `synlynk jobs` as `PERMISSION_DENIED` despite being fully correct, complete, committed work, each one only caught by checking `git log`/`git diff --stat` directly in the job's own worktree instead of trusting the summary.

## Strategic Note: The Goal at the End of This PR

Phase 1 (stacking + gate) is live; Phase 2 (footprint locking, wave scheduling for parallel dispatch) remains explicitly deferred. The PR's own test plan flags the real next milestone as unchecked: "First real usage: dispatch the remaining rollback-mechanism plan tasks against this mechanism and confirm zero add/add conflicts" — the rollback-mechanism plan (Tasks 1-4 landed earlier, Tasks 5-9 outstanding) is the natural first consumer of stacked dispatch in production. Separately, issue #461 (filed mid-session, tracking the recurring `PERMISSION_DENIED`/files-touched-drift misreporting pattern this PR's own build surfaced three more instances of) remains open and unaddressed — the ground-truth suite gate closes one blind spot (silent test regressions), but the underlying job-status self-reporting unreliability that makes manual `git log` verification necessary on every single dispatch is still unresolved.
