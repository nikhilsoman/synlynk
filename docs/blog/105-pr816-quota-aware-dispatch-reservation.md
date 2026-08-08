---
title: "PR #816 — Quota-Aware Dispatch Reservation"
date: 2026-08-08
series: "Building the OS for Multi-Agent Development"
post: 105
pr: "#816"
status: open
---

## The Broader Goal at the End of the Previous PR

PR #783 closed out the safe-caller-construction hardening thread (#720/#769), which documented
the two safe dispatch call shapes — Python-native and shell/CI-with-argument-list — and left a
single named placeholder (#782) for a future `--task-file`/stdin interface, deliberately deferred
until Team/Enterprise introduces non-Python dispatch callers. At that point synlynk's dispatch
surface was considered "safe by construction" for the callers it actually had. What it did not
yet have was any notion of quota headroom that held up under those same call shapes: `--force-agent`
and daemon-queued dispatches could reach a harness with zero rate-limit headroom left and simply
fail, because quota was only checked on the ordinary `_best_agent_for_story()` selection path —
not unconditionally.

## Strategic Shifts in This PR

None. This PR builds directly off the approved design at
`docs/superpowers/specs/2026-08-08-quota-aware-dispatch-reservation-design.md` and its plan at
`docs/superpowers/plans/2026-08-08-quota-aware-dispatch-reservation.md`, executed task-by-task
with no scope changes mid-flight. The one deviation from the plan was corrective, not strategic:
Task 12's full-suite run surfaced a regression that no single task's own test file caught (see
below), and a follow-up fix task was inserted to close it before merge.

## What This PR Shipped

The core addition is an `agent_reservations` SQLite ledger that tracks estimated-token
reservations per harness from the moment a job is queued or dispatched until it settles. This
closes the specific gap the previous PR's hardening work exposed: `dispatch_agent()` used to only
consult quota when routing through `_best_agent_for_story()`, so an explicit `--force-agent` call
(or a daemon picking a job off the queue) could reach a fully exhausted harness and just fail
outright, or worse, add to a load a harness had no room for.

Now `dispatch_agent()` consults quota unconditionally, including on the `--force-agent` path.
When a harness has no headroom, the call defers instead of raising: the job stays `queued` with
`blocked_reason=quota_exhausted`, and resumes automatically once the harness's quota window resets
— picked up by the next `synlynk watch` daemon poll, no manual re-dispatch required. The reservation
lifecycle is open → settle → release, with a lazy-expire path for reservations whose jobs never
report back.

Four other pieces round out the wiring:

- **`_dispatch_ready_jobs()` no longer falls through to an exhausted harness.** The pre-existing
  bug (`synlynk/jobs.py:2034`) let a blocked job's iteration continue trying other harnesses in a
  way that could silently drop the block; it now correctly leaves the job queued for the next poll.
- **`synlynk schedule --execute`'s `_enqueue_plan()`** opens real reservations for the whole batch
  at commit time, so scheduled batch dispatch respects the same quota gate as ad-hoc dispatch.
- **`_force_exhaust_quota()`** wires sentinel's existing `QUOTA_EXHAUSTED` pattern detection
  (`sentinel.py:477-486`) into the reservation ledger, without ever touching jobs that are already
  running.
- **`synlynk/tpm_hooks.py`** is a new, deliberately narrow module — three stub functions
  (`tpm_observe_reservations`, `tpm_reorder_queue`, `tpm_reallocate`) plus one real, read-only
  caller: `synlynk quota --tpm-view`, a CLI command to inspect all open reservations across
  harnesses at a glance.

Testing followed the plan's TDD task breakdown (Tasks 1-9 covered the schema, lifecycle functions,
and each wiring point individually), then Task 10 added the `--tpm-view` CLI surface, Task 11 added
two full-cycle integration tests (`test_full_reserve_dispatch_settle_release_cycle` and
`test_deferred_job_survives_reset_and_resumes_without_redispatch`), and Task 12 ran the entire
existing suite plus README documentation as a cross-cutting regression check rather than a
new-feature step.

That Task 12 run is what caught the one real defect in this body of work: the quota gate's
`finally: _quota_conn.close()` was closing a database connection that, in
`tests/test_ecosystem_status.py::test_preflight_receives_real_db_conn`, is a caller-supplied
shared connection (the test monkeypatches `_get_db` to hand one in). Closing it out from under the
caller broke that pre-existing test with `sqlite3.ProgrammingError: Cannot operate on a closed
database` — a regression no individual task's own narrow test file exercised, because none of them
ran the full suite. It was root-caused by bisecting `dispatch.py` against its pre-Task-5 state
inside the job worktree, then fixed by removing the `try/finally` entirely and dedenting the quota
block so it no longer owns the connection's lifecycle. Worth naming explicitly here since it's the
kind of bug the Blog Post Protocol exists to surface: I (Claude, as PM) caught myself making a
direct hand-edit to `dispatch.py` to fix this — a violation of this repo's rule that Claude never
implements features end-to-end — reverted my own edit, and re-dispatched the fix properly through
`synlynk dispatch codex`, same as every other task in this plan.

Final state before PR creation: 1751 tests passed, 2 skipped, zero failures.

## Brainstorm Visuals Used

None — this design's brainstorm was conducted in terminal-only mode (no visual companion session),
so there are no artifacts in `docs/brainstorm/` for this PR.

## What This Achieved on the Path to Autonomy

The previous milestone made the dispatch *call shape* safe. This one makes dispatch *quota-aware*
regardless of call shape — the same property, one layer down. A daemon that autonomously picks
work off a queue (the direction `synlynk watch` is heading) cannot be trusted with real autonomy
if it can walk into a rate-limit wall and either crash the job or silently overshoot a harness's
window. Deferral-not-failure plus automatic resume on window reset means the daemon can now queue
work ahead of known-tight quota without a human needing to babysit the exhaustion/retry cycle by
hand. The TPM hook stubs are intentionally inert for now — they exist so that a future scheduler
optimization (reordering the queue by projected headroom, reallocating reservations across
harnesses) has a wiring point already reviewed and merged, rather than needing its own separate
plumbing PR later.

## Strategic Note: The Goal at the End of This PR

Quota exhaustion is now a first-class, ledger-tracked state that every dispatch path — ad-hoc,
`--force-agent`, daemon-queued, and batch-scheduled — respects the same way. The three TPM hook
stubs are the next natural fork point: nothing consumes `tpm_reorder_queue` or `tpm_reallocate`
yet beyond the read-only `--tpm-view` inspector, so the next milestone in this thread is deciding
whether the daemon's poll loop should start acting on projected headroom rather than just
observing it — likely gated behind its own design/plan cycle once there's real usage data from
this reservation ledger to reason about.
