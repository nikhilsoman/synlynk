# Task 3 Report: Local admission re-baseline ledger binding

Commit: `feat(local): bind pilot admission to re-baseline ledger` (final HEAD)

## RED/GREEN

- RED: `pytest -q tests/test_dispatch.py -k 'local_pilot_dispatch_uses_isolated_runner_and_records_cohort_receipt'` failed because the expected `local_pilot_evidence` row was absent.
- GREEN: the same focused test passed after admission is written inside the Local reservation transaction, after isolated-runner setup and before process spawn.

## Verification

- `pytest -q tests/test_dispatch.py tests/test_dispatch_auto_routing.py tests/test_local_pilot.py tests/test_local_pilot_ledger.py` — 234 passed.
- `git diff --check` — passed.

## Changed files

- `synlynk/dispatch.py`: bind auto-routing and pre-spawn admission to re-baseline status; persist immutable cohort/admission/receipt-digest metadata; fail back to the frontier for ledger, reservation, and isolated-runner failures.
- `synlynk/local_pilot.py`: restrict runtime-qualified models to Ornith and add the fixed re-baseline share constant.
- `synlynk/local_pilot_ledger.py`: allow `record_admission` to participate in dispatch's existing reservation transaction.
- `tests/test_dispatch.py`, `tests/test_dispatch_auto_routing.py`: cover durable pending admission and disabled-runtime frontier fallback.

## Residual risks

- The Local runtime remains disabled by default; no workspace configuration was enabled or changed.
- Terminal runner-receipt reconciliation and safety-pausing are intentionally deferred to Task 4.
