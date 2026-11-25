# Goal-Cohesive Release Packaging (TPM sweep) - Design

Status: panel complete (dec-fb8ce5f7, approve with amendments, folded in below); awaiting sign-off. Amends dec-fcec4295 (gh:#5372).

## 1. Problem

`package_next_release_proposal()` in `synlynk/tpm_sweep.py` packages a goal-targeted proposal with a flat count cap of 12, enforced twice (SQL `LIMIT 12` near line 1211, and `target_count=12` in `_cluster_candidate_stories`). Stories without a goal get a flat cap of 5.

Observed on LIVE-35 (goal-62f693b8): the plan produced 13 stories, which would have left one orphaned. Folding two stories together fixed the symptom for that one goal. It also turned out that the goal holds 19 open stories, because the 7 parent-issue stories (#5498-#5504) are linked to the same goal and are `in_progress`. The cap would have dropped 7 of 19.

Defects, in order of severity:

1. **The cut is arbitrary.** The query orders by readiness, then priority, then `rowid`, and `LIMIT` cuts the tail. The story removed is whichever was created last, not whichever is least related. For LIVE-35 that is the rollout-verification story, which is meaningless without the rest.
2. **The cut is silent.** Nothing in the proposal, the sweep result or the logs says that stories were left out of a goal.
3. **Already-started work consumes the cap.** `in_progress` stories are selected and count against 12, though they need no packaging decision.
4. **A count is the wrong unit.** Twelve one-line config stories and twelve migrations carry very different review and rollback weight. `estimated_tokens` is already on every candidate and is not used.
5. **dec-fcec4295 was only partly implemented.** The panel recommended a soft ceiling and splitting at plan-phase boundaries with same-theme continuations. The code applied "goal-aware" but kept a count cut at an arbitrary point.

## 2. Principle

Stories that share a goal ship together. Proximity (same `goal_id`) outranks any count. A ceiling exists only as a safety valve against an unreviewable release, and when it triggers, the split happens at a declared boundary, never by insertion order, and it is reported.

## 3. Design

### 3.1 Candidate selection

For a goal-targeted proposal, select every story with `goal_id = target` and `status NOT IN ('done','archived')`. Remove `LIMIT 12`.

Stories with status `in_progress` or with an open PR are attached to the proposal for context (listed under "already underway") but are excluded from the size computation and from the ceiling.

### 3.2 Size and ceiling

- Size = number of packageable stories AND the sum of `estimated_tokens`. Null estimates default to the existing 25,000, so at defaults 1.5M tokens equals 60 stories: until estimates are real, the token ceiling is a count proxy and the 30-story ceiling is what binds. The spec states this rather than hiding it.
- Both ceilings are soft defaults in `.synlynk/policy.json` under a new `release_packaging` block (`goal_story_ceiling: 30`, `goal_token_ceiling: 1500000`, `mixed_pool_cap: 5`), tunable without a code change.
- Boundary semantics are inclusive: a goal with exactly 30 packageable stories ships whole.
- Cost-only and review-time ceilings were rejected by the panel (cost does not track review burden; review time is not modeled yet). A review-time or uncertainty multiplier is a later refinement.
- At or under the ceiling: one proposal with the whole goal.

### 3.3 Splitting when over the ceiling

1. **Dependency closure is a hard constraint.** Stories linked by `blocked_by` form components; a component is never split across proposals unless an explicit dependency edge permits it. A story blocked by `in_progress` work is a constraint on ordering, not just context.
2. **Phase is the preferred cut among valid cuts.** Fill the release with whole phases in ascending order until the next phase would exceed a ceiling. A cut is valid only if no dependency edge crosses it.
3. **No silent fallback.** If phase data is missing, mixed or cyclic, or every phase cut would sever a dependency, the sweep does not cut by `rowid`. It escalates to the operator: the proposal is held, a warning names the cause, and nothing is silently dropped.
4. **A single phase larger than the ceiling** is escalated the same way; it is the only case where a phase may be split, and only with operator confirmation.
5. **Escape hatch.** A goal whose phases are independently releasable may declare so in its metadata, in which case each phase is its own proposal with no continuation coupling.
6. **Continuation is auto-filed, but only on a clean boundary.** The continuation ("<theme> (part N)") is created transactionally with the original proposal and is idempotent, keyed by goal, theme and part, so repeated sweeps never duplicate it. It carries the split reason and the severed phase, and inherits owner and priority.
7. **Continuations are exempt from `max_active_proposals`**, otherwise the overflow gets blocked and the orphan problem returns. Milestone versions across parts are sequential (part 1 before part 2) and part 2 depends on part 1.
8. **Membership drift.** If stories join or leave the goal between proposal creation and dispatch, the sweep recomputes "part N of M" and refreshes the packaging section; a story added after a proposal was cut lands in the next unreleased part. Cross-goal dependencies are surfaced in the packaging section and never pulled in implicitly.

### 3.4 Visibility

The sweep result and the proposal ticket body gain a "Packaging" section: story count, token estimate, ceilings used, and either "complete goal" or "part N of M, split at phase <p>, remainder tracked in <ticket>". A goal with unpackaged stories and no continuation or escalation is a sweep error, not a warning.

### 3.5 Mixed and orphan pools

Unchanged in behavior: stories without a goal keep a cap, now `mixed_pool_cap` (default 5). Goal-awareness is additive. Orphan stories are never pulled into a goal's proposal to fill space.

### 3.6 Umbrella stories

A new boolean `umbrella` on stories is the source of truth. Umbrella stories and `in_progress` stories are excluded from both ceilings but listed in the proposal's context section. LIVE-35's seven parent stories (#5498-#5504) are backfilled with `umbrella=1`. Parsing "Fixes/part of #N" references is a warning only ("story X looks like an umbrella; set the flag"), never a source of truth, because reference text is inconsistent and can be edited after packaging.

## 4. Out of scope

- Re-mining and resequencing the held v0.39.x-v0.43.0 queue (tracked from dec-fcec4295).
- Changing `max_active_proposals` (the global cap on open proposals).
- Per-story cost estimation quality.

## 5. Testing

Unit tests on `package_next_release_proposal` with an in-memory state DB:

- A goal of 13 stories is packaged whole; exactly 30 is packaged whole (inclusive boundary).
- A goal of 19 stories where 7 are `in_progress` or `umbrella` packages the 12 plain stories and lists the 7 as underway/umbrella context.
- A 40-story goal with 3 phases splits on a phase boundary, never mid-phase, and files one continuation.
- A phase cut that would sever a `blocked_by` edge is rejected and the sweep escalates instead.
- A 40-story goal with missing, mixed or cyclic phase data escalates; it never cuts by `rowid`.
- A single oversized phase escalates and splits only with operator confirmation.
- Token ceiling binds before the story ceiling when estimates are large; with null estimates only the story ceiling binds.
- Repeating the sweep produces no duplicate continuation (idempotency).
- A continuation is created even when `max_active_proposals` is already reached.
- Stories added after proposal creation are reflected in "part N of M".
- A reference-parsed umbrella produces a warning and is still counted until flagged.
- Mixed pool still caps at 5; ordering never drops the last-created story preferentially.

Regression: a fixture reproducing the LIVE-35 shape (12 task stories, 7 parent stories flagged umbrella and `in_progress`, one rolled-up verification story).

## 6. Rollout

Single PR, no flag: the old behavior is defective, not a mode. One migration adds `stories.umbrella` (default 0) and the policy block; LIVE-35's parents are backfilled in the same PR. After merge, re-run the packager for goal-62f693b8 and confirm one proposal covering all plan stories.

## 7. Resolved panel questions

1. Ceiling: dual 30 stories / 1.5M tokens, soft, in policy.json; cost-only rejected.
2. Split boundary: dependency closure is a hard constraint; phase is the preferred valid cut; no silent fallback.
3. Umbrella: explicit flag; reference parsing is a warning only.
4. Continuation: auto-filed, transactional, idempotent, only on a clean boundary; fallback cuts escalate.
