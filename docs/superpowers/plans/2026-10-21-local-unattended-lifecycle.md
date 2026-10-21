# Unattended Local Ornith Lifecycle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Start oMLX and load the approved Ornith model automatically for admitted Local pilot jobs, then unload and stop Synlynk-managed oMLX after 15 idle minutes.

**Architecture:** Add a macOS Keychain-backed credential store, an authenticated oMLX client and host memory guard, and a host-global lifecycle supervisor integrated with the existing Synlynk daemon. A per-job authenticated relay keeps the key out of the Aider container; dispatch asks the supervisor to prepare Local only after pilot cohort admission, and falls back after one retry with deduplicated failure reporting.

**Tech Stack:** Python 3.10+, macOS Security.framework via `ctypes`, existing Synlynk daemon and dispatch code, oMLX 0.5.3 CLI/API, Docker Compose, pytest.

**Spec:** `docs/superpowers/specs/2026-10-21-local-unattended-lifecycle-design.md`

## Global Constraints

- Support unattended lifecycle automation on macOS; other platforms fail closed to frontier fallback.
- Use macOS Keychain service `com.synlynk.omlx`, account `local-runtime`; never put the key in process arguments, files, logs, telemetry, Docker configuration, or Aider's environment.
- Start/stop only a service that Synlynk observed absent and then started; leave operator-owned oMLX untouched.
- Load and unload only `Ornith-1.0-9B-4bit`, using authenticated model-specific API endpoints.
- Require at least 8 GiB available memory, normal macOS memory pressure, and no more than 256 MiB swap growth over a 10-second sample.
- Preserve Local pilot admission, the 20% cohort, one-concurrency limit, isolated execution, signed receipts, and LIVE-25 fallback binding.
- Retry lifecycle readiness once; after the second failure use the preselected frontier fallback and create/update one redacted failure ticket.
- Do not promote the Local cohort as part of this work.

## Review Focus

- **Keychain denial or locked keychain:** headless lifecycle fails closed without prompting or exposing a secret; test `test_unavailable_keychain_is_classified_without_prompt`.
- **Operator-owned service or start race:** service is never stopped or reconfigured by Synlynk; test `test_operator_owned_service_without_ornith_is_left_untouched`.
- **24 GiB memory pressure and swap growth:** model load is refused below the memory gate; test `test_memory_guard_rejects_low_available_memory_or_swap_growth`.
- **Repeated readiness failure:** exactly two attempts occur, no Local receipt/sample is created, and dispatch uses the original frontier selection; test `test_second_readiness_failure_falls_back_without_local_admission`.
- **Failure-ticket repetition or GitHub outage:** issue creation is fingerprint-deduplicated and offline reports remain in a redacted outbox; test `test_failure_report_deduplicates_and_queues_offline`.

---

## File Map

- Create `synlynk/local_credentials.py`: macOS Keychain store and narrow credential API.
- Create `synlynk/local_lifecycle.py`: host-memory snapshots, oMLX process/API adapter, lifecycle ownership, readiness retry, and idle cleanup.
- Create `synlynk/local_auth_proxy.py`: per-job HTTP-to-Unix-socket proxy boundary; adds Bearer authorization only on the host-side request to oMLX.
- Modify `synlynk/daemon.py`: tick the host-global Local lifecycle supervisor and recover persisted ownership after daemon restart.
- Modify `synlynk/local_pilot.py`: construct the isolated relay/Aider Compose environment without `OPENAI_API_KEY` in Compose variables or Aider environment.
- Modify `synlynk/local_pilot_runner.py`: use the credential-free in-network relay endpoint and ensure relay teardown on every exit path.
- Modify `synlynk/dispatch.py`: invoke lifecycle readiness after deterministic pilot admission and before model resolution, receipt, or job creation; preserve the existing frontier binding.
- Modify `synlynk/local_agent.py` and `synlynk/cli.py`: use Keychain-backed doctor auth and add `local credentials` and `local lifecycle` controls/status.
- Modify `synlynk/issue_reporter.py` (or the existing canonical issue-writing module identified during implementation): deduplicate exhausted readiness failures and retain a redacted offline outbox.
- Modify `docker/local-pilot.compose.yaml` and add `docker/local-pilot-relay.Dockerfile`: replace raw TCP `socat` passthrough with the credential-free Unix-socket relay container.
- Tests: create `tests/test_local_credentials.py`, `tests/test_local_lifecycle.py`, `tests/test_local_auth_proxy.py`; extend `tests/test_local_pilot.py`, `tests/test_local_agent.py`, `tests/test_dispatch.py`, and `tests/test_daemon.py`.
- Update `docs/reference/local-harness-pilot.md` and `docs/reference/local-harness-isolated-qualification.md` with the credential, lifecycle, ownership, and rollback procedures.

### Task 1: Keychain credential store and operator commands

**Files:**
- Create: `synlynk/local_credentials.py`
- Modify: `synlynk/cli.py`
- Modify: `synlynk/local_agent.py`
- Test: `tests/test_local_credentials.py`
- Test: `tests/test_local_agent.py`
- Test: `tests/test_cli_parser.py`

**Interfaces:**
- Produce `LocalCredentialStore.import_from_environment(environ: Mapping[str, str], *, replace: bool = False) -> None`, `get() -> str`, `delete() -> None`, and `is_configured() -> bool`.
- Use Keychain service `com.synlynk.omlx`, account `local-runtime`, accessibility `WhenUnlockedThisDeviceOnly`; missing/locked keychain raises `CredentialUnavailable` without prompting.
- Add `synlynk local credentials import|status|delete`; import requires an interactive terminal and reads only `OPENAI_API_KEY` from the caller environment.
- Update Local doctor to use the Keychain credential when no explicit test/in-process credential is provided; never print the value.

- [ ] **Step 1: Write failing Keychain adapter tests** for add, replace, retrieve, delete, missing item, locked/unavailable Keychain, and redaction.
- [ ] **Step 2: Run focused tests and confirm they fail** with the expected missing module/API errors.
- [ ] **Step 3: Implement `LocalCredentialStore`** using the macOS Security.framework API behind an injectable adapter; non-macOS calls raise a typed unsupported-platform error.
- [ ] **Step 4: Add CLI credential subcommands and doctor integration**; test that import refuses noninteractive use or missing environment value and that command output never includes the value.
- [ ] **Step 5: Run `pytest -q tests/test_local_credentials.py tests/test_local_agent.py tests/test_cli_parser.py`**; all focused tests pass.
- [ ] **Step 6: Commit** as `feat(local): store omlx credential in macos keychain`.

### Task 2: oMLX client and host-memory guard

**Files:**
- Create: `synlynk/local_lifecycle.py`
- Modify: `synlynk/local_agent.py`
- Test: `tests/test_local_lifecycle.py`
- Test: `tests/test_local_agent.py`

**Interfaces:**
- Produce `HostMemorySnapshot(physical_bytes: int, available_bytes: int, pressure: str, swap_used_bytes: int)` and `read_host_memory() -> HostMemorySnapshot`.
- Produce `OmlxClient(endpoint: str, credential_store: LocalCredentialStore)` with `list_models() -> list[str]`, `load_model(model_id: str) -> None`, and `unload_model(model_id: str) -> None`.
- Support only verified oMLX 0.5.3 initially: start/stop use `omlx start` / `omlx stop`; load/unload use authenticated `/v1/models/{model_id}/load` and `/unload`.
- All subprocesses use argument vectors and receive no credential. API calls keep the Keychain value in process memory and redact exceptions.

- [ ] **Step 1: Write failing tests** for model load/unload API paths, 401/404/507 classification, supported-version validation, no credential in subprocess arguments/environment, and memory snapshot parsing.
- [ ] **Step 2: Run `pytest -q tests/test_local_lifecycle.py`** and confirm the expected failures.
- [ ] **Step 3: Implement `OmlxClient` and typed lifecycle errors** with the exact Ornith ID allowlist and version contract.
- [ ] **Step 4: Implement the macOS memory sampler and admission gate**; require >=8 GiB available, normal memory pressure, and <=256 MiB swap growth over 10 seconds; fail closed if a metric cannot be read.
- [ ] **Step 5: Correct the hardware-tier classifier** so 24 GiB does not report as 32 GiB; preserve measured memory separately from tier labels.
- [ ] **Step 6: Run `pytest -q tests/test_local_lifecycle.py tests/test_local_agent.py`**; all focused tests pass.
- [ ] **Step 7: Commit** as `feat(local): add authenticated omlx lifecycle client`.

### Task 3: Host-global lifecycle supervisor and idle shutdown

**Files:**
- Modify: `synlynk/local_lifecycle.py`
- Modify: `synlynk/daemon.py`
- Modify: `synlynk/cli.py`
- Test: `tests/test_local_lifecycle.py`
- Test: `tests/test_daemon.py`

**Interfaces:**
- Produce `LocalLifecycleManager.ensure_ready() -> LocalRuntimeResult`, `record_job_started(job_id: str) -> None`, `record_job_finished(job_id: str) -> None`, `tick(now: float | None = None) -> None`, and `stop_managed_service() -> None`.
- Persist host-global ownership at `~/Library/Application Support/Synlynk/local-runtime.json`; record service PID/start identity, ownership generation, model, and last activity, but never credentials.
- `ensure_ready()` probes first; for an existing operator-owned endpoint it leaves service/model state unchanged. If absent, it invokes `omlx start`, records ownership only after successful start, loads Ornith through `OmlxClient`, and verifies live inventory.
- `tick()` unloads Ornith and calls `omlx stop` after 900 idle seconds only if no Local job or reservation exists and the manager can prove ownership.
- Add `synlynk local lifecycle status|stop`; stop only affects a Synlynk-owned process.

- [ ] **Step 1: Write failing tests** for start on absent endpoint, accept already-serving Ornith, leave operator-owned non-Ornith service untouched, ownership ambiguity during start race, persisted restart reconciliation, active reservation protection, and 900-second idle stop.
- [ ] **Step 2: Run the focused lifecycle and daemon tests** and confirm failure.
- [ ] **Step 3: Implement persistent host-global ownership and restart reconciliation** with PID plus process-start identity to prevent PID reuse.
- [ ] **Step 4: Integrate supervisor ticks with the existing Synlynk daemon loop**; ensure duplicate workspaces share one lock and reservation registry for port 8000.
- [ ] **Step 5: Add lifecycle status/stop CLI commands** and verify operator-owned oMLX cannot be stopped.
- [ ] **Step 6: Run `pytest -q tests/test_local_lifecycle.py tests/test_daemon.py`**; all focused tests pass.
- [ ] **Step 7: Commit** as `feat(local): supervise managed omlx idle lifecycle`.

### Task 4: Credential-free isolated authorization relay

**Files:**
- Create: `synlynk/local_auth_proxy.py`
- Create: `docker/local-pilot-relay.Dockerfile`
- Modify: `docker/local-pilot.compose.yaml`
- Modify: `synlynk/local_pilot.py`
- Modify: `synlynk/local_pilot_runner.py`
- Test: `tests/test_local_auth_proxy.py`
- Test: `tests/test_local_pilot.py`

**Interfaces:**
- Produce a host broker bound to a per-job Unix socket; it accepts only requests from the relay container and forwards to fixed `127.0.0.1:8000` with `Authorization: Bearer <key>` added in host memory.
- The relay container connects to the mounted socket and exposes the existing `http://omlx:8000/v1` shape to Aider. Aider receives no key, Docker environment, command args, or mounted credential file.
- Allow only OpenAI-compatible inference and model metadata paths required by Aider; deny arbitrary destinations and management API paths.
- Tear down the socket, relay, and transient key references on success, failure, timeout, and cancellation.

- [ ] **Step 1: Write failing proxy tests** for fixed upstream, Bearer injection, allowed paths, denied paths, no credential in container environment/config, bounded request forwarding, and socket cleanup.
- [ ] **Step 2: Run `pytest -q tests/test_local_auth_proxy.py tests/test_local_pilot.py`** and confirm failure.
- [ ] **Step 3: Implement the host Unix-socket broker** with fixed upstream, request validation, streaming-safe response forwarding, and secret-safe error handling.
- [ ] **Step 4: Replace the `socat` relay service with a minimal relay image** that forwards HTTP over the per-job socket; remove `OPENAI_API_KEY` from the Aider Compose environment.
- [ ] **Step 5: Update `build_isolated_compose_shell` and the Local runner** to create and clean up the socket/broker as part of the isolated run.
- [ ] **Step 6: Run `pytest -q tests/test_local_auth_proxy.py tests/test_local_pilot.py`**; all focused tests pass.
- [ ] **Step 7: Commit** as `fix(local): keep omlx credentials out of aider container`.

### Task 5: Dispatch readiness, retry, fallback, and failure tickets

**Files:**
- Modify: `synlynk/dispatch.py`
- Modify: `synlynk/local_lifecycle.py`
- Modify: canonical issue reporter module (identify and reuse existing GitHub issue-writing primitives before adding a new module)
- Modify: `synlynk/local_pilot_ledger.py`
- Test: `tests/test_dispatch.py`
- Test: `tests/test_local_lifecycle.py`
- Test: `tests/test_local_pilot.py`

**Interfaces:**
- Add a readiness entry point `prepare_local_pilot(repo_root: str, dispatch_key: str, pilot_class: str) -> LocalRuntimeResult`.
- Call it only after deterministic 20% cohort admission and before `resolve_effective_local_model`, signed receipt creation, Local job insertion, or sample-ledger admission.
- On readiness failure, retry once using the same approved model and lifecycle owner. On second failure, bind dispatch to the already-selected frontier fallback and create no Local receipt or eligible sample row.
- Build a deduplication key from `(phase, reason_code, omlx_version, approved_model_id)`. Use existing authorized control-plane issue-writing identity; append at most one update per fingerprint per hour. When unavailable, persist a redacted outbox event for retry.

- [ ] **Step 1: Write failing dispatch/ledger tests** for call ordering, exact two attempts, original-frontier fallback, no Local sample contamination, deduplication, rate limit, and offline outbox.
- [ ] **Step 2: Run `pytest -q tests/test_dispatch.py tests/test_local_pilot.py tests/test_local_lifecycle.py`** and confirm failure.
- [ ] **Step 3: Integrate lifecycle readiness after cohort selection** while retaining LIVE-25's selected-frontier binding and no-host-local fallback invariant.
- [ ] **Step 4: Implement redacted deduplicated failure reporting and outbox retry** through the canonical control-plane issue writer; Local receives no issue-writing authority.
- [ ] **Step 5: Verify failed Local readiness creates neither signed receipts nor sample-denominator records.**
- [ ] **Step 6: Run `pytest -q tests/test_dispatch.py tests/test_local_pilot.py tests/test_local_lifecycle.py`**; all focused tests pass.
- [ ] **Step 7: Commit** as `feat(local): retry pilot readiness and report failures`.

### Task 6: Host smoke verification and operator documentation

**Files:**
- Modify: `docs/reference/local-harness-pilot.md`
- Modify: `docs/reference/local-harness-isolated-qualification.md`
- Modify: `synlynk/local_agent.py`
- Test: `tests/test_local_agent.py`
- Test: `tests/test_local_pilot.py`
- Test: `tests/test_dispatch.py`
- Test: `tests/test_daemon.py`

**Interfaces:**
- Document key import/replacement/deletion, automated start/load, the untouched operator-owned-service rule, 15-minute idle stop, retry/fallback tickets, memory refusal, and emergency disable.
- Keep user-facing status redacted and distinguish stored credential, endpoint health, model loaded state, lifecycle ownership, and failure outbox status.
- Host smoke run is macOS-only and must use the same 20%/one-concurrency/isolated pilot restrictions.

- [ ] **Step 1: Add CLI/status tests** for credential state, service ownership, loaded model, idle countdown, memory gate, and pending failure ticket.
- [ ] **Step 2: Run the focused regression suite**: `pytest -q tests/test_local_credentials.py tests/test_local_lifecycle.py tests/test_local_auth_proxy.py tests/test_local_agent.py tests/test_local_pilot.py tests/test_dispatch.py tests/test_daemon.py`.
- [ ] **Step 3: Update the pilot and isolation runbooks** with exact macOS setup and recovery commands; do not include credential values.
- [ ] **Step 4: Run `synlynk local doctor` and the controlled host smoke sequence** on the 24 GiB host: import, absent-service start, Ornith load, isolated one-job dispatch, 15-minute unload/stop, and forced retry/fallback.
- [ ] **Step 5: Verify** no key appears in process arguments, Aider environment, Docker config, logs, state, telemetry, or tickets; confirm owned service stopped and operator-owned service preserved.
- [ ] **Step 6: Commit** as `docs(local): document unattended pilot lifecycle`.

## Integration Gate

- Run the focused suites above, then the full CI matrix and `qa-gate` on the PR.
- A non-author reviewer runs `synlynk pr check` from the PR worktree and the reviewer alone merges after `synlynk policy check-merge --role qa` passes.
- Run the 24 GiB macOS host smoke test before closing the lifecycle story; a unit-test-only pass does not establish Keychain, oMLX, or Docker operation.
- Keep the Local pilot at 20%; this plan creates no promotion or capacity increase.
