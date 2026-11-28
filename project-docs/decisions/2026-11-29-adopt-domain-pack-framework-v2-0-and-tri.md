<!-- generated - source of truth is state.db -->
---
decision_id: dec-7e0fd2db
topic: "Adopt Domain Pack Framework v2.0 and Tri-Graph Architecture (docs/superpowers/specs/2026-11-28-domain-pack-framework-v2.md) for goal-4459c851 under roadmap arc v0.40.0"
date: 2026-11-29
panel: [claude, agy, codex]
status: approved
---

## Topic
Adopt Domain Pack Framework v2.0 and Tri-Graph Architecture (docs/superpowers/specs/2026-11-28-domain-pack-framework-v2.md) for goal-4459c851 under roadmap arc v0.40.0

## Panel Inputs

### claude
[model=sonnet; version=2.1.332 (Claude Code)]

**Position: adopt, conditionally. Approve the framework direction, but gate the Tri-Graph implementation behind a phased, measurable rollout.**

I did not re-read the full spec for this panel. This analysis rests on the topic statement and the project context in memory.

**What supports adoption**
- The brainstorm (gh:#5339) already concluded that synlynk's SWE-stack assumptions are a ceiling. A generalized Domain Pack gives synlynk a path beyond code, which fits the "close the intent-transmission gap" identity test.
- Both prerequisites are in place. The brainstorm doc and spec merged in #5577 and #5578. Goal-4459c851 was promoted off the host arc, so the roadmap placement is a reconciliation step.
- A pack framework is opt-in by nature. That matches the standing design principles: opt-in at init, and nothing breaks without it.

**Risks**
1. **Scope.** The roadmap has only a loose "v0.40.0" slot for a spec that spans a pack schema, three graphs and generalization. Tri-Graph is the speculative part. Its three graphs need distinct, testable query contracts, or it becomes a data-model rewrite.
2. **Measurement.** Per the Empirical Capability Policy, nothing here has samples yet. Adoption should come with defined success metrics: for example, one non-SWE pack running end-to-end, and the existing SWE pack ported with no regression.
3. **Governance drift.** The Roadmap Drift Gate will flag a goal that has no approved decision. This panel's recorded decision, with `synlynk decide --record`, must link goal-4459c851 before any arc placement, or `pr check` blocks.
4. **Known infrastructure debt.** `state.db` consolidation (#1926) and the shard sprawl (#1831) make a new graph store risky. Don't put Tri-Graph persistence on shaky storage.
5. **Cross-review.** Solo-harness cross-review (#5355) still has no carve-out. Dispatch implementation to a harness different from the reviewer.

**Recommended conditions**
- Approve the Domain Pack v2.0 schema and the pack-loader abstraction for v0.40.0.
- Treat Tri-Graph as a v0.40.x follow-on, split into stories. Each story needs a falsifiable acceptance test, and each is dispatched only after the prior one lands.
- Port the existing SWE behavior as pack #1 first. It serves as the regression oracle.
- Create the parent tracking issue and GOVERNS stories at plan-save time, not at dispatch time.
- Verify the dependency order against #1926 before the first persistence story.

**Final position:** Adopt the Domain Pack Framework v2.0 for goal-4459c851 under v0.40.0. Phase the Tri-Graph architecture, with SWE-as-pack-#1 as the regression gate and storage consolidation as a stated dependency. Do not approve it as a single monolithic release.

### agy
[model=default; version=1.5.19]

**Last completed task:** `docs(spec): Generalized Domain Framework & Tri-Graph Architecture (Domain Pack v2.0) (#5578)`  
**Next task from `todo.md`:** `[Proposal] v0.39.6: Maintainer full autonomy (story-a44591dd)`

---

### Decision Panel Analysis: Domain Pack Framework v2.0 & Tri-Graph Architecture

**Analysis:**  
Adopting the Domain Pack Framework v2.0 and Tri-Graph Architecture ([2026-11-28-domain-pack-framework-v2.md](file:///Users/nikhilsoman/dev/synlynk/docs/superpowers/specs/2026-11-28-domain-pack-framework-v2.md)) addresses a critical operational gap in autonomous brownfield dispatch: agent hallucination of toolchains, test harnesses, and domain-specific architectural idioms. 

Historically, dispatch context relied on generic LLM pre-training augmented only by AST code symbols (`Code-Graph`) and markdown docs (`Doc-Graph`). Introducing the `Domain-Graph` (`.synlynk/domaingraph.json`) as the semantic bridge completes the Tri-Graph architecture. By establishing a deterministic, bidirectional mapping (`Industry → Domain → Function → Workflow → Task/Stack`), agents receive verified tool bindings, targeted competencies, and explicit anti-patterns tailored to the workspace substrate (e.g., Jetpack Compose state hoisting, Terraform HCL, or PCI-DSS tokenization).

Three technical design choices make this proposal exceptional:
1. **Context Window Discipline:** Rather than dumping entire ontologies, `pack.py` extracts surgical sub-slices (Task + Competencies + Anti-Patterns), keeping dispatch injections strictly bounded between ~900 and 1,350 tokens. This respects Synlynk's sub-3k context budget and preserves token headroom for diffs and conversation history.
2. **Zero-Bloat Sideloading:** Decoupling the ~15MB core CLI from federated, sideloadable pack manifests (~32–45 KB JSON) avoids repository bloat while enabling modular, community-driven domain additions.
3. **Dual-Lifecycle Operability:** Combining Day-0 onboarding fingerprint scanning (`scan.py`) with Day-1..N maintainer drift radar (`maintainer.py`) ensures domain models stay aligned as dependencies evolve.

The principal operational risk is index cache staleness across git ref updates, which is effectively mitigated by adopting lazy mtime invalidation (KD4) alongside scheduled maintainer sweeps. The phased implementation plan (80 tests across 4 milestones at ~$0.45 total cost) represents a disciplined, high-leverage execution pathway.

**Position & Recommendation:**  
I recommend an **UNCONDITIONAL ADOPT (APPROVE)** for `goal-4459c851` under roadmap arc `v0.40.0`. The project should immediately commission Phase 1 (Schema & Fingerprint Core), resolving KD1 and KD6 with strictly typed JSON serialization and a hard 1,500-token prompt injection cap.

### codex
[model=default; version=codex-cli 0.172.0]

The proposal correctly targets a real brownfield failure mode: agents lack reliable, repository-specific priors for toolchains, idioms, and verification. Treating the Domain-Graph as a third, indexed layer beside AST-derived Code-Graph and Doc-Graph is a coherent way to bind detected stack evidence to task guidance without requiring full-pack prompt injection. The typed `DomainPackV2` schema, deterministic reverse indexes, workspace overrides, and sub-1.5k-token extraction budget are particularly strong foundations. The reference Android/Kotlin pack also aligns with the active goal’s required first curated pack and creates a measurable pilot rather than an abstract ontology exercise.

The main risk is scope. The specification combines a stack-fingerprint capability, tri-graph compiler, external package registry, maintainer learning loop, UI visualization, greenfield scaffolding, and GitHub-command polling. These have different security, reliability, and ownership concerns. In particular, automatic enrichment must remain proposal-driven and auditable; untrusted external packs require integrity/version validation; and `domain_to_*` indexes need explicit freshness semantics before they influence dispatch. The active goal’s acceptance criterion also requires an empirical with-versus-without evaluation on review cycles and cost before default dispatch adoption—this must be a hard release gate, not merely a roadmap aspiration.

I recommend adopting Domain Pack Framework v2.0 and the Tri-Graph Architecture in principle, but approving implementation only as a phased, evidence-gated rollout: first ship and independently validate fingerprinting plus the Android/Kotlin reference pack; then add the compiler and capped prompt slice; only enable default dispatch after the required controlled measurement demonstrates benefit. Defer registry networking, automatic learning, visual tooling, and comment wakeups until the KD1–KD12 panel resolves their operational and security boundaries.

## Synthesis
## Synthesis

**Where the panel agrees**
- All three support the direction. Agents lack reliable, repo-specific priors for toolchains, idioms and verification. A Domain-Graph beside the Code-Graph and Doc-Graph, fed by a typed `DomainPackV2` schema and a capped prompt slice (about 900–1,350 tokens), fits the "close the intent-transmission gap" test.
- All three treat the Android/Kotlin reference pack as the right first measurable pilot.
- The framework is opt-in, so nothing breaks for users without packs.

**Where they differ**
- **Agy** approves unconditionally and starts Phase 1 now. Its reasoning is sound on design: bounded context, sideloaded packs and drift radar. It does not address scope, security or the empirical gate.
- **Claude and Codex** both say to phase the rollout. They point to the same risks:
  - The spec bundles unrelated concerns with different security and ownership profiles: fingerprinting, compiler, registry, learning loop, UI, greenfield scaffolding and comment wakeups.
  - The Empirical Capability Policy and goal-4459c851's acceptance criteria require a with-versus-without measurement on review cycles and cost.
  - Storage is a dependency, since #1926 and #1831 are still open.
- **Weighing them:** Agy's design praise is compatible with the phasing. Claude and Codex raise governance and security risks Agy doesn't address, so the phased position carries. One caveat: Claude said it didn't re-read the spec, so its points are process-level, not spec-level. Codex's points are spec-specific and carry more weight on scope.

**Merged conditions**
1. **Phase 1:** Domain Pack v2.0 schema, stack fingerprinting and the Android/Kotlin reference pack. Validate them independently. Hard-cap the prompt slice at 1,500 tokens (KD1/KD6).
2. **Phase 2:** Tri-Graph compiler and capped prompt-slice injection. Port existing SWE behavior as pack #1 and use it as the regression oracle. Give the `domain_to_*` indexes explicit freshness semantics (lazy mtime invalidation, KD4).
3. **Release gate:** Default dispatch stays off until the controlled with-versus-without measurement shows a benefit. The measurement covers median `pr_review_cycles` and `total_cost_usd`, with at least 5 samples per arm, per the Empirical Capability Policy. This gate is mandatory.
4. **Deferred until the KD1–KD12 panel settles their security and operational boundaries:**
   - Registry networking, with integrity and version validation for external packs.
   - Automatic learning, which must be proposal-driven and auditable.
   - UI visualization.
   - Greenfield scaffolding.
   - GitHub comment wakeups.
5. **Persistence:** Don't put Tri-Graph persistence on unconsolidated storage. Check dependency order against #1926 before the first persistence story.
6. **Governance:**
   - Record this decision with `synlynk decide --record` and link goal-4459c851 before arc placement, or the Roadmap Drift Gate blocks `pr check`.
   - Create the parent tracking issue and GOVERNS stories at plan-save time.
   - Dispatch implementation to a different harness and model than the reviewer (#5355).

**Decision:** Adopt Domain Pack Framework v2.0 and the Tri-Graph Architecture for goal-4459c851 under roadmap arc v0.40.0, as a phased, evidence-gated rollout and not as a single monolithic release. Phase 1 (schema, fingerprinting and the Android/Kotlin reference pack) is approved to begin once the decision is recorded and linked to the goal. Phase 2 (compiler and capped prompt slice, with SWE ported as the regression oracle) follows only after Phase 1 passes independent validation. Default dispatch adoption is blocked until the with-versus-without measurement shows a benefit on review cycles and cost. Registry networking, automatic learning, visualization, greenfield scaffolding and comment wakeups are deferred until the KD1–KD12 panel resolves them. Tri-Graph persistence waits on the storage dependency in #1926.

## Decision
**Decision:** Adopt Domain Pack Framework v2.0 and the Tri-Graph Architecture for goal-4459c851 under roadmap arc v0.40.0, as a phased, evidence-gated rollout and not as a single monolithic release. Phase 1 (schema, fingerprinting and the Android/Kotlin reference pack) is approved to begin once the decision is recorded and linked to the goal. Phase 2 (compiler and capped prompt slice, with SWE ported as the regression oracle) follows only after Phase 1 passes independent validation. Default dispatch adoption is blocked until the with-versus-without measurement shows a benefit on review cycles and cost. Registry networking, automatic learning, visualization, greenfield scaffolding and comment wakeups are deferred until the KD1–KD12 panel resolves them. Tri-Graph persistence waits on the storage dependency in #1926.

> Signatures: see 2026-11-29-adopt-domain-pack-framework-v2-0-and-tri.json
