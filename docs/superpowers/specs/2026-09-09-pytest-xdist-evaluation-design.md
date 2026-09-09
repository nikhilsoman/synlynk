# pytest-xdist Evaluation Design (#1496)

## Problem

The supported Python CI matrix is now 3.10 and 3.12 after #1494, and the
selftest probe metadata boundary is isolated after #1495. The remaining test
workflow is serial, so xdist needs an evidence-based evaluation before any CI
default changes.

## Decision

Do not enable global xdist in this change. Record the post-#1494/#1495 serial
baseline, repeat bounded xdist runs, classify test modules by isolation risk,
and document a reversible opt-in command. Keep the existing serial workflow as
the required CI path until the known live-selftest mutation failure is fixed
and a clean parallel run is independently demonstrated.

## Scope

- Measure the exact workflow test selection with serial, `-n 4`, and `-n auto`.
- Classify unit, subprocess, real-git, and live-selftest coverage.
- Record diagnostic and resource observations.
- Add no retries, quarantine markers, or unrelated fixes.

## Verification and rollback

The evaluation is documentation-only and can be reverted as one commit. The
serial CI command remains available unchanged. The optional experiment is
`pytest tests/ -m "not local_hardware" -n 4 --dist loadfile`; it must not be
promoted to CI until the exit status is clean across repeated runs.
