# PR #TBD — Cross-Harness Review Provenance Survives a Missing Cost Row

## The goalpost we inherited

The previous reliability work made `synlynk pr check` enforce cross-harness and
cross-model review using measured dispatch provenance. That gate should remain
fail-closed: a reviewer must not be allowed to merge when the implementing
identity is unknown.

## The problem this PR addresses

A successful dispatch can still lose its `cost_entries` row when job status
tracking records a false negative. In that case, the gate had no way to connect
a real implementation PR back to its daemon job, even though dispatch branch
names already carry the job identity.

## What shipped

- `synlynk/db.py` now falls back, after the existing capability-rating and
  linked-story lookups, to a PR head branch shaped like
  `dispatch/<harness>/job-<id>`.
- The fallback requires a matching `daemon_jobs` row and uses its harness and
  resolved/requested model. Existing cost-ledger evidence remains preferred.
- `synlynk cost log` accepts the concise `--story` spelling and `--job-id`, so
  interactive sessions can record the missing link.
- A missing-provenance check emits a one-line stderr reminder while preserving
  the hard failure.

## Verification

The focused suite passes: `tests/test_agent_cli.py` reports 147 passed and 1
skipped; the cost/database regression set reports 161 passed. New tests cover
branch-based recovery, fail-closed behavior without a daemon row, and the
existing cost-entry path.

## New goalpost

Review provenance is now resilient to a missing cost ledger row without turning
an unresolvable PR into an approved one. The next reliability step is to keep
job status and cost capture aligned at the source so the fallback remains a
rare recovery path.
