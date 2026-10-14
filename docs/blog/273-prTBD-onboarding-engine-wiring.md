---
title: "PR #TBD — Five Modules, Zero Callers: Finding the Other Dead Charter Bug"
date: 2026-10-14
series: "Building the OS for Multi-Agent Development"
post: 273
pr: 2310
status: open
author: "synlynk team"
version: "0.25.1"
tags: [posts]
---

## The Broader Goal at the End of the Previous PR

PR #2308 closed gh:#2305 end to end: dispatched-agent charters now bind superpowers skills with real
enforcement language, not just inert YAML. That closed item 5 of the day's master-plan recap. The goal
heading into this PR was item 6 — "auto-upgrade/bundled deps" — logged as a one-line stub with no scope.

## Strategic Shifts in This PR

The recap line gave no hint of scope, so the first move was tracing where "auto-upgrade/bundled deps" actually
came from. It traces to a 2026-10-01 DECIDE panel decision (`dec-00b401f2`) and a full design+plan that a
prior fleet dispatch (PR #1894) claims to have shipped "100% Complete & Verified Green (25/25 Tests Passing)."

Direct `grep` for import sites — not trusting the completion report's test-pass count — found the same failure
class gh:#2305 had just closed: four of the five new modules PR #1894 built (`probe_binding.py`,
`fleet_templates.py`, `version_policy.py`, `first_win_loop.py`) have zero callers anywhere outside their own
file and test suite. Their unit tests are real and green. Nothing in `cli.py`, `wizard.py`, or `viz/server.py`
ever imports them. `topology_discovery.py` is in the same state. Only `onboarding_state.py` made it into a live
code path. The existing `synlynk probe` command is unrelated pre-existing code that happens to share a name with
`probe_binding.py` — easy to mistake for coverage if you don't check the import graph directly.

The shift: item 6 isn't "design auto-upgrade from scratch." It's "five already-designed, already-tested modules
were never wired to anything real — wire them in, or retire whichever ones turn out superseded."

## What This PR Shipped

Filed gh:#2310 with the verified call-site table before writing any design, so the finding is reproducible by
anyone re-running the same `grep` later.

The design (`docs/superpowers/specs/2026-10-14-onboarding-engine-wiring-design.md`) and plan
(`docs/superpowers/plans/2026-10-14-onboarding-engine-wiring.md`) scope five independent wiring tasks:

- **`synlynk probe --deps`** — a new flag on the existing `probe` command (not a new command) that calls
  `probe_binding.probe_all_dependencies()` / `probe_all_harnesses()`. Read-only, matching the 2026-10-01 panel's
  "probe, plan, confirm, never silent-install" invariant.
- **`synlynk fleet list` / `synlynk fleet apply`** — wires `fleet_templates.py`'s role-template merge into a real
  command, with an explicit flag to verify its output shape actually matches what dispatch routing reads, since
  that path was never exercised end to end.
- **`synlynk upgrade --all`** — the piece that most literally matches item 6's "auto-upgrade" wording. Wires
  `version_policy.py`'s plan/check functions into a multi-workspace upgrade pass, one rollback checkpoint per
  workspace, explicit-invocation-only — the panel's own decision text was unambiguous that this must never run
  from the daemon.
- **`first_win_loop.py`'s fate** — not a blind wire-in. The task requires reading `wizard.py`'s current S10 stage
  handling first, since this module may already be superseded by something that shipped since 2026-10-01.
- **`topology_discovery.py` → `onboarding_state.py`** — the one case where the "wired" module
  (`onboarding_state.py`) depends on a sibling that was never actually connected to it.

Every task's definition of done requires an integration test that exercises the real CLI entry point — not
just the underlying module function in isolation — since that's precisely the gap that let PR #1894's dead
code pass review undetected the first time.

## Brainstorm Visuals Used

None — scoped directly from reading `probe_binding.py`, `fleet_templates.py`, `version_policy.py`,
`first_win_loop.py`, and the relevant `cli.py`/`wizard.py`/`viz/server.py` call sites.

## What This Achieved on the Path to Autonomy

A second confirmed instance, in one session, of "tests green" being treated as "feature shipped" when the
code was never reachable. gh:#2305 and gh:#2310 together are becoming a pattern worth naming explicitly:
fleet-dispatched implementation work needs an integration-test gate, not just a unit-test gate, before a
completion report can claim 100%.

## Strategic Note: The Goal at the End of This PR

Item 6's wiring plan is scoped and ready to dispatch. Item 7 — Vizor's full audit and revival — is next, and is
explicitly larger in scope than a one-line stub: Vizor is reportedly not working at all right now, and this
session already touched two of its files (`viz/server.py`'s onboarding endpoints) while investigating item 6,
without yet auditing Vizor as a whole.
