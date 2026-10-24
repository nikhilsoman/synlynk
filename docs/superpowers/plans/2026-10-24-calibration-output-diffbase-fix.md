# Calibration Output Diff-Base Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop `_await_calibration_job()` from reconstructing a calibration job's scored output from the wrong diff base when the dispatching process is running ahead of `origin/main`, so the output always reflects only that job's own worktree changes.

**Architecture:** `_await_calibration_job()` in `synlynk/capability_sweep.py` currently recomputes `git merge-base HEAD origin/main` (falling back to `main`) live, inside the job's worktree, to find the diff base. Every dispatched job already carries its own recorded `base_sha` (the actual fork point of its worktree, captured by `dispatch_agent()` at creation time and persisted on the job dict / `daemon_jobs.base_sha` column). The fix is to prefer `job.get("base_sha")` as the diff base, falling back to the existing merge-base recompute only when `base_sha` is missing or empty — a single-function, ~10-line change with no schema impact.

**Tech Stack:** Python 3 stdlib (`subprocess`, `os`), pytest, real temporary git repos for the regression test (no mocking of git subprocess calls, to faithfully exercise real `merge-base`/`diff` behavior).

---

## File Structure

- **Modify:** `synlynk/capability_sweep.py:329-371` (inside `_await_calibration_job()`) — change diff-base selection logic.
- **Test:** `tests/test_capability_sweep.py` — add one new regression test function, placed near the existing `_await_calibration_job()` tests (e.g. after `test_await_calibration_job_handles_timeout`).

No other files are touched. No new files are created.

---

### Task 1: Prefer recorded `base_sha` over live merge-base recompute in `_await_calibration_job()`

**Files:**
- Modify: `synlynk/capability_sweep.py:289-381` (the `_await_calibration_job()` function)
- Test: `tests/test_capability_sweep.py`

- [ ] **Step 1: Write the failing regression test**

Add this test to `tests/test_capability_sweep.py` (place it near the other `_await_calibration_job` tests, e.g. directly after `test_await_calibration_job_handles_timeout`):

```python
def test_await_calibration_job_uses_recorded_base_sha_not_live_merge_base(tmp_path):
    """gh:#2567 — dispatching a calibration job from a feature branch ahead of
    origin/main must not leak that branch's own prior commits into the job's
    reconstructed output. The job's own recorded base_sha (its real fork point)
    must be used as the diff base, not a live merge-base recompute against
    origin/main/main, which resolves to the wrong (earlier) commit in this case.
    """
    import subprocess

    from synlynk import capability_sweep

    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True, capture_output=True)
    (repo / "base.txt").write_text("base\n")
    subprocess.run(["git", "add", "base.txt"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "base commit"], cwd=repo, check=True, capture_output=True)

    # Simulate the dispatching process's own feature branch, ahead of main with
    # its own unrelated, already-committed work (e.g. the #2553 work in the real
    # incident).
    subprocess.run(["git", "checkout", "-b", "parent-feature"], cwd=repo, check=True, capture_output=True)
    (repo / "parent_change.txt").write_text("parent feature work\n")
    subprocess.run(["git", "add", "parent_change.txt"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "parent feature change"], cwd=repo, check=True, capture_output=True)
    parent_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()

    # The calibration job's own worktree, forked from the parent feature branch
    # (not from main) — mirrors how a nested dispatch worktree is actually created.
    job_dir = tmp_path / "job-worktree"
    subprocess.run(
        ["git", "worktree", "add", str(job_dir), "-b", "dispatch/job-xyz", "parent-feature"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    (job_dir / "job_change.txt").write_text("the job's own work\n")
    subprocess.run(["git", "add", "job_change.txt"], cwd=job_dir, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "job's own change"], cwd=job_dir, check=True, capture_output=True)

    job = {
        "job_id": "job-xyz",
        "status": "completed",
        "pid": None,
        "log_file": None,
        "worktree_path": str(job_dir),
        "base_sha": parent_sha,
    }

    result = capability_sweep._await_calibration_job(job, timeout_s=10)

    assert "job_change.txt" in result["output"]
    assert "parent_change.txt" not in result["output"], (
        "reconstructed output must not leak the dispatching branch's own prior "
        "commits (gh:#2567)"
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_capability_sweep.py::test_await_calibration_job_uses_recorded_base_sha_not_live_merge_base -v`

Expected: FAIL — the assertion `"parent_change.txt" not in result["output"]` fails because the current code recomputes `merge-base HEAD main` inside `job_dir`, which resolves to the "base commit" (the common ancestor of `main` and `parent-feature`), so the diff includes both `parent_change.txt` and `job_change.txt`.

- [ ] **Step 3: Implement the fix**

In `synlynk/capability_sweep.py`, replace the diff-base computation block inside `_await_calibration_job()` (currently lines ~329-360, the body of the `if worktree_path and os.path.exists(worktree_path): try: ...` block) with:

```python
            try:
                base_sha = (job.get("base_sha") or "").strip()
                if not base_sha:
                    # Fallback only (gh:#2567): no recorded base_sha available, so
                    # recompute against origin/main / main as before. Preferring
                    # the job's own recorded base_sha avoids leaking the
                    # dispatching process's own branch history into the
                    # reconstructed diff when that process is running ahead of
                    # origin/main.
                    base_ref = "origin/main"
                    mb_res = subprocess.run(
                        ["git", "-C", worktree_path, "merge-base", "HEAD", base_ref],
                        capture_output=True,
                        text=True,
                        check=False,
                        timeout=5,
                    )
                    base_sha = (mb_res.stdout or "").strip()
                    if not base_sha:
                        mb_res = subprocess.run(
                            ["git", "-C", worktree_path, "merge-base", "HEAD", "main"],
                            capture_output=True,
                            text=True,
                            check=False,
                            timeout=5,
                        )
                        base_sha = (mb_res.stdout or "").strip()

                if base_sha:
                    res = subprocess.run(
                        ["git", "-C", worktree_path, "diff", base_sha],
                        capture_output=True,
                        text=True,
                        check=False,
                        timeout=5,
                    )
                    diff_text = (res.stdout or "").strip()
                else:
                    res = subprocess.run(
                        ["git", "-C", worktree_path, "diff", "HEAD"],
                        capture_output=True,
                        text=True,
                        check=False,
                        timeout=5,
                    )
                    diff_text = (res.stdout or "").strip()
            except Exception:
                diff_text = ""
```

The surrounding function (imports, the `worktree_path`/`diff_text` setup before this block, and the log-text fallback after it) is unchanged.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_capability_sweep.py::test_await_calibration_job_uses_recorded_base_sha_not_live_merge_base -v`

Expected: PASS

- [ ] **Step 5: Run the full capability_sweep test module to check no regressions**

Run: `pytest tests/test_capability_sweep.py -q`

Expected: all tests pass, including `test_dispatch_calibration_task_awaits_async_job_and_captures_output` and `test_await_calibration_job_handles_timeout` (neither sets `worktree_path` on their job dicts, so they exercise the unchanged log-text-only path and are unaffected by this change).

- [ ] **Step 6: Commit**

```bash
git add synlynk/capability_sweep.py tests/test_capability_sweep.py
git commit -m "fix(capability-sweep): use recorded base_sha for calibration diff, not live merge-base (#2567)"
```

---

## Self-Review

**Spec coverage:**
- "Prefer `job.get('base_sha')` as the diff base" → Task 1, Step 3.
- "Fallback to existing merge-base-against-origin/main/main logic if base_sha is missing" → Task 1, Step 3 (unchanged fallback branch preserved verbatim).
- "No change to log-excerpt fallback path, or when dispatch result already carries real output" → untouched; the `if "output" not in job or not job["output"]:` guard and the trailing log-text/diff-text combination logic are unchanged.
- "Regression test: worktree fixture forked from a non-origin/main parent branch with its own extra commit... assert reconstructed output excludes parent branch's unrelated commit content and includes only the task's own change" → Task 1, Step 1.
- "Run pytest tests/test_capability_sweep.py -q... before marking complete" → Task 1, Step 5.
- Acceptance criterion "byte-for-byte unaffected when parent branch matches origin/main/main exactly" is satisfied structurally: when a job's worktree is forked directly from `origin/main`, `dispatch_agent()` records that same commit as `base_sha`, so `job.get("base_sha")` and the old merge-base recompute resolve to the identical SHA — no separate test needed since this is the default/common path already covered by the two existing tests in `tests/test_capability_sweep.py` that don't set `worktree_path` at all (they skip the diff logic entirely, confirming no regression in the no-diff-needed case).

**Placeholder scan:** No TBD/TODO, no "add appropriate handling," no code elided — full function body given in Step 3, full test given in Step 1.

**Type consistency:** `job` is a plain `dict` throughout (matches existing `_await_calibration_job(job: dict, timeout_s: int = 120) -> dict` signature — unchanged). `base_sha` is a `str` in both the new and fallback paths, consistent with existing usage (`.strip()` applied uniformly). No new functions or signatures introduced.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-10-24-calibration-output-diffbase-fix.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
