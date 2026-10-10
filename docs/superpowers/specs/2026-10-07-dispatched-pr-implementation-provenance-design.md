# Design Spec: Dispatched Implementation Provenance for PR Checks

> Status: design proposal; no implementation included
>
> Date: 2026-10-07
>
> Tracking: #2114; discovered while completing #2062 / PR #2081

## 1. Problem

`synlynk pr check` requires a canonical implementation identity so it can
compare the implementer's harness and model with the reviewer's. The current
resolver can find that identity through a capability-rating PR link, a PR's
closing issue, or a `dispatch/<harness>/job-<id>` branch. Its cost-entry
fallback only handles native cost rows whose `job_id` is null.

PR #2081 has a real dispatched implementation job (`job-2a2b25fa`, Grok) and
a real cost entry linked to PR #2081 and that job. The branch is task-scoped
(`test/grok/2062-adapter-conformance-suite`), capability-rating rows have no
PR number, and the PR correctly keeps #2062 open using `Refs #2062`. The
resolver therefore reports no implementing job provenance despite canonical
evidence already linking the PR to the job.

The implementation gate must resolve that evidence without manufacturing a
second cost row, editing `state.db` out of band, or weakening the required
cross-harness and cross-model comparison.

## 2. Goals and non-goals

### Goals

- Resolve dispatched implementation provenance from a canonical cost entry
  that links a PR number to a real daemon job.
- Classify implementation and review jobs using persisted, typed purpose and
  role metadata, never by searching task prose for words or numbers.
- Use exact PR/job identifiers for all joins; a PR number appearing in free
  text must never establish a provenance link.
- Keep harness and resolved-model identity sourced from the linked job record.
- Fail closed when evidence is missing, ambiguous, incomplete, or conflicting.
- Preserve the current resolution paths for capability ratings, closing issues,
  and dispatch-named branches.
- Make `synlynk pr check` explain which evidence path resolved the implementer.

### Non-goals

- Add native reviewer recording; that remains #2113.
- Change #2062's conformance-suite scope or close its remaining
  strangler-path work.
- Modify cost accounting, create duplicate cost entries, or hand-edit
  canonical state.
- Relax harness/model distinctness checks, PR review requirements, or merge
  authority.

## 3. Proposed resolver behavior

Persist an explicit `purpose` (`implementation`, `review`, or `other`) and
the existing dispatch `role` in `daemon_jobs`. Set purpose from the explicit
`--task-type` and role using a fixed mapping derived from
`role_task_type_compat` and `dev_authority.task_allocation`: `review` under
the `qa` role maps to review; implementation task types under the `dev` role
map to implementation; other role/type pairs map to other. Require explicit
role and task type for jobs that need PR provenance. Do not infer whether a
job implements or reviews from its natural-language task.

For a dispatched review job, use the existing structured `gh_write_target`
and `gh_write_expect` fields: the target must equal `pr:<N>` and the
expectation must equal `review_posted`. Verify the GitHub review event actor
against the configured GitHub App identity for the recorded role. This
replaces the current review lookup that searches task text for a PR number
and review wording. A PR number mentioned incidentally in task prose is
never a link.

For every implementation lookup path (capability rating, closing issue,
dispatch branch, or cost entry), require the joined job to have
`purpose=implementation`. For the new fallback, query `cost_entries` for
rows whose integer `pr_number` equals the PR number and whose `job_id` is
non-null. Join each candidate to `daemon_jobs`; the cost row establishes the
exact PR-to-job link, while `daemon_jobs` remains the source of role, harness,
and model identity. The resolver must not parse PR numbers from task text or
use prose to decide whether a job is implementation or review.

Accept this path only when exactly one distinct implementation job remains
and its harness and resolved model can be read from canonical job metadata.
Multiple matching jobs, conflicting identities, or incomplete metadata must
produce a clear blocked result. Do not silently choose the newest candidate.

When a canonical link resolves an implementation job, compare its identity to
the review job exactly as the existing gate does. The reviewer must still use
both a different harness and a different model. Resolve dispatched reviewers
using the exact target and expected effect described above; leave native
reviewer recording to #2113 and keep the other PR checks unchanged.

## 4. Data and interface

`cost_entries.pr_number` and `cost_entries.job_id` already store the
implementation link. `daemon_jobs` already stores role, harness, resolved
model, `gh_write_target`, and `gh_write_expect`; add and persist a typed
`purpose` field. Resolve the expected GitHub actor from the recorded role and
the repository's role-to-App identity configuration. Confirm the migration
and legacy-row behavior in the implementation plan before coding. Rows
without a typed purpose stay unresolved; never backfill purpose by
interpreting task prose or by hand-editing canonical state.

No new user-facing command is proposed. `synlynk pr check` should consume the
canonical records and report whether the implementer identity came from a
rating, linked issue, dispatch branch, or PR-linked cost entry. For a
dispatched reviewer, it should report the exact target, expected effect,
verified role actor, harness, and model. Native reviewer recording remains
#2113.

## 5. Acceptance criteria

- A cost entry with `pr_number=N`, `job_id=J` resolves `J` when `J` is the
  unique job with `purpose=implementation` and its canonical identity is
  complete.
- A dispatched review job for PR `N` resolves only when its structured target
  is `pr:N`, its expected effect is `review_posted`, and the GitHub review
  actor matches the App identity for its recorded role.
- Incidental PR numbers or review-like wording in task text never create a
  provenance link or classify the job.
- A task-scoped branch can pass provenance resolution through that link
  without a closing issue reference or a capability-rating PR number.
- A missing/unknown purpose, missing job, ambiguous job set, conflicting
  metadata, or missing role/harness/model remains blocked with an actionable
  reason.
- Existing branch-name, closing-issue, and capability-rating resolution tests
  continue to pass.
- Same-harness or same-model implementation/reviewer pairs remain blocked;
  valid distinct pairs pass.
- No extra cost entry or out-of-band database mutation is needed.
- On PR #2081's worktree, `synlynk pr check` resolves the actual implementing
  job and reports the comparison, after which the normal independent review
  and merge-policy gates remain required.

## 6. Risks and open checks

- `cost_entries.pr_number` may have more than one valid implementation job
  over a PR's lifetime. The implementation must define ambiguity using
  distinct job IDs and fail closed rather than infer which job is authoritative.
- A job linked to a PR may have subsequently been amended or superseded. The
  plan should inspect the existing job/commit linkage before deciding whether
  additional validation is needed.
- Existing daemon rows may lack persisted purpose. The plan must preserve
  fail-closed behavior for those rows and avoid fabricating purpose from task
  text; inspect whether a supported migration can recover it from a
  structured dispatch manifest. If it cannot, the affected PR must remain
  blocked until its provenance is recorded through a supported, auditable
  path.
- Native reviewer provenance (#2113) is a separate missing evidence path and
  is intentionally not resolved by this design.

## 7. Verification approach

Add focused database-level tests for the new cost-entry lookup, including
unique, missing, ambiguous, unknown-purpose, stray-task-number, and
incomplete-identity cases. Add exact-target tests for dispatched review
resolution. Run the targeted PR provenance tests first, then the repository's
relevant test suite. In the PR worktree, run `synlynk pr check` against the
actual linked records and capture its output for the independent reviewer.
The reviewer must also re-run `synlynk pr check` from that worktree and
independently apply the merge-policy check before merging.
