# Job Lifecycle Ground-Truth Verification — Epic Design

**Date:** 2026-07-07
**Author:** Claude (PM role)
**Tracks:** #126, #127, #128, #129 (all bugs, filed independently but sharing one root cause)
**Status:** Approved for dispatch, starting with #128

## Problem

synlynk's dispatch/job layer writes state and trusts it was written correctly, with no
independent check against reality (git, process, filesystem). Four separately-filed bugs
are symptoms of this one gap:

- **#128** — `dispatch_agent()` (`dispatch.py:636-643`) runs every job with `cwd=os.getcwd()`,
  the invoking shell's directory, shared across every concurrent dispatch. No per-job git
  worktree isolation exists.
- **#129** — `_reconcile_jobs` (`__init__.py:2716-2737`) derives job status *only* from a
  shell-written `<log_file>.exit` sentinel. If that file is missing (e.g. the process was
  SIGKILLed by the stall-killer, or externally), `exit_code` defaults to `-1` → `failed`,
  with no git-state cross-check. `_check_job_stall` (`dispatch.py:191-244`) also kills any
  job whose log file has been silent for the timeout window, regardless of whether the
  agent is legitimately just slow to flush output — a likely contributor to false failures.
- **#127** — `files_touched` is hardcoded to `[]` at both call sites (`__init__.py:2708`,
  `__init__.py:2766`). No code anywhere computes a real file diff for a job.
- **#126** — `cmd_migrate` (`db.py:505`) writes to the correct, intentionally centralized
  `DB_PATH` (`~/.synlynk/projects/<hash>/state.db`, per `_resolve_db_path()`,
  `__init__.py:553-568`) but never prints that path, so "is my data there" checks against
  a local `.synlynk/state.db` that doesn't exist. Additionally, every insert in
  `_migrate_import` (`db.py:348-462`) is wrapped in a bare `except Exception: print("skipped")`
  — a parser that throws on every row still produces a "success" banner with 0 imported rows,
  followed by `git rm --cached` and an unprompted auto-commit.

## Sequencing (dependency order — do not parallelize out of order)

1. **#128 — worktree-per-job isolation.** Prerequisite for everything else: you cannot
   trust a file diff (#127) or a completion signal (#129) when concurrent jobs' writes are
   interleaved in one shared tree.
2. **#129 — git-state-verified reconciliation.** Once each job has its own worktree,
   reconciliation can check `git log`/`git status` in that worktree as a second signal
   whenever the exit sentinel is missing or ambiguous. Also revisit `_check_job_stall`'s
   zero-bytes-for-N-minutes heuristic — false positives kill legitimately-working agents.
3. **#127 — real files_touched.** With a per-job worktree, `git diff --name-only
   <job-start-sha>..HEAD` is a two-line fix.
4. **#126 — migrate transparency + fail-loud.** Print the resolved `DB_PATH` in every
   `migrate` output line. Make the "Imported: N" banners a hard failure (non-zero exit,
   skip `git rm --cached` / auto-commit) when N is 0 for a non-empty source file.

## Scope of this dispatch

This first dispatch covers **#128 only**. Do not start #129/#127/#126 until #128 merges —
partial fixes built on the shared-cwd assumption would need to be redone.
