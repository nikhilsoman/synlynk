# Autonomous backlog pickup + scheduling wiring — Design Spec

**Date:** 2026-10-13
**Issue:** gh:#2262
**Story:** story-6e633122, linked to goal-8f64eff5 (Durable Platform Health & Performance)

## Problem

Three pieces of autonomy infrastructure exist and work correctly in isolation, but nothing connects them to the daemon's own poll loop:

- `synlynk/scheduler.py`'s `_compute_schedule_plan()`/`cmd_schedule()` does correct capability + quota-aware batch routing (reuses `_capability_candidates_for_story`, `_quota_status_for_agent`, in-batch headroom accounting) — but is only ever invoked manually via `synlynk schedule [--execute]`.
- `synlynk/backlog.py`'s `ingest_backlog()` / `triage_backlog()` / `auto_promote_backlog()` pipeline turns GitHub issues into `readiness='ready'` stories — but is CLI-only (`synlynk backlog ...`).
- `synlynk/daemon.py`'s `SynlynkDaemon._run_loop` calls `_reconcile_daemon_jobs()` + `_dispatch_ready_jobs()` every tick — this launches jobs **already** `queued` in `daemon_jobs`, but never calls `cmd_schedule`, `ingest_backlog`, `triage_backlog`, or `auto_promote_backlog` itself.
- `synlynk/autonomy.py`'s `AutonomyMode` enum and `can_auto_advance()` are fully implemented but not read anywhere in this path — `autonomy_mode` in `.synlynk/config.json` currently has no effect on backlog/scheduling behavior at all.

Net effect: durable agents only ever work on what a human has manually scheduled. The backlog of open GitHub issues and any stories sitting in `readiness != 'ready'` never gets autonomously triaged, promoted, or dispatched, regardless of `autonomy_mode`.

## Approach

### 1. Trigger model — hybrid interval + idle

Add a new function `_autonomy_pass(conn=None)` to `synlynk/scheduler.py` that runs, in order:

```
ingest_backlog() -> triage_backlog() -> auto_promote_backlog() -> (autonomy-mode gate) -> cmd_schedule(execute=True)
```

`SynlynkDaemon._run_loop` (synlynk/daemon.py) calls `_autonomy_pass()` under two conditions, both checked every tick (no new thread/timer — reuses the existing poll cadence):

- **Interval:** a new `_last_autonomy_pass_at` timestamp (persisted the same way the daemon already persists `.synlynk/daemon.start`, as a sibling file `.synlynk/daemon.autonomy_last_run`) is compared against `now`; if elapsed >= `autonomy_pass_interval_seconds` (new `.synlynk/config.json` key, default `1800`), run the pass.
- **Idle-triggered:** `_dispatch_ready_jobs()`'s existing return value (count launched) is compared against the daemon's in-memory count from the previous tick. If the previous tick launched 1+ jobs and this tick launches 0 **and** a direct query confirms zero rows with `status IN ('queued','running')` in `daemon_jobs`, treat the fleet as freshly idle and run `_autonomy_pass()` immediately (resetting the interval timer so the two triggers don't double-fire back to back).

Both triggers call the exact same `_autonomy_pass()` — no divergent logic path. This is a small, additive change to `_run_loop`; no new background thread, no new IPC.

### 2. Autonomy-mode gating — discovery always runs, mode gates dispatch only

`_autonomy_pass()` always runs `ingest_backlog()` / `triage_backlog()` / `auto_promote_backlog()` regardless of `autonomy_mode` — this is bookkeeping (keeping stories' `readiness` current) and carries no dispatch risk on its own.

Before the `cmd_schedule(execute=True)` call, `_autonomy_pass()` reads `get_autonomy_mode()` (from `synlynk/autonomy.py`):

- `AutonomyMode.MANUAL`: skip scheduling/dispatch. The pass is backlog-bookkeeping only.
- `AutonomyMode.SUPERVISED` or `AutonomyMode.AUTONOMOUS`: run `cmd_schedule(execute=True)` identically in both modes.

This intentionally does **not** add a new supervised-only approval/proposal step for this feature — `can_auto_advance()`'s existing stage semantics (supervised blocks `execute`/`release` stage-advancement, not story-level scheduling) stay as they are; this spec treats "is this story allowed to be auto-scheduled for dispatch" as a separate axis from "is this story's lifecycle stage allowed to auto-advance." If a future need arises for a supervised-only dry-run/approval gate specifically on scheduling, that's a separate, later change — not scoped here (YAGNI).

### 3. GOVERNS linkage for auto-promoted backlog items

`auto_promote_backlog()` (synlynk/backlog.py) gains a goal-matching step, run once per newly-promoted story, before it becomes eligible for scheduling:

- Match the backlog item (its GitHub issue title/body/labels) against active goals' `outcome`/`criterion` text via simple keyword overlap (no new ML/embedding dependency — reuses the kind of plain-text matching already used elsewhere in this codebase for label-based routing).
- **Confident match found:** link the story to that goal (same effect as `synlynk goal link <story_id> --goal <goal_id>`).
- **No confident match:** the story is still created (triage work is not discarded) but is left unlinked. `_compute_schedule_plan()` (synlynk/scheduler.py) gains a new check, parallel to its existing `no_capability_candidates`/`quota_exhausted` blocks: a story with no primary goal link is appended to `blocked` with reason `"no_goal_link"`, and is never included in `plan` (so it can never reach `_enqueue_plan()`/dispatch while unlinked). This surfaces identically to today's other blocked reasons in `synlynk schedule`'s dry-run output, for a human to resolve via the existing `goal link` command — no new CLI surface needed.

This keeps the "100% GOVERNS adherence" invariant intact automatically: an auto-promoted-but-unlinked story is structurally incapable of being scheduled, let alone dispatched, until it's linked.

## Data flow

```
daemon._run_loop (tick)
  -> _reconcile_daemon_jobs()
  -> launched = _dispatch_ready_jobs()
  -> if interval_elapsed OR (prev_launched > 0 AND launched == 0 AND queue empty):
       scheduler._autonomy_pass()
         -> backlog.ingest_backlog()
         -> backlog.triage_backlog()
         -> backlog.auto_promote_backlog()   # now also attempts goal-match/link per item
         -> mode = autonomy.get_autonomy_mode()
         -> if mode != MANUAL:
              scheduler.cmd_schedule(execute=True)
                -> _compute_schedule_plan()   # now also blocks on reason="no_goal_link"
                -> _enqueue_plan()
                -> _dispatch_ready_jobs()
```

## Error handling

- Each stage of `_autonomy_pass()` (`ingest_backlog`, `triage_backlog`, `auto_promote_backlog`, `cmd_schedule`) is wrapped individually in `try/except Exception`, logged to `.synlynk/daemon.log` with the stage name, and does not abort the remaining stages or crash `_run_loop` — mirrors the existing defensive pattern already used around `_refresh_agent_quotas_from_telemetry()` in `_compute_schedule_plan()` (`try: ... except Exception: pass`).
- `_autonomy_pass()` itself never raises out of `_run_loop` — a failure in any one tick's autonomy pass just means the interval/idle trigger re-attempts next tick.

## Testing

- `tests/test_scheduler.py` (or a new `tests/test_autonomy_pass.py`): unit test `_autonomy_pass()` directly (not through the daemon loop) for each `autonomy_mode` value, asserting `cmd_schedule`/dispatch is or isn't invoked (mock/spy), and that backlog functions are always called regardless of mode.
- Test for the new `no_goal_link` blocked reason: a story with no primary goal present in `_compute_schedule_plan()`'s input is excluded from `plan` and appears in `blocked` with that reason.
- Test for the goal-matching step in `auto_promote_backlog()`: a backlog item whose text keyword-overlaps a fixture goal gets linked; one that doesn't stays unlinked.
- Daemon-loop integration test: simulate consecutive `_run_loop` ticks with a fake clock, assert `_autonomy_pass()` fires on interval elapse and on the idle transition (launched: N>0 -> 0 with empty queue), and does not double-fire within the same tick window.
- All new tests must use the `project_dir` fixture (chdir isolation) per gh:#2263's finding — this spec's own tests must not reintroduce that bug class.

## Out of scope (YAGNI, not deferred-but-implied)

- A supervised-only dry-run/approval UI step for auto-scheduling (see §2) — not requested, not built.
- Any change to `_dispatch_ready_jobs()`'s own concurrency/dependency gating logic — untouched by this spec.
- Embedding-based or LLM-based goal matching — plain keyword overlap only, per YAGNI; can be revisited if false-negative rate proves high in practice.
