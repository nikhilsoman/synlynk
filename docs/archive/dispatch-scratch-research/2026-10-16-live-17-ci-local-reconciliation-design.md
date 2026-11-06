# LIVE-17 CI and Local Reconciliation Design

Status: Draft for Nikhil's review

## Problem

The LIVE-17 investigation recorded a mismatch where the serial test suite failed locally while CI passed on the same commit. The prior investigation ruled out several SQLite and test-runner hypotheses, but explicitly left two variables unresolved: macOS versus Ubuntu, and an already-populated `~/.synlynk/` versus CI's typically empty home directory. This story resolves that environmental uncertainty before changing production behavior.

## Goal

Make the CI and local environments comparable enough to reproduce the LIVE-17 failure, identify which environmental variable explains any difference, and preserve the result as a regression guard.

## Design

1. Run the relevant LIVE-17 tests on both `ubuntu-latest` and `macos-latest` in CI, using the same Python version and serial pytest invocation.
2. Give the test job a temporary, isolated HOME so user-level Synlynk state cannot silently affect CI. Add an explicit test variant that starts with representative pre-existing `~/.synlynk/` state only if inspection of the affected tests shows that state is part of their behavior.
3. Compare the same test selection and environment across the platform/home combinations. Record the exact failing test, exception, OS, Python version, and whether the Synlynk home was empty or populated.
4. Do not change SQLite connection or locking behavior in this story. If the matrix confirms a platform or home-state trigger, file or link a follow-up fix with the reproduction details; avoid masking a defect by merely extending timeouts.

## Acceptance criteria

- CI runs the targeted LIVE-17 regression tests on macOS and Ubuntu with a consistent Python version and serial execution.
- The test environment uses a controlled HOME and documents how the empty and populated state cases are represented.
- Any discovered divergence is reproducible from the recorded matrix dimensions and has a follow-up action tied to the result.
- No unrelated production behavior is changed as part of this diagnostic story.

## Risks and constraints

- A populated home directory can contain credentials or machine-specific state. Fixtures must use synthetic, minimal state and must not copy a developer's real home directory.
- macOS CI may be slower or have different availability than Ubuntu. Keep the matrix scoped to the regression tests if runtime is material.
- A passing matrix does not prove the original failure is fixed unless it reproduces the original conditions.

## Verification

Run `pytest -q` on the tests added or modified for this story. Do not use a guessed `-k` expression. Preserve full verification output in `.synlynk/logs/djob-0eabace7-verify-1.log` if it exceeds 4000 characters.

## Approval

This draft is not approved. Under the repository's Brainstorm-First Policy, implementation may begin after this spec is committed to the branch and Nikhil signs off.
