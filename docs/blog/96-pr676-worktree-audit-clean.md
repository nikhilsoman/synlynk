---
title: "PR #676 — synlynk worktree audit/clean: automating the hygiene protocol"
date: 2026-08-03
series: "Building the OS for Multi-Agent Development"
post: 96
pr: "#676"
---

## The Broader Goal at the End of the Previous PR

The Worktree Hygiene Protocol (CLAUDE.md, added via PR #575) formalized when a dispatch-job worktree/branch should be removed: on merge, confirmed via `git status --short` + `git merge-base --is-ancestor` (or PR state for squash merges), with a periodic full audit "at least every ~20 dispatched jobs." That periodic audit was pure manual archaeology — a July 2026 sweep found 30 stale worktrees/branches that had accumulated because cleanup only ever happened reactively, in large batches, long after the owning PRs had merged. The protocol existed; nothing enforced it.

## What This PR Shipped

`synlynk worktree audit` and `synlynk worktree clean`, a new command group in `synlynk/worktree.py` that runs the manual audit procedure automatically:

- **Classification** (`_classify_worktree`) applies the protocol's own checks as a pure function over pre-fetched signals: dirty-tree override → `git merge-base --is-ancestor` → `gh pr` state (including a net-diff-stat heuristic for closed-but-unmerged PRs) → four gh-required outcomes. A second pass, `_apply_nesting_floor`, enforces that a nested worktree can never rank safer than its parent — mirroring the hygiene protocol's rule that a parent PR's merge should sweep every nested `worktrees/job-*` inside it.
- **`synlynk worktree audit`** (read-only) reports every worktree as SAFE / NEEDS-REVIEW / UNSAFE with its reasoning, plus a `--json` payload for tooling.
- **`synlynk worktree clean`** is dry-run by default; `--apply` removes only SAFE items, nested-before-parent, with `git worktree remove --force` + `git branch -D` + best-effort `git push origin --delete`, continuing past individual failures instead of aborting the batch.
- **`synlynk status`** gained a lightweight `WORKTREES` hint line — local-only, no `gh` calls — so staleness is visible on every status check, not just when someone remembers to run a full audit.

Built via `synlynk dispatch codex` across six dispatched tasks (dataclasses/parsing → classification → nesting floor → audit/clean orchestration → CLI wiring → status integration), each reviewed by Claude directly (spec compliance, then code quality) before merging into the feature branch — matching this repo's locked PM/implementer role split. Two review-time fixes were needed: an import-ordering nit in the test file, and a missed `docs/reference/commands.md` regeneration after the new `worktree audit`/`worktree clean` entries were added to `synlynk/taxonomy.py` (caught by `test_docs_sync.py` before merge, not after).

Manual verification against this repo's own real worktree state (98 worktrees, accumulated across months of dispatch work) found 8 genuinely SAFE stale worktrees with merged-PR reasons — proving the tool works on the exact mess it was built to clean up.

## Goalpost

The Worktree Hygiene Protocol's periodic-audit step is now a single command instead of a manual `git worktree list --porcelain` + cross-reference exercise. Next: fold `synlynk worktree audit` into the actual cleanup cadence (post-merge, and periodically) so the 30-stale-worktree accumulation pattern doesn't recur.
