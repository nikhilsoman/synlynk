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
3. All terminal writers use one documented decision/settlement policy. A zero/nonzero wrapper exit is evidence, not a substitute for the declared job effect contract.
4. A required external effect (for example, a GitHub comment/review/PR operation) is verified against its target and expected actor/time/other declared predicates before the job receives a verified-completion status.
5. Inconclusive effect verification remains non-terminal (`verifying`/`unknown`) while the configured retry/deadline budget remains; after exhaustion, it becomes the existing explicit `failed_verification` / manual-review outcome, never an unqualified `failed` or `done` inferred from missing evidence.
6. Preserve useful compatibility projections and existing cost/reservation accounting while ensuring only one terminal decision wins concurrent reconciliation.

## Non-goals

- Redesigning all job-effect contracts or adding new external providers beyond the existing contract/evidence model.
- Changing the user-facing meanings of successful, no-op, permission-denied, or circuit-breaker statuses beyond correcting false certainty.
- Automatically retrying the harness task or replaying a GitHub write.
- Changing release policy or broadening this issue into the full job-status UI roadmap.

## Proposed behavior

### Process ownership and cleanup

- At dispatch, persist enough immutable launch identity to identify the worker's owned process group/session (including the group/session identifier and leader identity, with a versioned representation for legacy rows).
- Centralize termination in one helper used by stall, circuit-breaker, cancellation, and orphan/zombie paths. The helper first validates dispatch-time identity and ownership, sends a graceful termination signal to the owned group, waits a bounded grace period, escalates to forceful termination if needed, and verifies that the owned group is gone.
- Never infer ownership from a PID number alone. Do not signal a group if its identity cannot be validated or if the platform/process metadata does not support a safe ownership check. Legacy records without group identity use the safest existing leader-only behavior and remain explicitly marked as cleanup-unverified if descendants cannot be ruled out.
- Only settle the job as terminated after cleanup verification. If termination is uncertain, leave it in an explicit non-terminal/reconciliation-needed state, retain relevant capacity reservations as current policy requires, and emit an actionable alert with job id and evidence. Do not silently release capacity while an owned worker may still run.

### Outcome and side-effect truth

- Route terminal candidates from flat-file reconciliation, daemon reconciliation, stall/circuit-breaker paths, and zombie cleanup through the canonical job-truth decision and one atomic terminal settlement gate.
- Capture process exit, process-group cleanup, local worktree evidence, declared external-effect verification, and observer errors as distinct evidence; do not collapse observer failure into “effect absent”.
- For known contracts, require every declared predicate before projecting verified completion. Keep retries bounded and deadline-aware. When evidence remains inconclusive at the budget boundary, settle to the existing explicit verification-failure/manual-review outcome and preserve the evidence trail.
- For `unknown_contract`, do not claim external delivery or confidently classify a required effect as absent. Keep the result unknown/verifying until the existing verification policy can resolve it or its budget expires; then expose manual review. A separately verified independent effect may still establish completion only if it satisfies a declared contract and its predicates.
- Maintain backward-compatible status fields only as projections of the canonical decision; neither flat-file JSON nor daemon SQLite may overwrite a newer terminal decision with a weaker observation.

## Concurrency, recovery, and safety

- The daemon's existing terminal claim / compare-and-set settlement remains the serialization boundary; all writers must use it (or an equivalent atomic adapter) before cleanup that deletes worktrees or releases reservations.
- Reconciliation must be idempotent across daemon restart and repeated observations. Evidence events need stable deduplication keys so retries do not inflate or contradict the ledger.
- Process-group cleanup and effect verification are separate facts: a confirmed GitHub effect does not prove the worker stopped, and a stopped worker does not prove its requested effect landed.
- Do not delete worktrees or logs until terminal state and required cleanup evidence have been durably recorded.

## Acceptance criteria

1. A regression test starts a dispatch-owned parent and child in one session, triggers timeout/stall cleanup, and proves both are gone before terminal status is committed.
2. A reused leader PID or mismatched process-group identity is never signaled; the job remains visibly unresolved and emits cleanup uncertainty.
3. A process that ignores graceful termination is forcefully stopped within the configured bound, and the terminal record reflects the verified cleanup result.
4. A required GitHub side effect that landed despite a wrapper failure is classified from verified target/actor/time evidence; a failed/unavailable observer does not become “not delivered”.
5. A missing/unknown effect contract does not produce a falsely confident `done` or `failed` outcome; bounded exhaustion produces explicit verification failure/manual review.
6. Flat-file and daemon reconciliation produce the same canonical decision for the same evidence, including concurrent/replayed reconciliation.
7. Existing daemon reservations, cost accounting, events, and compatibility projections remain consistent on success, failure, and unresolved cleanup/verification.
8. Focused tests cover stall, circuit breaker, cancellation, zombie reaping, GitHub verification, legacy rows, daemon restart, and terminal-writer concurrency; the full relevant job/dispatch suites pass.

## Test strategy

Use deterministic subprocess fixtures for process-group ownership and termination, with platform guards where process-group semantics differ. Unit-test evidence precedence and retry/deadline behavior through `job_truth`; integration-test both flat-file and daemon reconciliation against the same evidence matrix. Include races between late exit markers, terminal claims, and group cleanup. Never depend on live GitHub writes in tests; mock verifier outcomes and assert the persisted evidence/status pair.

## Open design questions for Architect review

1. Should unsafe legacy jobs without a persisted group identity remain leader-only with an explicit cleanup warning, or should they remain non-terminal until an operator confirms descendants are gone?
2. Should cleanup uncertainty have a dedicated canonical status, or should it reuse `verifying` plus a distinct cleanup evidence/reason code?
3. Is the existing bounded GitHub verifier sufficient for this issue, with `job_truth` becoming the only terminal arbiter, or should contract deadline/retry state be consolidated as part of this change?
4. Which legacy status aliases must remain writable for one migration window versus read-only projections immediately?

## Rollout and migration

No destructive data migration is proposed. New dispatches persist versioned process-group identity. Existing rows are handled conservatively based on available PID identity and are never retroactively treated as proof that descendants were stopped. Ship behind no new user-facing toggle unless implementation uncovers an unavoidable platform-specific risk; if a compatibility guard is needed, its default and removal criterion belong in the implementation plan.

## References

- #2530 — dispatch tracker status mismatch and orphaned process
- #2465 — v0.25.2 stability/release gate
- `synlynk/dispatch.py::_check_job_stall`
- `synlynk/jobs.py::_verify_daemon_terminal_status` and `_reconcile_daemon_jobs`
- `synlynk/circuit_breaker.py::_kill_process_tree`
- `synlynk/job_truth.py::decide_job_outcome`
