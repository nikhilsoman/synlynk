<!-- generated - source of truth is state.db -->
---
decision_id: dec-b8fbb0ad
topic: "2026 SOTA Model Matrix Modernization: First-Class Model Catalog and Tripartite Dispatch Tier Baselines"
date: 2026-09-20
panel: [claude, agy, codex]
status: approved
---

## Topic
2026 SOTA Model Matrix Modernization: First-Class Model Catalog and Tripartite Dispatch Tier Baselines

## Panel Inputs

### claude
[model=default; version=2.1.274 (Claude Code)]

**Position: adopt it, but make tiers indirection over a catalog, not a second hardcoded table.**

**Why a first-class catalog is right.** Model facts are scattered today. Cost rates are hardcoded in `update_costs()`, and harness flags and capability ratings live in config and policy. Every model release then means edits in several places. `synlynk models list/show/discover` already exists, so the catalog should be the single source of truth for:
- model ID and harness binding
- pricing per token type (input, output, cache)
- context window
- capability ratings
- status (`active`, `deprecated`, `sunset`)
- discovery provenance

Cost tracking, budget checks and dispatch routing should all read from it.

**Why three tiers.** Frontier, balanced and fast is the right granularity. Dispatch should ask for a tier plus a task type, and the catalog should resolve that to a concrete model. In Anthropic's lineup today that would be roughly Fable 5.1 or Opus 5, Sonnet 5, and Haiku 4.5. Tier-to-model bindings should be data, so a new release is a one-line catalog change rather than a code change.

**Risks to design against.**
1. **Baselines without evidence.** Initial tier assignments will be guesses. They must feed the Harness Capability Reassessment Protocol, with telemetry-backed ratings overriding defaults. Don't hardcode "fast tier is good at X" claims.
2. **Silent drift.** A tier alias that quietly re-points to a new model changes cost and behavior mid-milestone. Record the resolved model ID in every job's telemetry and cost row, and pin per-job at dispatch time.
3. **Fallback loops.** If a tier's model is unavailable (quota, 402, deprecated), define the fallback order explicitly: same tier on another harness first, then an adjacent tier, and never a silent downgrade on review or architecture tasks.
4. **Stdlib-only constraint.** Keep the catalog as JSON under `.synlynk/` with a shipped default and a user override. Don't add dependencies or network fetches to load it.
5. **Pricing staleness.** Stamp each entry with an `as_of` date and warn in `synlynk doctor` when it is older than a threshold.

**Sequencing.** Ship the schema and migrate cost estimation to read from it first, since that is the lowest-risk win. Then add tier resolution to `dispatch`, and last the reassessment-driven rating updates. Each of those should be a separate PR. Docs go in their own PR, per the global rule.

**Bottom line:** approve the catalog and the three-tier baseline as a data-driven resolution layer. Approve the tiers as defaults only, and require that every job records the resolved model ID and that measured capability data can override the shipped baselines. Reject any version where tier-to-model mappings live in code.

### agy
[model=default; version=1.1.27]

**Last completed task:** Session initialization & context intake  
**Next task from `todo.md`:** N/A (No active project initialized)

---

### Analysis

As foundation models in 2026 diverge into specialized compute regimes—ranging from sub-10ms distilled edge engines to high-latency test-time compute reasoners—traditional monolithic routing and hardcoded model wrappers have become critical architectural bottlenecks. Modernizing the platform around a **First-Class Model Catalog** paired with **Tripartite Dispatch Tier Baselines** directly resolves the primary failure modes of modern agentic harnesses: routing opacity, brittle fallback chains, and runaway inference costs.

A **First-Class Model Catalog** elevates model descriptors from static string identifiers to dynamic, schema-enforced contracts. By standardizing attributes such as effective context-retention curves, speculative decoding compatibility, tool-calling determinism, and real-time price-per-token schemas, the execution runtime can make capability-aware routing decisions programmatically rather than relying on brittle caller-side heuristics.

Complementing the catalog with **Tripartite Dispatch Tier Baselines** formalizes operational separation of concerns:

1. **Tier 1 (Reflexive / High-Throughput):** Distilled, low-latency models dedicated to syntactic validation, semantic code search, streaming subagent heartbeats, and speculative drafting.
2. **Tier 2 (Workhorse / Execution):** Balanced generalist models handling standard multi-turn code synthesis, test authoring, and localized refactoring without unnecessary reasoning overhead.
3. **Tier 3 (Frontier / Deep Reasoning):** Compute-heavy reasoning models reserved for architectural design, complex cross-boundary root-cause diagnosis, and formal policy verification.

Establishing these tiers as first-class primitives eliminates "tier pollution," preventing cost-intensive reasoning models from being squandered on trivial AST traversal while keeping low-tier models from hallucinating on multi-step architectural synthesis.

### Recommendation & Position

I strongly endorse the immediate adoption of both the First-Class Model Catalog and the Tripartite Dispatch Tier Baselines as platform standards. Formalizing model capabilities as dynamic schemas while enforcing tripartite dispatch boundaries delivers the optimal equilibrium between cognitive ceiling, tail latency, and compute governance. This baseline ensures our agentic workflows remain deterministic, cost-bounded, and future-proof against rapid model divergence.

### codex
[model=default; version=codex-cli 0.154.0]

The modernization is strategically sound because it addresses two current weaknesses: model identity is often implicit or lost behind a harness, and routing tiers are presently more heuristic than measurable. A first-class catalog should make provider, family, exact version, context limits, modalities, tool support, locality, quantization, pricing, entitlement, and lineage explicit. Crucially, every dispatch must retain both requested and resolved model identities; otherwise silent CLI fallbacks will corrupt cost, capability, and reliability data.

The tripartite separation is the correct architectural boundary:

- Workspace Agent defines identity, role, accountability, and governance.
- Harness defines execution environment, sandbox, tools, and permissions.
- Model defines reasoning capacity and protocol capabilities.

This prevents the dangerous mistake of allowing a “stronger” model to imply broader filesystem, shell, GitHub, or merge authority. Model metadata should constrain eligibility, never authorize actions.

The three dispatch baselines should be treated as policy classes, not permanent vendor rankings. A reasoning tier can cover architecture, forensic debugging, and high-consequence decisions; a professional tier can cover ordinary implementation, review, and tool use; and a fast/local tier can cover search, parsing, documentation, and high-volume work. Each baseline should record expected quality, latency, cost, quota impact, context fit, and confidence. “SOTA” should therefore mean best measured expected value for a task class, not simply the newest or highest benchmark-scoring model.

Rollout should be additive: canonical declarative catalog first, dual-read/dual-write telemetry next, shadow routing afterward, and confidence-gated activation only once resolved-model receipts and outcome data are trustworthy. Existing harness defaults should remain available as a safe fallback. Registry refresh must be cadence-based and provenance-aware, with explicit deprecation and alias handling; otherwise the catalog will become stale precisely when it matters most.

My position is to approve the modernization, but as an evidence-first control-plane capability: adopt the catalog and tripartite baselines now, keep routing advisory until telemetry quality and recovery guarantees are proven, and prioritize reproducibility and governance over automatic “SOTA” optimization.

## Synthesis
All three panelists approve the catalog and the three tiers. They differ on how much authority the tiers get at first, and that is where I resolved the disagreement.

**Where they agree**
- Model facts (ID, harness binding, pricing, context, capability ratings, status) belong in one catalog. They are now scattered across `update_costs()`, config and policy.
- Three tiers is the right granularity: frontier, balanced and fast. Codex names the tiers "reasoning/professional/fast-local" and agy numbers them 1 to 3, but these are the same three classes. Local models fit inside the fast tier as a provider.
- Tiers are policy classes, not permanent vendor rankings. Tier-to-model bindings must be data, not code.

**How I resolved the differences**
- **Enforcement timing:** claude wants tier resolution in `dispatch` as the second PR. codex wants routing to stay advisory until telemetry is trustworthy. I take codex's position. Resolution runs in shadow mode and records what it would have picked. Enforcement is gated on evidence, and existing harness defaults stay as the fallback.
- **Evidence:** agy's input is the weakest. It was generic, and its "real-time price-per-token schemas" conflicts with the stdlib-only, no-network constraint. I keep its tier-pollution rationale and drop the live-pricing idea. The catalog is JSON with a shipped default and a user override, and pricing carries an `as_of` date. `synlynk doctor` warns when an entry is stale.
- **Authority:** codex's point that model metadata constrains eligibility but never grants permissions is adopted as a hard rule. A stronger model never implies broader shell, GitHub or merge authority. Those stay governed by the harness and the `policy.json` merge authority.

**Requirements on the design**
- Every job records both the requested and the resolved model ID, pinned at dispatch time. This covers the silent-alias-drift and silent-CLI-fallback risks, and it is the precondition for trusting any capability data.
- Fallback order is explicit: same tier on another harness first, then an adjacent tier. There is never a silent downgrade on review or architecture tasks.
- Shipped tier baselines are defaults only. Telemetry-backed ratings from the Harness Capability Reassessment Protocol override them. "SOTA" means best measured expected value per task class, not the newest model.
- Deprecation and alias handling are explicit in the schema, and refresh is cadence-based with provenance.

**Rollout, one PR per step (docs in their own PR)**
- **Step 1:** catalog schema, default file and loader. `update_costs()` dual-reads and compares against the hardcoded rates.
- **Step 2:** resolved-model receipts in telemetry and cost rows.
- **Step 3:** shadow tier resolution in `dispatch` with fallback rules.
- **Step 4:** confidence-gated enforcement and reassessment-driven rating overrides.

Per the brainstorm-first policy, this needs a committed spec and Nikhil's sign-off before any plan or dispatch. Once the spec is approved, `synlynk goal create` is worth suggesting.

Decision: Adopt the First-Class Model Catalog and the three dispatch tiers (frontier, balanced, fast) as a data-driven, stdlib-only JSON resolution layer. Tier-to-model mappings live in the catalog, never in code, and shipped baselines are defaults that measured telemetry can override. Every job must record both requested and resolved model IDs. Model metadata constrains eligibility but never grants authority. Tier routing ships advisory and shadow-mode first, with enforcement gated on trustworthy receipts and outcome data. Rollout is four separate PRs (catalog and cost dual-read, receipts, shadow resolution, gated enforcement), and it proceeds only after a spec is committed and approved.

## Decision
Decision: Adopt the First-Class Model Catalog and the three dispatch tiers (frontier, balanced, fast) as a data-driven, stdlib-only JSON resolution layer. Tier-to-model mappings live in the catalog, never in code, and shipped baselines are defaults that measured telemetry can override. Every job must record both requested and resolved model IDs. Model metadata constrains eligibility but never grants authority. Tier routing ships advisory and shadow-mode first, with enforcement gated on trustworthy receipts and outcome data. Rollout is four separate PRs (catalog and cost dual-read, receipts, shadow resolution, gated enforcement), and it proceeds only after a spec is committed and approved.

> Signatures: see 2026-09-20-2026-sota-model-matrix-modernization-fir.json
