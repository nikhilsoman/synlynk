# Hermes local-model measurement wiring — Design Spec

**Date:** 2026-10-11
**Roadmap:** docs/strategy/2026-10-10-dev-preview-revised-roadmap.md, Week 3 / Pillar 4 (line 53)
**Related:** gh:#1984 (CLOSED — Hermes added to local-harness roster), gh:#1993 (synlynk capability report, merged this session via PR #2209), gh:#2110 ([Epic] local/sovereign harness path)

**No interactive user review gate available this round — proceeding per the standing "implement all planned stories autonomously" directive, same pattern as the 2026-10-11 capability-report and SQLite WAL soak-test specs written earlier this session.**

## Problem

The roadmap is explicit that model *selection* for pillar 4 is already done — `Hermes-3-Llama-3.1-8B` is recommended and already present in `synlynk/models.py`'s `BUILTIN_MODEL_CATALOG` (`locality="on_device_local"`, `entitlement_tier=ZERO_COST_LOCAL`) and in the model catalog's `tiers.hermes.local` mapping (`synlynk/models.py:158`). What's missing is **measurement**: turning "Hermes is a 20% contributor" from a claim into a number the new `synlynk capability report` (gh:#1993, shipped) can actually show.

Two concrete gaps, confirmed by reading the code directly:

1. **`hermes` is not a selectable dispatch tier.** `synlynk/dispatch.py:48` defines `MODEL_TIERS = (MODEL_TIER_FAST, MODEL_TIER_PRO, MODEL_TIER_REASONING)` — `"hermes"` is absent. `resolve_model_tier()` (dispatch.py:273) and the `--model-tier` CLI flag (`{fast,pro,reasoning}`) both reject it today. Even though the catalog *contains* a `hermes` tier entry, nothing in the dispatch path can route to it except by harness being `local` and some other tier resolving to it by coincidence — which doesn't happen, since `fast`/`pro`/`reasoning` all map `"local"` to `qwen2.5` or `deepseek-r1`, never to `hermes-3-llama-3.1-8b`.
2. **No traffic-slicing mechanism exists.** `.synlynk/policy.json`'s `capability_policy` block has no concept of "route N% of dispatches of type X to harness/tier Y for measurement purposes" — routing today is all-or-nothing per task_type (via the suspended `task_allocation` table) or fully manual (`--force-harness`/`--model-tier` on a single dispatch call).

Without both, `capability_ratings`/`cost_entries` will never accumulate real Hermes rows, and the Week 2 go/no-go gate (roadmap Section 5, gate 2) explicitly says: if merged-job sample counts aren't trending toward the ≥5 bar, pillar 4 gets descoped from "measured" to "integrated, unmeasured" in the release claims. This spec is what prevents that descope.

## Approach

**Scope deliberately small** — this is a measurement-wiring task, not a new subsystem. Three pieces:

### 1. Add `"hermes"` as a real dispatch model tier

- `synlynk/dispatch.py:48`: `MODEL_TIERS = (MODEL_TIER_FAST, MODEL_TIER_PRO, MODEL_TIER_REASONING, MODEL_TIER_HERMES)` with a new `MODEL_TIER_HERMES = "hermes"` constant alongside the existing `MODEL_TIER_*` constants (find their definitions near line 48 and follow the exact same naming pattern).
- `resolve_model_tier()` must accept `"hermes"` as an explicit `--model-tier hermes` value without raising — it already does structurally once `MODEL_TIERS` includes it (the `ValueError` check at dispatch.py:308-309 is the only gate). No other change needed there.
- **Harness restriction:** `resolve_tier_model()` (`synlynk/models.py`) already returns `f"{harness}-default"` or a `pro`/`fast` fallback when a harness isn't in a tier's map — since `tiers.hermes` only has a `"local"` key, requesting `--model-tier hermes` for a non-`local` harness naturally falls back rather than erroring. That fallback behavior is correct and needs no change; just confirm it with a test (Testing section below) rather than adding new guard logic.

### 2. Fixed-slice routing config in `.synlynk/policy.json`

Add a new top-level block, sibling to `capability_policy`:

```json
"measurement_slicing": {
  "hermes_local": {
    "enabled": true,
    "task_types": ["implement", "test"],
    "slice_pct": 20,
    "harness": "local",
    "model_tier": "hermes",
    "started": "2026-10-11",
    "expires": "2026-11-01",
    "note": "Week 3 pillar 4 measurement wiring (roadmap Section 2). Routes a fixed 20% slice of implement/test dispatches to Hermes-3-Llama-3.1-8B so capability report (#1993) gets real sample rows. Remove this block (or set enabled:false) once the Week 3 go/no-go gate (roadmap Section 5) has read a verdict — this is a time-boxed measurement experiment, not a permanent routing rule."
  }
}
```

- `slice_pct: 20` matches the roadmap's own "20% contributor" framing (Section 2, Week 3) — not an arbitrary choice.
- `task_types` restricted to `["implement", "test"]` because those are the two task types the roadmap text names ("route a fixed slice of implement/test dispatch traffic").
- `expires` gives this a natural sunset tied to the Week 3 gate rather than leaving an unbounded experiment silently steering traffic forever.

**Where it's read:** `synlynk/dispatch.py`'s existing routing path — specifically wherever `resolve_model_tier()`'s result is combined with the harness pick for a dispatch whose `task_type` is `implement` or `test` and whose harness resolves to `local` is already a candidate for this slice (do not widen eligibility beyond harness=`local`, since Hermes only runs on-device). Insert slice-eligibility as a **post-resolution override**: after the normal tier/harness resolution picks a harness and tier for an eligible task_type, read `measurement_slicing.hermes_local`; if `enabled` and today's date is before `expires`, deterministically decide inclusion via a stable hash of the dispatch's `story_id` (or `task` text if no story) modulo 100 compared against `slice_pct` — deterministic hashing (not `random.random()`) so the same story always lands on the same side of the slice across retries, keeping `capability_ratings` rows for one story internally consistent. If included **and** the harness this dispatch was already going to use is `local` (never override a non-local harness pick into local — that would change *harness* routing, not just *model* within an already-local dispatch), override `model_tier` to `"hermes"`.

This keeps the slice conservative: it only ever changes which *model* a `local`-harness dispatch uses, never which *harness* gets picked. That avoids accidentally pulling `implement`/`test` work away from Codex/Grok/Agy's measured routing and reduces blast radius to exactly the local-harness lane.

### 3. Capability report must surface the Hermes rows distinctly

`synlynk/capability_report.py` (shipped via gh:#1993/PR #2209 this session) already buckets by `harness` from `cost_entries.harness`/`capability_ratings.agent`. Confirm (Testing section) that a `local` harness row with `model` = `Hermes-3-Llama-3.1-8B` is **not** collapsed into a generic `local` bucket — the report's existing per-harness bucketing already keys on the `agent`/`harness` string, and `local` dispatches of different models all share that same string today. Since the roadmap's ask is specifically "Hermes's own numbers," add a `--by-model` flag to `synlynk capability report` (additive, defaults off, preserves all existing output when unset) that sub-buckets the `local` harness rows by their `cost_entries.model` column instead of collapsing them, so `synlynk capability report --by-model` can show `local/Hermes-3-Llama-3.1-8B` as its own row with its own `n`/`median_pr_review_cycles`/`median_total_cost_usd` — this is the literal mechanism the roadmap means by "wire it into #1993's capability report."

## Out of Scope

- **Changing the suspended `task_allocation` table.** This slice is a parallel, time-boxed measurement mechanism, not a routing-policy promotion — Hermes getting real numbers doesn't by itself promote it into `task_allocation` (that still requires the ≥5-sample bar and a separate reviewed PR, per the Empirical Capability Assessment Policy).
- **Non-`local` Hermes variants** (`Hermes-3-Llama-3.1-70B`/`405B`) — those aren't `on_device_local`-practical for this measurement window; only the 8B model is in scope, matching the roadmap's explicit recommendation.
- **Auto-expiring the `measurement_slicing` block in code.** The `expires` field is advisory/documentary for this iteration — a human (or the Week 3 gate review) removes/disables the block manually. Auto-enforcement of `expires` is a reasonable follow-up but adds scheduling complexity this time-boxed experiment doesn't need.
- **Retrying/backfilling capability_ratings rows from before this slice existed.** Measurement starts now; no retroactive Hermes attribution.

## Testing

1. **Unit — tier resolution:** `resolve_model_tier`/`resolve_tier_model` with `model_tier="hermes"`, `harness="local"` returns `Hermes-3-Llama-3.1-8B`; same call with `harness="codex"` falls back to the existing `pro`/`fast` fallback chain (not a crash) — assert this explicitly since it's the nuance called out above.
2. **Unit — slice determinism:** given `measurement_slicing.hermes_local.slice_pct=20` and a fixed story_id, inclusion decision is stable across repeated calls; across 1000 synthetic story_ids, inclusion rate is within a reasonable tolerance (e.g. 15-25%) of the configured 20%.
3. **Unit — slice never changes harness:** a dispatch whose harness pick resolves to `codex`/`grok`/`agy` is never overridden to `local` by this mechanism, regardless of slice inclusion — only `model_tier` on an already-`local` dispatch can change.
4. **Unit — capability report `--by-model`:** mock `cost_entries` rows with `harness="local"`, two different `model` values; assert default output collapses them (today's behavior, unchanged) and `--by-model` output sub-buckets them into separate rows.
5. **Integration:** a real (or `--dry-run`) `synlynk dispatch local --model-tier hermes --task-type implement --task "..."` resolves to the Hermes model without error.
6. **Manual verification:** after merge, run a handful of real `implement`/`test` dispatches and confirm at least one lands on the Hermes slice (deterministic hash makes this checkable in advance for a known story_id), and that `synlynk capability report --by-model` then shows a `local/Hermes-3-Llama-3.1-8B` row once ≥1 `cost_entries` row exists for it.
