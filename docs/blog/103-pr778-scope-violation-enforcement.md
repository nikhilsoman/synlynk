---
title: "PR #778 — Scope Violation Enforcement: Making --scope-paths Mean Something"
date: 2026-08-08
series: "Building the OS for Multi-Agent Development"
post: 103
pr: "#778"
merged: 2026-08-08
---

## The Broader Goal at the End of the Previous PR

PR #770/#771 closed the first of three sub-projects under issue #769 (itself born from issue #720's
six-item hardening checklist): the permission-denied classifier fix, which stopped a live false-positive
pattern by corroborating denial-signatures against real worktree git activity before trusting them. That
left two sub-projects on the board — safe-caller-construction docs (not yet started), and this one: scope
enforcement for design-only/docs-only dispatches.

The gap it targets is specific. A dispatch's `--task` text can *ask* an agent to touch only
`docs/superpowers/specs/**`, but nothing before this PR checked whether the agent actually stayed inside
that boundary. A design-only job could drift into editing `synlynk/jobs.py` and still get auto-finalized,
pushed, and turned into a PR — the same unconditional path every other completed job takes.

## Strategic Shifts in This PR

None of substance. The design went through two factual corrections during brainstorming — first, that
`_resolve_dispatch_permissions()` governs the *dispatched agent's own* tool permissions, not synlynk's
post-hoc PR-creation call (so the real enforcement point had to be `_finalize_completed_worktree_job()`,
not the permissions resolver); second, that PR #768 never actually added a "receipt-compliance" cell to
`fleet.py`'s `run_matrix_dry()` — that precedent was fabricated in an early spec draft and had to be
struck before the plan was written, since a plan task built against it would have targeted code that
doesn't exist. Both corrections narrowed the design to what the codebase actually supports rather than
shifting its goal.

## What This PR Shipped

A new repeatable `--scope-paths <glob>` flag on `synlynk dispatch`, parallel to the existing
`--requires`/`--grant` flags. It's stored the same way every other ad-hoc job field is stored — jobs
persist as a plain JSON array via `_load_jobs()`/`_save_jobs()`, so `scope_paths` just becomes one more
key on the job dict with no schema migration.

Enforcement happens in two places:

1. **`_inspect_worktree_git_state()`** gained a `changed_files` field — the union of `git diff --name-only
   base_commit..HEAD` and any dirty working-tree paths, reusing the existing
   `_collect_worktree_status_paths()` helper.
2. **A new `_check_scope_compliance()` helper** (`fnmatch`-based) is wired into both existing
   reconciliation call sites in `jobs.py` (waitpid-reaped and dead-pid branches — the same two places the
   permission-denied and task-receipt checks already run). When a job declares `scope_paths` and its
   actual changed files drift outside every declared glob, the job's status is set to `SCOPE_VIOLATION`
   and `_finalize_completed_worktree_job()`/`_apply_dispatch_gate()` are skipped entirely — no commit, no
   push, no PR. The worktree is left intact for inspection, matching the repo's flag-don't-destroy
   posture. A compliant scope-declared job still pushes normally, but `_maybe_open_worktree_pr()` is
   skipped by default unless `--requires-gh-write` was also passed — reusing that existing flag rather
   than introducing a new grant type.

Tests: unit coverage for `_check_scope_compliance()` (single glob, multiple globs, an out-of-scope file,
the empty-scope no-op case) plus four reconciliation-level tests mirroring the existing `test_reconcile_*`
fixture style — violation blocks push/PR, in-scope-only reconciles to `completed` and pushes without a PR,
`--requires-gh-write` overrides the PR skip, and jobs with no `scope_paths` declared are unaffected
(the regression guard, given how much of the reconciliation path is shared).

One real bug surfaced during execution, not in the design: the dispatched README-documentation task
initially inserted its new `--scope-paths` and `scope_violation_files` docs *inside* the
`<!-- commands:start -->...<!-- commands:end -->` block that `scripts/generate_command_docs.py`
regenerates and `tests/test_docs_sync.py` asserts against verbatim. The full suite caught it
(`README.md's command section is stale`); a follow-up dispatch moved both subsections below the
`commands:end` marker, which fixed the test and left the generated block untouched.

The branch also needed reconciling against `origin/main`, which had moved five commits ahead during
this work (PRs #768, #770, #771, #762, #772). One add/add conflict in `tests/test_jobs.py` — both sides
had appended new test functions immediately after the same import block, no content overlap — resolved
by keeping both blocks. Full suite after merge: 1730 passed, 2 skipped.

## Brainstorm Visuals Used

None — this design was entirely text/API-shape, no visual companion was used.

## What This Achieved on the Path to Autonomy

This closes the loop between *asking* an agent to stay in scope and *enforcing* it. Before this PR,
scope was a request embedded in prose; a hallucinating or overreaching dispatch had no backstop beyond
the agent's own judgment. Now a design-only or docs-only dispatch has a hard boundary: drift outside the
declared glob and the job is quarantined as `SCOPE_VIOLATION` rather than silently merged. Combined with
the task-receipt protocol (#768) and the permission-denied corroboration fix (#770), the fleet now has
three independent, evidence-based gates — receipt delivery, denial corroboration, and changed-file
scope — none of which need to trust an agent's self-report.

## Strategic Note: The Goal at the End of This PR

Two of #769's three sub-projects are now shipped. The remaining piece — safe-caller-construction
docs — is unscoped and unscheduled; it's a documentation-only item with no enforcement mechanism of its
own, so it can be picked up independently whenever it's prioritized. With #769 nearly closed, the next
open thread on the hardening front is filing a follow-up issue for the live `permission_denied`
classifier false-positive observed on this branch's own Task 4 dispatch (job-48f5c006) — ground-truth
verification showed the flagged job had, in fact, done complete and correct work — which is a live
instance of exactly the failure mode #770/#771 was built to catch, just not yet fully eliminated.
