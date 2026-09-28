# RCA — LIVE-17: Nested-writer self-deadlock in the probe → capability-sweep → dispatch → quota path

- **Issue:** [#1816](https://github.com/nikhilsoman/synlynk/issues/1816)
- **Severity:** Sev1
- **Date opened:** 2026-09-28
- **Commit under test:** `c35a42e2`
- **Status:** root cause confirmed; fixes not yet dispatched
- **Goal:** `goal-079e2f37`

## Summary

Two tests fail deterministically on `main` on macOS while GitHub Actions CI is green on the
same commit. The failure is a **self-deadlock inside a single process**: `synlynk probe` holds
an open write connection to `state.db` and, while still holding it, calls transitively into
`dispatch_agent()`, which opens a *second* independent connection and attempts an `INSERT`.
The second writer waits on a transaction that can only commit once the second writer returns.

Two separate problems share one root cause, and each is Sev1 on its own merits:

1. A diagnostic command can spend money and spawn an agent mid-transaction — the exact
   write-path coupling that Invariant 4 (#1812/#1813) was shipped to eliminate.
2. CI's green signal does not imply the suite passes, which undermines every downstream
   "verified" claim.

## Timeline

| When | What |
|---|---|
| 2026-09-22..26 | Invariants 1–5 land (#1806–#1815), including Invariant 4's single-writer WAL ledger with leased worktree locks |
| 2026-09-28 | Deep architectural review session runs the full suite serially on macOS: `2 failed, 3385 passed, 1 skipped, 2 deselected in 488.48s` |
| 2026-09-28 | Both failures traced to the same frame, `synlynk/quota.py:555`, `sqlite3.OperationalError: database is locked` |
| 2026-09-28 | Six candidate explanations tested and falsified; nested-writer mechanism confirmed |
| 2026-09-28 | LIVE-17 (#1816) filed Sev1; goal `goal-079e2f37` created with 14 linked remediation stories |

## Failing tests

```
FAILED tests/test_ecosystem_status.py::test_probe_writes_status_and_cycle_capability   (32.02s)
FAILED tests/test_probe.py::test_probe_extracts_claude_version_from_descriptive_output  (6.98s)
```

Both rank among the slowest tests in the suite — consistent with each burning a `busy_timeout`
window before giving up rather than failing fast. `test_probe_writes_status_and_cycle_capability`
is the third-slowest test overall.

## Root cause

| Step | Location | What happens |
|---|---|---|
| 1 | `synlynk/probe.py:293-301` | Opens a write connection, `INSERT INTO harness_models`, `conn.commit()`, then calls `_queue_calibration_sweep(..., conn)` **with the connection still open** |
| 2 | `synlynk/capability_sweep.py:208` | `_dispatch_calibration_task` is reached via `cmd_capability_sweep_for_harness_model(...)` and calls `dispatch_agent(harness, task, ...)` |
| 3 | `synlynk/quota.py:542` `_open_reservation` | Opens a **second** connection through the `_pkg("_get_db")` shim and attempts the `INSERT INTO harness_reservations` at line 555 |

`busy_timeout` cannot resolve this. It is not lock contention between two processes racing for a
resource one of them will release; it is a cycle. The second writer's wait is a precondition for
the first writer's release. The timeout elapses in full and then raises — which is why the two
tests are also two of the slowest in the suite.

### Contributing factor

`synlynk/quota.py` already carries the correct idiom in three other places (`:255`, `:479`, `:987`):

```python
own_conn = conn is None
if own_conn:
    conn = _pkg("_get_db")()
```

The path reaching line 555 neither receives nor reuses the caller's connection, so it is
*structurally guaranteed* to open a second one. The idiom was applied inconsistently rather
than enforced.

## Hypotheses tested and falsified

Recorded so the next investigator does not repeat the work.

| # | Hypothesis | Verdict | Evidence |
|---|---|---|---|
| 1 | Test pollution / ordering | Ruled out | Fails when run in isolation |
| 2 | A stranded process held a write lock | Ruled out | `BEGIN IMMEDIATE` probe returned "writable — NOT locked" |
| 3 | Missing WAL / `busy_timeout` pragmas in the test stub (`tests/test_probe.py:179` uses a bare `sqlite3.connect`) | Ruled out | Forced WAL + `busy_timeout=30000` via a pytest plugin patching `sqlite3.connect`; still fails, after waiting the full 30s |
| 4 | Real harness binaries on `PATH` triggering a live dispatch | Ruled out | Re-ran with harness binaries hidden behind a clean `PATH` |
| 5 | pytest-xdist parallelism | Ruled out | Fails serially; the 488.48s run was serial |
| 6 | Python version (3.12 vs local) | Ruled out | Reproduced across versions |

An investigative dead end worth recording: a `synlynk init` process (PID 34436) was found
holding the 287 MB ledger open for ~8 hours, blocked on `/dev/ttys006`. It was initially
suspected as the lock holder. `ps -o lstart` showed it began the previous day at 16:20:02 from
a real TTY — it was an operator's own interactive `init`, not a test artifact, and hypothesis 2
above falsified it as the cause. It is independent corroboration of a *different* finding
(`init` has no `--yes` path and blocks on stdin — story `[R8]`), not of this one.

## Scope of the CI divergence

The deadlock mechanism is established independently of environment. What remains unexplained is
**why CI is green**. Two variables were not tested and are the next step:

- macOS (Darwin 25.6.0) vs `ubuntu-latest`
- this machine's populated `~/.synlynk/` (287 MB `state.db`, 89.7% freelist) vs CI's empty one

Both possible answers are bad, and neither should be allowed to stand:

- If the tests encode a real bug that CI's environment hides, CI is not testing the product.
- If the tests fail for anyone whose machine resembles a working maintainer's, the suite is
  hostile to exactly the contributors it needs.

This is explicitly *not* resolved in this RCA. Guessing between the two was declined in favour
of tracking it as story `[R3]`.

## Impact

- Any contributor on macOS with real project state sees a red suite on `main`.
- `synlynk probe`, a diagnostic, can incur cost and spawn an agent while holding a write transaction.
- Invariant 4's single-writer guarantee has a live hole on the probe → capability-sweep → dispatch → quota path.
- CI's green signal cannot be relied on as evidence the suite passes.

## Action items

| Story | Action | Owner role |
|---|---|---|
| `[R1]` | Make `_open_reservation` connection-reuse-aware — adopt the `own_conn` idiom on the `quota.py:555` path | dev |
| `[R2]` | Decouple `probe.py` from `capability_sweep`; a diagnostic must never reach `dispatch_agent()`, and no sweep may be invoked while a write connection is held | architect |
| `[R3]` | Reconcile CI with local — resolve the macOS/ubuntu and populated-`~/.synlynk` divergence, or assert it explicitly | qa |
| `[R4]` | Regression test that fails fast on a nested writer instead of on a `busy_timeout` expiry | qa |

All four are linked to goal `goal-079e2f37` and labelled `live-issue sev1 priority:p0`.

## Prevention

1. **A lint or test-time guard against nested writers.** The `own_conn` idiom is correct but
   optional, and an optional invariant is not an invariant. Invariant 4 should be enforced
   mechanically — a connection factory that refuses to hand out a second write connection
   within an open transaction on the same thread would have failed loudly at development time
   instead of silently at `busy_timeout` expiry.
2. **Diagnostics must be structurally incapable of dispatch.** `probe` reaching `dispatch_agent()`
   is a layering violation, not a bug in the call. The capability-sweep trigger belongs on a
   deferred queue drained outside any transaction, not on the probe's synchronous path.
3. **A `busy_timeout` expiry should be treated as a design smell, not a retry budget.** Tests
   whose runtime is dominated by lock waits are reporting an architectural problem; the suite's
   slowest-test list was in fact the first signal that led here.
4. **CI must run on at least one environment resembling a developer machine.** A matrix that
   only ever sees an empty `~/.synlynk/` on Linux cannot catch state-dependent faults.

## Source

Full findings, including the performance audit this incident was discovered during:
[`docs/reviews/2026-09-28-deep-architectural-review.md`](../reviews/2026-09-28-deep-architectural-review.md)
