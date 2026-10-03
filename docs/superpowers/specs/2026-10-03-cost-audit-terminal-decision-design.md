# Independent Cost Audit Linked to Job Decision Revisions

> Status: approved by Nikhil on 2026-10-03
>
> Date: 2026-10-03
>
> Issue: [#1951](https://github.com/nikhilsoman/synlynk/issues/1951)
>
> Depends on: `2026-10-03-job-status-truth-and-structured-completion-design.md`

## 1. Summary

Cost auditing will become an independent, append-only subsystem downstream of
the canonical job terminal decision. For each terminal decision revision, the
auditor records one audit outcome: a linked cost record, or an explicit reason
why cost evidence is absent. The auditor can reconcile provider usage, token
attribution, pricing, and legacy ledger rows, and can report discrepancies. It
cannot set, revise, or infer job status.

The status oracle remains the only writer of `job_terminal_decision`. Cost
observation failures, missing usage, unknown prices, and ledger repair failures
remain cost evidence and never become job outcomes. A verified circuit-breaker
intervention may be referenced as lifecycle evidence; a later financial audit
cannot create or erase that intervention.

## 2. Current constraints and motivation

The job-status design amended in commit `8b5de834` reserves cost attribution,
provider pricing, aggregation, budgets, retention, and discrepancy repair for
this separate follow-up. It requires stable linkage by `(job_id,
decision_revision)` and bars cost reconciliation from rewriting status.

The current `cost_entries` ledger is a mutable reporting table. Its sanctioned
writer in `synlynk/db.py` finds rows by `job_id`, updates the row in place, and
may infer `decision_revision` from the latest decision. That behavior cannot
preserve multiple decision revisions or an auditable correction history. The
existing lifecycle event `lifecycle.v1` is an observation stream and may
contain a worker-reported `terminal` event; it is not itself authority to
create a financial record. The canonical input must therefore be the
status-oracle decision persisted in `job_terminal_decision`, with a durable
outbox event emitted by the same transaction.

## 3. Goals

- Define versioned, durable contracts between job decisions and cost audit.
- Represent every terminal decision revision as linked, missing, or pending
  cost evidence with a machine-readable reason.
- Reconcile usage records from harness telemetry, provider billing exports,
  and the existing local ledger without silently double counting them.
- Make repeated ingestion idempotent and expose duplicate, late, conflicting,
  and unlinked records.
- Preserve raw provenance and immutable correction history while allowing a
  current audit projection for reports.
- Specify retention, redaction, shard growth, backup, and repair behavior.
- Keep cost audit unable to write job lifecycle decisions or terminal status.

## 4. Non-goals

- Changing the job-status state machine, decision precedence, or breaker
  semantics.
- Treating estimated/model-equivalent dollars as provider-billed actuals.
- Automatically changing quotas, budget limits, or dispatch routing from
  reconciled cost data in this phase.
- Replacing all existing cost reports or deleting `cost_entries` during the
  initial rollout.
- Claiming provider billing completeness where the provider offers no
  authoritative export or usage API.

## 5. Authority and dependency direction

`job_terminal_decision(job_id, revision)` is the sole authority for job
decisions. A decision revision is eligible for cost audit only when its status
is terminal under the status contract. Intermediate `queued`, `running`,
`observing`, and `verifying` revisions do not create terminal cost links.

The status writer writes the decision and a `job_terminal_outbox` row in one
SQLite transaction. The outbox payload is derived from the persisted row, not
from harness text. The independent auditor consumes that event and reads the
decision row for corroboration. Outbox delivery can be at-least-once; the
auditor is idempotent by stable event identity and decision key.

Allowed direction:

```text
job decision writer -> terminal outbox -> cost auditor -> cost audit events
                                               |              |
                                               v              v
                                        audit projection   reports
```

There is no edge from the auditor, projection, report, provider adapter, or
legacy ledger repair path back to the decision writer. Database permissions
and module boundaries must enforce this, not only comments or convention.

## 6. Versioned contracts

### 6.1 Terminal decision event

The outbox event uses schema `job-terminal-decision.v1` and contains:

| Field | Meaning |
| --- | --- |
| `event_id` | Stable UUID for this persisted `(job_id, decision_revision)` |
| `schema_version` | Literal `job-terminal-decision.v1` |
| `job_id` | Synlynk job identifier |
| `decision_revision` | Positive revision from `job_terminal_decision.revision` |
| `decision_status` | Persisted terminal status, copied without reinterpretation |
| `decision_reason` | Persisted reason code |
| `decided_at` | Decision timestamp, normalized to UTC |
| `effect_contract_version` | Effect-contract version copied from the persisted decision |
| `harness` | Known harness attribution, nullable when unavailable |
| `role` | Known role attribution, nullable when unavailable |
| `source_decision_digest` | Digest of canonical decision fields for conflict detection |

The stable event ID is deterministically derived from the job ID and revision,
or stored with a uniqueness constraint on those fields. Consumers must reject
an event whose decision digest conflicts with the canonical row and record a
cost-audit integrity finding. They must not write a replacement decision.

Worker-emitted `lifecycle.v1` events remain observations and cannot be used as
the authority for this event. If the status implementation initially lacks a
transactional outbox, the auditor may poll the canonical decision table as a
temporary adapter; that adapter must preserve the same event schema, key, and
digest check and must be retired once outbox delivery is available.

### 6.2 Cost audit event

Immutable audit events use schema `cost-audit.v1`. Required envelope fields:

`event_id`, `schema_version`, `audit_id`, `job_id`, `decision_revision`,
`event_type`, `occurred_at`, `recorded_at`, `source_kind`, `source_id`,
`payload_digest`, `supersedes_event_id` (nullable), and `payload`.

Supported event types:

- `decision_observed`: canonical terminal decision accepted for audit.
- `cost_linked`: source usage/ledger evidence linked to the decision.
- `cost_missing`: no usable cost evidence as of the stated observation time.
- `cost_pending`: source is expected but not yet available.
- `cost_corrected`: immutable correction, referring to the event it supersedes.
- `duplicate_detected`: repeated or competing source record surfaced.
- `conflict_detected`: non-equivalent values claim the same source identity.
- `reconciliation_completed`: reconciliation run and coverage result recorded.

`cost-audit.v1` is additive. Unknown event types or future major schema
versions are retained as rejected/unsupported input with a reason; they do not
block job completion. Sensitive payload values are excluded from the common
envelope and stored only in the restricted source-evidence store where needed.

### 6.3 Audit outcome per decision revision

The audit projection key is `(job_id, decision_revision)`. Its state is one of:

- `linked`: one or more eligible source facts were deterministically combined
  into one cost outcome.
- `missing`: no eligible evidence exists, with a required reason code.
- `pending`: evidence is expected within its source's lateness window.
- `conflict`: candidate facts disagree and require review or an explicit
  resolution event.

Missing reason codes include `telemetry_absent`, `provider_not_supported`,
`provider_export_delayed`, `usage_unavailable`, `model_unresolved`,
`price_unavailable`, `redacted_by_policy`, `legacy_unlinked`, and
`source_rejected`. A reason may include a bounded retry-after timestamp and
source expectation. Empty cost values must never be rendered as `$0.00` unless
the source explicitly reported zero usage and that zero is distinguishable
from absent data.

## 7. Data model

The implementation adds isolated cost-audit tables rather than changing
historical decisions or relying on mutable `cost_entries` as the audit log:

1. `job_terminal_outbox`: immutable canonical decision envelope; unique on
   `(job_id, decision_revision)` and `event_id`.
2. `cost_audit_source_record`: deduplicated source facts keyed by
   `(source_kind, source_account, source_record_id)`; preserve provider,
   billing period, model, usage dimensions, currency, timestamps, raw digest,
   and redacted payload reference.
3. `cost_audit_event`: append-only events conforming to `cost-audit.v1`,
   unique by `event_id`; corrections reference an earlier event and never
   update it.
4. `cost_audit_link`: current projection keyed by `(job_id,
   decision_revision)` with state, missing/conflict reason, selected source
   IDs, token totals, price basis, estimated cost, actual cost, currency,
   coverage interval, last reconciled time, and latest audit event ID.
5. `cost_audit_run`: run ID, adapter versions, input watermark, coverage window,
   counts, outcome, and timestamps for independently repeatable reports.

Projection rows are rebuildable from immutable events and source records. A
projection update may change only this cost-audit projection, never
`job_terminal_decision`, `daemon_jobs.status`, or the lifecycle event stream.

Existing `cost_entries` rows are ingested as `legacy_local_ledger` source
records. Their mutable row IDs and values are not treated as immutable provider
facts. Preserve original row ID, observed digest, imported timestamp, and
link-confidence. During migration, do not infer a revision from the latest
decision for historical rows. Assign only when there is an unambiguous source
link; otherwise record `legacy_unlinked` for review.

## 8. Source reconciliation and attribution

Each adapter yields normalized usage facts with explicit provenance and
quality. At minimum a fact records provider/account, source record ID, job ID
or attribution evidence, harness/model, input/output/cache token dimensions,
provider-reported amount and currency, Synlynk-estimated amount, pricing
catalog version, usage interval, observed time, and confidence.

Attribution precedence:

1. Exact `job_id` plus explicit decision revision from a trusted Synlynk event.
2. Exact job ID from a trusted structured harness usage event; bind to the
   terminal revision whose execution interval contains the usage, preserving
   the mapping rule/version.
3. Provider record matched through a stable external request/correlation ID.
4. Heuristic time/model/harness match, marked `low` confidence and never
   silently promoted to provider-verified actual.

One usage fact may not be counted twice because it appears in both telemetry
and a provider export. Source records are deduplicated by provider-native
identity where available; cross-source equivalence is a separate
reconciliation relation. Token totals, estimated price, provider-reported
actual, and user-paid amount remain distinct measures. Do not sum estimated
and actual amounts into one total.

Pricing is a versioned, effective-dated catalog with provider, model, region,
input/output/cache units, currency, and source reference. Every estimate records
the catalog version and rate effective at usage time. Unknown models and
missing rates produce `price_unavailable`; they do not fall back to current
pricing without a visible estimate basis.

## 9. Idempotency, lateness, and correction

- Replaying the same outbox or source event has no additional effect.
- The stable decision key is `(job_id, decision_revision)`; uniqueness is
  enforced in schema and in the reconciliation transaction.
- A second equivalent source fact is marked duplicate and counted once.
- A second non-equivalent fact for the same provider-native identity becomes a
  conflict event; it is not resolved by last-write-wins.
- Late provider usage transitions a `pending` or `missing` projection to
  `linked` by appending `cost_linked`/`cost_corrected`; the old missing event
  remains visible.
- Corrections identify prior and replacement source facts, reason, actor or
  adapter, and timestamp. Reports can reconstruct the view at any prior audit
  event sequence.
- Reconciliation retries use bounded backoff and source-specific lateness
  windows. Expired missing evidence remains auditable and can be reopened by a
  later source arrival.

## 10. Reports and acceptance fixtures

Provide a read-only audit report grouped by date, harness, provider, model,
cost source, confidence, audit state, and currency. Report coverage and
unlinked counts next to totals. Separate estimated, provider-reported, and
paid amounts. Each discrepancy row includes job/revision, source references,
reason code, first/last observation, and correction history. Reports expose no
prompt text, secret values, or unredacted provider payloads.

Acceptance fixtures cover:

- terminal revision with trusted telemetry, producing one stable linked
  outcome under repeated/reordered delivery;
- terminal revision with no usage and a specific missing reason, without
  changing its status;
- delayed provider usage arriving after a `pending` or `missing` outcome;
- estimated tokens and provider billing for the same request, with no double
  count and separate cost measures;
- duplicate identical exports and conflicting records sharing a source ID;
- model alias change, unknown model, missing price, currency conversion
  unavailable, and effective-date boundary;
- legacy `cost_entries` row with unique linkage and ambiguous/unlinked history;
- correction replay, audit reconstruction, and historical decision immutability;
- redaction, retention, restore, and shard-growth boundaries;
- auditor unavailable, corrupt input, or database failure while job status
  remains unchanged and terminal.

Required invariants:

1. Every eligible terminal decision revision has one audit projection with
   `linked`, `missing`, `pending`, or `conflict`; only `linked` has a selected
   cost outcome.
2. No `(job_id, decision_revision)` has more than one projection.
3. Every correction is a new immutable `cost-audit.v1` event.
4. No cost-audit code path writes job decision or legacy terminal-status
   columns.
5. Cost-audit failure cannot yield `permission_denied`,
   `task_delivery_failed`, or `completed`.
6. A verified breaker kill remains a status-oracle decision with linked
   evidence; pricing, aggregation, and later billing adjustments cannot
   fabricate or erase it.

## 11. Retention, redaction, growth, and repair

- Keep decision keys, event envelopes, source digests, aggregate usage, pricing
  basis, and correction lineage as compact audit metadata for the configured
  audit retention period.
- Keep raw provider payloads only when required for reconciliation; encrypt at
  rest, restrict access, redact tokens/credentials/prompt content at ingest,
  and apply a shorter configurable raw-payload retention period.
- Retention deletion is represented by a redaction/deletion audit event and
  leaves the source digest and reason where policy permits. Do not claim
  cryptographic erasure unless the storage design supports it.
- Partition or shard by bounded time windows only after measured growth needs
  justify it. Every shard carries schema version, time coverage, row counts,
  digest, and a manifest entry. Cross-shard reports must expose incomplete or
  missing shards.
- Repair runs are dry-run by default, produce an immutable run report, and
  append correction events. Rebuildable projections may be regenerated from
  retained events. Repair cannot alter historical job decisions or synthesize
  missing provider facts.
- Backups and restores include the audit event log, source identity indexes,
  pricing catalog versions, and shard manifests; restore verification checks
  counts and digests before reports declare complete coverage.

## 12. Security and failure handling

Provider adapters have read-only credentials. The cost-audit writer receives
write access only to cost-audit tables. The status writer owns the decision
table and outbox insert; the auditor has read-only access to both. The
projection/report path is read-only to callers. If SQLite cannot enforce
per-table roles, separate connection APIs and tested SQL allowlists enforce
the same boundary, with the limitation documented.

Malformed, unsupported, unauthenticated, or digest-mismatched provider input
is quarantined with a reason and redacted sample digest. Temporary adapter or
database failures create a retryable audit-run failure and leave prior audit
evidence intact. The status path does not wait on provider billing APIs and
does not fail because the auditor is unavailable.

## 13. Rollout

1. Add schema, event serialization, pure source normalizers, and fixture
   coverage; no production status-path dependency.
2. Shadow-reconcile terminal decisions and existing ledger/provider evidence;
   publish discrepancy reports without changing existing cost displays.
3. Compare coverage, duplicate handling, and totals with manual samples; gate
   promotion on documented thresholds and sign-off.
4. Enable canonical cost-audit projections for read-only reports. Keep legacy
   cost reporting available during a measured compatibility window.
5. Plan a separate migration/removal only after reports demonstrate parity and
   restore procedures are verified.

Each phase needs a rollback path that disables the auditor/report reader while
preserving append-only events. No phase changes job status semantics.

## 14. Decision gates before implementation

Before implementation begins, Nikhil must approve this committed spec. The
follow-on plan must settle:

- the exact terminal status enumeration and schema version in the current
  job-status contract;
- outbox ownership and transaction integration point in the status writer;
- initial provider adapter(s), authoritative source scope, and billing
  lateness windows;
- whether monetary values use decimal strings/minor units and supported
  currencies/conversion source;
- raw payload retention period and encryption/key ownership;
- coverage and discrepancy thresholds for leaving shadow mode;
- database enforcement mechanism for the read/write separation.

After this spec is committed and approved, create the implementation plan
under `docs/superpowers/plans/`. Do not begin the implementation until that
plan is committed.
