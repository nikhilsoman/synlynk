# Story Home Claims — Design

**Tracking issue:** gh:#2511
**Date:** 2026-10-21
**Role:** PM / Architect (Home Conductor, interactive, not dispatched)

## Problem

The existing home-harness handover mechanism (`synlynk home`, `.synlynk/handover.json`,
`.synlynk/config.json`'s `home_harness` key, `detect_active_home_harness()` in
`synlynk/context.py`) tracks which harness currently holds "home"/Active Project
Conductor status, so other harnesses/sessions know not to collide with in-progress
interactive work.

In practice it doesn't do this:

1. `.synlynk/config.json` and `.synlynk/handover.json` are both git-ignored and
   per-checkout. A handover recorded in one checkout is invisible to any other
   checkout or harness.
2. It drifts even within a single checkout: a completed handover record can
   disagree with `detect_active_home_harness()`'s live detection, which just
   reports whatever harness is running the *current* process.
3. It is never consulted before cross-cutting Conductor-level actions.

## Reframing (from brainstorm discussion)

The actual goal is narrower and more useful than "track one global home harness
for the whole project": a human may legitimately run multiple harnesses
interactively at once, each driving a *different* story/task. The real risk is
two interactive sessions — possibly different harnesses, possibly the same
harness in two checkouts — independently working the **same story**, producing
duplicated effort, divergent reasoning chains, and file-level collisions.

So the claim is scoped to **story/issue ID**, not to the whole project or
checkout.

## Decisions (from brainstorm Q&A)

- **Enforcement point:** Block at task-start, override allowed. A conflicting
  live claim refuses the start of new work on that story, but an explicit
  `--override` flag is available for legitimate edge cases (e.g. confirmed-stale
  claim, holder confirmed done out of band). No mid-task or write-path
  interception — the check happens once, at the moment a story transitions to
  `in_progress`.
- **Staleness:** Heartbeat + TTL. The holding session periodically bumps a
  `heartbeat_at` timestamp; a claim whose heartbeat has not been refreshed
  within the TTL window is considered dead and does not block a new claim.
- **Conflict scope:** Same story/issue ID only. No file-overlap heuristics —
  two different stories touching the same files is a separate, harder problem
  (file sets often aren't known before work starts) and is explicitly out of
  scope here.
- **Dispatch scope:** Interactive home sessions only. Headless `synlynk
  dispatch` jobs already get worktree isolation and GOVERNS story linkage from
  existing machinery; this fix targets the specific gap of interactive sessions
  believing they're uniquely "home" on a story when they aren't. Dispatched
  jobs do not take or check claims.

## Architecture

Model this directly on the existing `worktree_leases` table/pattern in
`synlynk/worktree_lease.py` — a TTL-based lease with heartbeat and dead-PID
reclamation, already proven in this codebase, already living in the same
shared `state.db` that `synlynk._get_db()` resolves to (confirmed:
`worktree_lease.py` uses `from synlynk import _get_db`, and the resulting DB
file is the per-workspace, cross-checkout `state.db` keyed by `workspace_id` —
not a per-checkout file). No new cross-checkout sync mechanism is needed; the
shared DB already is the thing every checkout reads.

### Implementation note (added after planning)

This design is implemented by extending the pre-existing `task_leases` table
and `synlynk/jobs.py` functions (`acquire_task_lease`, `renew_task_lease`,
`release_task_lease`, `get_active_lease`, originally built for gh:#1507 but
previously uncalled from anywhere) rather than by adding a new table/module.
See `docs/superpowers/plans/2026-10-21-story-home-claims-design.md` for the
full rationale and implementation detail. The schema gained `pid` and
`harness` columns; `acquire_task_lease` gained dead-PID detection and an
`override` flag; a new `synlynk story claim` CLI command, an `exec_command()`
heartbeat hook, and release hooks on `story done`/home handover are the new
integration points. `reclaim_stranded_stories` now also checks claim-PID
liveness.

`leased_by` is the composite session identity (`f"{harness}:{hostname}:{pid}"`,
set by `cmd_story_claim`) — note this is distinct from the separate `harness`
column, which stores only the bare harness name. Callers releasing a lease
must look it up via `get_active_lease()` first and pass the real `leased_by`
value through, not reconstruct or guess it (a bare-harness-string substitution
bug of exactly this kind was caught and fixed during Task 6's review — see the
plan's PR description for detail).

Session identity for the *claim-tracking marker* (as opposed to the
`task_leases.leased_by` value above) ended up being file-based rather than the
in-memory/env-var approach originally anticipated below: `synlynk/session.py`
tracks which story_ids the current checkout has claimed in a gitignored
`.synlynk/active_claims.json` marker file (`_read_active_claims()` /
`_add_active_claim()` / `_remove_active_claim()`), written by `cmd_story_claim`
and cleared by `cmd_story_done` / `execute_home_handover`. This lets a *later,
different-PID* process in the same checkout (e.g. a subsequent `synlynk exec`
invocation) still heartbeat the claim taken by an earlier one-shot `story
claim` process, via `heartbeat_claims_by_story_ids()` — solving the
cross-process heartbeat problem the in-memory/env-var approach below would not
have solved on its own.

## Error handling

If `_get_db()` fails (DB missing/locked/corrupt), **fail open**: log a
warning, proceed without taking or checking a claim. This is an advisory
safety net on top of normal work, not a hard dependency — consistent with this
project's existing posture on other advisory checks (e.g. `.synlynk/context.md`
generation degrades gracefully rather than blocking). A broken claims table
must never be able to halt all interactive work project-wide.

## Testing

- Unit tests for `story_claims.py`: conflict detection (live claim blocks),
  TTL expiry (stale heartbeat does not block), dead-PID reclamation (process
  gone does not block), override bypasses a live conflict, release clears the
  claim. These can adapt `worktree_lease.py`'s existing test fixtures directly
  since the shape is identical.
- Integration test: `story reclaim` sweeps both orphaned `in_progress` stories
  and stale `story_home_claims` rows in one pass.
- Integration test: two simulated sessions (distinct `session_id`/`pid`)
  attempting to claim the same story — second attempt without `--override`
  is refused; with `--override` it succeeds and transfers the claim.

## Out of scope

- File-overlap conflict detection across different stories (noted as a
  candidate follow-up, not designed here).
- Any claim/check for headless dispatched jobs.
- Replacing or removing the existing `.synlynk/handover.json` /
  `home_harness` config mechanism wholesale — this design adds the
  story-scoped claim as a new, separate safety net; reconciling or retiring
  the older whole-project handover concept is a separate decision not forced
  by this change.
