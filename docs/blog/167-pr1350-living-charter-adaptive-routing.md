---
title: "Living Charters and Capability-Gated Adaptive Routing"
date: 2026-09-02
series: "Building the OS for Multi-Agent Development"
post: 167
pr: "#1350"
status: open
---

## The Broader Goal at the End of the Previous PR

Dispatch had reliable harness metadata and cost telemetry, but its role guidance
still described a mostly static fleet.

## What This PR Shipped

The capability ledger records verified model, harness, and task-domain outcomes as
Beta-distribution evidence. Stale evidence is shrunk toward its prior with a
30-day default half-life, while token productivity and latency remain available
for routing decisions.

Adaptive routing evaluates expected value as success probability times task
criticality divided by amortized cost plus the latency penalty. The existing
deterministic path remains the safe first-run fallback until a domain has evidence.

`synlynk charters adapt` finds capability rates that differ from their static
charter by more than 25 percent and emits reviewable proposal documents. Humans
still approve changes to `.synlynk/roles.yaml` and the charter corpus.

## What This Achieved on the Path to Autonomy

The fleet can learn from verified work without silently rewriting governance.
Routing adapts from evidence, while charter changes remain auditable and
reviewable.
