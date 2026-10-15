# Daemon CWD Health Fix — Plan

Spec: `docs/superpowers/specs/2026-10-15-daemon-cwd-health-fix-design.md`
Story: story-e73fac9e (goal-bd5eaa14)
Closes: gh:#2261, gh:#2288

## Steps

1. In `synlynk/daemon.py`, change `_synlynk_daemon_child_main` and
   `_watch_daemon_child_main` to unconditionally call
   `os.chdir(_repo_common_dir(strict=True))` instead of only chdir'ing
   when `SYNLYNK_DAEMON_WORKSPACE_ROOT` is set. Keep the env var as a
   valid override (already handled inside `_repo_common_dir`).
2. Fix `_repo_common_dir()`'s non-strict fallback (`daemon.py:57`) to
   catch `FileNotFoundError` from `os.getcwd()` itself and raise a clear
   `RuntimeError` instead of letting it propagate as a raw stdlib
   exception; strict callers should still raise immediately on any
   resolution failure.
3. Audit `_daemon_state_path()` (`daemon.py:62`) call sites reached from
   inside a running daemon instance; where the instance already has
   `self.workspace_root` resolved, pass it through instead of calling
   bare `_repo_common_dir()` again.
4. In the CLI's `daemon start` failure path, read and print the last
   error line from `.synlynk/daemon.log` instead of the generic
   "check daemon.log for errors" message.
5. Add/update a regression test: simulate a daemon child started in a
   temp directory, delete that directory while simulating what the old
   code path would do, and assert the daemon's resolved workspace root
   (post-chdir) is unaffected.
6. Restart the daemon from the canonical repo root
   (`cd /Users/nikhilsoman/dev/synlynk && synlynk daemon start`) once the
   fix lands, and confirm `synlynk daemon status` reports healthy.
7. Run full suite (`pytest -q`) before opening the PR.

## Out of scope

See spec's Non-goals section — no `jobs.py`/`_reconcile_daemon_jobs`
chdir audit unless testing surfaces one.
