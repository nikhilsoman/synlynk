---
title: "PR #587 — Harness Capability Drift & Regression Classification"
date: 2026-08-01
series: "Building the OS for Multi-Agent Development"
post: 90
pr: "#587"
merged: status open
---

## The Broader Goal at the End of the Previous PR

PR #614 (post #89) landed dispatch-time capability enforcement — block or degrade a dispatch before it spawns, based on probe results and declared requirements. But that gate can only be as good as the data feeding it, and two gaps sat underneath it: capability data (`AGENT_CAPABILITY_BASELINES`, the probe results) only ever refreshed reactively at dispatch time, and when a harness-facing failure did occur, nothing distinguished "synlynk broke this" from "the harness changed underneath us." That second gap was concrete, not theoretical: issue #616/#617, where a host-side PR-auto-create fallback silently ignored `job['base_branch']` and shipped undetected because nothing exercised that code path.

## Strategic Shifts in This PR

The brainstorm for this work (`docs/superpowers/specs/2026-07-31-harness-capability-drift-regression-classification-design.md`) explicitly considered and rejected making this a synlynk-run hosted service — centralizing regression classification or smoke tests would require holding user GitHub credentials, a trust boundary this project has never crossed. The one piece with a real efficiency case (a shared, read-only capability-matrix data feed) was logged as a v2 signal instead (`docs/reference/capability-framework-generalization-notes.md`), decoupled from this spec's local-only mechanism.

The other shift was scope-internal: Task 8's plan named both `_run_free_probe` and `_run_paid_smoke_test` as needing classifier wiring, but the step-by-step only detailed the first. A final review pass caught the gap before merge — the paid/live smoke-test path is the one that actually exercises code, so leaving it unclassified would have left the most regression-relevant failure path with no audit trail. Same review pass caught a second real bug: `_dispatch_scenario` was incrementing `ctx.spent_usd` internally *and* `run_selftest`'s flatten loop was adding it again, doubling the effective spend against the $2 live-run budget cap.

## What This PR Shipped

Nine tasks, dispatched to Codex in dependency order (schema → triggers → selftest extensions → classifier → status surfacing), each verified via direct worktree diff read + test run before merge — never trusting job self-reports alone:

- **Schema** (`synlynk/db.py`): `capability_watch`, `gh_write_capability`, `capability_incidents` tables.
- **Staleness triggers** (`synlynk/capability_watch.py`): a free, structural TC1–5 re-probe fired from a background daemon thread on every CLI invocation (never blocks the real command), plus an opt-in paid `selftest --live` trigger gated by `auto_smoke_test` in config.
- **`selftest.py` Phase 1–3**: `ScenarioContext` gained `mode`/`harness` axes so dispatch/exec scenarios loop over every configured harness instead of one hardcoded name; `_dispatch_scenario` now waits for worktree finalization and asserts the resulting PR's base branch matches `job['base_branch']` — the exact check that would have caught #617; new GH-write-action scenarios populate `gh_write_capability` per harness × mode cell; and a mocking-depth reduction pass on `_scenario_join`/`_scenario_decide` replaced mocked internals with real devlog writes and real per-agent response assertions.
- **Classifier** (`synlynk/capability_classifier.py`): `classify_failure()` diffs the failing path's git history since the last known-green run against the harness fingerprint, landing a `regression` / `drift` / `unclassified` verdict in `capability_incidents`. Wired into both the free probe and (post-review-fix) the paid smoke test.
- **`synlynk status`**: surfaces "smoke test overdue" and the five most recent regression incidents, folded into the same string that's both printed and returned — preserving the existing `print(output); return output` contract rather than adding side-channel `print()` calls.

Two real bugs surfaced during the final review pass and were fixed before merge: the double-counted dispatch cost (`_dispatch_scenario` no longer self-increments `ctx.spent_usd`; only `run_selftest`'s flatten loop does) and the missing `_run_paid_smoke_test` classifier wiring. A third, unrelated regression was caught during full-suite verification and fixed independently: Task 2's background staleness thread was making real `subprocess.run` calls from inside any test that invoked `cli.py`'s `main()`, racing other tests' own subprocess mocks and causing nondeterministic failures — fixed with an autouse `stub_staleness_check_thread` fixture in `conftest.py`, matching the existing `stub_dispatch_worktree` pattern.

Full suite: 1510 passed, 2 skipped, stable across repeated runs.

## Brainstorm Visuals Used

None — the design doc's Discussion section (why not a hosted service) did the work a visual comparison usually would.

## What This Achieved on the Path to Autonomy

The dispatch-time gate from PR #614 now sits on top of data that keeps itself fresh without a daemon dependency, and every probe/smoke-test failure gets a first-pass verdict instead of pure human triage. `selftest --live` now actually exercises the #617-class failure mode (PR base-branch mismatch) instead of only asserting scenario presence. Two known, deliberate limitations remain from the plan itself (not implementation gaps): `harness_fingerprint_changed` is hardcoded `False` at every call site, so "drift" classification is structurally unreachable until fingerprint tracking exists, and the GH-write scenario is an explicitly-named "structural check" (does `gh` expose the subcommand) rather than a real per-agent/per-mode invocation — catching that class of flakiness for real would require dispatching genuine headless/home invocations per harness, a larger piece of work than this spec scoped.

## Strategic Note: The Goal at the End of This PR

Both known limitations above are candidates for a follow-up spec, not blockers for this one. The nearer-term goalpost: flip `_probe_results_trustworthy()` (still hardcoded `False`, tracked separately as #578/#580) so the dispatch-time gate this PR feeds can actually trust probe data instead of defaulting to no-coverage on every real dispatch.
