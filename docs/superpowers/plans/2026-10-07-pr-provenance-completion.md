# PR Provenance Completion Plan

> Design: `docs/superpowers/specs/2026-10-07-dispatched-pr-implementation-provenance-design.md`
>
> Tracking: #2114; native reviewer recording remains #2113.

## Objective

Make `synlynk pr check` resolve implementation and dispatched-review provenance
from exact PR/job identifiers and typed job metadata. Preserve the requirement
that implementation and review use different harnesses and different models.
Do not infer links or job purpose from task prose, duplicate costs, or mutate
canonical state outside supported Synlynk code paths.

## Constraints and invariants

- `cost_entries.pr_number` plus `cost_entries.job_id` is the exact link for a
  dispatched implementation job on a task-scoped branch.
- `daemon_jobs.purpose` is a typed value: `implementation`, `review`, or
  `other`. Set it from the explicit role and `--task-type` pair using a fixed
  mapping derived from `.synlynk/policy.json` role compatibility and task
  allocation: `qa` + `review` is review; `dev` + implementation task type is
  implementation; other combinations are other.
- `daemon_jobs.role`, `harness`, and `resolved_model` remain the sources of
  execution identity. A dispatched review also needs exact `gh_write_target`,
  `gh_write_expect=review_posted`, and a GitHub review actor matching the App
  identity for the recorded role.
- Free-text task content cannot establish a PR link or classify job purpose.
- Missing, conflicting, incomplete, or ambiguous provenance fails closed.
- Existing direct rating, closing-issue, and dispatch-branch paths remain
  supported, but must resolve only implementation-purpose jobs.
- Preserve the cross-harness and cross-model checks and all existing review,
  CI, GOVERNS, and merge-authority gates.
- Native interactive reviewer provenance is out of scope (#2113).

## Work breakdown

## Implementation progress (2026-10-07)

- Added migration 17 and persisted `task_type`, whether it was explicitly
  supplied, and a fixed `purpose` in the
  daemon row and flat dispatch manifest. `synlynk jobs` backfills only missing
  typed fields from structured manifest entries; mismatches remain unresolved.
- Provenance lookup now requires typed implementation jobs and exact
  `cost_entries.pr_number`/`job_id` association. Review lookup requires a
  unique `purpose=review`, exact `gh_write_target=pr:N`,
  `gh_write_expect=review_posted`, and a GitHub review by the configured actor
  submitted after dispatch started. Task prose is not consulted.
- The historical #2081 manifest records `role=dev` and `task_type=test` but
  does not record whether the type was explicitly supplied or inferred. It
  therefore cannot be backfilled under the explicit-type rule and remains
  unresolved. New dispatch manifests preserve that distinction. The review
  must run `synlynk pr check` from PR #2115's own worktree.
- Verification so far: provenance-focused tests (9 passed); migration,
  dispatch, and GitHub identity tests (188 passed). The broader
  `test_agent_cli.py` run reached 123 passed and 1 skipped before the sandbox
  denied a localhost socket in an unrelated callback test.

### 0. Inspect the current provenance records and role identity source

Before changing the resolver:

1. Confirm the current schema and dispatch serialization for `daemon_jobs`,
   `job_effect_contract`, and the flat job manifest. Identify every create,
   update, reconciliation, and migration path that must preserve purpose.
2. Confirm how role-to-App identities are configured and how `gh_write_author`
   / `expected_actor` are populated. Reuse the existing source of truth; do
   not add a second role-to-login map.
3. Inspect `job-2a2b25fa` and its PR #2081 cost link. If an existing structured
   dispatch record contains its explicit task type, design a supported,
   idempotent reconciliation path to persist its purpose. If no structured
   record supports that fact, leave it unresolved and report the specific
   evidence gap; do not derive purpose from the task sentence or edit state by
   hand.
4. Record the confirmed mapping and legacy-row behavior in this plan before
   implementation proceeds.

Initial audit findings:

- `dispatch.py` places explicit `task_type`, role, harness, and model identity
  in the flat job object. Its `daemon_jobs` insert/update persists role,
  harness, resolved model, and GitHub target/expectation, but does not persist
  `task_type` or a purpose field. `db_schema.py` likewise has no purpose
  column.
- Role-scoped GitHub actor provenance already uses the configured role:
  `_resolve_dispatch_gh_bot_login()` populates `gh_write_author`, and the
  effect contract stores its expected actor. Reuse that path rather than
  adding a separate role-to-login map.
- The job summary CLI for `job-2a2b25fa` does not expose `task_type`, but the
  structured root job manifest does. The migration must verify the exact job
  ID and explicit role/type values there before backfilling; absent or
  incomplete manifest data leaves the row unresolved.
- The root job manifest confirms `job-2a2b25fa` has `role=dev` and
  `task_type=test`; it also has exact `gh_write_target=pr:2062` and
  `gh_write_expect=pr_open`. The cost row separately supplies the exact PR
  #2081 to job link. The manifest predates `task_type_explicit`, so it cannot
  prove the type was explicit. Purpose remains unresolved for this legacy job;
  the task sentence and PR numbers are not evidence of purpose or association.

### 1. Persist typed job purpose

Files: `synlynk/db_schema.py`, `synlynk/db.py`, `synlynk/dispatch.py`,
`synlynk/jobs.py`, and focused dispatch/schema tests.

1. Add an additive `purpose` column to `daemon_jobs` with nullable legacy
   behavior. Add migration coverage for existing databases.
2. Define one deterministic mapping from explicit role + `--task-type` pairs
   to `implementation`, `review`, or `other`. Treat `qa` + `review` as
   review, the configured implementation types under `dev` as implementation,
   and all other pairs as other.
3. Require explicit role and `--task-type` on jobs that need PR provenance;
   do not infer purpose from the task string for this path.
4. Persist purpose and role consistently in both the canonical daemon row and
   the supported job manifest/reconciliation path. Keep both records aligned
   through queued, running, and terminal transitions.
5. Preserve unknown legacy purpose as null. Only backfill from a structured
   dispatch record containing explicit type metadata; migration must be
   idempotent and must not parse task prose.

Verification: migration tests for fresh and pre-existing schemas; dispatch
tests proving explicit type maps correctly and absent/unknown type does not
silently become implementation or review.

### 2. Resolve implementation jobs by exact canonical links

Files: `synlynk/db.py` and `tests/test_agent_cli.py` (or the focused PR-check
test module selected after inspecting current test organization).

1. Refactor the implementation lookup paths to require
   `daemon_jobs.purpose='implementation'` for capability-rating,
   closing-issue, branch-name, and cost-entry candidates.
2. Add the fallback join `cost_entries.pr_number = <PR number>` and
   `cost_entries.job_id = daemon_jobs.job_id`. Read harness/model/role from
   the daemon job row, never from cost notes or task text.
3. Deduplicate by job ID. Accept exactly one eligible implementation job;
   block with an actionable ambiguity message for multiple candidates or
   conflicting identity records. Never pick the newest row as a tiebreaker.
4. Preserve exact existing paths and return the selected provenance source in
   the gate message for diagnosis.

Verification: unique match; no match; missing job; null/unknown purpose;
review/other-purpose exclusion; duplicate cost rows pointing to one job;
multiple distinct candidate jobs; incomplete identity; task prose containing
the PR number without a structured link; and regression coverage for current
rating, closing-issue, and branch paths.

### 3. Resolve dispatched reviewers with exact target and role actor

Files: `synlynk/db.py`, the existing GitHub review query/helper if needed,
and focused PR-check tests.

1. Select dispatched reviewer jobs by typed `purpose='review'`, exact
   `gh_write_target='pr:<N>'`, and `gh_write_expect='review_posted'`.
2. Fetch the PR review events and require the event actor to match the
   recorded role's configured GitHub App identity (using existing
   `gh_write_author` / `expected_actor` metadata where authoritative).
3. Reject a task that merely contains `review` or the PR number. Reject
   missing or conflicting role/actor/target data.
4. Keep harness and resolved-model comparison independent of role identity:
   both harness and model must differ between implementation and review.

Verification: exact target match; stray PR number in task text; wrong purpose;
wrong GitHub actor for role; missing actor/role; missing review event;
same-harness and same-model rejection; valid distinct identities pass.

### 4. Verify the real PR #2081 records

1. Resolve the historical implementation purpose only from supported
   structured evidence identified in Task 0. If that evidence is unavailable,
   stop this acceptance step and report the gap without bypassing the check.
2. From PR #2081's own worktree and branch, run `synlynk pr check` and capture
   the source, role, harness, model, target, and actor resolution output.
3. Reconfirm CI status and worktree diff. The non-author QA reviewer must
   independently run `synlynk pr check` from that worktree and
   `synlynk policy check-merge --role qa` before deciding whether to approve
   and merge.
4. After PR #2114 lands, resume #2062's remaining legacy strangler scope and
   re-run its required checks before closing #2062.

## Dependencies

`Task 0 → Task 1 → Tasks 2 and 3 → Task 4`.

Tasks 2 and 3 share the PR-check resolver and should ship in one implementation
PR unless Task 0 shows that their identity sources require separate migrations.
Native reviewer support #2113 remains a separate follow-up.

## Acceptance

- No task-description text can create or classify a provenance link.
- PR #2081 resolves its actual implementation job using a canonical exact
  PR/job link and typed purpose, or reports why its historical record cannot
  be safely reconciled.
- Dispatched reviewer resolution uses the exact target, expected review
  effect, and verified role actor.
- Harness and model distinctness checks remain mandatory.
- Focused tests and `synlynk pr check` pass; all existing merge-policy and
  independent-review gates remain in force.
