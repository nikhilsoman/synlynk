---
title: "PR #TBD — Topology Discovery Finally Reaches Confirm"
date: 2026-10-14
series: "Building the OS for Multi-Agent Development"
post: 274
pr: TBD
status: open
author: "synlynk team"
version: "0.25.1"
tags: [posts]
---

## The Broader Goal at the End of the Previous PR

PR #2311 locked the onboarding-engine wiring design for gh:#2310: five modules from the
2026-10-01 fleet dispatch were built and unit-tested, but never imported by a live command
path. The goal after that spec landed was to wire each module into a real entry point, with
integration tests that hit CLI/wizard/Vizor rather than the module in isolation.

## Strategic Shifts in This PR

No redesign. `confirm_topology()` already did the right thing as a pure persist step — it
expects a topology dict and writes it. The missing piece was the discovery engine that was
supposed to produce that dict. This PR takes the plan's second integration approach:
call `topology_discovery` before `confirm_topology` and feed the scored candidate in.

## What This PR Shipped

- `propose_topology()` and `discover_and_confirm_topology()` in `onboarding_state.py`
- Vizor `POST /w/<slug>/api/onboarding/topology/confirm` runs discovery when the body is
  empty or sets `discover: true`, then confirms the candidate; explicit topologies still win
- Wizard `_advance_wizard_onboarding_state` advances through S4 with the same discover→confirm path
- Integration test on the real `VizorHandler.do_POST` entry point in `tests/test_onboarding_topology.py`

## Brainstorm Visuals

None for this wiring task.

## Progress Toward Full Autonomous Multi-Agent Dispatch

Closing one more "tests green, callers zero" gap from the 2026-10-01 onboarding fleet. Dual-surface
onboarding (TUI + Vizor) now actually uses evidence-scored archetype discovery before topology
confirmation.

## New Goalpost

Remaining gh:#2310 tasks: `probe --deps`, `fleet list/apply`, `upgrade --all`, and the
`first_win_loop.py` wire-or-retire decision (Task 4, sequenced after this PR to avoid
wizard/server merge conflicts).
