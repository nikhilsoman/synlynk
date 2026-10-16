---
title: "Issue #2063 — Empirical routing promotes a harness only after the sample-size bar"
date: 2026-10-06
series: "Building the OS for Multi-Agent Development"
post: 254
pr: "#TBD"
status: open
author: "synlynk team"
version: "unreleased"
tags: [posts]
type: pr
---

# Issue #2063 — Empirical routing promotes a harness only after the sample-size bar

## The Broader Goal at the End of the Previous PR

Dispatch can now name a missing GOVERNS link and still proceed while #1990's
hard-fail is unbuilt. The routing claim next to that was still suspended:
`capability_policy` said empirical mode, but `suspended_since: 2026-10-04`,
and the README said every task already goes to the best harness on a live
ledger.

## Strategic Shifts in This PR (if any)

Single-workspace routing no longer waits on fleet-wide shard consolidation
(#1926). A dispatch in this repo reads this workspace's `state.db`. The
fleet-wide `synlynk capability report` (#1993) stays blocked on that
consolidation. `task_allocation` remains the incumbent until a challenger
clears five samples and beats it on both median review cycles and average cost.

## What This PR Shipped

- `ranked_harness_for_task()` in `synlynk/capability.py`. `candidates[0]` is
  the incumbent. A later harness is returned only with at least five
  `capability_ratings` rows for that discipline (the stand-in for task type)
  joined to `cost_entries` on story and harness, and only when both median
  `pr_review_cycles` and average `total_cost_usd` are better.
- `compose_dispatch_preview`, an alias of `_infer_dispatch_defaults`, consults
  that ranking when the caller did not pass an explicit harness. An explicit
  harness still wins. With no qualifying sample, the role default and the
  allocation table are unchanged.
- `.synlynk/policy.json` drops `suspended_since` and `suspended_rationale`,
  and narrows `blocking_dependency` to fleet-wide aggregation.
- README line 15 now says routing uses the best-measured harness once it
  clears the sample-size bar, and otherwise the documented default.

Plan: `docs/superpowers/plans/2026-10-06-three-lens-followups-plan.md` Task A.
Design: `docs/superpowers/specs/2026-10-06-three-lens-followups-design.md`.

## Brainstorm Visuals Used

None. This follows the committed three-lens follow-up design and plan.

## What This Achieved on the Path to Autonomy

A preview can promote a harness from measured review cycles and cost instead
of leaving empirical mode as a flag that dispatch ignores. Below five samples
the documented default stays in place, so an uncalibrated harness is not
guessed into the route.

## Strategic Note: The Goal at the End of This PR

The next gap is fleet-wide comparison (#1993), still blocked on consolidating
sharded `state.db` files (#1926 / #1831). Until that lands, promotion is only
as good as this workspace's own ledger.
