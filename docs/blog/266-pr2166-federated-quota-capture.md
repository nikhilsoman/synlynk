---
title: "Federated quota capture"
date: 2026-10-10
series: "Building the OS for Multi-Agent Development"
post: 266
pr: "2166"
status: shipped
author: "synlynk team"
version: "0.25.0"
tags: [posts]
type: pr
---
# 266 — Federated quota capture

## Where the last PR left the goal

synlynk could price a job in `cost_entries` and could store a hand-entered ceiling in `harness_quotas`. It could not see which subscription was actually near its weekly limit, so PM and review work kept landing on whichever harness was home.

## What moved

The home harness hit 98% of its weekly quota during roadmap work. Allocation has to read the provider's own percent, not a local token estimate. Open-source usage tools were checked and rejected because they label their figures as API-equivalent estimates.

## What this PR ships

`quota_snapshots` (migration 20) stores `harness`, `window` (`5h` or `weekly`), `used_percent`, `resets_at`, `captured_at`, `source` (`task_boundary` or `poller`), `staleness_seconds`, and `job_id`. The registry in `synlynk/quota_capture.py` maps Claude and Agy to `cli -p "/usage" --output-format text`, Codex to the newest `payload.rate_limits` object under `~/.codex/sessions`, and Grok to `billing: fetched credits config` in `~/.grok/logs/unified.jsonl`. Boundary capture runs on a daemon thread after `exec_command` and after a dispatch job settles `done`. The daemon poller runs every 15 minutes. For Grok it sends `/usage` and Enter into `interactive_pane_id` only when that id is set and the log line is older than 15 minutes. `synlynk quota federated` prints the latest row per harness and window next to a 7-day `cost_entries` sum. A reading older than 30 minutes, or a missing reading, is `unknown`. Unknown falls back to `synlynk quota calibrate` data in `harness_quotas`. Unpinned dispatch then prefers the known weekly reading with the most room, and skips a harness whose known 5h reading is at least 100%.

## Brainstorm

No new brainstorm visuals. The approved spec is `docs/superpowers/specs/2026-10-10-federated-quota-capture-design.md`.

## On the way to autonomous dispatch

The fleet can now see subscription headroom the same way it already sees dollar burn. Grok stays `unknown` until a standing Herdr pane id is registered. That pane setup is a separate design.

## The new goalpost

Per-harness persistent Herdr panes, so Grok's weekly percent refreshes without a manual calibrate, and Herdr's place as a synlynk dependency gets its own spec.
