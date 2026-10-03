# Job Status Truth and Structured Completion Oracle

> Status: design proposal; no implementation included
>
> Date: 2026-10-03
>
> Scope: dispatch lifecycle, terminal status, effect verification, receipts, and
> job-status presentation

## 1. Executive summary

Synlynk's job status is still a collection of plausible signals rather than a
single, durable statement of what happened. A job can produce a real GitHub
review and be reported as `TASK_DELIVERY_FAILED`; a job can exit successfully
and later be relabeled by a reconciler; a job can have no local diff because its
effect was intentionally remote-only; and different commands can read from
different lifecycle stores.

This design makes completion evidence explicit and makes terminal status a
derived projection of that evidence. The system will:

1. Emit structured lifecycle events from the dispatcher and harness adapter,
   instead of treating stdout scraping as the primary completion interface.
2. Store one append-only evidence record per observed effect and one
   single-writer terminal decision per job in the canonical SQLite ledger.
3. Use `verify_effects.py` plus GitHub verification as the completion oracle,
   with local git activity, task receipts, exit codes, and harness output treated
   as evidence rather than verdicts.
4. Separate `status` from evidence dimensions such as receipt validity,
   local-work evidence, remote-effect evidence, instruction loading, and
   verification confidence.
5. Make uncertainty visible and retryable. Missing or unavailable evidence must
   not silently become `permission_denied`, `task_delivery_failed`, or a clean
   success.

The result is a status surface that answers two different questions precisely:

- What does Synlynk currently believe the job outcome is?
- What evidence supports or weakens that belief?

## 2. Why this design now

The 2026-10-02 Five-POV review identified trustworthy job status as the main
product-level failure despite strong dispatch and worktree capabilities. Its
architect recommendation was explicit: replace stdout scraping with structured
interfaces, define the job state machine on verified side effects, and make
`verify_effects.py` the single completion oracle. The developer POV made the
same requirement user-facing: the daily `dispatch -> jobs -> review -> merge`
loop must be boring and must not produce false success or false failure.

The other POVs make this a product prerequisite, not an internal cleanup:

- The VC POV's reliability bar is a measured verified-success rate above 99%,
  not a self-reported completion rate.
- The influencer POV's strongest story is an AI-run software company with
  auditable agent identities and public incident RCAs; misleading status
  undermines that story.
- The OpenRouter/founder POV depends on trustworthy per-task outcome data before
  cross-vendor routing can become a defensible data asset.

The latest concrete recurrence was job `job-726172fb`: the dispatched QA agent
posted a substantive approving review for PR #1947, while the dispatch result
reported `TASK_DELIVERY_FAILED`. That is not a cosmetic label mismatch. It means
the control plane cannot currently distinguish "the requested remote effect
landed" from "the local receipt protocol was incomplete".

## 3. Evidence from incident history

This design consolidates lessons from, but does not erase, prior fixes:

| Incident | Failure fingerprint | Design consequence |
| --- | --- | --- |
| #202, #461, #579 | stale/unknown/zero-files summaries after real work | status must expose provenance and use verified effects |
| #1377, #1429 | `permission_denied` persisted despite a real GitHub write | log classifiers cannot overwrite verified outcomes |
| #1381, #1382, #1500 | timeout/zombie classification raced real completion | liveness decisions must consult external effects before finalizing |
| #1383, #701 | SQLite and legacy JSON reconciliation diverged | one canonical ledger and one terminal writer |
| #1737, #1819 | GitHub read-after-write or canonical DB access was uncertain | `true/false/unknown` verification is mandatory and durable |
| #1825 | reported success without pushed branch or PR | effect verification must be a required completion step |
| #1850 | permission false-negative co-occurred with token-bloat evidence | alert signals must not independently decide terminal status |
| #1896/#1905 | circuit breaker stamped clean exits as `-9` | circuit breaker is an intervention event, not an unconditional verdict |
| #1922 | structured telemetry identified as the completion oracle | this design is the implementation-level follow-through |

The historical pattern is one architectural failure expressed through several
branches: a cheap proxy is allowed to overwrite stronger or merely unresolved
evidence. This design establishes evidence precedence and prevents that class
from recurring in a new classifier.

## 4. Goals and non-goals

### Goals

- Make the canonical SQLite ledger the only mutable source of terminal job
  status.
- Preserve an auditable sequence of lifecycle and verification evidence.
- Support local-change jobs, read-only analysis jobs, and remote-only GitHub
  jobs without pretending they have the same evidence shape.
- Make every terminal outcome explainable from persisted evidence.
- Preserve `unknown`/`pending` when verification is unavailable and make it
  eligible for bounded retry rather than irreversible failure.
- Replace regex stdout parsing as the primary path with structured harness
  events while retaining a clearly marked compatibility fallback.
- Provide a machine-readable status contract for CLI, Vizor, policy gates, and
  future external consumers.
- Measure status correctness against independent ground truth.

### Non-goals

- Reimplementing each vendor harness or fixing vendor-specific MCP/session
  failures at their source.
- Making every task produce a local git diff.
- Removing human review or merge policy gates.
- Building a hosted control plane or exporting telemetry without explicit
  consent.
- Changing routing policy, model selection, or budget ceilings except where
  needed to preserve evidence and state transitions.
- Closing every historical incident as part of the first implementation.

## 5. Design principles

### 5.1 Evidence is not status

Evidence records observations. Status is a deterministic projection created by
one terminal decision function. No individual observation may overwrite status
outside that function.

Examples:

- A missing task receipt is `receipt=absent`, not automatically
  `task_delivery_failed`.
- No local files is `local_effect=none`, not proof of no work.
- A failed GitHub read is `remote_effect=unknown`, not proof that the write
  failed.
- A harness exit code of zero is `process=exited(0)`, not proof of completion.

### 5.2 Strong evidence dominates weak evidence; uncertainty remains uncertainty

The decision function ranks evidence by what it directly proves:

1. Verified target effect (GitHub API, pushed branch, or explicit no-op
   contract).
2. Verified local effect (commit/diff plus scope and base checks).
3. Verified test or read-only result where the task contract permits no diff.
4. Structured harness terminal event and exit code.
5. Task/instruction receipts.
6. Regex log signatures, process liveness, and token/cost sentinels.

Lower-ranked evidence can explain or alert, but cannot contradict a verified
effect. An unavailable higher-ranked check yields `unknown`, not a guessed
failure.

Evidence rank is also a confidence ceiling. Structured harness events,
receipts, exit codes, legacy-text matches, liveness observations, and cost
sentinels may explain a decision, but none can independently promote a job to
`completed` or `permission_denied`. Those outcomes require the
contract-specific GitHub, git, artifact, or explicit-denial predicate.

For remote effects, presence and absence have different proof requirements. An
observed effect is accepted only when it is causally attributable to this job:
the expected actor/role matches, the observation is at or after `started_at`,
and the exact target and relevant head SHA or id match. An absent effect is not
final after one failed read. The verifier performs a bounded quorum of
consistent reads, including read-after-write retry and pagination checks; the
first miss remains `verifying`.

### 5.3 The task contract determines the expected effect

At dispatch time, persist an explicit effect contract:

```json
{
  "kind": "github_review",
  "target": "pr:1947",
  "expect": "review_posted",
  "local_change_policy": "optional",
  "receipt_policy": "required",
  "verification_deadline_seconds": 300,
  "contract_version": 1
}
```

Other contracts include `git_change`, `github_pr_open`, `github_comment`,
`read_only_report`, and `explicit_noop`. Contracts are immutable after launch,
versioned, and conjunctive: a contract may require both a local commit and a
push, or both a review and a matching target SHA. The result is the minimum of
its required predicates, so a diff without a push cannot be represented as a
completed publish operation.

Ad-hoc and legacy dispatches receive a persisted default contract. Read-only
tasks use `read_only_report`; mutating tasks without a known effect contract
use `unknown_contract` and cannot receive an unqualified green result. A
missing contract is an explicit migration state, not an invitation for a
legacy classifier to infer success.

`requires_gh_write` remains a routing and authorization input, but the effect
contract becomes the source of truth for what completion means.

### 5.4 One writer, many observers

Dispatch workers, daemon reconciliation, CLI status, sentinel checks, and Vizor
must not independently settle terminal state. They append evidence or request a
reconciliation. A single ledger transition function claims a running job,
evaluates all available evidence, and commits the terminal projection
atomically.

## 6. Current-state diagnosis

The current architecture has at least four overlapping paths:

1. `dispatch.py` launches the harness and writes legacy job summaries.
2. `jobs.py::_reconcile_jobs_unlocked()` reconciles flat-file jobs and can
   classify task delivery, permission denial, timeout, and effects.
3. `jobs.py::_reconcile_daemon_jobs()` reconciles SQLite `daemon_jobs` rows with
   a separate set of status decisions.
4. `cmd_jobs()` renders the SQLite path first but falls back to legacy data,
   while policy and review tooling may read summaries or job records directly.

The same job can therefore have different representations of completion. The
receipt classifier currently combines a first-line marker with local git
activity. That is insufficient for a remote-only review: a valid review can
have no local diff, and a valid harness log can be missing its first line due
to wrapper buffering or structured-output conversion. Separately, circuit
breaker, permission, timeout, and zombie paths have historically been able to
settle status before the strongest effect check runs.

The first implementation phase must inventory every terminal writer and either
route it through the oracle or explicitly convert it into an evidence event.

## 7. Target lifecycle model

The persisted lifecycle is split into process state, verification state, and
the user-facing terminal outcome.

```text
queued
  -> running
  -> observing
  -> verifying
  -> completed | completed_without_changes | failed
                       | failed_noop_denied | failed_verification
                       | task_delivery_failed | permission_denied
                       | timed_out | killed_zombie | circuit_breaker_tripped
                       | cancelled | unknown
```

`observing`, `verifying`, and `unknown` are not failures. They indicate that
the job is not yet safely settled. A bounded retry policy moves a job from
`unknown`/`verifying` back to `observing`; after the retry budget is exhausted,
the terminal status is `failed_verification` with a specific uncertainty code.

The state machine is monotonic after a terminal claim. A later observer may
append contradictory evidence and open a correction event, but it may not
silently rewrite a terminal result. Corrections require a new `status_revision`
and preserve the original decision, deciding agent, evidence IDs, and reason.

The canonical status enum is closed. Compatibility aliases are mapped only at
the API boundary:

| Canonical status | Legacy aliases | Required proof |
| --- | --- | --- |
| `completed` | `succeeded`, `success` | all contract predicates verified |
| `completed_without_changes` | `completed_noop` | explicit no-op or allowed no-change |
| `failed_noop_denied` | `task_noop_denied` | mutating contract, no effect, no explicit no-op |
| `failed_verification` | `verification_failed` | retry budget exhausted unresolved predicate |
| `permission_denied` | `access_denied` | verified denial prevented the effect |
| `circuit_breaker_tripped` | `killed_by_breaker` | breaker killed a live process |

`cancelled`, `killed_zombie`, `timed_out`, `permission_denied`,
`circuit_breaker_tripped`, and `failed_verification` are mutually exclusive.
The oracle applies this precedence: verified contracted effect first; then an
actual breaker kill; then explicit cancellation/timeout/zombie evidence; then
verified permission denial; then exhausted verification failure. A cancellation
or timeout observed after an effect landed keeps `completed` and adds warning
evidence. `unknown` and `verifying` have a hard maximum age; a daemon restart
or exhausted retry budget must idempotently advance them to
`failed_verification` with a reason code.

## 8. Evidence and schema design

### 8.1 `job_effect_contract`

One row per job:

| Field | Meaning |
| --- | --- |
| `job_id` | stable job identity |
| `kind` | expected effect type |
| `target` | normalized PR, issue, branch, or workspace target |
| `expect` | exact success predicate |
| `local_change_policy` | required, optional, or forbidden |
| `receipt_policy` | required, optional, or waived |
| `verification_deadline_at` | end of bounded verification window |
| `contract_version` | schema version |
| `started_at` | dispatch start used for causal attribution |
| `expected_actor` | role/login permitted to create the effect |
| `required_predicates_json` | immutable conjunction of effect predicates |

### 8.2 `job_evidence`

Append-only observations:

| Field | Meaning |
| --- | --- |
| `evidence_id` | unique event ID |
| `job_id` | owning job |
| `kind` | `process_exit`, `structured_event`, `task_receipt`, `git_effect`, `github_effect`, `instruction_receipt`, `timeout`, `circuit_breaker`, `cost_signal`, or `observer_error` |
| `result` | `true`, `false`, `unknown`, or `not_applicable` |
| `observed_at` | UTC timestamp |
| `source` | dispatcher, harness adapter, daemon, gh verifier, sentinel, or CLI |
| `payload_json` | redacted structured evidence |
| `confidence` | high, medium, low |
| `attempt` | verification attempt number |
| `event_id` | source event id for deduplication |

Evidence is idempotent on `(job_id, source, attempt, event_id)`. Payloads must
include only redacted identifiers, hashes, timestamps, actor ids, and error
classes. Clock skew is handled by recording source time and observer time;
causal attribution never relies on an unbounded local timestamp alone.

No access token, private key, or full harness transcript is stored in the
payload. Evidence stores identifiers, exit codes, target URLs/IDs, hashes,
counts, and redacted error classes.

### 8.3 `job_terminal_decision`

One current decision plus immutable revisions:

| Field | Meaning |
| --- | --- |
| `job_id` | stable job identity |
| `status` | derived user-facing status |
| `exit_code` | process result, nullable |
| `verification_state` | verified, failed, pending, or unknown |
| `primary_evidence_id` | evidence that justifies the decision |
| `evidence_snapshot_json` | IDs and summarized results used |
| `decision_reason` | stable machine-readable reason code |
| `decided_at` | UTC timestamp |
| `decided_by` | oracle version / code identity |
| `revision` | monotonic decision revision |
| `contract_version` | contract schema used by the oracle |
| `follow_up` | `none`, `retry_verification`, or `manual_review` |

Existing `daemon_jobs.status`, `exit_code`, and `gh_write_verified` remain
compatibility projections during migration. They are not independent writers.

## 9. Completion oracle

Create a pure decision boundary, conceptually:

```python
decision = decide_job_outcome(
    contract=effect_contract,
    evidence=ordered_evidence,
    retry_state=retry_state,
)
```

The oracle must be deterministic and side-effect free. It returns:

- `status`
- `verification_state`
- `reason_code`
- `required_follow_up` (`none`, `retry_verification`, `manual_review`)
- evidence IDs used for the decision

Representative rules:

| Contract/evidence | Result |
| --- | --- |
| `github_review` + verified matching review | `completed`, `verified` |
| `github_review` + explicit absent review after deadline | `failed_verification`, `failed` |
| `github_review` + GitHub API unavailable | `verifying`, `unknown`, retry |
| `git_change` + exit 0 + verified scoped diff | `completed`, `verified` |
| mutating task + exit 0 + no effect + no explicit no-op | `failed_noop_denied` |
| read-only report + exit 0 + report artifact verified | `completed`, `verified` |
| receipt absent + verified remote effect | `completed`, with receipt warning evidence |
| permission-shaped log + remote effect unknown | `verifying`, not `permission_denied` |
| circuit breaker actually killed live process | `circuit_breaker_tripped` |
| circuit breaker observed an already-dead process | no breaker terminal decision; continue verification |

`permission_denied` is reserved for an explicit, verified denial that prevented
the contracted effect. `task_delivery_failed` is reserved for a task that was
not accepted by the worker and has no verified effect; it is not a synonym for
missing receipt.

The truth table is executable and versioned with the oracle. A mutating task
may return `completed_without_changes` only when its immutable contract
explicitly permits a no-change result; otherwise the default is
`failed_noop_denied`. No policy-level `or` may reintroduce the old ambiguous
behavior.

## 10. Structured harness telemetry

### 10.1 Adapter contract

Each harness adapter exposes:

- command construction
- structured event mode and parser
- process exit interpretation
- token/cost extraction
- permission and quota events
- terminal-event extraction

The preferred stream is vendor JSON/JSONL output. The adapter emits normalized
events such as:

```json
{
  "event": "harness_terminal",
  "job_id": "job-...",
  "result": "completed",
  "exit_code": 0,
  "reported_effect": "review_posted",
  "reported_target": "pr:1947",
  "source": "claude-json-v1"
}
```

The event is an observation, not proof. The oracle still verifies the effect.

### 10.2 Compatibility fallback

For harnesses without structured output, stdout/stderr scraping remains a
compatibility path with `source=legacy-text`, lower confidence, and an alert
when it makes a material decision. The fallback must never be the only reason
to overwrite a verified effect.

### 10.3 Receipt handling

Task and instruction receipts remain useful provenance, but are moved out of
the terminal status classifier. Receipt results become evidence fields:

`ok`, `late`, `mismatch`, `absent`, `not_applicable`.

Remote-only jobs may require a receipt for audit quality while still completing
when the contracted remote effect is independently verified. The summary should
show `receipt: absent (warning)` rather than `TASK_DELIVERY_FAILED`.

### 10.4 Cost-audit boundary

Cost audit remains an independent design and implementation concern. The job
status oracle owns only the cost evidence needed to explain lifecycle truth;
the cost-audit subsystem owns token attribution, provider pricing, aggregation,
budgets, retention, and financial discrepancy repair.

The integration contract is:

1. Every terminal decision revision emits or links to exactly one cost record.
2. The stable linkage key is `(job_id, decision_revision)`; retries and
   observer races must not create duplicate cost rows.
3. Missing or unavailable cost data is a warning/evidence dimension, not an
   automatic job failure or permission denial.
4. A verified cost/token breaker kill may produce
   `circuit_breaker_tripped`; a cost-observer or pricing error may only produce
   `observer_error`, `unknown`, or a cost warning.
5. Cost-audit reconciliation may append a correction/audit event, but cannot
   independently rewrite the job terminal status.

The cost-audit redesign should consume the versioned job-terminal event and
decision revision rather than becoming another status writer. Its follow-up
ticket [#1951](https://github.com/nikhilsoman/synlynk/issues/1951) is tracked
separately so this design does not absorb financial-model, provider-billing, or
ledger-retention scope.

## 11. Reconciliation and concurrency

All observers call `request_reconciliation(job_id, reason)` or append evidence.
Only the canonical reconciler may claim a running row and settle it. The
transaction is:

1. Begin an IMMEDIATE transaction.
2. Claim the job if it is still in a non-terminal state.
3. Snapshot the effect contract and all evidence through the claim timestamp.
4. Run external verification outside the transaction where possible.
5. Append the verification evidence in a short transaction.
6. Re-read evidence and invoke the pure oracle.
7. Persist the decision and compatibility projections atomically.
8. Emit one `job_terminal` event with the decision revision.

Concurrent reconcilers that lose the claim must not emit summaries, costs, or
alerts from stale observations. They may append an `observer_race` event for
diagnostics. A late exit marker, GitHub review, or commit must be eligible for
the next verification attempt before a job is declared irrecoverably failed.

The daemon and CLI paths must share this reconciler. The legacy JSON path becomes
read-only migration input and cannot settle SQLite rows independently.

The claim uses a fencing token and never performs network calls while holding
the SQLite transaction. Verification happens outside the claim, then evidence
and the decision are committed conditionally on that token. There is exactly
one cost row per decision revision, written in the same transaction as the
terminal projection. Verification retries, API calls, and evidence payload
sizes have explicit caps to prevent a repair loop from creating unbounded cost
or storage growth.

## 12. CLI and product surface

### `synlynk jobs`

The table keeps a short status but adds an evidence marker:

```text
JOB            STATUS        VERIFY       EFFECT             RECEIPT   AGE
job-726172fb   completed     verified     review_posted      warning   3m
```

`synlynk jobs --summary JOB_ID` shows:

- effect contract and target
- final status and reason code
- verification attempts and timestamps
- local and remote effect evidence
- receipt/instruction evidence
- process and circuit-breaker evidence
- whether the result is provisional or corrected

### Machine-readable output

Add `synlynk jobs --json` with a versioned schema. Existing consumers may use
the compatibility status fields, but new consumers must use `status`,
`verification_state`, `reason_code`, and `evidence_summary`.

### Vizor and policy

Vizor consumes the same JSON projection. Policy gates must reject or pause on
`verification_state=unknown` for required effects rather than interpreting an
amber or green label. A green status without a primary evidence ID is invalid.

## 13. Migration and rollout

### Phase 0: inventory and guardrails

- Enumerate every write to terminal status, summary, `jobs.json`, and
  `daemon_jobs` in a checked-in manifest. Add a failing test when a new
  terminal writer is not in that manifest or bypasses the oracle.
- Add a test that fails if a terminal writer bypasses the oracle.
- Add telemetry counters for status changes by writer and reason code.
- Run the oracle in shadow mode and record disagreements, but do not treat the
  legacy status as trustworthy for operator or policy decisions.
- Promote only after a numeric gate: at least 100 representative jobs per
  effect class, zero unexplained terminal-status disagreements, and zero false
  negatives in the replay corpus. Any unexplained disagreement blocks
  promotion and resets the window.

### Phase 1: evidence tables and shared oracle

- Add schema migration for effect contracts, evidence, and decision revisions.
- Backfill only immutable metadata from existing rows; do not invent historical
  verification evidence.
- Route daemon reconciliation through the oracle.
- Keep legacy status and summaries as projections.

### Phase 2: structured adapters

- Implement normalized events for Claude, Codex, Agy, Grok, and local.
- Compare structured and legacy decisions in shadow mode.
- Promote structured events to the preferred source after a verification window.

### Phase 3: remote-effect parity

- Route all `requires_gh_write` contracts through the shared GitHub verifier.
- Add bounded read-after-write retries and persist `true/false/unknown`.
- Require causal actor/target/SHA attribution and an absence quorum before
  recording `false` for a remote effect.
- Make review/merge policy consume the verified projection.
- Add fresh live dispatch trials for read-only, git-only, PR-open, review, and
  comment effects.

### Phase 4: retire split-brain paths

- Stop legacy JSON reconciliation from mutating terminal state.
- Remove status decisions from log-only permission and receipt classifiers.
- Retain parsers only for evidence extraction and backward-compatible imports.
- Add retention/GC for logs and evidence payloads, with immutable decision rows
  retained longer than raw transcripts.
- Cap evidence payload bytes per event, partition retention classes, and add a
  metric for state-shard growth so the evidence ledger cannot repeat the
  multi-gigabyte growth seen in #1831.

## 14. Verification plan

### Unit tests

- Pure oracle truth table for every effect contract and evidence combination.
- Strong evidence cannot be downgraded by a later weak classifier.
- `unknown` verification schedules retry rather than failure.
- Receipt absent plus verified remote effect completes with a warning.
- Circuit breaker only settles when a process was actually killed.
- Terminal decision revision is monotonic and idempotent.
- Closed status enum and compatibility aliases reject unknown statuses.
- Weak evidence cannot promote a job above its verification confidence ceiling.
- Causal attribution accepts only matching actor, target, time window, and SHA.
- A single missed remote read remains `verifying`; quorum is required for
  explicit absence.
- A mutating no-op is `failed_noop_denied` unless the contract explicitly
  permits no change.
- Contract rows are immutable and conjunction predicates are evaluated as a
  minimum, not an any-match.

### Integration tests

- Daemon and CLI reconciliation converge to the same row and summary.
- Two concurrent reconcilers produce one terminal event and one cost record.
- Reconciliation produces exactly one cost record per terminal decision
  revision; a missing cost row is surfaced as evidence without changing a
  verified job outcome.
- A delayed `.exit` marker and delayed GitHub effect are both recovered.
- Review jobs with zero local files but a real GitHub review complete correctly.
- A GitHub API outage leaves a job verifying/unknown, then repairs after retry.
- A real permission denial with no effect remains `permission_denied`.
- A harness exit 0 with no effect becomes the contract-specific no-op/failure
  status, never an unqualified success.
- Known incident fixtures (#1377, #1429, #1825, #1896, and `job-726172fb`)
  replay to the expected status with independent GitHub ground truth.

### Live acceptance matrix

Run from a clean worktree with direct ground-truth checks:

| Job shape | Independent oracle | Required assertion |
| --- | --- | --- |
| read-only analysis | report/artifact hash | status and evidence agree |
| local code change | git diff/commit | files and scope agree |
| PR open | `gh pr view` | PR identity and branch agree |
| review post | `gh pr view --json reviews` | reviewer, body, target agree |
| issue comment | `gh issue view --json comments` | author, body, target agree |
| no-op | explicit contract | no-op is explicit, not inferred from zero files |
| permission failure | direct denied effect | denial is verified, not log-only |

The release gate should report a measured `verified_status_rate` and
`false_negative_rate` from these trials. The target is greater than 99% verified
terminal decisions and zero unclassified terminal decisions for required GH
effects before the product claims trustworthy cross-vendor routing.

Metrics are reported per harness and per effect class. A harness unavailable
for the review window is excluded from that denominator and called out
explicitly; it must not be silently counted as a successful or failed sample.

## 15. Observability and success metrics

Emit counters and dimensions without secret content:

- `job_status_decisions_total{status,reason_code,contract_kind}`
- `job_verification_attempts_total{source,result}`
- `job_status_corrections_total{from_status,to_status}`
- `job_evidence_unknown_total{source,reason}`
- `job_receipt_warning_total{contract_kind}`
- `job_verified_success_rate`
- `job_false_negative_rate`
- `job_terminal_writer_bypass_total` (must remain zero)
- `job_cost_link_missing_total{status,contract_kind}`
- `job_cost_link_duplicate_total{job_id,decision_revision}`

Dashboard and CLI reports must distinguish:

- actual task failures;
- verification failures;
- unavailable evidence;
- policy/permission denials;
- observer or persistence failures.

This supports the Five-POV review's required proof: reliability is measured by
independent effects, not by the number of green self-reports.

## 16. Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| More schema and migration complexity | versioned tables, compatibility projections, one DAO boundary |
| External API latency | bounded retries, async verification evidence, no long DB locks |
| Vendor JSON drift | adapter contract tests and legacy fallback with low confidence |
| Existing scripts expect old statuses | preserve aliases and add versioned JSON output |
| Remote-only jobs appear to have no files | effect contracts and remote evidence are first-class |
| Evidence volume grows like current 8.3 GB footprint | retention classes, redaction, hashes, GC, and payload size limits |
| Oracle becomes another god function | keep pure decision logic separate from adapters, persistence, and verification clients |
| Retry or verification races create duplicate effects/cost | fencing tokens, idempotency keys, bounded retries, and one cost row per decision revision |
| Shadow mode leaves operators acting on false legacy status | policy and operator surfaces use the shadow oracle's provisional status during promotion |
| Cost accounting becomes a second status oracle | versioned terminal-event contract; cost audit may append evidence/corrections but cannot rewrite status |

## 17. Decision gates before implementation

Implementation may begin only after explicit approval of this design and a
follow-on plan. The plan must preserve the sequence:

1. Add evidence/contract schema and pure oracle.
2. Add parity tests against both current reconciliation paths.
3. Route one effect class (GitHub review) end to end.
4. Verify with a fresh live dispatch and independent `gh` ground truth.
5. Expand to other effect classes and retire split-brain writers.

Before implementation begins, this design must also have:

- a checked-in terminal-writer manifest enforced by a failing test;
- fixture replays for the known incidents and `job-726172fb`;
- the closed enum, alias map, and executable truth table;
- causal attribution/quorum rules and a hard verification maximum age;
- the numeric shadow-mode promotion gate and rollback criteria;
- explicit per-harness and per-effect-class reliability reporting. A harness
  with no available credits is excluded from the denominator and remains a
  stated coverage gap.

The independent cost-audit redesign is intentionally not an implementation
phase here. It must consume the terminal-event contract, preserve the
`(job_id, decision_revision)` linkage, and remain unable to settle job status.

The first success criterion is not a prettier status table. It is that the next
real reviewer job that posts a valid GitHub review cannot be reported as a task
delivery failure merely because it produced no local diff or lost a receipt line.

## References

- `docs/strategy/2026-10-02-five-pov-review.md`
- `project-docs/decisions/2026-10-02-round-1-deep-architectural-re-review.md`
- `docs/superpowers/specs/2026-08-15-job-truth-gh-write-consolidation-design.md`
- `project-docs/decisions/2026-08-15-round-2-4-one-problem-or-two.md`
- `project-docs/memory.md` (job-truth and incident history)
- GitHub issue [#1951](https://github.com/nikhilsoman/synlynk/issues/1951) for
  the independent cost-audit redesign
- GitHub issues [#1922](https://github.com/nikhilsoman/synlynk/issues/1922),
  [#1896](https://github.com/nikhilsoman/synlynk/issues/1896),
  [#1850](https://github.com/nikhilsoman/synlynk/issues/1850),
  [#1819](https://github.com/nikhilsoman/synlynk/issues/1819),
  [#1377](https://github.com/nikhilsoman/synlynk/issues/1377), and
  [#1429](https://github.com/nikhilsoman/synlynk/issues/1429)
