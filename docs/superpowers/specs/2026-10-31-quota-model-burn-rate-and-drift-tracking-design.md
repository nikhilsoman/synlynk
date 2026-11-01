# Quota Model Burn-Rate Weighting and Estimate Drift Tracking — Design

**Milestone:** v0.26.9 ("Deep review of quota & dispatch capacity mechanics: detection, measurement, capacity recon by plan type, and dispatch pre-flight token-estimation accuracy")
**Related:** gh:#2632 (retitled this session — detection-accuracy bug, kept separate from this design), goal-aa48c456 (loop: keep the capability & cost metric reporting loop running)

## Context

A 2026-10-31 PM research sweep found that the core quota-capture and preflight-exhaustion-gate machinery for v0.26.9 already shipped via the 2026-10-10 federated-quota-capture design (`synlynk/quota_capture.py`, `harness_reservations` table, `_quota_status_for_agent` gate wired into `dispatch.py:4783-4821`). Two older specs — `2026-08-08-quota-aware-dispatch-reservation-design.md` and `2026-09-20-first-class-model-catalog-and-quota-calibration-design.md` — are superseded by what's already shipped; their `Status:` headers should be corrected to reflect that separately, as a docs-only change outside this spec's scope.

The sweep found three real, still-open gaps, which this spec covers together because they share the same code surface (`quota.py`, `cost_entries`, the dispatch-time gate) and are small enough to ship as one unit:

1. `resolve_harness_track` (`synlynk/quota.py:433`) only produces model-aware quota pools for Agy (`claude_proxy`/`gpt_oss`/`gemini`, genuinely metered separately by Antigravity). Claude, Codex, and Grok each report a single pooled 5h/weekly window from their own CLI/billing output regardless of which model is dispatched — confirmed by reading `parse_claude_usage_text`, `parse_codex_rate_limits`, and `parse_grok_billing_line` in `quota_capture.py`, none of which carry a per-model breakdown. The preflight gate is therefore blind to the fact that a heavier model (e.g. Opus) burns through a pooled window faster per token than a lighter one (e.g. Haiku).
2. `cost_entries` has an `estimate_basis` column describing *how* an estimate was derived but no numeric estimate to diff against the final actual row — so estimate accuracy (found this session: job-7dfa3f4e estimated ~$0.19, actual $0.3527, 86% over) cannot be tracked or alerted on.
3. `calibrate_and_update_quota` (`synlynk/quota.py:980`) is only ever invoked manually via `synlynk quota calibrate` (confirmed: its only caller is `synlynk/cli.py:3354-3355`) — it is not wired into the daemon's periodic tick loop the way `_run_capability_watch_tick` already is, so quota calibration silently never runs unless someone remembers to run it by hand.

## Part 1 — Burn-rate weighting for pooled-quota harnesses

**Decision (confirmed with Nikhil):** this is burn-rate *weighting* of a single pooled window, not synthetic per-model sub-pools. Claude/Codex/Grok don't meter per-model usage separately the way Antigravity does for Agy, so partitioning their one real window into fake sub-tracks would misrepresent what's actually being measured. `resolve_harness_track` stays exactly as it is (correct today for all four harnesses) — a new, separate function handles weighting.

### New function: `resolve_burn_rate_multiplier`

```python
def resolve_burn_rate_multiplier(harness: str, model: str, conn=None) -> float:
    """Returns a multiplier predicting how much faster/slower `model` consumes
    `harness`'s pooled quota window compared to that harness's own average
    across all models. 1.0 = neutral (no weighting) — this is the value
    returned for any harness/model pair without enough historical data, so
    unseen models never get an untrusted weighting applied to them.
    """
```

**Data source:** `cost_entries` history. For a given `(harness, model)` pair with at least 5 completed rows — reusing the Empirical Capability Assessment Policy's existing ≥5-sample threshold rather than introducing a second magic number — compute:

```
multiplier = avg_tokens(harness, model) / avg_tokens(harness, all_models)
```

Below 5 samples for that pair, return `1.0`.

**Storage:** a new table, cached rather than recomputed per dispatch (dispatch is latency-sensitive and `cost_entries` can grow large):

```sql
CREATE TABLE IF NOT EXISTS quota_burn_rate_weights (
    harness       TEXT NOT NULL,
    model         TEXT NOT NULL,
    multiplier    REAL NOT NULL DEFAULT 1.0,
    sample_count  INTEGER NOT NULL DEFAULT 0,
    updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (harness, model)
);
```

Recomputed by the same calibration pass as Part 3 below (one calibration tick, two tables updated: `harness_quotas` window calibration — already existing behavior — and this new weights table).

**Integration:** `dispatch.py`'s existing gate (around line 4772-4785) currently computes `_est_tokens` and passes it straight to `quota_status_fn`. This spec changes that call site to multiply `_est_tokens` by `resolve_burn_rate_multiplier(agent, model)` before the gate check, so a job estimated at the same raw token count predicts different pooled-window consumption depending on which model it targets.

## Part 2 — Estimate-vs-actual drift tracking

**Schema change** (`synlynk/db.py`, both `cost_entries` CREATE TABLE definitions at lines ~1851 and ~1998, plus a migration for existing databases):

```sql
ALTER TABLE cost_entries ADD COLUMN estimated_input_tokens INTEGER;
ALTER TABLE cost_entries ADD COLUMN estimated_output_tokens INTEGER;
ALTER TABLE cost_entries ADD COLUMN estimated_cost_usd REAL;
```

These are populated at dispatch time from the same `_est_tokens` value (and its weighted form from Part 1) already computed by the existing gate — no new estimation logic, just persisting a number that is currently computed and discarded. The existing `estimate_basis` column is untouched; it continues to describe *how* the final actual cost was derived (e.g. `cli_manual_entry`, `epic_unresolved`), which is a different concept from the new pre-dispatch prediction being added here.

**Drift alert:** when a job settles and its real `cost_entries` row is written (the existing write path in `db.py` around line 2588), compare `actual_usd` (or `total_cost_usd`) against `estimated_cost_usd` on the same row. If actual exceeds estimate by more than 50%, emit a `COST_ESTIMATE_DRIFT` entry via the existing `check_sentinel_patterns` mechanism (`synlynk/sentinel.py:1146`), writing to `.synlynk/sentinel.md` in the same shape as the existing FLATLINE/SUCCESS_LOOP/QUOTA_EXHAUSTED alerts — no new alerting pathway, no new file.

## Part 3 — Wire quota calibration into the daemon

**Problem confirmed:** `calibrate_and_update_quota`'s only caller anywhere in the codebase is the manual CLI path (`cli.py:3354-3355`, backing `synlynk quota calibrate`). It never runs unless a human remembers to invoke it.

**Fix:** add `_run_quota_calibration_tick` to `synlynk/daemon.py`, modeled directly on the existing `_run_capability_watch_tick` (line 1357) — same cadence mechanism, called from the daemon's periodic loop (`_run_loop`, line 1648) alongside the existing autonomous tick (`_autonomous_tick`, line 1346). This tick calls `calibrate_and_update_quota` for the existing window-calibration behavior, and also recomputes `quota_burn_rate_weights` (Part 1) in the same pass, since both are "refresh this cached derived-from-history number" operations on the same cadence.

**Safety net:** add a staleness warning to `synlynk status`'s output, matching the existing style (`⚠ capability sweep overdue — run 'synlynk capability sweep' (187 jobs since last sweep)`, `⚠ smoke test overdue`) — e.g. `⚠ quota calibration overdue` — so a daemon that isn't running (or crashed) doesn't let calibration silently go stale with no visible signal.

## Out of scope

- Fixing gh:#2632's detection-accuracy bug in `_quota_status_for_agent` itself (false positive/negative exhaustion detection) — tracked separately, not touched by this spec.
- Correcting the `Status:` headers on the two superseded 2026-08-08/2026-09-20 specs — docs-only housekeeping, not part of this implementation.
- Any change to Agy's existing multi-track resolution in `resolve_harness_track` — it already works correctly and is untouched here.
- A UI/dashboard for drift history — Vizor integration, if wanted, is a separate follow-on.

## Testing

- `resolve_burn_rate_multiplier`: unit tests for (a) <5 samples → 1.0, (b) ≥5 samples → correct ratio computation, (c) unknown harness/model → 1.0.
- Dispatch gate integration: a test dispatch with a seeded heavy-multiplier model should reduce effective remaining headroom more than the same raw token estimate on a 1.0x model.
- `cost_entries` migration: existing rows should get `NULL` for the three new columns (not `0`, which would read as a perfect-estimate false positive) and drift comparison must skip rows where `estimated_cost_usd IS NULL`.
- Sentinel drift alert: unit test feeding a synthetic cost_entries row with >50% overage confirms `COST_ESTIMATE_DRIFT` appears in `.synlynk/sentinel.md`; a row within threshold confirms no alert.
- Daemon tick: test that `_run_quota_calibration_tick` is actually invoked from `_run_loop` on the configured cadence (regression guard against this spec reintroducing the exact "exists but never called" bug it's fixing).
