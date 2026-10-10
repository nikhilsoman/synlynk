# TPM Daemon Autonomy Fix — Design

> Status: design proposal; no implementation included
>
> Date: 2026-10-10
>
> Scope: repair the existing `SynlynkDaemon` autonomous-tick mechanism so it
> actually runs in the background with no session needed, and fix the
> reliability bug that would re-sweep already-completed stories once it does.
> Sub-project 1 of 2 (see `docs/superpowers/specs/2026-10-10-continuous-momentum-design.md`
> for sub-project 2, the complementary session-driven self-claim layer).

## 1. Problem

The user asked: "we had earlier planned for the TPM agent role to keep this
autonomy going by invoking other agents with tasks as required... somehow
that doesn't seem to have worked... can we investigate why that didn't
work?"

Root-caused, by direct live system inspection (not guessed):

1. **`SynlynkDaemon` is not running.** `synlynk daemon status` reports "not
   running — stale pidfile cleaned." The only long-lived daemon-ish process
   on the machine is a stray `WatchDaemon` (`_watch_daemon_child_main`, a
   different, older class with no autonomous capability at all) — a
   leftover process doing only `context.md` polling, structurally incapable
   of running `_autonomous_tick()`.
2. **Even a healthy `SynlynkDaemon` would never tick autonomously**, because
   nothing — not the currently-installed launchd plist, not even what
   today's `_daemon_install_service()` code would generate if reinstalled —
   ever sets `SYNLYNK_AUTONOMOUS=1`, the sole environment variable gating
   `_autonomous_tick()` (`_synlynk_daemon_child_main`, `synlynk/daemon.py`
   ~line 1347). This is a gap in the installer code itself, not a one-off
   misconfiguration — reinstalling the service today would not fix it.
3. **Corroborating evidence:** the currently-installed
   `~/Library/LaunchAgents/com.synlynk.daemon.plist` has
   `ProgramArguments: [synlynk, daemon, start]` with no
   `EnvironmentVariables` block at all — it predates even the current
   `daemon run` + `SYNLYNK_DAEMON_WORKSPACE_ROOT`-only generator, proving
   the service was installed under older code and never reinstalled since.
4. **Already-filed, still-open reliability bug in the sweep logic itself**:
   `story-1e28248e` / gh:#1133 — `tpm_sweep.py`'s sweep pass doesn't clear a
   story's `readiness` flag when `synlynk story done` completes it, so the
   next sweep pass re-sweeps already-finished stories. This matters
   specifically *because* fixing (1) and (2) would otherwise immediately
   expose this bug in production.

A secondary, not-yet-root-caused anomaly was observed in the same session: a
burst of ~20+ alternating `claude`/`codex` jobs against `story-adhoc-*`
stories, mostly exiting 1 (`unknown_contract`), timestamped ~2h apart. This
spec does not fix that burst — it is flagged as a likely downstream symptom
of #1133 to re-check once this fix lands, not a confirmed root cause.

## 2. Relationship to the companion spec

This is deliberately scoped as a standalone, same-day fix, not bundled with
`docs/superpowers/specs/2026-10-10-continuous-momentum-design.md` (sub-project
2). That companion spec adds a session-driven, pull-based mechanism
(`synlynk story claim-next`) for when a harness session is actively running.
This spec repairs the complementary background mechanism — the daemon
ticks on its own schedule with zero sessions open. They are not
alternatives to each other (see that spec's revised §2); fixing this one
does not require or block the other, and vice versa.

## 3. Design

### 3.1 Wire `SYNLYNK_AUTONOMOUS=1` into both service installers

**File:** `synlynk/daemon.py`, `_daemon_install_service()` (~lines 730-830).

- **macOS (launchd):** the plist's `EnvironmentVariables` dict currently
  sets only `SYNLYNK_DAEMON_WORKSPACE_ROOT`. Add `SYNLYNK_AUTONOMOUS: "1"`
  to that same dict.
- **Linux (systemd):** the unit file's `Environment=` lines currently set
  only `SYNLYNK_DAEMON_WORKSPACE_ROOT=...`. Add a second
  `Environment=SYNLYNK_AUTONOMOUS=1` line, matching the existing
  single-key-per-line style already used there.
- **Scope note:** this makes autonomous mode the default for any daemon
  installed via `synlynk daemon install`. If a non-default (opt-in rather
  than opt-out) behavior is wanted instead, that is a product decision, not
  an implementation detail — flagged in §6, not assumed here. Default
  assumption for this spec: autonomous-by-default, matching the user's
  stated goal of continuous background progress.

### 3.2 Fix gh:#1133 — clear `readiness` on story completion

**Files:** `synlynk/tpm_sweep.py` (sweep pass logic) and whatever
`synlynk story done <id>` calls into (likely `synlynk/stories.py` or
equivalent — implementer confirms exact call site by tracing `story done`'s
command handler).

- Root cause (per gh:#1133's existing filing): completing a story via
  `synlynk story done <id>` updates `status` to `done` but does not clear
  `readiness` back to a non-`ready` value, so a later `run_sweep_pass()`
  pass still finds the row matching its `readiness='ready'` claim query and
  re-sweeps it.
- Fix: when `synlynk story done` sets `status='done'`, also set
  `readiness='done'` (matching the schema's existing three-value
  `readiness` enum: `draft`/`ready`/`done` — confirmed via direct query
  this session) in the same update, so completed stories stop matching any
  `readiness='ready'` claim/sweep query.
- Implementer must locate the exact current UPDATE statement for `story
  done` (grep for `status.*=.*'done'` or the function implementing the
  `story done` subcommand) before writing the fix, rather than assuming its
  shape.

### 3.3 Reinstall and verify

- Run `synlynk daemon stop` (if anything is registered), then
  `synlynk daemon install` (regenerates the plist/unit with the new env var)
  and `synlynk daemon start`.
- Verify via `synlynk daemon status` that the process is healthy and running
  as `SynlynkDaemon` (not the legacy `WatchDaemon`).
- Verify `_autonomous_tick()` is actually firing by checking for new
  `sre_heartbeat` telemetry events (`log_telemetry_event({"event":
  "sre_heartbeat", ...})`, emitted by `_autonomous_tick()` on both success
  and degraded paths) appearing at the daemon's poll interval after
  install.
- Clean up the stray orphaned `WatchDaemon` process (PID identified during
  this session's investigation) if it is still running after the new
  install — it is dead weight, not a dependency of anything.

## 4. Error handling / edge cases

- **`_autonomous_tick()` raises:** already handled — the existing
  `try/except` logs a `degraded` `sre_heartbeat` event rather than crashing
  the daemon loop. No change needed here.
- **Readiness-clear fix interacts with an in-flight claim:** out of scope
  for this spec — `claim-next` (sub-project 2) and `reclaim` safety are
  designed there; this fix only touches the `story done` → `readiness`
  transition, which is unaffected by whether a claiming mechanism exists
  yet.
- **Reinstalling while the stray `WatchDaemon` is still alive:** the two
  processes use different pidfiles (`watch.pid` vs `daemon.pid`), so
  reinstalling `SynlynkDaemon` does not require killing the stray process
  first, but it should still be cleaned up per §3.3 to stop it polluting
  `synlynk status`/process listings.

## 5. Testing

- Unit: a test asserting `_daemon_install_service()`'s generated plist
  dict (macOS path) and generated unit-file string (Linux path) both
  contain `SYNLYNK_AUTONOMOUS=1` / `SYNLYNK_AUTONOMOUS: "1"`.
- Unit: a regression test for gh:#1133 — complete a story via the `story
  done` code path against a test `state.db`, then assert its `readiness`
  column is no longer `'ready'` (matches `'done'`), and assert a subsequent
  `run_sweep_pass()` call does not re-select that story.
- Integration (manual, not CI): after reinstalling the service locally,
  confirm a new `sre_heartbeat` telemetry entry appears within one poll
  interval, and confirm `synlynk daemon status` reports the `SynlynkDaemon`
  class (not `WatchDaemon`).

## 6. Out of scope

- The `story-adhoc-*` job-burst anomaly — flagged as a likely symptom of
  #1133, not confirmed; re-check after this fix lands, file separately if
  it persists.
- Whether autonomous mode should be opt-in vs. opt-out by default long-term
  — this spec makes it the default to unblock the user's stated goal now;
  revisit if that default causes unwanted background activity once dog-fed.
- `synlynk story claim-next`, `synlynk decide --wait-approval`, and all of
  sub-project 2 — tracked entirely in the companion spec.
- Any change to `dispatch_loop()`/`story-bs8-loop` — unimplemented, tracked
  in sub-project 2's spec only.
