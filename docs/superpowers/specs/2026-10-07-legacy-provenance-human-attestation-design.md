# Legacy PR Provenance Human Attestation Design

> Status: Draft for Nikhil's review. No implementation plan or code is
> authorized until this spec is committed and approved.
>
> Tracking: PR #2081 / issue #2062; provenance implementation in #2114.

## Problem

PR #2081 was produced by dispatched job `job-2a2b25fa`. Its structured job
manifest records `role=dev` and `task_type=test`, and its cost record links
that job to PR #2081. Nikhil has confirmed that `--task-type test` was supplied
for this dispatch. The historical manifest predates the
`task_type_explicit` field, however, so the existing reconciliation code
cannot distinguish this confirmed case from a classifier-inferred task type.

The PR provenance gate correctly fails closed when the explicitness marker is
missing. There is currently no supported way to record a human confirmation
about a legacy dispatch without editing the manifest or canonical database by
hand. The generic `synlynk jobs reconcile` command records job-status evidence
and is not suitable for changing provenance metadata.

## Goal

Provide an auditable, supported way for an authorized human to attest to
missing historical provenance facts. Let the PR gate use a valid attestation
for legacy implementation/review classification while preserving the fact
that the original dispatch record lacked an explicitness marker.

For #2081, the attestation should record the confirmed `role=dev`,
`task_type=test`, and derived `purpose=implementation`. It must not claim that
the old manifest itself contained the missing marker.

## Non-goals

- Do not change the behavior or purpose mapping for new dispatches.
- Do not infer task type, role, PR association, harness, model, target, or
  actor from task prose, branch names, cost notes, or test results.
- Do not alter the exact PR/job association rules or cross-harness/model
  review requirements.
- Do not make an attestation replace missing job identity or cost-link data.
- Do not mutate `task_type_explicit` on the original dispatch row to imply
  that the old manifest carried it.
- Do not introduce a general-purpose database editing command.

## Proposed design

### 1. Append-only attestation record

Add a dedicated append-only table for human provenance attestations. Each row
is tied to one exact job ID and records:

- attested role and task type;
- derived purpose using the same deterministic mapping as dispatch;
- attestor identity and timestamp;
- a required rationale and optional reference to supporting material;
- a source marker identifying this as a human attestation, not dispatch
  metadata.

Keep the dispatch row's original `task_type_explicit` value unknown. Do not
rewrite or synthesize the original job manifest. An attestation is an
additional evidence source, not a correction to the historical event log.

### 2. Narrow CLI command

Add a dedicated command such as `synlynk provenance attest <job-id>` that
requires the attested role, task type, rationale, and attestor identity. It
must:

- resolve the job by exact ID and reject missing jobs;
- validate role/task-type compatibility and derive purpose through the
  existing policy mapping;
- show the exact job identity and resulting purpose before writing;
- require an explicit confirmation flag or interactive confirmation;
- append the attestation using a transaction and the supported database API;
- reject a second conflicting attestation and report an existing matching
  attestation idempotently;
- never change the job's harness, model, PR links, GitHub target, or actor.

The CLI must identify the human who invoked it through a documented local
identity source, or require an explicit attestor name if no reliable source is
available. It must not accept a dispatch role as proof of human identity.

### 3. Fail-closed PR provenance resolution

For provenance lookup only, a job without complete typed dispatch metadata
may qualify when it has exactly one valid, non-conflicting human attestation.
Resolve role, task type, and purpose from the attestation; continue to resolve
harness, model, job ID, and other execution facts from their existing
canonical sources. Keep the exact cost-entry PR/job link requirement.

If attestations conflict, are incomplete, use a disallowed role/task pair, or
refer to missing jobs, fail closed with an actionable error. A human
attestation must never override conflicting structured dispatch metadata.

`synlynk pr check` should identify whether each provenance component came
from dispatch metadata or a human attestation so reviewers can understand the
resolution without exposing unnecessary personal data.

### 4. Audit and authorization

Document who may attest and how the invoking identity is established. The
command should be available only in an interactive home-conductor context,
not from a dispatched job. If the runtime cannot reliably distinguish those
contexts, require an explicit confirmation that includes the job ID and
attested fields, and preserve the invocation source in the audit row.

Do not add a second GitHub role-to-login map. Human attestation resolves only
legacy task classification; the existing configured role actor remains the
source for reviewer identity checks.

## Alternatives considered

1. **Manually edit `state.db` or the old manifest.** Rejected: loses the
   distinction between original dispatch facts and later human judgment,
   bypasses supported write paths, and provides a weak audit trail.
2. **Infer implementation purpose from the task prompt or that tests ran.**
   Rejected: task prose and outcomes do not prove which explicit dispatch
   fields were supplied.
3. **Leave the legacy job permanently unresolved.** Safe fallback, but it
   cannot represent a human's authoritative, reviewable confirmation and
   leaves PR #2081 blocked despite the owner confirming the dispatch value.

## Acceptance criteria

- An authorized human can append a traceable attestation to one exact legacy
  job through a supported CLI/API path.
- Original dispatch metadata remains unchanged and distinguishable from the
  attestation.
- `synlynk pr check` accepts exactly one compatible attestation only when
  required exact identity and PR/job links are present.
- Missing, conflicting, stale, or incompatible evidence continues to fail
  closed with actionable output.
- New dispatched jobs continue to use the existing explicit metadata path.
- Tests cover the command, audit row, idempotency, conflict handling,
  authorization boundary, and real PR provenance resolution.
- A non-author reviewer independently verifies the PR gate and merge policy
  before any merge.

## Open design question for approval

What local identity source should the CLI use for `attested_by`? The spec
should prefer an existing authenticated human identity if Synlynk has one;
otherwise it should require a clearly labeled explicit attestor value and
store the invocation source.
