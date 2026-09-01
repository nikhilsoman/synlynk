# Daemon Re-exec Fork-Safety Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Execution routing (project CLAUDE.md — Default Agent Role):** Claude is PM/review/deploy only on this project. Whoever executes this plan (a subagent-driven-development controller or executing-plans session) must dispatch each implementation task via `synlynk dispatch` to Codex/Grok/Agy — Claude must never write the code changes in this plan directly. Claude's role here is limited to: writing this plan, reviewing dispatched PRs, and merging.

**Goal:** Eliminate the macOS ObjC fork-safety crash (#1263) by replacing `synlynk daemon`/`synlynk watch`'s raw `os.fork()` double-fork daemonization with a `subprocess.Popen`-based re-exec, and fix the resulting unblocked bug (#1264) where the GitHub App token cache writer ignores the worktree-aware `apps_dir` path.

**Architecture:** A new shared helper `_daemonize_via_reexec()` in `synlynk/daemon.py` spawns a brand-new detached Python interpreter process (`subprocess.Popen([sys.executable, "-c", ...], start_new_session=True)`) running one of two new module-level entry points (`_watch_daemon_child_main`, `_synlynk_daemon_child_main`). `WatchDaemon.start()` and `SynlynkDaemon.start()` shrink to a guard check plus one call to this helper — no `os.fork()` anywhere in the codebase. Separately, `refresh_installation_token()` in `synlynk/github_app_auth.py` gains an `apps_dir` parameter so the daemon's already-worktree-aware directory gets threaded all the way to the token-cache write path.

**Tech Stack:** Python 3 stdlib only (`subprocess`, `sys`, `os`) — no new dependencies. Existing test stack: `pytest`, `monkeypatch`, `tmp_path`.

---

## Spec

Full approved design: `docs/superpowers/specs/2026-08-29-daemon-reexec-fork-safety-fix-design.md` (committed `dbd90b3`). Read it if any task below is ambiguous — this plan implements it task-for-task and does not deviate.

## Files

- **Modify:** `synlynk/daemon.py` — remove `os.fork()` double-fork daemonization; add `_daemonize_via_reexec()`, `_watch_daemon_child_main()`, `_synlynk_daemon_child_main()`; rewrite `WatchDaemon.start()` and `SynlynkDaemon.start()`.
- **Modify:** `synlynk/github_app_auth.py` — add `apps_dir` parameter to `refresh_installation_token()`.
- **Modify:** `tests/test_daemon_token_refresh.py` — replace the 3 existing tests that mock `os.fork`/`os.setsid`/`os.dup2` directly (they test a code path that no longer exists) with tests against the new `subprocess.Popen`-based mechanism; add new tests for the helper and the two child entry points.
- **Modify:** `tests/test_github_app_auth.py` — add a test proving `refresh_installation_token(..., apps_dir=...)` writes under the given directory instead of the CWD-relative default.

---

### Task 1: `_daemonize_via_reexec()` helper

**Files:**
- Modify: `synlynk/daemon.py:59-61` (insert after `_daemon_state_path`, before `class WatchDaemon`)
- Test: `tests/test_daemon_token_refresh.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_daemon_token_refresh.py`:

```python
def test_daemonize_via_reexec_spawns_detached_subprocess(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import synlynk.daemon as daemon_mod

    captured = {}

    class FakePopen:
        def __init__(self, args, **kwargs):
            captured["args"] = args
            captured["kwargs"] = kwargs

    monkeypatch.setattr(daemon_mod.subprocess, "Popen", FakePopen)

    logfile = str(tmp_path / "test.log")
    daemon_mod._daemonize_via_reexec("synlynk.daemon._watch_daemon_child_main", logfile)

    assert captured["args"] == [
        daemon_mod.sys.executable,
        "-c",
        "from synlynk.daemon import _watch_daemon_child_main; _watch_daemon_child_main()",
    ]
    assert captured["kwargs"]["start_new_session"] is True
    assert captured["kwargs"]["close_fds"] is True
    assert captured["kwargs"]["stdin"] == daemon_mod.subprocess.DEVNULL
    assert captured["kwargs"]["stderr"] == daemon_mod.subprocess.STDOUT
    assert captured["kwargs"]["env"]["_SYNLYNK_DAEMON_CHILD"] == "1"
    assert os.path.exists(logfile)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_daemon_token_refresh.py::test_daemonize_via_reexec_spawns_detached_subprocess -v`
Expected: FAIL with `AttributeError: module 'synlynk.daemon' has no attribute '_daemonize_via_reexec'`

- [ ] **Step 3: Write minimal implementation**

In `synlynk/daemon.py`, insert immediately after `_daemon_state_path` (after line 60, before `class WatchDaemon:` on line 63):

```python
def _daemonize_via_reexec(entry_point: str, logfile: str) -> None:
    """Spawns a detached child process running the given module-level entry point.

    entry_point: dotted path to a zero-arg function, e.g.
    "synlynk.daemon._synlynk_daemon_child_main". The child signals itself via
    _SYNLYNK_DAEMON_CHILD=1 in its environment (defensive; the -c invocation
    itself is the only way this code path is ever reached).
    """
    module_path, func_name = entry_point.rsplit(".", 1)
    code = f"from {module_path} import {func_name}; {func_name}()"
    log = open(logfile, "a")
    env = {**os.environ, "_SYNLYNK_DAEMON_CHILD": "1"}
    subprocess.Popen(
        [sys.executable, "-c", code],
        stdin=subprocess.DEVNULL,
        stdout=log,
        stderr=subprocess.STDOUT,
        start_new_session=True,
        close_fds=True,
        env=env,
    )
    log.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_daemon_token_refresh.py::test_daemonize_via_reexec_spawns_detached_subprocess -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add synlynk/daemon.py tests/test_daemon_token_refresh.py
git commit -m "feat: add re-exec daemonization helper"
```

---

### Task 2: `WatchDaemon` re-exec migration

**Files:**
- Modify: `synlynk/daemon.py:75-101` (`WatchDaemon.start()`)
- Modify: `synlynk/daemon.py:227` region (insert `_watch_daemon_child_main()` right before `def _make_daemon_handler`)
- Modify: `tests/test_daemon_token_refresh.py:404-436` (delete `test_watch_daemon_start_defers_refresh_until_post_fork_run_loop` — tests a code path that no longer exists)
- Test: `tests/test_daemon_token_refresh.py`

- [ ] **Step 1: Delete the obsolete fork-based test**

Remove this entire test from `tests/test_daemon_token_refresh.py` (currently lines 404-436):

```python
def test_watch_daemon_start_defers_refresh_until_post_fork_run_loop(tmp_path, monkeypatch):
    ...
```

It asserts `os.fork` is called twice by `WatchDaemon.start()`. After this task, `start()` never calls `os.fork()`, so the assertion becomes meaningless (and would silently pass with `fork_calls == []` failing `len(fork_calls) == 2` — i.e. it would correctly fail, but for the wrong reason: it's testing removed behavior, not the new mechanism). Delete it; Steps 2-5 below add its replacements.

- [ ] **Step 2: Write the failing tests (replacement + new entry-point coverage)**

Append to `tests/test_daemon_token_refresh.py`:

```python
def test_watch_daemon_start_spawns_detached_child_and_returns_immediately(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()

    import synlynk.daemon as daemon_mod

    monkeypatch.setattr(daemon_mod.WatchDaemon, "_is_running", lambda self: False)

    captured = {}

    class FakePopen:
        def __init__(self, args, **kwargs):
            captured["args"] = args
            captured["kwargs"] = kwargs

    monkeypatch.setattr(daemon_mod.subprocess, "Popen", FakePopen)

    daemon_mod.WatchDaemon().start()

    assert captured["args"] == [
        daemon_mod.sys.executable,
        "-c",
        "from synlynk.daemon import _watch_daemon_child_main; _watch_daemon_child_main()",
    ]


def test_watch_daemon_child_main_writes_pidfile_then_runs_loop(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()

    import synlynk.daemon as daemon_mod

    call_order = []
    monkeypatch.setattr(
        daemon_mod,
        "_pkg",
        lambda name, default=None: (
            (lambda state: call_order.append(f"set_state:{state}"))
            if name == "set_state" else default
        ),
    )
    monkeypatch.setattr(daemon_mod.WatchDaemon, "_run_loop", lambda self: call_order.append("run_loop"))
    monkeypatch.setattr(os, "getpid", lambda: 12345)

    daemon_mod._watch_daemon_child_main()

    pidfile = tmp_path / ".synlynk" / "watch.pid"
    assert pidfile.read_text() == "12345"
    assert call_order == ["set_state:watching", "run_loop"]
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_daemon_token_refresh.py -k "watch_daemon_start_spawns or watch_daemon_child_main" -v`
Expected: FAIL — `test_watch_daemon_start_spawns_detached_child_and_returns_immediately` fails because `start()` still forks (no `Popen` call captured, `captured` stays `{}`, `KeyError` on `captured["args"]`); `test_watch_daemon_child_main_writes_pidfile_then_runs_loop` fails with `AttributeError: module 'synlynk.daemon' has no attribute '_watch_daemon_child_main'`.

- [ ] **Step 4: Write minimal implementation**

Replace `WatchDaemon.start()` in `synlynk/daemon.py` (currently lines 75-101):

```python
    def start(self) -> None:
        if self._is_running():
            print("  synlynk watch is already running.")
            return
        if os.path.exists(self.pidfile):
            os.remove(self.pidfile)
        _daemonize_via_reexec("synlynk.daemon._watch_daemon_child_main", self.logfile)
        print("  ● synlynk watch started.")
```

Then, immediately before `def _make_daemon_handler(daemon_instance):` (currently line 227, right after the end of the `WatchDaemon` class), insert:

```python
def _watch_daemon_child_main() -> None:
    d = WatchDaemon()
    with open(d.pidfile, "w") as f:
        f.write(str(os.getpid()))
    _pkg("set_state")("watching")
    d._run_loop()


```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_daemon_token_refresh.py -v`
Expected: All PASS (including the still-present token-refresh tests from before this plan — none of them touch `WatchDaemon.start()`'s internals, only `_refresh_github_tokens()`/`_run_loop()` directly, so they're unaffected by this change).

- [ ] **Step 6: Commit**

```bash
git add synlynk/daemon.py tests/test_daemon_token_refresh.py
git commit -m "fix: daemonize WatchDaemon via re-exec instead of os.fork (#1263)"
```

---

### Task 3: `SynlynkDaemon` re-exec migration

**Files:**
- Modify: `synlynk/daemon.py:732-764` (`SynlynkDaemon.start()`)
- Modify: `synlynk/daemon.py:862` region (insert `_synlynk_daemon_child_main()` right before `def cmd_relay_start`)
- Modify: `tests/test_daemon_token_refresh.py:355-402` (delete `test_synlynk_daemon_start_does_not_refresh_in_foreground` and `test_synlynk_daemon_start_defers_refresh_until_post_fork_run_loop` — both test a code path that no longer exists)
- Test: `tests/test_daemon_token_refresh.py`

- [ ] **Step 1: Delete the two obsolete fork-based tests**

Remove both of these from `tests/test_daemon_token_refresh.py` (currently lines 355-402):

```python
def test_synlynk_daemon_start_does_not_refresh_in_foreground(tmp_path, monkeypatch):
    ...

def test_synlynk_daemon_start_defers_refresh_until_post_fork_run_loop(tmp_path, monkeypatch):
    ...
```

Same reasoning as Task 2 Step 1 — they assert on `os.fork` call counts and stub `os.setsid`/`os.dup2`, none of which `SynlynkDaemon.start()` will call after this task.

- [ ] **Step 2: Write the failing tests (replacements + new entry-point coverage)**

Append to `tests/test_daemon_token_refresh.py`:

```python
def test_synlynk_daemon_start_spawns_detached_child_and_returns_immediately(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()

    import synlynk.daemon as daemon_mod

    monkeypatch.setattr(daemon_mod.SynlynkDaemon, "_is_running", lambda self: False)

    captured = {}

    class FakePopen:
        def __init__(self, args, **kwargs):
            captured["args"] = args
            captured["kwargs"] = kwargs

    monkeypatch.setattr(daemon_mod.subprocess, "Popen", FakePopen)

    daemon_mod.SynlynkDaemon().start()

    assert captured["args"] == [
        daemon_mod.sys.executable,
        "-c",
        "from synlynk.daemon import _synlynk_daemon_child_main; _synlynk_daemon_child_main()",
    ]


def test_synlynk_daemon_child_main_writes_pidfile_and_start_file_then_runs_loop(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()

    import synlynk.daemon as daemon_mod

    call_order = []
    monkeypatch.setattr(daemon_mod.SynlynkDaemon, "_run_loop", lambda self: call_order.append("run_loop"))
    monkeypatch.setattr(os, "getpid", lambda: 54321)

    daemon_mod._synlynk_daemon_child_main()

    pidfile = tmp_path / ".synlynk" / "daemon.pid"
    start_file = tmp_path / ".synlynk" / "daemon.start"
    assert pidfile.read_text() == "54321"
    assert start_file.exists()
    assert call_order == ["run_loop"]
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_daemon_token_refresh.py -k "synlynk_daemon_start_spawns or synlynk_daemon_child_main" -v`
Expected: FAIL — first test fails on `KeyError: 'args'` (start still forks, no Popen call captured); second fails with `AttributeError: module 'synlynk.daemon' has no attribute '_synlynk_daemon_child_main'`.

- [ ] **Step 4: Write minimal implementation**

Replace `SynlynkDaemon.start()` in `synlynk/daemon.py` (currently lines 732-764):

```python
    def start(self) -> None:
        if self._is_running():
            print("  synlynk daemon is already running.")
            return
        watch_pid = _daemon_state_path("watch.pid")
        if os.path.exists(watch_pid):
            print("  ⚠ synlynk watch is also running — both will poll project-docs/.")
        if os.path.exists(self.pidfile):
            os.remove(self.pidfile)
        _daemonize_via_reexec("synlynk.daemon._synlynk_daemon_child_main", self.logfile)
        print("  ● synlynk daemon started.")
```

Then, immediately before `def cmd_relay_start(port: int = None) -> None:` (currently line 863, right after the end of the `SynlynkDaemon` class), insert:

```python
def _synlynk_daemon_child_main() -> None:
    d = SynlynkDaemon()
    with open(d.pidfile, "w") as f:
        f.write(str(os.getpid()))
    start_time = time.time()
    d._start_time = start_time
    start_file = d.pidfile.replace(".pid", ".start")
    with open(start_file, "w") as f:
        f.write(str(start_time))
    d._run_loop()


```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_daemon_token_refresh.py -v`
Expected: All PASS.

- [ ] **Step 6: Commit**

```bash
git add synlynk/daemon.py tests/test_daemon_token_refresh.py
git commit -m "fix: daemonize SynlynkDaemon via re-exec instead of os.fork (#1263)"
```

---

### Task 4: Full existing daemon test suite sanity check

**Files:**
- None modified — verification-only task, run before moving to the #1264 fix.

- [ ] **Step 1: Run the full daemon + github_app_auth test files**

Run: `pytest tests/test_daemon_token_refresh.py tests/test_github_app_auth.py -v`
Expected: All PASS, 0 failures. This confirms Tasks 1-3 didn't regress any of the pre-existing token-refresh/run_loop tests (`test_synlynk_daemon_run_loop_refreshes_tokens_on_interval`, `test_watch_daemon_run_loop_refreshes_tokens_before_first_sleep`, etc.) — none of those call `start()` or `os.fork`, so they should be untouched, but confirm directly rather than assuming.

- [ ] **Step 2: Grep for any remaining `os.fork` references in daemon.py**

Run: `grep -n "os.fork\|os\.setsid\|hasattr(os, \"fork\")" synlynk/daemon.py`
Expected: No output (empty). If anything prints, one of Tasks 2-3's replacements is incomplete — go back and fix it before continuing.

No commit for this task (verification only, nothing to stage).

---

### Task 5: `refresh_installation_token()` accepts `apps_dir`

**Files:**
- Modify: `synlynk/github_app_auth.py:162-177`
- Test: `tests/test_github_app_auth.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_github_app_auth.py`:

```python
def test_refresh_installation_token_writes_to_explicit_apps_dir(monkeypatch, tmp_path):
    from synlynk import github_app_auth as gh_auth

    # Deliberately chdir somewhere that is NOT the apps_dir, to prove the
    # write follows apps_dir rather than the CWD-relative default.
    other_cwd = tmp_path / "unrelated_cwd"
    other_cwd.mkdir()
    monkeypatch.chdir(other_cwd)

    apps_dir = tmp_path / "worktree_common" / ".synlynk" / "github_apps"
    apps_dir.mkdir(parents=True)

    expires = time.time() + 3600
    monkeypatch.setattr(
        gh_auth,
        "_mint_installation_token",
        lambda app_id, installation_id, private_key_path: ("worktree-token", expires),
    )
    app_config = {"app_id": "1", "installation_id": "2", "private_key_path": "unused.pem"}

    gh_auth.refresh_installation_token("qa", app_config, apps_dir=str(apps_dir))

    cache_path = apps_dir / "qa.token.json"
    assert cache_path.exists()
    data = json.loads(cache_path.read_text())
    assert data["token"] == "worktree-token"
    # Must NOT have written under the CWD-relative default path.
    assert not (other_cwd / ".synlynk").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_github_app_auth.py::test_refresh_installation_token_writes_to_explicit_apps_dir -v`
Expected: FAIL with `TypeError: refresh_installation_token() got an unexpected keyword argument 'apps_dir'`

- [ ] **Step 3: Write minimal implementation**

In `synlynk/github_app_auth.py`, replace `refresh_installation_token()` (currently lines 162-177):

```python
def refresh_installation_token(role: str, app_config: dict, apps_dir: Optional[str] = None) -> None:
    """Mint a fresh installation token for `role` and cache it to disk.

    Daemon-only: this is the only remaining caller of _mint_installation_token
    (and transitively _sign_jwt/openssl). dispatch must never call this —
    it only reads the cache via read_cached_installation_token().
    ``apps_dir``, when given, overrides the default cwd-relative lookup —
    the daemon passes its own worktree-aware directory so the cache lands
    where read_cached_installation_token() (and dispatch.py) actually look.
    """
    token, expires_at = _mint_installation_token(
        app_config["app_id"], app_config["installation_id"], app_config["private_key_path"],
    )
    cache_path = _role_token_cache_path(role, apps_dir=apps_dir)
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    with open(cache_path, "w") as f:
        json.dump({"token": token, "expires_at": expires_at}, f)
    os.chmod(cache_path, 0o600)
    _persist_token_for_redaction(role, token, expires_at)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_github_app_auth.py -v`
Expected: All PASS, including the new test and every pre-existing test in the file (the `apps_dir=None` default preserves the old CWD-relative behavior those tests rely on).

- [ ] **Step 5: Commit**

```bash
git add synlynk/github_app_auth.py tests/test_github_app_auth.py
git commit -m "fix: refresh_installation_token accepts apps_dir override (#1264)"
```

---

### Task 6: Daemon threads `apps_dir` into `refresh_installation_token()`

**Files:**
- Modify: `synlynk/daemon.py:178-201` (`_refresh_github_tokens()`)
- Test: `tests/test_daemon_token_refresh.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_daemon_token_refresh.py`:

```python
def test_refresh_github_tokens_passes_apps_dir_through_to_refresh_call(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    apps_dir = tmp_path / ".synlynk" / "github_apps"
    apps_dir.mkdir(parents=True)
    (apps_dir / "dev.json").write_text(json.dumps({
        "role": "dev", "app_id": "1", "installation_id": "10", "private_key_path": "dev.pem",
    }))

    calls = []
    import synlynk.daemon as daemon_mod
    monkeypatch.setattr(
        daemon_mod.github_app_auth,
        "refresh_installation_token",
        lambda role, app_config, apps_dir=None: calls.append((role, apps_dir)),
    )

    WatchDaemon()._refresh_github_tokens()

    assert calls == [("dev", str(apps_dir))]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_daemon_token_refresh.py::test_refresh_github_tokens_passes_apps_dir_through_to_refresh_call -v`
Expected: FAIL — `assert calls == [("dev", str(apps_dir))]` fails because the current call site doesn't pass `apps_dir`, so `calls == [("dev", None)]`.

- [ ] **Step 3: Write minimal implementation**

In `synlynk/daemon.py`, inside `_refresh_github_tokens()` (currently lines 178-201), change the call at line 196 from:

```python
                github_app_auth.refresh_installation_token(role, app_config)
```

to:

```python
                github_app_auth.refresh_installation_token(role, app_config, apps_dir=apps_dir)
```

(`apps_dir` is already computed at the top of this method, line 184: `apps_dir = _daemon_state_path("github_apps")` — no other change needed.)

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_daemon_token_refresh.py -v`
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add synlynk/daemon.py tests/test_daemon_token_refresh.py
git commit -m "fix: daemon passes worktree-aware apps_dir to refresh_installation_token (#1264)"
```

---

### Task 7: Full test suite + pre-merge manual macOS verification

**Files:**
- None modified — final verification task.

- [ ] **Step 1: Run the full test suite**

Run: `pytest -q`
Expected: All tests pass (baseline before this plan: 2312 passed, 2 skipped, 2 pre-existing unrelated failures — `test_cmd_probewrite_fencetrue_clobbers_sop_harness` and `test_cmd_agent_add_onboards_agent` — confirm those same 2 are the only failures, if any, and that no *new* failures were introduced by this plan's changes).

- [ ] **Step 2: Manual macOS verification (required before merge — cannot be automated in CI)**

This step must be performed by a human (or Claude during PR review) on an actual macOS machine, not by the implementing dispatch agent as part of automated task completion. Record the results in the PR description.

```bash
# Repeat start/stop 5 times, checking for zero crash entries each time.
for i in 1 2 3 4 5; do
  python3 bin/synlynk.py daemon stop >/dev/null 2>&1
  python3 bin/synlynk.py daemon start
  sleep 2
  python3 bin/synlynk.py daemon status
done

# Confirm zero OBJC/crash entries appear anywhere in the log.
grep -i "objc\|crash\|abort" .synlynk/daemon.log && echo "FAIL: crash entries found" || echo "PASS: no crash entries"

python3 bin/synlynk.py daemon stop
```

If a role's GitHub App is provisioned on this machine, additionally confirm the #1264 fix landed correctly:

```bash
# Temporarily lower the refresh interval for a fast manual check, start the
# daemon, wait past the interval, then confirm the token cache file exists
# under the worktree-aware .synlynk/github_apps/ path (not a stray
# CWD-relative one created elsewhere).
python3 bin/synlynk.py daemon start
sleep 5
ls -la .synlynk/github_apps/*.token.json
python3 bin/synlynk.py daemon stop
```

Expected: token cache file(s) present under `.synlynk/github_apps/`, none under any other CWD-relative path.

No commit for this task — it's a verification checklist, not a code change. If either check fails, treat it as a plan escape hatch: stop, do not merge, and return to Task 1-3 (crash) or Task 5-6 (token cache) with the failure evidence for further investigation per `superpowers:systematic-debugging`.

---

## Self-Review Notes

- **Spec coverage:** Every element of the approved spec's "Design" section is covered — `_daemonize_via_reexec()` (Task 1), `WatchDaemon` migration (Task 2), `SynlynkDaemon` migration (Task 3), `apps_dir` threading through both `github_app_auth.py` (Task 5) and `daemon.py`'s caller (Task 6), removal of the `if not hasattr(os, "fork")` Windows guards (folded into Tasks 2 and 3's replacement code — the new `start()` bodies never reference `hasattr(os, "fork")`), and the required manual macOS verification (Task 7).
- **Placeholder scan:** No TBD/TODO markers; every step shows complete code or exact commands.
- **Type/signature consistency:** `_daemonize_via_reexec(entry_point: str, logfile: str) -> None` used identically in Tasks 2 and 3. `refresh_installation_token(role: str, app_config: dict, apps_dir: Optional[str] = None) -> None` (Task 5) matches the call site added in Task 6 (`apps_dir=apps_dir`) and matches the existing `_role_token_cache_path(role, apps_dir=None)` signature already in the file. `_watch_daemon_child_main()` / `_synlynk_daemon_child_main()` are both zero-arg, matching how `_daemonize_via_reexec` constructs its `-c` invocation string in Task 1.
- **Existing-test breakage identified and handled:** the pre-existing `tests/test_daemon_token_refresh.py` contained 3 tests (`test_synlynk_daemon_start_does_not_refresh_in_foreground`, `test_synlynk_daemon_start_defers_refresh_until_post_fork_run_loop`, `test_watch_daemon_start_defers_refresh_until_post_fork_run_loop`) that directly mock `os.fork`/`os.setsid`/`os.dup2`/`os.getpid` and assert fork-call counts. These test the exact mechanism being removed. Tasks 2 and 3 explicitly delete them and replace with equivalent-intent tests (start spawns detached child and returns immediately; child entry point writes pidfile/start-file before running the loop) against the new mechanism.
