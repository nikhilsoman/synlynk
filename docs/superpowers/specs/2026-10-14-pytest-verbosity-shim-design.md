# Pytest Verbosity Shim — Design

gh:#2294 (9th+ recurrence of the #1531/#1738/#1827/#1850/#1880/#1937/#2219/#2237/#2240
lineage: a dispatched harness runs a broad, unscoped `pytest ... -v` invocation that
gets amplified via transcript-resend, inflating cost far beyond the task's actual
scope). Two confirmed instances in the same session on 2026-10-14:

- `job-85fb27a2` (Codex): $7.13 / 2.3M tokens, 46-file `-v` run, despite a *narrow*
  task prompt ("add unit tests for migration idempotency...") that never mentioned
  running the suite at all.
- `job-55c546c8` (Codex): $36.30 / 11.9M tokens, full-suite `-v` run on a 2-file diff,
  despite the dispatch task text *explicitly* instructing `pytest -q` on named files
  only.

## Problem

Prior mitigations in this lineage (#2240 et al.) are dispatch-prompting discipline:
tell the task text to say `pytest -q` and scope to specific files. #2294 shows this
doesn't generalize — the model can and does choose a broader, more verbose invocation
on its own initiative, with no triggering phrase in the prompt to correct, and no
code-level backstop preventing it.

## Non-goals

- Not attempting to stop a harness from running a broader test selection than asked
  — breadth of *coverage* is a legitimate judgment call a model can reasonably make.
  This spec targets verbosity (`-v`/`--verbose`), which has no coverage value and is
  the specific mechanism that balloons token cost via per-test PASS line amplification
  (per #2219's root-cause finding on transcript-resend).
- Not reworking the transcript-resend mechanism itself (harness-internal, not ours to
  change) or the mid-turn circuit-breaker blind spot (separate, already-scoped in
  `2026-10-11-cost-inflation-circuit-breaker-visibility-design.md`).
- Not touching `local` (aider) — it has no sandboxed PATH injection point today and is
  out of scope here.

## Approach: deterministic `pytest` PATH shim, same mechanism as the existing `gh` shim

`synlynk/dispatch.py` already solves an equivalent problem for `gh` via a
PATH-prepended wrapper binary — but **confirmed during plan-writing (2026-10-14) that
this mechanism is not actually wired into the dispatch path at all today.**
`_create_exec_gh_shim`/`_exec_child_env` (dispatch.py:1152-1168) is only called from
the `synlynk exec` native-session code path (dispatch.py:5104); every *dispatched*
job (Codex/Grok/Agy/local, all harnesses) goes through the single shared
`_build_subprocess_env` (dispatch.py:1183, called once at dispatch.py:4637) — which
guards `gh` by injecting a role-scoped `GH_TOKEN` env var (fail-closed if absent),
not by PATH-shimming `gh` at all.

So there is no existing dispatched-job PATH shim to mirror — this will be the first
one. That's good news for scope: `_build_subprocess_env` is the single wiring point
for every harness (not four separate per-harness builders), so this is a one-call-site
change, not a four-call-site audit.

### `synlynk/pytest_shim.py` (new)

- `write_shim(path)`: writes an executable shell script (same shape as
  `synlynk/gh_shim.py::write_shim`) that:
  1. Strips any `-v`/`--verbose`/`-vv`/`-vvv` argument from `$@` before exec'ing the
     real `pytest` found later on `PATH` (i.e. the shim directory is prepended, so
     the shim must resolve and call the next `pytest` on the original `PATH`, not
     recurse into itself — same resolution approach `gh_shim.py` already uses for
     `gh`).
  2. Appends `-q` if not already present, so a stripped `-v` doesn't silently fall
     back to pytest's default (non-quiet) verbosity.
  3. Leaves every other argument (test file/dir selection, `-k`, `-m`, `-n`, `--dist`,
     `--durations`, etc.) untouched — this is a verbosity guard only, not a scope
     guard.

### Wiring

- Add `_create_pytest_shim()` (parallel in shape to `_create_exec_gh_shim`,
  dispatch.py:1152-1159) that writes `synlynk/pytest_shim.py`'s shim via its own
  `write_shim`.
- Inside `_build_subprocess_env` (dispatch.py:1183-1206ish, specifically after
  `proc_env` is populated from the allowlist/overrides), create the shim dir and
  prepend it to `proc_env["PATH"]` the same way `_exec_child_env` prepends the `gh`
  shim dir today. `_build_subprocess_env` currently returns only `proc_env` (a
  `dict`); it will need to also return (or its caller at dispatch.py:4637 will need
  to separately manage) the `tempfile.TemporaryDirectory` handle so it isn't garbage
  collected (and the temp dir deleted) before the subprocess runs — mirror how
  `_exec_child_env`'s caller at dispatch.py:5104 holds `gh_shim_dir` and calls
  `gh_shim_dir.cleanup()` after the subprocess completes (dispatch.py:5134).
- Env allowlist (`_ENV_ALLOWLIST_BASE`, dispatch.py:1105) already passes `PATH`
  through; no new allowlist entry needed, only the prepend.

### Verification

- Unit test: shim script given `pytest tests/ -v -m "not local_hardware"` resolves to
  `pytest tests/ -m "not local_hardware" -q` (order-independent assertion on the
  resulting arg set, not exact string match).
- Unit test: shim given `pytest tests/foo_test.py -q` (already-scoped, already-quiet)
  is a no-op pass-through.
- Integration: dispatch a trivial job whose task text does not mention verbosity,
  have it run `pytest -v`, confirm the job's own log shows quiet output and the
  job's `cost_entries` token count stays in the same order of magnitude as a
  deliberately-scoped equivalent run (regression guard against a 5x-plus blowup like
  job-55c546c8's).

## Rollout

Ship behind no flag — this is a strict improvement with no legitimate use case for
`-v` inside a dispatched sandbox job (humans reviewing dispatch logs read the `-q`
summary + failure tracebacks just fine; `-v`'s per-test PASS lines are the entire
cost driver with no corresponding signal value). Apply to all four harnesses whose
dispatch path constructs a sandboxed subprocess env (Codex, Grok, Agy, local once it
gains PATH injection — out of scope for this spec per Non-goals).

## Open question for implementer (resolved 2026-10-14, see Wiring above)

~~Confirm whether Grok/Agy's dispatch paths already share `_exec_child_env`'s PATH
injection or have their own separate env-construction function~~ — confirmed: all
dispatched harnesses share the single `_build_subprocess_env` call at
dispatch.py:4637. No per-harness audit needed. The remaining implementer-facing
detail is the `TemporaryDirectory` lifetime handling noted in Wiring (don't let the
shim dir get cleaned up before the subprocess exits, and do clean it up after).
