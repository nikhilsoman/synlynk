# Goal-Cohesive Release Packaging (TPM sweep) - Design

Status: draft for DECIDE panel. Amends dec-fcec4295 (roadmap composition review, gh:#5372).

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

- Size = number of packageable stories AND the sum of `estimated_tokens` (defaulting to the existing 25,000 when null).
- Soft ceiling: 30 stories or 1.5M estimated tokens, whichever is hit first. Both values live in `.synlynk/policy.json` under a new `release_packaging` block (`goal_story_ceiling`, `goal_token_ceiling`, `mixed_pool_cap`), so they are tunable without a code change and are included in audit.
- At or under the ceiling: one proposal containing the whole goal, whatever the count.

### 3.3 Splitting when over the ceiling

1. Group by `stories.phase` (the field already exists). Fill the release with whole phases in ascending order until adding the next phase would exceed the ceiling. A single phase larger than the ceiling is the only case where a phase is split.
2. If stories have no phase, group by dependency components (stories linked by `blocked_by` if present) and fall back to `rowid` order only as a last resort, with the proposal explicitly marked `split_reason: "no_phase_metadata"`.
3. The remainder becomes a continuation: the next proposal for the same goal and theme, titled "<theme> (part N)", filed before the sweep ends so the overflow is never left unscheduled.

### 3.4 Visibility

The sweep result and the proposal ticket body gain a "Packaging" section: story count, token estimate, ceiling used, and either "complete goal" or "part N of M, split at phase <p>, remainder tracked in <ticket>". A goal with unpackaged stories and no continuation ticket is a sweep error, not a warning.

### 3.5 Mixed and orphan pools

Unchanged in behavior: stories without a goal keep a cap, now `mixed_pool_cap` (default 5). Goal-awareness is additive, so existing maintenance batching does not regress. Orphan stories are never pulled into a goal's proposal to fill space.

### 3.6 Duplicate coverage

When a plan's task stories and a parent issue story describe the same work (as with LIVE-35), the parent story is the umbrella. A story with a `gh_issue` whose number is referenced as "Fixes/closes/part of #N" by other packaged stories is listed as umbrella and does not count toward size. Detection is conservative; when unsure, count it.

## 4. Out of scope

- Re-mining and resequencing the held v0.39.x-v0.43.0 queue (tracked from dec-fcec4295).
- Changing `max_active_proposals` (the global cap on open proposals).
- Per-story cost estimation quality.

## 5. Testing

Unit tests on `package_next_release_proposal` with an in-memory state DB:

- A goal of 13 stories is packaged whole.
- A goal of 19 stories where 7 are `in_progress` packages the 12 plain stories and lists the 7 as underway.
- A 40-story goal with 3 phases splits on a phase boundary, never mid-phase, and files a continuation.
- A 40-story goal without phase data splits by the fallback and carries `split_reason`.
- A single oversized phase is the only case that splits a phase.
- Token ceiling triggers before the story ceiling when estimates are large.
- Mixed pool still caps at 5.
- A goal with leftover stories and no continuation ticket raises a sweep error.
- Ordering within a release is stable and does not drop the last-created story preferentially.

Regression: a fixture reproducing the LIVE-35 shape (12 task stories, 1 rollout story, 7 umbrella stories).

## 6. Rollout

Single PR, behind no flag: the old behavior is defective, not a mode. Policy values default to the numbers above. After merge, re-run the packager for goal-62f693b8 and confirm it yields one proposal covering all plan stories.

## 7. Open questions for the panel

1. Are 30 stories / 1.5M tokens the right ceiling, or should the ceiling be cost-only, or review-time-based?
2. Is `phase` reliable enough as the split boundary, or should dependency components be primary?
3. Should umbrella detection (3.6) ship now, or should parent issues simply be excluded from size by an explicit `umbrella` flag set at story creation?
4. Should a continuation ticket be auto-filed by the sweep, or should the sweep stop and require an operator decision?
