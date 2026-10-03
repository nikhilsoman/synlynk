# Implementation Plan: Job Status Truth Pilot

> Design: `docs/superpowers/specs/2026-10-03-job-status-truth-and-structured-completion-design.md`
>
> Tracking: issue #1933 / GOVERNS story `story-issue-1933`; cost-audit
> redesign remains independent under issue #1951.

## Objective

Implement the first production-safe slice of the job-status truth design so a
remote-only GitHub write cannot be reported as `TASK_DELIVERY_FAILED` merely
because the local receipt or diff is absent. The pilot will introduce durable
effect contracts and evidence, route terminal decisions through one oracle,
and preserve existing CLI compatibility while measuring disagreements before
the legacy paths are retired.

The pilot is deliberately limited to dispatch jobs with GitHub effects and
the existing `verify_effects.py` integration. It does not redesign pricing,
token attribution, or cost reconciliation; those are referenced at the
decision-revision boundary and tracked by #1951.

## Constraints and invariants

- The canonical SQLite ledger is the only writer that may settle terminal
  status.
- Evidence observations are append-only and cannot directly overwrite status.
- A verified remote effect outranks missing receipt, no local diff, exit code,
  regex output, liveness, and cost sentinel evidence.
- A first remote read miss is `verifying`, not failure; verification uses a
  bounded retry/quorum policy and records the reason for every attempt.
- Effect contracts are immutable after dispatch and conjunctive: all required
  predicates must pass before `completed` is allowed.
- Existing status aliases remain available only at the API/CLI boundary.
- The pilot runs in shadow mode first; legacy classification remains the
  displayed result until promotion criteria are met.
- Cost audit remains an independent subsystem. Only the job decision revision
  identifier is shared with #1951.

## Work breakdown

### 1. Inventory terminal writers and define the pilot contract

Files to inspect/change:

- `synlynk/dispatch.py` — dispatch context and GitHub-write metadata.
- `synlynk/jobs.py` — legacy and daemon reconciliation paths.
- `synlynk/daemon.py` — SQLite `daemon_jobs` lifecycle updates.
- `synlynk/verify_effects.py` — current effect verification predicates.
- `synlynk/db.py` — canonical schema/migration helpers.

Tasks:

1. Enumerate every path that currently writes `done`, `failed`,
   `permission_denied`, timeout/zombie, or delivery-failure status.
2. Add a versioned GitHub effect-contract builder for review, comment, PR, and
   issue operations. Persist target, expected actor/role, expected SHA/id,
   receipt policy, verification deadline, and required predicates.
3. Define explicit legacy defaults for existing jobs. Missing contracts must
   be represented as `unknown_contract`, never inferred as success.
4. Add migration/backfill code that is idempotent and does not rewrite prior
   terminal history.

Verification: schema migration tests, contract serialization round trips,
legacy-job backfill tests, and an inventory test that fails if a new terminal
writer bypasses the shared decision entry point.

### 2. Add append-only evidence and terminal-decision records

Files to inspect/change:

- `synlynk/db.py` — tables, indexes, and atomic transition transaction.
- A focused module under `synlynk/` for evidence/decision projection (name to
  follow existing package conventions after the inventory).

Tasks:

1. Add `job_effect_contract`, `job_evidence`, and `job_terminal_decision`
   tables with job/revision foreign-key relationships, timestamps, actor,
   source, evidence kind, confidence, and reason fields.
2. Implement one transactional `record_evidence_and_reconcile()` entry point
   that claims the current revision, evaluates the contract, and writes a
   terminal decision atomically.
3. Make terminal decisions monotonic. Contradictory later observations create
   a correction revision and preserve the original decision and evidence IDs.
4. Add idempotency keys for repeated webhook/read/reconciliation observations.
5. Ensure concurrent dispatch reconciliation cannot create two terminal
   decisions for one job revision.

Verification: SQLite concurrency tests, duplicate-evidence tests, correction
revision tests, rollback tests, and invariant tests for one terminal writer.

### 3. Make `verify_effects.py` the pilot completion oracle

Files to inspect/change:

- `synlynk/verify_effects.py`.
- `synlynk/jobs.py` reconciliation callers.
- `synlynk/sentinel.py` circuit-breaker and timeout callers.

Tasks:

1. Return structured tri-state evidence (`true`, `false`, `unknown`) with
   source, target, actor, observed timestamp, relevant SHA/id, and retry
   metadata instead of only a boolean/result string.
2. Add causal attribution checks for GitHub observations: expected actor,
   target, start-time lower bound, and matching head/review/comment identity.
3. Implement bounded read-after-write retry and pagination/quorum checks. A
   single unavailable or empty read remains `verifying`.
4. Express completion as the minimum of all contract predicates. Missing
   receipt is an evidence flag, not an automatic delivery failure when the
   remote effect is verified.
5. Convert circuit-breaker, timeout, zombie, and permission observations into
   evidence events. They may explain or stop work, but may not settle a
   contradictory verified effect.

Verification: extend `tests/test_verify_effects.py` with remote-only review,
actor mismatch, SHA mismatch, first-read miss, eventual consistency, repeated
read, and circuit-breaker precedence fixtures.

### 4. Emit structured lifecycle telemetry and retain compatibility fallback

Files to inspect/change:

- `synlynk/dispatch.py` — launch/observe/finalize events.
- harness adapter/output handling used by the dispatch runner.
- `synlynk/jobs.py` and `synlynk/daemon.py` — event ingestion.

Tasks:

1. Emit versioned lifecycle events for `queued`, `running`, `observing`,
   `verifying`, terminal decision, and correction revision.
2. Include job ID, contract ID/version, event ID, sequence number, harness,
   role, process result, and evidence references in every event.
3. Treat `SYNLYNK_TASK_RECEIVED` and legacy stdout parsing as compatibility
   evidence only. Record parse failures without allowing them to override a
   verified effect.
4. Make event ingestion idempotent and reject out-of-order events without
   losing the observation for later reconciliation.

Verification: event schema tests, duplicate/out-of-order ingestion tests,
legacy log compatibility tests, and a regression fixture reproducing the
`job-726172fb`/QA-review false-failure pattern.

### 5. Add shadow status projection and product surfaces

Files to inspect/change:

- `synlynk/jobs.py` CLI rendering and JSON output.
- `synlynk/status.py`/observatory projections as applicable.
- policy/review consumers that read job status directly.

Tasks:

1. Add a machine-readable projection containing canonical status, lifecycle
   state, evidence summary, contract predicates, verification confidence,
   decision revision, and correction history.
2. Keep legacy aliases at the presentation boundary and expose the canonical
   value alongside them.
3. Add a shadow comparison showing legacy vs oracle decisions, with reason
   codes and no status mutation during the pilot.
4. Add metrics for false failure, false success, unknown/verifying age,
   verification retries, contract-missing jobs, and disagreements by harness
   and effect kind.

Verification: CLI snapshot/JSON tests, policy consumer compatibility tests,
projection determinism tests, and metric-label cardinality checks.

### 6. Roll out behind explicit gates

Rollout order:

1. Enable schema/evidence writes and shadow oracle for all new dispatches.
2. Replay the known incident fixtures, including the `job-726172fb`
   remote-review false-failure case, and a representative sample of at least
   100 jobs per effect class. Require zero replay-corpus false negatives, zero
   unexplained terminal-status disagreements, and documented explanations for
   every expected compatibility difference.
3. Promote GitHub review/comment effects to oracle-authoritative status for a
   bounded cohort.
4. Require the pilot to meet all promotion gates: at least 99% verified
   terminal-decision agreement on the eligible sample, zero unclassified
   required-GitHub decisions, no unbounded `verifying` jobs, and no terminal
   decision race in concurrency tests. Jobs from unavailable harnesses are
   excluded from the denominator only when their exclusion is recorded with a
   reason and reported separately; they must not disappear from the corpus.
5. Only then route the remaining GitHub effects and eventually other effect
   kinds through the oracle. Retire split-brain writers in a follow-up change.

Operational safeguards: feature flag, migration rollback procedure, bounded
verification deadline, alert on unknown/verifying age, and a documented
manual reconciliation command that appends evidence rather than editing
status directly. Roll back a cohort to shadow mode and block promotion when
any unexplained disagreement, replay false negative, unclassified required
decision, verification-age SLO breach, terminal race, or failed live trial is
observed. The QA/merge reviewer owns the stop decision; the implementation
owner disables the cohort flag and records the evidence revision that caused
the rollback.

## Test and acceptance matrix

### Unit and database tests

- Contract validation and immutable versioning.
- Evidence append/idempotency and terminal-decision atomicity.
- Precedence: verified remote effect over absent receipt/no diff/exit code.
- Unknown propagation, retry budget, hard max age, and correction revisions.
- Concurrent reconciliation and single-writer enforcement.
- Terminal-writer manifest enforcement: every known terminal writer must call
  the shared decision entry point, and the test must fail when a new writer is
  added without registration.

### Integration tests

- Dispatched GitHub review with no local diff reaches `completed` when the
  review is causally verified.
- Review write followed by one unavailable read reaches `verifying`, then
  completes after bounded read-after-write retry.
- Actor/SHA/target mismatch does not promote completion.
- Missing receipt plus verified effect is a warning evidence dimension, not a
  delivery failure.
- Circuit breaker or permission evidence cannot overwrite a verified effect.
- Legacy text-only dispatch remains observable and is marked compatibility
  fallback.
- Replay fixtures for the known incident corpus, including `job-726172fb`,
  assert no false negative for a causally verified remote effect.
- A parity fixture runs the oracle beside both existing reconciliation paths
  and records every expected/ unexpected disagreement before end-to-end
  routing is enabled.

### Live acceptance

- Run `synlynk pr check` from the PR worktree for the implementation PR.
- QA reviewer independently runs the same check and performs the merge gate.
- Validate a real remote-only QA review and confirm CLI/API agree on the
  canonical status and evidence.
- Confirm cost rows are keyed by `(job_id, decision_revision)` and that no
  cost-audit failure changes the job terminal status; detailed cost redesign
  remains #1951.
- Assert independent ground truth for each live required GitHub effect: the
  observed actor, target, and SHA/id must match the dispatch contract, and no
  terminal decision may remain unclassified.

## Deliverables and sequencing

Before implementation dispatch, the branch must contain the following
checked-in gates: the terminal-writer manifest and its enforcement test; the
known-incident replay fixtures; a closed status enum, alias map, and executable
truth table; causal attribution/quorum rules with a hard maximum verification
age; and per-harness/per-effect reporting. The implementation PR must also
include the parity test against both existing reconciliation paths before
GitHub review routing is enabled.

1. This plan committed on the plan branch and linked to the approved design.
2. Implementation PR 1: schema, contracts, evidence ledger, and oracle with
   unit/concurrency tests.
3. Implementation PR 2: structured telemetry ingestion and GitHub effect
   adapters with integration fixtures.
4. Implementation PR 3: shadow projection, CLI/API surfaces, metrics, and
   rollout controls.
5. Follow-up implementation for #1951 after the status pilot ships: cost
   attribution, pricing, aggregation, budget, retention, and correction
   workflows independent of terminal job status.

No implementation dispatch should begin until this plan is committed and the
implementation task is attached to the ready GOVERNS story.
