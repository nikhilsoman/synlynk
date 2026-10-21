# Task 2: Local pilot re-baseline state machine and proposal gate

## Commit

`f8d08614 feat(local): enforce re-baseline cohort gates`

## Changed files

- `synlynk/local_pilot.py`
- `synlynk/local_pilot_ledger.py`
- `tests/test_local_pilot.py`
- `tests/test_local_pilot_ledger.py`

## Behavior

- Adds the two-class re-baseline allowlist and a pure `RebaselineDecision`.
- Keeps historical `8/12` outside re-baseline arithmetic; validation advances only after `5/5` accepted evidence.
- Keeps the allocation at `20%`; ten consecutive expansion acceptances produce only `proposal_35_eligible=True`.
- Resets the expansion run after a quality rejection and pauses admission after any hard safety failure.
- Retires the legacy promotion gate with an explicit fail-closed response, so old callers cannot receive automatic `35%` or `50%` decisions.
- Preserves disabled-by-default behavior; this task adds no runner, task execution, GitHub action, or authority change.

## TDD evidence

RED: `pytest -q tests/test_local_pilot.py tests/test_local_pilot_ledger.py` produced eight expected failures: missing `evaluate_rebaseline`/re-baseline constants, legacy automatic `0.50` promotion, and absent `consecutive_accepted` status.

GREEN: `pytest -q tests/test_local_pilot.py tests/test_local_pilot_ledger.py` — `26 passed in 1.04s`.

## Verification

- Targeted policy plus migration/ledger integration: `26 passed in 1.04s`.
- `git diff --check`: passed.
- An additional full `pytest -q` was started with output captured in `.synlynk/logs/job-0e17f62c-verify-1.log`; before this task report was recorded, it had already shown unrelated failures outside the files changed here. The targeted task verification above is the task-gating result.

## Residual risks

- Task 3 must wire `evaluate_rebaseline` into durable dispatch admission and enforce the one-concurrent operational boundary.
- Task 4 must turn runner receipt/preflight drift into a durable safety pause.
- The final 35% decision remains a later human approval gate by design.
