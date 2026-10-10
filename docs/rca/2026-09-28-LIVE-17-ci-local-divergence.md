# LIVE-17: CI/local probe-test divergence

Date: 2026-09-28

## Conclusion

The responsible variable was the operating system, not pre-existing user
state. CI ran only on Ubuntu, while the reported failures occurred on macOS
Darwin 25.6.0.2. The two failing tests do not use the populated
`~/.synlynk` ledger.

## Evidence

- `github/workflows/test.yml` ran the test job only on `ubuntu-latest`.
- `tests/test_probe.py::test_probe_extracts_claude_version_from_descriptive_output`
  changes directory to pytest `tmp_path`, seeds
  `<tmp_path>/.synlynk/state.db`, and monkeypatches `synlynk._get_db` to that
  database.
- `tests/test_ecosystem_status.py::test_probe_writes_status_and_cycle_capability`
  creates its `db` fixture at `<tmp_path>/state.db`, passes that open connection
  directly to `_probe_agent`, and changes directory to the same pytest temp
  directory.
- On macOS, both tests reproduced `sqlite3.OperationalError: database is
  locked`. The first failure occurred when nested calibration dispatch called
  quota `_open_reservation` on a second connection to the temp database. The
  second failure occurred when nested dispatch attempted `BEGIN IMMEDIATE` on
  another connection to the same temp database.
- No failing path resolved or wrote the populated home-state database. The
  home directory therefore cannot explain these failures.
- The previously tested explanations (ordering/pollution, stranded lock
  holder, missing test-stub WAL/busy-timeout settings, real harness binaries,
  xdist, and Python version) were not retested here, per the incident scope.

## Resolution

The test matrix now includes both `ubuntu-latest` and `macos-latest`, for the
existing Python 3.10 and 3.12 combinations. This makes the macOS-specific
failure visible to CI while the separate quota/deadlock fix is developed.

## Next test

The underlying nested-writer/deadlock fix should be validated on both matrix
operating systems before this incident is considered resolved.
