<!-- generated - source of truth is state.db -->
---
decision_id: dec-5d37b005
topic: "Review PR #1949 design: Job Status Truth and Structured Completion Oracle. Evaluate whether the design fully addresses the flaky job-status incidents and Five-POV feedback, identify missing invariants, rollout risks, and concrete changes required before implementation. Three-harness fallback because Agy credits are unavailable."
date: 2026-10-03
panel: [claude, codex, grok]
status: approved
---

## Topic
Review PR #1949 design: Job Status Truth and Structured Completion Oracle. Evaluate whether the design fully addresses the flaky job-status incidents and Five-POV feedback, identify missing invariants, rollout risks, and concrete changes required before implementation. Three-harness fallback because Agy credits are unavailable.

## Panel Inputs

### claude
[model=sonnet; version=2.1.284 (Claude Code)]

**Position: approve the direction, but request amendments before an implementation plan is written.** I read the first ~400 lines of the spec (§1–11). I did not read the migration phases or the live acceptance matrix, so those are not reviewed.

**What it gets right.** The spec diagnoses the incident class correctly. In #1377, #1429, #1896 and `job-726172fb`, a cheap proxy overwrote stronger or unresolved evidence. The fixes are sound:
- evidence and status are separate, and uncertainty stays `unknown`;
- the task carries an effect contract;
- a single writer settles terminal status;
- receipts are demoted to evidence.

That covers the Five-POV architect and developer asks.

**Missing invariants:**
1. **Verify only what the task caused.** "Verified matching review" needs a definition. The oracle must bind the effect to the job: author identity, a timestamp after job start, and the exact target. Otherwise an unrelated pre-existing review on PR #1947 yields a false `completed`.
2. **Retry budget and verification deadline.** The spec doesn't say what happens to a job stuck in `verifying` if the daemon dies. A job needs a hard maximum age. After that, it goes to `failed_verification`, and the transition is idempotent.
3. **Revision semantics.** The spec allows late-evidence corrections but doesn't say whether policy gates, merge authority and cost rows follow the latest revision. A merge must never rely on a superseded decision.
4. **The oracle cannot be fooled by the agent.** Agents can write the `structured_event` and receipt evidence, so those two kinds can never raise confidence above what the GitHub or git checks establish.
5. **State-name inconsistency.** The lifecycle uses `failed_verification`, but the rules table also uses `failed_noop_denied` and `circuit_breaker_tripped`, which aren't in the lifecycle. Pick one closed enum.
6. **Contract creation.** Who writes the contract for ad-hoc and legacy dispatches? The spec needs a default (`read_only_report`/`unknown`) and a clear rule for jobs with no contract.

**Rollout risks:**
- Two ledgers during migration: JSON, `daemon_jobs` and the new tables need an explicit cutover and a shadow mode.
- Status-rename churn for Vizor and `status --json`: version the contract.
- Rate limits and read-after-write lag: GitHub verification can look like a failure.
- The #1937 cost concern: verification calls and retries need a cap.
- Evidence-table growth, given the 7GB `state.db` shards in #1831.

**Required changes:**
- Add a **shadow phase**: the oracle runs alongside the legacy writers and logs disagreements. Cut over only after N jobs with zero unexplained diffs.
- Make an **independent ground-truth audit** part of the acceptance bar, as the VC POV requires. That means replaying `job-726172fb`, #1429 and #1896 as fixtures.
- Add an **inventory of every status writer** as a gating deliverable of phase 1.
- Fold in the invariants above and the single enum.

I'd approve once these amendments land, and I'd merge the spec only after the non-authoring reviewer runs `synlynk pr check`.

### codex
[model=default; version=codex-cli 0.160.0]

PR #1949 addresses the core failure mode correctly: it separates observations from status, makes effect contracts explicit, gives verified remote effects precedence over receipts/exit codes, and centralizes terminal decisions. That directly covers the Five-POV requirement for structured telemetry and an independent completion oracle, including the critical remote-only review case behind `job-726172fb`. The rollout phases and live acceptance matrix are also directionally sound.

However, the design is not yet implementation-complete. Several invariants need to be explicit:

- Evidence must be idempotent and deduplicated by `(job_id, source, attempt, event_id)`; retries and concurrent observers must never double-count effects or costs.
- A verified remote effect must be attributable to this job, with precise target, actor identity, content/hash, and time/correlation rules; “matching review exists” is insufficient if it predated dispatch.
- Effect contracts must be immutable after launch, and their schema/version must be persisted in every decision.
- Terminality needs a precise definition: when does `verifying` become terminal `failed_verification`, and how are late effects represented without making dashboards contradictory?
- Verification must be safe against TOCTOU races, API pagination/staleness, clock skew, database crashes, and verifier authorization failures.
- `cancelled`, `killed_zombie`, `circuit_breaker_tripped`, and `permission_denied` need mutually exclusive precedence rules and explicit evidence requirements.

The principal rollout risk is complexity creating a new split brain: shadow decisions, legacy projections, structured adapters, and live verifiers can disagree for months. Agy’s unavailability also means the adapter matrix cannot be fully exercised before implementation; Claude/Codex/local and legacy fallback tests are necessary, with Agy explicitly gated rather than silently treated as covered. Add adversarial replay/concurrency tests, contract-attribution fixtures, migration rollback criteria, and a mandatory GitHub-review pilot before broadening effect classes.

My position: **conditionally approve the design for planning, but do not approve implementation yet**. Require the invariants above, an explicit decision/precedence table, idempotency and attribution rules, and a successful end-to-end GitHub-review pilot with independent `gh` ground truth before coding expands beyond the first effect class.

### grok
[model=default; version=grok 1.0.44 (5b807183dd79) [stable]]

I'll review the PR #1949 design against the flaky job-status incidents and the Five-POV feedback, then give a clear recommendation.**Amend PR #1949 before any implementation plan.** The design correctly names the recurring failure: a cheap proxy (exit code, receipt line, log signature) is allowed to overwrite a stronger or still-unresolved effect. The `job-726172fb` case — a real approving review reported as `TASK_DELIVERY_FAILED` — is the right acceptance test, and evidence-versus-status, `unknown` staying `unknown`, and a single terminal writer are the right structure. It does not yet close the invariants that made #1377, #1825, #1896, and Invariant 1 recur.

**Missing invariants**

- **Causal match, not existence.** A GitHub review counts only when `created_at >= started_at`, the actor is the dispatched role login, and the target SHA is the expected head. A pre-existing or stale review is a false success. Absence is N consistent reads after the deadline, not one miss. A 120-second deadline is too short for the #1737 read-after-write lag; the first miss stays `verifying`.
- **Rank-4 evidence cannot settle success or denial.** Exit code and `legacy-text` scraping may explain a row. They must not by themselves produce `completed` or `permission_denied`. That is the hole in §10.2.
- **Close the noop OR.** "Mutating task + exit 0 + no effect → `completed_without_changes` or `failed_noop_denied`, per policy" reintroduces the bug. Default is `failed_noop_denied` unless `kind` is `explicit_noop`. Publish an alias table onto the already-approved Invariant 1 names (`succeeded`, `failed_noop_denied`, `failed_verification`). `completed` versus `succeeded` will split CLI, Vizor, and policy.
- **Non-absorbing states.** `unknown`, `verifying`, and `failed_verification` may be upgraded by later stronger evidence inside the retry budget. A verified `completed` cannot be downgraded by a receipt, a classifier, or a circuit breaker. Cancellation after a landed effect stays `completed` with a warning.
- **One cost row per decision revision, same transaction, no network inside the SQLite claim** (fencing token). Five-POV structured telemetry includes the cost ledger (#1827); this design leaves regex cost on a side path.
- **Contracts are conjunctions.** A parent job's status is the minimum of its children's predicate results. One `primary_evidence_id` cannot represent "diff landed, push did not."

**Rollout.** Shadow mode that preserves today's lying status has no numeric promotion gate, so operators keep acting on false delivery failures. The Phase 0 writer inventory must be a failing test over a enumerated list, not a promise. Do not put Agy in the >99% denominator while credits are unavailable. Report `verified_status_rate` per harness, and keep harnesses without a JSON adapter on provisional status only.

**Required before a plan:** the alias map, an executable truth table with the OR removed, the causal match key and absence quorum, the cost-and-lease transaction rule, and a promotion gate that reclassifies fixtures for #1377, #1825, #1896, and the `job-726172fb` shape before any live writer switches.

I recommend **amend, not approve**. The direction matches the Five-POV oracle recommendation, but the status vocabulary, attribution rule, and promotion gate are still loose enough to recreate the same false status under a new function name.

## Synthesis
## Synthesis: PR #1949, Job Status Truth and Structured Completion Oracle

All three reviewers agree on the direction and on the gaps. The design correctly identifies the failure class: a cheap proxy (exit code, receipt line, log signature) overwrites stronger or unresolved evidence. Its main structural moves are sound:
- Evidence is separate from status.
- Uncertainty stays `unknown`.
- Tasks carry an effect contract.
- There is a single terminal writer.
- Receipts are demoted to evidence.

The `job-726172fb` case, where a real approving review was reported as a delivery failure, is the right acceptance test.

Claude reviewed only about the first 400 lines (§1–11). Codex and Grok looked at the rollout phases and the acceptance matrix, but I have not verified their readings of those sections. Treat those parts as less thoroughly reviewed.

### Required changes before an implementation plan

**1. Causal attribution, not existence (all three).**
- A remote effect counts only if it is bound to this job: actor is the dispatched role login, `created_at >= started_at`, and the exact target (PR and head SHA).
- Absence needs N consistent reads past the deadline, not one miss, because of read-after-write lag and pagination.
- The first miss stays `verifying`.
- The 120s deadline is too short.

**2. Evidence rank limits (Claude, Grok).**
- `structured_event`, receipt, exit-code and `legacy-text` evidence can never raise confidence above what the GitHub or git checks establish.
- Rank-4 evidence cannot by itself produce `completed` or `permission_denied`.

**3. Close the no-op loophole (Grok).**
- A mutating task with exit 0 and no effect defaults to `failed_noop_denied`, unless the contract kind is `explicit_noop`.
- The "per policy" OR in §10.2 reintroduces the bug.

**4. One closed status enum with an alias map (all three).**
- The spec uses `failed_verification`, `failed_noop_denied`, `circuit_breaker_tripped`, `completed` and `succeeded` inconsistently.
- Publish one enum, an alias table onto the already-approved Invariant 1 names, and an executable truth table.
- It needs mutually exclusive precedence among `cancelled`, `killed_zombie`, `circuit_breaker_tripped`, `permission_denied` and `failed_verification`, with the evidence each one requires.

**5. State transitions and revisions (all three).**
- `unknown`, `verifying` and `failed_verification` can be upgraded by later stronger evidence within a retry budget.
- A verified `completed` is never downgraded. Cancellation after a landed effect stays `completed` with a warning.
- Add a hard max age for `verifying` (so a daemon crash cannot strand a job), with an idempotent transition to `failed_verification`.
- Policy gates, merge authority and cost rows must follow the latest decision revision, never a superseded one.

**5a. Contracts (Claude, Codex, Grok).**
- Contracts are immutable after launch, and their schema version is persisted in every decision.
- Contracts are conjunctions: a job's status is the minimum of its predicates, so "diff landed, push did not" is representable.
- Ad-hoc and legacy dispatches get a default contract (`read_only_report` or `unknown`), and the spec states what happens to jobs with no contract.

**6. Idempotency, concurrency and cost (Codex, Grok).**
- Evidence is deduplicated by `(job_id, source, attempt, event_id)`.
- There is one cost row per decision revision, written in the same transaction.
- No network calls happen inside the SQLite claim (use a fencing token).
- Verification retries and API calls have a cap, given the #1937 cost-inflation concern.
- Address TOCTOU races, clock skew, crashes and verifier auth failures.

### Rollout requirements

- **Shadow phase with a numeric promotion gate.** The oracle runs next to the legacy writers and logs disagreements. Cutover needs N jobs with zero unexplained diffs. A shadow mode that keeps today's lying status is not enough, because operators keep acting on false failures.
- **Phase 0 writer inventory is a failing test over an enumerated list**, not a promise.
- **Fixture replay is part of the acceptance bar.** Replay #1377, #1429, #1825, #1896 and the `job-726172fb` shape, with independent `gh` ground truth, before any live writer switches.
- **GitHub-review pilot first.** Don't broaden to other effect classes until the first one is proven end to end.
- **Agy is explicitly gated.** It stays out of the >99% denominator, and `verified_status_rate` is reported per harness. Harnesses without a JSON adapter stay on provisional status only.
- **Version the status contract** for Vizor and `status --json`, and state rollback criteria.
- **Cap evidence-table growth**, given the 7GB state shards in #1831.

### Process

The spec should be amended and re-reviewed by a non-authoring reviewer who runs `synlynk pr check`. I'll route the amendments to the implementation agents. I won't write them myself, per the role split.

Decision: Amend PR #1949 and do not approve it as written. The direction is endorsed: the evidence/status separation, the effect contract and the single terminal writer all stay. No implementation plan gets written, and nothing gets dispatched, until the spec adds these:
- the causal attribution key and absence quorum
- rank limits on weak evidence
- the closed status enum with an alias map and an executable truth table that has the no-op OR removed
- non-absorbing transition rules and a verification deadline
- idempotency and cost-transaction rules
- immutable conjunctive contracts
- a shadow phase with a numeric promotion gate
- a failing-test writer inventory
- fixture replays of the known incidents
- Agy explicitly gated out of coverage claims

After that, a non-authoring re-review can approve the spec for planning. Implementation is limited to the GitHub-review effect class until its pilot passes against independent `gh` ground truth.

## Decision
Decision: Amend PR #1949 and do not approve it as written. The direction is endorsed: the evidence/status separation, the effect contract and the single terminal writer all stay. No implementation plan gets written, and nothing gets dispatched, until the spec adds these:

> Signatures: see 2026-10-03-review-pr-1949-design-job-status-truth-a.json
