# Local Pilot Host TCP Relay Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Replace the Local Pilot's unconnectable host Unix socket with a loopback-only, per-job TCP broker path through a fixed-destination relay while preserving Aider isolation and keeping the real oMLX key on the host.

**Architecture:** The host broker binds to `127.0.0.1` on an ephemeral port and retains the current endpoint/model/payload allowlist and upstream Keychain credential injection. The relay container joins both the internal pilot network and a dedicated bridge network, forwards only to `host.docker.internal:<per-job-port>`, and remains non-privileged. Aider stays on the internal network only and uses the relay's existing `omlx:8000` endpoint.

**Tech Stack:** Python `http.server` / `socketserver`, Docker Compose, Alpine `socat`, pytest.

**Spec:** `docs/superpowers/specs/2026-10-21-local-pilot-host-tcp-relay-design.md`

## Global Constraints

- Keep the Local Pilot at 20% share, concurrency 1, and no-promotion until evidence is reviewed.
- The broker binds to loopback only, never `0.0.0.0` or a LAN-facing address.
- The host broker port is unpredictable and per-job; it is passed only to the relay service, not Aider.
- The real Keychain credential stays in the host process and is cleared from memory on teardown.
- Aider has no host home, Docker socket, host filesystem, SSH/GitHub credentials, or general network access.
- The relay is trusted as a non-privileged, fixed-destination forwarder and does not support arbitrary forwarding, shell execution, or caller-controlled destination changes.
- If setup, authenticated requests, or isolation checks fail, fail closed and use the existing frontier fallback.

## Review Focus

- Broker bind/start failure must fail before Aider starts and must not leave an open listener.
- Unsupported endpoint, query, model, oversized, or malformed requests must not reach oMLX.
- Relay failure or timeout must produce a failed pilot result promptly and clean up Compose resources.
- The real oMLX key must not enter Aider arguments/environment, Docker inspect output, logs, receipts, or worktree files.
- Aider must not reach the host broker directly or arbitrary Internet destinations; only the relay receives the broker-facing network attachment.

---

### Task 1: Convert the host authentication broker to loopback TCP

**Files:**
- Modify: `synlynk/local_auth_proxy.py`
- Test: `tests/test_local_auth_proxy.py`

**Interfaces:**
- Produces: `LocalAuthBroker(credential, host="127.0.0.1", port=0, ...)`, `start() -> int` returning the bound port, and idempotent `close()`.
- Preserves: `from_settings(...)`, upstream `UPSTREAM_HOST="127.0.0.1"`, `UPSTREAM_PORT=8000`, endpoint/model filtering, response sanitization, and `ensure_inert_aider_key(...)`.

- [ ] **Step 1: Write broker TCP tests first**
  - Replace Unix-socket request helper coverage with a loopback TCP helper.
  - Add `test_broker_binds_loopback_ephemeral_port_and_injects_key` asserting an allocated port is nonzero, listener address is `127.0.0.1`, and the upstream receives the stored key while the inert Aider key is discarded.
  - Preserve tests for model inventory filtering, approved chat model rewriting, denied paths/queries, malformed and oversized requests, sanitized upstream failures, and credential clearing on close.
- [ ] **Step 2: Run `pytest tests/test_local_auth_proxy.py -q` and verify the new transport test fails because the broker only exposes a Unix socket**
- [ ] **Step 3: Implement the loopback TCP server with port `0` support and return the actual bound port from `start()`**
- [ ] **Step 4: Run `pytest tests/test_local_auth_proxy.py -q` and verify all broker tests pass**
- [ ] **Step 5: Commit**

```bash
git add tests/test_local_auth_proxy.py synlynk/local_auth_proxy.py
git commit -m "fix(local-pilot): expose host broker over loopback TCP"
```

### Task 2: Wire per-job broker port through the isolated relay topology

**Files:**
- Modify: `synlynk/local_pilot_runner.py`
- Modify: `docker/local-pilot.compose.yaml`
- Modify: `tests/test_local_pilot.py`
- Modify: `docs/reference/local-harness-pilot.md`

**Interfaces:**
- Consumes: Task 1 `LocalAuthBroker.start() -> int`.
- Produces: Compose environment `PILOT_RELAY_PORT`, set only in the host runner environment and consumed only by `omlx-relay`.

- [ ] **Step 1: Write runner and Compose regression tests first**
  - Update `test_isolated_runner_cleans_up_compose_and_redacts_persisted_logs` to assert broker startup precedes relay startup, its allocated port is passed to Compose, and broker close runs on success and failure.
  - Update `test_real_compose_uses_private_unix_relay_and_no_host_key_environment` to assert the relay's fixed `host.docker.internal:${PILOT_RELAY_PORT}` target, two networks on relay, internal-only Aider attachment, non-privileged settings, and absence of the host key and Unix socket mount.
- [ ] **Step 2: Run the focused tests and verify failure against the current runner/Compose configuration**
- [ ] **Step 3: Start the host broker before `docker compose up`, pass only the ephemeral port to Compose, and close it in every teardown path**
- [ ] **Step 4: Give `omlx-relay` the internal `local-pilot` network plus a dedicated bridge network; make its socat destination literal except for the host-assigned per-job port; leave Aider on `local-pilot` only**
- [ ] **Step 5: Update the pilot documentation to describe loopback TCP, the dedicated bridge, fixed relay destination, unchanged credential boundary, and failure behavior**
- [ ] **Step 6: Run `pytest tests/test_local_auth_proxy.py tests/test_local_pilot.py -q` and verify all focused tests pass**
- [ ] **Step 7: Commit**

```bash
git add synlynk/local_pilot_runner.py docker/local-pilot.compose.yaml tests/test_local_pilot.py docs/reference/local-harness-pilot.md
git commit -m "fix(local-pilot): route isolated relay to host broker"
```

### Task 3: Add a disposable Docker end-to-end relay check

**Files:**
- Create: `tests/test_local_pilot_relay_integration.py`
- Modify: `tests/test_local_pilot.py` if a shared test helper is needed

**Interfaces:**
- Consumes: Task 1 broker and Task 2 Compose topology.
- Produces: opt-in Docker integration coverage gated by `SYNLYNK_RUN_LOCAL_PILOT_RELAY_INTEGRATION=1`; it uses a fake upstream connection and never requires a real oMLX key or starts/stops oMLX.

- [ ] **Step 1: Write the gated integration test**
  - Start the host broker with a fake upstream returning a controlled model inventory and chat completion.
  - Start only the Compose relay with a unique project name and per-job broker port.
  - Send `/v1/models` and `/v1/chat/completions` through `omlx:8000` from a temporary client attached to the internal pilot network; assert the approved model and fake upstream response are returned and the real test credential is injected only upstream.
  - Assert denied paths/models fail without upstream calls; assert Aider-network clients cannot bypass the relay to reach the host broker; always tear down the project and broker.
- [ ] **Step 2: Run the integration test with the feature flag unset and verify it skips without Docker side effects**
- [ ] **Step 3: Run `SYNLYNK_RUN_LOCAL_PILOT_RELAY_INTEGRATION=1 pytest tests/test_local_pilot_relay_integration.py -q` on OrbStack and verify authenticated inventory and chat requests succeed through the relay, prohibited paths fail, and no temporary resources remain**
- [ ] **Step 4: Run the focused regression suite `pytest tests/test_local_auth_proxy.py tests/test_local_pilot.py tests/test_dispatch.py -q`**
- [ ] **Step 5: Commit**

```bash
git add tests/test_local_pilot_relay_integration.py
git commit -m "test(local-pilot): verify isolated host TCP relay end to end"
```

### Task 4: Final verification and handoff

**Files:**
- Verify the task diff and all three commits; no additional source files unless required by a test-driven fix.

- [ ] **Step 1: Run `pytest` for the complete repository suite; report every failure by name**
- [ ] **Step 2: Run the Docker-backed integration check again and inspect the relay/Aider network attachments and teardown state**
- [ ] **Step 3: Confirm the worktree and Docker project contain no residual broker, relay container, test network, or scratch worktree**
- [ ] **Step 4: Do not automatically launch the Local Pilot canary; request a separate operator go-ahead after reporting the integration evidence**
