---
title: "v0.25.3 — Muse Readiness and Capacity-Routing Evidence"
date: 2026-10-24
series: "Building the OS for Multi-Agent Development"
post: 280
pr: "#TBD"
status: open
---

## Intent

v0.25.3 closes out the last open gate failures standing between the v0.25.x line and a clean release: giving Muse a real, bounded place in the fleet instead of leaving it unauthenticated and un-routable, and fixing three capability/cost-routing defects that were quietly feeding bad signal into the empirical capability policy this project runs on.

## Context

The empirical capability policy (`.synlynk/policy.json`) only promotes a harness into a task-type's routing table once it clears a five-merged-job sample-size bar on measured `pr_review_cycles` and `total_cost_usd`. Muse couldn't clear that bar because it had never been authenticated or allowlisted for any dispatch — it had zero samples to measure. Separately, three defects were discovered that undermined the measurement itself: Codex's model-tier set collapsed to a single tier whenever discovery returned one model, `pr_review_cycles` turned out to be an inert metric that never varied across harnesses, and `capability_calibration_results.quality_verified` could silently default to a passing score instead of recording that verification never happened.

## Pathway

Each fix went through its own design → plan → build cycle per this project's Brainstorm-First Policy:

- **Muse readiness (#2554):** a short, approved spec turned the already-recorded decision — implement/test access only, no review or GitHub-write authority until Muse clears the five-merged-job bar — into `.synlynk/policy.json` changes: Muse added as a fallback harness for `implement`/`test` task types, explicitly excluded from `review`/`gh_write`/`pm`/`deploy`, and left in `not_yet_calibrated` until it has real samples.
- **Codex tier collapse (#2552):** fixed so a single-model discovery response no longer erases the rest of Codex's known tier set.
- **Routing metric replacement (#2551):** `pr_review_cycles` is retired as a routing signal and replaced with `dispatch_rework_rate`, which actually varies with harness performance.
- **Silent verification fallback (#2170):** `quality_verified` defaulting silently to a passing value is now detected and surfaced rather than masquerading as a verified score; the calibration diff also now uses the recorded base SHA instead of a live merge-base, closing a second accuracy gap in the same code path.
- **Daemon pidfile crash (#2553):** `status()` now tolerates a missing daemon pidfile instead of crashing, closing out an unrelated but blocking daemon-reliability gate.

A deliberately separate decision was made **not** to bundle a capability sweep or a production backfill into this release. A prior sweep attempt under a $1.50 cost cap produced no useful output, and simply raising the cap isn't a fix for whatever bounded the sweep's scope — that work is being scoped fresh, as its own follow-up, with particular attention to Muse and Grok specifically now that Muse has a routable identity and Agy's prior quota exhaustion may no longer be a constraint.

## Outcome

Muse is authenticated and usable at implement/test privilege. The routing and calibration signals that capability-based dispatch depends on are now measuring something real instead of a flat or silently-defaulted number. 5,058 tests collected. Quota/capacity truth for Muse remains explicitly unknown rather than estimated — that's the next piece of work, scoped separately rather than folded into this release.

## Strategic Note: The Goal at the End of This Release

The next goalpost is the capability sweep itself: a bounded-scope, cost-estimated pass focused on Muse and Grok, run with Agy's quota status reconsidered, so the empirical policy has the samples it needs to actually promote or demote harnesses on measured evidence rather than interim defaults.
