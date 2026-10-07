# Legacy PR Provenance Human Attestation Plan

> Spec: `docs/superpowers/specs/2026-10-07-legacy-provenance-human-attestation-design.md`
> Tracking: PR #2081 / issue #2062; provenance implementation in #2114.

## Objective

Add a supported, append-only human attestation for incomplete historical PR
provenance. Preserve the original dispatch record, use attestations only for
missing task classification, and keep all exact job/PR, harness/model, and
reviewer checks fail-closed.

## Design decisions

- The CLI resolves the operator using Synlynk's existing `team.get_username()`
  attribution helper. That helper prefers the authenticated GitHub login and
  falls back to `git config user.name`; unknown identity is rejected. Store
  the resulting username and mark the attestation source as the local CLI.
  Do not treat the GitHub reviewer App identity as the human attestor.
- The command requires a rationale and an exact confirmation value containing
  the job ID, role, and task type. This makes non-TTY use explicit while
  preventing accidental writes; there is no force or overwrite option.
- Attestations are append-only. Matching duplicates are idempotent; any
  conflicting existing attestation blocks a new write and requires a separate
  reviewed resolution path.
- Original `task_type_explicit` remains false or null. Provenance resolution
  uses an attestation only when dispatch metadata is incomplete and does not
  conflict with the attestation.
- The owner-confirmed `dev` + `test` pair maps to `purpose=implementation`
  using the existing `_job_purpose()` policy.

## Task 1: Add append-only provenance attestation storage

Files: `synlynk/db_schema.py`, `synlynk/db.py`, `tests/test_migrate.py`, and
focused database tests.

1. Add a migration after the current migration version creating
   `job_provenance_attestations`, keyed by an integer ID and linked to
   `daemon_jobs.job_id`.
2. Store exact job ID, attested role, task type, derived purpose, attestor,
   rationale, source, and timestamp. Constrain required values and index by
   job ID. Do not add update/delete operations to the API.
3. Add a database helper to insert an attestation transactionally. Validate
   the job exists, derive purpose with `dispatch._job_purpose(role,
   task_type)`, reject unsupported pairs, and compare with any existing typed
   dispatch metadata. Reject conflicting attestations; return an existing
   identical row without duplication.
4. Add a read helper that returns a unique valid attestation for an exact job
   ID and reports conflicts as unresolved.
5. Verify fresh and pre-existing database migrations, constraints, idempotent
   insertion, and conflict rejection.

## Task 2: Add the narrow CLI command

Files: `synlynk/cli.py`, `synlynk/__init__.py` command routing as needed,
database helpers, and focused CLI tests.

1. Add `synlynk provenance attest <job-id> --role <role> --task-type <type>
   --reason <text> --confirm <job-id>:<role>:<type>`.
2. Resolve the human username with `team.get_username()` and reject
   `unknown`. The confirmation must exactly match the parsed job ID, role,
   and task type. No generic `--yes` or force mode.
3. Before writing, print the job's existing harness/model/role/type metadata,
   the proposed attestation values, the derived purpose, and the attestor.
   Refuse if supplied role/type conflict with complete dispatch metadata.
4. Call the database helper and print whether the attestation was inserted or
   an identical one already exists. Never change cost rows or dispatch/job
   metadata.
5. Test missing jobs, invalid role/type, missing rationale/identity,
   confirmation mismatch, metadata conflict, duplicate idempotency, and
   successful recording.

## Task 3: Resolve implementation identity from an attestation

Files: `synlynk/db.py`, focused PR-check tests in `tests/test_agent_cli.py` or
the current provenance test module.

1. Update implementation-candidate lookup so a job with
   `purpose=implementation` from dispatch metadata continues to work as today.
2. For a job whose dispatch purpose is null/unknown only, accept one
   compatible human attestation. Do not allow an attestation to override any
   conflicting non-null dispatch role, type, or purpose.
3. Keep implementation selection tied to the existing exact
   `cost_entries.pr_number` + `cost_entries.job_id` association and read
   harness/model from the canonical job row.
4. Keep reviewer selection, GitHub actor checks, and harness/model difference
   checks unchanged. Include the attestation source in the successful gate
   explanation.
5. Test valid attestation, missing attestation, incompatible pair, conflict,
   multiple candidate jobs, exact PR/job link, conflicting dispatch metadata,
   same-harness/model rejection, and regression coverage for current
   non-attested paths.

## Task 4: Verify #2081 using the new path

1. From PR #2081's worktree, check the current branch/worktree state and run
   the new provenance attestation command for `job-2a2b25fa`, using
   `role=dev`, `task_type=test`, a concise reason referencing Nikhil's
   confirmation, and the exact confirmation value.
2. Run `synlynk pr check --pr 2081` from that worktree. Capture the resolved
   source, job ID, role, purpose, harness, and model. Do not amend PR #2081 to
   conceal or weaken any gate.
3. Recheck CI and the worktree diff. A non-author QA reviewer must run
   `synlynk pr check` from the PR worktree and
   `synlynk policy check-merge --role qa`; only that reviewer may approve and
   merge, and only if all gates pass.
4. If the attestation does not make the gate pass for an independent reason,
   leave #2081 open and report the exact remaining failure. Do not broaden
   the attestation beyond the confirmed task classification.

## Verification commands

- `pytest tests/test_migrate.py -q`
- Focused attestation storage and CLI tests.
- Focused provenance/PR-check tests, including existing cross-harness cases.
- `git diff --check`
- From the PR worktree: `synlynk pr check --pr 2081`.
- Independent QA review: `synlynk pr check` and
  `synlynk policy check-merge --role qa` from that worktree.

## Acceptance

- The original dispatch manifest and `task_type_explicit` value are unchanged.
- A compatible human attestation is stored through a supported, auditable
  path and is idempotent for identical inputs.
- PR provenance consumes only a unique, compatible attestation and preserves
  exact job/PR association and cross-harness/model rules.
- #2081 passes its provenance check, or remains open with a specific reason
  independent of missing explicit task type.
- A non-author reviewer makes the merge decision under existing policy.
