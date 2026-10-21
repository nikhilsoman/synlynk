# Local Harness pilot

The initial production-equivalent cohort is limited to the qualified Ornith
profile and the explicit task classes `test_summary`, `test_diagnosis`,
`codepath_summary`, `change_summary`, `documentation_edit`, and
`mechanical_edit`. Work must be dispatched as `auto` with a class; the router
keeps unclassified, excluded, and out-of-cohort tasks on the configured
frontier fallback.

For example:

```sh
synlynk dispatch auto --local-pilot-class test_summary \
  --task-type test --story <story-id> \
  --scope-paths path/to/test.log \
  --task "Summarize the focused test output and list failures"
```

Every class needs at least one bounded `--scope-paths` entry; absolute paths,
parent traversal, `.git`, and `.synlynk` paths are rejected. Summary classes
are opened read-only to Aider. Edit classes can only be copied back to the job
worktree when every changed path matches the declared scope.

The cohort assignment is stable for a story/issue key (or task digest when no
key is supplied). The checked-in workspace policy starts at 20%. Only the
approved 20%, 35%, and 50% gates are accepted. Promotion is an operator
decision based on receipts: at least 30 jobs and 90% acceptance before 35%;
at least 75 jobs, 90% acceptance, stable latency and memory, and a passed
rollback drill before 50%. A serious incident or failed gate returns the
recommended share to the frontier (0%).

Pilot Aider runs use `docker/local-pilot.compose.yaml`: Aider is on an
internal-only Docker network; its sole peer is a relay with a fixed destination
of a per-job host credential broker over loopback TCP. The host broker binds only
to `127.0.0.1` on an ephemeral port. The relay alone also joins a dedicated bridge
network so it can reach `host.docker.internal`; it forwards only to that broker port.
Aider remains attached only to the internal network, so it cannot reach the host
broker directly or use the relay for arbitrary destinations. The relay is a
non-privileged fixed-destination forwarder. Aider receives a credential-scanned copy of only
explicitly scoped files in a disposable scratch repository, not the job
worktree or its Git metadata. Out-of-scope tracked and untracked files are not
copied into the model's view. Only validated in-scope edits are applied back
to the disposable job worktree. The Aider container receives an inert API-key
placeholder, but no host credentials, GitHub tokens, SSH credentials, or host
home directory. The API base inside Aider is rewritten to
`http://omlx:8000/v1`. Aider is given only an inert placeholder API key; the
host broker discards it and injects the Keychain credential. A Docker, Compose,
authentication, or isolation setup failure never falls back to host Aider
execution.

## Unattended host lifecycle

The Local pilot starts and loads only the approved
`Ornith-1.0-9B-4bit` model when an admitted pilot dispatch needs it. On macOS,
the API key must be imported once into the user's Keychain; the value is never
written to a file or passed to Aider/Docker. In an interactive terminal:

```sh
read -s OPENAI_API_KEY
export OPENAI_API_KEY
synlynk local credentials import
unset OPENAI_API_KEY
synlynk local credentials status
synlynk local lifecycle status
```

To rotate the stored credential, repeat the import with `--replace`; to revoke
it, run `synlynk local credentials delete`. Do not put the key in shell history,
command arguments, a `.env` file, or issue text. Credential status reports only
whether a value is present. `synlynk local lifecycle status` separately reports
credential presence, endpoint reachability, approved-model load state,
Synlynk ownership, active leases, idle time, and the count of pending redacted
failure reports.

Synlynk never takes over an already-running operator-owned oMLX service. If that
service does not expose the approved model, Local is not changed or restarted:
the dispatch retries readiness once, then routes to the frontier harness
already selected for that dispatch. The same fallback applies to Keychain,
authentication, model-load, memory-pressure, unsupported-version, or isolated
runner errors. A failed readiness creates no Local receipt or eligible sample.
The control plane files or updates one deduplicated GitHub issue per failure
fingerprint, at most once an hour; if GitHub is unavailable, only a redacted
event is retained locally for a later retry.

Synlynk-owned oMLX is stopped only after 15 minutes idle with no active Local
jobs or reservations. Host memory admission requires normal macOS memory
pressure, at least 8 GiB available, and no more than 256 MiB swap growth during
the sampling interval. To disable pilot routing immediately, set
`local_pilot.enabled` to `false`; to stop only a provably Synlynk-owned idle
service, run `synlynk local lifecycle stop`. A running operator-owned service
is never stopped by either command.

The pilot remains at 20%, one concurrent Local job, and isolated execution.
The host TCP broker and relay topology are covered by the opt-in test
`SYNLYNK_RUN_LOCAL_PILOT_RELAY_INTEGRATION=1 pytest tests/test_local_pilot_relay_integration.py -q`.
Do not use a real dispatch as a smoke test until this Docker-backed check passes.

To stop Local Pilot routing immediately, set `local_pilot.enabled` to `false`
in `.synlynk/workspace.json`. To roll back the cohort without changing the
feature configuration, set `local_pilot.share` to `0`; the router rejects that
unapproved share and uses the frontier fallback. Do not raise the share without
the corresponding evidence review.

This pilot does not authorize production-file changes, refactors, architecture
or specification work, dependency changes, GitHub writes, reviews, merges,
secrets work, or broad test execution. Those jobs must not be tagged with a
Local Pilot class.
