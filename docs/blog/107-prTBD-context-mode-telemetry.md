---
title: "PR TBD — Context-Mode Telemetry: Measuring Right-Sized Context"
date: 2026-08-09
series: "Building the OS for Multi-Agent Development"
post: 107
---

# Context-Mode Telemetry — Measuring Right-Sized Context

## Broader goal (previous)

Platform ops could score hygiene vs real multi-agent work (windowed sentinels, job reap). The scoreboard still could not answer a product-critical question: **do jobs get task-level or full context?**

## Why this PR

Right-sizing context by job type is a core synlynk claim. Without telemetry we only had defaults (`--context-mode task`) and folklore (PM often forces `full`). After a week of real `by_context_mode` data we can refine modes and, later, replace static `generate_context` with an **Architect Workspace Agent** as a configurable context provider.

## What shipped

1. **`daemon_jobs.context_mode` + `context_bytes`** — written on every dispatch (after truncation).
2. **`jobs.json` + telemetry** — same fields on the job object / dispatch event.
3. **`cost_entries.context_mode`** — inherited from the job row on cost insert when not passed.
4. **`ops report`** — L1 `by_context_mode` counts + %, `context_bytes` summary; L2 cost by mode.
5. **`synlynk jobs`** table — CTX column.
6. **Design note** — `docs/superpowers/specs/2026-08-09-context-mode-telemetry-and-architect-context-provider-design.md` for the Architect provider path.

## On the long arc

Instrumentation first → policy second → Architect-built context third. This PR is the measurement spine.

## New goalpost

- Nightly ops shows mode mix (even if early data is mostly `unknown` + new `task`/`full`).
- After ~7 days: open Architect provider design implementation; mode policy informed by data.
