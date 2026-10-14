# Model Catalog Discovery — Implementation Plan

Spec: `docs/superpowers/specs/2026-10-14-model-catalog-discovery-design.md` (committed, signed off 2026-10-14)
Target release: v0.25.1

## Plan-stage questions resolved

1. **Primary key**: 3-column `(harness_name, model_id, provider)`. Migration adds `provider TEXT NOT NULL DEFAULT 'native'` and widens the PK; existing rows backfill as `provider='native'`, which is a no-op for every row that exists today since no gateway rows exist yet.
2. **Probe strategy for harnesses with no "list models" CLI** (Codex confirmed this session): read the harness's own config file as a single-model signal (`~/.codex/config.toml`'s configured model for Codex) and mark `discovery_source='config_file'`. Treat this the same as `curated_fallback` for trust purposes (i.e. not validated against a live listing) but keep it distinguishable in the column for future debugging.
3. **24h cadence basis**: wall-clock since last successful discovery row write (`MAX(discovered_at)` across `harness_models`), not daemon-uptime — matches how `is_probe_stale`/`is_smoke_test_stale` already work, and survives daemon restarts correctly (no re-discovery storm every time the daemon bounces).

## Work breakdown

Four dispatched sub-tasks, mirroring the earlier 4a/4b/4c/4d split pattern — each independently reviewable and mergeable, in dependency order. 1 and 2 must land before 3 and 4 can be meaningfully tested end-to-end, but 3 and 4 can be built against the schema/discovery-function signatures in parallel once 1+2 are specced (not merged) — given v0.25.1 urgency, dispatch 1 first, then 2+3+4 as soon as 1's schema is reviewable (not necessarily merged), so reviewers aren't serialized behind a merge queue.

### Sub-task 1 — Schema migration (state.db)
- Add migration: extend `harness_models` with the 10 new columns from the spec, widen PK to 3 columns, backfill `provider='native'` on existing rows.
- Add/extend `upsert_harness_model()` (or equivalent existing helper in db.py) to accept the new fields; add a read helper `get_active_harness_models(conn, harness=None, tier=None)` returning newest-`discovered_at`-wins rows with `status='active'`.
- Unit tests: migration idempotency (running twice doesn't error/duplicate), backfill correctness on a seeded pre-migration fixture, upsert/read round-trip including the new columns.
- No behavior change to `resolve_tier_model()` or dispatch in this sub-task — schema only, additive and backward-compatible.

### Sub-task 2 — Discovery pipeline generalization
- New `run_model_catalog_discovery(conn)` in `synlynk/models.py` per the spec's 5-step design: iterate `HARNESS_CAPABILITY_BASELINES` keys (not hardcoded), probe native CLI listing where it exists, fall back to config-file read or curated defaults where it doesn't, attempt rate-card extraction, attempt complexity-tier/effort-level extraction (null when unverifiable, never fabricated), upsert via sub-task 1's helper, mark previously-seen-now-absent rows `status='stale'`.
- Gateway loop is present but iterates zero configured providers today (reads an as-yet-empty config list) — must not error on empty, must be trivially extensible when gh:#2076 lands.
- `synlynk models discover` CLI command updated to call this new function instead of (or in addition to) its current narrower behavior, so manual invocation and auto-refresh share one code path.
- Unit tests: per-harness probe success/fallback branches (mock the CLI probe calls), rate/tier extraction parsing, stale-marking behavior, empty-gateway-list no-op.

### Sub-task 3 — 24h auto-refresh wiring
- Add `is_model_catalog_stale(conn, threshold_hours=24)` next to `is_probe_stale`/`is_smoke_test_stale` in `capability_watch.py`, using sub-task 1's `MAX(discovered_at)` query.
- Wire into `maybe_trigger_staleness_checks()`'s existing due-check sequence; spawn via the existing `spawn_staleness_check_thread()` fire-and-forget helper, calling sub-task 2's `run_model_catalog_discovery()`.
- Unit tests: staleness boundary (23h59m vs 24h01m), trigger fires exactly once per due window (no duplicate concurrent spawns), daemon-tick and CLI-startup call sites both exercise the check.

### Sub-task 4 — Dispatch-time live resolution
- `resolve_tier_model(tier, harness, repo_path=None)` in `synlynk/models.py`: primary read path becomes sub-task 1's `get_active_harness_models()`; `BUILTIN_MODEL_CATALOG`/`.synlynk/models.json` become the bootstrap seed used only when state.db has zero discovery rows for that harness (fresh install) or as the rate-card value when a discovered row's rate columns are null.
- `synlynk/dispatch.py`'s explicit `--model` handling (current line ~3928): validate the supplied id against `get_active_harness_models(harness=...)` before subprocess launch; on no match, fail fast with the current valid ids for that harness+tier printed in the error, no job spawned.
- Unit tests: fresh-db bootstrap-seed fallback, state.db-present override of the static catalog, explicit `--model` validation pass/fail paths including the error message content.
- Integration check (manual, by reviewer): re-run the two failing commands from this session (`--model grok-code-fast-1`, `--model gpt-5.1-codex`) and confirm both now fail locally pre-dispatch instead of burning a job.

## Dispatch routing

Per Default Agent Role (interim) and this session's measured GH-write priority (`codex, grok, claude, agy`): this feature is `implement`/`refactor`-shaped, not GH-write-heavy itself (schema + pure functions + one dispatch-path change), so route by the Capability-Based Task Allocation table rather than the GH-write override.

- Sub-task 1 (schema/db) → Codex (cli-plumbing/refactor lane, clean db.py work)
- Sub-task 2 (discovery pipeline) → Grok (infra lane — probing live CLIs, closest existing-work overlap from this session's 4a)
- Sub-task 3 (24h wiring) → Grok (same infra lane, small, stacks naturally on sub-task 2's branch)
- Sub-task 4 (dispatch resolution) → Codex (cli-plumbing lane, touches dispatch.py directly)

Cross-harness+model review required per Hardened PR Review Policy: Codex-authored PRs reviewed by Grok or Agy; Grok-authored PRs reviewed by Codex or Agy. Each dispatch must link a GOVERNS story — file one goal with 4 linked stories (one per sub-task) before dispatching, per the 100% GOVERNS adherence gate.

## Release

v0.25.1: VERSION bump + CHANGELOG entry once all 4 sub-tasks merge; `synlynk release --check-docs` must pass before cut, per Named Release README Sync.
