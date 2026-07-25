# Dispatch Stacking & Ground-Truth Merge Gate — Design

**Status:** Proposed
**Date:** 2026-07-22
**Author:** Claude (PM/review role), brainstormed with Nikhil

## Problem

`synlynk dispatch <agent>` is the mechanism by which Claude (PM/reviewer, per this repo's locked role split) hands implementation work to Codex/Gemini/Grok. Over the course of executing a 9-task plan (`docs/superpowers/plans/2026-07-22-rollback-mechanism.md`) via Subagent-Driven Development against a long-lived feature branch, four compounding failure modes emerged that turned what should be fast agentic iteration into a slow, error-prone, manually-supervised process:

1. **Always-branch-off-main.** `_resolve_dispatch_worktree_base_ref()` (`synlynk/dispatch.py:302`) unconditionally resolves the freshest `origin/main`/`origin/master` and anchors every new job worktree there — regardless of whether the dispatch is part of a multi-task plan already accumulating commits on a feature branch. Task 2's job worktree has no knowledge of Task 1's merged changes; Task 3's has no knowledge of Task 1 or 2's. Every merge from Task 2 onward produces an add/add conflict on any file a prior task already touched, requiring the reviewer to manually diff and choose `--ours`/`--theirs` per file, per task.

2. **Prompt self-containment / transcription bugs.** Because a job's worktree branches off stale mainline, it cannot see the current state of files modified by prior tasks on the feature branch. The only way to give a job the correct starting point is to paste the complete current file content into the dispatch prompt by hand. This is verbose, wastes tokens, and is error-prone: a literal `.synlynk` → `synlynk` (missing leading dot) corruption recurred **four times** in one session, in different files (`ROLLBACK_DIR`, `_SCRIPT_INSTALL_PATHS`), each time requiring a manual reviewer catch-and-fix.

3. **Unreliable job-status self-reporting.** `synlynk jobs`' completion summaries have a "borrowed worktree" attribution path (`synlynk/jobs.py:1183-1189`) that can override the ground-truth `_worktree_files_touched()` diff with files attributed from an unrelated remote ref, producing completion summaries that list files that were never actually committed by the task (uncommitted pipeline noise, stale worktree leftovers). The only fully reliable signal turned out to be manually running `git diff origin/main --stat` inside the job's own worktree — a step the reviewer has to remember and repeat for every job.

4. **Reviewer judgment errors from partial test visibility.** A job (Task 4) made a legitimate, necessary change (defensive `None`-handling in `_git_dirty()`/`_git_head_sha()`, discovered because pre-existing tests monkeypatch `subprocess.run` to return `None`) alongside some genuinely bad changes (a reintroduced dot-bug, a dropped `-u` flag). The reviewer, seeing the explicit-instruction violation and the bad parts, rejected the *entire* rewrite via `git checkout --ours`, which silently reintroduced the very regression the job had fixed. This was only caught by later running the *full* test suite — something the review step didn't do at merge time.

**Goal:** redesign the dispatch → merge pipeline so that sequential task chains stack cleanly with no manual conflict reconciliation, prompts stop needing full-file transcription, and merge-eligibility is judged from computed ground truth rather than self-report or partial review — as a foundation for later increasing dispatch concurrency without sacrificing repo safety.

## Non-goals

- This design does not change *what* Codex/Gemini/Grok are dispatched to do, or the PM/review/deploy role split in `CLAUDE.md`. Claude still never implements features directly.
- True multi-agent concurrency (footprint locking, wave scheduling) is scoped as Phase 2, deliberately deferred until Phase 1's stacking primitive has been used in real plan executions and proven stable. Phase 2 depends on Phase 1's correctness; shipping them together would make failures harder to isolate.
- This design does not attempt AST-aware / semantic merge tooling. Phase 1 makes textual merges safe by construction (jobs stack on the true current tip, so conflicts should be rare-to-nonexistent for the sequential case); if Phase 2 concurrency produces same-wave collisions, the design treats that as an anomaly to re-plan around (abort & re-dispatch on the fresh tip), not something to teach an agent to merge through.

## Architecture — Phase 1

### Stacked dispatch branches

`dispatch_agent()` gains a `base_branch` parameter (default: auto-detected). Resolution order:

1. If the dispatch is invoked from inside a worktree whose current branch is **not** `main`/`master` (detected the same way `finishing-a-development-branch` already checks — `git branch --show-current`), that branch is the default base.
2. Otherwise, fall back to today's behavior: freshest `origin/main`/`origin/master`.
3. An explicit `--base <branch>` flag on `synlynk dispatch` always wins over auto-detection, for one-off dispatches that intentionally want a clean-main baseline.

`_create_job_worktree()` creates the job's worktree anchored to the resolved base branch's **current tip commit**, not a hardcoded mainline ref:

```python
worktree_cmd = ["git", "worktree", "add", worktree_path, "-b", worktree_branch, base_sha]
```

`_assert_dispatch_worktree_base_is_fresh()` is updated to verify against whichever `base_ref` was actually selected (it already takes `base_ref` as a parameter — this is a call-site change, not a new function).

**Effect:** a job dispatched for Task N of a plan already has Task 1..N-1's merged changes on disk in its own worktree. The dispatch prompt only needs to describe the *delta* for Task N — no more pasting whole files from memory into the prompt, which is what eliminates the transcription-bug class at the root. Merging the job's commit back onto the feature branch becomes a fast-forward or a clean three-way merge, because the job's parent commit *is* the branch's HEAD at dispatch time — no more add/add conflicts on files prior tasks already touched.

### Ground-truth merge gate

Before a job is ever reported as mergeable, the harness (not the agent) runs the project's test suite inside the job's own worktree and records the result as a first-class field on the job, not a self-reported claim:

- Config: `.synlynk/config.json` gains `dispatch.gate_suite_cmd` (e.g. `"pytest tests/ -q"` for synlynk itself — deliberately scoped to avoid the nested-`worktrees/`-directory collection-error trap that an unscoped `pytest -q` falls into, fixed once in config instead of rediscovered by every reviewer).
- The harness runs `gate_suite_cmd` in the job's worktree after the job process exits (successfully or not) and before writing the final job summary.
- Result is stored as `suite_result: {passed, failed, skipped, ran_at}` on the job record and surfaced directly in `synlynk jobs` / `synlynk logs --job <id>` output.
- A job with `suite_result.failed > 0` is marked `NEEDS_FIX`, not `DONE` — it is not presented to the reviewer as a candidate for merge until a re-run comes back clean.

This directly targets failure mode 4: the reviewer would have seen "suite: 1329 passed, 0 failed" (or a failure) as a hard, harness-computed fact at the moment of the merge decision, rather than having to separately remember to run the full suite after merging to discover a hidden regression.

## Data model

**Job record** (wherever `.synlynk/jobs.json`-equivalent state lives) gains:

| Field | Type | Description |
|---|---|---|
| `base_branch` | string | Branch the job was actually stacked on (`chore/rollback-mechanism-design` or `origin/main`) |
| `base_sha` | string | Exact commit the job worktree was anchored to at creation (promotes the existing ad hoc `_resolve_worktree_base_commit()` result to a stored, first-class field) |
| `suite_result` | object | `{passed: int, failed: int, skipped: int, ran_at: ISO8601}` from the mandatory gate run |

**Config** (`.synlynk/config.json`) gains a `dispatch` block:

```json
{
  "dispatch": {
    "stacking": "auto",
    "gate_suite_cmd": "pytest tests/ -q"
  }
}
```

`stacking`: `"auto"` (default — stack on current branch when not main/master, else origin/main) | `"always"` (always stack on current branch, error if on main/master) | `"never"` (always origin/main, today's behavior — escape hatch for projects/situations not ready to adopt stacking).

## Error handling

- **Feature branch moves during a job** (a parallel session merges another task, or someone pushes directly): before merging a completed job, check `git merge-base --is-ancestor <job.base_sha> <feature-branch-HEAD>`. If the branch has advanced past what the job was stacked on, do not force a merge — mark the job `STALE_BASE` and surface it to the reviewer. Per the "abort & regenerate beats debugging a bad merge" principle, the default recommended action is re-dispatching the same task fresh against the new tip (fast, since the task's logic is already known) rather than attempting a manual reconcile.
- **Gate suite fails.** Job stays `NEEDS_FIX`. Reviewer sees the failure inline; no separate manual pytest run required to discover it. Reviewer may re-dispatch a fix job (following the established self-contained-prompt pattern) or, for narrow proven pipeline defects, apply a one-line fix directly per the existing reviewer-exception precedent.
- **`stacking: auto` misfires** (e.g. dispatched from a detached-HEAD or unrecognized worktree state): falls back to `origin/main` and logs a one-line note. A fresh-off-main dispatch is always a valid, if suboptimal, choice — never hard-error here.
- **Orphaned locks** (Phase 2 concern, noted for forward-compatibility of the data model): not applicable to Phase 1, since Phase 1 has no lock registry.

## Testing plan

- **Unit — base ref resolution:** on a feature branch → returns branch name + its tip SHA; on `main`/`master` → returns `origin/main`; `stacking: never` config → always returns `origin/main` regardless of current branch; `stacking: always` on `main` → errors clearly rather than silently stacking on mainline.
- **Integration — sequential stacking:** in a temp repo, dispatch two fake sequential jobs against a feature branch; assert the second job's worktree base SHA equals the first job's post-merge tip; assert merging the second job's commit produces zero conflicts.
- **Integration — gate:** a job worktree seeded with one deliberately failing test → `suite_result.failed > 0` and job status is `NEEDS_FIX`, never `DONE`.
- **Regression — stale base:** simulate the feature branch advancing after a job's worktree was created but before merge → job is flagged `STALE_BASE`, merge is refused (not silently forced).
- **Manual verification (first real usage):** run this against a real multi-task plan end-to-end (a good candidate: the remaining Tasks 5-9 of `docs/superpowers/plans/2026-07-22-rollback-mechanism.md`, once this design ships) and confirm zero add/add conflicts and zero manual `git diff origin/main --stat` ground-truth checks were needed.

## Phase 2 (forward-looking scope, not part of this implementation)

Once Phase 1 has run for real across a few plan executions and proven stable:

- **Footprint locking.** Parse each plan task's `Files:` block (already a required field in `writing-plans` output — no new inference needed) into a set of paths. Maintain `.synlynk/dispatch/locks.json`: before dispatching a wave of tasks, check for path overlap against any currently-running job. Non-overlapping tasks in the same wave dispatch concurrently, each stacking per Phase 1's mechanism, all anchored to the same branch tip at wave-start. Overlapping tasks queue until the lock clears.
- **Wave-based merge ordering.** Within a wave, merge order is first-completed-first-merged. Later same-wave jobs re-resolve their base against the now-updated tip before merging — a rebase-or-requeue check, not a blind merge — since footprints were supposed to be disjoint, a same-wave collision is treated as an anomaly to re-plan around rather than something to auto-resolve.
- **Stale-lock cleanup.** Locks carry the owning job's id; a killed/crashed job's lock is dropped automatically on the next dispatch cycle (or via an explicit `synlynk dispatch locks --clear-stale`).

This phase is what unlocks genuine multi-agent concurrent velocity; it is deliberately not attempted until Phase 1's stacking and gating primitives are proven, since Phase 2's safety guarantees (no two agents touching the same files concurrently) depend entirely on Phase 1 already merging correctly.

## Rollout

Phase 1 ships as its own PR against synlynk itself (pure dispatch-tooling change — `synlynk/dispatch.py`, `synlynk/jobs.py`, config schema). It changes nothing about the *content* of already-in-flight plans; it changes how dispatch resolves worktree bases and what merge-eligibility is judged on. No migration needed for existing job records — new fields (`base_branch`, `base_sha`, `suite_result`) are additive and optional on read.

Phase 2 is a distinct, later PR, gated on Phase 1 having been used in at least one real multi-task plan execution (the remaining rollback-mechanism plan tasks are a natural first real-world test) with no stacking or gate-related surprises.
