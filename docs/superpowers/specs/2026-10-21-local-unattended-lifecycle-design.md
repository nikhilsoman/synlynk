# Unattended Local Ornith Lifecycle Design

**Date:** 2026-10-21  
**Status:** Approved by Nikhil on 2026-10-21; runtime ownership and credential-source amendments proposed 2026-10-21, awaiting sign-off
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
2. The existing persistent oMLX-generated API key in oMLX's active
   `settings.json` is authoritative. Synlynk reads it into memory only when
   needed for authenticated readiness/model-management API calls and the
   narrow Synlynk relay; it does not prompt, import, replace, or persist a
   second copy in Keychain. This supersedes the Keychain/`OPENAI_API_KEY`
   path from the 2026-10-16 operationalization design for Local lifecycle
   readiness and relay only. The foreground oMLX process reads the same
   settings file using the installed wrapper's base-path behavior. Aider
   receives no credential: the relay adds authorization only to its fixed
   upstream oMLX connection. The key is never written to project files,
   state/telemetry, logs, command-line arguments, Docker configuration, or
   mounted container files. If the active settings file or key is missing,
   unreadable, or invalid, Local readiness fails closed to frontier fallback.
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
7. **Ownership amendment proposed by Nikhil on 2026-10-21:** when the endpoint
   is absent, Synlynk launches a dedicated foreground `omlx serve` process,
   rather than using the app-managed `omlx start` command. Synlynk records the
   exact spawned PID plus process-start identity and only signals that exact
   process after revalidating both values. The command binds only to
   `127.0.0.1:8000`; it uses the installed oMLX wrapper/default base-path and
   settings, but receives neither `OPENAI_API_KEY` nor `OMLX_API_KEY` in its
   environment and receives no API key argument. Its stdout/stderr are not
   persisted by Synlynk. Synlynk reads the key from oMLX's active persistent
   settings for authenticated readiness and the host relay. If the wrapper cannot be
   resolved, the child cannot be identity-verified, or the endpoint appears
   before the child binds, Synlynk does not claim or stop that endpoint and
   falls back.

## Scope and non-goals

The change applies only after existing admission has selected Local through
auto-routing: Ornith-only, one concurrent job, 20% cohort, signed receipt,
isolated Compose runner, and existing allowlisted pilot classes. It does not
allow explicit `local` forcing, model selection, reviews, GitHub writes,
merges, secrets work, broad tests, architecture/specification work, or a
larger pilot share.

Synlynk does not download models, manage a multi-model resident pool, expose
the key to Aider, duplicate or mutate the oMLX key, or create GitHub issues
when Local was never selected for the cohort. `synlynk local credentials import`
may remain as a legacy credential-management command for other consumers, but
it is not a prerequisite or source for this lifecycle path; `local doctor` must
report the active oMLX settings credential state without printing it or relying
on `OPENAI_API_KEY`. An operator-controlled emergency disable remains
authoritative and stops new starts immediately.

## Components

### Credential access

For this lifecycle path, `LocalCredentialStore` reads the active oMLX `settings.json` selected by the
same base-path resolution as the installed oMLX wrapper (including its macOS
bootstrap file). It extracts only `auth.api_key` into process memory; it must
not log the settings document or key. It does not invoke a shell, expose the
key in arguments/environment, create or mutate credentials, or maintain a
Synlynk-owned duplicate. The relay adds the Bearer authorization header only
when forwarding to `127.0.0.1:8000`; its egress remains fixed to that endpoint.
Missing file/key, permission or parse errors, and authentication rejection are
classified readiness failures, never an interactive prompt. The unattended
path is supported on macOS; other platforms report lifecycle automation as
unsupported and use frontier fallback.

### Local lifecycle manager

`LocalLifecycleManager.ensure_ready()` is hosted by Synlynk's persistent local
daemon/launch agent, so idle shutdown survives the short lifetime of a
dispatch CLI process. Lifecycle is host-global because all workspaces share
the local endpoint on port 8000. One lock and reservation registry cover every
workspace on the host. A durable ownership record stores the managed service
PID, process start time, Synlynk supervisor launch-agent label, model ID, and lifecycle generation;
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
   Ornith ID is served. If no service is running, use a Synlynk-owned
   foreground process instance.
4. The managed-service adapter resolves the installed `omlx` executable and
   validates its version. The evaluated host has oMLX 0.5.3, whose
   `omlx serve --host 127.0.0.1 --port 8000` command runs the ASGI server in
   the foreground; its authenticated API exposes
   `POST /v1/models/{model_id}/load` and
   `POST /v1/models/{model_id}/unload`. When the endpoint is absent at step 3,
   the manager starts this command through an argument-vector `Popen` call,
   with no shell and with API-key environment variables removed. It retains the
   direct child PID/start identity and uses that identity as the only proof
   authorizing a later stop. The process inherits the oMLX install wrapper's
   base-path behavior and uses the existing oMLX settings; Synlynk does not
   alter those settings or pass a key through args/environment. It then
   authenticates with the persistent settings credential and loads only
   `Ornith-1.0-9B-4bit` through the model-specific API. It polls readiness and
   live inventory with bounded timeout/backoff. The adapter supports only
   explicitly tested oMLX versions; unknown versions or missing endpoints
   produce `unsupported_load_contract` and frontier fallback.
5. Confirm that `/v1/models` contains the exact approved model, Aider and
   Docker/Compose are available, and the isolated relay can be constructed.
   Only then issue the signed pilot receipt and start the job.

The host supervisor starts a 15-minute idle timer after the last Local job and
rechecks that no Local job or reservation exists before calling the
authenticated per-model unload endpoint and sending `SIGTERM` to the exact
managed foreground PID. It never invokes the global `omlx stop` command. It
revalidates PID plus process-start identity immediately before signaling, so
PID reuse or a replacement operator process cannot be stopped. Ownership is
durably recorded only after Synlynk observes the endpoint absent, launches the
foreground server itself, verifies its child identity, and sees that exact
process own port 8000. If an unrelated process wins the bind race, Synlynk
terminates only its own failed child (if still alive), creates no ownership
record, and falls back. If the Synlynk daemon restarts, the LaunchAgent resumes
ownership reconciliation and the idle timer from the last recorded activity
time.

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

- Synlynk reads the existing persistent oMLX key from the active settings file
  without prompting or creating a duplicate; no repository, log, process
  argument, telemetry record, or Docker config contains the value.
- The Aider container and oMLX process environments contain no API key; only
  the in-process authenticated API client and narrowly scoped authorization
  relay read it at runtime.
- An admitted, eligible Local job starts oMLX and makes Ornith ready without
  an operator shell export when the service is absent.
- A pre-running operator-owned oMLX service is probed but is never stopped by
  Synlynk's idle timer; if its roster lacks Ornith, the readiness retry and
  frontier fallback occur without taking over that service. An endpoint
  appearing during startup never authorizes stopping its listener.
- The managed foreground process stops only through its verified PID/start
  identity, and Ornith unloads after 15 idle minutes only when no Local job or
  reservation exists.
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
and clears its in-memory credential reference. Removing or invalidating the
oMLX key causes future Local dispatches to fail closed to their frontier fallback.
Operator-owned services are never affected by the stop command.

## Verification plan

Unit tests cover missing/unreadable/invalid settings credential handling and
redaction, doctor reporting based on settings rather than `OPENAI_API_KEY`,
legacy-import independence, foreground-process ownership tracking, readiness
retry/fallback, idle-timer and bind races,
memory rejection, issue deduplication, and proof that failed readiness does
not create Local sample evidence. Integration tests use fake process and
inventory adapters; they must not require a real keychain, oMLX server, Docker
daemon, or GitHub token.
A single controlled host smoke run verifies persistent-settings auth, managed
start, Ornith inventory, isolated receipt, 15-minute idle shutdown, and a forced
failure fallback. The pilot remains at 20% and requires separate receipt
review; this feature does not itself promote it. Before implementation, verify
the installed oMLX version's documented launch and exact-model load API and
pin the supported contract in tests; absent such an API, keep fallback behavior
and file the unsupported-contract ticket rather than guessing.
