---
title: "Grok reports its own model roster into models.json"
date: 2026-10-21
series: "Building the OS for Multi-Agent Development"
post: 279
pr: TBD
status: open
author: "synlynk team"
tags: [posts]
type: pr
---

# 279 — Grok reports its own model roster into models.json

Date: 2026-10-21
PR: TBD
Story: story-issue-2457 / gh:#2457

## Goalpost coming in

gh:#2454 / job-595f5739 already asked each harness's own CLI for real model
tiers and pricing, then wrote those answers into `.synlynk/models.json` for
Claude, Codex, Agy, and local. Grok's row stayed a placeholder because the
2026-10-20 audit hit Grok's weekly quota mid-query.

## What shifted

The quota reset. This dispatch ran `grok models` (CLI 1.0.62) against the live
account and read `~/.grok/models_cache.json` plus official xAI text-API
pricing at docs.x.ai. Muse is still out of scope here (same ticket, still
blocked on gh:#2077).

## What shipped

Live Grok Build roster (2026-10-21):

| CLI id | Name | Role |
|---|---|---|
| `grok-4.7` | Grok 4.7 (default) | Latest frontier model; `pro` and `reasoning` dispatch tiers |
| `grok-4.7-build-fast` | Grok 4.7 Fast | Premium latency SKU; CLI description "2x the price" |
| `grok-4.6` | Grok 4.6 | Previous generation; `fast` dispatch tier |
| `grok-4.5` | Grok 4.5 | Older generation still on the CLI |

There is no separate reasoning model id. `grok-4.7` exposes
`reasoning_effort` (`xhigh` / `high` / `medium` / `low`). Mapping
`grok-4.7-build-fast` onto synlynk's cheap `fast` tier would invert the
economic meaning used by Claude/Codex/Agy, so `fast` stays `grok-4.6`.

Standard (<200k prompt) rates encoded per 1k tokens from docs.x.ai, with
`grok-4.7-build-fast` at 2× `grok-4.7` because that SKU is not on the public
price table. Context window is 500k (CLI also lists a 256k compact window).
Max output is unpublished (`0`).

## Goalpost going out

Grok's catalog gap on gh:#2457 is closed. Muse still needs a live CLI roster
once its usage/API-key blocker clears.
