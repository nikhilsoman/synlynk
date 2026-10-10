---
title: "Probe Should Discover Models, Not Spend Money"
date: 2026-09-28
series: "Building the OS for Multi-Agent Development"
post: 226
pr: "TBD"
status: open
author: "synlynk team"
version: "0.23.0-dev"
tags: [posts]
type: pr
---
## The Broader Goal at the End of the Previous PR

Make diagnostic commands safe to run routinely while the launch-credibility review closes correctness and latency gaps.

## Strategic Shifts in This PR (if any)

Probe is explicitly diagnostic. Discovering a harness/model pair no longer implicitly starts paid calibration work or dispatches agents while a database write transaction is open.

## What This PR Shipped

The probe records a newly discovered pair in `harness_models` with `active` status and `self_report` discovery source, then commits and returns. It emits one concise instruction to run `synlynk capability sweep` when calibration is wanted. Regression tests cover the import and dispatch boundary, persisted metadata, and release of the SQLite write transaction.

## Brainstorm Visuals Used

None.

## What This Achieved on the Path to Autonomy

Routine health checks are now bounded, non-spending observations. Calibration remains an intentional operator action, while uncalibrated models can still participate through the routing explore bonus.

## Strategic Note: The Goal at the End of This PR

Diagnostics should remain fast and side-effect constrained; expensive fleet actions belong behind explicit commands and their own operational budget.
