<!-- generated - source of truth is state.db -->
---
decision_id: dec-9cfa2b28
topic: "Reassessment: Aligning the 5 Strategic Initiatives with Shipped W0-W9 Workspace Identity, Graphify v0.22.0, and Sev1 State DB Hardening"
date: 2026-09-19
panel: [codex]
status: approved
---

## Topic
Reassessment: Aligning the 5 Strategic Initiatives with Shipped W0-W9 Workspace Identity, Graphify v0.22.0, and Sev1 State DB Hardening

## Panel Inputs

### codex
[model=default; version=codex-cli 0.154.0]

The five initiatives remain strategically relevant, but they no longer have equal urgency or independent identity.

1. Inter-agent relay is validated: the event bus, SSE/JSON-RPC transport, and artifact exchange now support the control-plane direction.

2. Autonomous backlog triage is also aligned and should become a core operating loop, especially as W0-W8 workspace identity establishes durable products, roles, packs, and connectors.

3. Ephemeral swarm infrastructure is premature. W7 proves identity isolation and fail-closed worker execution, but external cloud runners would amplify operational and cost risk before the state layer is fully trustworthy.

4. Living charter evolution is directionally strengthened by Graphify v0.22.0. Graph-backed skills, context packs, impact analysis, and attested PR checks provide the telemetry and architectural evidence needed for measured routing. However, adaptive charter mutation should remain proposal-based and human-gated.

5. The model registry and complexity dispatch initiative is useful, but should follow the same evidence-first model: stable registry, explicit entitlements, cost/rate data, and reproducible routing decisions—not opaque automatic optimization.

The W0-W9 result changes the sequencing. W0-W8 now provide a coherent workspace identity substrate; W9 remains intentionally hosted/deferred. Graphify v0.22.0 supplies the architectural intelligence layer. The Sev1 State DB incident demonstrates the prerequisite beneath both: canonical state must be singular, explicitly addressed, fail-closed, idempotent, and independently recoverable. Until that hardening and the second-machine restore drill are complete, scale-oriented initiatives should not be treated as launch blockers.

My position is to retain all five initiatives, but consolidate them into a dependency-ordered portfolio: first canonical State DB and recovery hardening; second relay, backlog automation, Graphify-backed evidence, and governed charter adaptation; third model registry; and only then ephemeral swarm infrastructure. Do not expand W9 hosting or cloud-scale execution until the control plane passes sustained recovery and integrity tests.

## Synthesis
The five initiatives remain valid, but they should be consolidated into a dependency-ordered portfolio rather than pursued as equally urgent, independent programs. W0-W8 establish the workspace identity foundation, Graphify v0.22.0 provides the evidence and architectural intelligence layer, and the Sev1 State DB incident identifies canonical, recoverable state as the critical prerequisite.

The immediate priority is to harden the State DB: ensure singular canonical addressing, fail-closed behavior, idempotent operations, integrity checks, and a successful second-machine restore drill. In parallel, advance the already validated relay and backlog-automation capabilities, use Graphify to support evidence-based impact analysis and routing, and keep charter evolution proposal-based with explicit human approval. Next, establish a transparent model registry with explicit entitlements, cost data, and reproducible dispatch decisions. Defer ephemeral swarm infrastructure, W9 hosting expansion, and cloud-scale execution until sustained recovery and integrity testing demonstrate that the control plane is trustworthy.

Decision: Retain all five strategic initiatives, but sequence them behind State DB and recovery hardening; proceed with relay, backlog automation, Graphify-backed evidence, and governed charter adaptation; then build the model registry; and defer ephemeral swarms and W9 hosting until the hardened control plane passes sustained recovery and integrity tests.

## Decision
Decision: Retain all five strategic initiatives, but sequence them behind State DB and recovery hardening; proceed with relay, backlog automation, Graphify-backed evidence, and governed charter adaptation; then build the model registry; and defer ephemeral swarms and W9 hosting until the hardened control plane passes sustained recovery and integrity tests.

> Signatures: see 2026-09-19-reassessment-aligning-the-5-strategic-in.json
