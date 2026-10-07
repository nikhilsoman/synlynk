---
title: "PR #2083 — Routing fallbacks are written down, not only printed"
date: 2026-10-06
series: "Building the OS for Multi-Agent Development"
post: 257
pr: "#2083"
status: open
author: "synlynk team"
version: "unreleased"
tags: [posts]
type: pr
---

# PR #2083 — Routing fallbacks are written down, not only printed

## The Broader Goal at the End of the Previous PR

v0.24.0 still needs a dispatch to move from implementation to a trusted
review verdict on GitHub state alone. The previous PR made a missing
GOVERNS link visible in the log and in `sentinel.md`, while #1990's
hard-fail stays unbuilt. The next visibility gap in the same class is
auto-routing: when local cannot run, dispatch already prints the
fallback and then forgets it.

## Strategic Shifts in This PR (if any)

No strategy change. Issue #2064's title talks about failing closed.
The committed design keeps today's routing and only records the
decision. Fail-closed stays out of this PR.

## What This PR Shipped

- `_resolve_dispatch_agent()` still prints `Routing to: <fallback>` when
  local oMLX is unreachable or the local capability score is under the
  threshold. The same line is appended to `.synlynk/sentinel.md` as
  `DISPATCH_ROUTING_FALLBACK` through the existing
  `_write_sentinel_alert` helper.
- The job dict and `daemon_jobs` gain `requested_harness`,
  `actual_harness`, and `fallback_reason`. A fallback from local to
  codex is stored as requested `local`, actual `codex`.
- `synlynk jobs` prints `local->codex` on that row. A dry run discards
  the pending decision so it cannot attach to a later job.
- Choosing local, or naming a harness explicitly, does not write a
  fallback alert. Return values and control flow are unchanged.

Plan: `docs/superpowers/plans/2026-10-06-three-lens-followups-plan.md`,
Task B. Design: `docs/superpowers/specs/2026-10-06-three-lens-followups-design.md`,
Section B.

## Brainstorm Visuals Used

None. This follows the committed design and plan.

## What This Achieved on the Path to Autonomy

Job history can show that a run asked for local and executed the
fallback. Cost attribution and `synlynk jobs` can read that from the
job row instead of inferring it from a harness name that was already
substituted.

## Strategic Note: The Goal at the End of This PR

The routing decision is now durable. The next piece of this follow-up
set is still the sample-size-gated empirical ranking (#2063), the
config schema checks (#2065), and the adapter conformance suite
(#2062). #1990's GOVERNS hard-fail remains the enforcement step for
the warning shipped just before this.
