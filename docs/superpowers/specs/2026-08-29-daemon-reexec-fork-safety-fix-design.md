# Daemon Re-exec Fork-Safety Fix — Design

## Problem

`synlynk daemon start` reports success but the daemon process crashes immediately on macOS. Confirmed via `superpowers:systematic-debugging`:

- `.synlynk/daemon.log` shows repeated crashes for PIDs 42938 and 78075, both terminated `objc[PID]: +[NSNumber initialize] may have been in progress in another thread when fork() was called. ... Crashing instead.`
- These two PIDs exactly match two of macOS's own crash reports generated the same day (`~/Library/Logs/DiagnosticReports/Python-2026-08-29-211137.ips`, `...-220848.ips`), both terminated `namespace: OBJC`, `EXC_CRASH`/`SIGABRT` — first-party confirmation, not just a reported symptom.
- Root cause: `WatchDaemon.start()` (`synlynk/daemon.py:84`/`:89`) and `SynlynkDaemon.start()` (`synlynk/daemon.py:744`/`:749`) both daemonize via the classic double-fork idiom using raw `os.fork()`. On macOS, if any Apple system framework has lazily spun up a background thread in the process before `fork()` is called (common once a Python process has touched networking/SSL machinery), a fork mid-initialization of an Objective-C class causes the runtime to abort the child rather than risk continuing with corrupted state (`objc_initializeAfterForkError`). This is a structural hazard of raw `fork()`-without-immediate-`exec()` on modern macOS, not something specific to synlynk's code.
- Consequence: because the crash happens at `fork()` itself, the child process never reaches `_run_loop()` → `_refresh_github_tokens()` (`daemon.py:210`/`:196`). The daemon has never completed a single token-refresh cycle on this machine.

This connects directly to a second, related bug (synlynk#1264): `--requires-gh-write` dispatch fails with "no role-scoped GitHub App token available" even when the token cache is supposedly fresh. #1264's own code-level bug is real (`refresh_installation_token()` at `synlynk/github_app_auth.py:162` calls `_role_token_cache_path(role)` at `:172` without the `apps_dir` override the function supports, so it writes to a CWD-relative path instead of the worktree-aware path `synlynk/dispatch.py:245`'s `_resolve_github_apps_dir()` reads from) — but it is currently unreachable and unverifiable in practice, because the daemon crashes before ever executing that code path.

**Out of scope:** A separate, unrelated crash pattern was found during this investigation — 5 of 7 crash reports generated the same day are `SIGSEGV` in Apple's `Network.framework` (`nw_path_evaluator_evaluate` etc.), all with `parentPid: 1` and no `synlynk` string anywhere in the report. No evidence ties this to synlynk. Not addressed by this design; may warrant its own investigation ticket later.

## Goals

1. Eliminate the fork-safety crash class structurally, not just avoid today's specific trigger.
2. Unblock #1264's fix from ever being testable, by fixing the CWD-relative token-cache write path in the same effort.
3. Keep the change contained to daemonization mechanics — no changes to daemon polling logic, HTTP API, or job dispatch.

## Non-Goals

- Fixing the unrelated `Network.framework` `SIGSEGV` crash pattern.
- Changing `SynlynkRelay` (it runs in the foreground, no fork involved).
- Any change to token *signing* logic, GitHub API interaction, or role provisioning.

## Design

### Re-exec daemonization

Replace the double-fork pattern in both `WatchDaemon.start()` and `SynlynkDaemon.start()` with a `subprocess.Popen`-based re-exec. Instead of the parent process calling `os.fork()` and continuing execution as the (still-warm, ObjC-tainted) child, the parent spawns a **brand-new Python interpreter process** and exits. A freshly `exec`'d interpreter has no partially-initialized ObjC state to inherit from a concurrently-running background thread — the crash class is structurally impossible, not merely avoided.

**New shared helper** in `synlynk/daemon.py`:

```python
def _daemonize_via_reexec(entry_point: str, logfile: str) -> None:
    """Spawns a detached child process running the given module-level entry point.

    entry_point: dotted path to a zero-arg function, e.g. "synlynk.daemon._synlynk_daemon_child_main".
    The child signals itself via _SYNLYNK_DAEMON_CHILD=1 in its environment (defensive;
    the -c invocation itself is the only way this code path is ever reached).
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

`start_new_session=True` gives the child its own session (replacing the `os.setsid()` call in the old code) so it's fully detached from the invoking terminal. Redirection happens via `Popen`'s own `stdout`/`stderr` args (the child's fds, set up before the child process image is even loaded), replacing the old `dup2`-after-fork dance.

**New child entry points**, one per daemon class (kept separate rather than unified with an `isinstance` branch, since their post-daemonization setup already differs):

```python
def _watch_daemon_child_main() -> None:
    d = WatchDaemon()
    with open(d.pidfile, "w") as f:
        f.write(str(os.getpid()))
    _pkg("set_state")("watching")
    d._run_loop()

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

**`WatchDaemon.start()`** shrinks to:

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

**`SynlynkDaemon.start()`** shrinks equivalently, keeping its existing "watch is also running" warning check:

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

The `if not hasattr(os, "fork")` Windows guard is removed from both `start()` methods — `subprocess.Popen` with `start_new_session=True` works on Windows too (it maps to `CREATE_NEW_PROCESS_GROUP`), so the platform restriction this guard existed for no longer applies. This is a positive side effect, not a goal — no Windows-specific testing is in scope, since nothing about this change is Windows-specific to verify.

### #1264 fix: worktree-aware token cache write path

In `synlynk/github_app_auth.py`, `refresh_installation_token(role, app_config)` currently calls `_role_token_cache_path(role)` (line ~172) with no `apps_dir` argument, defaulting to a CWD-relative path. `_refresh_github_tokens()` in `daemon.py` already computes the correct worktree-aware directory as `apps_dir = _daemon_state_path("github_apps")` (`daemon.py:184`). Thread it through:

1. `refresh_installation_token(role, app_config, apps_dir=None)` — add the parameter, default `None` preserves current behavior for any other caller.
2. Inside, pass `apps_dir` through to `_role_token_cache_path(role, apps_dir=apps_dir)` (the function already supports this override per the read-side pattern in `dispatch.py:245`'s `_resolve_github_apps_dir()`).
3. `_refresh_github_tokens()` (`daemon.py:196`) passes its already-computed `apps_dir` into the call: `github_app_auth.refresh_installation_token(role, app_config, apps_dir=apps_dir)`.

This fix was previously unreachable/unverifiable because the daemon crashed before this code path ever executed. With the re-exec fix in place, this becomes testable end-to-end for the first time.

## Testing

**Automated (Linux + macOS CI, since these are pure process-lifecycle assertions, not crash-specific behavior):**
- `synlynk daemon start` produces a running process whose PID (read from the pidfile) is alive (`os.kill(pid, 0)` doesn't raise).
- `synlynk daemon stop` / `synlynk daemon status` still behave correctly against a re-exec'd child.
- A full start → stop → start cycle works (no stale pidfile / "already running" false positives).
- Same three checks for `synlynk watch start`/`stop`/`status`.
- `refresh_installation_token()` called with an explicit `apps_dir` writes the token cache file under that directory, not CWD (unit test with a temp dir, no real GitHub API call — mock the signing/HTTP calls as existing tests for this function already do).

**Manual, on this Mac, required before merge (recorded here since it cannot be automated in CI and is the actual proof the crash is fixed):**
- Run `synlynk daemon start` at least 5 times (stopping between runs), confirm zero `OBJC`/crash entries appear in `.synlynk/daemon.log` afterward.
- With a role's GitHub App provisioned, confirm the token cache file appears under the worktree-aware `.synlynk/github_apps/` path (not a stray CWD-relative one) after a token refresh — either by waiting out the real ~50min interval once, or by temporarily lowering `token_refresh_interval_seconds` for the manual test run.

## Rollout

Implementation goes through `synlynk dispatch` to Codex/Grok/Agy per this project's Default Agent Role — Claude (this session) does design and review only, not implementation. One PR covers both the re-exec fix (#1263) and the `apps_dir` threading fix (#1264), since the latter is only verifiable once the former lands and both changes are needed for a real live-reproduction test.
