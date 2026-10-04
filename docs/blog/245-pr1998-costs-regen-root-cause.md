---
title: "The Archive Was Never Lost — It Was Gitignored"
date: 2026-10-04
series: "Building the OS for Multi-Agent Development"
post: 245
pr: "1998"
issue: "1995,1999"
status: published
author: "synlynk team"
version: "0.25.0-dev"
tags: [posts, bugfix, cost-ledger, investigation]
type: story
---

## The Broader Goal at the End of the Previous PR

PR #1994 (post #244) suspended the heuristic Default Agent Role lock in favor
of empirical capability measurement, and named `project-docs/costs.md` —
specifically `cost_entries`/`capability_ratings` — as the data the new
`capability_policy` would eventually measure routing against. The goalpost
coming out of that PR was building the enforcement gates (#1990, #1991) and
the `capability report` generator (#1993) that policy depends on.

This PR is a detour forced by a standing problem with that very data source:
gh:#1995, a bug that had already triggered three manual "restore the rows
that got dropped" commits on this branch before this PR shipped an actual
fix, rather than a fourth restoration.

## Strategic Shift in This PR

No roadmap shift — this is debugging work that had to happen before the
capability-measurement goalpost above could trust its own inputs. But it's
worth naming the shift in how the investigation itself went, because it's
the most useful thing in this post: the first root-cause theory was wrong,
and the PR body says so rather than quietly fixing the write-up after the
fact.

## What This PR Shipped

**First theory (retracted):** `_rotate_project_doc()` writes an archive file
for rows rotated out of the live `costs.md`/`roadmap.md`/`memory.md` view.
The initial hypothesis was that a dispatched job's ephemeral git worktree —
deleted post-merge per this repo's Worktree Hygiene Protocol — was silently
destroying that archive before it ever got committed. Plausible, and matched
`git log --oneline -- project-docs/archive/` showing zero history.

**What was actually true:** `_synlynk_project_docs_dir()` resolves through
`_project_root()`, which calls `git rev-parse --git-common-dir` — identical
across every linked worktree of a repo, main checkout or nested job worktree
alike (verified directly from both). The archive was never worktree-scoped;
it lands in the shared, persistent `<main-repo>/.synlynk/project-docs/archive/`,
which survives worktree cleanup fine. It's absent from `git log` because
`.synlynk/*` is bulk-gitignored by this repo's own `.gitignore` — by design,
not by accident. Nothing was silently destroyed.

**The real cause of the visible symptom:** `_PROJECT_DOC_KEEP_N` was 50,
far smaller than the rate `cost_entries` grows. Nearly every regen truncated
the git-tracked `costs.md` to its last 50 rows, so the live window slid on
almost every PR touching cost logging — indistinguishable, in a PR diff,
from data loss. The fix: raise it to 500, shared automatically by the
roadmap and memory generators since all three call the same function.

**A more severe bug found along the way, not fixed here:** the archive file
itself is massively duplicated. One monthly shard,
`.synlynk/project-docs/archive/costs-2026-H10.md`, had 268,445 lines but
only ~3,262 unique rows — one row repeated 45+ times, a 160MB file for what
should be a few hundred KB. `_rotate_project_doc()` re-appends the *entire*
overflow slice on every call instead of tracking a high-water mark of what
it already archived. Filed separately as gh:#1999 rather than folded into
this PR, since fixing it changes archival semantics more than a keep_n bump
does and deserves its own review.

**Also shipped:** `_rotate_project_doc()` now best-effort `git add`s a
freshly written archive file. In this repo's actual migrated-and-gitignored
configuration that's a no-op in practice (`git add` refuses an ignored path
without `-f`, and force-adding hundred-MB generated files into git history
would be actively harmful — not done). It's still correct, tested code that
closes the real worktree-loss case for any non-migrated synlynk-managed repo,
where the archive path *is* the tracked, worktree-local one.

Verification: direct `sqlite3` query against `state.db` confirmed the
`cost_entries` table never lost the rows in question — all three "regen-drop"
incidents were generated-view symptoms, not data-loss incidents, throughout.

## Caught in Review

The retraction itself: after pushing the first fix and posting the initial
root-cause comment to gh:#1995, re-checking `_project_root()`'s actual
implementation (not just its name) disproved the ephemeral-worktree framing.
Rather than leave the wrong claim standing in the issue thread, a correction
comment went up immediately, and the PR description was rewritten before
requesting review — the dispatched reviewer saw the corrected version, not
the retracted one.

## What Was Achieved Toward the Long-Arc Goal

`project-docs/costs.md` stops exhibiting window-slide churn that looked like
data loss, closing the loop that had produced three restoration commits on
this branch alone. More importantly for the capability-measurement goalpost
from PR #1994: the data this policy will eventually route on was confirmed,
end to end, to be durable in `state.db` regardless of what the generated
markdown views show — the measurement substrate is sound even though its
rendered view had a cosmetic bug.

## The New Goalpost

Two threads now open against the cost-ledger surface: gh:#1999 (archive
duplication — needs a high-water-mark design, not a quick patch) and the
still-unbuilt `capability report` generator (gh:#1993) that PR #1994 flagged
as blocked on `state.db` consolidation (gh:#1926). Either is a reasonable
next pull on this thread; neither has started.

Refs #1995, #1999, #1994, #1993, #1926.
