# Selftest Probe Metadata Isolation Plan

## 1. Add an explicit probe mode to the scenario context

- Add a context field distinguishing synthetic test setup from production live
  probing.
- Keep synthetic mode as the safe default for directly constructed test
  contexts.
- Set live mode explicitly from `run_selftest(live=True)`.

## 2. Isolate metadata provisioning

- Keep the existing source-ledger copy and cold-start real probe helper for
  live mode.
- Add a deterministic baseline-backed synthetic provider for test mode.
- Ensure setup writes rows only into the scratch DB and never mutates the
  source DB.

## 3. Test both boundaries

- Update existing setup tests to assert synthetic mode makes no probe call.
- Retain a focused empty-source integration test using an injected probe
  boundary and assert the resulting row is copied into the scratch DB.
- Assert production orchestration opts into live mode.

## 4. Verify and document

- Run focused selftest and metadata tests first, then the full test suite.
- Capture `pytest tests/test_selftest.py` timing before and after where a stable
  baseline is available.
- Run `git diff --check`, `synlynk pr check`, and record verification in the PR.
