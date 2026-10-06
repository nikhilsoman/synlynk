---
title: "PR #2074 — Dispatch names a missing GOVERNS link before #1990 can block on it"
date: 2026-10-06
series: "Building the OS for Multi-Agent Development"
post: 253
pr: "#2074"
status: open
author: "synlynk team"
version: "unreleased"
tags: [posts]
type: pr
---

# PR #2074 — Dispatch names a missing GOVERNS link before #1990 can block on it

## The Broader Goal at the End of the Previous PR

v0.24.0 still needs a dispatch to move from implementation to a trusted review
verdict on GitHub state alone. The completion oracle now reads the pull
request the task actually named. The remaining velocity gap called out at the
end of that work was the GOVERNS preflight: CLAUDE.md already describes a
hard-fail (#1990) that dispatch does not enforce.

## Strategic Shifts in This PR (if any)

No strategy change. #1990 stays the hard-fail. This PR only makes the gap
visible, using option (a) from the 2026-10-06 velocity design, so in-flight
epics are not blocked while that hard-fail is still unbuilt.

## What This PR Shipped

- `dispatch_agent()` preflight checks whether `--story`, `--issue`, or `--pr`
  is resolvable. `--issue` still counts when it is auto-detected from `#N` in
  the task. `--pr` counts from an explicit number or from a pull request named
  in the task. An ad-hoc `story-adhoc-*` id created later does not count.
- When none of those is resolvable, preflight prints
  `GOVERNS linkage missing — dispatch proceeding, but this will hard-fail once #1990 ships`
  and writes the same line to `sentinel.md` as `GOVERNS_LINKAGE_MISSING`.
  The job still starts.
- A dispatch that already has a linked story keeps the previous path: no
  warning, and an explicit story with no goal still fail-closes (#2029).
- CLAUDE.md's #1990 notes (Hardened PR Review Policy and PR Review Discipline)
  now say this warning is live and distinct from the unbuilt hard-fail.
- Tests cover the warning plus a proceeding job, a linked story with no
  warning, and the unchanged unlinked-story hard-fail.

Plan: `docs/superpowers/plans/2026-10-06-governs-velocity-unblock-plan.md` §4.
Design: `docs/superpowers/specs/2026-10-06-governs-velocity-unblock-design.md` §3.4.

## Brainstorm Visuals Used

None. This follows the committed design and plan.

## What This Achieved on the Path to Autonomy

An operator can see, in the dispatch log and in `sentinel.md`, that a job
left without a GOVERNS link. The fleet can keep moving while #1990 is still
open, instead of rediscovering the documentation gap by running a dispatch
and watching nothing happen.

## Strategic Note: The Goal at the End of This PR

#1990's hard-fail is the next enforcement step for this check. Until it
ships, a missing `--issue`/`--pr`/`--story` warns and proceeds. Cross-harness
review still closes #2073.
