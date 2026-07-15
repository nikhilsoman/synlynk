# Vizor Effort & Cost Tab: Flag Estimated vs. Actual Cost Rows — Design

**Issue:** [#258](https://github.com/nikhilsoman/synlynk/issues/258)
**Epic:** #210 (Structured Integration Layer, Fable H0 gate) — this closes the epic's last remaining scope alongside #259.
**Theme:** v0.12.0, Measurement Ledger Hardening

## Problem

Fable's H0 pre-GA gate requires: *"every number synlynk displays is either structurally sourced or visibly labeled as an estimate."* Measurement Ledger Hardening Phase 1 (PR #236) already added `cost_source`/`estimate_basis` columns to `cost_entries` and flags non-actual rows with `[est] `/`[legacy] ` prefixes in `project-docs/costs.md`. The Vizor web HUD's Effort & Cost tab (`synlynk/viz.py`) has no equivalent — it currently has zero references to `cost_source` or `estimate_basis` (confirmed via grep), so a structurally-measured row and a heuristically-estimated row render identically. This design closes that gap for the tab's three chart panels (By Dream, By Agent, By Stage) and its summary cards.

## Current Data Flow

`generate_viz_data()` (`synlynk/viz.py:130`) queries `cost_entries` at `synlynk/viz.py:417-419`:

```python
cost_rows = conn.execute(
    "SELECT session_date, agent, total_cost_usd, notes FROM cost_entries ORDER BY id"
).fetchall()
```

Rows are aggregated into pure-float SUM accumulators:
- `by_agent` (`viz.py:442-452`) — `{agent_name: float}`
- `by_stage` (`viz.py:533-534`) — `{stage_name: float}`
- Per-dream `cost_total`/`cost_est` (`viz.py:490-543`)
- `data["costs"]` final assembly (`viz.py:558-562`) — `{"total_usd": float, "by_agent": {...}, "by_stage": {...}}`

No per-row provenance survives this pipeline; `cost_rows` is discarded after the aggregation loop.

`generate_effort_html()` (`viz.py:2503`) consumes this dict to build summary stat cards and three SVG bar charts via a shared `render_bar_chart()` helper (`viz.py:2613`), which currently draws one `<rect>` per row.

## Design

### 1. Data layer changes (`generate_viz_data()`)

Extend the query to also select `cost_source`:

```python
cost_rows = conn.execute(
    "SELECT session_date, agent, total_cost_usd, notes, cost_source FROM cost_entries ORDER BY id"
).fetchall()
```

Classify each row: `is_actual = (row[4] == "actual")`. Every other value — `"estimated_token_rate"`, `"estimated_tshirt"`, `"legacy_unknown"`, or `NULL` (pre-migration rows) — buckets as estimated. This mirrors the exact actual-vs-not split `update_costs()` already uses for the `[est]`/`[legacy]` prefix in `costs.md` (`synlynk/costs.py` `flag = "" if cost_source == "actual" else (...)`).

Change aggregate shapes from `{name: float}` to `{name: {"actual": float, "estimated": float}}` for both `by_agent` and `by_stage`. Each dream gains a new `cost_total_estimated` field alongside its existing `cost_total`/`cost_est`. `data["costs"]` gains a top-level `total_usd_estimated` alongside `total_usd`.

Existing consumers of `by_agent`/`by_stage`/dream `cost_total` as plain floats (e.g. `top_agent = max(by_agent.items(), key=...)` in `generate_effort_html()`) must be updated to read `.get("actual", 0) + .get("estimated", 0)` where a total is needed, or a helper `_row_total(d) -> float` used consistently.

### 2. Summary cards

Add a 5th stat card, "~Estimated": `_fmt_usd(total_usd_estimated)` + `(pct%)` of `total_usd`. Always rendered, even at $0/0%, for consistency with the always-visible flagging philosophy already established in `costs.md` (no conditional suppression when everything happens to be actual).

CSS grid changes from `repeat(4, minmax(0, 1fr))` to `repeat(5, minmax(0, 1fr))` on desktop. Existing responsive breakpoints (`viz.py:2813-2820`) adjust: `repeat(3, minmax(0,1fr))` at the 980px breakpoint (currently 2-col), and unchanged 1-col stacking at 700px.

### 3. Bar chart rendering (`render_bar_chart`)

Each row (`dream_rows`, `agent_rows`, `stage_rows`) gains an `"estimated"` field alongside its existing `"value"`/`"spend"` field (which continues to represent the row's *total*, actual + estimated combined, so existing sort order and max-scale computation are unaffected).

Inside the per-row SVG loop, when a row's `estimated` portion is > 0, draw two adjacent rects instead of one:

```python
actual_val = value - estimated_val
actual_width = (actual_val / max_value) * 380 if max_value else 0.0
est_width = (estimated_val / max_value) * 380 if max_value else 0.0
svg_rows.append(
    f'<rect x="110" y="{y}" width="{actual_width:.2f}" height="18" rx="9" fill="{bar_color}"></rect>'
    f'<rect x="{110 + actual_width:.2f}" y="{y}" width="{est_width:.2f}" height="18" fill="{bar_color}" fill-opacity="0.4"></rect>'
)
```

(Corner radius `rx` omitted on the estimated segment so the two segments read as one continuous bar rather than two pills; a follow-up visual pass can add a rounded cap on the trailing edge only if it reads poorly in practice — not blocking for this PR.)

Rows with zero estimated spend render exactly as today: a single solid rect, no behavior change, no extra DOM.

Value label text becomes `f"{_fmt_usd(value)} (est: {_fmt_usd(estimated_val)})"` when `estimated_val > 0`, otherwise unchanged (`_fmt_usd(value)` alone, or the existing dream `/ est {budget}` format for the By Dream panel — the two suffixes are compatible since one is about budget-vs-actual overrun and the new one is about provenance; they can co-occur, e.g. `"$42.00 (est: $12.00) / est $50.00"` is correct and unambiguous given the differing text, though verbose — acceptable since it's a rare intersection: a dream must both have a budget set AND contain non-actual cost entries).

### 4. Legend

One line added to the existing page subtitle (`viz.py:2829`, `<div class="subtle">Workspace spend, dream overruns, and agent allocation at a glance.</div>`): append ` Faded segments indicate estimated (non-structural) cost.` No per-panel legend, to avoid repeating the same note three times.

### 5. Testing

New/extended tests, added to the existing `tests/test_viz.py`:

- `generate_viz_data()` with a mix of `cost_source="actual"` and `cost_source="estimated_token_rate"` rows for the same agent produces correct `{"actual": X, "estimated": Y}` split in `by_agent`.
- A row with `cost_source=NULL` (simulating a pre-migration legacy row) is classified as estimated, not actual.
- `generate_effort_html()` renders without error given the new data shape, for both the empty-state (`total_usd == 0`) and populated paths.
- Generated HTML contains `(est: $` for a row with estimated spend, and does not contain `(est: $` for a row that is 100% actual.
- Generated HTML contains the "~Estimated" summary card text and a `$0.00 (0%)` rendering when all cost entries are actual (verifying the card is not conditionally suppressed).

## Out of Scope

- Filtering/toggling to show only actual or only estimated rows (considered and rejected during brainstorming — the goal is visibility, not a new interaction model; deferred if requested later).
- Per-entry drill-down or tooltips beyond the `(est: $Y.YY)` inline label (SVG tooltips are a larger interaction-design change, not needed to satisfy the H0 gate).
- `synlynk status` surfacing `rates_updated_at` — that is issue #259, a separate PR.
- Any change to `costs.md` flagging — already shipped in Phase 1, untouched here.
