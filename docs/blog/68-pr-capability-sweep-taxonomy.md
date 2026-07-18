---
title: "Capability Sweep + Industry Taxonomy — Calibrating Agents Against Real Skill Axes"
date: 2026-07-19
series: "Building the OS for Multi-Agent Development"
post: 68
pr: "TBD"
merged: status: open
---

## The Broader Goal at the End of the Previous PR

After #292's model-identity fix, `capability_ratings` rows finally key on a real `model_at_dispatch` instead of collapsing three of four agents into `unknown`. But the ratings themselves were still scored against ad-hoc, free-text `discipline` / `org_domain` / `industry` labels with no standard vocabulary and no calibration mechanism beyond whatever a single job happened to touch. There was no way to bootstrap a new agent's capability profile before it had done any real work, and no way to reward an agent for shipping a PR that sailed through review clean versus one that took four rounds of changes.

## Strategic Shifts in This PR

None to the roadmap — this is the next planned increment of Horizon-0 measurement credibility, decomposed into two independent specs executed in parallel worktrees: capability-sweep-taxonomy (this PR) and payment-model-accounting (in progress, see next post). No API surface was cut; the taxonomy and multiplier are additive to the existing `capability_ratings` schema.

## What This PR Shipped

**Taxonomy layer** (`synlynk/taxonomy_standards.py`): static NAICS / APQC / SFIA lookup tables replace free-text discipline/org_domain/industry fields. `_migrate_db()` crosswalks legacy values on migration via `LEGACY_DISCIPLINE_CROSSWALK` / `LEGACY_ORG_DOMAIN_CROSSWALK` / `LEGACY_INDUSTRY_CROSSWALK`; anything with no match is tagged `legacy_unmapped=1` rather than silently dropped or coerced. `_taxonomy_label(axis, code)` resolves a code to its human-readable label for display, falling back to the raw code for anything unmapped.

**Calibration sweep** (`synlynk/capability_sweep.py`, new, 269 lines): `synlynk capability sweep` seeds each agent's capability ledger from `capability_baseline.json` (shipped with the package) and dispatches SFIA-scoped calibration tasks with independent cross-agent verification scoring, gated by a configurable `capability_sweep.cost_cap_usd` (default `$10`). `capability_ratings` rows seeded this way carry `sample_count` 3–5 and `signal_source='baseline_seed'`, so real, organically-earned ratings can outweigh the synthetic baseline as they accumulate — the blending logic treats baseline seeds as a soft prior, not a permanent score.

**PR review-cycle multiplier** (`synlynk/pr_multiplier.py`, new, 71 lines): `synlynk pr check` now applies a geometric decay — `1.10 × 0.825^(N-1)`, floored at `0.25x` — to a PR's `capability_ratings.quality` values at merge time, where `N = 1 + changes_requested_count`. A clean first-pass approval earns a 10% bonus; each round of requested changes erodes the credit. Scoped to the *current* branch's own PR via `gh pr view --json number` — not any historical PR — so the multiplier can never misapply one PR's review count to another's ledger rows. GitHub-only in v1 (`_is_github_remote()` gates it); off GitHub, ratings pass through unmultiplied.

**Distribution & linkage**: `capability_baseline.json` ships in package releases; `_maybe_open_worktree_pr()` now captures and returns the created/existing PR's number so `capability_ratings.pr_number` can be set at job-finalization time, giving the multiplier something to join against.

**Tests**: four new test files covering taxonomy crosswalk idempotency (including the `legacy_unmapped` edge case), the sweep command's cost guardrail, PR-number capture, and the multiplier's decay/floor/clamping behavior with 8 dedicated cases.

**Follow-up caught in final review**: the sweep command's first pass registered its own CLI taxonomy entry dynamically at `build_parser()`-time via a `weakref.finalize` hook, to satisfy `test_taxonomy_matches_real_cli_surface()` without the author noticing the codebase's existing convention — a static dict entry in `taxonomy.py`, same as all 59 other commands. Fixed as a small follow-up commit; the fix itself broke `test_docs_sync.py` (the generated `docs/reference/commands.md` no longer matched), resolved by regenerating that doc via the existing `scripts/generate_command_docs.py`.

## Brainstorm Visuals Used

None — this spec was scoped directly from the Horizon-0 measurement-credibility backlog without a visual-companion session.

## What This Achieved on the Path to Autonomy

Capability ratings now speak a shared, industry-standard vocabulary (NAICS/APQC/SFIA) instead of free text, making cross-project and cross-agent comparison meaningful. New agents get a defensible starting capability profile instead of a cold-start `unknown`. And the review-cycle multiplier makes `capability_ratings.quality` reflect not just "did the code work" but "did it work on the first try" — a real signal for future agent-routing decisions.

## Strategic Note: The Goal at the End of This PR

Both plan documents for this Horizon-0 measurement cycle are complete: capability-sweep-taxonomy (this PR) and payment-model-accounting (its sibling branch, converting raw token counts into an honest per-payment-model dollar figure — subscription quota, overage, or granted credit — instead of a uniform pay-as-you-go assumption). The next goalpost is finishing payment-model-accounting and, once both land, revisiting the deferred #353 dependency this sweep's organic-reinforcement blending was partially gated on.
