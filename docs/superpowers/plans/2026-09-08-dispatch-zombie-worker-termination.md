# Dispatch Zombie Worker Termination Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent erroneous `killed_zombie` classifications, eliminate datetime `TypeError`s, resolve GitHub App `.pem` private key paths across worktrees, isolate per-job reconciliation exceptions, and store job logs persistently outside disposable worktrees (#1498).

**Architecture:**
1. In `synlynk/gh_verify.py` and `synlynk/jobs.py`, normalize all datetime comparisons to timezone-aware UTC and guard comparisons defensively against `TypeError`.
2. In `synlynk/github_app_auth.py`, implement `_resolve_private_key_path` to resolve `.pem` relative paths to absolute paths before passing to `openssl`, regardless of current working directory.
3. In `synlynk/jobs.py:_reconcile_daemon_jobs`, wrap each job iteration in a `try...except Exception:` block so an unhandled exception on one job cannot terminate reconciliation or crash the daemon loop.
4. In `synlynk/dispatch.py`, configure worker stdout/stderr redirection and `.exit` file creation to use the repo's central `.synlynk/logs/` directory instead of inside disposable worktrees; in `_reap_zombie_worktree`, preserve logs before deleting worktrees.
5. In `synlynk/jobs.py:_reconcile_daemon_jobs`, inspect `{log_path}.exit` and process exit status before classifying an exited job as a zombie, correctly distinguishing clean completions (`done`), crashes, and timeouts from zombies.

**Tech Stack:** Python 3.9+, SQLite3, git worktrees, openssl, pytest.

**Spec:** `docs/superpowers/specs/2026-09-08-dispatch-zombie-worker-termination-design.md`

## Global Constraints
- Preserve all existing fail-closed Sentinel safety gates.
- Zero fallback to personal host GitHub authentication; respect role-scoped App tokens.
- Do not bypass worktree isolation for worker execution.
- Maintain test coverage across macOS and Linux.

---

### Task 1: Timezone-Aware Datetime Normalization in `gh_verify.py` and `jobs.py`

**Files:**
- Modify: `synlynk/gh_verify.py`
- Modify: `synlynk/jobs.py`
- Test: `tests/test_gh_verify.py`
- Test: `tests/test_jobs.py`

**Interfaces:**
- Consumes: `datetime`, `timezone`, `_parse_iso8601`
- Produces: `_to_utc_dt(val: Union[str, datetime, None]) -> Optional[datetime]`, defensive `gh_write_verified` comparisons, safe `_apply_gh_write_verification`

- [ ] **Step 1: Write failing test in `tests/test_gh_verify.py` reproducing datetime TypeError**
  Create test asserting `gh_write_verified` handles offset-naive `since` string compared with offset-aware GitHub timestamp without raising `TypeError`.
- [ ] **Step 2: Run test to confirm failure**
  Run `pytest tests/test_gh_verify.py -k test_datetime_naive_and_aware_comparison`.
- [ ] **Step 3: Implement `_to_utc_dt` and defensive comparisons in `synlynk/gh_verify.py` and `synlynk/jobs.py`**
  Ensure all datetimes are converted to UTC before comparison, wrap comparisons in `try...except (TypeError, ValueError)`, and wrap `gh_write_verified` in `_apply_gh_write_verification` in `try...except Exception:`.
- [ ] **Step 4: Run tests to verify pass**
  Run `pytest tests/test_gh_verify.py tests/test_jobs.py`.
- [ ] **Step 5: Commit changes**
  `git commit -m "fix(gh_verify): normalize datetimes to timezone-aware UTC (#1498)"`

---

### Task 2: Absolute `.pem` Private Key Resolution Across Worktrees

**Files:**
- Modify: `synlynk/github_app_auth.py`
- Modify: `synlynk/daemon.py`
- Test: `tests/test_github_app_auth.py`
- Test: `tests/test_daemon_token_refresh.py`

**Interfaces:**
- Consumes: `private_key_path: str`, `apps_dir: Optional[str]`
- Produces: `_resolve_private_key_path(private_key_path: str, apps_dir: Optional[str] = None) -> str`

- [ ] **Step 1: Write failing test in `tests/test_github_app_auth.py`**
  Test that `refresh_installation_token` and `_sign_jwt` resolve a relative `private_key_path` when CWD is changed to an external directory.
- [ ] **Step 2: Run test to confirm failure**
  Run `pytest tests/test_github_app_auth.py -k test_resolve_private_key_path_from_worktree`.
- [ ] **Step 3: Implement `_resolve_private_key_path` in `synlynk/github_app_auth.py`**
  Resolve relative path against `apps_dir`, `_daemon_state_path("github_apps")`, repo common directory, or CWD. Update `_sign_jwt` and `refresh_installation_token`.
- [ ] **Step 4: Run tests to verify pass**
  Run `pytest tests/test_github_app_auth.py tests/test_daemon_token_refresh.py`.
- [ ] **Step 5: Commit changes**
  `git commit -m "fix(auth): resolve github app pem paths to absolute paths across worktrees (#1498)"`

---

### Task 3: Per-Job Exception Isolation in Daemon Reconciler

**Files:**
- Modify: `synlynk/jobs.py`
- Test: `tests/test_jobs.py`

**Interfaces:**
- Consumes: `_reconcile_daemon_jobs`, `_reconcile_jobs`
- Produces: Loop-level isolation protecting reconciler from single-job exceptions

- [ ] **Step 1: Write failing test in `tests/test_jobs.py`**
  Create test where one job raises an unexpected `RuntimeError` during reconciliation, verifying subsequent jobs in the same batch are still reconciled.
- [ ] **Step 2: Run test to confirm failure**
  Run `pytest tests/test_jobs.py -k test_reconcile_daemon_jobs_isolates_exceptions`.
- [ ] **Step 3: Implement per-job `try...except Exception:` block in `_reconcile_daemon_jobs` and `_reconcile_jobs`**
  Catch exceptions per job iteration, log warning with traceback to stderr, and continue to the next job.
- [ ] **Step 4: Run tests to verify pass**
  Run `pytest tests/test_jobs.py -k test_reconcile`.
- [ ] **Step 5: Commit changes**
  `git commit -m "fix(jobs): isolate per-job exceptions in daemon reconciliation (#1498)"`

---

### Task 4: Persistent Job Logs Outside Disposable Worktrees

**Files:**
- Modify: `synlynk/dispatch.py`
- Modify: `synlynk/jobs.py`
- Test: `tests/test_dispatch.py`
- Test: `tests/test_jobs.py`

**Interfaces:**
- Consumes: `_repo_common_dir()`, `worktree_path`, `job_id`
- Produces: Persistent logs in `.synlynk/logs/{job_id}.log`, worktree reap log preservation

- [ ] **Step 1: Write failing test in `tests/test_dispatch.py` and `tests/test_jobs.py`**
  Verify that when a job is dispatched in a worktree and the worktree is reaped/deleted, `{job_id}.log` and `{job_id}.log.exit` remain accessible in `.synlynk/logs/`.
- [ ] **Step 2: Run test to confirm failure**
  Run `pytest tests/test_dispatch.py -k test_job_logs_outside_worktree`.
- [ ] **Step 3: Update `dispatch.py` to write logs to central `.synlynk/logs` and `jobs.py:_reap_zombie_worktree` to preserve logs**
  Point `logs_dir` in `dispatch.py` to `os.path.join(_repo_common_dir(), ".synlynk", "logs")`. In `_reap_zombie_worktree`, copy any existing log file out before deleting the worktree directory.
- [ ] **Step 4: Run tests to verify pass**
  Run `pytest tests/test_dispatch.py tests/test_jobs.py`.
- [ ] **Step 5: Commit changes**
  `git commit -m "fix(dispatch): store job logs outside disposable worktrees (#1498)"`

---

### Task 5: Proper Exit Signal Detection & Zombie Classification Fix

**Files:**
- Modify: `synlynk/jobs.py`
- Test: `tests/test_jobs.py`

**Interfaces:**
- Consumes: `_reconcile_daemon_jobs`, `{log_path}.exit`, `_gtv_status_for_daemon_exit`
- Produces: Correct exit classification for non-gh-write design/review jobs

- [ ] **Step 1: Write failing test in `tests/test_jobs.py`**
  Simulate a completed design/review job with `requires_gh_write=False`, an existing worktree, dead PID, and `{log_path}.exit` containing `0`. Verify it reconciles as `done` (exit code 0), NOT `killed_zombie` (exit code -9).
- [ ] **Step 2: Run test to confirm failure**
  Run `pytest tests/test_jobs.py -k test_design_job_with_worktree_not_classified_as_zombie`.
- [ ] **Step 3: Refactor `_reconcile_daemon_jobs` exit resolution order**
  Check `{log_path}.exit` and waitpid status BEFORE evaluating zombie fallback. Only mark `killed_zombie` if PID is dead AND no exit marker exists AND no git activity / receipt exists.
- [ ] **Step 4: Run tests to verify pass**
  Run `pytest tests/test_jobs.py`.
- [ ] **Step 5: Commit changes**
  `git commit -m "fix(jobs): prevent premature zombie classification on completed worktree jobs (#1498)"`

---

### Task 6: Full Regression Testing & Verification

**Files:**
- Test: Full test suite (`pytest tests/`)
- Test: `synlynk doctor`

- [ ] **Step 1: Run full test suite**
  Run `pytest` to confirm all tests pass.
- [ ] **Step 2: Run `synlynk doctor`**
  Verify ecosystem health checks pass.
- [ ] **Step 3: Update devlog and docs**
  Update `project-docs/devlogs/agy.md` and `project-docs/costs.md`.
- [ ] **Step 4: Commit and create PR**
  Create pull request referencing `#1498`.
