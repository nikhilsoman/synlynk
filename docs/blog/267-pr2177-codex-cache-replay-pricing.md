---
title: "PR #2177 — Codex cache-replay was priced as fresh input"
date: 2026-10-10
series: "Building the OS for Multi-Agent Development"
post: 267
pr: "#2177"
status: open
---

## The Broader Goal at the End of the Previous PR

PR #2166 landed federated subscription-quota capture. The next cost question was already live: parallel dispatches were recording 1.2–1.6M input tokens and the in-flight breaker was killing two of three of them.

## Strategic Shifts in This PR (if any)

The suspected cause was Graphify auto-refresh and pack synthesis (gh:#2140, gh:#2141). Measurement rejected that. The assembled task context was 3,641 bytes and the prompt file was about 7KB. The million-token figure is Codex's tool-loop sum, not a prompt we built.

## What This PR Shipped

Codex `turn.completed.usage.input_tokens` is the sum of every model call inside one turn. `cached_input_tokens` is a subset of that sum. On `job-54fa8a6a` the rollout showed 35 calls. The first call was 21,096 input tokens (5,888 cached). The last call's prompt was 55,388. The turn total was 1,631,802 input / 1,560,832 cached.

`_job_cost_usd` and `resolve_payment_value` priced the whole sum at the fresh-input rate, and daemon cost capture dropped `cache_read_tokens`, so the ledger stored cache as 0. That produced the sentinel lines:

- `job-fccc76c4` (fast tier): `Cost limit breached: $3.88 >= $2.00`, exit -9
- `job-fda2e4ef`: `Zero-file runaway: 1,232,564 tokens`, exit -9
- `job-54fa8a6a`: TOKEN_BLOAT plus COST_INFLATION at $5.03, then `SCOPE_REVIEW_REQUIRED`

Codex fresh input is now `input_tokens - cached_input_tokens`. Cache reads use the cache rate. Claude, Grok, and Agy cache reads stay a separate pool. The circuit breaker and TOKEN_BLOAT check use the fresh remainder. An uncached 600k input still trips the zero-file limit. `_TokenCounts` is unpacked instead of subscripted, so daemon cost rows keep the log's real counts instead of falling through to the t-shirt estimate.

## Brainstorm Visuals Used

None. The evidence is the job logs, the Codex rollout `token_usage_record`s, and the sentinel lines above.

## What This Achieved on the Path to Autonomy

A normal tool loop no longer looks like a runaway and no longer gets killed after the tokens are already spent. The ledger can tell fresh input from cache replay.

## Strategic Note: The Goal at the End of This PR

gh:#2140 and gh:#2141 stay open. They are real gaps (refresh a stale graph, stop swallowing pack errors) and they did not produce this bill. The remaining spend is the cache re-read on each Codex tool call. Shrinking that prefix is a separate change from pricing it honestly.

## Related Docs

- `docs/rca/2026-09-09-ISSUE-1531-dispatch-token-inflation.md`
- `docs/rca/2026-10-08-ISSUE-2133-stale-graph-and-cost-inflation.md`
- GOVERNS story-f336c1c5, goal-8f64eff5
