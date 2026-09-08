# Design Spec: Diagnose and Prevent Zombie Worker Termination (#1498)

- **Date:** 2026-09-08
- **Author:** @nikhilsoman (Agy / AntiGravity)
- **Status:** Draft (Spec Review)
- **Issue:** [#1498](https://github.com/nikhilsoman/synlynk/issues/1498)
- **Story:** `story-92c4e2ca`

---

## 1. Problem Statement & Empirical Evidence

Multiple recent design and review dispatches (`job-75c99b2f` on Codex, `job-8276115e` on Agy, `job-98c2d44f` on Grok) terminated unexpectedly after 3–5 minutes with status `killed_zombie` and exit code `-9`. In each case:
- Zero files were produced in the workspace.
- No `STALL_NO_OUTPUT` sentinel event was logged.
- Worker logs were unavailable because the disposable worktrees were reaped upon zombie classification.
- The supervisor/daemon log (`.synlynk/daemon.log`) revealed repeated daemon crashes and errors:
  1. `TypeError: can't compare offset-naive and offset-aware datetimes` in `synlynk/gh_verify.py` during list-expect verification.
  2. GitHub App JWT signing openssl failures: `Could not open file or uri for loading private key from .synlynk/github_apps/architect.pem: No such file or directory`.
  3. Historical macOS fork-safety warnings: `objc_initializeAfterForkError`.

This is an infrastructure reliability and supervisory state-machine failure. The active CLI and imported source both report Synlynk `0.18.0`.

---

## 2. Root Cause Analysis

### 2.1 The Premature Zombie Reaping & Log Annihilation Bug
In `synlynk/jobs.py:_reconcile_daemon_jobs` (lines 2598–2667):
```python
def has_leaked_worktree(job_id, log_path):
    path = _daemon_job_worktree_path(job_id, log_path)
    return bool(path and os.path.exists(os.path.join(path, ".git")))
```
For any job that ran in an isolated worktree, `path` contains `.git`. Therefore, `has_leaked_worktree` evaluates to `True` unconditionally.

When the worker process completes, `os.waitpid(pid, os.WNOHANG)` raises `ChildProcessError` because the worker was spawned detached (`start_new_session=True`). The exception handler:
```python
except ChildProcessError:
    if not _pid_is_alive(pid):
        exited = True; zombie = has_leaked_worktree(job_id, log_path)
```
sets `zombie = True`!
Then, in lines 2631–2667:
```python
if exited:
    if zombie:
        ...
        if not requires_gh_write or gh_write_verified_str != "true":
            zombie_status, zombie_exit_code = "killed_zombie", -9
        _reap_zombie_worktree(job_id, log_path)
        conn.execute("UPDATE daemon_jobs SET status=?, exit_code=?, completed_at=? ...", ...)
        conn.commit()
        continue
```
Because the job did not require a GitHub write (like a design or review task), `zombie_status` was unconditionally assigned `"killed_zombie"` with exit code `-9`. `_reap_zombie_worktree` was immediately executed, and `continue` skipped the entire normal exit code detection block (reading `{log_path}.exit`, evaluating ground-truth verification, writing cost entries, and writing job summaries).

Crucially, because `dispatch.py` placed `logs_dir` at `worktree_path/.synlynk/logs`, `_reap_zombie_worktree` deleted the worktree directory, permanently destroying `{job_id}.log` and `{job_id}.log.exit`.

### 2.2 Datetime TypeError in Verification
In `synlynk/gh_verify.py` and `synlynk/jobs.py`:
- `_apply_gh_write_verification` in `jobs.py` parsed `since = started_at` using `_parse_iso8601(since)`.
- When GitHub returns timestamps (e.g. `submittedAt` or `createdAt` on PR reviews/comments), they end with `"Z"` and parse to timezone-aware UTC datetimes.
- If `since` was stored in `daemon_jobs.started_at` without an offset or timezone tag and parsed naively, comparing `entry_dt < since_dt` in `gh_verify.py` raised `TypeError: can't compare offset-naive and offset-aware datetimes`.
- In `_apply_gh_write_verification`:
```python
except TypeError as exc:
    if "evidence" not in str(exc):
        raise
```
The TypeError was re-raised, escaping unhandled!

### 2.3 Unprotected Reconciler Loop Exception Boundary
In `synlynk/jobs.py:_reconcile_daemon_jobs`:
```python
try:
    for (job_id, ...) in rows:
        ...
```
A single `try` wrapped the entire `for` loop across all jobs. When any job triggered an exception (e.g. the datetime `TypeError`, a DB lock, or an I/O error), the loop crashed. The daemon's `_run_loop()` in `daemon.py` either terminated or aborted the iteration, leaving running jobs unreconciled.

### 2.4 Relative `.pem` Private Key Paths Across Worktrees
In `synlynk/daemon.py:_refresh_github_tokens`, `apps_dir` is located via `_daemon_state_path("github_apps")`.
However, `app_config["private_key_path"]` inside `architect.json` stores a relative path (e.g. `.synlynk/github_apps/architect.pem`).
When `github_app_auth.refresh_installation_token()` passes `app_config["private_key_path"]` directly to `_sign_jwt()`, `openssl` executes:
`openssl dgst -sha256 -sign .synlynk/github_apps/architect.pem`
If the current working directory is a worktree (`/worktrees/job-xxxx`), openssl cannot open `.synlynk/github_apps/architect.pem` because that directory does not exist in the worktree.

### 2.5 Remaining TOCTOU Race During Zombie Cleanup

The remediation must also protect the destructive cleanup itself. A reconciler
can observe a dead PID and a clean worktree, then pause while GitHub-write
verification, filesystem inspection, or cost accounting runs. During that
pause, a second reconciler (or the sentinel timeout path) can settle the row,
or a wrapper can finish writing the exit marker. The first reconciler would
then continue with its stale observation and remove a worktree that no longer
belongs to the terminal outcome it inspected. The current ordering of
"update terminal status, then remove worktree" prevents one narrow lost-update
case, but the terminal update is not an ownership claim: it does not identify
which observation is authorized to perform the subsequent deletion.

This is a classic check-then-act race across processes; an in-process lock is
insufficient because daemon and sentinel paths may use different processes.

---

## 3. Remediation Architecture & Design

### 3.1 Fix Job Exit Classification and Preserve Worktree Logs
1. **Persistent Log Directory:** In `synlynk/dispatch.py`, compute `logs_dir` using the repo common directory:
   `main_logs_dir = os.path.join(_repo_common_dir(), ".synlynk", "logs")`
   Workers redirect stdout/stderr to `main_logs_dir/{job_id}.log` and write exit code to `main_logs_dir/{job_id}.log.exit`. The logs are located outside the disposable worktree.
2. **Log Preservation on Reap:** In `synlynk/jobs.py:_reap_zombie_worktree`, before calling `git worktree remove` or `rmtree`, check if `log_path` exists within the worktree. If so, copy `log_path` and `log_path + ".exit"` to the central `.synlynk/logs` directory before deleting the worktree.
3. **Correct Exit Resolution Sequence:**
   In `_reconcile_daemon_jobs`:
   - Never classify an exited job as `killed_zombie` before inspecting `{log_path}.exit`!
   - If `{log_path}.exit` exists, parse the exit code. If the exit code is 0, the job completed cleanly. If the exit code is non-zero (e.g. 1 or 127), the job failed with that exit code.
   - Only consider a job a true `zombie` if:
     - The PID is dead,
     - AND no exit file `{log_path}.exit` exists,
     - AND no waitpid status was captured,
     - AND there is no git activity or completed receipt.
   - Distinguish exit outcomes cleanly:
     - `done` (exit code 0).
     - `failed` (exit code > 0 or specific error).
     - `permission_denied` (log signature match).
     - `timed_out` (supervisor or stall-killer timeout).
     - `killed_zombie` (dead PID, no exit marker, no output, unreconciled).

### 3.2 Timezone-Aware Datetime Normalization in `gh_verify.py` & `jobs.py`
1. Introduce a strict timezone normalizer `_to_utc_dt(val)` in `synlynk/gh_verify.py`:
   - If `val` is a string, parse via `_parse_iso8601(val)`.
   - If `val` is a datetime, ensure `val.tzinfo` is not None (replace with UTC or local wall-clock if naive), then convert via `.astimezone(timezone.utc)`.
2. Defensive comparison:
   - When evaluating `entry_dt < since_dt` and `created < since_dt`, ensure both operands are UTC-aware.
   - Guard comparisons with `try...except (TypeError, ValueError)` so an unexpected timestamp format treats the comparison safely rather than raising an unhandled exception.
3. In `_apply_gh_write_verification`:
   - Wrap the call to `gh_write_verified` in `try...except Exception as exc:`: log a warning and return `(status, "unknown")` instead of letting an exception escape to the reconciler loop.

### 3.3 Reconciler Loop Exception Isolation
In `synlynk/jobs.py:_reconcile_daemon_jobs`:
- Wrap the body of each job iteration in a `try...except Exception as exc:` block:
```python
for (...) in rows:
    try:
        # Reconcile single job
    except Exception as exc:
        print(f"  ⚠ exception reconciling job {job_id}: {exc}", file=sys.stderr)
        traceback.print_exc()
        continue
```
- A failure on one job cannot terminate reconciliation for the remaining jobs or crash the daemon loop.

### 3.4 Absolute `.pem` Private Key Resolution
1. In `synlynk/github_app_auth.py`:
   - Implement `_resolve_private_key_path(private_key_path: str, apps_dir: Optional[str] = None) -> str`:
     - If `os.path.isabs(private_key_path)` and exists: return it.
     - If `apps_dir` is provided and `os.path.exists(os.path.join(apps_dir, os.path.basename(private_key_path)))`: return that absolute path.
     - If `os.path.exists(_daemon_state_path("github_apps", os.path.basename(private_key_path)))`: return that absolute path.
     - If `os.path.exists(os.path.abspath(private_key_path))`: return `os.path.abspath(private_key_path)`.
   - In `refresh_installation_token`, resolve `app_config["private_key_path"]` to an absolute path before passing to `_mint_installation_token`.
   - In `_sign_jwt`, call `_resolve_private_key_path` if the provided path is not absolute or doesn't exist relative to CWD.

---

## 4. Acceptance Criteria & Verification

1. **No Erroneous Zombie Classification:** Dispatched design-only and review jobs that exit cleanly (or with standard exit codes) are correctly recorded as `done` or `failed` rather than `killed_zombie`.
2. **Preserved Worker Logs:** Dispatched worker logs (`{job_id}.log` and `{job_id}.log.exit`) exist in `.synlynk/logs/` and survive worktree cleanup/reaping.
3. **Timestamp Normalization & Robustness:** `gh_verify.py` and `jobs.py` survive comparisons between naive and aware timestamps, None values, and malformed strings without throwing `TypeError`.
4. **App Auth Path Independence:** GitHub App token refresh functions identically whether CWD is the repo root, a linked worktree, or a subdirectory.
5. **Reconciler Resilience:** An injected exception in one job row does not prevent subsequent jobs in the same batch from being reconciled.
6. **Zero Bypass:** No Sentinel gates bypassed; no fallback to personal host credentials.

## 5. Race-Safe Cleanup Extension

Add a nullable `terminal_claim_token` (and, optionally, a claim timestamp) to
`daemon_jobs`, with an idempotent migration for existing databases. After
observing a dead PID, atomically claim the row with SQLite:

```sql
UPDATE daemon_jobs
SET terminal_claim_token=?
WHERE job_id=? AND status='running' AND terminal_claim_token IS NULL
```

Continue only when exactly one row changed. The token identifies the generation
of this observation; it must not be inferred from `job_id` or PID because PIDs
can be reused. Re-read the exit marker, PID liveness, and git state after
acquiring the claim. If new evidence says the worker completed, abandon the
claim and never remove the worktree.

Before removal, atomically transition to the terminal state only when
`job_id`, `status='running'`, and `terminal_claim_token=?` all match. If that
update affects zero rows, the lease was lost (for example, the sentinel won),
so skip `_reap_zombie_worktree`. Keep the token until cleanup completes, or
record a separate `cleanup_complete` flag; stale claims can be reclaimed after
a bounded lease timeout using a fresh token and evidence scan.

The invariant is: **only the process holding the claim token for the same
running-row generation may delete the worktree**. Add a two-reconciler
regression test that settles the row between the initial scan and cleanup, and
assert both that the terminal winner is preserved and that the worktree remains
intact.
