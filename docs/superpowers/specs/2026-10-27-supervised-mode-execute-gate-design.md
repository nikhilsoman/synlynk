---
title: "SUPERVISED mode execute-stage gate for daemon autonomy pass — Design Specification"
date: 2026-10-27
status: approved
author: "Claude (Home Conductor)"
goal: "goal-bd5eaa14"
epic: "#2470"
milestone: "v0.26.4"
arc: "runtime"
issue: "#2631"
---

# Design: SUPERVISED mode does not halt daemon auto-dispatch (gh:#2631)

**Date:** 2026-10-27
**Goal:** `goal-bd5eaa14` — Daemon runs reliably and autonomously drives the backlog→schedule→dispatch pipeline per the Tri-Modal Autonomy Dial

## Context — what Phase 3 actually needs

The v0.26.4 handoff describes Phase 3 as "wire `_compute_schedule_plan()`/`_dispatch_ready_jobs()`
into `synlynk daemon`'s live loop, guarded by `autonomy_mode`." That work already shipped:

- `synlynk/daemon.py`'s poll loop calls `_dispatch_ready_jobs()` every tick and
  `self._maybe_run_autonomy_pass(launched)` (daemon.py:1707-1713).
- `_maybe_run_autonomy_pass()` → `synlynk/scheduler.py:_autonomy_pass()` on a hybrid
  interval/idle trigger.
- `_autonomy_pass()` runs `ingest_backlog`/`triage_backlog`/`auto_promote_backlog`/
  maintainer-triage unconditionally, then calls `cmd_schedule(execute=True)` — which
  calls `_compute_schedule_plan()` + `_dispatch_ready_jobs()` — unless `get_autonomy_mode()
  == AutonomyMode.MANUAL`.
- This landed in PR #2269 ("feat: add `_autonomy_pass()` chaining backlog pipeline +
  mode-gated scheduling (gh:#2262)"), confirmed via `git log -L` on `scheduler.py`.
- `story-issue-2262` / `story-f573de2b` (goal-bd5eaa14) still show `status=open` in
  `state.db` — stale; the underlying issue is closed by #2269. These should be marked
  done as part of this story's cleanup, not re-implemented.

**The handoff's Phase 3 description is stale.** The real gap is narrower.

## The actual gap

`synlynk/autonomy.py:can_auto_advance(stage, mode)` encodes the Tri-Modal Autonomy Dial's
intent directly and is covered by `tests/test_autonomy_dial.py::test_can_auto_advance_rules`:

- `MANUAL` → no automatic transitions.
- `SUPERVISED` → auto-advances everything **except** `execute` and `release` — i.e.
  SUPERVISED should compute/visualize the plan but halt before actually running it.
- `AUTONOMOUS` → auto-advances everything, including `execute`.

`can_auto_advance()` is never called anywhere outside its own module (`grep -rn
"can_auto_advance" synlynk/*.py` returns only the definition and its test). In
particular, `_autonomy_pass()` does not call it — it only branches on
`mode == AutonomyMode.MANUAL`, treating SUPERVISED identically to AUTONOMOUS:

```python
if mode == AutonomyMode.MANUAL:
    return
try:
    cmd_schedule(execute=True)   # <-- runs for SUPERVISED too
```

So today, flipping `autonomy_mode` from `manual` to `supervised` already gives the daemon
full auto-dispatch — there is no functional difference between SUPERVISED and AUTONOMOUS
for this pipeline. That breaks the three-way dial's premise and the goal's own stated
criterion ("autonomy_mode can be safely flipped to autonomous without manual CLI
driving" implies SUPERVISED is a meaningfully safer intermediate step, not a no-op
rename of AUTONOMOUS).

## Fix

Gate the `execute` stage in `_autonomy_pass()` through `can_auto_advance()`:

```python
from synlynk.autonomy import AutonomyMode, can_auto_advance, get_autonomy_mode
...
if mode == AutonomyMode.MANUAL:
    return
try:
    cmd_schedule(execute=can_auto_advance("execute", mode))
except Exception:
    ...
```

- `MANUAL` — unchanged, returns before scheduling at all (backlog bookkeeping stages
  still run via `ingest_backlog`/`triage_backlog`/`auto_promote_backlog`, which is
  existing, separate behavior this change does not touch).
- `SUPERVISED` — `cmd_schedule(execute=False)` runs the dry-run path: computes and
  prints the plan (`_compute_schedule_plan()`), does **not** call `_enqueue_plan()` or
  `_dispatch_ready_jobs()`. An operator inspects `synlynk status`/daemon logs and runs
  `synlynk schedule --execute` manually to actually dispatch — this is the intended
  "halts before execution" semantic `can_auto_advance` already documents.
  Need to also confirm `cmd_schedule(execute=False)`'s print path is quiet enough not
  to spam daemon logs every poll tick (it currently prints a results table + "would be
  scheduled" line unconditionally) — add a `quiet=` or rate-limit the print to the
  existing `_autonomy_pass_interval_seconds()` cadence rather than every tick, since
  `_maybe_run_autonomy_pass` can also fire on idle-transition.
- `AUTONOMOUS` — unchanged, `cmd_schedule(execute=True)`.

## Tests to add (`tests/test_daemon_autonomous_schedule.py`)

1. `_autonomy_pass()` with `mode=SUPERVISED` computes a plan but does not call
   `_dispatch_ready_jobs()` / does not enqueue daemon_jobs rows.
2. `_autonomy_pass()` with `mode=AUTONOMOUS` does call through to dispatch (can reuse
   existing `_enqueue_plan`/`_dispatch_ready_jobs` mocking patterns from
   `tests/test_fleet_scheduler.py`).
3. `_autonomy_pass()` with `mode=MANUAL` unchanged (regression guard).
4. Mark `story-issue-2262` / `story-f573de2b` `done` (via `synlynk story done`) as part
   of the same PR's housekeeping, citing PR #2269 as the actual closing commit — not a
   code change, a state.db correction.

## Non-goals

- Not touching `story-issue-1857` (circuit breaker), `story-issue-2324` (repo-root
  resolution), or `story-issue-2510` (cost attribution) — open stories under the same
  goal but unrelated to this gap, out of scope for this PR.
- Not changing the Phase 4 target: `story-2349673f` is actually "Fix
  `capability_calibration_results.quality_verified` migration gap (gh:#2569)" under a
  different goal (`goal-aa48c456`) — unrelated to daemon scheduling. The handoff's
  Phase 4 instruction to verify scheduling via this story_id appears to be another stale
  reference; Phase 4's "trigger daemon/`synlynk schedule --execute`" verification should
  target a real ready story under `goal-bd5eaa14` instead (none are currently in
  `readiness=ready` state — will need one promoted first, or verify via a synthetic
  test story).
