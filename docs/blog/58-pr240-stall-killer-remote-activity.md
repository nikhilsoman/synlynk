---
title: "PR #240 — The Stall-Killer Wasn't Checking Its Own Receipts"
date: 2026-07-14
series: "Building the OS for Multi-Agent Development"
post: 58
pr: "#240"
issue: "#202"
merged: 2026-07-14
---

## The Broader Goal at the End of the Previous PR

PR #238 (previous post) closed a small dispatch-hygiene gap. #202 — filed 2026-07-12 and deliberately parked at the time ("until fixed, don't trust `synlynk jobs` status display alone; cross-check `jobs.json`, `git log`/`git status`, and `gh pr list` directly") — was the next item pulled off the backlog, per explicit user sequencing. The symptom: `synlynk jobs` would show `FAILED (exit -1)` for jobs that had, in fact, completed real work — committed, pushed, PR opened — with the discrepancy only visible by manually cross-checking `jobs.json` against git history.

## Strategic Shifts in This PR (if any)

The fix landed smaller than first scoped. The initial read (presented to the user before implementation started) proposed three changes: (1) add the missing remote-activity check, (2) route stall-kills through the existing `failed_unverified` status instead of a hard `failed`, and (3) fix `_write_job_summary()`'s label formatting so a `None` exit code wouldn't print misleadingly as `-1`. Tracing the downstream reconcile logic in full before writing the dispatch prompt showed (2) and (3) were unnecessary: if the stall-killer simply *stops killing prematurely* in the one scenario it was wrongly killing, the job stays `"running"` and gets picked up — correctly, with the correct label — by reconcile logic that already existed from the "Job Lifecycle Ground-Truth Verification" epic (#128/#129/#182/#184/#185/#198). That epic added `remote_has_activity`-aware promotion to `"completed"` in `_reconcile_jobs()`'s `waitpid_reaped` branch months earlier — it just never got wired into the *stall-kill* branch, which runs earlier in the same function and short-circuits before the good logic ever executes.

## What This PR Shipped

**Root cause.** `_check_job_stall()` (`synlynk/dispatch.py`) is the code that SIGKILLs a job whose log file has gone stale past its configured timeout. Before killing, it checks for local git activity in the worktree and extends the grace period if any is found — but the call was `_inspect_worktree_git_state(job.get("worktree_path"))`, a single argument. That function accepts two more optional parameters (`worktree_branch`, `started_at`) needed to also check whether `origin/<branch>` already has pushed commits; without them, `_inspect_origin_branch_activity()` returns `None` immediately (it requires all three inputs truthy), so `remote_has_activity` was always `False` from this call path — even for a job that had already pushed and opened a PR.

**The fix, in full:**

```python
git_state = inspect_worktree_git_state(
    job.get("worktree_path"), job.get("worktree_branch"), job.get("started_at")
) if inspect_worktree_git_state else None
if git_state and git_state.get("has_activity"):
    ...
    return False
if git_state and git_state.get("remote_has_activity"):
    remote_ref = git_state.get("remote_ref")
    remote_commit_count = git_state.get("remote_commit_count", 0)
    print(
        f"  Stall check extended for job {job.get('id')}: remote activity detected on "
        f"{remote_ref} ({remote_commit_count} commit(s) since {job.get('started_at')})."
    )
    return False
```

The hard-kill / `failed` / `exit_code=-1` path below is untouched — it still fires, correctly, for jobs with zero local *and* zero remote activity. Two new tests pin both branches: `test_check_job_stall_extends_on_remote_activity` (remote activity present → extends, doesn't touch `job["status"]`) and `test_check_job_stall_still_kills_on_zero_activity` (regression guard on the pre-existing kill path).

**Investigation, not implementation, was the expensive part.** Getting to this two-line fix required reading four separate call sites of `_write_job_summary()` across `dispatch.py` and `jobs.py`, confirming three of them (the ones the roadmap had actually flagged as suspects) were already correct, and tracing the one genuinely-broken path back to a single missing pair of function arguments. The dispatch prompt handed to the implementer encoded all of that — exact diff, exact reasoning for why nothing else needed to change — so the actual code change executed in a single pass.

## Brainstorm Visuals Used

None — code-tracing investigation, no visual/UI decisions.

## What This Achieved on the Path to Autonomy

`synlynk jobs` status is now trustworthy for the one scenario that was silently lying: a job that did real, confirmed work but happened to look locally clean when its log went stale. #202's original parked guidance ("cross-check manually") can be retired for this case. Cost: 21,502 in / 5,376 out tokens (~$0.15), 309s, first-pass with no rework — cherry-picked, full-suite verified (1010 passed, 2 skipped), and merged same-session as #238.

## Strategic Note: The Goal at the End of This PR

Both #237 and #202 — the two items pulled forward to strengthen the v0.12.0 "Trust & Cost-Aware Routing" theme — are now merged. What's left before that release can be cut: PR #236 (Measurement Ledger Hardening Phase 1) merging, and PR #241 (the design spec + plan docs for that same epic) merging. Housekeeping also surfaced 22 stray auto-opened per-task dispatch PRs (#214–#235, #239) that duplicate work already integrated into #236/#240 — flagged for cleanup, pending explicit confirmation before a bulk close.
