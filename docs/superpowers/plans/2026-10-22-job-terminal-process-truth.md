# Job Terminal Process and Outcome Truth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ensure Synlynk records worker cleanup and requested-effect verification as separate, evidence-backed facts, and never releases capacity while a worker may still execute.

**Architecture:** Add an explicit effect-state result to the job-truth ledger and preserve process state/termination-domain ownership alongside each daemon job. A shared lifecycle module will capture and terminate host process groups or container runtimes; every terminal writer will use it outside DB transactions, then atomically persist process state and reservation changes. A bounded, audited operator command resolves cleanup uncertainty without pretending termination was verified.

**Tech Stack:** Python 3, SQLite migrations, POSIX process groups, Docker CLI, pytest.

**Spec:** `docs/superpowers/specs/2026-10-22-job-terminal-process-truth-design.md`

## Global Constraints

- `termination_grace_seconds` defaults to 5 seconds; `cleanup_verification_timeout_seconds` defaults to 300 seconds; GitHub effect contracts keep a 300-second verification window.
- Never auto-release capacity while the process termination domain may still be live; only verified stop or an audited operator override releases it.
- Never hold a SQLite write transaction across process signaling, grace waits, container runtime calls, or effect verification.
- Never signal PID/PGID 0 or 1, the daemon's own group, the dispatcher group, a reused PID, or an unvalidated process group.
- Container cleanup must target the container, not only the Docker client; Local pilot cleanup uses the dispatch process group and releases its pilot lock only after verified process exit.
- Nested dispatches are separate jobs; parent cleanup cannot attest to child cleanup.
- Non-POSIX platforms without an equivalent safe termination primitive report `cleanup_unverified` rather than claiming success.
- Tests mock GitHub effects and container commands; no live GitHub writes or production container stops.
- Deduplicate the same causal evidence across reconciliation paths without collapsing distinct observations by second-level timestamps.

## Review Focus

- A process exits before termination-domain capture: record cleanup uncertainty and never guess a PGID; cover in `test_capture_domain_marks_already_exited_process_unverified`.
- A PID/PGID is reused or identity inspection fails: mismatch is never signaled and inspection errors retry only to the 300-second bound; cover in `test_terminate_domain_refuses_reused_or_unverifiable_identity` and `test_cleanup_inspection_error_expires_to_unknown`.
- A Docker client exits while its container remains alive: stop and verify the container itself before releasing capacity; cover in `test_container_domain_stops_runtime_not_client`.
- A partial external-effect event precedes a fully matching event, or the verifier raises: matching causal evidence can establish the effect, while observer errors remain unknown; cover in `test_later_complete_predicate_event_resolves_effect` and `test_verifier_exception_records_unknown_effect`.
- Legacy rows contain null deadlines or unmapped statuses: do not synthesize an expired deadline or crash on aliases; cover in `test_legacy_null_deadline_remains_unknown` and `test_legacy_status_aliases_project_without_error`.

---

### Task 1: Make effect decisions deadline-aware and explicitly separate

**Files:**
- Modify: `synlynk/job_truth.py`
- Modify: `synlynk/db_schema.py`
- Modify: `synlynk/db.py`
- Modify: `synlynk/job_status_projection.py`
- Test: `tests/test_job_truth.py`
- Test: `tests/test_job_status_projection.py`
- Test: `tests/test_db_migration.py`

**Interfaces:**
- `CompletionDecision` gains `effect_state: Literal["not_required", "verifying", "verified", "not_verified", "unknown"]`.
- `build_github_effect_contract(..., verification_deadline_seconds=300)` persists a UTC `verification_deadline_at`; `_contract_row` returns the persisted deadline without inventing one for legacy rows.
- `record_evidence_and_reconcile(..., manage_transaction: bool = True)` owns `BEGIN/COMMIT/ROLLBACK` only when `manage_transaction` is true; callers inside an outer transaction pass false.
- `project_job_status(conn, job_id)` adds `process_state` and `effect_state` while retaining existing compatibility fields.

- [ ] **Step 1: Write failing tests** for deadline creation/loading, null legacy deadlines, unknown-contract expiry, causal predicate grouping, `remote_effect`, verifier exceptions, effect-state projections, alias normalization (`done`, `failed_unverified`, `succeeded_gh_write_failed`), and transaction ownership.
- [ ] **Step 2: Run the focused tests** with `pytest -q tests/test_job_truth.py tests/test_job_status_projection.py tests/test_db_migration.py`; confirm the new cases fail for the current behavior.
- [ ] **Step 3: Add `effect_state` and deadline semantics** in `job_truth.py`; evaluate required predicates against a single causal observation/event, make unknown-contract expiry remain unknown/manual-review, and map legacy status aliases before canonicalization.
- [ ] **Step 4: Add the additive SQLite migration and compatibility adapter** for `job_terminal_decision.effect_state`; preserve existing rows as `unknown` where the old decision cannot prove an effect state, and normalize existing legacy status values without rewriting the raw historical status evidence.
- [ ] **Step 5: Make transaction ownership explicit** in `record_evidence_and_reconcile`; nested callers must not commit or roll back the outer transaction.
- [ ] **Step 6: Project both axes** from the daemon process state and latest effect decision; keep legacy status fields available.
- [ ] **Step 7: Run the focused tests** from Step 2; expect all new and existing cases to pass.
- [ ] **Step 8: Commit** as `fix: preserve independent job effect truth`.

### Task 2: Persist process state, termination domains, and parent lineage

**Files:**
- Modify: `synlynk/db_schema.py`
- Modify: `synlynk/db.py`
- Modify: `synlynk/dispatch.py`
- Modify: `synlynk/job_status_projection.py`
- Test: `tests/test_db_migration.py`
- Test: `tests/test_dispatch.py`
- Test: `tests/test_job_status_projection.py`

**Interfaces:**
- Add nullable/versioned `daemon_jobs.termination_domain_json`, `parent_job_id`, and `cleanup_deadline_at`; add `process_state TEXT NOT NULL DEFAULT 'unknown'`.
- Accepted process states: `running`, `stop_requested`, `stopped_verified`, `cleanup_unverified`, `cleanup_overridden`.
- Dispatch persistence stores `termination_domain_json` and `parent_job_id` in SQLite and the flat-file job record; child dispatches inherit `SYNLYNK_PARENT_JOB_ID` from the invoking job.

- [ ] **Step 1: Write failing migration and projection tests** for old daemon rows, versioned termination-domain JSON, process-state defaults, parent linkage, and both-axis status output.
- [ ] **Step 2: Run** `pytest -q tests/test_db_migration.py tests/test_job_status_projection.py tests/test_dispatch.py`; confirm the new schema/projection assertions fail.
- [ ] **Step 3: Add additive columns** through the canonical schema and migration/ensure-column paths; leave pre-existing jobs at `process_state='unknown'` without fabricating termination identity.
- [ ] **Step 4: Persist launch metadata** in daemon and flat-file records and propagate `SYNLYNK_PARENT_JOB_ID` only through the dispatch subprocess environment allowlist.
- [ ] **Step 5: Run the focused tests** from Step 2; expect migration compatibility and record round-trips to pass.
- [ ] **Step 6: Commit** as `feat: persist job process lifecycle state`.

### Task 3: Add one safe termination-domain implementation

**Files:**
- Create: `synlynk/process_lifecycle.py`
- Modify: `synlynk/container_exec.py`
- Modify: `synlynk/dispatch.py`
- Modify: `synlynk/config_schema.py`
- Test: `tests/test_process_lifecycle.py`
- Test: `tests/test_dispatch_container.py`

**Interfaces:**
- `capture_termination_domain(proc: subprocess.Popen, *, container_id: str | None = None, parent_job_id: str | None = None) -> dict` returns a versioned host-group or container domain plus leader identity; failed capture returns an explicit unknown domain.
- `terminate_job_domain(domain: Mapping[str, Any], *, grace_seconds: float = 5.0, inspect_process_group=..., signal_process_group=..., stop_container=..., inspect_container=...) -> TerminationResult` never reports `stopped_verified` until the owned domain is confirmed stopped.
- `TerminationResult` contains `process_state`, `attempted`, `method`, `reason_code`, and serializable evidence.
- Configuration defaults: `termination_grace_seconds=5`; `cleanup_verification_timeout_seconds=300`.

- [ ] **Step 1: Write failing unit tests** for own-group/PID 0/1/daemon-group rejection, reused-PID rejection, graceful-then-force escalation, verified death, inspection failure, non-POSIX behavior, and Docker-client/container distinction.
- [ ] **Step 2: Run** `pytest -q tests/test_process_lifecycle.py tests/test_dispatch_container.py`; confirm the new tests fail before implementation.
- [ ] **Step 3: Implement immutable termination-domain/result types** and `capture_termination_domain` in `synlynk/process_lifecycle.py`; capture host PGID immediately after spawn and bind it to PID identity.
- [ ] **Step 4: Implement verified host-group termination** with an injectable clock/inspection/signal boundary; refuse unsafe groups and return `cleanup_unverified` for identity mismatch or exhausted observer retries.
- [ ] **Step 5: Extend container wrapping** with a unique `--cidfile`; implement container stop/inspect using that identity and never equate Docker-client exit with container exit.
- [ ] **Step 6: Add and validate the two configuration defaults** in the canonical schema, preserving existing config files without rewrite.
- [ ] **Step 7: Run** `pytest -q tests/test_process_lifecycle.py tests/test_dispatch_container.py`; expect all termination-domain tests to pass.
- [ ] **Step 8: Commit** as `feat: safely terminate owned job domains`.

### Task 4: Route all dispatch and watchdog cleanup through the shared lifecycle

**Files:**
- Modify: `synlynk/dispatch.py`
- Modify: `synlynk/circuit_breaker.py`
- Modify: `synlynk/sentinel.py`
- Modify: `synlynk/container_exec.py`
- Test: `tests/test_dispatch.py`
- Test: `tests/test_circuit_breaker.py`
- Test: `tests/test_reconcile_circuit_breaker.py`
- Test: `tests/test_dispatch_container.py`
- Test: `tests/test_local_pilot_ledger.py`
- Test: `tests/test_sentinel.py`

**Interfaces:**
- `_check_job_stall` invokes `terminate_job_domain` and records `process_state` / cleanup evidence; it does not directly set a terminal status after merely sending a signal.
- `_kill_process_tree` becomes a compatibility adapter to `terminate_job_domain`; the `Popen` path receives no identity bypass.
- Sentinel verifies the owned termination domain after requesting cleanup; it reports cleanup as verified only after observing the domain stopped, otherwise it records `cleanup_unverified` and raises/retains an actionable alert.
- The Local pilot control lock remains held until the child process group is verified stopped; it does not define an alternate worker process identity.

- [ ] **Step 1: Add failing regressions** for stall-killing a parent with a child, circuit-breaker `Popen` identity verification, container cleanup after client loss, Local pilot lock retention until verified stop, and Sentinel's orphan cleanup path. Assert Sentinel does not treat a signal request or wrapper exit as verified cleanup, and retains an actionable alert when termination cannot be confirmed.
- [ ] **Step 2: Run** `pytest -q tests/test_dispatch.py tests/test_circuit_breaker.py tests/test_reconcile_circuit_breaker.py tests/test_dispatch_container.py tests/test_local_pilot_ledger.py tests/test_sentinel.py`; confirm the regression cases fail.
- [ ] **Step 3: Capture termination domains at spawn** and persist `process_state='running'` only after identity capture result is recorded.
- [ ] **Step 4: Replace direct PID kills** in stall and circuit-breaker flows with `terminate_job_domain`; persist stop-requested and final cleanup evidence separately.
- [ ] **Step 5: Replace direct PID signaling** in Sentinel orphan-cleanup paths with the shared helper. Require post-signal termination-domain observation before recording verified cleanup; preserve/raise an actionable alert for identity or observer uncertainty.
- [ ] **Step 6: Ensure child jobs inherit and persist parent linkage**; a parent cannot report full cleanup while any recorded child remains running or unresolved.
- [ ] **Step 7: Move external operations outside DB transactions**; signal/stop/inspect first, then persist process state and reservation changes.
- [ ] **Step 8: Run** the focused tests from Step 2; expect all cleanup paths to use the shared helper.
- [ ] **Step 9: Commit** as `fix: unify dispatch worker cleanup`.

### Task 5: Make reconciliation atomic, exhaustive, and capacity-safe

**Files:**
- Modify: `synlynk/jobs.py`
- Modify: `synlynk/job_truth.py`
- Modify: `synlynk/job_status_projection.py`
- Test: `tests/test_jobs.py`
- Test: `tests/test_job_truth.py`

**Interfaces:**
- `_settle_daemon_job_terminal` accepts an already-evaluated `process_state` and `effect_state`; its transaction updates process state, compatibility status, and reservation only after the external termination/effect checks have completed.
- `_release_daemon_job_reservation` is called only for `stopped_verified` or `cleanup_overridden`.
- `TERMINAL_WRITER_MANIFEST` registers flat-file stall, daemon, terminal JSON, zombie, circuit-breaker, cancellation, and stranded-story writers with their canonical adapters.

- [ ] **Step 1: Write failing tests** for transaction not held during grace, process/effect independence, idempotent dual reconcilers, evidence dedup across sources, reservation held for unknown cleanup, and complete terminal-writer manifest coverage.
- [ ] **Step 2: Run** `pytest -q tests/test_jobs.py tests/test_job_truth.py`; confirm the new race/accounting assertions fail.
- [ ] **Step 3: Refactor terminal reconciliation** so process cleanup and effect verification are observed outside write transactions and state projection/reservation updates commit atomically afterward.
- [ ] **Step 4: Apply retry/deadline behavior** to daemon and flat-file paths consistently, including unknown contracts and observer errors; preserve timeout/cancellation/forced-stop evidence when remote effects verify.
- [ ] **Step 5: Add stable per-kind evidence identities** and normalize all legacy aliases before canonical decision writes.
- [ ] **Step 6: Register every terminal writer** and make `validate_terminal_writer_manifest()` fail if any writer bypasses the shared process/effect adapters.
- [ ] **Step 7: Keep worktrees and logs until process/effect evidence and the state transition are durably recorded; only then run existing worktree cleanup.**
- [ ] **Step 8: Run** `pytest -q tests/test_jobs.py tests/test_job_truth.py`; expect the new transaction, concurrency, and accounting tests to pass.
- [ ] **Step 9: Commit** as `fix: reconcile job terminal facts atomically`.

### Task 6: Add bounded audited operator recovery for unresolved cleanup

**Files:**
- Modify: `synlynk/cli.py`
- Modify: `synlynk/jobs.py`
- Modify: `synlynk/job_status_projection.py`
- Modify: `docs/reference/commands.md`
- Test: `tests/test_jobs.py`
- Test: `tests/test_job_status_projection.py`

**Interfaces:**
- Add `synlynk jobs cleanup-resolve JOB_ID --accept-risk --reason TEXT`.
- The command is unavailable until `cleanup_verification_timeout_seconds` (300 seconds) has elapsed, requires a non-empty reason and explicit `--accept-risk`, records the invoking OS user and timestamp in append-only lifecycle evidence, sets `process_state='cleanup_overridden'`, and releases the reservation in the same transaction. It must not claim `stopped_verified` or rewrite effect state.

- [ ] **Step 1: Write failing CLI and DB tests** for missing acknowledgement/reason, early invocation, unknown job, successful audited override, idempotent repeat, reservation release, and preservation of unknown effect state.
- [ ] **Step 2: Run** `pytest -q tests/test_jobs.py tests/test_job_status_projection.py`; confirm the new command cases fail.
- [ ] **Step 3: Implement the CLI parser and handler** with explicit acknowledgement and timeout checks; append the actor/reason audit evidence before releasing capacity.
- [ ] **Step 4: Add the command's status output** showing `cleanup_overridden` separately from verified process stop and effect state.
- [ ] **Step 5: Document** the exact warning, preconditions, and examples in `docs/reference/commands.md`.
- [ ] **Step 6: Run** the focused tests from Step 2; expect the audit and reservation assertions to pass.
- [ ] **Step 7: Commit** as `feat: add audited job cleanup recovery`.

### Task 7: Verify integrated behavior and release readiness

**Files:**
- Modify: tests listed below as needed
- Modify: `docs/superpowers/specs/2026-10-22-job-terminal-process-truth-design.md` only if implementation reveals a necessary approved-spec correction; otherwise do not change it.

- [ ] **Step 1: Add the incident-shaped end-to-end regression**: a wrapper exits, its child survives, and the expected GitHub effect is independently verified; assert process state, effect state, legacy status projection, reservation, and evidence history are all correct.
- [ ] **Step 2: Run focused integration suites:** `pytest -q tests/test_job_truth.py tests/test_job_status_projection.py tests/test_db_migration.py tests/test_process_lifecycle.py tests/test_dispatch.py tests/test_dispatch_container.py tests/test_circuit_breaker.py tests/test_reconcile_circuit_breaker.py tests/test_jobs.py tests/test_local_pilot_ledger.py`.
- [ ] **Step 3: Run the full repository suite** with `pytest -q`; report any pre-existing sparse-checkout failures separately and do not waive failures introduced by this branch.
- [ ] **Step 4: Run static checks** `ruff check synlynk tests` and `git diff --check`.
- [ ] **Step 5: Verify the acceptance matrix** against every numbered criterion in the spec and attach results to #2530.
- [ ] **Step 6: Verify Sentinel cleanup truth independently**: signal-requested, leader-exited/child-live, observer-error, and domain-stopped cases must project respectively as unverified, unverified, unverified, and verified; confirm unresolved cases remain visible as actionable Sentinel alerts.
- [ ] **Step 7: Commit** remaining test-only work as `test: verify job terminal truth end to end`.
