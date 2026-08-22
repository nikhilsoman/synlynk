---
title: "PRs #1082–#1089 — Shipping the QA Merge Gate, and the Bug It Found on the Way"
date: 2026-08-22
series: "Building the OS for Multi-Agent Development"
post: 123
pr: "#1082, #1083, #1084, #1086, #1088, #1089"
merged: 2026-08-21/22
---

## The Broader Goal at the End of the Previous PR

PR #1079 (still open as of this post — see note below) laid out the design for
**block-only** merge-gate authority: compute a qa-gate verdict from CI matrix status
plus sentinel health, wire it into `synlynk pr check`, add a CI job that enforces it,
and finally make GitHub's own branch protection require that job to pass. The plan
(`docs/superpowers/plans/2026-08-20-qa-merge-gate-authority.md`) decomposed this into
four stacked PRs, each dispatched to Codex or Grok per the plan's harness assignment,
with every review/merge step staying with Claude per this project's PM-only role.

## Strategic Shifts in This PR (if any)

No scope changes to the qa-gate plan itself. The one real shift was operational,
discovered mid-execution: **synlynk's own state-DB migration logic had a live bug**
(tracked as LIVE-5, issue #1087) that surfaced while dispatching the stacked PRs —
`_migrate_db()` was copying the entire state DB on *every* connection instead of only
when a schema change was actually pending, producing 384 stale `.pre-migration-*.bak`
files (1.8GB) and lock-contention crashes in `synlynk probe`/`dispatch`/`pr check`.
That got triaged as a Sev1 per the Live Issues SOP, RCA'd, fixed, and merged
(PR #1086, #1088) in the middle of the qa-gate stack rather than deferred — the gate
work couldn't proceed reliably while the dispatch tooling underneath it was corrupting
its own state.

## What This PR Shipped

**The qa-gate stack (Tasks 1–4 of the plan):**
- **#1082/#1083** — the `qa_gate_verdict` module (CI matrix + sentinel health →
  block/pass verdict) and its wiring into `synlynk pr check`.
- **#1084** — the `qa-gate:` CI job, added inside `.github/workflows/test.yml` as
  `needs: test` rather than a standalone `qa-gate.yml`. Same-file `needs:` was a
  deliberate choice: separate workflow files run in parallel with no cross-file
  ordering, so a standalone file would almost always see the test matrix as still
  pending and fail closed.
- **#1089** — `scripts/apply_qa_gate_branch_protection.sh`, a dry-run-only
  read-modify-write script that adds `qa-gate` to main's required status checks
  without clobbering existing ones. This one took two dispatch cycles: the first
  Codex delivery (job-424c7c39) shipped with `--jq 'contexts'` — invalid jq syntax
  missing the leading dot — but Codex's own self-test didn't catch it because the
  test harness PATH-injected a **mock `gh` binary** that silently ignored `--jq`
  entirely and returned pre-shaped JSON. I found the bug by running the script
  against the real `gh` CLI directly during review. The fix-dispatch explicitly
  banned mocking `gh` a second time and required reproduction against the real CLI
  before and after the fix — verified independently again before merge.
  Task 4 also cost two wasted dispatch cycles from a different cause: the branch
  actually created by the first Codex job was `chore/qa-gate-branch-protection`
  (the plan's task text contained a literal `git checkout -b` instruction that
  Codex followed verbatim), not the `dispatch/codex/job-*` auto-naming convention
  the redispatch assumed — `_resolve_explicit_base_ref()` in `synlynk/dispatch.py`
  happily resolved the wrong `--base` to main's tip instead of erroring, so two
  redispatches silently produced worktrees missing the actual script until the
  branch was confirmed directly via `git branch --show-current`.
  Two Grok attempts at this same task also failed earlier with `stopReason:
  "cancelled"` after 53–90s each, with correct in-progress reasoning per the
  job's `"thought"` field — read as backend/session instability rather than a
  task-comprehension problem, so the harness was switched to Codex rather than
  retried a third time on Grok.

**The LIVE-5 fix (#1086 RCA, #1088 code):**
- Gated `_snapshot_before_migration()` behind a schema-fingerprint check so it only
  backs up when a migration is actually about to change something — zero file
  copies on the common already-migrated-DB path.
- Added a `PRAGMA user_version`-gated `_DB_MIGRATION_VERSION` constant to make
  repeated `_migrate_db()` calls on an already-current DB cheap and idempotent.
- Fixed a second, harder-crash bug in `_run_harness_rename_migration()`: the
  rename from `agent_reservations` to `harness_reservations` only checked that the
  source table existed, not that the destination didn't — if `agent_reservations`
  got re-created empty by a later `CREATE TABLE IF NOT EXISTS` in the same
  migration pass, the next connection's rename crashed with
  `OperationalError: there is already another table or index with this name`.
- Three regression tests: double-migration produces zero new backups, rename is
  safe when both tables already exist, and the normal single-migration path still
  produces exactly one backup.

## Brainstorm Visuals Used

None — this work executed directly off the already-approved
`docs/superpowers/plans/2026-08-20-qa-merge-gate-authority.md` plan document; no new
brainstorming was needed for either the gate stack or the LIVE-5 fix.

## What This Achieved on the Path to Autonomy

The qa-gate is the mechanism that lets synlynk eventually trust a dispatched agent's
PR without a human re-running CI checks by hand — `synlynk pr check` now computes a
real block/pass verdict from CI + sentinel state, and once
`apply_qa_gate_branch_protection.sh` is actually run (still a deliberate,
human-confirmed-only step — see below), GitHub itself will refuse to merge a PR
whose qa-gate job hasn't passed. That's a concrete step toward "qa role delegated
merge-gate authority," the follow-up spec flagged back in #1075's Out of Scope.

Just as importantly, the LIVE-5 catch is a case study in the review discipline this
project runs on: a dispatched agent's own self-test (via a mock tool) can look green
while masking a real bug, and this project's non-authoring-reviewer-runs-it-for-real
step caught it before merge, twice in a row (the branch-protection jq bug, and
independently the DB migration storm that was found through direct production
symptoms, not through any agent's test suite).

## Strategic Note: The Goal at the End of This PR

The full qa-merge-gate-authority stack (#1082, #1083, #1084, #1089) plus the LIVE-5
fix (#1086, #1088) are on `main`. Three items remain explicitly deferred, not silently
dropped:

1. **Actually applying branch protection** — `apply_qa_gate_branch_protection.sh`
   exists and is verified safe in dry-run, but running it for real against `main`'s
   protection rules is a human-confirmed action, not yet scheduled.
2. **PR #1079** (the original block-only design spec) is still open, unmerged — the
   implementation shipped ahead of the spec doc landing, which is a process gap worth
   closing separately rather than retconning here.
3. A full worktree hygiene audit ran immediately after this stack shipped (9 stale
   worktrees/branches from this and prior sessions cleaned up, 2 genuinely open
   branches — #1079 and #1081 — correctly left alone), keeping the "clean up the
   moment the owning PR merges" protocol from silently drifting into the kind of
   30-worktree backlog a prior audit had to clear in bulk.
