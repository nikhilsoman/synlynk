---
title: "First-Class Models: Giving Dispatch a Real Registry"
date: 2026-09-02
series: "Building the OS for Multi-Agent Development"
post: 162
pr: "#1339"
merged: status: open
---

## The Broader Goal at the End of the Previous PR

Synlynk had reliable harness and workspace-agent boundaries, but model identity
was still implicit in each CLI adapter. That made model capability, context
limits, and local-versus-metered economics difficult to inspect consistently.

## What This PR Shipped

Phase 1 introduces frozen `ModelFamily` and `ModelSpec` dataclasses, explicit
context geometry, rate cards, and four entitlement tiers. A built-in catalog
seeds the SQLite `model_families` and `models` tables. Phase 2 adds safe probes
for the four CLI harnesses, Ollama, and oMLX, with discoveries retained as
first-class model records.

The new `synlynk models list`, `models show`, and `models discover` commands
make the registry useful from a shell. Doctor also verifies that the canonical
catalog is available, while the existing taxonomy and generated command docs
advertise the new surface.

## What This Achieved on the Path to Autonomy

Dispatch can now reason about a model as a separate resource from the agent
and harness. Later phases can use this registry for complexity-aware model
selection and entitlement arbitration without changing permission ownership.

## Strategic Note: The Goal at the End of This PR

The next step is to connect model requisition to dispatch and attribute the
requested model, resolved model, and cost source through the job ledger.
