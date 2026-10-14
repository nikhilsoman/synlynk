# Pytest Verbosity Shim — Implementation Plan

Design: `docs/superpowers/specs/2026-10-14-pytest-verbosity-shim-design.md`
gh:#2294

## Task 1 — `synlynk/pytest_shim.py`

- New module, mirrors `synlynk/gh_shim.py`'s shape.
- `write_shim(path: str) -> None`: writes an executable wrapper script to `path`
  (mode 0o755) that:
  1. Resolves the real `pytest` by searching `$PATH` entries *after* the shim's
     own directory (same resolution approach `gh_shim.py` already uses for `gh`
     — must not recurse into itself).
  2. Filters `-v`, `--verbose`, `-vv`, `-vvv` out of `$@`.
  3. Appends `-q` if not already present in the filtered args.
  4. Execs the real `pytest` with the filtered+appended args, preserving exit
     code and stdio untouched otherwise.
- Unit tests in `tests/test_pytest_shim.py`:
  - `pytest tests/ -v -m "not local_hardware"` → resolves to running with
    `-m "not local_hardware" -q` (assert on the resulting arg set, not exact
    string equality — order independent for non-flag args).
  - `pytest tests/foo_test.py -q` (already scoped, already quiet) → passthrough,
    no duplicate `-q`.
  - `pytest -vv tests/` → single `-q`, no leftover `-v` of any count.

## Task 2 — Wire into dispatch sandbox env construction

- Audit every harness-specific subprocess env builder `dispatch.py` actually
  uses for Codex/Grok/Agy dispatched jobs (not just `_exec_child_env`, which is
  the `synlynk exec` path) — per the design doc's open question, confirm
  whether they share one function or each build env separately.
- Add a `_create_pytest_shim()` (parallel to `_create_exec_gh_shim`) and prepend
  its directory to `PATH` in every env builder identified above, the same way
  the `gh` shim dir is already prepended.
- `local` (aider) is explicitly out of scope per the design doc's non-goals.

## Task 3 — Integration regression test

- Dispatch a trivial fixture job (or extend an existing dispatch-path test) whose
  task text does not mention verbosity, have it invoke `pytest -v`, and assert
  the job's own log shows quiet output (no per-test PASS lines) and token count
  stays within the same order of magnitude as an equivalent `-q` run — a
  regression guard against a recurrence of job-55c546c8's blowup.

## Verification

- `pytest tests/test_pytest_shim.py tests/test_dispatch.py -q` (scoped — do not
  run the full suite for this verification; see the very bug this plan fixes).
- Confirm `gh_shim.py`'s existing tests still pass unmodified (no shared-state
  regressions from adding a sibling shim).

## Out of scope (see design doc's Non-goals)

- Changing dispatched harnesses' test *scope* choices.
- Transcript-resend mechanism itself.
- Mid-turn circuit-breaker blind spot (separate spec,
  `2026-10-11-cost-inflation-circuit-breaker-visibility-design.md`).
- `local` (aider) harness.
