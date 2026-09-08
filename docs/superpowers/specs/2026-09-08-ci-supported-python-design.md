# CI Supported-Python Matrix Design

## Problem

The package declares `requires-python = ">=3.9"` and classifiers for Python 3.9 through 3.12, while the main test workflow still runs Python 3.8, 3.10, and 3.12. The 3.8 job is outside the declared support policy and is the slowest matrix leg.

## Decision

Change only `.github/workflows/test.yml` so the standard test matrix runs Python 3.10 and 3.12. Keep the 3.12-only fleet matrix and the 3.12 QA gate unchanged. Do not change package metadata, test behavior, dependencies, or historical documentation in this ticket.

## Compatibility and operational checks

- Confirm the package metadata and active README already state Python 3.9+.
- Search active workflow and policy references for required `test (3.8)` checks.
- Do not rewrite historical blog/archive references.
- If branch protection contains `test (3.8)`, document the required operator follow-up rather than silently changing remote policy.

## Verification

- YAML remains valid.
- Local collection and focused tests pass.
- CI passes for Python 3.10 and 3.12.
- Before/after CI timing is recorded from comparable runs.

## Rollback

Revert the workflow-only commit to restore the previous matrix.

## Approval gate

This design intentionally drops Python 3.8 from CI coverage; package support remains governed by `pyproject.toml` and is not broadened or narrowed by implementation.
