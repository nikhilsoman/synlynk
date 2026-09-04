<!-- generated - source of truth is state.db -->
---
decision_id: dec-36925bda
topic: "Making Model and Model Family First-Class Citizens in Synlynk: Architecture for Capability, Cost, Entitlement, and Dispatch across Core and Local Harnesses"
date: 2026-09-02
panel: [agy, codex, claude]
status: approved
---

## Topic
Making Model and Model Family First-Class Citizens in Synlynk: Architecture for Capability, Cost, Entitlement, and Dispatch across Core and Local Harnesses

## Panel Inputs

### agy
**Last completed task:** Session initialization and panel brief review.  
**Next task from `todo.md`:** Awaiting panel consensus and architectural specification sign-off.

---

### Analysis

Treating models merely as configuration strings or opaque API endpoints introduces severe operational bottlenecks in multi-tier, hybrid agent architectures. As Synlynk expands across centralized cloud infrastructure (**Core**) and edge/on-device runtimes (**Local Harness**), decoupling model identities from their behavioral, economic, and security boundaries is no longer viable.

Elevating **`ModelFamily`** and **`Model`** to first-class, schema-driven architectural primitives resolves four foundational vectors:

1. **Capability & Adapter Standardization:** `ModelFamily` captures intrinsic architectural invariants—context topologies, tokenizer semantics, reasoning modes, and native tool-calling formats—allowing harnesses to apply correct prompt adapters and validation pipelines deterministically.
2. **Deterministic Cost Governance:** Modeling concrete `Model` entities enables precise token accounting (input, output, cached context, reasoning overhead) and pre-flight budget arbitration across both commercial APIs and local compute quotas.
3. **Entitlement & Data Residency:** A structured model hierarchy empowers policy engines to enforce tenant-level access tiers, enterprise compliance rules, and data governance policies (e.g., pinning regulated workloads to air-gapped Local Harnesses versus cloud Core).
4. **Intelligent Hybrid Dispatch:** A unified dispatcher can dynamically evaluate task requirements against cost, latency, and hardware constraints, seamlessly routing lightweight or privacy-critical jobs to local quantized models while delegating heavy reasoning to Core frontier models.

### Recommendation & Position

Synlynk should adopt a declarative two-tier schema:
- **`ModelFamily`**: Defines interface protocols, tokenization profiles, and harness adapter specifications.
- **`ModelSpec` / `ModelInstance`**: Encapsulates parameter scale, quantization, context ceilings, per-token pricing, and tenant entitlement bindings.

**Final Position:** I strongly recommend establishing `Model` and `ModelFamily` as first-class citizens within the Synlynk core architecture. This foundation is essential for scalable policy enforcement, transparent cost controls, and resilient, workload-aware dispatching across Core and Local harnesses.

### codex
Synlynk should make model and model family first-class, but as a distinct resource dimension—not as a replacement for Workspace Agent or Harness. The approved separation is the right foundation: Workspace Agents provide identity and accountability, Harnesses provide execution, and models provide reasoning capacity. Dispatch should therefore evaluate a tuple such as `(role, harness, model)` against task requirements, policy, quota, capability evidence, and cost.

The data model should introduce a canonical model registry with provider, family, version, context limits, modalities, pricing, local/remote status, lineage, and normalization aliases. Every dispatch, cost record, capability rating, and verification event should retain both the requested model and the resolved model actually used. This is especially important for CLIs that can silently switch models mid-session. Capability scores should be keyed primarily by model family/version and task domain, with harness-specific adjustments for tool execution, sandboxing, and output reliability.

Model identity must not become an authorization mechanism. Entitlements should remain attached to the Workspace Agent and enforced by the execution environment; model metadata may constrain eligibility—for example, a model lacking tool calling cannot satisfy a coding task—but it must not grant filesystem, shell, GitHub, or merge permissions. The same policy engine should govern core and local harnesses, while adapters expose each backend’s enforceable controls and clearly mark advisory limitations.

For upgrades, avoid treating hand-authored multipliers as facts. Use inherited priors with low confidence, explicit lineage, recency decay, and rapid replacement by verified outcomes. Local models should use stable family identities plus immutable quantization/build metadata, preventing both fragmented statistics and misleading equivalence. Cost routing should optimize expected value—quality probability, latency, token/dollar cost, and quota headroom—not raw price.

My recommendation is to approve a model-aware control-plane architecture now: canonical model registry, exact telemetry attribution, family/version capability ledgers, policy-independent entitlements, and one dispatch decision pipeline for core and local harnesses. Roll it out additively with dual-read/dual-write migrations and confidence-gated routing, preserving current harness behavior until measurement proves the model-aware path reliable.

### claude
You've hit your session limit · resets 1:30pm (Asia/Calcutta)

## Synthesis
**Last completed task:** Synthesis and review of panel inputs on first-class Model and ModelFamily architecture.  
**Next task from `todo.md`:** Finalize architectural specification and schema design for canonical Model Registry and Dispatch Pipeline.

---

### Synthesis: First-Class Model & Model Family Architecture

#### 1. Orthogonal Architectural Primitives & Separation of Concerns
The panel reaches consensus on elevating **`ModelFamily`** and **`Model`** to first-class, schema-driven primitives within Synlynk. To maintain clean system boundaries, models are established as a distinct resource dimension alongside existing constructs:
* **Workspace Agent:** Provides identity, tenant context, and legal/operational accountability.
* **Harness (Core / Local):** Provides execution runtimes, tool sandboxing, OS/filesystem isolation, and adapter boundaries.
* **Model / Model Family:** Provides cognitive reasoning capacity, context window geometry, and prompt/tokenizer compatibility.

#### 2. Canonical Model Registry & Telemetry Attribution
A centralized, declarative two-tier schema will govern model definitions:
* **`ModelFamily`:** Defines invariant protocol specifications, tokenizer profiles, context topologies, native tool-calling schemas, and harness adapter bindings.
* **`ModelSpec` / `ModelInstance`:** Encapsulates parameter scale, immutable quantization/build metadata (critical for deterministic local models), context ceilings, token pricing tiers (input, output, cache, reasoning), and locality (remote API vs. local compute).
* **Dual-State Telemetry:** Every dispatch event, cost ledger record, capability rating, and verification log must record both the **`requested_model`** and the **`resolved_model`** actually executed, ensuring full auditability when CLI harnesses switch models dynamically.

#### 3. Security, Entitlement, and Policy Isolation
Model identity is strictly decoupled from authorization:
* **Eligibility vs. Authorization:** Model metadata serves as an **eligibility constraint** (e.g., verifying tool-calling capability or data residency constraints such as air-gapped local execution) but **never grants capabilities or permissions**.
* **Access Control Anchoring:** Filesystem, shell, merge, and credential permissions remain anchored to the Workspace Agent and enforced at the Harness layer.

#### 4. Workload-Aware Expected Value Dispatch
Dispatch will evaluate the tuple `(role, harness, model)` against task complexity, tenant budget, hardware availability, and compliance rules:
* Routing is optimized for **Expected Value**—balancing success probability, latency, dollar/compute cost, and quota headroom rather than basic price minimization.
* Capability ratings will be tracked across `(model_family/version, task_domain)` with harness-specific execution adjustments, initialized with low-confidence priors and rapidly updated via verified task outcomes.

#### 5. Phased Rollout & Migration
The control-plane enhancements will follow an additive deployment strategy:
* Introduce dual-read/dual-write paths across registries and ledgers.
* Use confidence-gated routing to validate model-aware dispatch decisions in shadow mode before cutting over live production traffic.

---

Decision: Synlynk will establish `ModelFamily` and `Model` as first-class architectural primitives within a unified, model-aware control plane across Core and Local harnesses. The architecture will implement a canonical two-tier model registry, enforce strict decoupling between model eligibility and agent authorization, mandate exact requested-versus-resolved telemetry tracking, and deploy an expected-value dispatch pipeline via a phased, dual-read/dual-write migration strategy.

## Decision
Decision: Synlynk will establish `ModelFamily` and `Model` as first-class architectural primitives within a unified, model-aware control plane across Core and Local harnesses. The architecture will implement a canonical two-tier model registry, enforce strict decoupling between model eligibility and agent authorization, mandate exact requested-versus-resolved telemetry tracking, and deploy an expected-value dispatch pipeline via a phased, dual-read/dual-write migration strategy.

> Signatures: see 2026-09-02-making-model-and-model-family-first-clas.json
