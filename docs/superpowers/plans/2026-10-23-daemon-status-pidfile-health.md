# Daemon Status Missing-PIDfile Health Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop `synlynk daemon status` from raising `FileNotFoundError` when the daemon is alive via lock-owner/port evidence but its pidfile is absent (gh:#2553), by sharing `stop()`'s existing three-tier PID resolution with `status()`.

**Architecture:** Extract `SynlynkDaemon.stop()`'s inline pidfile → lock-owner → HTTP-port-listener resolution into a new `_resolve_live_pid()` method (pure refactor, no behavior change to `stop()`). Extract `status()`'s "not running" output block into `_print_not_running()` (pure refactor). Then rewire `status()`'s "running" branch to resolve its PID the same way, falling back to `_resolve_live_pid()` when the pidfile itself is missing or unreadable, and printing one extra diagnostic line when it had to fall back.

**Tech Stack:** Python 3 stdlib, pytest. No new dependencies.

---

Approved design spec: `docs/superpowers/specs/2026-10-23-daemon-status-pidfile-health-design.md`.

### Task 1: Extract `_resolve_live_pid()` from `stop()`

**Files:**
- Modify: `synlynk/daemon.py` (`SynlynkDaemon.stop()`, currently lines 1419–1436)
- Test: `tests/test_daemon_status_pidfile_health_2553.py` (new)

- [ ] **Step 1: Write the failing tests for the not-yet-existing helper**

Create `tests/test_daemon_status_pidfile_health_2553.py`:

```python
"""Regression tests for synlynk issue #2553:
SynlynkDaemon.status() crashes with FileNotFoundError when the daemon is
alive via lock-owner or HTTP-port evidence but its pidfile is absent --
the same fingerprint #2544 fixed for WatchDaemon, now closed for
SynlynkDaemon's own _health() override.
"""

import os
import socket

import synlynk.daemon as daemon_module
from synlynk.daemon import (
    SynlynkDaemon,
    _daemon_lock_path,
    _try_acquire_daemon_lock,
    _release_daemon_lock,
)


def _isolated_http_port(daemon, monkeypatch):
    """Point daemon.HTTP_PORT at a port this test controls (LIVE-25, gh:#2329):
    the real default must never be probed by a test's port-listener fallback.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        test_port = probe.getsockname()[1]
    monkeypatch.setattr(daemon, "HTTP_PORT", test_port)
    return test_port


def test_resolve_live_pid_prefers_valid_pidfile(tmp_path):
    pidfile = str(tmp_path / "daemon.pid")
    daemon = SynlynkDaemon()
    daemon.pidfile = pidfile
    with open(pidfile, "w") as f:
        f.write(f"{os.getpid()}\n")

    assert daemon._resolve_live_pid() == os.getpid()


def test_resolve_live_pid_falls_back_to_lock_owner_when_pidfile_absent(tmp_path, monkeypatch):
    pidfile = str(tmp_path / "daemon.pid")
    daemon = SynlynkDaemon()
    daemon.pidfile = pidfile
    assert not os.path.exists(pidfile)

    monkeypatch.setattr(daemon_module, "_daemon_lock_owner_pid", lambda _path: 4242)
    monkeypatch.setattr(daemon_module, "_pid_is_alive", lambda pid: pid == 4242)

    assert daemon._resolve_live_pid() == 4242


def test_resolve_live_pid_falls_back_to_port_listener_when_no_pidfile_or_lock(tmp_path, monkeypatch):
    pidfile = str(tmp_path / "daemon.pid")
    daemon = SynlynkDaemon()
    daemon.pidfile = pidfile
    _isolated_http_port(daemon, monkeypatch)

    monkeypatch.setattr(daemon_module, "_daemon_lock_owner_pid", lambda _path: None)
    monkeypatch.setattr(daemon_module, "_pid_is_alive", lambda pid: pid == 5150)
    monkeypatch.setattr(daemon_module, "_find_pid_listening_on_port", lambda port: 5150)

    assert daemon._resolve_live_pid() == 5150


def test_resolve_live_pid_returns_none_when_no_evidence(tmp_path, monkeypatch):
    pidfile = str(tmp_path / "daemon.pid")
    daemon = SynlynkDaemon()
    daemon.pidfile = pidfile
    _isolated_http_port(daemon, monkeypatch)

    monkeypatch.setattr(daemon_module, "_daemon_lock_owner_pid", lambda _path: None)
    monkeypatch.setattr(daemon_module, "_pid_is_alive", lambda pid: False)
    monkeypatch.setattr(daemon_module, "_find_pid_listening_on_port", lambda port: None)

    assert daemon._resolve_live_pid() is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_daemon_status_pidfile_health_2553.py -v`
Expected: FAIL with `AttributeError: 'SynlynkDaemon' object has no attribute '_resolve_live_pid'` on all four tests.

- [ ] **Step 3: Add `_resolve_live_pid()` and rewire `stop()` to use it**

In `synlynk/daemon.py`, add this new method immediately before `def stop(self) -> None:` inside `SynlynkDaemon`:

```python
    def _resolve_live_pid(self) -> Optional[int]:
        """Resolve a live PID for this daemon: pidfile, then lock owner, then
        whatever process is listening on the daemon's HTTP port.

        Pidfile is the primary source of truth; the lock-owner and port-listener
        fallbacks exist because SynlynkDaemon._health() can already consider the
        daemon "running" via those signals alone when the pidfile is absent or
        stale. Shared between stop() (unchanged behavior) and status() (gh:#2553,
        which previously opened the pidfile unconditionally once _is_running()
        passed, raising FileNotFoundError on exactly this fallback path).
        """
        lock_path = _daemon_lock_path(self.pidfile)
        owner_pid = _daemon_lock_owner_pid(lock_path)
        pid = None
        if os.path.exists(self.pidfile):
            try:
                with open(self.pidfile) as f:
                    pid = int(f.read().strip())
            except (OSError, ValueError):
                pass

        if owner_pid == os.getpid():
            owner_pid = None
        target_pid = pid if (pid and _pid_is_alive(pid)) else (owner_pid if _pid_is_alive(owner_pid) else None)
        if not target_pid:
            port_pid = _find_pid_listening_on_port(self.HTTP_PORT)
            if port_pid and _pid_is_alive(port_pid) and port_pid != os.getpid():
                target_pid = port_pid
        return target_pid
```

Then replace the start of `stop()` (the block that computed `lock_path`, `owner_pid`, `pid`, and `target_pid` inline) with a call to the new helper. Change:

```python
    def stop(self) -> None:
        lock_path = _daemon_lock_path(self.pidfile)
        owner_pid = _daemon_lock_owner_pid(lock_path)
        pid = None
        if os.path.exists(self.pidfile):
            try:
                with open(self.pidfile) as f:
                    pid = int(f.read().strip())
            except (OSError, ValueError):
                pass

        if owner_pid == os.getpid():
            owner_pid = None
        target_pid = pid if (pid and _pid_is_alive(pid)) else (owner_pid if _pid_is_alive(owner_pid) else None)
        if not target_pid:
            port_pid = _find_pid_listening_on_port(self.HTTP_PORT)
            if port_pid and _pid_is_alive(port_pid) and port_pid != os.getpid():
                target_pid = port_pid
        start_file = self.pidfile.replace(".pid", ".start")
```

to:

```python
    def stop(self) -> None:
        target_pid = self._resolve_live_pid()
        lock_path = _daemon_lock_path(self.pidfile)
        start_file = self.pidfile.replace(".pid", ".start")
```

(`lock_path` must stay defined in `stop()` itself — the method's later cleanup blocks at the "not target_pid" and success paths still reference it directly.)

- [ ] **Step 4: Run the new tests to verify they pass**

Run: `pytest tests/test_daemon_status_pidfile_health_2553.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Run the existing stop() regression suite to confirm no behavior change**

Run: `pytest tests/test_control_plane_daemon_health.py tests/test_daemon_liveness_1572.py tests/test_daemon_start_lock_decoupling.py -v`
Expected: PASS, same pass count as before this change (this refactor must not alter `stop()`'s externally-visible behavior).

- [ ] **Step 6: Commit**

```bash
git add synlynk/daemon.py tests/test_daemon_status_pidfile_health_2553.py
git commit -m "refactor(daemon): extract _resolve_live_pid() from SynlynkDaemon.stop()

Pure extraction, no behavior change to stop(). Shared PID resolution
(pidfile -> lock owner -> HTTP port listener) is needed by status() too
to fix gh:#2553 in the next commit.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_012e1QQLmASW6pndrJ5xhXxJ"
```

---

### Task 2: Extract `_print_not_running()` from `status()`

**Files:**
- Modify: `synlynk/daemon.py` (`SynlynkDaemon.status()`, currently lines 1501–1521)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_daemon_status_pidfile_health_2553.py`:

```python
def test_print_not_running_cleans_stale_pidfile(tmp_path, capsys):
    pidfile = str(tmp_path / "daemon.pid")
    daemon = SynlynkDaemon()
    daemon.pidfile = pidfile
    with open(pidfile, "w") as f:
        f.write("99999999\n")  # certainly-dead PID

    daemon._print_not_running()

    output = capsys.readouterr().out
    assert "daemon not running" in output
    assert "stale pidfile cleaned" in output
    assert not os.path.exists(pidfile)
```

- [ ] **Step 2: Run it to verify it fails**

Run: `pytest tests/test_daemon_status_pidfile_health_2553.py::test_print_not_running_cleans_stale_pidfile -v`
Expected: FAIL with `AttributeError: 'SynlynkDaemon' object has no attribute '_print_not_running'`

- [ ] **Step 3: Add `_print_not_running()` and rewire `status()`'s early-return branch**

In `synlynk/daemon.py`, add this method immediately before `def status(self) -> None:`:

```python
    def _print_not_running(self) -> None:
        stale_pidfile = os.path.exists(self.pidfile)
        if stale_pidfile:
            os.remove(self.pidfile)
        print("  ✦ synlynk daemon not running")
        if stale_pidfile:
            print("    stale pidfile cleaned")
        if _daemon_service_installed():
            registration = _daemon_service_registration()
            registration_text = (
                "registered" if registration is True
                else "not registered" if registration is False
                else "registration unknown"
            )
            print(
                f"    service: installed ({registration_text}) but process is not healthy"
            )
        else:
            print("    service: not installed")
        print("    Tip: run 'synlynk daemon --install-service' to supervise and auto-start across reboots.")
```

Change the start of `status()` from:

```python
    def status(self) -> None:
        if not self._is_running():
            stale_pidfile = os.path.exists(self.pidfile)
            if os.path.exists(self.pidfile):
                os.remove(self.pidfile)
            print("  ✦ synlynk daemon not running")
            if stale_pidfile:
                print("    stale pidfile cleaned")
            if _daemon_service_installed():
                registration = _daemon_service_registration()
                registration_text = (
                    "registered" if registration is True
                    else "not registered" if registration is False
                    else "registration unknown"
                )
                print(
                    f"    service: installed ({registration_text}) but process is not healthy"
                )
            else:
                print("    service: not installed")
            print("    Tip: run 'synlynk daemon --install-service' to supervise and auto-start across reboots.")
            return
        with open(self.pidfile) as f:
```

to:

```python
    def status(self) -> None:
        if not self._is_running():
            self._print_not_running()
            return
        with open(self.pidfile) as f:
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/test_daemon_status_pidfile_health_2553.py::test_print_not_running_cleans_stale_pidfile -v`
Expected: PASS

- [ ] **Step 5: Run the broader daemon suite to confirm `status()`'s not-running branch is unchanged**

Run: `pytest tests/test_daemon_liveness_1572.py tests/test_control_plane_daemon_health.py tests/test_daemon_supervision_discovery.py -v`
Expected: PASS, same pass count as before.

- [ ] **Step 6: Commit**

```bash
git add synlynk/daemon.py tests/test_daemon_status_pidfile_health_2553.py
git commit -m "refactor(daemon): extract _print_not_running() from SynlynkDaemon.status()

Pure extraction, no behavior change. Needed so the next commit's fix
can reuse this branch's output from a second call site without
duplicating it.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_012e1QQLmASW6pndrJ5xhXxJ"
```

---

### Task 3: Fix `status()` to use `_resolve_live_pid()` instead of an unguarded open

**Files:**
- Modify: `synlynk/daemon.py` (`SynlynkDaemon.status()`, the "running" branch)

- [ ] **Step 1: Write the failing regression tests**

Append to `tests/test_daemon_status_pidfile_health_2553.py`:

```python
def test_status_crashes_reproduction_is_fixed_when_pidfile_missing_but_lock_owner_alive(
    tmp_path, monkeypatch, capsys
):
    """Reproduces gh:#2553: daemon considered running via lock-owner evidence,
    but pidfile absent. Before the fix this raised FileNotFoundError.
    """
    pidfile = str(tmp_path / "daemon.pid")
    daemon = SynlynkDaemon()
    daemon.pidfile = pidfile
    assert not os.path.exists(pidfile)

    monkeypatch.setattr(daemon_module, "_daemon_lock_owner_pid", lambda _path: 4242)
    monkeypatch.setattr(daemon_module, "_pid_is_alive", lambda pid: pid == 4242)

    daemon.status()  # must not raise

    output = capsys.readouterr().out
    assert "daemon running" in output
    assert "pid 4242" in output
    assert "pidfile missing" in output


def test_status_reports_degraded_running_via_port_listener_when_no_pidfile_or_lock(
    tmp_path, monkeypatch, capsys
):
    pidfile = str(tmp_path / "daemon.pid")
    daemon = SynlynkDaemon()
    daemon.pidfile = pidfile
    _isolated_http_port(daemon, monkeypatch)
    assert not os.path.exists(pidfile)

    monkeypatch.setattr(daemon_module, "_daemon_lock_owner_pid", lambda _path: None)
    monkeypatch.setattr(daemon_module, "_pid_is_alive", lambda pid: pid == 5150)
    monkeypatch.setattr(daemon_module, "_find_pid_listening_on_port", lambda port: 5150)

    daemon.status()  # must not raise

    output = capsys.readouterr().out
    assert "daemon running" in output
    assert "pid 5150" in output
    assert "pidfile missing" in output


def test_status_reports_not_running_when_health_and_resolver_disagree(
    tmp_path, monkeypatch, capsys
):
    """Edge case: _is_running() says running but _resolve_live_pid() finds no
    safe PID (e.g. the owner died between the two checks). Must degrade to
    "not running" rather than crash or report a bogus PID.
    """
    pidfile = str(tmp_path / "daemon.pid")
    daemon = SynlynkDaemon()
    daemon.pidfile = pidfile
    _isolated_http_port(daemon, monkeypatch)

    monkeypatch.setattr(daemon, "_is_running", lambda: True)
    monkeypatch.setattr(daemon, "_resolve_live_pid", lambda: None)

    daemon.status()  # must not raise

    output = capsys.readouterr().out
    assert "daemon not running" in output


def test_status_unchanged_for_valid_pidfile(tmp_path, capsys):
    """Regression-safety: the common healthy case must not gain the new note."""
    pidfile = str(tmp_path / "daemon.pid")
    daemon = SynlynkDaemon()
    daemon.pidfile = pidfile
    with open(pidfile, "w") as f:
        f.write(f"{os.getpid()}\n")

    daemon.status()

    output = capsys.readouterr().out
    assert "daemon running" in output
    assert f"pid {os.getpid()}" in output
    assert "pidfile missing" not in output
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_daemon_status_pidfile_health_2553.py -v`
Expected: the four new tests FAIL — the first two with `FileNotFoundError` (the actual #2553 crash), the third also with `FileNotFoundError` (resolver disagreement isn't handled yet), the fourth (valid-pidfile case) already PASSes since it doesn't touch the buggy path. That is: 3 new failures, 1 pass, alongside the earlier Task 1/2 tests still passing.

- [ ] **Step 3: Rewire `status()`'s running branch**

Change:

```python
        with open(self.pidfile) as f:
            pid = int(f.read().strip())
        start_file = self.pidfile.replace(".pid", ".start")
```

to:

```python
        pidfile_pid = None
        if os.path.exists(self.pidfile):
            try:
                with open(self.pidfile) as f:
                    pidfile_pid = int(f.read().strip())
            except (OSError, ValueError):
                pidfile_pid = None

        degraded = pidfile_pid is None
        pid = pidfile_pid if pidfile_pid is not None else self._resolve_live_pid()

        if pid is None:
            # _is_running() and _resolve_live_pid() disagree (e.g. the lock
            # owner died between the two checks): no safe PID to report.
            self._print_not_running()
            return

        start_file = self.pidfile.replace(".pid", ".start")
```

Then, at the end of the method, change:

```python
        print(f"    http: http://localhost:{self.HTTP_PORT}")
```

to:

```python
        print(f"    http: http://localhost:{self.HTTP_PORT}")
        if degraded:
            print("    (pidfile missing — reporting degraded evidence)")
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_daemon_status_pidfile_health_2553.py -v`
Expected: PASS (all tests in the file, cumulative from Tasks 1–3)

- [ ] **Step 5: Run the full daemon-related test suite**

Run: `pytest tests/test_daemon_liveness_1572.py tests/test_control_plane_daemon_health.py tests/test_daemon_supervision_discovery.py tests/test_daemon_start_lock_decoupling.py tests/test_daemon_start_false_failure_2333.py tests/test_daemon_token_refresh.py tests/test_capability_watch.py -v`
Expected: PASS, same pass counts as the pre-change baseline for every file other than the new one.

- [ ] **Step 6: Commit**

```bash
git add synlynk/daemon.py tests/test_daemon_status_pidfile_health_2553.py
git commit -m "fix(daemon): tolerate missing daemon pidfile in status() (#2553)

SynlynkDaemon.status() opened self.pidfile unconditionally once
_is_running() passed, but _health() can already report 'running' via
lock-owner or HTTP-port evidence alone when the pidfile itself is
absent -- the same fingerprint #2544 fixed for WatchDaemon. status()
now falls back to the shared _resolve_live_pid() resolution and
reports a degraded-but-non-crashing running state with a diagnostic
note, matching stop()'s existing tolerance for this case.

Fixes #2553

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_012e1QQLmASW6pndrJ5xhXxJ"
```

---

### Task 4: Full-suite verification and PR

**Files:** none (verification only)

- [ ] **Step 1: Run the full test suite**

Run: `pytest tests/ -q`
Expected: all tests pass (no regressions outside the daemon-specific files already re-run in Tasks 1–3).

- [ ] **Step 2: Run `synlynk pr check`-equivalent local sanity (no uncommitted changes, correct branch)**

Run: `git status --short && git branch --show-current`
Expected: clean working tree; branch is `fix/claude/2553-daemon-status-pidfile`.

- [ ] **Step 3: Push and open the PR**

```bash
git push -u origin fix/claude/2553-daemon-status-pidfile
```

Then open a PR (base `main`, head `fix/claude/2553-daemon-status-pidfile`) titled `fix(daemon): tolerate missing daemon pidfile in status() (#2553)`, body summarizing the spec/plan path and linking `Fixes #2553`, `docs/superpowers/specs/2026-10-23-daemon-status-pidfile-health-design.md`, and this plan file. Per the Hardened PR Review Policy, dispatch a cross-harness+model reviewer (different harness and model than whichever dispatch implements this plan) who runs `synlynk pr check` and performs the merge itself as the final step of its own dispatch.

---

## Self-Review Notes

- **Spec coverage:** every acceptance criterion in the design spec maps to a test: valid pidfile unchanged (Task 3 Step 1 test 4), missing pidfile + live lock owner (test 1), missing pidfile + live port listener (test 2), no live evidence anywhere (test 3 here, plus Task 2's `_print_not_running` test), `stop()` behavior preserved (Task 1 Step 5 regression run).
- **No placeholders:** every step shows exact before/after code and exact pytest invocations with expected outcomes.
- **Type/signature consistency:** `_resolve_live_pid(self) -> Optional[int]` and `_print_not_running(self) -> None` are used identically everywhere they're referenced across all three tasks.
- **LIVE-25 (gh:#2329) regression avoided:** every new test that can reach the port-listener fallback isolates `HTTP_PORT` to a locally-bound ephemeral port before exercising it, per the existing convention in `tests/test_control_plane_daemon_health.py`.
