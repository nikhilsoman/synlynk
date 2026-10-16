---
title: "Worktree hygiene audit: archive before you prune"
date: 2026-10-15
series: "Building the OS for Multi-Agent Development"
post: 278
pr: 2334
status: open
author: "synlynk team"
version: "0.25.1"
tags: [posts]
type: pr
---

# 278 — Worktree hygiene audit: archive before you prune

Date: 2026-10-15
PR: #2334
Story: story-issue-1487 / gh:#1487

## Goalpost coming in

The Worktree Hygiene Protocol already said merge-time cleanup should be the
default, with a periodic audit sweeping anything left behind. In practice the
fleet still accumulated hundreds of stale `dispatch/*` worktrees — many merged
by squash, many dirty only on `project-docs/*`, and a few still carrying unique
unmerged design/blog drafts.

## What shifted

This pass treated the audit classes as operational truth, with one correction:
`synlynk worktree audit` must be run from the main checkout. Running it from a
nested job worktree reclassifies `main` as a parent and floors nearly every
nested worktree to `needs-review`, hiding hundreds of SAFE removals.

## What shipped

1. `synlynk worktree clean --apply` from main removed **277** confirmed-SAFE
   worktrees/branches (merged ancestors, patch-equivalent, or stale
   registrations).
2. A second triage pass reclassified **162** additional NEEDS-REVIEW items as
   safe (committed state already on main / patch-equivalent / noise-only /
   superseded volatile forks) and removed them.
3. **55** unique files that were missing on `origin/main` were archived under
   `docs/archive/worktree-hygiene-2026-10-15/` with a MANIFEST before their
   source branches are eligible for deletion.
4. Four open-PR worktrees were left untouched: #2241, #2175, #1970, #2264.

## On the autonomy arc

Autonomous fleet operation needs a maintainer loop that can prune without
discarding unique work. This audit is that loop executed once at scale, and it
surfaces a follow-up: gh PR lookup via `head:branch` search is missing open PRs
that `gh pr view` finds, so open work currently lands in NEEDS-REVIEW instead of
UNSAFE.

## New goalpost

Keep the four open-PR worktrees intact, land the archive PR, then escalate the
remaining differs-only branches whose committed trees still diverge from main
on non-volatile paths.
