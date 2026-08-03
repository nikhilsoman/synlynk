---
title: "PR #592 — Finally, the CLAUDE.md Regeneration"
date: 2026-07-30
series: "Building the OS for Multi-Agent Development"
post: 86
pr: "#592"
merged: 2026-07-30
---

## The Broader Goal at the End of the Previous PR

PR #591 fixed the last known bug blocking `synlynk sync --repair-sops --confirm` from producing a correctly-formatted regeneration of the harness-managed instruction files. Nothing remained in the way.

## Strategic Shifts in This PR

None — this is the capstone of a five-PR chain (#584, #588, #589, #591, #592) that started as a single "update CLAUDE.md" ask and kept growing one root-cause tooling bug at a time. No shortcuts were taken along the way: at no point was the harness-managed content hand-patched directly, even though that would have been faster at every single step.

## What This PR Shipped

`synlynk sync --repair-sops --confirm`, run clean on a fresh branch off updated `main`:
- **CLAUDE.md / GROK.md**: refreshed the stale `## Capability-Based Task Allocation` section with the real per-repo routing table (generated from `.synlynk/config.json`, not synlynk's hardcoded default fleet assumptions) and the current GitHub-write-routing text — Grok-by-default, Agy's conditional headless capability (contingent on local `settings.json` allow-rules, not reliably verifiable mid-task), Codex's sandboxed network block, and the #569 caveat that `--requires-gh-write`'s token-stripping fallback isn't a hard identity guarantee.
- **GEMINI.md**: had zero pre-existing SOP headers, so all six harness sections filled in fresh.

Formatting was manually verified section-by-section before committing — exactly one blank line at every boundary, headers rendering correctly — rather than trusting the tool blindly, given the newline bug found on the previous attempt (#591). This was a docs-only change, kept in its own PR per this project's own CLAUDE.md convention separating doc-only changes from code changes. Non-authoring review (Grok, via COMMENT fallback) confirmed the diff scope, table content against `.synlynk/config.json`, and formatting before merge.

## Brainstorm Visuals Used

None.

## What This Achieved on the Path to Autonomy

The instruction files every dispatched agent reads now accurately describe the fleet's real GitHub-write capability, instead of a stale "Grok only" rule that this same session's own evidence (Agy succeeding at PR #589's review/merge) had already contradicted. This closes a chain that started as a simple documentation update and, by insisting on root-causing rather than patching, surfaced and fixed four separate tooling bugs (#339's vacuous doctor checks, #339's own live-subprocess-in-hot-path side effect, #583's stale-detection gap, and #583's own newline-spacing regression) along the way.

## Strategic Note: The Goal at the End of This PR

With doctor/probe trustworthy and the instruction files current, the fleet-parity audit (#332, #338, #340, #342, #347, #348, #419, #461) can resume on solid footing. Issue #573 (Agy can't call Stitch MCP tools headless) remains queued behind it.
