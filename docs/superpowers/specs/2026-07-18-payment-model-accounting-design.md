# Payment-Model-Aware Cost/Value Accounting Layer — Design

**Date:** 2026-07-18
**Status:** Proposed
**Related:** [Capability sweep + industry taxonomy design](2026-07-18-capability-sweep-taxonomy-design.md) (Horizon-0 measurement credibility, same theme)

## Problem

`update_costs()` and `cmd_cost_log` both assume every agent CLI is billed pay-as-you-go: tokens in/out multiplied by a flat rate (`$0.003`/1K in + `$0.015`/1K out fallback, or a per-model rate from `_model_rate_for_version`). In practice, agent CLIs are consumed under at least four payment models:

1. **Pay-as-you-go API access** — token cost is a real dollar, billed per request.
2. **Subscription with tiered quotas** — a flat fee covers a bucket of usage; marginal token cost is $0 until the tier's quota is exhausted.
3. **Overage/extra usage** — subscribers who exceed their tier's included quota pay a real marginal rate, but only past the threshold.
4. **Granted/promotional token credits** — a stated face-value balance is consumed with no cash outlay, until exhausted.

Today, `costs.md` shows a single dollar figure that is fictitious for subscription and credit-grant users, and silently wrong for anyone in overage. The token/request unit of account itself is correct and must not change — `check_budgets()`, capability-matrix scoring, and `quota.py`'s rolling-window `agent_quotas` all depend on raw consumption counts. What needs to change is only the dollar translation layer sitting on top of that consumption.

**Out of scope for this spec:** the "without synlynk vs. with synlynk" ROI/efficiency value comparison. This is a distinct concern (comparing synlynk-assisted throughput against an unassisted baseline) and is tracked as a separate follow-up spec, not designed here.

## Section 1: Config schema

New `payment_models` section in `.synlynk/config.json`, keyed per agent:

```json
"payment_models": {
  "codex": {
    "mode": "subscription",
    "tier_quota_tokens_in": 2000000,
    "tier_quota_tokens_out": 500000,
    "overage_rate_per_1k_in": 0.003,
    "overage_rate_per_1k_out": 0.015
  },
  "grok": { "mode": "pay_as_you_go" },
  "agy":  { "mode": "credit_grant" }
}
```

- `mode` ∈ `pay_as_you_go | subscription | credit_grant`.
- Any agent absent from `payment_models` defaults to `pay_as_you_go` using today's existing rate-table behavior — this section is purely additive, no migration needed for existing `.synlynk/config.json` files.
- `subscription` mode requires `tier_quota_tokens_in`/`tier_quota_tokens_out` and `overage_rate_per_1k_in`/`overage_rate_per_1k_out`. `credit_grant` mode requires no extra fields here (balance lives in the `credit_grants` table — Section 3).

## Section 2: Value calculation

New function `resolve_payment_value(agent: str, tokens_in: int, tokens_out: int) -> PaymentValue` in `synlynk/costs.py`, called from `update_costs()` in place of the current single-rate lookup.

```python
@dataclass
class PaymentValue:
    api_equivalent_usd: float
    actual_usd: float
    mode: str
    quota_pct_used: float | None = None      # subscription only
    credit_remaining_usd: float | None = None  # credit_grant only
```

Always computes two figures:

1. **`api_equivalent_usd`** — unchanged from today: `_model_rate_for_version` lookup against the flat pay-as-you-go rate table. This is what capability-matrix cost/quality tradeoffs already key off, and it keeps working identically regardless of how the agent is actually paid for.
2. **`actual_usd`** — branches on `mode`:
   - **`pay_as_you_go`** → `actual_usd = api_equivalent_usd` (today's behavior, unchanged).
   - **`subscription`** → reads `quota.py`'s existing rolling-window `agent_quotas` for that agent's configured cycle window. If cumulative tokens this cycle are within `tier_quota_tokens_in`/`tier_quota_tokens_out`, `actual_usd = 0.0` and `quota_pct_used` is set. Once the cycle's cumulative tokens exceed the tier quota, only the excess tokens are billed, at `overage_rate_per_1k_in`/`overage_rate_per_1k_out`.
   - **`credit_grant`** → decrements the agent's active `credit_grants` row (Section 3) by `api_equivalent_usd` — credits are consumed at API-equivalent value, not a separate rate. While balance remains, `actual_usd = 0.0` and `credit_remaining_usd` is set. If a job's `api_equivalent_usd` would exceed the remaining balance, only the overshoot is billed, falling back to that agent's *next* configured payment model (or `pay_as_you_go` if none is configured) for the overshoot portion only.

The raw token/request values passed into `check_budgets()`, `_write_capability_rating`, and `agent_quotas` are untouched — this function only produces a dollar figure for display and cost-log rows.

## Section 3: Credit grants ledger

New table:

```sql
CREATE TABLE IF NOT EXISTS credit_grants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent TEXT NOT NULL,
    face_value_usd REAL NOT NULL,
    remaining_usd REAL NOT NULL,
    granted_at TEXT NOT NULL,
    expires_at TEXT,
    note TEXT
);
```

New CLI command, mirroring the existing `synlynk cost log` pattern:

```bash
synlynk credit grant --agent <agent> --amount <usd> [--expires <ISO8601>] --note "..."
```

`resolve_payment_value()` selects the oldest non-expired row for that agent with `remaining_usd > 0` (oldest-first consumption when multiple grants exist) and decrements it. When a row reaches `remaining_usd == 0`, it is left in place (not deleted) as a historical record; the next non-exhausted row is used going forward. If no non-exhausted row exists, `actual_usd` for that agent falls back to the next configured payment model per Section 2.

## Section 4: Display

`costs.md`'s per-row table replaces the single "Est. Cost (USD)" column with two columns:

| ... | API-Equiv. Value | Actual $ Charged | ... |
|---|---|---|---|

- **API-Equiv. Value** — `api_equivalent_usd`, always populated, using the same `[est]`/`[est?]` confidence prefixes the current single column already uses.
- **Actual $ Charged** — `actual_usd`, with a bracketed mode tag: `$0.00 [in-quota]`, `$0.42 [overage]`, `$0.00 [credit]`, or plain `$0.42` for `pay_as_you_go` rows (matching today's behavior exactly when no payment model is configured).

`update_costs()`'s existing "Budget Pulse" print block gains a per-agent payment-model rollup line, appended after the existing budget/request-count summary:

```
Budget Pulse
  ...(existing budget/request lines, unchanged)...

  Payment Models
    codex   [subscription]  quota: 62% used this cycle ($0 marginal)
    agy     [credit_grant]  balance: $14.20 remaining of $25.00 granted
    grok    [pay_as_you_go] $0.42 this run
```

No new `synlynk value` or `synlynk status`-embedded command in this pass. This keeps the change additive to the existing `costs.md`/`update_costs()` surface rather than introducing a new one. The "without synlynk vs. with synlynk" ROI comparison remains a separate, not-yet-scoped follow-up spec.

## Schema changes summary

- New table: `credit_grants` (Section 3).
- New config section: `payment_models` in `.synlynk/config.json` (Section 1) — additive, no migration.
- `costs.md` table: two columns replace one (Section 4) — existing rows are historical and not rewritten; the new columns apply going forward only.
- New CLI command: `synlynk credit grant` (Section 3).

## Out of scope

- The "without synlynk vs. with synlynk" ROI/efficiency value comparison — tracked as a separate future spec, not designed here.
- Automatic detection of a provider's real overage rate (Section 2 uses a user-entered flat rate, not a derived one).
- Migrating or backfilling historical `costs.md` rows to the new two-column format.
- Any change to `check_budgets()`, `_write_capability_rating`, or `agent_quotas` internals — these continue operating on raw token/request counts exactly as today.
