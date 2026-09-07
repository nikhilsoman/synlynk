# Regression Test Strategy: Flaky Integration Tests

**Date:** 2026-09-07  
**Status:** Calibration deliverable (QA advanced / general scenario)  
**Story:** `story-adhoc-1788746015`  
**Role:** qa  
**Difficulty:** advanced  
**Context:** a general scenario at advanced difficulty  

---

## 1. Purpose

Design a regression strategy that turns an intermittently failing integration test into a
**deterministic, root-cause-locked regression suite** — without papering over races with
blind retries, and without quarantining forever.

This is the advanced QA bar: diagnose flake class → isolate the non-determinism → encode
invariants as fixed tests → gate merge on the new suite → retire the quarantine.

---

## 2. Flake Taxonomy (classify before fixing)

| Class | Typical signals | First-line control |
|---|---|---|
| **Timing / race** | Fails under load, passes alone; sleeps "fix" it | Deterministic waits on state, not wall-clock |
| **Shared mutable state** | Order-dependent; fails after sibling test | Per-test isolation (`tmp_path`, fresh DB, unique ports) |
| **External service** | Network, `gh`, daemon, clock skew | Fake boundary + recorded ground truth |
| **Environment** | CI-only (`TERM`, locale, FS case, parallelism) | Explicit fixture defaults + matrix job |
| **Resource leak** | Fails late in suite; ports/files/locks linger | Teardown asserts + process/lock audit |
| **Non-deterministic input** | Random seeds, unordered sets/maps, time.now | Seed control + sorted assertions |

Do **not** start with `pytest-rerunfailures`. Retries measure flake rate; they do not
encode the regression.

---

## 3. Strategy Phases

### Phase A — Reproduce & quarantine (hours, not days)

1. Capture failing CI log, seed, worker id, and `-q --count=N` local reproduction.
2. Mark the test `@pytest.mark.flaky_quarantine` (or move under `tests/quarantine/`) so
   main stays green while investigation proceeds.
3. Open a `live-issue` / tech-debt ticket with: last green SHA, flake rate, taxonomy
   hypothesis, owner.

**Exit criteria:** flake reproducible locally ≥3/20 under stress (`pytest-xdist` or loop).

### Phase B — Isolate the non-determinism

1. Binary-search the suite (bisect test order, then code path) until a minimal repro.
2. Replace wall-clock sleeps with **condition waits** on observable state
   (file exists, DB row, HTTP ready, lock released).
3. For process/daemon integration: inject fakes at the subprocess / network boundary
   (see synlynk patterns: fake `gh`, stub daemon sentinel, monkeypatched `subprocess.run`).
4. Record **ground truth** the test asserts against (e.g. fake GitHub write ledger), not
   the process exit code alone — exit 0 with zero side effects is a known false green.

**Exit criteria:** single-file minimal repro fails 100% when the bug is present, 0% when fixed.

### Phase C — Encode the regression suite

Build a layered suite; each layer must be independently runnable:

1. **Unit pin** — pure function / state machine that held the race (fast, no I/O).
2. **Boundary contract** — fake external service asserting the write-through / retry /
   idempotency invariant.
3. **Integration lock** — one hermetic integration test using the same fixtures as
   production path, with injected clocks and unique resource names.
4. **Stress / soak (optional CI nightly)** — `--count=50` or xdist stress job that must
   stay green for N consecutive nights before quarantine lift.

Name tests after the invariant, not the symptom:
`test_<component>_<invariant>_under_<contention_model>`.

### Phase D — Merge gate & quarantine retirement

1. New regression tests run on every PR that touches the component path.
2. Quarantine marker removed only after:
   - root-cause fix merged,
   - regression suite green on main for the soak window,
   - flake rate on the original test is 0 across the soak window.
3. Add a one-line note to the component's test module docstring: flake class, root cause,
   regression test ids.

---

## 4. Anti-patterns (do not ship)

- Blind `@pytest.mark.flaky(reruns=3)` as the "fix".
- Increasing `time.sleep` until CI goes green.
- Asserting only on process exit code when the side effect is the product truth.
- Sharing module-scoped DB/daemon/port fixtures across mutating tests without reset.
- Quarantining without a ticket, owner, and retirement criteria.
- Deleting the flaky test instead of replacing it with a deterministic pin.

---

## 5. Synlynk-shaped examples (general advanced scenario)

These map the strategy onto classes of flake this repo already sees:

| Scenario | Flake class | Regression pin |
|---|---|---|
| Curses/TUI CI failure when `TERM` unset | Environment | Fixture forces `TERM=xterm`; assert pad init |
| Worktree clean batch continues after one branch delete fails | Shared state / partial failure | Monkeypatch one `git branch -D` failure; assert sibling still deleted |
| Daemon job `done` with zero GitHub side effect | External + false green | Fake `gh` ground-truth ledger; assert `written is True` |
| Concurrent `git worktree` ref lock errors | Timing / race | Serialize via `git_ref_operation_lock`; stress under xdist |
| Naive vs aware datetime compare in `jobs --all` | Environment / data | Fixture feeds mixed timestamps; assert no `TypeError` |

---

## 6. Verification contract for this deliverable

```bash
pytest tests/test_agent_cli.py -k 'design_a_regression_test_strategy_for_a_' -v
```

Expected: matched tests pass; strategy doc present under `docs/qa/` with taxonomy,
phased plan, anti-patterns, and retirement criteria.

---

## 7. Success criteria (advanced)

A regression strategy is complete when:

1. Flake class is named and evidenced.
2. Non-determinism is removed or controlled (clock, seed, isolation, fake boundary).
3. At least one fast deterministic regression test fails if the root cause returns.
4. Quarantine has an explicit retirement gate (soak + owner).
5. Retries, if any, are diagnostic-only and not the merge-gate definition of green.
