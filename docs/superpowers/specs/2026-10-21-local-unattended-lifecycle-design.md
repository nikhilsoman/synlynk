# Unattended Local Ornith Lifecycle Design

**Date:** 2026-10-21  
**Status:** Draft -- awaiting Nikhil approval  
**Extends:** `docs/superpowers/specs/2026-10-16-local-harness-operationalization-design.md`  
**Release:** v0.25.2 fleet capacity recovery  
**Related pilot:** gh:#2349

## Intent

Make the approved Local Ornith pilot usable without an operator remaining at a
terminal to export an oMLX key, start oMLX, or load the model. This removes an
operational availability bottleneck while preserving the pilot's narrow,
fail-closed execution boundary.

## Decisions

1. Synlynk owns lifecycle of the local oMLX service for admitted Local pilot
   work: it starts the service when absent and loads only
   `Ornith-1.0-9B-4bit`.
2. The oMLX credential is imported once from the operator's current
   `OPENAI_API_KEY` into the macOS Keychain. Thereafter only the local runtime
   supervisor reads it, at the last responsible moment. It is supplied to the
   managed oMLX process and the Synlynk relay through short-lived process
   environments. Aider receives no credential: the relay adds authorization
   to its fixed upstream oMLX connection. The key is never written to project
   files, state/telemetry, logs, command-line arguments, Docker configuration,
   or mounted container files.
3. After 15 minutes without an admitted Local job, Synlynk unloads Ornith and
   stops the service. The timeout is reset only by a successfully admitted
   Local job, not by rejected or frontier-routed work.
4. If service start, model load, authenticated inventory, isolation, or
   readiness validation fails, Synlynk retries the full readiness operation
   once. A second failure routes the job to its approved frontier fallback,
   records redacted evidence, and creates or updates one deduplicated GitHub
   issue for the failure fingerprint.
5. Runtime host evidence is authoritative. The managed host is 24 GiB;
   incorrect static hardware labels must not inflate scheduling capacity.
6. If oMLX is already running and is operator-owned, Synlynk leaves it
   untouched. If its authenticated roster lacks Ornith, Synlynk retries the
   read-only readiness probe once, then falls back and files the failure
   ticket. It never takes over, restarts, or unloads an operator-owned server.

## Scope and non-goals

The change applies only after existing admission has selected Local through
auto-routing: Ornith-only, one concurrent job, 20% cohort, signed receipt,
isolated Compose runner, and existing allowlisted pilot classes. It does not
allow explicit `local` forcing, model selection, reviews, GitHub writes,
merges, secrets work, broad tests, architecture/specification work, or a
larger pilot share.

Synlynk does not download models, manage a multi-model resident pool, expose
the key to Aider, persist it outside the keychain, or create GitHub issues
when Local was never selected for the cohort. An operator-controlled emergency
disable remains authoritative and stops new starts immediately.

## Components

### Credential setup and access

`synlynk local credentials import` reads `OPENAI_API_KEY` from the invoking
environment once and stores it under a stable host-level macOS Keychain
service/account (`com.synlynk.omlx`, account `local-runtime`). The command
prints neither value nor a reversible identifier. It requires an interactive
terminal and reports only that storage succeeded. The implementation uses the
macOS Keychain Services API, not a shell command that places the value in
process arguments. Import supports explicit replacement and deletion; headless
startup never prompts or writes credentials.

`LocalCredentialStore` is the only production reader. It retrieves the secret
at the last responsible moment, injects it into an in-memory environment for
the oMLX readiness client, managed server, and Synlynk relay, then removes
references after lifecycle operations. It is not passed to Aider. The relay
replaces the current raw TCP passthrough and adds the Bearer authorization
header only when forwarding to `127.0.0.1:8000`; its egress remains fixed to
that endpoint. Missing or inaccessible keychain entries are a classified
readiness failure, never a prompt for a secret in headless mode. The unattended
path is supported on macOS; other platforms report lifecycle automation as
unsupported and use frontier fallback.

### Local lifecycle manager

`LocalLifecycleManager.ensure_ready()` is hosted by Synlynk's persistent local
daemon/launch agent, so idle shutdown survives the short lifetime of a
dispatch CLI process. Lifecycle is host-global because all workspaces share
the local endpoint on port 8000. One lock and reservation registry cover every
workspace on the host. A durable ownership record stores the managed service
PID, process start time, launch-agent label, model ID, and lifecycle generation;
it stores no credential. PID plus start time prevents PID-reuse cleanup.
After daemon restart, the supervisor reconciles that record against the actual
process and authenticated endpoint before managing anything. Unknown or
operator-owned processes are never stopped.

It follows this sequence:

1. Read the pilot policy and confirm current Local admission has already
   passed; never start oMLX merely because a task mentions Local.
2. Inspect actual host memory before loading. Require at least 8 GiB available
   memory, normal macOS memory pressure, and no rising swap pressure; sample
   `sysctl vm.swapusage` twice ten seconds apart and reject startup if used
   swap grows by more than 256 MiB. If any signal is unavailable, fail closed.
   Recheck immediately before model load.
   This leaves roughly twice the observed 4.1 GiB Ornith peak for the model,
   Synlynk, Docker, and the desktop workload.
3. Probe the authenticated inventory. If an operator-owned server is already
   running, leave it untouched and accept it only if the exact approved
   Ornith ID is served. If no service is running, use a Synlynk-managed
   launch-agent instance.
4. The managed-service adapter resolves the installed `omlx` executable,
   validates it against the supported version range, and starts it using a
   documented, versioned argument-vector contract (never a shell command).
   It requests only `Ornith-1.0-9B-4bit`, then polls authenticated readiness
   and the live model inventory with bounded timeout/backoff. The manager must
   not guess CLI flags or load APIs: if the installed version exposes no
   supported exact-model load operation, it records `unsupported_load_contract`
   and falls back.
5. Confirm that `/v1/models` contains the exact approved model, Aider and
   Docker/Compose are available, and the isolated relay can be constructed.
   Only then issue the signed pilot receipt and start the job.

The host supervisor starts a 15-minute idle timer after the last Local job and
rechecks that no Local job or reservation exists before unloading Ornith and
stopping its managed service. It never terminates an operator-owned oMLX
process; service ownership is durably recorded at start time. If the Synlynk
daemon restarts, the LaunchAgent resumes ownership reconciliation and the idle
timer from the last recorded activity time.

### Failure and fallback

Each readiness attempt emits a redacted structured result containing phase,
classified reason, retry count, host-memory summary, and no secret material.
Readiness occurs after deterministic pilot-cohort admission but before model
resolution, signed Local receipt, or job creation. The first failed readiness
attempt causes one clean retry. After the second failure, dispatch binds to the
preselected frontier fallback, as required by LIVE-25; no Local receipt is
issued and the attempt is excluded from pilot sample denominators.

Synlynk's control-plane issue reporter (never the Local harness) creates or
updates a GitHub issue using its already-authorized ordinary issue-writing
identity. The deduplication fingerprint is `(phase, reason_code, omlx_version,
approved_model_id)` and excludes host paths, user identifiers, and secret
material. At most one open ticket exists per fingerprint; subsequent failures
append a timestamped summary no more than once per hour. If GitHub is
unavailable or no issue-writing identity is configured, a redacted local
outbox entry is retained and retried by the control plane; Local still falls
back immediately.

### Host capacity truth

`synlynk local doctor` reports measured usable memory separately from a named
tier. Correct the tier classifier so a 24 GiB machine is never reported as a
32 GiB machine. Scheduling uses measured capacity and the configured Local
policy, not the displayed tier label. A doctor warning for a label/capacity
mismatch is actionable but does not permit a different model.

## Acceptance criteria

- An interactive one-time import stores the oMLX key in the OS keychain; no
  repository, log, process argument, telemetry record, or Docker config
  contains the value.
- The Aider container environment contains no API key; only the host-side
  oMLX process and the narrowly scoped authorization relay receive it at
  runtime.
- An admitted, eligible Local job starts oMLX and makes Ornith ready without
  an operator shell export when the service is absent.
- A pre-running operator-owned oMLX service is probed but is never stopped by
  Synlynk's idle timer; if its roster lacks Ornith, the readiness retry and
  frontier fallback occur without taking over that service.
- The managed service stops and Ornith unloads after 15 idle minutes only when
  no Local job or reservation exists.
- A failed readiness sequence retries once, then uses the bound frontier
  fallback; it never runs host-side Aider and never silently retries forever.
- Exhausted readiness failures create or update a deduplicated redacted GitHub
  ticket, and do not count as Local pilot samples.
- The 24 GiB memory guard and static-label mismatch are covered by tests.
- Readiness and issue creation run after cohort admission but before any Local
  receipt or sample is recorded.
- Existing Local-pilot isolation, receipt, one-concurrency, 20% cohort, and
  fallback-binding tests remain green.

## Rollback

Setting `local_pilot.enabled` to `false` prevents new lifecycle starts.
`synlynk local lifecycle stop` explicitly stops only a Synlynk-managed service
and clears its in-memory credential reference. Removing the keychain entry
causes future Local dispatches to fail closed to their frontier fallback.
Operator-owned services are never affected by the stop command.

## Verification plan

Unit tests cover keychain interface failures/redaction, ownership tracking,
readiness retry/fallback, idle-timer races, memory rejection, issue
deduplication, and proof that failed readiness does not create Local sample
evidence. Integration tests use fake process and inventory adapters; they must
not require a real keychain, oMLX server, Docker daemon, or GitHub token.
A single controlled host smoke run verifies the keychain import, managed start,
Ornith inventory, isolated receipt, 15-minute idle shutdown, and a forced
failure fallback. The pilot remains at 20% and requires separate receipt
review; this feature does not itself promote it. Before implementation, verify
the installed oMLX version's documented launch and exact-model load API and
pin the supported contract in tests; absent such an API, keep fallback behavior
and file the unsupported-contract ticket rather than guessing.
