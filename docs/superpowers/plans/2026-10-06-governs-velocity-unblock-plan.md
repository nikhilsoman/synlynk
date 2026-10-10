# Implementation Plan: GOVERNS-Adherence Velocity Unblock

> Design: `docs/superpowers/specs/2026-10-06-governs-velocity-unblock-design.md`
>
> Tracking: this plan; cross-references #2041, #2048, #2051, #2056 (already-filed
> overlapping bugs — see §0), #1990 (GOVERNS hard-fail, §3.4 scope only).

## 0. Overlap reconciliation (read this before dispatching anything)

Three of the four work items below already have partially-overlapping open
issues filed independently of this design. This plan does not duplicate them;
it either folds their scope in explicitly or narrows this plan's own scope to
avoid collision. Check before dispatch:

| Spec section | Overlapping issue | Resolution |
| --- | --- | --- |
| §3.1 completion oracle | #2056 (gh-write verification target defaults to `--issue` instead of actual PR under review) | Same root cause. #2056 is the bug report; §1 below is its fix, scoped to also cover the fix-job cross-branch-push fingerprint (#2056 only names the review-job fingerprint). Close #2056 as part of this work, do not file a second issue. |
| §3.1 completion oracle | #2048 (cold-start tiebreak silently substitutes 'local', reroute message blames wrong harness) | Different trigger (cold-start routing, not cross-branch GitHub effects) but same class of "oracle trusts the wrong evidence source." Reference, do not fold in — #2048's fix is routing-tiebreak logic, not the GitHub-effect evidence dimension this plan adds. Leave #2048 open, separately scheduled. |
| §3.1 completion oracle | #2041 (cross-harness review gate misattributes fix jobs whose task text mentions a prior review) | Adjacent but distinct: #2041 is about `pr check`'s gate misreading task text, not the dispatch-side completion oracle. Leave open; §1's new evidence-threading (task→PR number) may incidentally help #2041's fix but does not resolve it. Flag in #2041 as related once §1 ships. |
| §3.2 cost provenance | #2051 (`pr check` cross-harness gate hard-fails when implementer job has no `cost_entries` row, blocks #2043/#2047) | Direct overlap. PR #2059 already shipped a partial fix. Before starting §2 below, re-check #2051's current state — if PR #2059 fully closed it, §2 only needs the *reviewer-logs-on-behalf-of-implementer* workflow piece (the part #2059 didn't cover, since #2059 was a gate-side fix, not a provenance-capture workflow). |

## Objective

Implement the four fixes from the design spec so that an epic's PRs can move
through `dispatch(dev) → push → dispatch(cross-harness review) → verified
review event → merge(qa) → cleanup` on GitHub-state transitions alone, without
a manual `gh pr view` verification pass as a matter of routine, and without
silently accepting a role/task_type mismatch at dispatch time.

This plan is scoped to the four items in the design's §3.1-§3.4 only. It does
not re-implement #1990/#1991/#1992's full designs (already separately
tracked), does not touch the self-approval or cross-harness-review guards'
actual decision logic, and does not revisit the admin-override-merge path
(confirmed a real GitHub permissions wall, not a synlynk policy choice).

## Constraints and invariants

- No change in this plan may loosen the self-approval guard's or the
  cross-harness-review guard's actual decision logic. Both are confirmed
  working correctly; this plan only gives them legitimate paths and
  trustworthy status reporting.
- The completion oracle's local-diff evidence path (used by jobs that work
  entirely in their own dispatch worktree) must remain unchanged. The new
  cross-branch evidence dimension in §1 is additive, not a replacement.
- Cost provenance records must remain a factual record of token counts, not a
  judgment call — §2's reviewer-logging path must not become a second path to
  approve one's own work; the reviewer logging it must still be a different
  harness/role than the implementer.
- `role_task_type_compat` validation in §3 must hard-fail with an actionable
  error (naming the correct role), matching the existing `RuntimeError`
  pattern already used for unknown task_types — not a new silent-accept path.
- §4 (GOVERNS hard-fail ambiguity) ships the non-blocking preflight-warning
  option (design's recommended option (a)) in this pass. Do not implement the
  hard-fail itself — that remains #1990's full scope.
- Every task dispatched for this plan must itself be linked to a GOVERNS
  goal/story (dogfooding the very discipline this plan is trying to make
  cheaper to follow).

## Work breakdown

### 1. Extend the completion oracle to cross-branch GitHub effects (spec §3.1)

Files to inspect/change:

- `synlynk/verify_effects.py` — effect-contract evidence predicates.
- `synlynk/dispatch.py` — where `--requires-gh-write` plus a task mentioning a
  PR/issue number is parsed; this already partially resolves a target, per
  the design spec's note that `dispatch_agent()` "already knows the target PR."
- `synlynk/jobs.py` / `synlynk/daemon.py` — terminal-status writer.

Tasks:

1. At dispatch time, when task text or `--issue`/`--pr` names a target
   different from the job's own dispatch branch, persist that target
   PR/issue number into job metadata (new column or JSON field — check
   existing job metadata schema in `synlynk/db.py` before adding a new one).
2. In the terminal-status writer, when job metadata has a target PR/issue
   different from the job's own branch, query `gh pr view <N>
   --json reviews,commits` filtered to events after the job's dispatch
   start timestamp, and treat that as the primary evidence source. Fall back
   to the existing local-diff heuristic only when no target is recorded
   (preserves current behavior for in-worktree jobs).
3. Close #2056 referencing this fix (same root-cause fingerprint: verification
   target defaulting to `--issue` instead of the actual PR).

Verification: a unit test simulating a review-only dispatch job (task mentions
PR N, job's own branch has 0 commits) that resolves to `completed` once a
fresh review lands on PR N, even though the job's own worktree diff is empty.
Also a regression test for the existing in-worktree completion path to
confirm no behavior change there.

### 2. Reviewer-logged cost provenance for native-session PRs (spec §3.2)

Files to inspect/change:

- Reviewer dispatch task template (wherever review tasks are composed —
  check `synlynk/dispatch.py`'s task-template construction or a prompts/
  templates file referenced from it).
- `synlynk/costs.py` / `cost_entries` schema — confirm `estimate_basis` field
  exists or needs adding.

Tasks:

1. Re-check #2051's current state first (per §0 above) — confirm what PR
   #2059 already covers before scoping this item, to avoid redundant work.
2. Add a standing instruction to the reviewer dispatch task template: if
   `cost_entries` has no row for the PR's implementer, log one via
   `synlynk cost log --pr <N> --harness <implementer-harness> --note
   "logged by reviewer, see design spec 2026-10-06"` before submitting the
   review verdict.
3. For a native Claude PM session with no dispatched implementer job to pull
   token counts from, the reviewer estimates using the light/medium/heavy
   tiers already documented in `~/.claude/CLAUDE.md`'s token-estimation
   section, tagged `estimate_basis: reviewer_estimated` in the cost_entries
   row (add this field if it doesn't exist).

Verification: a test PR authored in a native session with no cost_entries
row, reviewed by a dispatched role — confirm the reviewer's dispatch logs a
cost_entries row tagged `reviewer_estimated` before `pr check` is run, and
that `pr check`'s cross-harness gate no longer hard-fails on missing
provenance for that PR.

### 3. Role × task_type compatibility matrix, enforced at dispatch (spec §3.3)

Files to inspect/change:

- `synlynk/policy.py` — `check_authority()`.
- `.synlynk/policy.json` — add `role_task_type_compat` table.

Tasks:

1. Derive `role_task_type_compat` from CLAUDE.md's existing
   Capability-Based Task Allocation table: `dev → {implement, test, css,
   templates, content, subpages, canvas, js, infra, refactor, cli-plumbing}`,
   `qa → {review, test}`, `pm → {pm, brainstorm, architecture-review,
   deploy}`.
2. In `check_authority()`, for `task_dispatch:<task_type>` actions, add a
   check that `task_type in role_task_type_compat[role]`, not just
   `task_type in task_allocation`. On mismatch, raise the same
   `RuntimeError` pattern used for unknown task_types, with a message naming
   the correct role for that task_type (look it up from the same table,
   inverted).
3. Confirm this does not break any currently-passing dispatch call across
   the test suite — a role/task_type combination that was silently accepted
   before (like this session's `--role pm --task-type pm` mistake on an
   implement-shaped task) is expected to now hard-fail; anything that was a
   legitimate combination must still pass.

Verification: unit test dispatching `--role pm --task-type implement` and
confirming a `RuntimeError` naming `dev` as the correct role. Unit test for
every currently-valid role/task_type pair in the existing table, confirming
none now incorrectly hard-fails.

### 4. Resolve GOVERNS hard-fail enforcement ambiguity (spec §3.4, option (a))

Files to inspect/change:

- `synlynk/dispatch.py` — preflight checks.
- `synlynk/sentinel.py` (or wherever `sentinel.md` pattern-writing lives).

Tasks:

1. In dispatch preflight, when no `--issue`/`--pr`/`--story` is resolvable,
   emit a loud warning (not a hard-fail) to both stdout and `sentinel.md`,
   naming the gap explicitly (e.g. "GOVERNS linkage missing — dispatch
   proceeding, but this will hard-fail once #1990 ships").
2. Do not block the dispatch. This is a visibility fix only, closing the
   documentation/reality gap, not implementing #1990's actual hard-fail.
3. Update CLAUDE.md's existing #1990 reference to note that this preflight
   warning (not yet a hard-fail) is live as of this plan's merge, so future
   sessions don't have to empirically rediscover the gap the way this
   session did.

Verification: dispatch a job with no `--issue`/`--pr`/`--story` and confirm
a warning appears in both stdout and `sentinel.md`, and that the job still
proceeds (no regression in existing dispatch behavior for calls that
intentionally omit GOVERNS linkage, if any legitimately do).

## Sequencing

Items 1-4 are independent of each other and can be dispatched in parallel to
different roles/harnesses (respecting §3's own new role×task_type
compatibility rule once it ships — so dispatch item 3 first, or at minimum
validate its own dispatch call manually against the matix before relying on
it). Each item is its own PR, reviewed cross-harness per existing policy,
following the target workflow in the design spec's §4.
