---
title: "PR #TBD — Native Sessions Can Prove Cross-Harness Review Provenance"
date: 2026-10-06
series: "Building the OS for Multi-Agent Development"
post: 251
pr: "#TBD"
merged: null
author: "synlynk team"
version: "unreleased"
tags: [posts]
type: pr
---

# PR #TBD — Native Sessions Can Prove Cross-Harness Review Provenance

## The goalpost we inherited

The previous provenance recovery work kept `synlynk pr check` fail-closed when
a dispatched implementation lost its cost row. The remaining gap was a
legitimate implementation authored directly from an interactive home session,
where no dispatch job exists to identify the implementer.

## The problem this PR addresses

The cross-harness review gate only knew how to resolve implementation identity
through dispatch jobs: capability ratings, linked issues, or a dispatch branch.
Native sessions therefore failed the gate even when the PR had a recorded
cost entry and a valid cross-harness review.

## What shipped

- `cost_entries` now records an optional `pr_number`, with additive migration
  support for existing databases.
- `synlynk cost log --pr <pr-number> --harness <harness>` records native
  implementation provenance without reusing the categorical
  `dispatch_context` field.
- `synlynk pr check` uses the newest matching native cost entry only after all
  existing job-based paths fail, while preserving the same identity and
  incomplete-provenance checks.
- The missing-provenance hint and `CLAUDE.md` now distinguish native `--pr`
  logging from dispatched `--job-id` logging.

## Verification

The focused database, CLI, and cost-ledger suites pass: 310 tests passed and 1
was skipped before the final persistence assertion was added. Coverage includes
matching native provenance, mismatched PR numbers failing closed, and all three
existing job-based recovery paths remaining green.

## New goalpost

Interactive home sessions can now participate in the same measured,
cross-harness review gate as dispatched work, without weakening fail-closed
behavior for unrecorded or incomplete provenance.
