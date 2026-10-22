# Design: Local Pilot Host TCP Relay (#2525)

**Status:** Approved by Nikhil in conversation on 2026-10-21; implementation follows a committed plan
**Date:** 2026-10-21
**Parent:** GitHub issue #2525; pilot story #2349
**Scope:** Replace the unsupported host-Unix-socket transport in the Local Pilot only.

## Intent

Restore a reliable path from the isolated Aider container to the host-authenticated
oMLX broker so Local Pilot can produce real task receipts. Keep the oMLX credential
on the host and preserve the Aider container's restricted execution environment.

## Context

The canary `job-3e8e426d` passed readiness, but its Docker relay repeatedly received
`Connection refused` connecting to the mounted host socket at
`/run/synlynk/relay.sock`. The runner starts the host broker before starting the
relay container, so the observed failure is not explained by the current startup
ordering.

This was reproduced on OrbStack 29.8.2 / macOS Apple Silicon with a disposable host
Unix socket and `alpine/socat`: a bind-mounted socket returned the same connection
refusal. A second disposable probe succeeded when a host service bound only to
`127.0.0.1` was reached from a normal bridge container through
`host.docker.internal`.

The current runtime contract is documented in
`docs/reference/local-harness-pilot.md`; the broker implementation is
`synlynk/local_auth_proxy.py`, and the relay topology is
`docker/local-pilot.compose.yaml`.

## Goals

- Remove dependence on mounting a macOS Unix socket into a Linux container.
- Keep the real oMLX API key on the host; Aider and Docker must never receive it.
- Keep Aider on an internal-only Docker network with no general Internet route.
- Allow only the relay service to reach a per-job host broker endpoint.
- Preserve broker restrictions: approved model only, `/v1/models` and
  `/v1/chat/completions` only, bounded request/response sizes, no credential logging.
- Fail closed and terminate promptly when relay setup or authenticated inference fails.
- Keep Local Pilot at 20% share, concurrency 1, and no-promotion until evidence is
  reviewed.

## Non-goals

- Changing the approved model, pilot cohort, task classes, or rollout gates.
- Exposing oMLX itself to Docker, the LAN, or the public network.
- Passing the real oMLX key through Aider, Docker environment, command arguments,
  worktree files, or logs.
- Restarting or otherwise taking ownership of an operator-started oMLX service.
- Replacing OrbStack or provisioning a VM.

## Proposed design

1. The host runner starts the existing authenticated broker on `127.0.0.1` using
   an ephemeral TCP port allocated for that job. The broker continues to inject the
   stored oMLX key only on its upstream loopback request to port 8000.
2. Compose gives the small relay service two networks: the existing internal pilot
   network shared with Aider, and a dedicated bridge network used to reach the host
   broker through `host.docker.internal`. Aider remains attached only to the
   internal network. It must not receive the host broker port or a route around the
   relay.
3. The relay listens on its existing service endpoint (`omlx:8000`) and uses a
   fixed forwarding destination: `host.docker.internal:<per-job-port>`. The broker
   port is passed only to the relay service. The relay must not accept a caller-
   supplied destination or become a general-purpose forward proxy.
4. The broker validates request method/path, model ID, payload bounds, and content
   length before contacting oMLX. It injects the stored oMLX credential upstream
   and does not log credentials or request bodies.
5. Startup includes a broker/relay readiness handshake before Aider starts. Socket
   or TCP setup failures, timeouts, invalid credentials, disallowed paths/models,
   and upstream failures must produce a failed pilot receipt promptly and follow
   the existing frontier-fallback policy.
6. Teardown closes the broker listener, revokes the per-job capability, stops the
   relay, and removes its Docker networks and scratch worktree on every exit path.

## Security and isolation constraints

- The broker binds to loopback only, never `0.0.0.0` or a LAN-facing address.
- The host broker port is unpredictable and per-job; it is passed only to the
  relay service, not Aider. The broker binds to loopback only.
- The real Keychain credential stays in the host process and is cleared from
  memory on teardown as in the current implementation.
- Aider has no host home, Docker socket, host filesystem, SSH/GitHub credentials,
  or general network access.
- The dedicated host-access bridge is attached only to the minimal relay service.
  Aider stays off that bridge. The relay process uses a literal, per-job destination
  and does not accept destination overrides from Aider.
- The relay is trusted as a non-privileged, fixed-destination forwarder. Its bridge
  may provide network-layer egress, but the relay itself must not support arbitrary
  forwarding, shell execution, or caller-controlled destination changes. Nikhil
  explicitly accepted this boundary for the quick recovery path.
- Relay and broker logs redact credentials; error output must not include HTTP
  Authorization values or payloads.
- If these constraints cannot be met on OrbStack, fail closed and use the selected
  frontier fallback rather than weakening isolation.

## Acceptance criteria

- A disposable integration test proves host-loopback TCP reachability from the
  relay container over `host.docker.internal` on the supported OrbStack setup.
- An end-to-end test exercises authenticated model inventory and one chat-completion
  request through the isolated Aider-to-relay-to-host-broker path.
- Aider cannot reach the host broker directly and cannot reach arbitrary Internet
  hosts; only the relay has the broker-facing network attachment.
- Missing/invalid capability, unsupported endpoint/model, refused connection, and
  timeout cases fail promptly with explicit failure receipts and no credential
  leakage.
- The real oMLX key is absent from Aider environment/configuration, process args,
  Docker inspect output, logs, task receipts, and worktree files.
- Teardown leaves no broker listener, relay container, temporary network, capability,
  or scratch worktree behind.
- The original read-only Local canary can then be rerun only after the integration
  test passes; the pilot gates do not change.

## Approved security boundary

The dual-network relay is trusted as a small, non-privileged fixed-destination
forwarder; Aider remains the untrusted component and stays on the internal-only
network. The bridge may provide network-layer egress, but the relay must not be a
general-purpose proxy or execute task-supplied commands. The builder must verify
the exact dual-network routing and prove that Aider cannot directly reach the host
broker or arbitrary Internet destinations before claiming the isolation criteria
pass. The internal-network probe did not complete within its timeout, so it is not
treated as verification of this property.

## Evidence and references

- Local canary and socket-refusal evidence: GitHub issue #2525.
- OrbStack container-to-Mac TCP support:
  <https://docs.orbstack.dev/docker/network#connecting-to-servers-on-mac>
- OrbStack discussion of Unix sockets on the shared macOS filesystem:
  <https://github.com/orbstack/orbstack/issues/62>
