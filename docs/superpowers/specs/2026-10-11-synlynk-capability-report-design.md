# synlynk capability report — Design Spec

**Date:** 2026-10-11
**Issue:** gh:#1993
**Roadmap:** docs/strategy/2026-10-10-dev-preview-revised-roadmap.md — "this roadmap's single highest-priority `[NEW-ish]` build item" (lines 46, 163)

**Correction vs. the roadmap doc:** The roadmap claims "spec/design exists per #1927's held panel." This is factually wrong — gh:#1927 is an unrelated CLI core/packs-split issue, and `docs/strategy/2026-10-02-decide-panel-roadmap.md` (the doc #1927 itself cites) has zero mentions of #1993 or "capability report." No spec existed before this document. The roadmap's own #1993 reference line (163) should be corrected to drop the "#1927 held panel" attribution once this spec lands.

## Problem

`.synlynk/policy.json`'s `task_allocation` block (the thing CLAUDE.md's Capability-Based Task Allocation table and the Default Agent Role routing actually read) is 100% hand-authored. The Empirical Capability Assessment Policy (CLAUDE.md, 2026-10-04) says routing should instead be driven by measured outcomes already sitting in two tables in the canonical `state.db` (`/Users/nikhilsoman/.synlynk/workspaces/synlynk/state.db`):

- `capability_ratings` (2,238 rows as of 2026-10-11) — per-story quality/rework/review-cycle signal.
- `cost_entries` (2,041 rows) — per-job token/cost signal.

Nothing today reads these back into a routing proposal. `synlynk capability sweep` (already shipped) populates `capability_ratings`; this issue is the missing other half — turning that data into a reviewable `task_allocation` diff.

**Blocking dependencies, reconciled 2026-10-11 (both now actually resolved, not just assumed):**
- gh:#1926 (state.db consolidation) — CLOSED, PR #2085 merged 2026-10-06. Confirmed live: both tables are populated and queryable in the single canonical `state.db`.
- gh:#1831 (11,384 legacy per-job shards under `~/.synlynk/projects/`) — was still showing OPEN on GitHub at the start of this spec; reconciled and closed in this session. Its actual fix (PR #2155, "safe reconciliation path for orphaned state shards") merged 2026-10-09 — the open issue was stale bookkeeping, same pattern as the `story-issue-2010` staleness found earlier this session, not outstanding work. Fleet-wide aggregation is therefore unblocked.

## Schema (read directly from the canonical state.db, 2026-10-11)

```
capability_ratings: id, story_id, agent, model_version, model_at_dispatch, model_at_completion,
  split_model, engg_domain, org_domain, org_domain_tags, industry, phase, signal_source,
  quality, quality_auto, verifier_agent, verifier_model, test_pass_rate, build_success,
  dispatch_rework, micro_rework, pr_review_cycles, duration_vs_estimate, verified_by_ci,
  correct, note, ed25519_sig, ts, discipline, role, stage, stack_tags, legacy_unmapped, pr_number

cost_entries: id, session_date, agent, model, input_tokens, output_tokens, cache_read_tokens,
  story_id, epic_id, phase_id, total_cost_usd, notes, cost_source, estimate_basis, job_id,
  recorded_at, api_equivalent_usd, actual_usd, payment_mode, dispatch_context, context_mode,
  session_id, harness, agent_role, type_id, decision_revision, turn_usage_json, pr_number
```

Join key: `capability_ratings.story_id = cost_entries.story_id` (4,865 matching rows confirmed live). Harness-name columns use the same vocabulary on both sides: `capability_ratings.agent` and `cost_entries.harness` (values: `codex`, `claude`, `grok`, `agy`, `local`, `nikhil`, `muse`, `gemini`, `unknown`).

**No explicit `task_type` column exists on either table.** `cost_entries.type_id` is almost entirely NULL (2,039/2,041 rows) and not usable. The closest real signal is `capability_ratings.discipline` (live values: `testing`, `backend`, `architecture`, `frontend`, `security`, `docs`, `ml`, `cli`, `devops`, plus a `PROG` legacy bucket) — but this vocabulary does **not** line up 1:1 with `.synlynk/policy.json`'s `task_allocation` task_type keys (`implement`, `test`, `css`, `templates`, `content`, `subpages`, `canvas`, `js`, `infra`, `refactor`, `cli-plumbing`, `pm`, `review`, `deploy`, `brainstorm`). This mismatch is a real design gap, not an oversight to paper over — see Approach step 2.

**`quality_verified` column (pending, per gh:#1993's own comment thread):** PR #2172 (merged 2026-10-10, gh:#2170) adds a `quality_verified INTEGER` column to `capability_ratings`/`capability_calibration_results` via `synlynk/db.py`'s version-gated migration path (`_run_legacy_migration_and_repairs` → `ALTER TABLE ... ADD COLUMN quality_verified`). As read directly from the live DB on 2026-10-11 the column is **not yet present** — the migration runs lazily on the next write-path DB connection, not retroactively. The report generator must not assume the column exists; detect it (`PRAGMA table_info`) and if present, treat `quality_verified IN (0, NULL)` as "no real quality signal" (the 5.0 fallback case), not as a confirmed low score, per the issue thread's own guidance. If absent, skip quality-based filtering entirely rather than erroring.

## Approach

1. **New CLI command: `synlynk capability report`** (`synlynk/cli.py`, alongside the existing `capability sweep` subcommand family). Read-only against `state.db` — opens it through `synlynk/db.py`'s normal connection path (so any pending migration, including `quality_verified`, applies normally) but issues no mutating queries of its own.

2. **task_type bucketing: discipline is the practical proxy, with an explicit, reviewable mapping table — not a silent 1:1 rename.** Add a small hardcoded dict in the new report module:
   ```python
   DISCIPLINE_TO_TASK_TYPE = {
       "testing": "test",
       "backend": "implement",
       "frontend": "implement",
       "cli": "cli-plumbing",
       "devops": "infra",
       "architecture": "review",
       "docs": None,       # no task_allocation bucket for docs today — excluded, not guessed
       "security": None,
       "ml": None,
       "PROG": None,
   }
   ```
   Rows whose discipline maps to `None` are excluded from the report (surfaced in a "skipped, no task_type mapping" footer count) rather than forced into a wrong bucket. This mapping lives in code, not policy.json, so it's visible in the PR diff when it's adjusted — expect it to need iteration as `capability sweep` starts tagging stories against the `task_allocation` vocabulary directly (a cleaner fix, but out of scope here — see Out of Scope).

3. **Per harness × task_type bucket, compute:**
   - `n` = count of distinct `story_id` in the bucket (the sample for the `min_sample_size` gate).
   - `median_pr_review_cycles` from `capability_ratings.pr_review_cycles`, restricted to rows where `quality_verified` is `1` (or the column doesn't exist, per Schema section above) — rows with `quality_verified = 0` contribute to `n` only if `pr_review_cycles` itself is a trustworthy field independent of the quality-score fallback (it is — `pr_review_cycles` is a count of actual GitHub review rounds, not a quality score — so do **not** exclude on `quality_verified` for this metric, only for anything built on `quality`/`quality_auto`). State this distinction explicitly in the command's `--help` text since it's non-obvious.
   - `median_total_cost_usd` from the joined `cost_entries.total_cost_usd`, one row per merged PR (dedupe on `pr_number` where non-null, else on `story_id`+`job_id`, to avoid double-counting a story with multiple cost-log rows e.g. a dispatch row plus a reviewer-logged backfill row per the Cost Visibility protocol's backfill mechanism in CLAUDE.md).

4. **Apply the `min_sample_size` gate from `.synlynk/policy.json`'s `capability_policy.min_sample_size` (currently 5).** A bucket with `n < min_sample_size` is reported as "unmeasured" and never produces a routing recommendation, matching the policy text ("treat it as unmeasured, not as evidence of poor fit").

5. **Output: a proposed diff against the live `task_allocation` block, never an auto-write.** For each task_type currently routed to a given harness in `.synlynk/policy.json`, if a *different* harness clears `min_sample_size` on that task_type with a better median on **both** metrics (lower `pr_review_cycles` AND lower `total_cost_usd` — a split result, e.g. cheaper but more review cycles, is reported as inconclusive, not as a recommendation), print:
   ```
   implement: claude (current, n=12, cycles=2.5, cost=$3.10) -> codex (n=18, cycles=1.5, cost=$1.80)
   ```
   Exit 0 always (this is a report, not a gate) — no `--apply`/`--write` flag in this iteration (see Out of Scope).

6. **`--json` output flag** for machine consumption by a future `.synlynk/policy.json` regeneration tool (not built here — see Out of Scope), matching the existing `--json` convention used by `synlynk status --json` etc.

## Out of Scope (explicitly, per the issue and to keep this shippable)

- **Auto-writing `.synlynk/policy.json`.** The issue is explicit: "for human/PM review — not an auto-write." This command only prints/returns a proposed diff.
- **Retroactively reclassifying `discipline` values into the `task_allocation` vocabulary**, or changing what `capability sweep` tags new rows with. The `DISCIPLINE_TO_TASK_TYPE` mapping in this spec is a pragmatic bridge over existing data, not a fix to the root mismatch — that's a separate, larger follow-up (tag calibration/dispatch rows with the real task_type vocabulary at write time) and should be filed as its own issue once this report ships and the mismatch's practical impact is visible.
- **Backfilling `quality_verified` on pre-#2170 rows.** The issue thread itself defers this ("not yet scheduled"); this report treats `NULL` as unverified per that guidance, nothing more.
- **Fleet-wide / multi-workspace aggregation beyond this repo's own `state.db`.** `.synlynk/policy.json`'s own `capability_policy.blocking_dependency` note already draws this line: single-workspace routing (this repo's own `task_allocation`) only ever needed this workspace's canonical `state.db`, which has been queryable since #1926 landed. Nothing here reaches into other workspaces' state.
- **A `--apply` flag or any mechanism to write the diff back.** Per the Capability-Based Task Allocation table's own note: "This table is generated from `.synlynk/config.json`" is the eventual end state, but promotion still requires "a reviewed PR updating this file plus docs/harness-capability-baseline.md, not a silent edit" — this command produces the evidence for that PR, not the PR itself.
- **`grok`/`muse` calibration.** Both are explicitly `not_yet_calibrated` in `capability_policy`; the report will simply show them as unmeasured (too few/no rows) wherever that's true today — no special-casing needed, the `min_sample_size` gate already handles it.

## Testing

1. **Unit:** mock `state.db` with a handful of `capability_ratings`/`cost_entries` rows (including a `quality_verified` mix and a bucket below `min_sample_size`) and assert the bucketing, gating, and dedupe-on-`pr_number` logic directly — no real DB needed for this layer.
2. **Integration:** run the real command against a copy of the live `state.db` (read-only, copy to a temp path first — never open the canonical file read-write from a test) and assert it runs to completion and produces well-formed output (text and `--json`) without mutating the source file (`md5sum` before/after).
3. **Manual verification (not automated):** run `synlynk capability report` for real against the live workspace once implemented, eyeball the proposed diff against the current `task_allocation`, and sanity-check it against what's already informally known (e.g. `feedback_prefer_codex_grok_over_agy.md`'s project-memory finding that Agy is less reliable for dispatch — if the report's cost/cycle numbers don't at least not-contradict that, treat it as a bug to investigate, not a routing surprise to act on blindly).
