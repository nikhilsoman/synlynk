# Unattended Local Ornith Lifecycle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make admitted Local pilot work start the managed foreground oMLX server and Ornith model without operator intervention, using the existing persistent oMLX API key and safe frontier fallback.

**Architecture:** Keep the existing lifecycle manager and LocalCredentialStore boundaries, but resolve the oMLX active settings path exactly like the installed wrapper and read only `auth.api_key` into memory. Replace global app-managed `omlx start/stop` with an owned foreground `omlx serve` process whose PID/start identity is verified before cleanup; preserve pilot admission, relay isolation, retry, issue reporting, and idle timeout.

**Tech Stack:** Python, pytest, macOS Keychain-independent settings access, subprocess/Popen, HTTP API client, Synlynk daemon and launch-agent supervision.

**Spec:** `docs/superpowers/specs/2026-10-21-local-unattended-lifecycle-design.md`

## Global Constraints

- Only admitted Local pilot work may start the service; keep Ornith-only, one concurrent job, 20% cohort, signed receipt, isolated Compose runner, and existing allowlisted pilot classes.
- The managed host has 24 GiB; require at least 8 GiB available, normal pressure, and no more than 256 MiB swap growth across the 10-second sample.
- Use only `Ornith-1.0-9B-4bit` and `http://127.0.0.1:8000`.
- Idle shutdown is 15 minutes and only applies to Synlynk-owned foreground oMLX processes with no active Local jobs/reservations.
- Retry a failed readiness operation once, then bind to the approved frontier fallback and report a redacted, deduplicated failure.
- Never expose the oMLX API key in repo files, logs, telemetry, command arguments, child environments, Docker config, or mounted container files.
- Unknown oMLX versions or unsupported API contracts fail closed; no explicit Local forcing, model choice, review/GitHub-write work, merges, or broader pilot.

## Review Focus

- Missing, unreadable, malformed, or absent `auth.api_key` must fail closed without printing settings contents or the key.
- The credential reader must match wrapper base-path resolution, including `~/Library/Application Support/oMLX/base-path`; a readable non-empty bootstrap overrides inherited `OMLX_BASE_PATH`, otherwise use inherited path then `~/.omlx`.
- A running operator-owned endpoint and a bind race must never be claimed or stopped by Synlynk.
- PID reuse, daemon restart, stale ownership, and lost process identity must never authorize signaling an unrelated process.
- Legacy `local credentials import` must not be required; `local doctor` must describe the active oMLX settings credential state without exposing it or depending on `OPENAI_API_KEY`.

---

### Task 1: Read the authoritative oMLX settings credential

**Files:**
- Modify: `synlynk/local_credentials.py`
- Modify: `tests/test_local_credentials.py`
- Modify: `synlynk/local_agent.py`
- Modify: tests covering local doctor and local-agent auth messages

**Interfaces:**
- Preserve `LocalCredentialStore.get() -> str` and `is_configured() -> bool` for current consumers.
- Keep `import_from_environment()` and `delete()` as independent legacy credential operations; lifecycle readiness, relay, and doctor must not use them.

- [x] **Step 1: Add failing settings-reader tests** for bootstrap-over-environment precedence, inherited `OMLX_BASE_PATH` fallback, default `~/.omlx`, absent file/key, malformed JSON, permission failure, and empty key. Assert errors are redacted and `is_configured()` is false for failures.
- [x] **Step 2: Run** `pytest tests/test_local_credentials.py -q` and confirm the new cases fail against the Keychain-only reader.
- [x] **Step 3: Implement active base-path resolution and memory-only `auth.api_key` reading** in `LocalCredentialStore`, following the installed oMLX wrapper’s precedence; do not log settings content or retain a second persistent copy.
- [x] **Step 4: Update doctor/auth guidance tests** so `local doctor` reports the active settings key state and 401 guidance does not recommend import as a lifecycle prerequisite. Preserve the legacy import command's independent behavior.
- [x] **Step 5: Run** `pytest tests/test_local_credentials.py tests/test_local_agent.py -q`; expect all credential and doctor/auth-message tests to pass.
- [x] **Step 6: Commit** as `fix: read local runtime key from oMLX settings`.

### Task 2: Own the foreground oMLX process safely

**Files:**
- Modify: `synlynk/local_lifecycle.py`
- Modify: `tests/test_local_lifecycle.py`

**Interfaces:**
- Keep `LocalLifecycleManager.ensure_ready() -> LocalRuntimeResult`, `tick()`, and `stop_managed_service()` contracts.
- Replace injectable service callbacks with foreground-process adapters that return/validate `(pid, process_start)` ownership; adapt fakes in tests.

- [x] **Step 1: Add failing process-ownership tests** for `omlx serve --host 127.0.0.1 --port 8000`, environment removal of both `OPENAI_API_KEY` and `OMLX_API_KEY`, no shell, no captured/persisted stdout or stderr, exact listener PID verification, and safe bind-race handling.
- [x] **Step 2: Add failing shutdown/reconciliation tests** proving only the recorded PID/start identity is signaled after 15 idle minutes, never call `omlx stop`, and leave operator-owned/replaced processes untouched after daemon restart or PID reuse.
- [x] **Step 3: Run** `pytest tests/test_local_lifecycle.py -q` and confirm the new tests fail against the app-managed lifecycle.
- [x] **Step 4: Implement foreground process launch and ownership state** in `LocalLifecycleManager`; persist the Synlynk supervisor launch-agent label separately from the oMLX child identity, and signal only the verified child PID.
- [x] **Step 5: Run** `pytest tests/test_local_lifecycle.py -q`; expect foreground start, bind race, idle stop, and reconciliation cases to pass.
- [x] **Step 6: Commit** as `fix: own local oMLX foreground process`.

### Task 3: Integrate credential-backed readiness and pilot fallback

**Files:**
- Modify: `synlynk/local_lifecycle.py`
- Modify: `synlynk/local_auth_proxy.py`
- Modify: daemon lifecycle integration as discovered from `tests/test_daemon_local_lifecycle.py`
- Modify: `tests/test_local_auth_proxy.py`
- Modify: `tests/test_daemon_local_lifecycle.py`
- Modify: `tests/test_local_pilot.py`

**Interfaces:**
- `OmlxClient` and `LocalAuthBroker` continue to depend on `LocalCredentialStore.get()`; key material remains in memory only.
- Preserve `prepare_local_pilot()` retry-once and frontier-fallback behavior and existing signed-receipt/pilot-ledger ordering.

- [x] **Step 1: Add failing integration tests** proving persistent-settings auth is used for readiness and relay, missing/invalid settings key retries once then falls back, no Local receipt/sample is created on failure, and deduplicated issue reporting remains redacted.
- [x] **Step 2: Run** `pytest tests/test_local_auth_proxy.py tests/test_daemon_local_lifecycle.py tests/test_local_pilot.py -q` and verify the credential/fallback cases fail before integration changes.
- [x] **Step 3: Update integration wiring** so managed startup and relay use the new reader, while a pre-running operator-owned service is only probed and never controlled.
- [x] **Step 4: Run** the same focused integration command and expect retry, fallback, relay authorization, receipt ordering, and ownership tests to pass.
- [x] **Step 5: Commit** as `fix: fail over safely when local readiness fails`.

### Task 4: Verify release-level regression and host smoke criteria

**Files:**
- Modify: tests in `tests/test_local_agent_hardware.py`, `tests/test_local_pilot_ledger.py`, and related existing lifecycle suites only where coverage requires it
- Modify: `docs/superpowers/plans/2026-10-21-local-unattended-lifecycle.md` to check off verified steps

**Interfaces:**
- No new production interfaces; this task verifies the cross-component behavior defined in Tasks 1-3.

- [x] **Step 1: Add any missing regression tests** for 24 GiB capacity truth, >=8 GiB memory gate, normal pressure, <=256 MiB swap growth, 10-second samples, existing 20% cohort and one-concurrency invariants, and `local doctor` independence from `OPENAI_API_KEY`.
- [x] **Step 2: Run focused suite** `pytest tests/test_local_credentials.py tests/test_local_agent.py tests/test_local_lifecycle.py tests/test_local_auth_proxy.py tests/test_daemon_local_lifecycle.py tests/test_local_pilot.py tests/test_local_pilot_ledger.py tests/test_local_agent_hardware.py -q`.
- [ ] **Step 3: Run required isolated host smoke checks** for installed oMLX 0.5.3 settings-path parity, foreground start, exact model inventory, relay, 15-minute idle stop, and forced fallback; do not alter operator-owned service state. **Deferred:** an operator-owned oMLX listener is already active (PID 1868) and Docker/OrbStack is stopped. Read-only authenticated `/v1/models` succeeded and showed the approved Ornith model; lifecycle start/stop, model load/unload, and Compose smoke were deliberately not run.
- [x] **Step 4: Run** `git diff --check` and record any known unrelated/full-suite failures without claiming a clean full suite unless verified.
- [x] **Step 5: Commit** remaining test-only changes as `test: verify unattended local lifecycle gates`.
