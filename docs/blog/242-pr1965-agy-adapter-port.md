---
title: "gh:#1924 PR4 — Porting Agy to the HarnessAdapter Protocol"
date: 2026-10-03
series: "Building the OS for Multi-Agent Development"
post: 242
pr: "1965"
issue: "1924"
status: published
author: "synlynk team"
version: "0.25.0-dev"
tags: [posts, dispatch, harness-adapters]
type: story
---

## The Broader Goal at the End of the Previous PR

LIVE-22 (#1964) had just closed the GitHub-identity zone-boundary gap, clearing the way back to
the adapter migration. The goalpost coming into this PR: PR4 of the plan, porting Agy next,
following the exact same discipline PR2 (Codex) and PR3 (Grok) had already established — one
harness at a time, verified against that harness's own real failure modes before moving on.

## Strategic Shifts in This PR

None — PR4 exactly as scoped in the plan.

## What This PR Shipped

`AgyAdapter` implements the `HarnessAdapter` protocol for Agy (Gemini):

- **`translate_permissions()`**: no permission grant → `[]`; a read-only grant →
  `["--mode", "plan"]`; any write grant → `["--sandbox"]`.
- **`build_cmd()`**: delegates to `_dispatch_flags_for_agent("agy")` plus the translated
  permission flags, matching the pattern `CodexAdapter`/`GrokAdapter` already established.
- **`classify_failure()` / `parse_output()`**: classifies the 429 `RESOURCE_EXHAUSTED`
  credit-exhaustion failure mode this session has hit live against Agy more than once (see the
  standing `Grok auth / Agy fallback` memory — Agy's known failure signature).

## Caught in Review

The first review found a real gap: `parse_output()` returned only `raw_text` and `failure`,
missing the `lifecycle_events` and `compatibility_evidence` population that `CodexAdapter` and
`GrokAdapter` both do by importing `compatibility_evidence, parse_output` from
`synlynk.lifecycle` inside the method body. Without it, Agy dispatches would silently lose
lifecycle telemetry that the other two ported harnesses already report correctly — exactly the
kind of asymmetry the adapter pattern is supposed to prevent by construction, caught here
because it wasn't. The fix was scoped tightly to `synlynk/harness_adapters/agy.py` and its test
file, mirrored the Codex/Grok pattern exactly, added a regression test asserting both fields
populate, and came back with a fresh `APPROVE` on re-review.

This PR also hit the same README test-count CI gate as #1964, a second time, for the same
underlying reason — this PR's own new tests pushed the branch's true `pytest --collect-only`
count past what #1964 had already synced it to (3722 → 3727). Fixed the same way: a direct
commit on the PR's own branch, not a separate docs PR, since the gate is branch-scoped.

## What Was Achieved Toward the Long-Arc Goal

Three of four harnesses (Codex, Grok, Agy) are now off `LegacyAdapter`. Each port so far has
independently caught something real — Grok's port surfaced a stale capability-routing bug that
needed its own fix PR; Agy's port caught a lifecycle-telemetry gap in review before it shipped.
The strangler pattern is doing exactly the job it was designed for: making each harness's quirks
a visible, testable, single-adapter concern instead of a silent gap in a shared conditional.

## The New Goalpost

PR5 is the last port: Claude and local, then delete `LegacyAdapter` once nothing in the
registry still depends on it — closing out gh:#1924 entirely.

Refs #1924.
