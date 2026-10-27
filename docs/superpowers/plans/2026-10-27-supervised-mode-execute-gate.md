---
title: "Plan: Gate _autonomy_pass() execute stage through can_auto_advance()"
date: 2026-10-27
status: approved
author: "Claude (Home Conductor)"
goal: "goal-bd5eaa14"
epic: "#2470"
milestone: "v0.26.4"
arc: "runtime"
issue: "#2631"
---

# Plan: Gate `_autonomy_pass()` execute stage through `can_auto_advance()`

Spec: `docs/superpowers/specs/2026-10-27-supervised-mode-execute-gate-design.md`
Goal: `goal-bd5eaa14`
Issue: `#2631`

## Task 1 — Fix the gate in `synlynk/scheduler.py`

In `_autonomy_pass()`:

1. Import `can_auto_advance` alongside the existing `AutonomyMode, get_autonomy_mode`
   import.
2. Replace:
   ```python
   if mode == AutonomyMode.MANUAL:
       return
   try:
       cmd_schedule(execute=True)
   except Exception:
       print("  ⚠ _autonomy_pass: cmd_schedule failed:")
       traceback.print_exc()
   ```
   with:
   ```python
   if mode == AutonomyMode.MANUAL:
       return
   try:
       cmd_schedule(execute=can_auto_advance("execute", mode))
   except Exception:
       print("  ⚠ _autonomy_pass: cmd_schedule failed:")
       traceback.print_exc()
   ```
3. In `cmd_schedule()`, the `execute=False` (dry-run) branch currently always prints
   the plan table and a "would be scheduled" line. Since `_autonomy_pass()` can now
   call this every poll tick in SUPERVISED mode, add a `quiet: bool = False` parameter
   to `cmd_schedule()` that suppresses the print output when set, and pass
   `quiet=True` from `_autonomy_pass()`'s call. Do not change the default (CLI-invoked
   `synlynk schedule` without `--execute` must keep printing normally).

## Task 2 — Tests: `tests/test_daemon_autonomous_schedule.py` (new file)

Follow the mocking patterns already used in `tests/test_fleet_scheduler.py` for
`_compute_schedule_plan` / `_enqueue_plan` / `_dispatch_ready_jobs`.

1. `test_autonomy_pass_supervised_computes_plan_without_dispatch` — set
   `autonomy_mode=supervised`, seed one ready story, call `_autonomy_pass()`, assert
   `_compute_schedule_plan()` was invoked (plan computed/logged) but
   `_dispatch_ready_jobs()` / `_enqueue_plan()` was NOT called and no `daemon_jobs` row
   was inserted.
2. `test_autonomy_pass_autonomous_dispatches` — same setup with
   `autonomy_mode=autonomous`; assert `_enqueue_plan()` and `_dispatch_ready_jobs()` ARE
   called and a `daemon_jobs` row is created.
3. `test_autonomy_pass_manual_skips_scheduling_entirely` — `autonomy_mode=manual`;
   assert `cmd_schedule` is never called at all (regression guard for existing
   behavior — must still pass unchanged).
4. `test_cmd_schedule_quiet_suppresses_output_on_dry_run` — call
   `cmd_schedule(execute=False, quiet=True)` with a non-empty plan, assert no stdout
   output (capsys), and call it again with `quiet=False` (or omitted) asserting the
   existing table/"would be scheduled" output still prints — regression guard that the
   default CLI path (`synlynk schedule`, no flags) is unaffected.

Run `pytest tests/test_daemon_autonomous_schedule.py tests/test_fleet_scheduler.py
tests/test_autonomy_dial.py -q` before opening the PR — all three files must pass
together since this change touches code paths all three exercise.

## Task 3 — state.db housekeeping (same PR)

Run:
```
synlynk story done story-issue-2262 --note "Closed by PR #2269 (gh:#2262); state.db status was stale"
synlynk story done story-f573de2b --note "Duplicate of story-issue-2262, closed by PR #2269"
```
(Use whatever the actual `synlynk story done` flag is for a closing note — check
`synlynk story done --help` in the dispatch worktree; if there's no `--note` flag, skip
it and just mark done.) This is a data correction, not a code change — include it in
the same PR as Tasks 1-2 since it's directly cited by the spec.

## Out of scope (do not touch)

- `story-issue-1857` (circuit breaker), `story-issue-2324` (repo-root resolution),
  `story-issue-2510` (cost attribution) — unrelated open stories under the same goal.
- `story-2349673f` — unrelated story under a different goal; not a verification target
  for this change.
- Anything under `docs/superpowers/specs/2026-10-13-finalize-workspace-agent-charters-design.md`
  or PR #2621 — this plan does not touch charter/role governance code.

## Verification before PR

- `pytest tests/test_daemon_autonomous_schedule.py tests/test_fleet_scheduler.py tests/test_autonomy_dial.py -q`
- `python3 bin/synlynk.py schedule` (no flags) on a repo with at least one ready story
  still prints the plan table as before (manual smoke check, not just the new quiet
  test).
- `synlynk pr check` from within the PR's own worktree before requesting review.

## Routing

Per the project's Default Agent Role policy (interim default, 2026-10-27): this is
implementation + test work, routes to Codex or Grok via `synlynk dispatch`, not
implemented directly by Claude. Claude (this session) reviews/merges per the Hardened
PR Review Policy (reviewer differs from implementer in harness AND model; reviewer's
own dispatched job performs the merge).
