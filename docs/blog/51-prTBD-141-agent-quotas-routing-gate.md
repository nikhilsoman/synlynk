# #141 — agent_quotas Base Table + Stage-2 Quota Gate

**Date:** 2026-07-11  
**PR:** TBD  
**Branch:** `dispatch/grok/job-8876c978` → `main`  
**Tracks:** #141 (part of #137 capability-matrix hardening)

---

## The Goal at the End of the Previous PR

#139 wired dead capability signals and the VERIFIER tier into weighted scoring.
#140 made token/cost extraction model-aware (cache tokens, rate table, story/epic/phase FKs).
Routing still had only one real stage: pick the highest `capability_scores` row. The
token-budget brainstorm's three-stage sequence (capability → quota headroom → cost) was
still one-stage in code — `agent_quotas` had been designed in 2026-06 and never created.

---

## What Moved the Goalpost in This PR

Scope stayed the **base matrix only** from the epic design
(`docs/superpowers/specs/2026-07-11-capability-matrix-hardening-design.md` §#141). The
optimizer/scheduler design (maximize fleet output across plan windows) stays a Claude
architect follow-up — no code here.

Two design refinements from the issue body landed in the schema:

1. **`quota_type` is plan-driven**, not a fixed shared shape — includes Claude's **5h**
   rolling window alongside hourly/daily/weekly/monthly.
2. **`unit` column (`tokens` | `requests`)** — unifies with `.synlynk/config.json`
   `budget.limit_requests` instead of assuming every harness caps on tokens.

---

## What Shipped

### Schema

`agent_quotas` in `_DB_SCHEMA` + additive `_migrate_db` path:

| Column | Notes |
|---|---|
| `agent`, `model` | Per-harness / per-model plan row |
| `quota_type` | `5h` \| `hourly` \| `daily` \| `weekly` \| `monthly` |
| `unit` | `tokens` \| `requests` |
| `limit_tokens`, `used_tokens` | Capacity in the row's unit (historical names) |
| `reset_at`, `updated_at` | Window boundary + freshness |
| UNIQUE | `(agent, model, quota_type, unit)` |

Headroom is computed as `max(0, limit_tokens - used_tokens)`.

### Routing (`_best_agent_for_story`)

1. **Capability** — rank candidates for the story coordinate (same fallback ladder as before).
2. **Quota headroom** — **real gate**: drop agents whose binding window cannot cover
   `estimated_tokens` / one request. Empty or unreadable quota signal → **degraded mode**:
   keep the agent eligible (do not hard-block), prefer agents with known headroom.
3. **Cost** — when top remaining scores sit within 0.15, pick the cheaper model via
   `_model_rate_for_version`.

Helpers: `_upsert_agent_quota`, `_quota_status_for_agent`, `_project_request_quota_from_config`,
`_capability_candidates_for_story`.

### Tests

Five acceptance tests under
`test_build_the_base_agent_quotas_table_and_wi_*` in `tests/test_agy_dispatch_fix.py`.

---

## On Track to Multi-Agent Dispatch

With capability scores, costs, and quota headroom all real inputs, the routing engine
finally matches the 2026-06 token-budget design. The next goalpost is not more gating —
it is the **optimizer design doc** (Claude): load-balance and sequence the job queue to
maximize useful output across uneven per-harness plan windows, using this matrix as a
trusted signal rather than a diagnostic label.

---

## New Goalpost

- Probe path that *writes* `agent_quotas` from each harness's own usage reporting.
- Optimizer design doc (#141 follow-up, architect-owned).
- Optional: surface `block_reason='quota'` on stories when every candidate is exhausted.
