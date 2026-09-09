# pytest-xdist evaluation (#1496)

Date: 2026-09-09

## Decision

Keep the required CI test job serial. Do not add `pytest-xdist` to the CI
installation or change the workflow to `-n auto` yet. A bounded xdist command
is useful for local experimentation after the live-selftest isolation defect
is fixed, but the current evidence does not support making it the global CI
default.

## Baseline and experiment

The workflow command is:

```text
pytest tests/ -v -m "not local_hardware"
```

The checked-in test collection is 2,689 tests, with 2 local-hardware tests
deselected. Comparable post-#1494/#1495 Actions runs were:

| Run | 3.10 test leg | 3.12 test leg | Result |
|---|---:|---:|---|
| #34257922584 (after #1494) | 508s | 213s | pass |
| #34298546000 (after #1495) | 231s | 165s | pass |

The first row is included as nearby historical evidence; the second row is the
post-#1494/#1495 baseline used for this evaluation. Actions job duration
includes setup and installation, so it is not directly comparable to local
pytest-only wall time.

Local Python 3.12 experiment (pytest 9.1.1, pytest-xdist 3.8.0 in a temporary
virtual environment):

| Invocation | Wall time | Result |
|---|---:|---|
| serial, one run | 426.78s | 2684 passed, 2 skipped, 1 failed, 2 deselected |
| `-n 4`, one run | 180.40s | 2684 passed, 2 skipped, 1 failed |
| `-n auto` (16 workers), one run | 162.07s | 2684 passed, 2 skipped, 1 failed |

The same test failed in all three runs:
`tests/test_agent_quota_tracking.py::test_synlynk_selftest_live_clobbers_real_repo`.
It observes live selftest changing `.synlynk/config.json`, creating runtime
metadata, and creating `worktrees/` in a synthetic repository. This is a
pre-existing serial failure, not an xdist-only failure, and is not fixed here.

## Classification

| Class | Current candidates | Rule for promotion |
|---|---|---|
| Parallel-safe | Pure unit modules using `tmp_path`, `monkeypatch`, or injected fakes; the ordinary tests covered by the autouse isolation fixtures in `tests/conftest.py` | No process-global cwd/env/DB writes and green across repeated xdist runs |
| Serial-only for now | `tests/test_agent_quota_tracking.py` live selftest coverage; live orchestration paths in `tests/test_selftest.py` and `tests/test_fleet_scheduler.py` | Keep serial until their repo/worktree and process-global side effects are explicitly isolated |
| Requires isolation work | Any test that invokes live selftest, changes a real repository, creates real worktrees, or relies on shared scheduler/telemetry files | Move all generated state under a test-owned directory and assert cleanup before parallel promotion |

This is a risk classification, not a pytest marker. No quarantine marker is
introduced to make a failing test disappear.

## Resource and diagnostics findings

`-n 4` reduced local wall time by about 58% versus serial. `-n auto` reduced it
by about 62%, but used 16 workers and had substantially higher aggregate CPU
and process output for a subprocess-heavy suite. Both xdist runs retained the
worker id, test node id, traceback, and captured output, so failure identity was
actionable. The live selftest itself emits many worktree/context lines, making
parallel logs noisy and harder to scan.

The local speedup is not an Actions guarantee: the hosted runner has different
CPU limits, and xdist's setup/serialization overhead may dominate smaller
workflow shards. Measure CI again only after the serial suite is green.

## Scoped strategy and rollback

Until the isolation work is complete, keep CI on:

```text
pytest tests/ -v -m "not local_hardware"
```

For an explicit local experiment, install `pytest-xdist` in the environment and
run:

```text
pytest tests/ -m "not local_hardware" -n 4 --dist loadfile
```

The `-n 4` cap avoids the unbounded resource behavior observed with `-n auto`.
Do not use retries or quarantine markers. The rollback boundary is the serial
workflow invocation and this evaluation documentation; reverting the
evaluation commit restores the pre-experiment repository behavior without
touching #1497.
