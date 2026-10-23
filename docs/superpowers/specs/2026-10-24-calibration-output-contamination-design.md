# Calibration Output Diff-Base Contamination Design

**Status:** Approved.
**Issue:** [#2567](https://github.com/nikhilsoman/synlynk/issues/2567)
**Related:** [#2170](https://github.com/nikhilsoman/synlynk/issues/2170) (verifier quality-parsing root cause), [#2229](https://github.com/nikhilsoman/synlynk/issues/2229) (same contamination class, dispatch briefs), [#2332](https://github.com/nikhilsoman/synlynk/issues/2332) (closed, unrelated — already fixed)
**Parent:** #2458, step 10 (capability sweep / backfill scoping)

## Intent

Make `_await_calibration_job()`'s reconstructed job output immune to which branch the *dispatching* process happens to be running from, so a capability-sweep calibration task's scored output always reflects that task's own work, not unrelated prior commits leaked in from a parent feature branch.

## Current failure

`_await_calibration_job()` (`synlynk/capability_sweep.py:289-381`) populates `job["output"]` from a git diff when the dispatch result doesn't already carry one (gh:#2350). It computes the diff base by recomputing, live, at await-time, inside the job's own worktree:

```python
base_ref = "origin/main"
mb_res = subprocess.run(["git", "-C", worktree_path, "merge-base", "HEAD", base_ref], ...)
base_sha = (mb_res.stdout or "").strip()
if not base_sha:
    mb_res = subprocess.run(["git", "-C", worktree_path, "merge-base", "HEAD", "main"], ...)
    base_sha = (mb_res.stdout or "").strip()
...
res = subprocess.run(["git", "-C", worktree_path, "diff", base_sha], ...)
```

(`synlynk/capability_sweep.py:333-360`)

When the dispatching process itself is running from a feature branch ahead of `origin/main` (e.g. a `fix/claude/*` worktree with its own unmerged commits), every nested calibration dispatch job's worktree forks from *that* branch's HEAD, not from `origin/main`. The live `merge-base HEAD origin/main` recompute then resolves to `origin/main`'s actual tip — so `git diff {that_sha}` includes the entire parent branch's unmerged history, not just the calibration task's own changes.

## Reproduction (2026-10-24)

A diagnostic probe dispatched a trivial calibration task ("write a one-line `add(a, b)` function") from inside the `fix/claude/2553-daemon-status-pidfile` worktree (at commit `c8884c47`). The reconstructed `executor_result["output"]` came back as a diff of `README.md`'s test-count badge — a change from that worktree's own prior, already-committed `#2553` work — rather than anything related to the toy prompt. The verifier then scored this contaminated input (`quality: 6.0, correct: False`), which is a real verdict on the wrong input, not a parsing failure (see #2170's findings comment, posted same session).

## Fix

Use the job's own recorded `base_sha` as the diff base directly, instead of recomputing merge-base against `origin/main`/`main`:

- `dispatch_agent()` already captures and stores `base_sha` on every dispatched job at creation time (`synlynk/dispatch.py:3366`, `:3421`, `:4992`, `:5559`) — the exact commit the job's worktree was forked from, regardless of what branch the dispatching process was running on. It is also persisted in the `daemon_jobs.base_sha` column (`synlynk/dispatch.py:5795`).
- In `_await_calibration_job()`, prefer `job.get("base_sha")` as the diff base: `git diff {base_sha}` in the job's worktree. This correctly isolates the job's own changes no matter what branch dispatched it, because `base_sha` is precisely the fork point, not a recomputed guess.
- **Fallback (defensive only):** if `job.get("base_sha")` is missing or empty — not expected given the above, but kept for safety — fall back to the existing merge-base-against-`origin/main`/`main` logic unchanged. No regression for any path that works today.
- No change to the log-excerpt fallback path, or to anything when a dispatch result already carries real `output` (the common case this function exists to backstop, per gh:#2350).

## Compatibility and scope

- Touches only the diff-base selection inside `_await_calibration_job()` (~10 lines). No schema change (the column already exists and is already populated). No other dispatch path is affected — this function is specific to capability-sweep calibration dispatches.
- Does not address the separate, already-answered question of whether `# synlynk-meta` parsing itself works (#2170: confirmed yes, mechanically).
- Does not address why the probe's two jobs independently reported `TASK_DELIVERY_FAILED`/`FAILED_NOOP_DENIED` — those are receipt/no-op-detection protocol outcomes (#720) on synthetic calibration dispatches, orthogonal to this diff-contamination bug, and out of scope here.
- Out of scope (unchanged): #2170's remaining historical backfill-audit item (~3390 rows with `quality_verified=NULL`), and any full capability-sweep run — both still require their own separate approval per the standing step-10 hold.

## Acceptance criteria

- A calibration job dispatched from a worktree whose parent branch is ahead of `origin/main` (has unmerged commits of its own) produces a reconstructed `output` diff containing **only** that job's own worktree changes — none of the parent branch's prior commits.
- A calibration job dispatched from a worktree whose parent branch matches `origin/main`/`main` exactly (today's common case) is byte-for-byte unaffected — `base_sha` and the old merge-base recompute resolve to the same commit in that case, so output is identical.
- If `job.get("base_sha")` is absent (defensive edge case), behavior falls back to today's merge-base recompute, unchanged.
- Regression test: construct a worktree fixture forked from a non-`origin/main` parent branch with its own extra commit, dispatch a trivial calibration task against it, and assert the reconstructed output's diff excludes the parent branch's unrelated commit content and includes only the task's own change.
- Run `pytest tests/test_capability_sweep.py -q` (or the closest matching existing module) plus the new regression test before marking complete.

## Approval record

Approved by Nikhil via AskUserQuestion ("Spec + fix #2567 now (recommended)") in the conductor session, 2026-10-24, authorizing this spec as the next step-10 action after gh:#2332 was found already-fixed and closed.
