---
title: "gh:#1924 PR3 — Porting Grok to the HarnessAdapter Protocol"
date: 2026-10-03
series: "Building the OS for Multi-Agent Development"
post: 239
pr: "1957"
issue: "1924"
status: published
author: "synlynk team"
version: "0.25.0-dev"
tags: [posts, dispatch, harness-adapters]
type: story
---

## The Broader Goal at the End of the Previous PR

PR1/PR2 of the gh:#1924 strangler-pattern migration had already landed the shared
`DispatchRequest` + `HarnessAdapter` Protocol + registry + `dispatch_pipeline.py`, with
`LegacyAdapter` as the fallback for every harness, and `CodexAdapter` ported and verified
against real dispatch traffic as the pilot. The goalpost at that point was: repeat the same
verify-before-next-port discipline for each remaining harness, one PR at a time, so a quirk in
one harness never again requires touching the shared `dispatch_agent()` conditionals that used
to hold all four harnesses' branching logic at once.

## Strategic Shifts in This PR

None. This PR is PR3/5 of the plan exactly as scoped: port Grok next, in isolation, leaving
Agy, Claude, and local untouched behind `LegacyAdapter`.

## What This PR Shipped

`GrokAdapter` implements the `HarnessAdapter` protocol for Grok, covering the four pieces of
harness-specific behavior this session had previously hit as bespoke carve-outs scattered
through `dispatch_agent()`:

- **Permission translation** — the plan-specified mapping from a generic permission grant to
  Grok's own CLI flags.
- **Command building** — `build_cmd()` assembling the Grok invocation from the translated
  permissions plus the harness's dispatch flags.
- **Failure classification / output parsing** — explicitly covering the three failure modes
  this session had already hit live against Grok: 402 billing exhaustion, session expiry, and
  the sandbox's silent bash-execution denial (which reports exit 0 with no real side effect —
  exactly the "job status alone is not ground truth" pattern this project has learned to
  distrust).
- **Model resolution** — Grok's model-list lookup, moved out of the shared conditional.

Five Task 10 regression tests exercise permissions, 402 billing exhaustion, session expiry, and
sandbox bash denial directly against the new adapter. The registry change is a single line:
only `grok` gets rebound to `GrokAdapter`; `agy`, `claude`, `local`, and `codex` stay exactly as
PR2 left them.

## What Was Achieved Toward the Long-Arc Goal

Two harnesses (Codex, Grok) are now off `LegacyAdapter` and onto the typed protocol, with their
quirks encoded as adapter methods instead of `if harness == "grok"` branches living next to
three other harnesses' branches. The strangler pattern is holding exactly as designed: each port
is independently testable and independently verifiable against the exact failure modes that
harness has actually produced in production dispatch traffic, not hypothetical ones.

## The New Goalpost

Port Agy next (PR4), then Claude/local (PR5), then delete `LegacyAdapter` once nothing depends
on it. Agy's known failure mode — credit exhaustion returning a 429 — is the next adapter's
`classify_failure()` to get right.

Refs #1924.
