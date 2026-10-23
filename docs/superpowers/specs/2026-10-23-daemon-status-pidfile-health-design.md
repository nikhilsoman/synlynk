# Daemon Status Missing-PIDfile Health Design

**Status:** Draft — pending Nikhil sign-off.
**Issue:** [#2553](https://github.com/nikhilsoman/synlynk/issues/2553)
**Release:** v0.25.3 readiness sweep (#2466)

## Intent

Make `synlynk daemon status` behave safely when the daemon's pidfile is absent but the daemon is otherwise verifiably alive — the same failure fingerprint as #2537, which #2544 (`6d047311`) fixed for `synlynk watch status`/`stop`/`start`, but scoped explicitly to `WatchDaemon` only. `SynlynkDaemon` overrides `_health()` and was left out of that fix on purpose (its spec: "Keep the change scoped to `WatchDaemon` unless inspection demonstrates that shared helper semantics require another caller... document it and add its regression cases in the same approved scope rather than silently broadening behavior").

## Current failure

`SynlynkDaemon._health()` (`synlynk/daemon.py:1290-1304`) already returns `"running"` when the pidfile is absent but the daemon's lifetime-lock owner PID is alive:

```python
if not os.path.exists(self.pidfile):
    return "running" if _pid_is_alive(owner_pid) else "stopped"
```

`SynlynkDaemon.status()` (`synlynk/daemon.py:1501-1524`) calls `self._is_running()` (which routes through `_health()`) to decide whether to take the "not running" branch, then falls straight into an unguarded read on the `else` side:

```python
def status(self) -> None:
    if not self._is_running():
        ...  # handles missing/stale pidfile, prints, returns
        return
    with open(self.pidfile) as f:        # line 1523 — unguarded
        pid = int(f.read().strip())
```

So a daemon considered "running" via the lock-owner path (no pidfile present) crashes `status()` with `FileNotFoundError`.

Note `SynlynkDaemon.stop()` (`synlynk/daemon.py:1419-1499`) does **not** have this bug — it already resolves the PID through a three-tier fallback (pidfile → lock owner → HTTP-port listener, `daemon.py:1420-1436`) before ever doing anything with the file, and tolerates every absence/parse failure along that chain.

## Design

1. Extract `SynlynkDaemon.stop()`'s existing PID-resolution fallback (pidfile → verified lock owner → HTTP-port listener) into a small private helper, `_resolve_live_pid() -> Optional[int]`, and have both `stop()` and `status()` call it. No behavior change for `stop()` — it is a pure refactor there.
2. `status()` keeps its existing `_is_running()` gate for the "not running" branch (unchanged — that path is correct today). On the "running" branch, replace the unguarded `open(self.pidfile)` with `_resolve_live_pid()`:
   - If the pidfile itself is present and parses, behavior and output are unchanged from today (no regression for the common, healthy case).
   - If the pidfile is absent/unreadable but `_resolve_live_pid()` still returns a PID (lock owner or port listener), print the existing running-status block using that PID, and append one line: `    (pidfile missing — reporting degraded evidence)`.
   - `_resolve_live_pid()` returning `None` here would mean `_is_running()` and the resolver disagree; treat that edge as "not running" (fall back to the same block the `not self._is_running()` branch already prints) rather than crashing, since no safe PID exists to report.
3. No change to `_health()` semantics, `stop()` externally-visible behavior, or the uptime/job-count reporting below the PID line — those already tolerate a missing `.start` file and query the DB independently of the pidfile.

## Compatibility and scope

- Scoped to `SynlynkDaemon.status()` plus the shared helper extraction from `SynlynkDaemon.stop()`. `WatchDaemon` is untouched (already fixed by #2544).
- No CLI output change for the ordinary healthy (valid pidfile) or fully-stopped cases — only the previously-crashing degraded case gains a reportable, non-crashing output.
- No schema, config, or migration changes.
- Out of scope (left for separate follow-up, not blocking this fix): auditing every other `open(self.pidfile)` call site in `daemon.py` for the same gap (the issue flags this as worth a future sweep); the CWD-relative pidfile-path question adjacent to #1228.

## Acceptance criteria

- Missing pidfile + genuinely live lock owner: `status()` does not raise; it reports running with the owner PID and the "pidfile missing" note.
- Missing pidfile + live HTTP-port listener but no live lock owner: `status()` does not raise; it reports running with the port-listener PID and the same note.
- Missing pidfile + no live owner + no live port listener: `status()` reports not-running (existing branch), unchanged.
- Valid pidfile: `status()` output is byte-identical to current behavior.
- Stale/malformed pidfile with no other live evidence: unchanged (`not self._is_running()` branch already handles this).
- Regression tests cover each case above, using isolated `tmp_path` pidfile/lock paths and mocked PID-liveness/port-listener probes — never signaling or inspecting the host's real daemon.
- Run `pytest tests/test_daemon_liveness_1572.py tests/test_synlynk.py -k daemon -q` (or the closest matching existing daemon test modules) plus the new regression tests before marking complete.

## Approval record

Pending — awaiting Nikhil's review of this spec before the implementation plan is written, per Brainstorm-First Policy.
