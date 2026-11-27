# #4953 — Cluster A stopgap implementation readiness

## Question

Validate whether the retry-gate wiring plan is a narrow, non-terminal Cluster A stopgap that avoids both the rejected retry-cap redesign and deferred oracle promotion.

## Verdict

**Derived from the recorded synthesis.** The plan is ready because it reuses shipped retry gates at a missing settlement call site and introduces no new status, column, terminal writer, or oracle dependency. Dispatch should include the synthesis’s cross-call-site parity test and proof that both gates can defer before every terminal-write path.

## Findings

### Recorded panel synthesis (verbatim)

> Decision: Approve the plan for dispatch. All three panelists (Claude, Agy, Codex) independently converge: wiring the two already-shipped, already-tested retry gates (`_gh_write_verification_retry_pending`, `_unpushed_branch_retry_pending`) plus `_guard_unpushed_branch` into `_reconcile_terminal_jobs_json` is call-site parity with the existing `_reconcile_daemon_jobs` pattern — zero new columns, status values, or terminal writers — so it does not reintroduce Approach 1's split-brain risk, and it makes no contact with oracle trust, so it does not creep toward the deferred Approach 2. Proceed with dispatch to Codex (per Default Agent Role routing and Agy's domain-fit reasoning, with Grok excluded per the known-flaky pattern noted in this re-run), with two additions folded into the existing task structure rather than new tasks:
>
> 1. **Fold into Task 4** (the job-26b6196d-shape regression test): add an explicit cross-call-site parity assertion that `_reconcile_terminal_jobs_json` produces the same defer/cap-exhausted decision as `_reconcile_daemon_jobs` for identical job state, so the two call sites can't silently drift in behavior even though they call the same gate functions.
> 2. **Fold into task acceptance criteria**: confirm both gates execute and can defer *before* any terminal write, that a defer from one gate cannot be bypassed via the other gate or the bridge's fallback path, and that the `SELECT` extension for `worktree_path`/`branch` is proven populated at the bridge (not just mocked in tests).
>
> No other gaps block dispatch; the base branch (`origin/main`), spec/implementation call-site alignment (confirmed post-`e7cd9fb1`), and test plan scope (schema extension, per-gate defer/cap-exhausted, real-world regression shape, full-suite check) are otherwise sufficient as written.

- The cited spec and plan are absent at their live paths on this branch; archived copies were read. Their live-path availability is **not verified**.

## Recommended follow-ups

- **New ticket: No. Proposed title:** “Wire retry gates into reconcile_terminal_jobs_json.” Use the existing implementation story/plan.
- **New ticket: No. Proposed title:** “Assert bridge/main-loop retry decision parity.” Fold into the existing regression-test task.
- **New ticket: No. Proposed title:** “Prove defer-before-terminal-write and persisted worktree fields.” Add to the existing acceptance criteria.

## Sources

- [GitHub issue #4953](https://github.com/nikhilsoman/synlynk/issues/4953)
- `docs/archive/worktree-hygiene-2026-10-15/docs/superpowers/specs/2026-10-11-reconcile-terminal-jobs-retry-gate-design.md`
- `docs/archive/worktree-hygiene-2026-10-15/docs/superpowers/plans/2026-10-11-reconcile-terminal-jobs-retry-gate.md`
