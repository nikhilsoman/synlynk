# Daemon CWD Health Fix — Design

**Date:** 2026-10-15
**Author:** Claude (PM session)
**Closes:** gh:#2261, gh:#2288
**Goal:** goal-bd5eaa14 / story-e73fac9e

## Problem

Both gh:#2261 and gh:#2288 root-cause to the same bug: the daemon's detached
child process never unconditionally pins its own working directory to the
canonical repo root at startup.

`_synlynk_daemon_child_main` (`synlynk/daemon.py:1359-1362`) and
`_watch_daemon_child_main` (`synlynk/daemon.py:464-467`) both do:

```python
workspace_root = os.environ.get("SYNLYNK_DAEMON_WORKSPACE_ROOT")
if workspace_root:
    os.chdir(workspace_root)
```

`os.chdir()` only runs when that env var happens to be set. In the normal
case (no env var), the child inherits whatever cwd its launching process
had. gh:#2261 shows the daemon was started from inside a nested dispatch
worktree (`worktrees/job-597c6896`); once that worktree was removed per the
Worktree Hygiene Protocol, the daemon process's cwd pointed at a deleted
directory. `_repo_common_dir()`'s except-fallback (`daemon.py:57`,
`return os.getcwd()`) then throws `FileNotFoundError` itself, because
`os.getcwd()` raises when the cwd no longer exists on disk — it doesn't
return a stale string. This kills `_refresh_github_tokens` (gh:#2288) and
the daemon's own run loop (gh:#2261) with no supervised restart, since
launchd's wrapper process already exited 0 before the detached child's
later crash.

`SYNLYNK_DAEMON_WORKSPACE_ROOT` (set manually per gh:#2288's workaround) is
the correct value — it's just not applied unconditionally.

## Fix

1. **Always resolve and chdir in both daemon child-main entry points**,
   not conditionally on the env var:
   ```python
   workspace_root = _repo_common_dir(strict=True)
   os.chdir(workspace_root)
   ```
   `strict=True` surfaces a resolution failure immediately at startup
   (current documented intent of the `strict` flag) rather than deferring
   to a fallback that can itself throw later mid-loop. The env var remains
   a valid override (`_repo_common_dir` already checks it first).

2. **Make `_repo_common_dir()`'s fallback crash-proof.** Replace the bare
   `return os.getcwd()` at `daemon.py:57` with a try/except around
   `os.getcwd()` itself, falling back to a value that cannot have been
   deleted — e.g. `os.path.expanduser("~")` is unacceptable as a repo root,
   so instead: if `os.getcwd()` raises, re-raise when `strict=True` (the
   daemon's own constructors already pass `strict=True` and are meant to
   fail loudly at startup per the existing comment), and only swallow for
   non-strict one-shot CLI callers — but even then, catch the
   `FileNotFoundError` from `os.getcwd()` and raise a clear
   `RuntimeError("cwd no longer exists; cannot resolve repo root")` instead
   of letting the cryptic stdlib `FileNotFoundError` propagate uncaught.

3. **Stop re-deriving the repo root mid-loop where an already-resolved
   value exists.** `_daemon_state_path()` (`daemon.py:62`) calls bare
   `_repo_common_dir()` (no `strict`, re-run on every call) instead of
   accepting the daemon instance's already-resolved `self.workspace_root`.
   Audit call sites of `_daemon_state_path` reachable from inside the
   running daemon's own methods and thread the resolved root through
   instead of re-deriving it from (possibly stale) process cwd each time.

4. **CLI diagnostics** (gh:#2288 fix direction #4): when
   `synlynk daemon start` fails, print the last error line from
   `.synlynk/daemon.log` directly in the CLI output instead of only
   "check daemon.log for errors."

## Non-goals

- Not fixing `_reconcile_daemon_jobs` / per-job worktree inspection logic
  itself (gh:#2288 found no `os.chdir()` there — the stale-cwd state was
  inherited from the chdir gap in (1) above, not caused by job
  reconciliation). No chdir audit needed in `jobs.py` unless the
  implementer finds one during testing.
- Not changing `SYNLYNK_DAEMON_WORKSPACE_ROOT`'s semantics — it stays a
  valid override, just no longer the *only* path that produces a safe cwd.

## Verification

- Start the daemon from a disposable worktree path, then delete that
  worktree while the daemon is running; confirm the daemon's own cwd was
  already pinned to the canonical repo root at startup (unaffected by the
  deletion) and `_refresh_github_tokens` / `_reconcile_daemon_jobs` keep
  running without crashing.
- `synlynk daemon status` reports `running` continuously across a
  worktree-deletion event that previously would have killed it.
- `synlynk daemon start` failure output includes the actual root-cause
  line, not just the generic "check daemon.log" message.
