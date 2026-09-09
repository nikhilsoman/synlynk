# Selftest Probe Metadata Isolation Design

## Problem

Live selftest scenarios need probe records in their scratch database before
dispatch and exec scenarios can exercise capability preflight. When the source
ledger is empty, the current setup invokes the real harness probe. That makes
ordinary tests depend on installed CLIs, network access, npm lookups, and
machine credentials.

## Decision

Make probe setup an explicit boundary on `ScenarioContext`:

- Normal test contexts use deterministic synthetic metadata generated from the
  supported harness baselines. Synthetic rows are clearly marked as test data
  and are never used by production dispatch.
- The production `synlynk selftest --live` path opts into the existing real
  probe behavior.
- One focused integration test opts into the real-probe boundary with an
  injected probe callable and an empty source ledger. It proves cold-start
  provisioning without invoking a vendor CLI or network in the test process.

The metadata copy and destination DB behavior remain unchanged. No changes are
made to dispatch preflight, probe semantics, or the `--live` CLI contract.

## Scope and non-goals

In scope: selftest context/setup, focused unit and integration coverage, and
timing evidence for `tests/test_selftest.py`.

Out of scope: pytest-xdist, CLI lazy imports, production probe logic, and broad
test fixture refactoring.

## Acceptance checks

- Ordinary selftest tests do not call `cmd_probe` or external probe commands.
- Synthetic metadata is sufficient for dispatch/exec scenario preflight.
- The explicit cold-start integration test verifies an injected real-probe
  boundary populates the scratch ledger.
- Existing fail-closed behavior and production live probing remain intact.
- Focused selftest tests pass and their runtime is recorded in the PR notes.
