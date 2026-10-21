# Task 3 report — dispatch enforcement, pause serialization, and fallback context

## Implementation

- Dispatch now requires a durable `active` resume authorization whose signed
  preflight receipt names the exact 20% / one-concurrent target, in addition
  to the enabled, qualified, isolated runtime. Missing authority, staged or
  terminal authorization, configuration drift, and ledger uncertainty all
  route to the configured frontier fallback.
- The runtime surface now exposes `max_concurrent`, so dispatch rejects a
  widened concurrency setting rather than defaulting it to one.
- Terminal Local safety reconciliation passes its existing ledger connection
  to `pause_local_pilot`. Pause revokes the active authorization before it
  writes the disabled configuration, so a safety event cannot leave an active
  authority paired with an enabled configuration.
- The recursive frontier fallback now retains the original `pr` argument.
- The operator runbook documents the interactive ceremony, host-key
  attestation limitation, preflight fields, lifecycle/crash recovery,
  dispatch gate, and the no-live-dispatch rule.

No resume command was invoked and no Local configuration was enabled.

## TDD and verification

RED observations:

1. `test_enabled_local_pilot_without_active_resume_authorization_falls_back`
   initially routed to `local` with only an enabled config.
2. `test_pause_revokes_active_resume_authorization_before_disabling_config`
   initially failed because `pause_local_pilot` had no ledger connection and
   therefore could not revoke the active authority.
3. `test_terminal_safety_failure_passes_ledger_connection_to_serialized_pause`
   initially failed because terminal reconciliation called pause without its
   ledger connection.
4. `test_local_frontier_fallback_preserves_pr_context` initially failed with
   no `pr` value on the fallback recursive dispatch.

GREEN evidence:

- `pytest tests/test_dispatch.py tests/test_jobs.py tests/test_local_pilot_ledger.py -q -k "local_pilot or resume_authorization"`
  — `39 passed, 349 deselected`.
- `pytest tests/test_local_pilot.py tests/test_local_pilot_ledger.py tests/test_dispatch.py tests/test_jobs.py -q`
  — `417 passed`.
- `pytest tests/test_agent_cli.py -q -k "local_pilot"`
  — `17 passed, 160 deselected`.
- `pytest tests/test_agent_cli.py -q -k "local_pilot_operations_runbook"`
  — `1 passed, 176 deselected`.
- `git diff --check` — passed.

## Known baseline

The recorded broad-suite baseline remains the sandbox-denied localhost bind in
`tests/test_agent_cli.py::test_manifest_auth_prevent_dropped_oauth_codes_in_manifest_callback_server`
(`PermissionError: [Errno 1] Operation not permitted`). It is unrelated to
Task 3 and was intentionally not changed.
