# Rework-Rate Routing Metric — Design Spec

**Date:** 2026-10-23
**Issue:** gh:#2551
**Status:** Approved (pending user sign-off on this file)

## Problem

`synlynk capability report` (`synlynk/capability_report.py`) is the Empirical Capability
Assessment Policy's routing mechanism: it's supposed to propose swapping which harness
handles a task type when a measured candidate beats the incumbent on both quality and
cost. In practice it can never propose anything, because its quality signal,
`pr_review_cycles`, medians to exactly `0` for every calibrated harness in every
14-day window measured so far (codex n=656, claude n=476, grok n=234, agy n=183, all
`AVG=0.0`). `propose_diff()` requires the candidate's median to be strictly less than
the incumbent's (`synlynk/capability_report.py:130-135`); two medians of `0` can never
satisfy `<`. This isn't a fleet-health problem — zero review round-trips in a mostly
first-pass-approved fleet is the expected, good outcome — it's a metric-selection
problem: `pr_review_cycles` has no usable variance to route on.

Nikhil's decision on #2551 (2026-10-23 issue comment): **replace** `pr_review_cycles`
as the primary routing signal, not supplement or revise it in place.
`dispatch_rework`/`micro_rework` — two fields already written to every
`capability_ratings` row — were named as the likely replacement candidates.

## Data grounding (live query, 14-day window, canonical `~/.synlynk/workspaces/synlynk/state.db`)

| harness | n | avg dispatch_rework | jobs w/ dispatch_rework>0 | avg micro_rework | jobs w/ micro_rework>0 |
|---|---|---|---|---|---|
| codex | 663 | 0.671 | 144 (21.7%) | 0.015 | 4 (0.6%) |
| claude | 486 | 0.029 | 11 (2.3%) | 0.000 | 0 |
| grok | 239 | 0.059 | 11 (4.6%) | 0.000 | 0 |
| agy | 188 | 0.176 | 23 (12.2%) | 0.059 | 10 (5.3%) |
| muse | 28 | 0.214 | 5 (17.9%) | 40.571 | 28 (100%) |
| local | 19 | 0.000 | 0 | 0.000 | 0 |

Two things fall out of this:

1. **dispatch_rework has real separation as a rate** (codex 21.7% vs. claude 2.3% is a
   meaningful gap), but its per-harness **median is 0 for every harness** — the same
   sparse-signal shape as `pr_review_cycles`. A literal median-for-median swap would
   likely still propose nothing, just for the same structural reason one level down.
2. **micro_rework is dominated by Muse's outlier** (avg 40.6, 100% of its 28 jobs
   nonzero) — this is pre-calibration noise from an uncalibrated harness
   (`[[project-synlynk]]`: Muse calibration is blocked on gh:#2077, human-gated
   `MUSE_API_KEY`), not a real quality signal. Outside Muse, micro_rework is close to
   zero everywhere (codex 0.6%, agy 5.3%, claude/grok 0%).

## Decisions (from brainstorming session)

1. **Replace the metric and the comparison together.** The gating statistic moves from
   "median `pr_review_cycles`" to **dispatch_rework rate**: the percentage of jobs in a
   harness×task_type bucket with `dispatch_rework > 0`. Rates are continuous and already
   show real separation in the live data; medians of a mostly-0/1 field do not.
2. **Require a fixed percentage-point margin**, not a strict inequality, before
   proposing a swap. `MIN_REWORK_RATE_MARGIN_PP = 10.0` (a named module constant in
   `capability_report.py`): the candidate's rework rate must be at least 10 percentage
   points lower than the incumbent's. This is deliberately simple and auditable rather
   than a statistical test — the module has no dependencies beyond stdlib today and this
   keeps it that way.
3. **micro_rework is reported, not gating.** Its rate is computed and included in
   `summarize_buckets()`'s output and the text/JSON report, as context for whoever reads
   a proposal, but it does not participate in `propose_diff()`'s pass/fail logic. Given
   its near-zero baseline everywhere except one uncalibrated harness, folding it into the
   gate risks either no effect (true everywhere but Muse) or a single-outlier false
   signal (if Muse enters a comparison bucket before calibration completes).
4. **Cost stays a required second gate**, unchanged in spirit: a proposal fires only when
   both `rework_rate_ok` (new) and `cost_ok` (existing, `median_total_cost_usd`
   comparison, untouched) hold. This preserves the existing two-factor
   quality-and-economics structure; only the quality half's definition changes.
5. **This is a read-side swap only.** `pr_review_cycles`'s column, its writer
   (`sentinel._extract_pr_review_cycles()`), and `synlynk pr check`'s existing write path
   are untouched — the field keeps being collected and keeps appearing in the report as
   historical/informational data. Only `propose_diff()`'s gating logic stops reading it.
   `min_sample_size` (today's `n >= min_sample_size` "measured" gate, config-driven,
   ≥5 per the Empirical Capability Assessment Policy) is unchanged and still applies per
   bucket before any rate is treated as meaningful.

## Design

### `summarize_buckets()` changes

Add two fields per bucket, alongside the existing `n`/`measured`/`median_total_cost_usd`
(the existing `median_pr_review_cycles` field stays, for the historical/report view):

```python
"dispatch_rework_rate": (
    sum(1 for v in data["dispatch_rework"] if v > 0) / n * 100.0
    if n else None
),
"micro_rework_rate": (
    sum(1 for v in data["micro_rework"] if v > 0) / n * 100.0
    if n else None
),
```

This requires the bucket-collection step (`collect_buckets()` or equivalent upstream of
`summarize_buckets()`) to also accumulate raw `dispatch_rework`/`micro_rework` values per
bucket, the same way it already accumulates `cycles` and `costs`.

### `propose_diff()` changes

Replace the `cycles_ok` check with:

```python
MIN_REWORK_RATE_MARGIN_PP = 10.0

rework_rate_ok = (
    entry["dispatch_rework_rate"] is not None
    and current_entry["dispatch_rework_rate"] is not None
    and (current_entry["dispatch_rework_rate"] - entry["dispatch_rework_rate"])
        >= MIN_REWORK_RATE_MARGIN_PP
)
```

`cost_ok` is unchanged. The gate becomes `if rework_rate_ok and cost_ok:`. Proposal
dicts gain `dispatch_rework_rate`/`micro_rework_rate` fields alongside the existing
`median_pr_review_cycles`/`median_total_cost_usd` ones already on `current`/`proposed`,
so a human reading a proposal sees both the new gating numbers and the old
historical ones.

### `format_text_report()` / JSON output changes

Surface `dispatch_rework_rate` and `micro_rework_rate` (both as context, the latter
explicitly labeled non-gating) in both the per-bucket summary table and any proposal
line. The "no proposals" message updates from referencing "median" to referencing the
new rate-and-margin framing, so a reader isn't left checking stale wording against new
logic.

## Testing

- Unit tests for `summarize_buckets()`: rate computed correctly including the `n == 0`
  and all-zero-rework edge cases (rate should be `0.0`, not `None`, when `n > 0` and no
  rows have rework).
- Unit tests for `propose_diff()`: margin boundary (`exactly 10.0pp` passes, `9.9pp`
  doesn't), both-zero case no longer silently matches (0% vs 0% is a 0pp margin, fails
  as expected — this must NOT regress to "propose a swap when both are tied at zero"),
  cost_ok still required alongside the new rate gate.
- A regression test reproducing the exact today's-data shape (all harnesses at
  `median_pr_review_cycles == 0`) should now be able to produce a rate-based proposal
  where the old median-based logic produced none — this is the spec's actual
  acceptance criterion.
- Existing tests referencing `cycles_ok`/`median_pr_review_cycles`-driven proposals need
  updating to the new field names; no behavior they cover is removed, since
  `median_pr_review_cycles` remains computed and reported.

## Out of scope

- Changing `min_sample_size` or the Empirical Capability Assessment Policy's ≥5-sample
  rule.
- Any change to how `dispatch_rework`/`micro_rework` themselves are computed or written
  (`jobs.py:_count_dispatch_rework`, `jobs.py:_extract_micro_rework`).
- Fixing `quality_verified` coverage (~5% of rows) or `pr_number` coverage (~24% of
  rows) — both flagged in #2551 as separate, real gaps, but not blocking this metric
  swap and not addressed here.
- The capability sweep / production backfill work — held separately per the standing
  v0.25.3 conductor sequence, requires its own bounded scope, cost cap, and verified
  backup before any run.
