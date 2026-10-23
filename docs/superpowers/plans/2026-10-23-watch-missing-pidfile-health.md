# Watch Missing-PIDfile Health Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `synlynk watch start`, `status`, and `stop` safe and consistent when `.synlynk/watch.pid` is absent, stale, malformed, or unreadable.

**Architecture:** Add a shared health snapshot for `WatchDaemon` that classifies the PID-file condition and considers a lock-owner PID only when the lifetime lock is verifiably held. Reuse that snapshot in start/status/stop so they agree; never signal a PID based solely on lock-file text.

**Tech Stack:** Python 3.9+, `fcntl` locking, pytest, existing daemon helpers in `synlynk/daemon.py`.

**Spec:** `docs/superpowers/specs/2026-10-23-watch-missing-pidfile-health-design.md`

## Global Constraints

- Keep the change scoped to `WatchDaemon` unless a shared-helper change demonstrably requires another caller.
- Do not change state DB identity, schema, configuration, or migration behavior.
- Never signal a PID based only on stale/unverified lock-file metadata.
- Preserve starter/lifetime lock serialization and ordinary valid-PID behavior.
- Tests must use isolated temporary PID/lock paths and must not inspect or signal a host daemon.

## Review Focus

- A missing PID file while a live daemon holds the lifetime lock must not crash status or allow a duplicate start; pin with the missing-file/live-lock regression.
- A stale lock file whose recorded PID happens to be live must not be treated as a daemon or signaled; pin with an unheld-lock/live-unrelated-PID regression.
- A malformed or concurrently removed PID file must not raise or leave start/status/stop disagreeing; pin the malformed-file and read-race cases.
- A valid PID file must retain healthy behavior; retain and run the current valid/stale PID tests.
- A stale PID file with no live lock owner must be cleaned without signaling its recorded PID; pin with an `os.kill` non-call assertion.
- PID cleanup must acquire the lifetime lock and re-read before unlinking; if a concurrent start has published a PID after the health snapshot, preserve that file.

---

### Task 1: Add a trustworthy watch-health snapshot

**Files:**
- Modify: `synlynk/daemon.py` near `_daemon_lock_owner_pid()`, `_pid_is_alive()`, and `WatchDaemon._health()`
- Test: `tests/test_daemon_liveness_1572.py`

**Interfaces:**
- Consumes: `_daemon_lock_path(pidfile)`, `_daemon_lock_owner_pid(lock_path)`, `_pid_is_alive(pid)`.
- Produces: internal `_WatchHealth` tuple with `state`, `pid`, and `pidfile_state`; `WatchDaemon._health_snapshot() -> _WatchHealth`.

- [ ] **Step 1: Add failing tests for PID-file classification and lock verification**

Add these cases using `tmp_path` and monkeypatching only the probe/liveness boundary; do not touch global daemon paths:

- `test_health_snapshot_classifies_absent_pid_with_verified_lock`: assert `state == "degraded"`, `pid == owner_pid`, and `pidfile_state == "absent"`.
- `test_health_snapshot_ignores_unheld_lock_with_live_pid`: a live unrelated PID is recorded in an unheld lock file; assert `state == "stopped"` and `pid is None`.
- `test_health_snapshot_classifies_malformed_pid_without_owner`: assert `state == "zombie"` and `pidfile_state == "malformed"`.
- `test_health_snapshot_preserves_valid_live_pid`: assert `state == "running"`, `pid == os.getpid()`, and `pidfile_state == "valid"`.
- `test_daemon_lock_probe_distinguishes_held_lock_without_mutating_pid`: assert a held lock probes true, an unheld lock probes false, and the diagnostic PID text is byte-identical before and after both probes.

- [ ] **Step 2: Run the new tests and confirm they fail for the current implementation**

Run: `pytest -q tests/test_daemon_liveness_1572.py -k 'health_snapshot or health_classifies'`
Expected: FAIL because `_health_snapshot()` and a non-mutating held-lock probe do not exist.

- [ ] **Step 3: Implement lock verification and `_health_snapshot()`**

Add `_daemon_lock_is_held(lock_path: str) -> bool` using a non-blocking exclusive `flock` probe on an already-existing read-only file descriptor; it must not create, truncate, or rewrite the diagnostic PID. Release the probe lock immediately if acquired. Define `_WatchHealth` as a `NamedTuple` with `state: str`, `pid: Optional[int]`, and `pidfile_state: str`; use only the state values `running`, `stopped`, `zombie`, `degraded` and PID-file values `absent`, `valid`, `stale`, `malformed`, `unreadable`. Resolve health in this order: valid live PID file; verified held lifetime lock with a live recorded owner (degraded if PID file unusable); otherwise stopped/zombie according to whether stale PID metadata exists. Treat file read/parse races as unusable metadata, not uncaught errors. Keep `_health()` backward-compatible by mapping snapshot state `degraded` to `running`; status consumes `_health_snapshot()` directly for the more precise display state. This preserves existing `_is_running()` and `SynlynkDaemon` behavior for a lock-backed live process.

- [ ] **Step 4: Run the new tests and the existing health tests**

Run: `pytest -q tests/test_daemon_liveness_1572.py tests/test_control_plane_daemon_health.py`
Expected: PASS; existing callers of `_health()` continue receiving the same string values for existing states.

- [ ] **Step 5: Commit the health-snapshot change**

```bash
git add synlynk/daemon.py tests/test_daemon_liveness_1572.py
git commit -m "fix: verify watch lock ownership in health checks"
```

### Task 2: Align watch start, status, and stop with the snapshot

**Files:**
- Modify: `synlynk/daemon.py` in `WatchDaemon.start()`, `WatchDaemon.status()`, and `WatchDaemon.stop()`
- Test: `tests/test_daemon_liveness_1572.py`

**Interfaces:**
- Consumes: `WatchDaemon._health_snapshot() -> _WatchHealth` from Task 1.
- Produces: consistent command behavior using the snapshot without changing command syntax.

- [ ] **Step 1: Add failing command-level regressions**

Add the following command-level tests and assertions:

- `test_watch_status_reports_degraded_without_pidfile`: assert no exception, output contains `degraded` and the verified owner PID.
- `test_watch_start_does_not_spawn_for_verified_lock_owner`: assert output contains `already running` and the fake spawn function was not called.
- `test_watch_stop_signals_verified_lock_owner_without_pidfile`: assert `os.kill` receives exactly `(owner_pid, 15)`.
- `test_watch_status_ignores_unheld_lock_metadata_for_live_pid`: with an unheld lock containing a live unrelated PID and no PID file, assert output contains `watch stopped` and not `watch running`.
- `test_watch_start_proceeds_for_unheld_lock_metadata`: assert the fake spawn function is called once.
- `test_watch_stop_does_not_signal_unheld_lock_metadata`: assert `os.kill` is not called with the recorded PID.
- `test_watch_status_preserves_pidfile_published_after_health_snapshot`: inject a start after the status snapshot and assert the newly published PID file remains.
- `test_watch_stop_preserves_pidfile_published_after_health_snapshot`: inject a start after the stop snapshot and assert the newly published PID file remains.
- `test_watch_status_handles_pidfile_disappearing_before_read`: simulate `FileNotFoundError` between existence check and read; assert no exception.
- `test_watch_start_cleans_malformed_pid_without_owner`: assert no exception, the stale file is removed, and one child spawn is attempted.
- `test_watch_stop_cleans_malformed_pid_without_signaling`: assert no exception, the stale file is removed, and `os.kill` is not called.
- `test_watch_status_reports_valid_live_pid`: assert output says running and includes the PID-file PID.
- `test_watch_start_does_not_spawn_for_valid_live_pid`: assert output says already running and fake spawn is not called.
- `test_watch_stop_signals_valid_live_pid`: mock `os.kill` and assert the valid PID is sent signal 15.

- [ ] **Step 2: Run the command-level tests and confirm they fail**

Run: `pytest -q tests/test_daemon_liveness_1572.py -k 'missing_pid or verified_lock_owner or unheld_lock_metadata or malformed_pid or pidfile_disappears'`
Expected: FAIL because status opens an absent PID file and stop treats absence as proof of stopped state.

- [ ] **Step 3: Update start/status/stop to consume the health snapshot**

`start()` must refuse a second spawn for `running` or `degraded` backed by a verified lock owner, while preserving its starter-lock serialization. `status()` must print the PID from the snapshot when available and never unconditionally open the PID file. `stop()` may signal only a live PID selected from a valid PID file or verified live lock-owner evidence; when neither exists, remove stale PID metadata only after acquiring the lifetime lock and re-reading the path. If a concurrent start owns that lock, leave the PID file and state untouched. Catch filesystem races at the read/cleanup boundary.

- [ ] **Step 4: Run focused daemon regressions**

Run: `pytest -q tests/test_daemon_liveness_1572.py tests/test_daemon_start_false_failure_2333.py tests/test_control_plane_daemon_health.py`
Expected: PASS; all missing, valid, stale, malformed, and lock-owner scenarios pass without host-process side effects.

- [ ] **Step 5: Run adjacent daemon integration tests and inspect the diff**

Run: `pytest -q tests/test_daemon_token_refresh.py && git diff --check`
Expected: PASS; no whitespace errors and no changed files outside the stated scope.

- [ ] **Step 6: Commit the command behavior and regression tests**

```bash
git add synlynk/daemon.py tests/test_daemon_liveness_1572.py
git commit -m "fix: make watch controls tolerate missing pidfiles"
```

## Final verification

Run the full focused set from Tasks 1–2 once more, inspect `git status --short`, and record exact results in the PR and parent issue #2458. Obtain non-author review before closing #2537 or tagging v0.25.2.
