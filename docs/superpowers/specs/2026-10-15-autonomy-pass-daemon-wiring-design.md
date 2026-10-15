# Autonomy-pass daemon wiring — Design Spec

**Date:** 2026-10-15
**Issue:** gh:#2262 (Task 4)
**Story:** story-f67acd86, linked to goal-bd5eaa14 / goal-06758149

## Context

This is the narrow remainder of a larger piece of work originally scoped in
`2026-10-13-autonomous-backlog-scheduling-design.md` (story-6e633122,
goal-8f64eff5). That design's Tasks 1-3 are **already merged into `main`**,
confirmed directly by grep on 2026-10-15:

- `synlynk/backlog.py`: `MIN_GOAL_MATCH_SCORE`, `require_explicit_goal` on
  `link_backlog_item_to_goal()`, and `auto_promote_backlog()` passing
  `require_explicit_goal=True` — all present (Task 1).
- `synlynk/scheduler.py`: `_compute_schedule_plan()` blocks stories with no
  `goal_id` with reason `"no_goal_link"` (Task 2).
- `synlynk/scheduler.py`: `_autonomy_pass_interval_seconds()` and
  `_autonomy_pass(conn=None)` exist and run
  `ingest_backlog -> triage_backlog -> auto_promote_backlog -> (autonomy-mode
  gate) -> cmd_schedule(execute=True)`, each stage independently
  try/excepted, never raising out (Task 3).

That original spec's own Task 1-3 commits (`df45144a` design doc,
`626e6281` plan doc) never actually landed on `main` — they were committed
only inside a now-abandoned nested worktree chain and are not an ancestor of
`origin/main`. The code they describe shipped anyway (evidently via a
different, since-untracked path). This spec recovers and re-commits the
design intent for the one piece that is confirmed still missing —
**Task 4: wiring `_autonomy_pass()` into `SynlynkDaemon._run_loop`** — so the
Brainstorm-First / Design→Plan→Build policy has an actual committed spec to
point to before that remaining work is dispatched. Tasks 1-3 are not
re-specified or re-implemented here; they are cited as already-shipped
prior art.

## Problem

`gh:#2262`'s own finding, reconfirmed directly against current
`synlynk/daemon.py` on 2026-10-15: `SynlynkDaemon._run_loop` calls
`_reconcile_daemon_jobs()` + `_dispatch_ready_jobs()` every tick, but never
calls `_autonomy_pass()`. `.synlynk/config.json`'s `autonomy_mode` and
`autonomy_pass_interval_seconds` therefore still have zero effect on daemon
behavior — a human must still run `synlynk schedule`/`synlynk backlog ...`
by hand for anything to be picked up autonomously, regardless of what
`autonomy_mode` says.

## Approach

Add a hybrid interval + idle trigger to `SynlynkDaemon`, reusing the existing
poll tick (no new thread/timer):

1. **New instance state**, set in `SynlynkDaemon.__init__` alongside the
   existing `self._last_autonomous_run = 0.0` (synlynk/daemon.py:1078) —
   deliberately a different name/attribute so this doesn't collide with the
   pre-existing, unrelated `autonomous`/`_autonomous_tick()` heal/TPM-sweep
   mechanism already on that class:
   - `self._last_autonomy_pass_at = 0.0`
   - `self._last_dispatch_count = 0`

2. **New method `_maybe_run_autonomy_pass(self, launched: int)`**, added to
   `SynlynkDaemon`:
   - **Interval trigger:** `time.time() - self._last_autonomy_pass_at >=
     _autonomy_pass_interval_seconds()`.
   - **Idle trigger:** the previous tick launched 1+ jobs
     (`self._last_dispatch_count > 0`) and this tick launched 0
     (`launched == 0`), confirmed by a direct query that
     `daemon_jobs` has zero rows with `status IN ('queued','running')`
     (guards against a `max_parallel` cap making the fleet look idle when
     it isn't).
   - Either trigger calls the same `_autonomy_pass()` — no divergent logic
     path — and resets `self._last_autonomy_pass_at` so both triggers can't
     double-fire in the same tick.
   - `self._last_dispatch_count = launched` is updated unconditionally at
     the end, regardless of whether a pass ran.
   - The call to `_autonomy_pass()` is wrapped in `try/except Exception:
     traceback.print_exc()` even though `_autonomy_pass()`'s own docstring
     already promises never to raise — belt-and-suspenders, matching the
     existing defensive style around it in `_run_loop`.

3. **Call site in `_run_loop`** (synlynk/daemon.py:1349-1353): capture
   `_dispatch_ready_jobs()`'s return value (already an `int` count launched,
   confirmed via `synlynk/jobs.py:5178`'s docstring) and pass it to
   `self._maybe_run_autonomy_pass(launched)` right after the existing
   `_reconcile_daemon_jobs()` / `_dispatch_ready_jobs()` try/except block.

4. **Import**: `from synlynk.scheduler import _autonomy_pass,
   _autonomy_pass_interval_seconds` added to `synlynk/daemon.py`'s existing
   `from synlynk...import` block.

Autonomy-mode gating itself (`MANUAL` skips `cmd_schedule`, `SUPERVISED`/
`AUTONOMOUS` both run it) is already implemented inside `_autonomy_pass()`
— nothing here duplicates or re-checks that gate.

## Data flow

```
daemon._run_loop (tick)
  -> _reconcile_daemon_jobs()
  -> launched = _dispatch_ready_jobs(max_parallel=max_parallel)
  -> self._maybe_run_autonomy_pass(launched)
       -> if interval_elapsed OR idle_transition:
            scheduler._autonomy_pass()   # already shipped, Task 3
       -> self._last_dispatch_count = launched
```

## Error handling

- `_autonomy_pass()` itself never raises (already true, Task 3). The call
  inside `_maybe_run_autonomy_pass` is still wrapped defensively.
- A failure in the idle-trigger's DB query (e.g. transient lock) is caught
  and treated as "not idle" for that tick — it does not block the interval
  trigger from firing on a later tick.

## Testing

- Unit test `_maybe_run_autonomy_pass` directly (not through the real
  `_run_loop` sleep loop): interval-elapsed case fires, idle-transition case
  fires, neither-condition case does not fire, and a monkeypatched
  `_autonomy_pass` that raises does not propagate out of
  `_maybe_run_autonomy_pass`.
- Reuse whichever existing daemon test file already instantiates
  `SynlynkDaemon` without a real fork/daemonize/sleep (check
  `tests/test_daemon_supervision_discovery.py` and
  `tests/test_daemon_token_refresh.py` first — both were touched by recent
  daemon work this week, PR #2324).

## Out of scope

- Any change to `_autonomy_pass()`, `_autonomy_pass_interval_seconds()`,
  the goal-match threshold, or the `no_goal_link` scheduler gate — all
  already shipped (Tasks 1-3).
- The pre-existing, unrelated `autonomous`/`_autonomous_tick()` heal/TPM
  sweep mechanism — untouched.
- Any new CLI surface or config key beyond what Task 3 already added.
