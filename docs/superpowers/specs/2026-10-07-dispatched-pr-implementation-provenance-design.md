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
- Keep harness and resolved-model identity sourced from the linked job record.
- Fail closed when evidence is missing, ambiguous, incomplete, or conflicting.
- Preserve the current resolution paths for capability ratings, closing issues,
  and dispatch-named branches.
- Make `synlynk pr check` explain which evidence path resolved the implementer.

### Non-goals

- Change reviewer provenance or add native reviewer recording; that remains
  #2113.
- Change #2062's conformance-suite scope or close its remaining
  strangler-path work.
- Modify cost accounting, create duplicate cost entries, or hand-edit
  canonical state.
- Relax harness/model distinctness checks, PR review requirements, or merge
  authority.

## 3. Proposed resolver behavior

After the existing capability-rating, linked-issue, and branch lookups fail,
query `cost_entries` for rows whose `pr_number` matches the PR and whose
`job_id` is non-null. Join each candidate to `daemon_jobs`; exclude jobs whose
task identifies them as review work. The cost row establishes the PR-to-job
link, while `daemon_jobs` remains the source of the execution identity.

Accept this path only when exactly one distinct implementation job remains
and its harness and resolved model can be read from canonical job metadata.
Multiple matching jobs, conflicting identities, or incomplete metadata must
produce a clear blocked result. Do not silently choose the newest candidate.

When a canonical link resolves an implementation job, compare its identity to
the review job exactly as the existing gate does. The reviewer must still use
both a different harness and a different model. Keep the current dispatched
review lookup and all other PR checks unchanged.

## 4. Data and interface

No schema change is expected. `cost_entries.pr_number` and
`cost_entries.job_id` already store the required link, and `daemon_jobs`
already stores the job's harness and resolved model. Confirm these fields and
their uniqueness assumptions in the implementation plan before coding.

No new user-facing command is proposed. `synlynk pr check` should consume the
existing canonical records and report whether the identity came from a rating,
linked issue, dispatch branch, or PR-linked cost entry.

## 5. Acceptance criteria

- A cost entry with `pr_number=N`, `job_id=J` resolves `J` when `J` is the
  unique non-review implementation job and its canonical job identity is
  complete.
- A task-scoped branch can pass provenance resolution through that link
  without a closing issue reference or a capability-rating PR number.
- A missing job, review-only job, ambiguous job set, conflicting metadata,
  or missing harness/model remains blocked with an actionable reason.
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
- Native reviewer provenance (#2113) is a separate missing evidence path and
  is intentionally not resolved by this design.

## 7. Verification approach

Add focused database-level tests for the new cost-entry lookup, including
unique, missing, ambiguous, review-only, and incomplete-identity cases. Run
the targeted PR provenance tests first, then the repository's relevant test
suite. In the PR worktree, run `synlynk pr check` against the actual linked
records and capture its output for the independent reviewer. The reviewer
must also re-run `synlynk pr check` from that worktree and independently apply
the merge-policy check before merging.
