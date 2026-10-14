# Model Catalog Discovery, Cost & Capability Persistence — Design Spec

Status: proposed, pending sign-off
Date: 2026-10-14
Related: gh:#2268 / PR #2278 (Agy-only precedent), gh:#2291 (gap writeup this spec supersedes the scope of), gh:#2287/#2288 (same session, downstream symptoms)

## Problem

Two concrete failures this session (job-48ec683b: `grok-code-fast-1` rejected as unknown; job-32f3643b: `gpt-5.1-codex` rejected for the active account) traced back to a structural gap: synlynk's model catalog is a static, hand-maintained source (`BUILTIN_MODEL_CATALOG` in `synlynk/models.py` + `.synlynk/models.json` fallback), live-validated against the real CLI for exactly one harness (Agy, via PR #2278), with no periodic refresh, no cost-rate discovery, no capability-tier discovery, and no enforcement that dispatch actually reads the live-validated value rather than a hardcoded default or an operator-supplied `--model` string.

Nikhil's direction (2026-10-14): fix this properly, scoped to cover every harness and every future provider gateway, not just patch Grok/Codex to match Agy's narrow fix.

## Requirements (from Nikhil, verbatim intent)

1. Cover **all harnesses** (claude, agy, codex, grok, local, muse) **and any future provider gateways** (OpenRouter, LiteLLM proxy, direct BYOK endpoints — see gh:#2076's `GenericAPIAdapter`, not yet built but the catalog schema must not assume a closed harness set).
2. Run **model discovery** — enumerate what models are actually available per harness/provider right now.
3. Per discovered model, also discover:
   - **Cost**: $/Mtok for input (read), output (write), cache read/write, and tool-use, where the provider exposes it.
   - **Capability**: complexity tier and effort-level support (what `resolve_model_tier`/`--effort` can legitimately ask this model for).
4. **Persist in `state.db`** — not `.synlynk/models.json`, not a hardcoded tuple. State.db is explicitly the canonical store (consistent with `cost_entries`/`capability_ratings` already living there).
5. **Capture token unit rates from the discovery pass itself** — rates are a discovered fact, not a hand-maintained constant.
6. **Refresh on a periodic cycle — every 24h** — a full discovery pass re-runs and rewrites state.db on this cadence, not on-demand/manual-only.
7. **Dispatch always reads the latest known catalog from state.db** — never a static fallback, never an operator's remembered `--model` string without validation against what's actually current.
8. **Target release: v0.25.1.** Framed as critical — this blocks reliable dispatch across the whole fleet, not a nice-to-have.

## Current state (grounded in code read this session)

- `synlynk/models.py`: `BUILTIN_MODEL_CATALOG` (hardcoded tuple, `as_of: 2026-09-24`), `.synlynk/models.json` (static JSON fallback with the same shape), `resolve_tier_model(tier, harness)` reads from these two sources only.
- `discover_models()` (models.py:307) already probes live CLIs for `claude`/`codex`/`agy`/`grok` via `probe_cli_harness()`, plus `probe_local_runtimes()` — but only Agy's result is wired into `resolve_tier_model()`'s validation (PR #2278). The other three harnesses' probe results are discarded by anything that matters for dispatch defaults.
- `cmd_models_discover()` (models.py:348) is a **manual CLI command** (`synlynk models discover`) that writes discovered models into `state.db`'s `models`/`model_families` tables via `upsert_model`/`upsert_model_family` (db.py:733-786) — but `resolve_tier_model()` doesn't read from there; it reads the static files. Two disconnected stores already exist.
- `harness_models` table (db.py:1440) already tracks `(harness_name, model_id)` with `first_seen_at`, `last_seen_at`, `status`, `superseded_by`, `discovery_source` — this is the right shape to build on for existence-tracking, but has no cost-rate or capability-tier columns.
- `capability_watch.py`'s `maybe_trigger_staleness_checks()` is the existing precedent for an **auto-triggered periodic check** (daemon tick + CLI startup both call it, per its docstring) — for harness-auth/capability probes, not model catalog. This spec's periodic-refresh piece should follow the same shape: cheap "is it due" check called from the same places, not a new standalone cron concept.
- `synlynk/dispatch.py`'s explicit `--model` flag (around line 3928: `model_at_dispatch = model or (probe_model(agent, cli) ...)`) is passed straight through with **no validation against anything** — the harness subprocess is the first thing that ever checks whether the id is real.
- `synlynk/_constants.py`'s `HARNESS_CAPABILITY_BASELINES` already has a `strengths` list per harness (free text, not structured) and roles — this is adjacent to "capability" but not the same as a model-level complexity/effort rating.

## Proposed design

### 1. Schema (state.db)

Extend `harness_models` (it already has the right primary key and lifecycle columns) rather than inventing a parallel table — add the fields the current schema is missing:

```sql
ALTER TABLE harness_models ADD COLUMN provider TEXT NOT NULL DEFAULT 'native';
  -- 'native' (the harness's own CLI/account), or a gateway id: 'openrouter', 'litellm', 'byok:<label>'
ALTER TABLE harness_models ADD COLUMN rate_input_per_mtok REAL;
ALTER TABLE harness_models ADD COLUMN rate_output_per_mtok REAL;
ALTER TABLE harness_models ADD COLUMN rate_cache_read_per_mtok REAL;
ALTER TABLE harness_models ADD COLUMN rate_cache_write_per_mtok REAL;
ALTER TABLE harness_models ADD COLUMN rate_tool_use_per_mtok REAL;
ALTER TABLE harness_models ADD COLUMN rate_currency TEXT NOT NULL DEFAULT 'usd';
ALTER TABLE harness_models ADD COLUMN rate_source TEXT;
  -- how the rate was obtained: 'provider_api', 'cli_probe', 'curated_fallback'
ALTER TABLE harness_models ADD COLUMN complexity_tier TEXT;
  -- 'fast' | 'pro' | 'reasoning' | future tiers, discovered not assumed
ALTER TABLE harness_models ADD COLUMN max_effort_level TEXT;
  -- highest --effort value this model actually accepts, per discovery
ALTER TABLE harness_models ADD COLUMN context_window_tokens INTEGER;
ALTER TABLE harness_models ADD COLUMN max_output_tokens INTEGER;
ALTER TABLE harness_models ADD COLUMN discovered_at TEXT NOT NULL;
  -- this specific discovery pass's timestamp, distinct from first_seen_at/last_seen_at
```

Open question for plan stage: whether `provider` becomes part of the primary key (`harness_name, model_id, provider`) to let the same model id exist under both a harness's native account and a gateway (e.g. a Claude model available natively and also via OpenRouter at a different rate) — current read says yes, this needs to be a 3-column key, not 2, to satisfy requirement 1's "any future provider gateway" without collision.

### 2. Discovery pass

A single `run_model_catalog_discovery(conn)` function (new, in `synlynk/models.py`) that:

1. For each registered harness (iterate `HARNESS_CAPABILITY_BASELINES` keys, not a hardcoded list of 4 — so a future harness addition doesn't require touching this function) with `provider='native'`, probe its live "list models" surface. Where no such surface exists (Codex has no `codex models` equivalent found this session — needs a per-harness probe strategy, possibly reading `~/.codex/config.toml`'s configured model as the only known-good signal for harnesses without a listing command), record what's discoverable and mark the rest `discovery_source='curated_fallback'` rather than failing the whole pass.
2. For each configured gateway/BYOK provider (initially: none shipped, since gh:#2076's `GenericAPIAdapter` isn't built yet — this pass must be a no-op with zero configured gateways, not an error), query the gateway's model-list endpoint (OpenRouter and most LiteLLM-compatible proxies expose `/models` with per-model pricing already in the response — this is actually the easiest source of real $/Mtok rates, likely easier than scraping cost from CLI-native harnesses that don't expose pricing via CLI at all).
3. For every model found, attempt to extract rate-card figures from whatever the probe surface offers; when a harness/provider doesn't expose rates at all (several CLI-native harnesses won't), fall back to the existing curated `RateCard` defaults in `BUILTIN_MODEL_CATALOG` and set `rate_source='curated_fallback'` so callers can tell real discovered rates from guesses.
4. Capability/complexity-tier and max-effort-level discovery: where a harness CLI's model-list output encodes this (Agy's tiers are already named `-low`/`-medium`/`-high` in the id itself, for example), parse it; otherwise leave null rather than fabricate a rating — this must not silently invent capability claims that weren't actually verified against the live CLI/provider.
5. Upsert every discovered row into the extended `harness_models` table, updating `last_seen_at`/`discovered_at`; anything previously seen but absent from this pass gets `status='stale'` (not deleted — history matters for the Empirical Capability Assessment Policy's sample tracking) rather than silently vanishing.

### 3. Periodic 24h refresh

Mirror `capability_watch.py`'s existing pattern exactly rather than inventing a second cadence mechanism:

- Add `is_model_catalog_stale(conn, threshold_hours=24)` next to the existing `is_probe_stale`/`is_smoke_test_stale` (same file).
- Add the check into `maybe_trigger_staleness_checks()`'s existing due-check sequence, so it rides the same daemon-tick + CLI-startup trigger points that already exist — no new scheduler, no new daemon loop.
- The discovery pass itself must be cheap/bounded enough to run synchronously inside that existing staleness-check call path (the existing free-probe path already does something structurally similar for harness auth), or be spawned the same way `spawn_staleness_check_thread()` already fires-and-forgets — reuse that thread-spawn helper rather than writing a new one.

### 4. Dispatch always reads the live catalog

- `resolve_tier_model(tier, harness, repo_path=None)` changes from reading `.synlynk/models.json`/`BUILTIN_MODEL_CATALOG` to querying `state.db`'s `harness_models` table for `status='active'` rows matching `(harness, complexity_tier=tier)`, newest `discovered_at` wins. The static catalog becomes the **seed/bootstrap** data only (used once, on a fresh `state.db` with zero discovery history, or as the `curated_fallback` rate source) — never the thing dispatch trusts once real discovery data exists.
- `synlynk dispatch --model <explicit-id>`: validate the supplied id against the current `harness_models` catalog before launching. If it's not found for that harness/provider, fail fast with a clear error listing the actual current valid ids for that harness+tier (turns "burn a job to discover `grok-code-fast-1` is invalid" into an immediate, cheap CLI error) — this directly prevents the two failures that triggered this spec.
- `_write_capability_rating`'s existing hard-refusal for an unregistered agent (`jobs.py:1584-1590`, raises `ValueError` on an unknown harness) stays as-is; this spec only changes where *model* ids are validated, not harness ids.

## Explicitly out of scope for this spec

- Building `GenericAPIAdapter`/actual OpenRouter or LiteLLM wiring (gh:#2076) — this spec only ensures the catalog schema and discovery function don't assume a closed 4-harness world, so that work slots in later without another schema migration.
- Calibration-task scoring (`capability_calibration_tasks`/`capability_calibration_results`, `capability_ledger`) — those are a different, already-existing capability-measurement path (empirical pr_review_cycles/cost per the Empirical Capability Assessment Policy) and are not touched here. This spec's "capability" column is about what a model/provider *advertises* it supports (effort levels, complexity tier), not measured outcome quality.
- Retroactively backfilling historical `cost_entries`/`capability_ratings` rows with corrected rates — this spec is forward-looking only.

## Plan-stage questions to resolve before implementation

1. Primary key shape for the extended `harness_models` table (2-col vs. 3-col with `provider`) — leaning 3-col per the design above, needs confirming against existing FK references elsewhere in db.py before committing.
2. Exact per-harness probe strategy for harnesses with no "list models" CLI surface (Codex confirmed to have none found this session) — config-file read vs. a maintained minimal curated list vs. something else.
3. Whether the 24h check should be wall-clock since last successful discovery or since daemon start — matters for a long-lived daemon vs. frequent CLI-only usage with no daemon running.

## Release

Targeted for **v0.25.1**, per Nikhil's explicit direction (2026-10-14) — treated as a reliability-critical fix, not a feature-cluster named release. VERSION bump and CHANGELOG entry per the Named Release Policy at implementation time, not at spec-approval time.
