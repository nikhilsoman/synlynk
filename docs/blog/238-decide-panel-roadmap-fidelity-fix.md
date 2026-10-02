---
title: "The Synthesis Lost Detail the Panel Actually Gave Us"
date: 2026-10-03
series: "Building the OS for Multi-Agent Development"
post: 238
pr: "TBD"
status: published
author: "synlynk team"
version: "0.23.0-dev"
tags: [posts, strategy, roadmap]
type: story
---

## The Broader Goal at the End of the Previous PR

PR #1919 synthesized three `synlynk decide` panel runs into a consolidated architecture
roadmap, a surface-simplification plan, and a broader-issues remediation plan — the direct
follow-through on the five-POV review's open questions. The architecture roadmap compressed
nine distinct improvement opportunities from the review down to seven table rows.

## Strategic Shifts in This PR

No code changed here either, and the roadmap's substance doesn't change. What changed is
fidelity: checking the shipped table against the original nine-item list showed the
synthesis pass had been too aggressive. Three items — a `HarnessAdapter` plugin registry for
third-party harnesses, a CI release-version gate, and an explicit cold-start performance
budget — were dropped entirely rather than reconciled or deferred. Two more — the
`dispatch_agent` pipeline's actual stage shape, and containerized execution for untrusted
harnesses — survived only as a passing mention, missing the specifics the panel's own
per-harness responses had given. This is a real lesson about this kind of synthesis step:
compressing multiple detailed inputs into a short table is exactly where information gets
silently discarded, and the discard isn't visible unless someone checks the table against
the raw inputs it claims to summarize.

## What Shipped

- `docs/strategy/2026-10-02-decide-panel-roadmap.md`, revised: the architecture roadmap
  table grew from 7 rows to 10, recovered from the session's captured per-harness panel
  output rather than re-running the panel (the original responses were still available).
  - Row 5 now names the actual pipeline shape (`resolve → authorize → prepare_worktree →
    spawn → observe → finalize`) and the full `HarnessAdapter` method set (`build_cmd()`,
    `parse_events()`, `permissions()`, `detect_quota()`, `models()`), plus the plugin-registry
    detail for third-party harnesses.
  - A new row 6, **safe-by-default execution**, separates the permission-default flag flip
    (already covered, in the broader-issues plan) from containerized execution for untrusted
    harnesses (not covered anywhere until now), and cross-references both documents so the
    shared flag change lands once, not twice.
  - Row 8 (CLI core/packs split) now names the actual ~15 core commands and the 15–20K LOC
    target instead of a bare direction.
  - New rows 9 and 10 restore the CI release gate (tie to the live version-drift issue,
    #1914) and the lazy-import/cold-start performance budget, both previously missing
    entirely.
  - The sequencing decision and the cross-cutting note were updated to match the new item
    numbers.

## What This Achieved on the Path to Autonomy

The original panel-decide loop worked end to end — real multi-harness deliberation,
real synthesis, real committed output. This PR closes the gap between what the panel
actually said and what the committed document claims it said, which matters more for a
process meant to be trusted as a planning input than any individual roadmap item does.

## Strategic Note: The Goal at the End of This PR

The architecture roadmap and both companion plans are now a complete, faithful
representation of the five-POV review's findings. The next milestone is unchanged from
before this patch: ship roadmap items #1+#2 (state/worktree GC and the regen-bug guard)
first, since they're small, parallel-safe, and stop data loss that has already recurred
multiple times.
