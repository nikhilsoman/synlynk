# PR #156/#157 — Fleet Dispatch Scheduler v1 Ships, v2 Deferred to a Tracked Goal

**Date:** 2026-07-11
**PRs:** #156 (scheduler), #157 (roadmap + deferred goal)
**Branches:** `dispatch/grok/job-*` → `main`, `chore/fleet-scheduler-v2-deferred-goal` → `main`
**Tracks:** #141 optimizer follow-up (closes out epic #137 capability-matrix hardening)

---

## The Goal at the End of the Previous PR

PR #148/#151/#152/#154 (blog post 51) shipped the **base matrix**: `agent_quotas`,
the 3-stage `_best_agent_for_story` routing (capability → quota headroom → cost),
and degraded-mode non-hard-blocking when quota signal is missing. That closed the
gating half of the 2026-06 token-budget design. The optimizer half — sequencing a
*batch* of stories against fleet-wide capacity, not just picking one agent per story
— was explicitly left as a follow-up architect design doc, not code.

---

## What Moved the Goalpost in This PR

Two design docs were written this session
(`docs/superpowers/specs/2026-07-11-fleet-dispatch-scheduler-design.md` and its
implementation plan) to scope that optimizer follow-up. The scope decision that
mattered most: **v1 ships a batch scheduler with fleet-level in-batch headroom
accounting and a binary readiness gate; the harder problems — reset-timing-aware
bin-packing, persistent quota-blocking history, and a GOVERNS-aware readiness gate
that checks a plan's coverage across all 7 SDLC stages — are out of scope until we
have real production data on how v1 behaves.**

Rather than let that scope decision live only as a "later" comment in the design
doc, it was formalized as a dated goal (`synlynk goal create`, `goal-d38e3c83`,
deadline 2026-08-10) — a 30-day observation window on v1's `synlynk schedule`
behavior before v2 is even converted into stories.

---

## What Shipped

### Schema & readiness gate
- `stories.priority` / `stories.readiness` columns (additive migration)
- `synlynk story ready` / `synlynk story draft` — binary gate, no story is
  schedulable until explicitly marked ready

### Scheduler (`synlynk/scheduler.py`)
- `_compute_schedule_plan` — batch routes ready stories through
  `_best_agent_for_story`, accumulating in-batch headroom consumption per
  `(agent, model, quota_type)` so story 2 in a batch sees story 1's projected spend,
  not just the pre-batch quota snapshot
- `_enqueue_plan` — commits the plan to dispatch queue
- Retry/reassignment: `MAX_STORY_RETRIES=2`, reassigns to next-best agent on
  failure rather than re-queuing to the same exhausted candidate

### CLI
- `synlynk schedule [--execute] [--max-stories N]` — dry-run plan preview by
  default, `--execute` commits it

### Tests
- `tests/test_fleet_scheduler.py` — e2e coverage of the batch plan, in-batch
  headroom accounting, retry policy, and CLI wiring

Grok implemented all 8 tasks from the plan; diff and tests reviewed and verified
independently before merge (PR #156). CI showed only the known baseline failure
set (5 environment-specific tests, confirmed unchanged across #151/#152/#154/#156)
— no regression.

### Roadmap + deferred goal (PR #157, docs-only per branch discipline)
- Cross-Cutting Epics table: epic #137–141 marked **Shipped**, new **Fleet
  Scheduler v2 (deferred)** row pointing at `goal-d38e3c83` and the design doc's
  Future Work section

---

## On Track to Full Autonomous Multi-Agent Dispatch

Epic #137 is now closed end-to-end: capability score → quota gate → cost
tie-break → batch scheduling, all real code paths instead of design-doc
intentions. The three v2 problems (bin-packing around reset windows, persistent
blocking-pattern history, stage-aware readiness) are real but premature —
scoping them before v1 has run in production would be guessing at requirements
instead of reading them off actual `blocked`/`retry`/`degraded-mode` counts.

---

## New Goalpost

- Run `synlynk schedule` in production for 30 days (2026-07-11 → 2026-08-10)
- Revisit `goal-d38e3c83` at deadline: review blocked-story reasons, retry
  frequency, degraded-mode incidence
- Only then convert v2's three Future Work bullets into scoped stories
