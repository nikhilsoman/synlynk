# One discovery pass for every harness baseline

The previous goalpost, after the provider-aware `harness_models` schema landed, was still a static catalog. `BUILTIN_MODEL_CATALOG` and a single Agy live check were what dispatch could trust. Sub-task 1 stored rates, effort, and a `(harness, model, provider)` key. Nothing wrote those columns from a live probe.

## What changed

`run_model_catalog_discovery(conn)` walks `HARNESS_CAPABILITY_BASELINES` instead of a fixed list of four CLIs. Each harness is recorded with `provider='native'`.

Claude, Agy, and Grok still use their model-list commands. The probe now keeps rate, context, and explicit tier fields when the listing payload actually contains them. Agy ids that end in `-low`, `-medium`, or `-high` set `complexity_tier` and `max_effort_level`. Any other id leaves both columns null. A curated row never receives a tier just because its id looks tiered.

Codex has no list command. The pass reads `model` from `CODEX_HOME/config.toml` and stores `discovery_source='config_file'`. If that file has no model, the harness falls back to `BUILTIN_MODEL_CATALOG` with `discovery_source='curated_fallback'`. The same fallback covers a listing harness whose probe returns nothing. When the probe names a model but does not quote a price, the catalog `RateCard` is scaled from per-1k to per-million tokens and stored with `rate_source='curated_fallback'`.

`CONFIGURED_GATEWAY_PROVIDERS` is empty. The gateway loop runs and queries nothing, so an OpenRouter row is not marked stale and no adapter is called. Previously active native rows that this pass did not see become `status='stale'`. They are not deleted.

`synlynk models discover` calls this function. `resolve_tier_model`, `dispatch --model`, and the 24h watch are unchanged. Those are the next two sub-tasks.

## Goalpost

The catalog table can now be filled from whatever harnesses are registered, with rates and tiers only where a probe or the curated card actually supports them. The next step is the 24h refresh, then dispatch reading `status='active'` rows instead of the static catalog.
