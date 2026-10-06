---
title: "PR #TBD — Empirical routing promotes a harness only after five measured samples"
date: 2026-10-06
series: "Building the OS for Multi-Agent Development"
post: 255
pr: "#TBD"
status: open
author: "synlynk team"
version: "unreleased"
tags: [posts]
type: pr
---

# PR #TBD — Empirical routing promotes a harness only after five measured samples

## The Broader Goal at the End of the Previous PR

v0.24.0 still needs dispatch to choose a harness from measured outcomes, and
to say so honestly in the README. PR #2074 made a missing GOVERNS link visible
before #1990 can hard-fail on it. Routing itself was still the suspended
heuristic table.

## Strategic Shifts in This PR (if any)

Single-workspace routing no longer waits on shard consolidation (#1926).
Each repo's dispatch preview reads that workspace's own canonical `state.db`.
Fleet-wide `synlynk capability report` aggregation (#1993) stays blocked on
#1926 and #1831. That split is what lets empirical promotion ship now.

## What This PR Shipped

- `ranked_harness_for_task()` in `synlynk/capability.py`. `candidates[0]` is
  the incumbent. A later harness is preferred only with at least five
  `capability_ratings` rows whose `discipline` matches the task type
  (there is no `task_type` column) and a joined `cost_entries` row on
  `story_id` where `ce.harness` equals `cr.agent`. It must beat the
  incumbent on both median `pr_review_cycles` and average `total_cost_usd`.
  Otherwise the function returns `None`.
- `compose_dispatch_preview()` is the public name for
  `_infer_dispatch_defaults()` at the `task_allocation` read. When no
  explicit agent, role, or story is bound, a promoted harness replaces the
  table default. Explicit CLI values and story metadata still win. The
  local-threshold path in `_resolve_dispatch_agent()` is unchanged.
- `.synlynk/policy.json` `capability_policy` drops `suspended_since` and
  `suspended_rationale`, restates `blocking_dependency` for the
  single-workspace vs fleet split, and names `README.md:15` next to
  `task_allocation` and `docs/harness-capability-baseline.md` for any
  future suspension.
- README line 15 now says routing uses the best-measured harness once it
  clears the sample-size bar, and the documented default otherwise.

Tests seed an in-memory ledger (creating `cost_entries`, which lives in the
db.py migration rather than `_DB_SCHEMA`) and a dispatch preview that stubs
the ranker. `tests/test_governs_linkage_warning.py` still passes.

Plan: `docs/superpowers/plans/2026-10-06-three-lens-followups-plan.md` Task A.
Design: `docs/superpowers/specs/2026-10-06-three-lens-followups-design.md` Section A.
Issue: #2063.

## Brainstorm Visuals Used

None. This follows the committed design and plan.

## What This Achieved on the Path to Autonomy

Dispatch preview can now prefer a harness the workspace has actually measured,
and it refuses to do that on a thin sample. Below five rows the documented
allocation stays in force, which is the honest default until grok and muse
are calibrated.

## Strategic Note: The Goal at the End of This PR

The next follow-up is durable logging of routing fallback (#2064): the
decision this preview makes has to survive in `sentinel.md` and job metadata,
not only on stdout. Fleet-wide capability reporting remains behind #1926.
