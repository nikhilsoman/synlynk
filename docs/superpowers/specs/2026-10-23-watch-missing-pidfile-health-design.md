# Watch Missing-PIDfile Health Design

**Status:** Approved by Nikhil on 2026-10-23 via explicit go-ahead to implement both reviewed work items.
**Issue:** [#2537](https://github.com/nikhilsoman/synlynk/issues/2537)
**Release:** v0.25.2 stability gate (#2465)

## Intent

Make `synlynk watch start`, `status`, and `stop` behave safely and consistently when the watch PID file is missing, valid, stale, or malformed, including the observed case where the lifetime lock identifies a live daemon but `watch.pid` is absent.

## Current failure

`WatchDaemon._health()` returns `running` when `watch.pid` is absent but the PID recorded in the lifetime lock is alive. `WatchDaemon.status()` then opens `watch.pid` unconditionally and raises `FileNotFoundError`. Conversely, `stop()` currently treats an absent PID file as proof that nothing is running, even though the lock can identify a live owner. A malformed/stale PID file can also disagree with a live owner.

The lifetime lock file's recorded PID is diagnostic metadata; it is not proof that the process still owns the OS lock. PID liveness alone also cannot prove process identity. The solution must avoid signaling a process based only on stale/unverified lock metadata.

## Design

1. Introduce one internal health snapshot/resolution path used by `WatchDaemon`'s status and stop logic. It should distinguish at least `running`, `stopped`, `zombie`, and `degraded` (live lock evidence but no usable PID file), and retain the best safe-to-report PID plus the PID-file condition (`absent`, `valid`, `stale`, `malformed`, or unreadable).
2. A valid live PID file remains the primary daemon identity. When it is absent or unusable, report a live lock-owner PID as degraded evidence only; status must not open the missing file, and must not claim an ordinary healthy PID-file-backed state.
3. Before using lock-owner PID evidence to claim a daemon is alive or to signal it, confirm the lifetime lock is actually held by another process using a non-blocking lock probe. A PID merely written in a stale lock file is not sufficient. Existing self-PID protections remain in force.
4. `start()` must refuse to spawn a second watch process only when a valid live PID or independently verified live lifetime-lock owner exists. Stale/malformed PID and lock metadata must not permanently block restart; preserve the existing starter/lifetime lock serialization.
5. `status()` must never raise for filesystem races or malformed/unreadable PID files. It reports running for a valid live PID; degraded with PID when a verified live lock owner is the only evidence; otherwise stopped, cleaning stale PID metadata only when safe. Cleanup must acquire the lifetime lock and re-read the PID file before unlinking; if a daemon acquired the lock or published a PID after the health snapshot, leave the PID file untouched.
6. `stop()` uses the same resolution. It may signal a valid live PID, or a PID from a lock that was verified held by that process; it must not signal based only on stale lock text. Missing/stale/malformed files with no verified live owner produce the normal stopped/cleanup result. Preserve signal and state-update behavior for existing healthy cases.

## Compatibility and scope

- No CLI command or output changes for the ordinary healthy (valid PID file) and fully stopped cases beyond more precise degraded diagnostics.
- Keep the change scoped to `WatchDaemon` unless inspection demonstrates that shared helper semantics require another caller. If `SynlynkDaemon` behavior must change, document it and add its regression cases in the same approved scope rather than silently broadening behavior.
- No schema, config, or migration changes.

## Acceptance criteria

- Missing PID file + genuinely held lifetime lock + live owner: `status` does not raise and reports degraded state with the owner PID; `start` does not double-spawn; `stop` safely terminates that owner.
- Missing PID file + stale/unheld lock metadata: status reports stopped, start can proceed, and stop does not signal the recorded PID.
- Valid live PID file: status/start/stop retain their healthy behavior.
- Stale and malformed PID files: each command behaves deterministically, does not raise, does not signal an unrelated process, and permits a later start when no verified daemon remains.
- A PID file published by a concurrent start after a status/stop health snapshot is preserved; stale cleanup must not unlink a new owner's file.
- Add regression tests for each matrix case, including a PID that is live but has no relationship to the stale lock metadata.
- Run targeted daemon tests and the relevant integration checks; obtain an independent review before marking #2537 complete or tagging v0.25.2.

## Verification approach

Use isolated `tmp_path` PID/lock paths and subprocesses or mocked lock probes so tests never inspect or signal the host's real daemon. Cover race-safe missing-file reads and verify both command output/state and whether a process was signaled. Run the existing daemon liveness, start-failure, token-refresh, and control-plane daemon health tests as appropriate.

## Approval record

Nikhil approved both reviewed work items with the explicit instruction to proceed with both implementations autonomously on 2026-10-23. The implementation plan and code are authorized under that approval.
