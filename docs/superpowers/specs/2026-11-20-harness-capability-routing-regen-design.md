# Harness Capability Routing & Policy Regen — Design

## Status

New spec. Not a rewrite of an existing one. Builds directly on top of PR #5395's
`synlynk/routing.py` (`LiveQueryRouter`, per-cell floor-of-5 round-robin, `dec-8ed62afa`) —
that mechanism is **retained as-is**, not replaced. This spec extends its inputs
(eligibility, scoring) and closes the separate documentation-drift problem (gh:#1993)
that sits next to it.

**Revision 2 (2026-11-20):** incorporates the decide panel's review
(`project-docs/decisions/2026-11-20-review-docs-superpowers-specs-2026-11-20.md`,
panel claude/agy/codex/muse, approved-with-required-changes). All 8 points raised
(missing-correctness default, unit normalization, blast-radius guard, shared
calibration criterion, regen safety, explicit joins, review-collision check,
exploration-spend cap) are folded into Sections 1–5 below. No implementation
begins until this revision is itself committed and GOVERNS-linked, per the
panel's decision.

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

**Hard availability/permission filter (panel finding 3, part B).** Universal
*learned* eligibility (this section) is not the same gate as *can this harness
physically attempt this task at all* — that gate already exists piecemeal
(`_dispatch_capability_preflight`/`_preflight_dispatch` in `dispatch.py`, e.g.
`can_gh_write`, manifest/auth checks) and must run **before** `eligible_harnesses` is
built, filtering out a harness that fails it entirely rather than letting it enter the
round-robin and fail the dispatch. This spec does not add a new preflight mechanism —
it requires that `LiveQueryRouter.select`'s caller always applies the existing
preflight filter first, so "round-robin-eligible by policy" never overrides "cannot
actually run" (e.g. a harness with `can_gh_write: false`/`unproven` is excluded from a
`requires_gh_write` cell's `eligible_harnesses` outright, not merely disadvantaged by
the score).

**Blast-radius guard (panel finding 3, part A).** For `deploy`, `infra`,
`architecture-review`, and any task dispatched with `--requires-gh-write`: sub-floor
round-robin exploration does not auto-dispatch unattended. These task types'
round-robin picks are surfaced for explicit human approval (reuse the existing
`require_linked_goal_mode`/`cross_harness_review_required_mode` `observe`/`enforce`
pattern — add a `sub_floor_exploration_mode` of the same shape, defaulting to
`observe`: the router still records which harness *would* be picked, but dispatch
waits for a human go-ahead before that pick is actually used for these four
categories). All other task types keep fully autonomous round-robin, unchanged.

**Review-collision filter (panel finding 7).** For the `review` task_type (and any
`pm`-role task acting as a review gate), `eligible_harnesses` must exclude whichever
harness+model implemented the PR under review — matching `merge_authority`'s existing
`cross_harness_review_required` check (reviewer must differ from implementer in
harness **and** model, per `.synlynk/policy.json`). Universal eligibility (this
section) widens the *candidate pool*; it must not widen it into a pool that includes
the implementer itself. This filter runs at the same point as the hard
availability/permission filter above, before the pool reaches `LiveQueryRouter`.

## Section 2 — Composite capability score

Replaces `LiveQueryRouter._score` (`synlynk/routing.py`), used only for cells that have
already cleared the floor-of-5 on every eligible harness (the round-robin branch is
unchanged). Current formula is `median(pr_review_cycles) + median(total_cost_usd) /
divisor` — this folds in review-cycle rework and cost, but not whether the work was
actually correct.

**Data join (panel finding 6 — explicit, replacing the earlier ambiguous
`(agent, discipline)` reference):** every query in this section is keyed by
`(capability_ratings.agent = harness, capability_ratings.discipline = task_type)`,
matching `LiveQueryRouter._sample_count`'s existing join exactly (that method already
uses `agent`/`discipline`, not `agent`/`task_type` — this spec's scoring code reuses
the same two columns so the floor check and the score never disagree on what a "cell"
is). `cost_entries` joins on `(agent = harness, type_id = task_type)`, also matching
`LiveQueryRouter._score`'s existing join today.

**Raw per-harness, per-cell terms**, each normalized to `[0, 1]` across the eligible
harnesses for that cell before weighting (panel finding 2 — this replaces the earlier
raw-unit sum, which mixed review-cycle counts, dollars, and duration ratios with no
common scale):

```
raw_success_deficit(h)  = 1 - success_ratio(h)
raw_rework(h)            = median(pr_review_cycles) + mean(dispatch_rework != 0 OR micro_rework != 0)
raw_cost_time(h)         = median(total_cost_usd) / SCORE_COST_DIVISOR[task_type]
                            + median(duration_vs_estimate)

norm(x, h) = (raw_x(h) - min(raw_x across eligible harnesses in this cell))
             / (max(raw_x across eligible harnesses in this cell) - min(... ) )
             -- 0 if max == min (all harnesses tied on this term)

score(h) = w1*norm(success_deficit, h) + w2*norm(rework, h) + w3*norm(cost_time, h)

w1 = 2.0, w2 = 1.0, w3 = 1.0   (confirmed by Nikhil 2026-11-20; success weighted
                                 heaviest so a cheap, fast, wrong answer never wins)
```

Min-max normalization within the cell (not a fixed global scale) is deliberate: it
keeps the formula scale-invariant per cell — multiplying every harness's cost by a
constant, or every duration by a constant, does not change the ranking, which is the
scale-invariance property the panel asked to be tested (see Testing section).

**Missing-correctness default (panel finding 1 — replaces the earlier flat `1.0`
fallback, which let a harness with zero verdicts beat one with a real 90% success
rate):**

- `success_ratio(h)` is computed from `COUNT(correct = 1) / COUNT(correct IS NOT NULL)`
  **only when** that harness has at least 3 non-null-`correct` rows for the cell
  (`MIN_VERDICTS_FOR_SUCCESS_RATIO = 3`).
- Below that threshold, `success_ratio(h)` is **not** defaulted to `1.0` or `0.0`.
  It takes the **median `success_ratio` across the other eligible harnesses in the
  same cell that do meet the 3-verdict threshold** (a neutral, cell-local prior,
  not an assumption of innocence or guilt).
- If **no** eligible harness in the cell meets the 3-verdict threshold (every harness
  is under-verified), every harness's `success_ratio` is `1.0` and the term
  effectively drops out of the score for that cell — a degenerate case, logged as such,
  not silently treated as meaningful signal.
- Per-component scores (`norm(success_deficit)`, `norm(rework)`, `norm(cost_time)`,
  and which branch of the missing-correctness rule applied) are logged alongside the
  final `score(h)` for audit, per the panel's request.

Weights are a tunable constant in `routing.py`, not hardcoded inline, so a future
re-weighting (e.g. after the recorded $133/44M-token cost-inflation incident) is a
one-line change.

**Shared calibration criterion (panel finding 4).** A single function,
`is_calibrated(harness, task_type, conn) -> bool`, returns
`sample_count(harness, task_type) >= SAMPLE_SIZE_FLOOR` (the same per-cell floor-of-5
`LiveQueryRouter` already uses). Both `LiveQueryRouter.select` (to decide round-robin
vs. scored routing) and `synlynk capability regen` (Section 3, to decide
`not_yet_calibrated` membership) call this one function — today's regen draft used a
weaker "≥5 samples on *any* task_type" criterion, which could mark a harness
calibrated overall while it is still sub-floor on most individual cells; this fixes
that mismatch at the source.

## Section 3 — Capability policy regen (closes gh:#1993)

New CLI subcommand `synlynk capability regen` (wired the same way existing `tool`/
`spec`/`harness` subcommands are in `synlynk/cli.py`). On run, it:

1. Queries `capability_ratings`, `daemon_jobs` (for `requires_gh_write`/
   `gh_write_verified`), and `cost_entries` from the canonical `state.db`
   (`~/.synlynk/registry.json` → `canonical_path`, per the Stray-local-state.db
   correction already in memory).
2. Computes, per harness: total sample count, and `not_yet_calibrated` membership via
   the **same `is_calibrated(harness, task_type)` function Section 2 defines**
   (`sample_count >= SAMPLE_SIZE_FLOOR` on that task_type) — a harness is dropped from
   `not_yet_calibrated` only once `is_calibrated` is true for **at least one**
   task_type, and the rewritten `note` lists *which* task_types it's calibrated on, not
   just a yes/no, so the one-criterion-per-tool mismatch the panel flagged can't
   recur. `can_gh_write` is computed from `daemon_jobs`: `true` if any
   `gh_write_verified = 1` row exists for that harness, `false` only if every
   `requires_gh_write = 1` attempt resolved `gh_write_verified = 0`/`false` with zero
   `true` rows, and a third state — `"unproven"` — if the harness has
   `requires_gh_write = 1` attempts but none yet resolved true or false (covers muse's
   current 5-attempts/0-verified state honestly, instead of collapsing it into a flat
   `false`).
3. Rewrites only `capability_policy.not_yet_calibrated`, `capability_policy.note`, and
   `capability_policy.eligibility.*.can_gh_write` in `.synlynk/policy.json` — leaves
   `dev_authority.task_allocation` and every other block untouched, per `dec-0a6db720`.
   The rewritten `note` records the query timestamp and the harness-level counts, same
   style as today's hand-written note, so a human reading it later can still see where
   the numbers came from.
4. **Safety (panel finding 5):**
   - Resolves the canonical `state.db` path via `~/.synlynk/registry.json` →
     `canonical_path` and **fails loudly** (non-zero exit, clear stderr message) if that
     path can't be resolved or the file doesn't exist — never silently falls back to a
     stray local shard (per `[[stray-local-state-db]]`).
   - Writes `policy.json` atomically: serialize to a temp file in the same directory,
     `fsync`, then `os.replace()` onto the real path. A crash mid-write leaves the
     original file intact, never a truncated one.
   - Supports `--dry-run`, which prints a unified diff of the three target fields
     (old vs. proposed) to stdout and exits without writing anything.
   - The earlier "byte-identical before/after" test claim is replaced: JSON
     re-serialization is not guaranteed byte-identical (key order, whitespace). The
     actual contract, and the actual test, is **semantic preservation** — every key
     outside the three rewritten fields parses to an equal Python value before and
     after, checked by value comparison, not string diff.
   - Explicit failure-mode tests: canonical path file missing, `state.db` locked by
     another writer (busy-timeout then clear error, no partial write), malformed
     existing `policy.json` (refuses to touch it, exits non-zero).
5. Is idempotent and side-effect-free beyond the policy.json rewrite — no dispatches,
   no other DB writes. Safe to run on a schedule or ad hoc.

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

**Exploration-spend cap (panel finding 8).** Widening every `fallback` list (Section 1)
means sub-floor round-robin can now route real backlog work to an untested harness on
a cell it's never touched — the same shape of exposure as the recorded $133/44M-token
cost-inflation incident, just spread across more cells instead of concentrated in one.
Add a per-cell cumulative cap: `routing_rotation_state` gains an
`exploration_spend_usd` column, incremented from `cost_entries.total_cost_usd` each
time a sub-floor round-robin pick is dispatched for that `(harness, task_type)` cell.
Once cumulative spend for a cell crosses `EXPLORATION_SPEND_CAP_USD` (default `$10`,
a `routing.py` constant, tunable) while that cell is still sub-floor, further sub-floor
picks for that specific `(harness, task_type)` pair pause — the round-robin skips it
and falls through to the next eligible harness — until a human reviews and either
raises the cap for that cell or confirms the harness should be scored as-is on
whatever samples it collected before the cap hit. This is a circuit breaker on
*unproven* exploration spend specifically, not a general cost cap — once a harness
clears the floor on a cell, its dispatches are no longer "exploration" and this cap no
longer applies to it.

## Testing

- Unit tests for the new `score()` formula in `synlynk/routing.py`: fixed
  `capability_ratings`/`cost_entries` fixtures covering (a) a harness below the
  3-verdict threshold gets the cell-median `success_ratio`, not a flat default;
  (b) every eligible harness below threshold → `success_ratio = 1.0` for all, term
  drops out, logged as degenerate; (c) mixed correct/incorrect rows above threshold →
  ratio computed correctly; (d) min-max normalization is correct at the boundary
  (single harness, or all harnesses tied on a term, → `norm = 0`); (e) weight
  application matches the `2.0/1.0/1.0` formula exactly; (f) **scale-invariance test**
  — multiply every harness's cost and duration by a constant factor (e.g. 1000x) and
  assert the resulting ranking of harnesses is unchanged.
- Unit test for `is_calibrated()`: confirms `LiveQueryRouter.select`'s floor check and
  `synlynk capability regen`'s `not_yet_calibrated` computation both call the same
  function and agree on the same fixture data.
- Unit tests for `synlynk capability regen`: in-memory `state.db` fixture with known
  `capability_ratings`/`daemon_jobs` rows → assert the three rewritten `policy.json`
  fields match expected output; assert every other key in `policy.json` is
  **semantically equal** (parsed-value comparison, not byte-identical) before/after
  (proves the "only rewrite these three fields" contract); failure-mode tests for
  missing canonical path, locked DB, and malformed existing `policy.json`; test that
  `--dry-run` writes nothing and prints the expected diff.
- Integration test: widen one task_type's `fallback` in a test `policy.json`, run a
  handful of simulated sub-floor dispatches through `LiveQueryRouter.select`, assert
  the round-robin cursor visits the newly-added harness (proves Section 1 actually
  reaches the existing round-robin code path with no change needed there).
- Unit test for the review-collision filter: implementer harness+model excluded from
  `eligible_harnesses` for a `review`-task_type selection, even when universal
  eligibility would otherwise include it.
- Unit test for the exploration-spend cap: simulated cumulative `cost_entries` spend
  for one sub-floor `(harness, task_type)` cell crossing `EXPLORATION_SPEND_CAP_USD` →
  assert that cell is skipped in the next round-robin pick and a different eligible
  harness is chosen instead.

## Explicitly out of scope

- Any change to `LiveQueryRouter`'s round-robin (sub-floor) branch mechanics or the
  floor value itself (`SAMPLE_SIZE_FLOOR = 5`) — settled by `dec-8ed62afa`. This spec
  adds a pre-filter (hard availability/permission, blast-radius guard, review-collision,
  exploration-spend cap) in front of that branch; it does not alter how the branch
  itself rotates once a cell's eligible set is decided.
- Any change to `role_task_type_compat`.
- The dead/empty `gh_write_capability` table — ticket only.
- Re-weighting the score formula beyond the `2.0/1.0/1.0` confirmed here — future work
  if real data suggests otherwise.
- Building a fleet-wide (multi-workspace) capability report — still blocked on
  #1926/#1831 shard consolidation per `capability_policy.blocking_dependency`; this
  spec is single-workspace only, same scope boundary the existing router already has.
- The actual human-approval UX for the blast-radius guard's `observe` mode (which
  surface shows the pending pick, how approval is granted) — this spec only requires
  the mode exist and default to `observe`; the UX is implementation-plan-level detail.
