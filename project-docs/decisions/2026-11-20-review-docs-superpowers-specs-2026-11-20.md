<!-- generated - source of truth is state.db -->
---
decision_id: dec-a1b506e3
topic: "Review docs/superpowers/specs/2026-11-20-harness-capability-routing-regen-design.md: universal round-robin harness eligibility across all task types, composite capability score (2x success-ratio weight vs 1x rework-rate vs 1x cost/time), and a synlynk capability regen command to close gh:#1993's policy.json drift. Approve, request changes, or flag risks."
date: 2026-11-20
panel: [claude, agy, codex, muse]
status: approved
---

## Topic
Review docs/superpowers/specs/2026-11-20-harness-capability-routing-regen-design.md: universal round-robin harness eligibility across all task types, composite capability score (2x success-ratio weight vs 1x rework-rate vs 1x cost/time), and a synlynk capability regen command to close gh:#1993's policy.json drift. Approve, request changes, or flag risks.

## Panel Inputs

### claude
[model=sonnet; version=2.1.327 (Claude Code)]

**Position: approve with changes.** The direction is right, and a few details need fixing before implementation.

**What's sound**
- Section 1 fixes a real structural problem. With `fallback: []`, a harness can never get samples in that cell, so it can never be measured or promoted. Widening eligibility and letting the existing round-robin gather evidence is the minimal fix. It needs no new mechanism.
- Section 3 is scoped narrowly. It rewrites three fields, leaves `task_allocation` alone, and has a byte-identical test. The `"unproven"` state for `can_gh_write` is more honest than a flat `false`. It also closes the drift behind gh:#1993.

**Risks and requested changes**

1. **Exploration cost is unbounded.** Universal eligibility sends real work to uncalibrated harnesses in every cell. That includes risky ones such as `deploy`, `infra` and `gh_write`, and sends `pm` work to muse. Each of the 16 types needs 4 harnesses × 5 samples, about 80 production dispatches, and each bad draw costs rework. The spec calls this "no new mechanism needed", but it needs at least a guardrail: a cap on exploration spend per cell, or a start-in-observe period for destructive task types. This ties into the recorded $133 cost-inflation incident.

2. **`success_ratio` defaulting to 1.0 on missing `correct` is exploitable.** A harness with no verdicts gets the best possible success term, so it can beat a harness with real evidence of 90% correct. I'd require a minimum number of non-null `correct` rows before the term counts. Below that, use a neutral prior such as the cell median, not a perfect score.

3. **The formula mixes scales.** `rework_rate` adds review cycles (0 to several) to a 0–1 fraction. `normalized_cost_time` adds dollars-over-divisor to `duration_vs_estimate`. The 2:1:1 weights are only meaningful if each term is normalized to a common range, for example min-max or rank within the cell. Otherwise review cycles will dominate, and the weight on success won't mean what the spec says. Add a test for scale invariance.

4. **The router and the regen command can disagree.** The router ranks on `capability_ratings`, but regen demotes `not_yet_calibrated` using "≥5 samples on at least one task_type". That is weaker than the router's per-cell floor. Define the criterion once, in a shared function.

5. **Regen needs a few safeguards:** an atomic write (temp file plus rename), a `--dry-run` or diff output, and a clear failure if the canonical `state.db` path is unresolved. Without these it could silently regen from a stray shard (gh:#1831).

6. **Governance:** this changes routing authority for `pm` and `review`, which are Claude's interim roles. Confirm it is consistent with the policy that a reviewer must differ from the implementer in harness and model. Auto-routing a task to the same harness that implemented it must not create a review collision.

**Recommendation:** approve with changes. Fix items 2 and 3 in the spec text. Add the guardrail in item 1 and the shared criterion in item 4 before the plan is written.

### agy
[model=default; version=1.5.13]

**Last completed task:** Documented harness capability routing & policy regen design spec (`fc754e9d`).  
**Next task:** Decision panel review and recommendation for [2026-11-20-harness-capability-routing-regen-design.md](file:///Users/nikhilsoman/dev/synlynk/.claude/worktrees/chore+claude+harness-capability-routing-regen-design/docs/superpowers/specs/2026-11-20-harness-capability-routing-regen-design.md).

---

### Panel Review & Analysis

The proposed design in [2026-11-20-harness-capability-routing-regen-design.md](file:///Users/nikhilsoman/dev/synlynk/.claude/worktrees/chore+claude+harness-capability-routing-regen-design/docs/superpowers/specs/2026-11-20-harness-capability-routing-regen-design.md) effectively addresses the cold-start stagnation in `LiveQueryRouter` and eliminates long-standing manual policy drift (gh:#1993). My evaluation covers the three core pillars:

1. **Universal Round-Robin Eligibility:** Broadening `fallback` across all 16 task types breaks structural lock-in and allows empirical outcomes to govern routing rather than static assumptions. However, universal eligibility without task-tier risk boundaries introduces operational exposure. High-blast-radius tasks (such as `deploy` or production infrastructure operations) should not be subject to unconstrained trial-and-error across unproven harnesses.
2. **Composite Capability Score (2:1:1):** Heavily weighting correctness (`w1 = 2.0`) over rework and cost/time (`w2, w3 = 1.0`) is architecturally sound—cheap, fast hallucinations must never win routing priority. However, defaulting `success_ratio = 1.0` when non-null `correct` records are absent introduces a perverse incentive: an uncalibrated harness receives a zero error penalty (`1.0 - 1.0 = 0`), allowing it to outscore a seasoned harness operating with an authentic 90% success rate. The fallback should default to a neutral cohort baseline or retain the harness in the sub-floor exploration phase until at least one verified verdict is recorded. Furthermore, `duration_vs_estimate` requires bounded normalization so duration variance does not dwarf the cost divisor.
3. **Capability Policy Regen:** The `synlynk capability regen` command cleanly decouples routing execution from state-derived documentation. The addition of the ternary `"unproven"` status for `can_gh_write` accurately reflects empirical reality (e.g., Muse's unverified attempts) without lossy boolean collapse.

### Recommendation

**Position: Approve with requested changes.** I approve the core architecture and the `synlynk capability regen` workflow, but request two targeted adjustments before finalizing the build plan: (1) revise the missing-correctness fallback from an optimistic `1.0` to the cohort mean (or withhold promotion until at least one explicit correctness verdict exists), and (2) exclude high-blast-radius task types like `deploy` from universal unconstrained fallback until safety prerequisites are verified.

### codex
[model=default; version=codex-cli 0.169.1]

The proposal addresses a real policy-drift problem and correctly separates live routing evidence from the stale `policy.json` documentation layer. Universal fallback eligibility is also a reasonable way to eliminate structural cold-start lock-in, provided it does not bypass operational, role, permission, or harness-availability constraints. The regen command is appropriately scoped, idempotent, and safer than allowing routing code to mutate policy implicitly.

Several risks need resolution before approval. The composite score is underspecified at the data-boundary: it says “per (agent, discipline)” while routing is task-type based, and does not define joins, missing values, or minimum denominators for cost, duration, and rework. Treating zero correctness evidence as `success_ratio = 1.0` can systematically favor unmeasured harnesses over harnesses with observed failures; at minimum, this should be explicitly framed as an exploration policy and paired with confidence/sample safeguards. The rework expression also combines review-cycle counts with a boolean mean without normalization, making its relative influence dataset-dependent despite the stated weights.

Universal eligibility may route work to harnesses that are technically unable to execute a task or lack required permissions. The spec should define a hard safety/availability filter distinct from learned performance eligibility. For regen, “byte-identical” preservation is unlikely if ordinary JSON serialization rewrites whitespace or key ordering; the implementation contract should instead require semantic preservation, atomic replacement, and tests for malformed/missing registry or database state. The `can_gh_write` state machine and mixed true/false attempt semantics also need precise tests.

My recommendation is **request changes**, not reject. Approve the direction conditionally after the spec defines data joins and missing-value handling, adds confidence/safety gates for universal eligibility, specifies atomic semantic policy updates, and expands failure-mode tests.

### muse
[model=default; version=Muse Code 1.4.24 (1.4.24-R9131.1)]

Analysis of `2026-11-20-harness-capability-routing-regen-design.md` against `synlynk/routing.py` and `.synlynk/policy.json`:

**Section 1 - Universal eligibility:** Strongest part of the spec. Root-cause diagnosis is correct: `LiveQueryRouter` is healthy but `task_allocation` `fallback: []` for 9 of 16 task types (css/templates/content/subpages, canvas/js/infra, refactor/cli-plumbing) creates structural lock-in — a harness with no fallback slot can never earn samples to be evaluated. Widening each `fallback` to all-other-harnesses is a data-only fix that lets the existing floor-of-5 round-robin (`dec-8ed62afa`, `SAMPLE_SIZE_FLOOR=5`) actually rotate. No new exploration mechanism needed, minimal blast radius. Risk is bounded: exposure is at most 5 sub-floor dispatches per cell before scoring takes over, and `merge_authority.cross_harness_review_required` remains. Residual risk is on low-volume/high-blast task types — `deploy`, `infra`, `architecture-review` — where 5 exploratory samples may take months and a bad rotation has outsized impact. The spec's Section 4 correctly notes these get few dispatches naturally; habit change to `--agent auto` alone may not seed them.

**Section 2 - Composite score:** Fixes a real gap in current `median(cycles)+median(cost)/divisor` which can reward cheap/fast/wrong. New `score = 2.0*(1-success_ratio) + 1.0*rework_rate + 1.0*normalized_cost_time` with `correct IS NOT NULL` denominator is directionally right, and `w1=2` ensures correctness dominates, informed by the $133/44M-token incident. Two concerns: (a) `success_ratio=1.0` fallback when `correct` is all-null is generous — absence of signal reads as perfect, which temporarily favors unjudged harnesses over one with 4/5 correct. Prefer neutral 0.5 or exclude correctness term until n>=3 non-null. (b) `rework_rate` sums a median (cycles) and a mean (binary rework flag) without normalization, and `normalized_cost_time` sums two medians with different scales — weights will be sensitive to `SCORE_COST_DIVISOR` tuning. Making weights/divisors a tunable constant is correct; add score-breakdown logging for audit.

**Section 3 - `synlynk capability regen` (gh:#1993):** Essential hygiene. Hand-maintained `not_yet_calibrated`/`can_gh_write` is demonstrably stale (muse: 43 ratings + 5 gh_write attempts vs `false`/`n=1`; grok: 627 ratings vs `not_yet_calibrated`). Scoping regen to three fields, leaving `task_allocation` untouched per `dec-0a6db720`, with idempotent DB-to-JSON flow and new tri-state `true/false/unproven` for `can_gh_write`, is well-scoped. Out-of-scoping the empty `gh_write_capability` table to a tech-debt ticket is appropriate.

**Position: Approve with two requested changes before merge.** Ship universal eligibility and regen as designed; amend (1) deploy/architecture-review to require human approval or observe-mode during sub-floor rotation, and (2) change the all-null `success_ratio` default to neutral and log per-component scores. With those, the design restores empirical routing without introducing unmeasured correctness bias.

## Synthesis
Four of the five panelists approve with changes, and codex asks for changes before approval. The panel is unanimous on the direction and on the two main defects, so I'm treating this as approve with required spec changes.

**Where the panel agrees**
- **Universal eligibility (§1):** Widening `fallback` is the right minimal fix. Cells with `fallback: []` can never collect samples, so no harness can be measured or promoted there. Data-only changes plus the existing 5-sample round-robin floor is the right mechanism.
- **`capability regen` (§3):** It is scoped narrowly. It rewrites only the three drifted fields, leaves `task_allocation` alone, and the tri-state `can_gh_write` (`true`/`false`/`unproven`) is more honest than a boolean. It closes gh:#1993.
- **Composite weighting (§2):** Weighting correctness 2x is sound because cheap, fast, wrong output must not win.

**Required changes (raised by 3 or more panelists)**
1. **Missing `correct` must not score 1.0.** All five panelists flagged this. A harness with no verdicts currently beats one with a real 90% success rate. Require a minimum number of non-null verdicts (n≥3) before the term counts. Below that, use a neutral prior such as the cell median. Log per-component scores for audit.
2. **Normalize the score terms.** `rework_rate` adds review-cycle counts to a 0–1 fraction. `normalized_cost_time` adds dollars to a duration ratio. Normalize each term to a common range, for example rank within the cell, and add a scale-invariance test.
3. **Guard high-blast-radius task types.** `deploy`, `infra` and `architecture-review` (and gh-write work) should not get unconstrained exploration. Use observe-mode or human approval during sub-floor rotation. Separately, add a hard availability and permission filter that is distinct from learned eligibility, so a harness that can't do the task is never picked.

**Additional changes (raised by 1–2 panelists)**
4. Define the "calibrated" criterion once in a shared function used by both the router and regen. Right now regen's "≥5 samples on any task type" is weaker than the router's per-cell floor.
5. Make regen safe. Write atomically (temp file plus rename), support `--dry-run` or diff output, and fail loudly if the canonical `state.db` path can't be resolved. Replace the "byte-identical" claim with semantic preservation, since JSON reserialization won't be byte-identical. Add failure-mode tests.
6. Specify the data joins. The spec says "per (agent, discipline)" while routing is by task type. Also define denominators for missing cost, duration and rework values.
7. Confirm that auto-routing `review` and `pm` can't pick the implementer's own harness and model, which would collide with the cross-harness review policy.
8. Add an exploration-spend cap per cell, tied to the $133 cost-inflation incident.

**Next steps:** Revise the spec for items 1–8 and commit it. Then create the GOVERNS-linked parent issue and goal, since the spec can't skip that step. The implementation plan comes only after that. I haven't made any edits yet.

Decision: Approve the design direction (universal round-robin eligibility, the 2:1:1 composite score, and `synlynk capability regen` scoped to the three drifted fields) conditional on the spec being revised first. The revision must (a) replace the missing-correctness default of 1.0 with a neutral prior gated on at least 3 verdicts, (b) normalize all score terms to a common scale, (c) add observe-mode/approval and a hard availability filter for high-blast-radius task types, and (d) fold in the shared calibration criterion, atomic and dry-run-capable regen, explicit data joins, a review-collision check, and an exploration-spend cap. No implementation plan or dispatch begins until the revised spec is committed and linked to a GOVERNS goal.

## Decision
Decision: Approve the design direction (universal round-robin eligibility, the 2:1:1 composite score, and `synlynk capability regen` scoped to the three drifted fields) conditional on the spec being revised first. The revision must (a) replace the missing-correctness default of 1.0 with a neutral prior gated on at least 3 verdicts, (b) normalize all score terms to a common scale, (c) add observe-mode/approval and a hard availability filter for high-blast-radius task types, and (d) fold in the shared calibration criterion, atomic and dry-run-capable regen, explicit data joins, a review-collision check, and an exploration-spend cap. No implementation plan or dispatch begins until the revised spec is committed and linked to a GOVERNS goal.

> Signatures: see 2026-11-20-review-docs-superpowers-specs-2026-11-20.json
