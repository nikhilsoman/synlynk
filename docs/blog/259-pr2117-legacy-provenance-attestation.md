---
title: "PR #2117 — A Human Attestation for Legacy Job Provenance"
date: 2026-10-07
series: "Building the OS for Multi-Agent Development"
post: 259
pr: "#2117"
issue: "2081"
status: open
author: "synlynk team"
version: "unreleased"
tags: [posts, provenance, policy]
type: pr
---

# PR #2117 — A Human Attestation for Legacy Job Provenance

## The Broader Goal at the End of the Previous PR

PR #2116 retired the generic legacy adapter fallback while preserving the
registered harness behavior. The related adapter conformance suite in #2081
was still waiting on the cross-harness provenance gate. The wider goal remains
to make adapter contracts explicit and to require review evidence that can be
traced to the jobs that performed the work.

## Strategic Shifts in This PR (if any)

The provenance resolver now handles a fact that a new dispatch can record
directly but an older dispatch cannot: whether its task type was explicitly
selected. For job `job-2a2b25fa`, Nikhil confirmed that `--task-type test` was
supplied. Synlynk should preserve that as a later human attestation, rather
than writing it back into the historical manifest as if it had always been
there.

## What This PR Shipped

Migration 18 adds `job_provenance_attestations`, an append-only table tied to
an exact job ID. `synlynk provenance attest` records the role, task type,
derived purpose, operator attribution, rationale, and local CLI source. It
requires the exact `JOB_ID:ROLE:TASK_TYPE` confirmation and rejects unknown
operators, incompatible roles, and conflicts with existing job metadata.

The PR check accepts one compatible attestation only when dispatch purpose is
missing, and still requires the exact PR/job cost link. Harness and model
identity continue to come from the existing job/cost records. Reviewer actor,
cross-harness, and cross-model checks remain in place. The historical
`task_type_explicit` field stays unknown.

Focused verification passed: 59 provenance and migration tests, plus 16
existing PR-check tests. The implementation PR is open for independent review;
the attestation for #2081 will be entered through the new CLI after the change
is reviewed and merged.

## Brainstorm Visuals Used

No brainstorm visual informed this change.

## What This Achieved on the Path to Autonomy

Synlynk can now retain an explicit human decision about an incomplete legacy
record without blurring it with dispatch telemetry. Review gates can use that
decision while keeping job identity and PR links anchored to canonical
records.

## Strategic Note: The Goal at the End of This PR

The provenance path has a reviewed design, a supported attestation command,
and fail-closed resolution. Once this PR passes independent review, apply the
owner-confirmed `dev` / `test` attestation to #2081, rerun its gate, and resume
the remaining #2062 checks.
