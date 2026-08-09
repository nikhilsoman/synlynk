---
title: "PR #854 — Fresh --base: Stop Dispatching Against Stale main"
date: 2026-08-09
series: "Building the OS for Multi-Agent Development"
post: 108
issue: 832
---

# Fresh `--base` — Stop Dispatching Against Stale `main`

## Broader goal

Multi-step plans dispatch many jobs with `--base main`. Operators were hand-guarding stale bases; intermittent BLOCKED statuses looked like implementer failure.

## What shipped

`--base main` (and other bare branch names) now **fetch `origin/<branch>`** and anchor the worktree on the **remote tip** when available. Local-only refs remain a fallback with a warning. Resolved SHA is logged before worktree create. Tests cover stale local main vs advanced origin.

## Related

Epic plan for job-status/cost truth + GH-write identity:
`docs/superpowers/plans/2026-08-09-job-truth-and-gh-write-epics.md`

## New goalpost

Hand `--base main` after fetch is no longer required for correctness; epic A/B still needed for status/cost/GH identity.
