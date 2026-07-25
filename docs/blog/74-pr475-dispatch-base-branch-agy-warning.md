---
title: "PR #475 — Dynamic PR Base Resolution + Silent Agy No-Op Warning"
date: 2026-07-24
series: "Building the OS for Multi-Agent Development"
post: 74
pr: "#475"
merged: 2026-07-24
---

## The Broader Goal at the End of the Previous PR

PR #463 had just landed dispatch stacking and the ground-truth suite gate — jobs now branch off the actual feature branch tip instead of stale `origin/main`, and a job can no longer report `completed` while leaving the test suite red. That work assumed the dispatch pipeline's surrounding plumbing (PR creation, headless permission handling) was already solid; this PR exists because a job dispatched from a *different* repo (rxcc) surfaced that it wasn't.

## Strategic Shifts in This PR

None planned — this PR is a direct reliability fix triggered by a live failure report from a sibling session, not a scoped design. No spec or plan preceded it; the two bugs were small enough to fix directly once diagnosed.

## What This PR Shipped

Two independent dispatch-pipeline bugs, fixed together because both surfaced from the same failed job report:

1. **Hardcoded PR base branch** (`synlynk/jobs.py`): `_maybe_open_worktree_pr` called `gh pr create --base main` unconditionally. Any repo whose default branch isn't literally `main` (e.g. `master`) failed with "no commits between main and branch" even though the dispatched work was real, complete, and already pushed. Fixed by resolving the actual default branch via `origin/HEAD`'s symbolic-ref, falling back through `origin/main` → `origin/master` → `main` → `master` if the symbolic-ref lookup itself fails.

2. **Silent no-op in headless `agy` dispatch** (`synlynk/dispatch.py`): when a job has no write/run permissions granted — the default state whenever `.synlynk/config.json` has no `roles` entry for `agy` and no explicit `--grant` flag is passed — `_permissions_to_flags` returned an empty flag list with no `--dangerously-skip-permissions`. In headless mode there's no human to approve a gated tool call, so any approval-required tool gets auto-denied and the job does nothing while still looking like a clean success. The fix doesn't change that behavior (skip-permissions still isn't force-added) — it makes the failure mode loud: a warning prints whenever `agy` is dispatched with no permissions granted, so a silent zero-output job is now a visible one.

Two new unit tests cover `_resolve_default_base_branch` (both the `origin/main`-present and `origin/master`-only-fallback paths) and one covers `_maybe_open_worktree_pr` using the resolved branch in its `gh pr create` call. Two more cover `_permissions_to_flags("agy", ...)` — warning on empty permissions, staying silent on the happy path. 45/45 passing in `tests/test_dispatch.py` + `tests/test_jobs.py`. Squashed to `10387db` on 2026-07-24.

## Brainstorm Visuals Used

None — diagnosed and fixed directly from a failure report, no brainstorming session preceded this PR.

## What This Achieved on the Path to Autonomy

Both fixes remove a class of dispatch failure that looks identical to success from the outside — a `gh pr create` that silently can't run because of a wrong assumed default branch, and an `agy` job that silently does nothing because of an unstated permission gap. Neither bug is exotic: both are the kind of thing that only surfaces once synlynk is dispatched against repos it wasn't originally built and tested against (rxcc, in this case) — which is exactly the generalization step autonomous multi-agent dispatch across multiple projects requires. Making the second failure loud rather than silent is the more important half: a job dispatch that returns exit 0 with zero file changes is worse than one that fails outright, because nothing downstream (job status, `synlynk jobs`, the ground-truth gate from PR #463) currently distinguishes "nothing needed to be done" from "nothing was allowed to be done."

## Strategic Note: The Goal at the End of This PR

The warning added here is a diagnostic aid, not a structural fix — it makes the silent-no-op failure mode visible in logs, but doesn't prevent it or auto-remediate it (e.g. by escalating permissions automatically). The very next PR in this session (#479) exists because the warning alone didn't explain a *second*, more specific instance of headless permission denial (Antigravity CLI's own "jetski" auto-deny message) reported from the same sibling session — that investigation is where this thread picks up.
