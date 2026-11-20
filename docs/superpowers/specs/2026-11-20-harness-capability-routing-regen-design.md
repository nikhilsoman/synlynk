# Harness Capability Routing & Policy Regen — Design

## Status

New spec. Not a rewrite of an existing one. Builds directly on top of PR #5395's
`synlynk/routing.py` (`LiveQueryRouter`, per-cell floor-of-5 round-robin, `dec-8ed62afa`) —
that mechanism is **retained as-is**, not replaced. This spec extends its inputs
(eligibility, scoring) and closes the separate documentation-drift problem (gh:#1993)
that sits next to it.

## Why

Nikhil asked whether all 5 core harnesses (claude, codex, agy, grok, muse) are active
across all task types. The answer pulled from `.synlynk/policy.json`'s
`capability_policy` block was wrong: it listed grok and muse as `not_yet_calibrated`
and `muse.can_gh_write: false`, with a stale hand-written note citing "n=1" for muse.
Direct query of the canonical `state.db` showed the opposite — muse has 43
`capability_ratings` rows, 5 decide-panel participations, 24 real `implement` dispatches,
and 5 `requires_gh_write` attempts (0 verified true, i.e. attempted-but-unproven, not
"never tried" as the flat `false` implied). Grok has 627 `capability_ratings` rows and
is also flagged `not_yet_calibrated`.

Root cause, once traced: `LiveQueryRouter` (shipped in PR #5395) already queries live
evidence correctly for **routing decisions** — it is not stale. What's stale is a
separate, hand-maintained prose block in `policy.json` (`not_yet_calibrated`, `note`,
`eligibility.*.can_gh_write`) that nothing regenerates from the DB. That block is what
I (and presumably anyone else reading policy.json) was trusting as ground truth. This
is exactly the long-tracked gh:#1993 gap.

A second, independent problem surfaced during design: `task_allocation`'s per-task_type
`fallback: []` arrays (css/templates/content/subpages → agy only; canvas/js/infra →
grok only; refactor/cli-plumbing → codex only) mean `LiveQueryRouter`'s round-robin
exploration has nothing to rotate over for those task types — a harness never
assigned fallback status for a task_type can never accumulate samples there, so it can
never be measured, so it can never be promoted. This is a structural lock-in, not
evidence of unsuitability. Nikhil's direction: no harness is presumptively excluded
from any task_type — every harness starts round-robin-eligible everywhere, and only
real outcome data (success ratio, rework rate, cost/time) should ever demote one.

## Governing decisions (binding, not re-litigated here)

- `dec-6da80f2a`, `dec-0a6db720`, `dec-8ed62afa` — per the harness-routing-manifest-mechanics
  spec: Capability-Based Task Allocation (`task_allocation`) is retained as the binding
  routing authority; per-cell floor-of-5 round-robin replaces any global bootstrap
  window; no change to the floor value here.
- This spec does not touch `LiveQueryRouter`'s round-robin branch (sub-floor behavior)
  or the `routing_rotation_state` migration. It extends two things downstream of it:
  the **eligible-set input** (Section 1) and the **score formula** used once a cell
  clears the floor (Section 2).

## Section 1 — Universal eligibility

**Decision:** every task_type's `task_allocation[type]` gains a `fallback` list
containing all harnesses other than its current `harness` (primary). No task_type
keeps `fallback: []`. This is a one-time data edit to `.synlynk/policy.json`, not a
code change — `LiveQueryRouter` already treats `eligible_harnesses` generically.

Concretely, for each of the 16 task types, `fallback` becomes `[claude, codex, agy,
grok, muse] - {harness}` (order doesn't matter; round-robin cursor determines actual
rotation order, not list position). `gh_write`'s existing fallback list is widened the
same way.

This does not change `overrides.role_task_type_compat` — role eligibility (which
*role* a task_type requires: dev/qa/architect/pm) is orthogonal to which *harness*
executes it, per the Role-vs-Harness split in `docs/glossary-agent-vs-harness.md`. A
harness dispatched under a role's identity (e.g. muse running as the `pm` role) is
already how the system works; this spec only widens which harnesses are eligible to be
dispatched under each role's task types.

**Consequence:** `LiveQueryRouter`'s existing round-robin branch now has real
candidates for every task_type, so cold-start lock-in resolves itself as real dispatch
traffic flows through `--agent auto`, with no new exploration mechanism required.

## Section 2 — Composite capability score

Replaces `LiveQueryRouter._score` (`synlynk/routing.py`), used only for cells that have
already cleared the floor-of-5 on every eligible harness (the round-robin branch is
unchanged). Current formula is `median(pr_review_cycles) + median(total_cost_usd) /
divisor` — this folds in review-cycle rework and cost, but not whether the work was
actually correct.

**New formula** (lower score wins, same convention as today):

```
score = w1*(1 - success_ratio) + w2*rework_rate + w3*normalized_cost_time

success_ratio        = COUNT(correct = 1) / COUNT(correct IS NOT NULL)
                        -- capability_ratings.correct, per (agent, discipline)
rework_rate           = median(pr_review_cycles) + mean(dispatch_rework != 0 OR micro_rework != 0)
                        -- capability_ratings.pr_review_cycles / dispatch_rework / micro_rework
normalized_cost_time  = median(total_cost_usd) / SCORE_COST_DIVISOR[task_type]
                        + median(duration_vs_estimate)
                        -- cost_entries.total_cost_usd; capability_ratings.duration_vs_estimate

w1 = 2.0, w2 = 1.0, w3 = 1.0   (confirmed by Nikhil 2026-11-20; success weighted
                                 heaviest so a cheap, fast, wrong answer never wins)
```

If `correct` is null for a row (not all dispatches get a correctness verdict),
exclude it from the `success_ratio` denominator rather than treating it as a failure.
If a harness has zero rows with non-null `correct` for a cell that otherwise cleared
the floor on `pr_review_cycles`/cost, `success_ratio` defaults to `1.0` (no evidence of
failure) rather than `0.0` (no evidence of success) — absence of a correctness signal
is not evidence of wrongness, consistent with the "innocent until proven guilty"
framing driving Section 1.

Weights are a tunable constant in `routing.py`, not hardcoded inline, so a future
re-weighting (e.g. after the recorded $133/44M-token cost-inflation incident) is a
one-line change.

## Section 3 — Capability policy regen (closes gh:#1993)

New CLI subcommand `synlynk capability regen` (wired the same way existing `tool`/
`spec`/`harness` subcommands are in `synlynk/cli.py`). On run, it:

1. Queries `capability_ratings`, `daemon_jobs` (for `requires_gh_write`/
   `gh_write_verified`), and `cost_entries` from the canonical `state.db`
   (`~/.synlynk/registry.json` → `canonical_path`, per the Stray-local-state.db
   correction already in memory).
2. Computes, per harness: total sample count, whether it has ≥5 samples on at least
   one task_type (demotes out of `not_yet_calibrated` once true), and `can_gh_write`
   from `daemon_jobs`: `true` if any `gh_write_verified = 1` row exists for that
   harness, `false` only if every `requires_gh_write = 1` attempt resolved
   `gh_write_verified = 0`/`false` with zero `true` rows, and a third state —
   `"unproven"` — if the harness has `requires_gh_write = 1` attempts but none yet
   resolved true or false (covers muse's current 5-attempts/0-verified state honestly,
   instead of collapsing it into a flat `false`).
3. Rewrites only `capability_policy.not_yet_calibrated`, `capability_policy.note`, and
   `capability_policy.eligibility.*.can_gh_write` in `.synlynk/policy.json` — leaves
   `dev_authority.task_allocation` and every other block untouched, per `dec-0a6db720`.
   The rewritten `note` records the query timestamp and the harness-level counts, same
   style as today's hand-written note, so a human reading it later can still see where
   the numbers came from.
4. Is idempotent and side-effect-free beyond the policy.json rewrite — no dispatches,
   no DB writes. Safe to run on a schedule or ad hoc.

**Out of scope for this subcommand:** the `gh_write_capability` table, found empty (0
rows) during this investigation — it appears to be dead/superseded by
`daemon_jobs.gh_write_verified`. File a tech-debt ticket to confirm and either wire it
up or drop it; this spec's regen command does not read or write it.

## Section 4 — Seeding under-sampled cells

No synthetic calibration-dispatch batch. Once Sections 1–3 ship, cells that are
currently under the floor for a reason other than "never eligible" (e.g. `pm`/
`brainstorm`/`architecture-review`/`deploy` get few dispatches today because that work
is usually done natively by whichever harness is home/PM, not dispatched) get real
samples organically as real backlog work is routed through `--agent auto` instead of
being hardcoded to one harness. This is a change in dispatch habit (prefer `--agent
auto` for eligible task types going forward), not a new mechanism — flagged here so
it's not forgotten, not because it needs its own code.

## Testing

- Unit tests for the new `score()` formula in `synlynk/routing.py`: fixed
  `capability_ratings`/`cost_entries` fixtures covering (a) all-null `correct` →
  `success_ratio = 1.0` fallback, (b) mixed correct/incorrect rows → ratio computed
  correctly, (c) weight application matches the `2.0/1.0/1.0` formula exactly.
- Unit tests for `synlynk capability regen`: in-memory `state.db` fixture with known
  `capability_ratings`/`daemon_jobs` rows → assert the three rewritten `policy.json`
  fields match expected output; assert every other key in `policy.json` is
  byte-identical before/after (proves the "only rewrite these three fields" contract).
- Integration test: widen one task_type's `fallback` in a test `policy.json`, run a
  handful of simulated sub-floor dispatches through `LiveQueryRouter.select`, assert
  the round-robin cursor visits the newly-added harness (proves Section 1 actually
  reaches the existing round-robin code path with no change needed there).

## Explicitly out of scope

- Any change to `LiveQueryRouter`'s round-robin (sub-floor) branch or the floor value
  itself (`SAMPLE_SIZE_FLOOR = 5`) — settled by `dec-8ed62afa`.
- Any change to `role_task_type_compat`.
- The dead/empty `gh_write_capability` table — ticket only.
- Re-weighting the score formula beyond the `2.0/1.0/1.0` confirmed here — future work
  if real data suggests otherwise.
- Building a fleet-wide (multi-workspace) capability report — still blocked on
  #1926/#1831 shard consolidation per `capability_policy.blocking_dependency`; this
  spec is single-workspace only, same scope boundary the existing router already has.
