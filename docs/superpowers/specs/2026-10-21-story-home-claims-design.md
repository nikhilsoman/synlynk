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

### Schema

New table in `state.db`, initialized the same way `worktree_leases` is
(`init_worktree_lease_schema`-style function called at DB-open time):

```sql
CREATE TABLE IF NOT EXISTS story_home_claims (
    story_id      TEXT PRIMARY KEY,
    harness       TEXT NOT NULL,
    session_id    TEXT NOT NULL,   -- "<hostname>:<checkout_path>:<pid>"
    pid           INTEGER NOT NULL,
    acquired_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    heartbeat_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status        TEXT NOT NULL DEFAULT 'active'   -- active | released
);

CREATE INDEX IF NOT EXISTS idx_story_home_claims_status
    ON story_home_claims(status, heartbeat_at);
```

`session_id` is generated once per interactive session (not per command) and
reused for every claim/heartbeat/release call that session makes. `pid` is the
interactive session's own process id, used for the dead-PID reclamation check
exactly as `worktree_lease.py` already does for `_is_pid_alive()`.

### New module: `synlynk/story_claims.py`

Mirrors `worktree_lease.py`'s shape:

- `take_story_claim(story_id, harness, session_id, pid, *, override=False) ->
  ClaimResult` — looks up any `status='active'` row for `story_id`. If found
  and (heartbeat within TTL) and (PID alive), it's a live conflicting claim:
  return `ClaimConflict(holder_harness, holder_session_id, acquired_at)` unless
  `override=True`. Otherwise (no live conflict, or override), upsert the row
  with the new claimant's harness/session_id/pid and fresh timestamps.
- `heartbeat_story_claim(story_id, session_id) -> bool` — bumps `heartbeat_at`
  for the row matching `(story_id, session_id)`; no-op (returns False) if that
  session doesn't hold the claim (e.g. it was already reclaimed).
- `release_story_claim(story_id, session_id) -> bool` — sets `status =
  'released'` for the row matching `(story_id, session_id)`.
- `is_claim_stale(row, ttl_seconds) -> bool` — shared predicate: heartbeat older
  than TTL, or PID no longer alive (reuses `_is_pid_alive` from
  `worktree_lease.py` rather than duplicating it).

Default TTL: 45 minutes (same order of magnitude as `story reclaim`'s existing
30-minute default, intentionally slightly larger since a claim's heartbeat
only needs to arrive once per `synlynk exec` cycle, not continuously).

### Integration points

- **Claim acquisition:** wherever the existing story state machine flips a
  story's status to `in_progress` for an *interactive* session (as opposed to
  a dispatched job). Call `take_story_claim()` there; on `ClaimConflict`,
  print the holder's harness/session/claimed-at and exit non-zero unless
  `--override` was passed on the command that triggered the transition.
- **Heartbeat:** `exec_command()` in `bin/synlynk.py` already runs once per
  `synlynk exec` invocation and already knows the active story from
  `.synlynk/context.md` generation. Add a call to
  `heartbeat_story_claim(active_story_id, session_id)` there if a story is
  active — reuses an existing per-command hook, no new polling loop.
- **Release:** `synlynk story done <id>` and `execute_home_handover()` (the
  existing handover path in `synlynk/handover.py`) both call
  `release_story_claim()` for the relevant story.
- **Reclamation:** extend the **existing** `reclaim_stranded_stories()` /
  `story reclaim` command (`synlynk/jobs.py`) to also sweep
  `story_home_claims` for stale rows (TTL-expired or dead-PID) in the same
  pass as its current orphaned-`in_progress`-status logic, rather than adding
  a second, separate reclaim command.

### session_id generation

Generated once per interactive session start (first `synlynk exec` call, or
wherever the session first becomes "home"), as `f"{socket.gethostname()}:
{repo_root}:{os.getpid()}"`, and held in-memory / in an env var for the rest of
that process's lifetime. Not persisted to any gitignored per-checkout file —
the claim row in shared `state.db` is the only durable record.

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
