# Job Terminal Process and Outcome Truth — Design

**Status:** Draft for independent Architect review; not approved for implementation  
**Tracking:** [#2530](https://github.com/synlynk/synlynk/issues/2530), v0.25.2 stability gate [#2465](https://github.com/synlynk/synlynk/issues/2465)

## Intent

Make dispatch terminalization trustworthy in both directions: once Synlynk records a job as terminal, the job's owned worker process tree must no longer be executing; and the recorded outcome must reflect verified effects, not merely a wrapper exit code or an incomplete/unknown effect contract. This addresses the orphaned-process and false-negative-status symptoms tracked together in #2530.

## Context and observed behavior

- Dispatch starts the harness with `start_new_session=True` (`synlynk/dispatch.py`) but persists the leader PID and PID identity, not an explicit process-group ownership record.
- The stalled-job path in `_check_job_stall` identity-checks and sends `SIGKILL` to that one PID. A child harness can survive its leader and continue consuming resources or performing side effects.
- The circuit-breaker module has a separate `_kill_process_tree` helper, but its ordinary PID path still signals one PID; dispatch can also provide a `Popen` handle. Cleanup semantics therefore differ between paths.
- Daemon reconciliation calls `_verify_daemon_terminal_status` and defers some unknown GitHub-write checks before settling. The flat-file stall path and other terminal writers do not all share that complete verification/settlement sequence.
- `job_truth.decide_job_outcome` already models `unknown`/`verifying` as non-terminal projections and has an explicit `unknown_contract` outcome. Legacy or missing contracts can therefore remain unresolved instead of justifying a confident success/failure label.
- Baseline: `pytest -q tests/test_jobs.py tests/test_dispatch.py` passed, 371 tests, on 2026-10-22.

The incident recorded in #2530 reports a Grok job whose GitHub comment landed although its job was classified `timed_out`/`unknown_contract`; the wrapper exited but its harness process remained alive until manually stopped. This design treats that report as the motivating case; implementation must add a reproducible regression test and must not rely on the incident alone as process-ownership proof.

## Goals

1. A terminal transition caused by timeout, stall, cancellation, circuit breaker, or zombie cleanup does not leave a process in the dispatch-owned process group running.
2. Cleanup is fail-closed: Synlynk never signals a reused PID or an unowned process group; if ownership or termination cannot be established, it records an explicit cleanup/verification-pending condition and alerts rather than claiming successful cleanup.
3. Track worker/process cleanup and requested-effect verification as independent facts. A confirmed stop does not prove an effect landed, and a verified effect does not prove the worker stopped.
4. All terminal writers use one documented decision/settlement policy. A zero/nonzero wrapper exit is evidence, not a substitute for the declared job effect contract.
5. A required external effect (for example, a GitHub comment/review/PR operation) is verified against its target and expected actor/time/other declared predicates before the job receives a verified-effect state.
6. Inconclusive effect verification is never collapsed into “effect absent”. The effect axis remains `verifying`/`unknown` while its explicit retry/deadline policy allows; exhaustion leads to manual review with unknown evidence, not a fabricated failed-delivery fact.
7. Preserve useful compatibility projections and existing cost/reservation accounting while ensuring each process-state and effect-state transition is serialized and idempotent.

## Non-goals

- Redesigning all job-effect contracts or adding new external providers beyond the existing contract/evidence model.
- Changing the user-facing meanings of successful, no-op, permission-denied, or circuit-breaker statuses beyond correcting false certainty.
- Automatically retrying the harness task or replaying a GitHub write.
- Changing release policy or broadening this issue into the full job-status UI roadmap.

## Proposed behavior

### Process ownership and cleanup

- At dispatch, persist a versioned termination-domain record: host process group/session, container/runtime handle, or local-pilot handle, plus immutable launch identity. Capture it immediately after launch and before recording the job as fully running. If capture fails or the leader has already exited, record cleanup as unknown; do not infer group ownership later from a PID alone.
- Centralize termination in one helper used by stall, circuit-breaker, cancellation, and orphan/zombie paths. The helper first validates dispatch-time identity and ownership, sends a graceful termination signal to the owned group, waits a bounded grace period, escalates to forceful termination if needed, and verifies that the owned group is gone.
- Never infer ownership from a PID number alone. Refuse to signal PID/PGID 0 or 1, the daemon's own process group, or the dispatcher/daemon group; verify the target is still the dispatch-owned domain immediately before signaling.
- The container termination verb must stop the container itself (not just its client process); local-pilot termination must target its runner handle. A nested dispatch is an independent job/session: parent cleanup must not claim child cleanup, and child jobs must be reconciled through their own persisted termination domains. Parent/child relationships must be observed so the parent is not reported fully cleaned up while an owned child job remains active.
- Legacy rows without a termination-domain record may use identity-checked leader-only cleanup, but must keep `process_state=cleanup_unverified` if descendants cannot be ruled out. Non-POSIX hosts must report the same explicit uncertainty when safe group termination is unavailable; they must not silently claim group cleanup.
- Cleanup identity checks distinguish mismatch from observer failure. A mismatch is never signaled; a transient inspection error is retried within a bounded cleanup-verification budget and then recorded as unknown with an alert.
- Capacity reservations are tied to the process axis: release only when the worker termination domain is verified stopped or an explicitly audited operator recovery action accepts the residual risk. Do not retain capacity indefinitely without an escalation deadline; after the configured bound, surface a manual recovery action and alert, but do not auto-release while the worker may still execute.

### Outcome and side-effect truth

- Represent `process_state` (at minimum: `running`, `stop_requested`, `stopped_verified`, `cleanup_unverified`) separately from `effect_state` (at minimum: `not_required`, `verifying`, `verified`, `not_verified`, `unknown`). Existing job `status` remains a compatibility projection that can express an observed timeout/failure while the effect axis is still unknown; it must never imply verified delivery or verified cleanup unless both facts are supported.
- Route process-lifecycle transitions from flat-file reconciliation, daemon reconciliation, stall/circuit-breaker paths, and zombie cleanup through one process-state transition policy. Route requested-effect evidence through `job_truth`; do not hold a process cleanup transition or capacity release hostage to an unrelated effect retry.
- Capture process exit, termination-domain cleanup, local worktree evidence, declared external-effect verification, and observer errors as distinct evidence; do not collapse observer failure into “effect absent”.
- For known contracts, require all declared predicates within a single causal observation (or a set explicitly tied to the same event) before projecting verified effect. Fix predicate evaluation so one incomplete/false-positive event cannot veto a later complete matching event, and so supported `remote_effect` evidence is not left permanently in `verifying`.
- Persist an actual `verification_deadline_at` when a contract is created and reconstruct it consistently when loading the contract. Keep retries bounded and deadline-aware. For `unknown_contract`, exhaustion means “effect remains unknown; manual review required,” not verified absence or generic task failure. Process facts such as timeout, cancellation, or circuit-breaker termination must still be preserved on the process/status projection even when the effect contract is unknown.
- Ensure any verified remote effect does not erase evidence that the worker was cancelled, timed out, or forcibly stopped. Keep both facts visible.
- Maintain backward-compatible status fields only as projections of canonical process/effect state; neither flat-file JSON nor daemon SQLite may overwrite a newer observation with a weaker one. Normalize all currently emitted aliases (`done`, `failed_unverified`, `succeeded_gh_write_failed`) before passing them to `canonical_status`, with an explicit migration/compatibility policy for persisted rows.

## Concurrency, recovery, and safety

- Never hold a SQLite write transaction or terminal claim across process termination grace periods, runtime stop calls, or external verification. Gather/verify cleanup first, then record its evidence and commit the relevant state transition. Keep the process-state transition and reservation release atomic with each other.
- Effect ledger decision and compatibility projection must use an explicit transaction ownership/nesting contract; do not allow `record_evidence_and_reconcile` to commit independently from an outer reconciliation transaction or roll back unrelated work on a shared connection.
- Register stall, circuit-breaker, cancellation, daemon, flat-file, and zombie terminal writers in `TERMINAL_WRITER_MANIFEST` (or a successor exhaustive registry) and ensure each delegates through the canonical adapters.
- Reconciliation must be idempotent across daemon restart and repeated observations. Define stable deduplication identity per evidence kind so the same observation from flat-file and daemon paths cannot count twice, while distinct observations are not collapsed by second-level timestamps.
- Process-group cleanup and effect verification are separate facts: a confirmed GitHub effect does not prove the worker stopped, and a stopped worker does not prove its requested effect landed.
- Do not delete worktrees or logs until terminal state and required cleanup evidence have been durably recorded.

## Acceptance criteria

1. A regression test starts a host worker and child, triggers stall/timeout cleanup, and proves the owned termination domain is stopped before `process_state=stopped_verified` or capacity release is committed.
2. Tests prove reused identities, PGID 0/1, and the daemon/dispatcher process group are never signaled; a PID-inspection error is retried and ends as explicit cleanup uncertainty within a bounded deadline.
3. A worker that ignores graceful termination is forcefully stopped and death is verified within a configurable grace bound; the `Popen` handle path uses the same ownership checks and never reports success merely because a signal was sent.
4. Container and local-pilot tests verify the actual runtime worker is stopped, not only its client process. A nested dispatch test verifies parent status does not falsely attest to cleanup of an active child job.
5. No SQLite write transaction is held across the graceful wait/escalation period, container-stop call, or external verification. Process cleanup evidence and capacity release are persisted atomically.
6. A required GitHub side effect that landed despite wrapper failure is represented as verified effect plus the independent timeout/stop facts; a failed/unavailable observer produces unknown evidence, not “not delivered”.
7. An unknown/missing effect contract retains `effect_state=unknown` after bounded expiry and requires manual review, while known process facts remain visible. Tests cover actual persisted deadline creation/loading and budget expiry.
8. Mixed evidence tests cover a partial event followed by a complete matching event, unrelated predicate mismatches, `remote_effect` evidence, and duplicate observations from both reconcilers.
9. Legacy aliases (`done`, `failed_unverified`, `succeeded_gh_write_failed`) are safely normalized for existing rows and future writes; no live row causes `canonical_status` to raise during reconciliation.
10. `TERMINAL_WRITER_MANIFEST` (or replacement validation) includes stall, circuit-breaker, cancellation, daemon, flat-file, and zombie writers.
11. Existing daemon reservations, cost accounting/outbox, events, and compatibility projections remain consistent on success, failure, and unresolved cleanup/verification. Unresolved process cleanup does not create a terminal cost outbox event or release capacity while the worker might still execute.
12. Focused tests cover all supported termination domains, legacy rows, daemon restart, transaction rollback/ownership, and terminal-writer concurrency; the full relevant job/dispatch suites pass.

## Test strategy

Use deterministic subprocess fixtures for process-group ownership and termination, and fakes for container/local-pilot termination domains. On non-POSIX hosts, assert explicit cleanup uncertainty when a safe termination primitive is unavailable. Unit-test evidence precedence and retry/deadline behavior through `job_truth`; integration-test both flat-file and daemon reconciliation against the same evidence matrix. Include races between late exit markers, process cleanup, transaction boundaries, and reconciliation. Test verifier exceptions as `observer_error`, not effect absence. Never depend on live GitHub writes in tests; mock verifier outcomes and assert the persisted process/effect state pair.

## Open design questions for Architect review

1. What is the maximum cleanup-uncertainty age and which audited operator action resolves it? Capacity must not be released automatically while a worker might still be live; an operator override must record the accepted risk and actor.
2. Keep cleanup uncertainty as process-axis state/evidence (`cleanup_unverified`) rather than adding a canonical job status, unless the cost-outbox impact of changing `TERMINAL_STATUSES` is explicitly analyzed.
3. The existing GitHub verifier is not sufficient unchanged: the implementation must persist/load deadlines, define unknown-contract expiry, correct predicate/event matching, and unify observer-error evidence. Should that contract fix live in #2530 or a directly adjacent prerequisite story?
4. Confirm the compatibility/migration approach for `failed_unverified` and `succeeded_gh_write_failed`, which live writers emit but `canonical_status` currently rejects.

## Rollout and migration

No destructive data migration is proposed. New dispatches persist a versioned termination-domain record. Existing rows are handled conservatively based on available PID identity and are never retroactively treated as proof that descendants were stopped. Existing contract deadlines that are null remain unknown; do not synthesize a past deadline and falsely classify effects as absent. Ship behind no new user-facing toggle unless implementation uncovers an unavoidable platform-specific risk; if a compatibility guard is needed, its default and removal criterion belong in the implementation plan.

## References

- #2530 — dispatch tracker status mismatch and orphaned process
- #2465 — v0.25.2 stability/release gate
- `synlynk/dispatch.py::_check_job_stall`
- `synlynk/jobs.py::_verify_daemon_terminal_status` and `_reconcile_daemon_jobs`
- `synlynk/circuit_breaker.py::_kill_process_tree`
- `synlynk/job_truth.py::decide_job_outcome`
