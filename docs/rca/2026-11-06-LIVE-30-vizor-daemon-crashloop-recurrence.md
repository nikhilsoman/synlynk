# RCA: [LIVE-30] Vizor launchd daemon crash-loop — recurrence, architectural root cause

**Date:** 2026-11-06
**Severity:** Sev1
**Issue:** #5142 (supersedes #4376; original incident: [LIVE-16] #1794)

## Summary

The Vizor HUD daemon (`com.synlynk.vizor-daemon`) is down again with the exact symptom
LIVE-16 (2026-09-26) was supposed to have fixed permanently:
`ModuleNotFoundError: No module named 'synlynk'` under launchd, in a tight restart loop.
This is the **third confirmed occurrence** of this failure class on this machine
(LIVE-16, this recurrence, and a parallel occurrence in the dispatch subsystem fixed
yesterday by PR #5138). Per the systematic-debugging skill's rule — three or more
recurrences of the same symptom through different point-fixes means the architecture
itself is wrong, not any single patch — this RCA does not propose a fix. It documents
the mechanism precisely enough to run a `synlynk decide` panel on durable alternatives.

## Timeline

- 2026-09-25/26 — LIVE-16: daemon's plist had no `PYTHONPATH`; editable install resolved
  to a deleted worktree. Fixed by writing a resolved `PYTHONPATH` into the plist at
  `install()`-time (`_synlynk_import_root()` in `synlynk/vizor_daemon.py`).
- 2026-11-05 23:31 — PR #5138 merged (`fix: import synlynk from the dispatch worktree`,
  fixes #2442/#2483): the *same failure shape* recurs independently in the dispatch
  subsystem — `dispatch_agent`'s global launcher import resolves through an editable
  install pointing at a deleted job worktree, causing dispatched jobs to fail
  `ModuleNotFoundError` before `pr check` can even run. Fixed narrowly by having
  `dispatch_agent` pass the specific job worktree's path into `_build_subprocess_env`.
- 2026-11-06 — User reports Vizor is down. Sentinel shows a CRITICAL
  `VIZOR_DAEMON_CRASHLOOP` alert. Investigation (this RCA) finds the daemon's plist
  `PYTHONPATH` points at `/Users/nikhilsoman/dev/synlynk/.worktrees/origin-main`, a
  directory that does not exist on disk. `daemon.log` shows the identical
  `ModuleNotFoundError: No module named 'synlynk'` repeating every ~30s
  (`ThrottleInterval`).

## Root causes

1. **There is no durable, worktree-independent install of `synlynk` on this machine.**
   Checked three distinct resolution paths, all ephemeral:
   - `pipx list` → `synlynk 0.23.0.dev0` — stale, unrelated to current `VERSION` (0.27.5).
   - `pip show synlynk` → version 0.25.1, `Editable project location:
     /Users/nikhilsoman/dev/synlynk/worktrees/job-b861e7ec` — itself a disposable
     dispatch-job worktree.
   - Running the daemon's exact interpreter (`/opt/homebrew/opt/python@3.14/bin/python3.14`)
     with `cwd=/` and no `PYTHONPATH` override reproduces `ModuleNotFoundError` directly.
   Every consumer that needs to `import synlynk` from a non-worktree `cwd` (launchd,
   with `cwd=/`; a dispatched job's subprocess, with `cwd=$HOME` per that failure mode)
   has nothing stable to resolve against.

2. **LIVE-16's fix snapshots a worktree path once, at `install()`-time, and never
   revisits it.** `synlynk/vizor_daemon.py::_synlynk_import_root()`:
   ```python
   def _synlynk_import_root() -> str:
       """Directory that must be on PYTHONPATH for `python -m synlynk.vizor_daemon`.

       Launchd/systemd start with cwd `/` or `$HOME`. An editable install that
       points at a deleted worktree is invisible from those cwds, which is the
       LIVE-16 crash-loop.
       """
       import synlynk
       return str(Path(synlynk.__file__).resolve().parent.parent)
   ```
   This function's own docstring names the exact failure class it was written to
   prevent — and then prevents it only for the one worktree that happened to be
   importable the moment `install()` last ran. It bakes that path into the launchd
   plist's static `EnvironmentVariables.PYTHONPATH` (`_plist_env_xml()` /
   `_launchd_plist_contents()`), which launchd then reads unconditionally on every
   restart, forever, until `install()` runs again.

3. **The project's own Worktree Hygiene Protocol is the trigger, not an external
   accident.** `CLAUDE.md`'s Worktree Hygiene Protocol mandates deleting a worktree
   "the moment the PR that owns them lands." Whatever worktree `_synlynk_import_root()`
   captured at the last `install()` is, by design, exactly the kind of thing this
   protocol removes once its PR merges. There is no coordination between "a worktree
   is about to be deleted" and "something has that worktree's path baked into a
   long-lived daemon's environment" — the two systems are unaware of each other.

4. **`KeepAlive=true` + `ThrottleInterval=30` convert a permanent misconfiguration
   into a continuous, silent restart loop** rather than a single visible failure —
   consistent with LIVE-16's original finding, unchanged by that fix.

5. **Independent corroboration that this is systemic, not Vizor-specific:** PR #5138
   (merged the day before this recurrence) fixed the identical failure shape
   (`ModuleNotFoundError` from an editable install pointing at a deleted worktree) in
   a completely unrelated subsystem — dispatched job subprocesses — with its own
   narrow, local fix (explicitly passing the job worktree's path through
   `_build_subprocess_env`). Two independently-engineered point-fixes for the same
   underlying defect, discovered a day apart in different code paths, is the pattern
   the debugging skill calls an architectural smell, not a coincidence of two unlucky
   bugs.

## Impact

- Vizor HUD (daemon-served agent/role visualization) unavailable; same blast radius
  as LIVE-16 — the OS-supervised daemon is down, a session-level workaround can mask
  it if one happens to be running, GitHub-App-based dispatch and token refresh are
  unaffected (they don't depend on this daemon).
- Recurrence erodes confidence in "fixed" status reporting generally: LIVE-16 was
  closed as resolved, the fix shipped, and the identical symptom returned within
  ~6 weeks through the exact mechanism the fix's own docstring predicted but didn't
  prevent.

## What this RCA is NOT doing

Per the Iron Law of systematic debugging ("NO FIXES WITHOUT ROOT CAUSE INVESTIGATION
FIRST") and the 3+-recurrence rule ("STOP and question the architecture... discuss
with your human partner before attempting more fixes"), this RCA stops short of
proposing or implementing a fix. A 4th point-fix of the same shape (e.g., re-pointing
`PYTHONPATH` at whichever worktree currently exists) would only reset the clock until
the next worktree cleanup.

## Candidate directions for the decide panel

1. **Stable non-editable install.** Install `synlynk` as a real (non-editable) wheel
   into a fixed location (e.g. a dedicated venv or `pipx`-managed install built from
   a tagged release), and have the daemon/dispatch resolve against that location
   instead of whatever worktree is ambiently importable.
2. **Dynamic re-resolution, not a static snapshot.** Have the daemon (and dispatch)
   re-resolve its import root on every launch/restart rather than freezing a path at
   `install()`-time — so a stale worktree reference self-heals on the next restart
   instead of persisting until someone manually reruns `install()`.
3. **Pre-delete guard in the Worktree Hygiene Protocol.** Before a worktree is removed,
   check whether anything long-lived (an installed daemon's plist, a pip-editable
   install's `Editable project location`) currently points at it, and refuse/warn
   instead of deleting silently.

These are not mutually exclusive; (1) addresses the root cause directly, (2) and (3)
are complementary defense-in-depth. Decision to be recorded via `synlynk decide`.
