---
title: "PR TBD — agent_quotas finally gets real usage (#291)"
date: 2026-07-16
series: "Building the OS for Multi-Agent Development"
post: 66
pr: "TBD"
merged: pending
---

## The Broader Goal at the End of the Previous PR

v0.12.0 closed the measurement-and-reliability arc: structured token adapters, a provenance-aware cost ledger, and a 3-stage capability → quota → cost router with a fleet batch scheduler. The quota stage shipped as schema + helpers (`agent_quotas`, `_upsert_agent_quota`, `_quota_headroom`, `_quota_status_for_agent`) in the #141 base matrix work — but the table stayed empty in production. Stage 2 was a real gate against a signal that was never written. Issue #291 named that gap: decorative plumbing, no CLI, no non-zero `used_tokens`.

## Strategic Shifts in This PR

None to the product goal. One implementation choice locked for this PR: **telemetry proxy first**, not provider API scraping. Most coding CLIs still do not expose a durable usage/limits surface synlynk can poll headlessly. The issue explicitly allowed accumulating from `.synlynk/telemetry.json` via the existing upsert path. Live provider meters remain a future probe enhancement (already noted as follow-up in the #141 blog post).

Limits are therefore **config defaults** (overridable at `budget.quota_limits`), not Anthropic/OpenAI plan meters. The CLI labels that honesty: "source: telemetry proxy + config limits."

## What This PR Shipped

1. **`refresh_agent_quotas_from_telemetry()`** in `synlynk/quota.py`  
   - Reads `.synlynk/telemetry.json`  
   - Attributes events by `agent` field or first command token (`claude` / `agy` / `codex` / `grok` / `local`; `gemini` → `agy`)  
   - Rolls tokens and request counts into every plan window (`5h`, `hourly`, `daily`, `weekly`, `monthly`)  
   - Upserts via `_upsert_agent_quota()` with `reset_at` and both `tokens` + `requests` units  

2. **`synlynk quota [--agent NAME] [--json]`**  
   - Refreshes from telemetry, then prints per-agent min headroom and per-window used/limit/reset using `_quota_headroom` / `_read_agent_quota_rows` / `_quota_status_for_agent`  

3. **Wiring so stage 2 sees non-zero data**  
   - After each `exec` telemetry write  
   - Once at the start of `_best_agent_for_story`  
   - Once at the start of fleet `_compute_schedule_plan`  

4. **Tests** in `tests/test_agent_quota_tracking.py` — populate-from-telemetry, stage-2 non-degraded after refresh, routing prefers non-exhausted agent after refresh, CLI text/JSON, agent attribution edge cases.

## Brainstorm Visuals Used

None — gap fix against already-designed #141 matrix.

## What This Achieved on the Path to Autonomy

The capability → quota → cost router can finally hard-gate on something other than an empty table or the project-level `limit_requests` floor. Operators can answer "how much 5h / weekly headroom does claude have in *this* workspace?" without opening SQLite. The signal is a proxy — but a proxy that updates on every exec is still the difference between a decorative schema and a live control surface.

## New Goalpost

- Optional probe path that overwrites proxy rows with harness-native usage when a CLI exposes it  
- Surface `block_reason='quota'` on stories when every candidate is exhausted  
- Fleet Scheduler v2 reset-timing bin-packing (already deferred to goal-d38e3c83) can consume real `reset_at` once production data accrues  
