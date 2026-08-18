# Phantom-PR Guard for Review/GH-Write-Only Dispatch Jobs (#1058) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop `_maybe_open_worktree_pr` from auto-opening a GitHub PR for review-type or gh-write-only dispatch jobs, which are never supposed to produce code changes.

**Architecture:** Add a single early-return guard at the top of `_maybe_open_worktree_pr` in `synlynk/jobs.py`, checking `job.get("task_type") == "review"` or `job.get("requires_gh_write")` — both already present on the `job` dict by the time this function runs, so no new parameters or call-site plumbing are needed.

**Tech Stack:** Python, pytest, `monkeypatch` on `subprocess.run` (existing test pattern in `tests/test_jobs.py`).

---

### Task 1: Add early-return guard to `_maybe_open_worktree_pr`

**Files:**
- Modify: `synlynk/jobs.py:336-343`
- Test: `tests/test_jobs.py` (add tests after `test_maybe_open_worktree_pr_uses_resolved_base_branch`, currently ending at line 958)

- [ ] **Step 1: Write the failing tests**

Add these two tests to `tests/test_jobs.py`, immediately after `test_maybe_open_worktree_pr_uses_resolved_base_branch` (after line 958):

```python
def test_maybe_open_worktree_pr_skips_for_review_task_type(tmp_path, monkeypatch):
    import synlynk.jobs as jobs_mod

    worktree_path = tmp_path / "repo"
    worktree_path.mkdir()

    def fake_run(cmd, **kwargs):
        raise AssertionError(f"no subprocess call expected, got: {cmd}")

    monkeypatch.setattr(jobs_mod.subprocess, "run", fake_run)

    pr_number = jobs_mod._maybe_open_worktree_pr(
        {"id": "job-1", "task": "review PR 1053", "task_type": "review"},
        str(worktree_path),
        "dispatch/agy/job-1",
    )

    assert pr_number is None


def test_maybe_open_worktree_pr_skips_for_requires_gh_write(tmp_path, monkeypatch):
    import synlynk.jobs as jobs_mod

    worktree_path = tmp_path / "repo"
    worktree_path.mkdir()

    def fake_run(cmd, **kwargs):
        raise AssertionError(f"no subprocess call expected, got: {cmd}")

    monkeypatch.setattr(jobs_mod.subprocess, "run", fake_run)

    pr_number = jobs_mod._maybe_open_worktree_pr(
        {"id": "job-2", "task": "close stale issue", "task_type": "", "requires_gh_write": True},
        str(worktree_path),
        "dispatch/codex/job-2",
    )

    assert pr_number is None
```

Note: these tests assert `subprocess.run` is never called at all (any call raises `AssertionError`), which is a stronger check than inspecting `captured` calls after the fact — it fails immediately at the first unexpected call.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_jobs.py -k "maybe_open_worktree_pr" -v`

Expected: `test_maybe_open_worktree_pr_skips_for_review_task_type` and
`test_maybe_open_worktree_pr_skips_for_requires_gh_write` both FAIL with
`AssertionError: no subprocess call expected, got: [...]` (since the guard doesn't
exist yet, the function proceeds to call `detect_remote_owner_repo`/`gh pr list`,
which is not mocked via `_pkg` in these two new tests, so it will hit `_pkg` and
likely return early before subprocess — re-check actual failure mode and confirm it
is a genuine failure, not an accidental pass, before proceeding).

- [ ] **Step 3: Implement the guard**

In `synlynk/jobs.py`, modify `_maybe_open_worktree_pr` (currently lines 336-343):

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
    if not detect_remote_owner_repo:
        return
```

(This replaces the 4-line function opening with the 4-line opening plus the new
6-line guard block; everything from `detect_remote_owner_repo = _pkg(...)` onward
is unchanged.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_jobs.py -k "maybe_open_worktree_pr" -v`

Expected: all three tests pass —
`test_maybe_open_worktree_pr_uses_resolved_base_branch` (regression, unaffected
since its `job` dict has no `task_type`/`requires_gh_write` keys),
`test_maybe_open_worktree_pr_skips_for_review_task_type`, and
`test_maybe_open_worktree_pr_skips_for_requires_gh_write`.

- [ ] **Step 5: Run the full test suite to confirm no regressions**

Run: `pytest tests/ -x -q`

Expected: all tests pass (same pass count as baseline, plus the 2 new tests).

- [ ] **Step 6: Commit**

```bash
git add synlynk/jobs.py tests/test_jobs.py
git commit -m "fix: skip auto-PR creation for review/gh-write-only dispatch jobs (#1058)

_maybe_open_worktree_pr previously opened a PR for any finalized worktree
with a non-empty diff, regardless of job type. Review-dispatch and
gh-write-only jobs are never supposed to produce code changes, so an
incidental diff (stray scratch files, lockfile churn, partial edits)
triggered a phantom PR. This adds an early-return guard skipping PR
creation when job.task_type == 'review' or job.requires_gh_write is set."
```

---

## Self-Review Notes

- **Spec coverage:** The spec's single "Fix" requirement (early-return guard,
  exact condition, exact log message) is fully implemented in Task 1 Step 3. The
  spec's "Testing" section requirements (review-type case, gh-write-only case,
  regression case) map to Steps 1/4 (new tests) and Step 5 (existing
  `test_maybe_open_worktree_pr_uses_resolved_base_branch` plus full suite).
- **Placeholder scan:** none found — all code blocks are complete and copy-pasteable.
- **Type consistency:** `job.get("task_type")` and `job.get("requires_gh_write")`
  match the exact key names already used at `synlynk/dispatch.py:609,2579` and
  `synlynk/jobs.py:574` (the existing `scope_paths` guard) — no naming drift.
