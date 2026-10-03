# Implementation Plan: Independent Cost Audit for Terminal Decisions

> Design: `docs/superpowers/specs/2026-10-03-cost-audit-terminal-decision-design.md`
>
> Tracking: issue #1951
>
> Approved spec commit: `49c8e396`

## Objective

Implement the independent, replayable cost-audit subsystem in #1951. Every
terminal job decision revision will have one audit outcome (`linked`,
`missing`, `pending`, or `conflict`) keyed by `(job_id, decision_revision)`.
The existing mutable `cost_entries` table remains a compatibility source and
reporting surface during rollout. No new code in cost audit may write job
decisions or job status.

## Resolved design choices

- Terminal statuses are all current `CANONICAL_STATUSES` except
  `unknown` and `verifying`; the terminal set is explicit in the audit module
  and covered by a fixture so a new status requires a conscious update.
- The status writer adds a transactional outbox row only when it inserts a
  terminal decision revision. Event schema is `job-terminal-decision.v1`;
  `effect_contract_version` preserves the existing meaning of
  `job_terminal_decision.contract_version`.
- Money is stored as canonical decimal text plus ISO 4217 currency. No implicit
  currency conversion is performed. Token-rate estimates, provider-billed
  amounts, and paid subscription allocations stay separate.
- Initial source adapters cover structured Synlynk usage facts, the existing
  `cost_entries` ledger, and a documented provider billing export interchange
  (JSONL/CSV with provider record identity, job/correlation reference,
  provider amount, currency, and usage interval). Vendor API polling is outside
  this phase; source records retain export file digest and import run ID.
- Preserve normalized audit events, linked aggregates, and correction lineage
  for the lifetime of the state ledger unless an explicit retention command
  removes them. Default raw provider payload retention is 30 days, configurable
  per workspace; redact credentials and prompt content at ingestion. Export
  files are not copied into the state database.
- The first release is opt-in/manual via `synlynk cost audit` commands and a
  shadow report. Terminal decision creation only enqueues the outbox event; it
  never waits for cost reconciliation.

## Invariants

1. Only the job-truth module writes `job_terminal_decision`; terminal insertion
   and outbox insertion are one transaction.
2. Outbox and source ingestion are at-least-once and idempotent.
3. Exactly one current audit projection exists per terminal decision revision;
   absent usage is represented with a reason, never as zero dollars.
4. Source and audit events are immutable. Corrections append events and update
   only rebuildable cost-audit projections.
5. One provider source record contributes at most once. Estimated, billed, and
   paid measures are not added together.
6. Cost observer, parser, pricing, database, or repair failures cannot create
   or revise terminal status.
7. Raw usage and provider payloads never include prompt content or secrets.

## Work breakdown

### 1. Add schema and terminal decision outbox

Files:

- `synlynk/db_schema.py` — outbox, source, audit event, projection, and run
  tables plus unique/index constraints.
- `synlynk/job_truth.py` — explicit terminal-status predicate, deterministic
  `job-terminal-decision.v1` event construction, and same-transaction outbox
  insertion in `record_evidence_and_reconcile()`.
- `tests/test_job_truth.py`, `tests/test_db.py` — schema, nonterminal exclusion,
  rollback, revision uniqueness, and no duplicate outbox on repeated evidence.

Migration is additive. It must tolerate a partially migrated state DB and must
not backfill guessed revisions. Existing decisions are discoverable by a
polling/backfill command that inserts outbox events idempotently from canonical
rows.

### 2. Implement the isolated cost-audit core

Files:

- New `synlynk/cost_audit.py` — versioned event validation, source normalization,
  deduplication, decision-event consumption, attribution, pricing snapshot,
  projection rebuild, and dry-run/repair operations.
- `synlynk/db_schema.py` — audit tables and bounded indexes described in the
  design.
- `synlynk/costs.py` — thin read/report integration only; keep existing write
  behavior backward compatible during shadow rollout.
- New `tests/test_cost_audit.py` — pure fixtures for event replay, duplicates,
  late data, pricing effective dates, missing reasons, conflicts, corrections,
  and projection reconstruction.

Use canonical decimal strings for monetary values. Price estimation uses the
existing model-rate source only when it can record the exact configured rate
version and basis; otherwise emit `price_unavailable`. No FX conversion or live
provider network call occurs in the core.

### 3. Add three source adapters and reconciliation

Source inputs:

1. Trusted structured harness usage facts with job/correlation identifiers.
2. Existing `cost_entries` rows imported with original row ID, source digest,
   and confidence; do not infer the latest revision for historical rows.
3. Provider billing interchange records (JSONL and CSV) with provider-native
   ID, amount/currency, interval, model, and job/correlation reference.

Reconciliation uses exact decision/revision links first, then stable request
IDs, and only then low-confidence time/model/harness attribution. Source-native
duplicates are idempotent; disagreements become conflict events. Late records
append link/correction events and retain the old missing/pending event.

Tests include repeated file imports, same job with multiple terminal
revisions, shared provider IDs, estimated-vs-actual separation, ambiguous legacy
rows, missing rates, unsupported currencies, and import digest verification.

### 4. Expose independent audit commands and reports

Files:

- `synlynk/cli.py` — `synlynk cost audit reconcile`, `import`, and `report`
  subcommands with dry-run as the default for repair-like operations.
- `synlynk/cost_audit.py` — read-only summaries by date, harness, provider,
  model, confidence, audit state, and currency; coverage and discrepancies
  accompany each total.
- `tests/test_cost_audit_cli.py` and targeted `tests/test_synlynk.py` coverage.

CLI import accepts explicit input paths, stores file digest and metadata rather
than copying raw files, and reports rejected rows without hiding successful
rows. Report output excludes prompt/secret content and labels estimated,
provider-billed, and paid amounts separately.

### 5. Prove status isolation, migration, and operational recovery

Add contract tests which snapshot terminal decision rows and legacy statuses,
then run missing/corrupt/unsupported imports, price failures, database
observer failures, and dry-run repairs; status rows must remain byte-for-byte
unchanged. Verify correction replay, event-log projection rebuild, migration
from pre-feature DBs, and backup/restore metadata checks. Document the
interchange schema, 30-day raw-payload policy, supported limitations, and
manual reconciliation procedure in the CLI help and project docs as needed.

## Verification matrix

- Targeted tests for `job_truth`, `cost_audit`, CLI, and DB migrations.
- Full relevant integration tests for lifecycle telemetry and cost ledger
  compatibility.
- Acceptance invariants from the design: one outcome per terminal decision,
  idempotent duplicates, immutable correction events, independent provider
  reconciliation, and no false status from audit failure.
- `git diff --check`, CLI help smoke checks, and a temporary database migration
  plus replay/report walkthrough.

## Rollback

Disable the manual auditor command/report consumer. Keep outbox, source, and
audit event tables intact for replay. Do not roll back or edit terminal
decisions. Since writes are isolated in new tables, rollback requires no
destructive data migration. Any schema-forward correction must preserve the
event history and rebuild the projection.
