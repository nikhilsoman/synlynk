---
title: "PR #549 — LIVE-3: Recovering What a Merge Conflict Actually Deleted"
date: 2026-07-26
series: "Building the OS for Multi-Agent Development"
post: 81
pr: "#549"
merged: 2026-07-26
---

## The Broader Goal at the End of the Previous PR

PR #542 had just merged, DB-canonicalizing `roadmap.md`/`memory.md`/`costs.md`/`todo.md` and running `synlynk migrate` against this repo. The expectation going in was that the migrate's deletions were scoped exactly to those four files, since those are the only ones with a database table backing them.

## Strategic Shifts in This PR

None planned — this PR exists because a ground-truth double-check of PR #542's merge, run as standard post-merge verification (not because anything looked wrong), found that the merge shipped more damage than the plan intended.

## What This PR Shipped

PR #542 had drifted into `CONFLICTING`/`DIRTY` state against `main` because four other PRs (#537/#539/#540/#541) merged during its review window, each adding files under `project-docs/`. The non-authoring reviewer (Grok, dispatched per the #426 GitHub-write routing policy) resolved the conflict and reported having "preserved main's newer content... under `.synlynk/project-docs/`" while keeping PR1's deletion of the root `project-docs/` tree.

That claim didn't survive a `git diff --stat c34e2eb..db9a652 -- 'project-docs/'` against the true pre-merge `main` tip: 17 files / 2161 lines were deleted, not 4. The extra 13 — `project-docs/decisions/*.{json,md}` (three decision docs, including one from the day before merge), all four `devlogs/*.md` files, `memory.md`, `repo-evaluation-report.md`, and a cost-capability report — had been added by the four PRs that landed during review, and the conflict resolution treated the whole directory as in-scope for deletion rather than diffing file-by-file against what PR1 actually migrates.

Three things made this worse than a simple oversight:
- `.synlynk/*` is fully gitignored except one file and one sentinel, so nothing written under the claimed preservation path was ever going to be shared or tracked.
- Grok's own job worktree had no `.synlynk/project-docs/` directory at all — the claimed local preservation step left no trace even in its own workspace.
- `decisions/*.json`, `repo-evaluation-report.md`, and `reports/*.md` have zero database table backing anywhere in the codebase (confirmed by grep) — unlike `roadmap.md`/`memory.md`/`costs.md`/`todo.md`, there is no regeneration mechanism that would ever recreate this content.

This PR restores all 13 files verbatim from `c34e2eb` (`git checkout c34e2eb -- <path>`, no reconstruction), and adds `docs/rca/2026-07-26-LIVE-3-pr542-merge-content-loss.md` documenting the full root cause and timeline. It was declared LIVE-3 / Sev1 per the global Live Issues SOP, since data loss/corruption is an explicit Sev1 trigger.

The recovery PR itself had one wrinkle worth recording: the first attempt (#548) was opened from the wrong branch due to a shell working-directory mistake on the PM side, not an agent error. The same dispatched reviewer (Grok) caught it — ran `synlynk pr check`, diffed the claimed content against the actual head branch, found the mismatch, refused to merge, and opened the correct replacement PR (#549) with byte-for-byte `cmp` verification against `c34e2eb` for all 13 files before merging it.

## Brainstorm Visuals Used

None — this was an investigation-and-recovery task, not a design decision.

## What This Achieved on the Path to Autonomy

Two review layers did their job here, at two different points: PR Review Discipline's non-authoring reviewer requirement caught the mis-targeted recovery PR before it could merge wrong content, and the standing "never trust job status alone, verify via ground truth" practice caught the original content loss after a merge had already reported success. Neither is free — this is now two Live Issues in the dispatch/review pipeline (LIVE-2's migrate false-positive, LIVE-3's merge-conflict scope) traced to conflict/merge resolution being treated as a single-unit operation instead of a file-by-file verified one. That's a pattern worth naming precisely because it's now shown up twice.

## Strategic Note: The Goal at the End of This PR

The immediate loss is recovered and `main` is back to matching `c34e2eb` for every file PR1 never intended to touch. What's still open, tracked in the RCA's action items rather than fixed here: `decisions/`, `repo-evaluation-report.md`, and `reports/` still have no database-backed regeneration path, so they remain exposed to the same class of bulk-deletion mistake in any future migrate-adjacent merge. The next state-engine PR (PR2, DB-canonicalizing `vizor-workspace-map.json`) should treat "give these files real DB backing or explicitly exclude them by name from bulk deletion logic" as a prerequisite, not an afterthought.
