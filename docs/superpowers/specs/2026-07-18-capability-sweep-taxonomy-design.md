# Capability Sweep + Industry Taxonomy — Design Spec

**Status:** Approved for planning
**Date:** 2026-07-18
**Context:** Horizon-0 measurement credibility (per `docs/strategy/2026-07-12-fable-deep-review-and-strategic-roadmap.md`), ahead of a week of intensive multi-project dogfooding.

## Problem

synlynk's capability ledger (`capability_ratings` table, `_write_capability_rating` in `jobs.py:607-750`) has two structural gaps:

1. **No deliberate calibration.** Scores accumulate only from organic production job outcomes. There's no discovery of which models are actually available per agent CLI (e.g. codex/agy/grok may each support multiple underlying models), and no baseline exists until enough real jobs happen to populate one. A fresh project starts with an empty ledger and `_best_agent_for_story` has nothing to route on.
2. **Homegrown taxonomy.** `engg_domain`/`discipline`, `org_domain`, and `industry` are free-text categories invented for this project, with no crosswalk to anything external. No one outside synlynk can look at a capability report and recognize the categories.

Additionally, this spec closes part of the #353 self-attestation gap (capability scores are 85%-weighted on an agent's own log output) by introducing a genuinely independent scoring path for both the calibration sweep and real production PR outcomes.

## 1. Taxonomy Layer

Adopt three existing, publicly documented, internationally recognized standards — one per axis the project already tracks:

| synlynk axis | Standard | Column affected |
|---|---|---|
| Business/industry domain | **NAICS** (North American Industry Classification System) | `stories.industry` |
| Functional discipline | **APQC PCF** (Process Classification Framework) | `stories.org_domain` |
| Technical competency | **SFIA** (Skills Framework for the Information Age) | `stories.engg_domain` / `discipline` |

**Scope:** curated subset, top 2 hierarchy levels only — roughly 15-30 codes per standard, covering software/product work (synlynk's actual domain), not the full ~2,000-code NAICS tree or ~1,000-subprocess APQC tree. Extensible later by adding codes, not restructuring.

**Storage:** new `synlynk/taxonomy_standards.py` holds three static lookup tables (`NAICS_CODES`, `APQC_CODES`, `SFIA_CODES`), each `{code: {"label": str, "parent": str | None}}`. Existing columns keep their names and types (`TEXT`) — values change from free-text to standard codes. A display-layer lookup (`_taxonomy_label(axis, code)`) translates codes to human-readable labels wherever they're printed (`viz.py`, `__init__.py:3388` capability ledger view, `context.py`).

**Migration:** a new step in `_migrate_db()` runs once, mapping existing free-text values via a hand-built crosswalk dict (e.g. `"backend"` → SFIA `PROG`, `"platform"` → APQC `1.0`, `"unknown"` → NAICS `none`). Any value with no crosswalk entry gets tagged `legacy_unmapped` — kept, not deleted, but excluded from taxonomy-based queries/reports going forward. `test_capability_scoring.py:871-892`'s existing pattern (call `_migrate_db()`, assert post-migration columns) is the template for the new migration's test.

## 2. Calibration Sweep

New command: `synlynk capability sweep` (manual trigger, no cron — matches how `synlynk exec`/live selftest already avoid unattended paid spend).

**Model discovery:** for each agent in `AGENT_CAPABILITY_BASELINES`, attempt CLI introspection first (a `--model` flag's help text, or a models-listing subcommand if the CLI exposes one); if unavailable, fall back to a maintained static list in `_constants.py` (same pattern as `AGENT_CAPABILITY_BASELINES` already uses for `cli`/flags per agent).

**Calibration scope: SFIA only.** For each (agent, model, SFIA-skill) combination, dispatch one small, fixed task targeting that skill (e.g. a tiny `PROG` programming task, a tiny `TEST` testing task, a tiny `REQM` requirements task). NAICS and APQC codes remain descriptive tags attached to real production stories — they are **not** separately calibrated, since there's no meaningful sense in which a model is "better at healthcare" independent of the technical work involved.

**Scoring: independent cross-agent verification.** The agent that ran the calibration task never scores its own output. Either the task has a deterministic checkable outcome (a small test that passes/fails), or a *different* agent reviews and scores the result. This is a genuine fix — not a patch — of the #353 self-attestation problem, for the seeded portion of the ledger.

**Cost guardrail:** before dispatching anything, the sweep computes an estimated cost (agents × models × SFIA skills × 2 calls each for executor + verifier) and aborts before spending past a configurable cap — default **$10** (higher than the live selftest's $2 one-off cap since this is a real periodic operation covering multiple agents/models/skills, but still bounded) — unless overridden explicitly with a confirmation flag. The cap is configurable in `.synlynk/config.json` alongside the existing `limit_usd`/`limit_requests` budget fields.

## 3. Distribution

A `synlynk/capability_baseline.json` file ships inside the synlynk package itself, regenerated periodically by the maintainer's own sweep runs and bundled into each release/upgrade (`install.sh`/PyPI package, alongside the existing `VERSION` bump discipline). On `init` or `upgrade`, if a project's `capability_ratings` table is empty, it seeds from this bundled baseline. Any user can instead (or additionally) run their own `synlynk capability sweep` to generate a project-local baseline from their own paid dispatches.

## 4. Organic Reinforcement

Baseline rows are inserted into `capability_ratings` with a small phantom `sample_count` (3-5) and `signal_source='baseline_seed'` (a new value alongside the existing `'auto'`/`'verifier'`). This guarantees `_best_agent_for_story` never routes against a blank slate, while being light enough that a handful of real organic jobs dominate the weighted average quickly.

**Explicit dependency:** this "organic data quickly outweighs the seed" behavior assumes the ledger's weighted-average math (`_DB_SCORES_VIEW`, `__init__.py:939-953`) is sample-count-aware. It currently is not — #353 documents both a decay-cancellation bug (`weighted_score = SUM(quality*w)/SUM(w)` cancels the age-weighting term for any single dominant sample) and the complete absence of a sample-count factor in ranking (`__init__.py:3393`, `jobs.py:768-769`). **This spec does not re-solve #353** — it is called out here as a prerequisite for the blend to behave as designed, and the implementation plan should either sequence after a #353 fix or explicitly flag the baseline-vs-organic blend as best-effort until that fix lands.

## 5. PR Review-Cycle Multiplier

**Existing mechanism (found during design, not previously known):** `sentinel.py:219-247`'s `_extract_pr_review_cycles()` already pulls real GitHub review state transitions via `_gh_pr_view_payload()` (genuinely independent, not self-attested) and feeds a `pr_review_cycles` count into `quality_auto` at a 15% sub-weight (`jobs.py:678-680`). This has three limitations this spec fixes rather than duplicates:

1. **Timing** — computed at job-completion time (`jobs.py:641`), almost always before a human has reviewed the PR, so it's typically 0/stale.
2. **Weight** — 15% of `quality_auto`, which is itself only 15% of final `quality` when a verifier signal exists (`jobs.py:712`) — real effect is ~2%, far below the intended ±10-25% swing.
3. **Semantics** — counts only full CHANGES_REQUESTED→APPROVED round trips; has no concept of a *bonus* for a clean first-pass approval.

**New mechanism:** a post-hoc multiplicative update, applied at `synlynk pr check` merge time (when review data is actually final), reusing the existing `_gh_pr_view_payload`/`_extract_pr_review_cycles` machinery rather than rebuilding it.

- `N = 1 + (count of CHANGES_REQUESTED reviews before merge)`, sourced the same way `_extract_pr_review_cycles` already does.
- `multiplier(N) = 1.10 × 0.825^(N-1)`, floored at 0.25× (a 1-shot PR gets a 10% bonus; 2-shot ≈ -9%; 3-shot ≈ -25%; asymptotically decaying, never zeroing out the score).
- Applied to the already-written `quality` value on the `capability_ratings` row(s) tied to that PR, clamped to the existing [0, 10] scale.
- The existing 15%-weighted `pr_review_score` component in `quality_auto` is left in place as a legacy fallback for work that never goes through a real PR (e.g. calibration-sweep tasks, or if `synlynk pr check` is skipped) — it is superseded, not removed, when the new post-hoc update runs.

**Linkage requirement:** no `pr_number` is currently stored on jobs/stories — `_maybe_open_worktree_pr` (`jobs.py:246`) only embeds the job ID as free text in the PR body. This spec adds a `pr_number` column (jobs table or an equivalent lookup) populated when the PR is created, so `synlynk pr check` can find the right `capability_ratings` row(s) to update at merge time.

**Scope: GitHub-only for v1.** synlynk's PR/review tooling is entirely GitHub-specific today — `detect_remote_owner_repo()` (`__init__.py:2405-2425`) hardcodes `github.com/`, every PR operation shells to `gh` directly, and there is no GitLab/Bitbucket code path anywhere in the codebase. The multiplier only activates when a `github.com` remote is confirmed; on any other host (or no detectable remote) it defaults to neutral 1.0× rather than erroring. GitLab/Bitbucket review-provider support is out of scope here and should be filed as a separate follow-up issue if needed later. (Note: Jira/Asana/Linear are issue/task trackers, not code-review platforms — they have no REQUEST_CHANGES-equivalent concept and are not a relevant axis for this signal regardless of git host.)

## Schema Changes Summary

- `stories.industry` / `org_domain` / `engg_domain` / `discipline`: values become standard codes (NAICS/APQC/SFIA) instead of free text; column names/types unchanged.
- `capability_ratings.signal_source`: new allowed value `'baseline_seed'` alongside existing `'auto'`/`'verifier'`.
- New `jobs`-side (or equivalent lookup) column: `pr_number` (nullable TEXT/INTEGER), populated by `_maybe_open_worktree_pr`.
- New file: `synlynk/taxonomy_standards.py` (static lookup tables).
- New file: `synlynk/capability_baseline.json` (bundled with package releases).
- Migration additions to `_migrate_db()`: free-text → taxonomy-code crosswalk for existing rows.

## Out of Scope

- Re-solving #353's decay-cancellation/sample-count-blindness bugs (explicit dependency, not duplicated work here).
- GitLab/Bitbucket review-provider support (follow-up issue if needed).
- Calibrating NAICS/APQC axes directly (kept as descriptive tags only, per design discussion).
- Any Jira/Asana/Linear integration (separate, unrelated initiative — not a dependency of this spec).
