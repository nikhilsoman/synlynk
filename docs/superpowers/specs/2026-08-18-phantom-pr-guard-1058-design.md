# Phantom-PR Guard for Review/GH-Write-Only Dispatch Jobs (#1058) — Design

## Problem

`_maybe_open_worktree_pr` (`synlynk/jobs.py:336`) auto-opens a GitHub PR whenever a
finalized worktree has a non-empty diff, regardless of what kind of job produced it.
Review-dispatch jobs (`task_type="review"`) and gh-write-only dispatch jobs
(`requires_gh_write=True`) are not supposed to produce code changes at all — their
only legitimate output is a GitHub review or comment, independently verifiable via
`gh_write_verified()`. When these jobs incidentally leave a non-empty worktree diff
(e.g. stray scratch files, lockfile churn, an agent partially editing before reverting),
the daemon opens a phantom PR nobody asked for.

This produced 5+ confirmed phantom PRs in one session alone (#1049, #1052, #1054,
#1055, #1057), each requiring manual discovery and closure.

## Root cause (verified against current code, not the issue's original hypothesis)

The issue's own body guesses the logic lives in `synlynk/dispatch.py`. It does not.
The actual auto-finalize-to-PR entry point is `_maybe_open_worktree_pr` in
`synlynk/jobs.py`, called from exactly one call site (`synlynk/jobs.py:581`), inside
the branch that runs after a worktree commit/push. That call site already has one
partial guard:

```python
if job.get("scope_paths") and not job.get("requires_gh_write"):
    print(f"  ⚠ scope-declared job {job.get('id', '')}: skipping automatic PR creation "
          f"(pass --requires-gh-write to allow)")
else:
    pr_number = _maybe_open_worktree_pr(job, worktree_path, worktree_branch)
```

This only covers scope-declared jobs without `requires_gh_write`. It does nothing for
review-type jobs or for jobs that legitimately have `requires_gh_write=True` (whose
diff, if any, was never the point of the job).

Both `job.get("task_type")` and `job.get("requires_gh_write")` are confirmed reliably
present on the `job` dict by the time `_maybe_open_worktree_pr` runs:
- `task_type` is set at `synlynk/dispatch.py:2579` (`"task_type": task_type or ""`) and
  already read the same way at `synlynk/dispatch.py:609`.
- `requires_gh_write` is already read at the existing guard above (`jobs.py:574`).

No new parameters or plumbing are required.

## Fix

Add an early-return guard at the top of `_maybe_open_worktree_pr`, before any `gh`
calls are made:

```python
def _maybe_open_worktree_pr(job: dict, worktree_path: str, worktree_branch: Optional[str]) -> Optional[int]:
    """Opens a PR for a finalized worktree if one does not already exist."""
    if not worktree_path or not worktree_branch:
        return

    if job.get("task_type") == "review" or job.get("requires_gh_write"):
        print(
            f"  ⚠ skipping automatic PR creation for {worktree_branch}: "
            f"job is review/gh-write-only (task_type={job.get('task_type') or 'none'}, "
            f"requires_gh_write={bool(job.get('requires_gh_write'))})"
        )
        return

    detect_remote_owner_repo = _pkg("detect_remote_owner_repo")
    ...
```

This condition was chosen over the alternative (a diff-relevance floor requiring the
diff to touch files named in the task) because it requires no new heuristics or
task-text parsing, uses signals already present and already trusted elsewhere in the
same file, and matches exactly the two categories the issue itself identifies as
never expected to produce code.

## Non-goals

- No change to the existing `scope_paths`-without-`requires_gh_write` guard.
- No diff-relevance floor (rejected — more complex, no reliable "files named in task"
  signal exists yet; can be revisited later if a new failure mode appears that this
  guard doesn't cover).
- No change to `gh_write_verified()` or the review-verification path — this only
  stops spurious PR creation, it doesn't change how review/gh-write jobs report
  success.

## Testing

Add a test (likely `tests/test_jobs.py` or wherever `_maybe_open_worktree_pr` is
already covered — search first) with two new cases:

1. `job = {"task_type": "review", ...}` → `_maybe_open_worktree_pr(job, path, branch)`
   returns `None` without calling `gh pr list`/`gh pr create` (assert via mock/monkeypatch
   on `subprocess.run` that it's never invoked, or that no `gh` subprocess call happens).
2. `job = {"requires_gh_write": True, "task_type": "", ...}` → same assertion.
3. Regression: an existing/new case with `task_type=""` and `requires_gh_write=False`
   still proceeds to the existing `gh pr list`/`gh pr create` flow (unchanged behavior).

Also re-run the existing test(s) covering `_maybe_open_worktree_pr`'s current behavior
to confirm no regression.
