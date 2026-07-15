---
title: "PR #TBD — One Dispatch Path: Queue Launcher Stops Reimplementing Spawn"
date: 2026-07-12
series: "Building the OS for Multi-Agent Development"
post: 54
pr: "#TBD"
issue: "#190"
merged: —
---

## The Broader Goal at the End of the Previous PR

Fable's external review (blog-adjacent strategy doc, PR #188) laid out a multi-year arc for synlynk as the OS for multi-agent development. One concrete finding was independent of the local-agent MLX work: the daemon/scheduler queue path and the interactive `dispatch` path had silently forked. Fleet scheduler v1 (`synlynk schedule --execute`) is designed to call `_dispatch_ready_jobs` as its execution primitive — so any isolation or flag gap there becomes a fleet-wide failure class, not a niche daemon bug.

## Strategic Shifts in This PR (if any)

No goalpost move. The review agreed we should **not** delete `_dispatch_ready_jobs` (it owns priority ordering, dependency gating, and concurrency caps that `dispatch_agent` correctly does not absorb). The fix is collapse-to-one-execution-implementation: keep the scheduler brain, delete the second spawn body.

Cost-accounting hardcoding at the reconcile path remains out of scope (#189).

## What This PR Shipped

### `dispatch_agent(..., job_id=None)`

Optional `job_id` lets the queue path hand the pre-existing `daemon_jobs` primary key into the shared launcher. When the row already exists, the DB write is an `UPDATE` (preserves `priority`, `depends_on`, `enqueued_at`) instead of `INSERT OR REPLACE` defaults.

### `_dispatch_ready_jobs` delegates spawn

The inline block that built `cli + non_interactive_flags` only, skipped `_preflight_dispatch`, and `Popen`'d `sh -c` with no `cwd` is gone. Per ready queue row it now calls:

```python
dispatch_agent(agent, task, story_id=story_id, force_agent=True, job_id=job_id)
```

Scheduling logic (priority `ORDER BY`, failed/unmet `depends_on`, `max_parallel` slots) is unchanged. Preflight/worktree failures mark the queue row `failed` so the daemon does not spin forever.

### Regression test

`test_dispatch_ready_jobs_creates_worktree_and_applies_dispatch_flags` asserts that a queued row launched via `_dispatch_ready_jobs`:

- creates the job worktree layout (`worktrees/<job_id>/.synlynk/{logs,prompts}`)
- applies Claude `dispatch_flags` (`--dangerously-skip-permissions`)
- sets `Popen(..., cwd=worktree_path)`
- records `worktree_path` / `worktree_branch` on the jobs.json entry under the **same** `job_id`

Priority / dependency / concurrency tests continue to pass.

## On Track Toward Full Autonomous Multi-Agent Dispatch

The scheduler and the interactive CLI no longer have two half-copies of "how to run an agent." When fleet dispatch launches concurrent cross-agent jobs, each one gets worktree isolation and the same permission/dispatch flag translation as a human `synlynk dispatch`. That is a prerequisite for safe parallel execution under `synlynk schedule --execute`.

## New Goalpost

- Land #190; confirm daemon + schedule paths dogfood the unified launcher.
- #189 still open for cost-accounting rate-table bypasses (including the reconcile path next to this code).
- Local-agent / MLX driver work can assume queue isolation is real rather than re-litigating it.
