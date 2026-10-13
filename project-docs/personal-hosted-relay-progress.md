# Personal Hosted Relay execution ledger

Date: 2026-10-13
Goal: goal-f4ce526a
Issue: #2201
Conductor session: session-0fe91cb1
Feature branch: feat/codex/personal-hosted-relay

| Task | Story | Status | Evidence |
| --- | --- | --- | --- |
| 1 Optional dependency and lazy import | story-52549f07 | Verified; story done | Original 2375ec24 preserved as d7ed8c7c; 10 relay tests pass |
| 2 Event types | story-085360d0 | Verified; story done | Source 3d2a452f; four red cases; 14 relay tests pass; broad verification 1381 passed, 1 skipped; spec/quality review passed |
| 3 Subject routing | story-76b7162d | Verified; story done | Source c76484b9; 114 targeted passed; 1473 broad passed, 1 skipped; spec/quality review passed |
| 4 Device credentials | story-0c7ecea4 | Verified; story done | Source ec156673; 131 targeted passed; 1492 broad passed, 1 skipped; real NATS config parse; spec/quality review passed |
| 5 Hub bridge | story-2263ec9a | Verified; story done | Source bf60fcaa; 153 targeted,1514 broad passed,1 skipped; independent async/concurrency review approved |
| 6 Durable replay | story-29cc4aad | Verified; story done | Source 25d397ba integrated as 31683d36; 166 targeted, 1527 broad passed, 1 skipped; real authenticated replay; independent review approved |
| 7 CLI | story-43a01b32 | Verified; story done | Source 814151bf plus reviewed onboarding corrections integrated as 84d730ab; 191 targeted passed, worker broad 1546 passed/1 skipped; independent review approved |
| 8 Real NATS integration | story-f4824a3e | In progress | job-02ef4311; failed cross-provider reroute job-20b0e6e2 had zero tokens/no changes, tracked in #2255 |
| 9 Document preview | story-dbf68f01 | Pending | |
| 10 Full regression | story-f1639150 | Pending | Baseline: 4173 passed, 10 failed, 5 errors, 7 skipped, 5 xfailed (757s); final run mandatory |

## Decisions and constraints

- User authorized conductor ownership and implementation on 2026-10-13.
- Preserve the user's root checkout and other sessions' work.
- Sequential implementation dispatches, task-level commits, review before integration.
- Use CLI story commands; do not edit generated todo.md.
- Keep NATS imports lazy and the hub extra optional.
- Do not describe generated configuration as a running managed service.
- Verify actual replay, echo prevention, revocation, and safe preview paths against real behavior.
- Five-minute progress heartbeat active in the user thread.
- Deferred reconnect/status/managed-service gates tracked in gh:#2256.
- Main advanced by 2fd63ac6 (Muse API key passthrough); integrate before final
  regression so Task 10 covers the actual PR base.
- Job projection/reconciliation tuple-row crash filed as #2254. Session checkpoint
  shows stale running labels despite verified commits/tests/comments. Report task
  status from concrete evidence; do not fabricate oracle success or bypass checks.
- User explicitly approved gpt-6-astra for this epic on 2026-10-13. The default
  gpt-5.3-codex was rejected as unsupported by the ChatGPT account; the failed job
  recorded zero tokens. Astra is used for async transport, durability, credential,
  and filesystem integration reasoning, with task-scoped dispatches and telemetry.

## Pre-implementation integration audit

- Real NATS server v2.11.8 rejects the plan's authorization.users token field
  (unknown field; user entry requires a user). It accepts user=device ID and
  password=random bearer secret. Preserve the settled secret-based mechanism.
- Broker INSERT OR IGNORE only deduplicates persistence; subscribers still receive
  duplicate publish calls. The bridge must prevent both own echoes and duplicate
  inbound delivery rather than relying on SQLite alone.
- Use a production async NATS transport, observed publish/subscribe results, and
  clean shutdown rather than only a test SyncWrapper.
- Wire actual per-category JetStream streams and per-device durable consumers.
  Acknowledge after delivery; track streams independently. Contiguous sequence
  last=5/earliest=6 is not a gap.
- Generated credentials must work with JetStream API, ack, and inbox permissions.
  Test authenticated delivery and actual revocation; changing a registry alone
  cannot revoke a connected server client.
- CLI/runtime must attach to the running local broker and consume subscription
  settings. Config-file generation alone does not create a functioning bridge.
- Preview writes must reject traversal and symlink escape, constrain source roots,
  enforce read-only output, and bound serialized-envelope bytes.
- Integration environment: /private/tmp/synlynk-relay-test-env (nats-py 2.16.0),
  /private/tmp/synlynk-relay-bin/nats-server (v2.11.8).

## Baseline full-suite evidence (before Task 2 integration)

Command: python3 -m pytest -q; log: /private/tmp/personal-relay-baseline.log.
Result: 10 failed, 4173 passed, 7 skipped, 5 xfailed, 5 errors in 757.21s.
Failures span local socket/process permission tests, Muse command construction,
Grok failover, Vizor workspace setup, and packaging's blocked PyPI build dependency
download. Preserve as baseline and compare exact failures during Task 10; do not
attribute them to relay implementation. Run final verification with necessary
local server/network permissions to separate sandbox failures from regressions.
