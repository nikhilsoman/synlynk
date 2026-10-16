# TPM Daemon Autonomy Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `SynlynkDaemon`'s background autonomous-tick loop actually run unattended, by wiring `SYNLYNK_AUTONOMOUS=1` into every service-installer code path (macOS launchd, Linux systemd, and the crontab fallback) and by adding a regression test that locks in the already-fixed gh:#1133 readiness-clear behavior.

**Architecture:** `_daemon_install_service()` in `synlynk/daemon.py` has three platform branches (launchd plist, systemd unit, crontab `@reboot` entry), each of which currently sets `SYNLYNK_DAEMON_WORKSPACE_ROOT` but never `SYNLYNK_AUTONOMOUS` — the sole env var gating `_autonomous_tick()` in `_synlynk_daemon_child_main()`. All three branches get the same one-line addition. Separately, `cmd_story_done()` in `synlynk/db.py` already sets `readiness='done'` alongside `status='done'` (confirmed via `git blame`: landed in commit `f501e1385`, 2026-08-23) — gh:#1133's root cause is already fixed in the current codebase, so this plan adds a regression test rather than a new fix, and flags the discrepancy with the spec for the user.

**Tech Stack:** Python 3 stdlib, `pytest` + `monkeypatch`/`unittest.mock`, SQLite (`state.db` via `synlynk.db._get_db()`), existing `isolated_db`/`project_dir` pytest fixtures.

---

## Finding to surface before implementation: gh:#1133 is already fixed

The approved spec (`docs/superpowers/specs/2026-10-10-tpm-daemon-autonomy-fix-design.md`, §3.2) describes fixing gh:#1133 by making `synlynk story done` set `readiness='done'` alongside `status='done'`. Reading `synlynk/db.py:3855-3885` (`cmd_story_done`) shows this exact UPDATE already exists:

```python
conn.execute(
    "UPDATE stories SET status='done', readiness='done' WHERE story_id=?",
    (story_id,),
)
```

`git blame -L 3867,3869 synlynk/db.py` attributes this line to commit `f501e1385` (2026-08-23), predating today. A repo-wide grep (`grep -rn "status='done'" synlynk/*.py`) confirms `cmd_story_done` is the only write path that ever sets a story's `status` to `done` — there is no second, unfixed code path. `mark_story_done_after_merge()` (`synlynk/db.py:3888`) calls into `cmd_story_done`, so it inherits the fix too.

**Task 2 below is therefore a regression test, not a fix** — it locks in behavior that already exists so a future regression is caught, and documents that gh:#1133 should be checked for closure. This is called out again in the Execution Handoff section.

## Scope note: three installer branches, not two

The spec's §3.1 says "both service installers" (macOS + Linux), written before the crontab fallback branch was discovered. Reading `synlynk/daemon.py`'s `_daemon_install_service()` shows a third branch for hosts with neither `launchd` nor `systemctl`, gated on `shutil.which("systemctl")` being `None`, which writes a crontab `@reboot` entry and currently sets no environment variables at all — same underlying bug as the other two. This plan fixes all three, since leaving the crontab path unfixed would silently reintroduce the exact bug this plan exists to close for any host that falls into that branch. Flagged to the user in the Execution Handoff; this is a same-root-cause, same-file, mechanical addition, not a scope expansion requiring a design decision.

---

## File Structure

- **Modify:** `synlynk/daemon.py` — `_daemon_install_service()`, three branches:
  - macOS/launchd branch: the `plist` f-string's `EnvironmentVariables` dict (currently one `<key>`/`<string>` pair).
  - Linux/systemd branch: the `unit` f-string's `Environment=` line (currently one line).
  - crontab fallback branch: the `entry = f"@reboot ..."` string (currently sets no env vars at all — needs an `env` prefix added to the crontab line itself, since crontab entries have no separate env-var block).
- **Test:** `tests/test_synlynk.py` — extend the three existing tests `test_install_service_macos`, `test_install_service_linux`, `test_install_service_crontab` (all already present, lines ~7754-7867) with assertions for the new env var.
- **Test:** `tests/test_tpm_sweep.py` — add one new regression test, `test_story_done_clears_readiness_and_sweep_does_not_resweep`, using the existing `isolated_db`/`project_dir` fixtures and `cmd_story_create`/`cmd_story_ready`/`cmd_story_done` imports.
- **No changes to `synlynk/tpm_sweep.py` or `synlynk/db.py`** — both already implement the spec's required behavior; only tests are added.

---

## Task 1: Wire `SYNLYNK_AUTONOMOUS=1` into the macOS launchd installer

**Files:**
- Modify: `synlynk/daemon.py` (macOS branch of `_daemon_install_service()`, ~line 715, the `EnvironmentVariables` dict inside the `plist` f-string)
- Test: `tests/test_synlynk.py:7754` (`test_install_service_macos`)

- [ ] **Step 1: Write the failing assertion**

Add one line to the existing `test_install_service_macos` test, right after the existing `ThrottleInterval` assertion (currently line 7789):

```python
    assert plistlib.loads(plist.encode())["EnvironmentVariables"]["SYNLYNK_AUTONOMOUS"] == "1"
```

So the tail of the test reads:

```python
    assert plistlib.loads(plist.encode())["KeepAlive"] is True
    assert plistlib.loads(plist.encode())["ThrottleInterval"] == 30
    assert plistlib.loads(plist.encode())["EnvironmentVariables"]["SYNLYNK_AUTONOMOUS"] == "1"
    assert calls[0][0] == ["launchctl", "load", "-w", str(plist_path)]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_synlynk.py::test_install_service_macos -v`
Expected: FAIL with `KeyError: 'SYNLYNK_AUTONOMOUS'`

- [ ] **Step 3: Add the env var to the plist dict**

In `synlynk/daemon.py`, find the macOS branch's plist f-string (the one containing `<key>EnvironmentVariables</key>`). It currently reads:

```python
              <key>EnvironmentVariables</key>
              <dict>
                <key>SYNLYNK_DAEMON_WORKSPACE_ROOT</key>
                <string>{workspace_root}</string>
              </dict>
```

Change it to:

```python
              <key>EnvironmentVariables</key>
              <dict>
                <key>SYNLYNK_DAEMON_WORKSPACE_ROOT</key>
                <string>{workspace_root}</string>
                <key>SYNLYNK_AUTONOMOUS</key>
                <string>1</string>
              </dict>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_synlynk.py::test_install_service_macos -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add synlynk/daemon.py tests/test_synlynk.py
git commit -m "feat(daemon): set SYNLYNK_AUTONOMOUS=1 in launchd plist installer

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0167ERumamwnBGV98mN3gXMQ"
```

---

## Task 2: Wire `SYNLYNK_AUTONOMOUS=1` into the Linux systemd installer

**Files:**
- Modify: `synlynk/daemon.py` (Linux branch of `_daemon_install_service()`, the `Environment=` line inside the `unit` f-string)
- Test: `tests/test_synlynk.py:7793` (`test_install_service_linux`)

- [ ] **Step 1: Write the failing assertion**

Add one line to `test_install_service_linux`, right after the existing `SYNLYNK_DAEMON_WORKSPACE_ROOT=` assertion (currently line 7830):

```python
    assert "Environment=SYNLYNK_AUTONOMOUS=1" in unit
```

So the tail of the test reads:

```python
    assert "ExecStart=/usr/bin/python3 -m synlynk daemon run" in unit
    assert "SYNLYNK_DAEMON_WORKSPACE_ROOT=" in unit
    assert "Environment=SYNLYNK_AUTONOMOUS=1" in unit
    assert "Restart=on-failure" in unit
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_synlynk.py::test_install_service_linux -v`
Expected: FAIL — `assert "Environment=SYNLYNK_AUTONOMOUS=1" in unit` is False

- [ ] **Step 3: Add the env var line to the systemd unit**

In `synlynk/daemon.py`, find the Linux branch's unit f-string. It currently reads:

```python
            [Service]
            Type=simple
            WorkingDirectory={workspace_root}
            ExecStart={python_path} -m synlynk daemon run
            Environment=SYNLYNK_DAEMON_WORKSPACE_ROOT={workspace_root}
            Restart=on-failure
            RestartSec=30
```

Change it to:

```python
            [Service]
            Type=simple
            WorkingDirectory={workspace_root}
            ExecStart={python_path} -m synlynk daemon run
            Environment=SYNLYNK_DAEMON_WORKSPACE_ROOT={workspace_root}
            Environment=SYNLYNK_AUTONOMOUS=1
            Restart=on-failure
            RestartSec=30
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_synlynk.py::test_install_service_linux -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add synlynk/daemon.py tests/test_synlynk.py
git commit -m "feat(daemon): set SYNLYNK_AUTONOMOUS=1 in systemd unit installer

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0167ERumamwnBGV98mN3gXMQ"
```

---

## Task 3: Wire `SYNLYNK_AUTONOMOUS=1` into the crontab fallback installer

**Files:**
- Modify: `synlynk/daemon.py` (crontab branch of `_daemon_install_service()`, the `entry = f"@reboot ..."` line)
- Test: `tests/test_synlynk.py:7836` (`test_install_service_crontab`)

A crontab entry has no separate environment-variable block — the env var must be set inline on the `@reboot` line itself (the standard crontab idiom: `@reboot VAR=value command`).

- [ ] **Step 1: Write the failing assertion**

Add one line to `test_install_service_crontab`, right after the existing `"@reboot" in crontab_contents[0]` assertion (currently line 7864):

```python
    assert "SYNLYNK_AUTONOMOUS=1" in crontab_contents[0]
```

So the tail of the test reads:

```python
    assert "@reboot" in crontab_contents[0]
    assert "SYNLYNK_AUTONOMOUS=1" in crontab_contents[0]
    assert crontab_contents[0].count("daemon start") == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_synlynk.py::test_install_service_crontab -v`
Expected: FAIL — `assert "SYNLYNK_AUTONOMOUS=1" in crontab_contents[0]` is False

- [ ] **Step 3: Add the env var to the crontab entry line**

In `synlynk/daemon.py`, find the crontab branch. It currently builds the entry as:

```python
        entry = f"@reboot {python_path} -m synlynk daemon start"
```

Change it to:

```python
        entry = f"@reboot SYNLYNK_AUTONOMOUS=1 {python_path} -m synlynk daemon start"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_synlynk.py::test_install_service_crontab -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add synlynk/daemon.py tests/test_synlynk.py
git commit -m "feat(daemon): set SYNLYNK_AUTONOMOUS=1 in crontab fallback installer

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0167ERumamwnBGV98mN3gXMQ"
```

---

## Task 4: Regression test locking in gh:#1133's existing fix

**Files:**
- Test: `tests/test_tpm_sweep.py` (new test, appended after the existing `test_ready_stories_includes_story_with_failed_job` at the end of the file)
- No source changes — `synlynk/db.py:cmd_story_done` and `synlynk/tpm_sweep.py:_ready_stories`/`run_sweep_pass` already implement the required behavior.

- [ ] **Step 1: Write the test**

Append to `tests/test_tpm_sweep.py`:

```python
def test_story_done_clears_readiness_and_sweep_does_not_resweep(isolated_db, project_dir):
    from synlynk.db import cmd_story_done

    story_id = cmd_story_create(title="finish me", story_id="story-done-1")
    cmd_story_ready(story_id)

    with patch("synlynk.tpm_sweep.check_authority") as mock_auth, \
            patch("synlynk.tpm_sweep.dispatch_agent") as mock_dispatch:
        mock_auth.return_value = MagicMock(allowed=True, requires_approval=False)
        mock_dispatch.return_value = {"id": "job-done-1", "agent": "codex"}
        run_sweep_pass()

    cmd_story_done(story_id)

    conn = synlynk._get_db()
    row = conn.execute(
        "SELECT status, readiness FROM stories WHERE story_id=?", (story_id,)
    ).fetchone()
    conn.close()
    assert row == ("done", "done")

    assert _ready_stories() == []

    with patch("synlynk.tpm_sweep.check_authority") as mock_auth, \
            patch("synlynk.tpm_sweep.dispatch_agent") as mock_dispatch:
        mock_auth.return_value = MagicMock(allowed=True, requires_approval=False)
        mock_dispatch.return_value = {"id": "job-done-2", "agent": "codex"}
        summary = run_sweep_pass()

    assert summary == {"advanced": 0, "parked": 0, "failed": 0}
    mock_dispatch.assert_not_called()
```

- [ ] **Step 2: Run test to verify it already passes**

Run: `python3 -m pytest tests/test_tpm_sweep.py::test_story_done_clears_readiness_and_sweep_does_not_resweep -v`
Expected: PASS (this confirms the plan's finding above — gh:#1133's root cause is already fixed in `cmd_story_done`; no source change is needed for this task)

If this test fails instead, STOP — it means the plan's finding is wrong and gh:#1133 is not actually fixed. Re-open systematic-debugging on `cmd_story_done`/`_ready_stories` rather than proceeding, since the spec's §3.2 fix would then still be needed.

- [ ] **Step 3: Run the full test file to confirm no regressions**

Run: `python3 -m pytest tests/test_tpm_sweep.py -v`
Expected: All tests PASS, including the new one.

- [ ] **Step 4: Commit**

```bash
git add tests/test_tpm_sweep.py
git commit -m "test(tpm_sweep): lock in gh:#1133 readiness-clear regression coverage

cmd_story_done already sets readiness='done' (commit f501e1385,
2026-08-23); this adds coverage so a future change can't silently
reintroduce the re-sweep bug.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0167ERumamwnBGV98mN3gXMQ"
```

---

## Task 5: Full test suite verification

**Files:** None modified — verification only.

- [ ] **Step 1: Run the full suite**

Run: `python3 -m pytest tests/ -q`
Expected: All tests pass (no regressions from Tasks 1-4), matching the project's pre-existing pass count plus the 4 new/extended assertions in this plan.

- [ ] **Step 2: Commit nothing further**

This task is verification-only; if the suite is clean, proceed to the manual verification task below (Task 6), which is explicitly out of CI/automated-test scope per the spec.

---

## Task 6 (manual, not committed code): Reinstall and verify the live daemon

Per spec §3.3, this is a manual operational step, not a test. Run this once Tasks 1-5 are merged and the fix is live in the installed package:

```bash
synlynk daemon stop
synlynk daemon install
synlynk daemon start
synlynk daemon status
```

Expected: `synlynk daemon status` reports the `SynlynkDaemon` class running (not `WatchDaemon`). Then, after one poll interval, check for a fresh `sre_heartbeat` telemetry event confirming `_autonomous_tick()` fired:

```bash
grep -c "sre_heartbeat" ~/.synlynk/workspaces/synlynk/telemetry.json
```

Compare the count before and after waiting one poll interval — it should increase. Finally, identify and clean up the stray orphaned `WatchDaemon` process if still running:

```bash
ps aux | grep -i watchdaemon | grep -v grep
```

If a process is found, confirm it's the legacy `WatchDaemon` (not `SynlynkDaemon`) before killing it, since the two use different pidfiles (`watch.pid` vs `daemon.pid`) and are safe to handle independently.

---

## Self-Review

**1. Spec coverage:**
- §3.1 (wire `SYNLYNK_AUTONOMOUS=1` into both installers) → Tasks 1 and 2, plus Task 3 for the crontab branch the spec didn't know about yet (flagged above, not silently expanded).
- §3.2 (fix gh:#1133) → Task 4, converted from "fix" to "regression test" per the finding that the fix already shipped in commit `f501e1385`.
- §3.3 (reinstall and verify) → Task 6, kept manual per the spec's own "manual, not CI" framing.
- §4 error handling (existing try/except around `_autonomous_tick`, reclaim-safety out of scope, stray-process pidfile independence) → no code change required, already true; Task 6's manual step addresses the stray-process cleanup directly.
- §5 testing (unit tests for both installer paths + regression test for gh:#1133 + manual integration check) → Tasks 1-4 and Task 6.
- §6 out of scope (story-adhoc-* burst, opt-in/out debate, sub-project 2, dispatch_loop()) → correctly excluded from every task above.

**2. Placeholder scan:** No TBD/TODO markers. Every step shows exact code, exact file paths, exact commands with expected output. No "similar to Task N" references — Tasks 1-3 repeat the full pattern each time since each touches a different installer branch.

**3. Type consistency:** `_ready_stories()` returns `list[dict]` with keys `story_id`/`title`/`role` consistently across Task 4's test and the existing `tpm_sweep.py` source. `run_sweep_pass()`'s return shape `{"advanced": int, "parked": int, "failed": int}` matches existing tests' assertions exactly. `cmd_story_done(story_id: str) -> None` signature matches its existing callers.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-10-10-tpm-daemon-autonomy-fix.md`.

**Scope note:** This plan is a single tightly-coupled change (3 near-identical one-line env-var additions in one function across its 3 platform branches, plus one regression test) and should be executed as one implementer task rather than split across multiple dispatches — splitting it further would add coordination overhead with no isolation benefit, since all three edits are in the same function and reviewed together naturally.

**Per this project's Default Agent Role policy** (CLAUDE.md, interim default under the 2026-10-04 empirical reassessment): actual implementation of this plan should be dispatched via `synlynk dispatch` to Agy/Grok/Codex rather than implemented directly by Claude, since Claude's default role is PM/review/deploy/brainstorm. Recommended dispatch: `synlynk dispatch --as-agent dev --task-type implement --role dev "Implement docs/superpowers/plans/2026-10-10-tpm-daemon-autonomy-fix.md task-by-task"` to Codex (per the `implement/test/refactor/cli-plumbing` lane) or Agy, with Claude reviewing per the Hardened PR Review Policy's cross-harness+model requirement.

Two execution options:

**1. Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks, fast iteration. Given the Default Agent Role policy above, this means dispatching to Agy/Grok/Codex via `synlynk dispatch`, not a generic Claude subagent.

**2. Inline Execution** — execute tasks in this session using executing-plans, batch execution with checkpoints. This would mean Claude implementing directly, which runs against the interim Default Agent Role policy unless the user wants to use this as a calibration data point for the ongoing empirical capability reassessment.

**Which approach?**
