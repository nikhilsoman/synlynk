# Implementation Plan: Version Authority and Release Metadata Integrity

Date: 2026-10-20  
Design: `docs/superpowers/specs/2026-10-20-version-authority-design.md`  
Issue: #1914  
Parent: #2458

## Objective

Make the repository-root `VERSION` the one editable version authority, and
make release checks fail closed before named canonical roadmap releases are
created or changed.

## Task 1: Centralize Read-Only Version Validation

1. Add a small, dependency-free version-authority helper that resolves a
   repository root and reads `VERSION`, package/runtime metadata, README
   release markers, and the current CHANGELOG header.
2. Return structured findings with the observed source, expected authority,
   and a remediation message; do not edit files.
3. Treat a missing `VERSION` as an error for release validation. Retain the
   installed-package fallback only for ordinary version display, with a
   visible warning.

**Verification:** focused unit tests cover a matching repository, every
individual mismatch, and a missing `VERSION`.

## Task 2: Harden `release --check-docs`

1. Route `cmd_release(..., check_docs=True)` through the shared validator.
2. Preserve the existing README test-count waiver behavior, but never permit
   a waiver for a missing/mismatched version authority or CHANGELOG release
   header.
3. Require a non-empty `## [vX.Y.Z]` CHANGELOG section for a checked named
   version and print all discrepancies before exiting non-zero.
4. Remove unsafe fallback defaults from named-release mutation paths: a
   release cannot infer a version when `VERSION` is absent.

**Verification:** CLI tests prove success on the repository fixture and
non-zero failure for absent authority, README mismatch, package mismatch, and
missing/empty CHANGELOG entry.

## Task 3: Doctor and Historical-Gap Evidence

1. Add a read-only `doctor --version` check that reports the canonical source
   and all release-facing projections.
2. Document v0.23.0 and v0.24.0 as preserved historical gaps in CHANGELOG,
   linking the approved roadmap reconciliation design rather than creating
   fabricated release entries.

**Verification:** unit tests assert a useful diagnostic and the documented
gap rationale.

## Task 4: CI Gate

1. Run the shared `release --check-docs` path for pull requests that modify
   release-facing files, for workflow dispatch, and for version tags.
2. Keep normal test jobs unaffected by unrelated changes.
3. Confirm a deliberately mismatched fixture fails the job command.

**Verification:** workflow tests inspect the triggering conditions and the
command; focused local check passes on the repaired repository.

## Task 5: Reconciliation Handoff

1. Run the targeted version-authority tests and full release-docs command.
2. Open a dedicated PR, obtain independent QA review, and merge only through
   the reviewer/policy process.
3. Record the merge and validation evidence on #1914 and #2458.
4. Only after merge, resume canonical roadmap migration: snapshot the DB,
   create the v0.25.2--v0.29.0 arcs, and issue a disposition report before
   any bulk story reclassification.

## Completion Criteria

- `VERSION` is the exclusive editable authority.
- Release validation and CI fail closed on version or CHANGELOG drift.
- Historical gaps are explicit and immutable.
- The #1914 blocker is closed with tests and review evidence.
- No named canonical roadmap release is touched before this PR merges.
