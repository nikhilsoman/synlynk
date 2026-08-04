# [LIVE-4] `_reconcile_jobs()` unhandled FOREIGN KEY IntegrityError crashes every stateful command

**Date:** 2026-08-04
**Severity:** Sev1 — core product broken for all stateful commands, no workaround
**Source:** [#689 (comment)](https://github.com/nikhilsoman/synlynk/issues/689#issuecomment-5175103641)
**Status:** Root cause confirmed. Fix not yet implemented (pending dispatch).

## Impact

Every `synlynk` subcommand that reaches `synlynk/cli.py` (i.e. effectively all of
them — `status`, `logs`, `dispatch`, `jobs`, ...) crashes with an uncaught
`sqlite3.IntegrityError: FOREIGN KEY constraint failed` before the requested
subcommand's own logic runs. Confirmed by the reporter on `synlynk logs --job
job-395817fd` and a `dispatch` attempt for Dialify/cc-videoreframing PR #97 — the
dispatch never created a job. There is no per-command workaround; the crash
happens ahead of argument dispatch.

## Root cause

1. `synlynk/cli.py:860` calls `_reconcile_jobs()` unconditionally at the top of
   every CLI invocation, **not** wrapped in `try/except`. (Contrast with the very
   next block, `cli.py:861-868`, which wraps an equivalent best-effort check in
   `try/except Exception: pass` specifically "never block a real command on
   this" — the established pattern in this file — but it was not applied here.)

2. `_reconcile_jobs()` (`synlynk/jobs.py:1010`) iterates jobs from
   `.synlynk/jobs.json` — a flat file with **no referential integrity to the
   SQLite `stories` table**. For any job whose status is `running` and has
   stalled, it calls `update_costs(..., story_id=job.get("story_id"), ...)`
   (`jobs.py:1046-1056`).

3. `update_costs()` (`synlynk/costs.py:633`) forwards `story_id` straight to
   `_insert_cost_row()` (`synlynk/db.py:850`), which inserts a row into
   `cost_entries`. The `cost_entries.story_id` column is declared
   `TEXT REFERENCES stories(story_id)` (`db.py:486`), and `PRAGMA
   foreign_keys=ON` is set on every connection (`synlynk/__init__.py:1058-1059`)
   — so this FK is actually enforced, not just declared.

4. **The gap:** `story_id` only gets inserted into the `stories` table via
   `resolve_or_create_story_id()`, and that function is only called when a
   caller does **not** supply `--story` explicitly
   (`synlynk/dispatch.py:1586-1588`, `1621-1627`). If a job was dispatched with
   an explicit `--story <id>` where `<id>` was never created as a real story
   (typo, a PR number, a stale/pre-migration id, a story later reset from a
   different DB), that raw string is written verbatim into the job's
   `story_id` field in `jobs.json` (`dispatch.py:1950`) with zero existence
   check against `stories`.

5. Any later `synlynk` invocation that reconciles that stalled job hits the FK
   violation on insert, and because step 1 has no exception boundary, the
   IntegrityError propagates out of `main()` and kills the process — for
   *every* command, not just ones that touch jobs/costs/stories.

This matches the reporter's description exactly: "one orphaned or inconsistent
job-cost foreign key prevents all commands from reaching their requested
operation."

## Why this wasn't caught

`tests/test_jobs.py` covers `_reconcile_jobs()` writing a normal summary and
marking a headless permission denial, but no test seeds a job with a
`story_id` absent from `stories` and asserts reconciliation survives it —
exactly the fixture gap the reporter called out in the acceptance-criteria
addition.

## Proposed mitigation (not yet implemented)

Two independent layers, per defense-in-depth — both are needed, neither alone
is sufficient:

1. **Isolate at the chokepoint (blocking, must ship first):** wrap the
   `update_costs(...)` call inside `_reconcile_jobs()`'s stall-handling branch
   (`jobs.py:1046-1056`) in `try/except sqlite3.IntegrityError`, log/surface
   the offending `job_id` + `story_id` (e.g. into `sentinel.md`, matching the
   existing sentinel pattern in this same function), and continue reconciling
   the remaining jobs instead of aborting. This alone stops the bleeding for
   *all* commands regardless of root trigger.
2. **Prevent orphaned references at the source:** in `dispatch_agent()`
   (`dispatch.py:1573`), validate/create the `stories` row for an
   explicitly-passed `--story <id>` the same way `resolve_or_create_story_id`
   does for the auto-generated path, instead of only doing that when
   `story_id` is falsy.
3. **Regression coverage:** add the fixture the reporter requested — seed a
   `jobs.json` entry with a `story_id` not present in `stories`, run
   `_reconcile_jobs()`, and assert `status`/`logs`/`dispatch` still complete
   successfully afterward.

## Next steps

- Dispatch fix to Codex (cli-plumbing/refactor role) per capability routing —
  touches `jobs.py`, `dispatch.py`, and test fixtures, no GitHub-write
  required.
- Non-authoring reviewer (Agy or Grok) required before merge per PR Review
  Discipline.
- Track as a `fix/` branch off `main`, PR references this RCA and closes out
  the acceptance-criteria addition on #689's 2026-08-04 comment.
