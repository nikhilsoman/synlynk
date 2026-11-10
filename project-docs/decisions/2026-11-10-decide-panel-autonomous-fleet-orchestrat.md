<!-- generated - source of truth is state.db -->
---
decision_id: dec-4a53a2ee
topic: "DECIDE PANEL: Autonomous Fleet Orchestrator, Archetype Abstraction & Visual Organogram Designer (Horizon 3 Foundation).

CONTEXT: A design spec has been committed at docs/superpowers/specs/2026-11-10-autonomous-fleet-orchestrator-and-organogram-designer-design.md (commit 40aeb9ac). It proposes: (1) 6 universal core archetypes (orchestrator, strategist, director, creator, inspector, custodian) decoupled from job titles, with 1:N cardinality per workspace; (2) 3D taxonomic grounding via SFIA 8/9, APQC, and NAICS with deterministic tool/resource inference for FTUE/BAU; (3) a 3-tier Autonomy Evolutionary Ladder (L1 Advisory -> L2 Gated -> L3 Autonomous) gated by Google Research Harness^2 RSI scoring and automated circuit-breaker demotion; (4) a Vizor Visual Organogram & Workflow Designer node-graph canvas; (5) TPM agent as reference orchestrator implementation.

Evaluate and give a clear position on:
1. 6 Universal Archetypes & 1:N Cardinality: Does this clean abstraction hold across diverse domains (Software, Hitchcock Film, Vdowrx, Rxcc) without leaky abstractions?
2. Deterministic Resource Inference: Is grounding in SFIA 8/9 + APQC + NAICS practical and effective for auto-recommending MCP tools, path scopes, and prompts?
3. Autonomy Ladder & RSI Circuit Breakers: Is the L1->L2->L3 progression with empirical RSI telemetry and automated tripwire demotion safe and operationally sound?
4. Vizor Organogram Designer: Is an offline-first HTML/SVG node-graph canvas the right interface for managing agent organograms and workflow edges?
5. Future Roadmap & Empirical Usage Gates: Where and how should this design expand over time (cross-workspace federation, cloud swarms, multi-tenant org charts), and what empirical usage gates (sample sizes, error ceilings, human override frequencies) should govern promotion across milestones?

Provide a structured, rigorous assessment with a definitive recommendation."
date: 2026-11-10
panel: [claude, agy, codex, grok]
status: approved
---

## Topic
DECIDE PANEL: Autonomous Fleet Orchestrator, Archetype Abstraction & Visual Organogram Designer (Horizon 3 Foundation).

CONTEXT: A design spec has been committed at docs/superpowers/specs/2026-11-10-autonomous-fleet-orchestrator-and-organogram-designer-design.md (commit 40aeb9ac). It proposes: (1) 6 universal core archetypes (orchestrator, strategist, director, creator, inspector, custodian) decoupled from job titles, with 1:N cardinality per workspace; (2) 3D taxonomic grounding via SFIA 8/9, APQC, and NAICS with deterministic tool/resource inference for FTUE/BAU; (3) a 3-tier Autonomy Evolutionary Ladder (L1 Advisory -> L2 Gated -> L3 Autonomous) gated by Google Research Harness^2 RSI scoring and automated circuit-breaker demotion; (4) a Vizor Visual Organogram & Workflow Designer node-graph canvas; (5) TPM agent as reference orchestrator implementation.

Evaluate and give a clear position on:
1. 6 Universal Archetypes & 1:N Cardinality: Does this clean abstraction hold across diverse domains (Software, Hitchcock Film, Vdowrx, Rxcc) without leaky abstractions?
2. Deterministic Resource Inference: Is grounding in SFIA 8/9 + APQC + NAICS practical and effective for auto-recommending MCP tools, path scopes, and prompts?
3. Autonomy Ladder & RSI Circuit Breakers: Is the L1->L2->L3 progression with empirical RSI telemetry and automated tripwire demotion safe and operationally sound?
4. Vizor Organogram Designer: Is an offline-first HTML/SVG node-graph canvas the right interface for managing agent organograms and workflow edges?
5. Future Roadmap & Empirical Usage Gates: Where and how should this design expand over time (cross-workspace federation, cloud swarms, multi-tenant org charts), and what empirical usage gates (sample sizes, error ceilings, human override frequencies) should govern promotion across milestones?

Provide a structured, rigorous assessment with a definitive recommendation.

## Panel Inputs

### claude
[model=default; version=2.1.322 (Claude Code)]

## Panel Assessment: Autonomous Fleet Orchestrator / Organogram Designer

**1. Archetypes & 1:N cardinality.** The six-way split (orchestrator/strategist/director/creator/inspector/custodian) holds up across the four domain examples given — each maps cleanly without obvious overlap, and 1:N cardinality correctly avoids forcing e.g. `@editor` and `@sound-designer` into one bucket. The leak risk is at the *edges*, not the core: `strategist` vs `director` will blur in small workspaces (who gates scope vs. who gates the plan when there's one principal), and `custodian` is thin on creative-domain examples (no Hitchcock/Vdowrx custodian shown at all). Acceptable for v1 if the schema allows an agent to carry a secondary archetype later — confirm it does before locking the DB migration.

**2. Deterministic resource inference (SFIA/APQC/NAICS).** Directionally sound and the crosswalk table is genuinely useful documentation even before any code ships. But "deterministic" is doing a lot of work: SFIA codes were designed for IT skill levels, not tool-binding rules, so the `creator+SNDD → ffmpeg/sox` mappings are hand-curated heuristics dressed as a taxonomy lookup. That's fine as a seed table, but the spec should name it as a maintained mapping, not claim it's derived from the standards themselves.

**3. Autonomy ladder + RSI circuit breakers.** This is the strongest section — explicit human-authorized promotion, automatic demotion, and the weighted formula are safety-appropriate. The RSI formula's four weights ($w_1$–$w_4$) are unspecified; don't ship with magic defaults untested against real telemetry. Section 9's "can never self-promote" invariant is correctly load-bearing and must be enforced at the DB/write-path level, not just by convention.

**4. Organogram canvas.** Offline-first HTML/SVG is consistent with Vizor's existing local-first posture and is the right call — no new infra dependency.

**5. Roadmap/gates.** Phased plan (Phase 1 DB → Phase 5 TPM integration) is correctly sequenced. Before Phase 3 ships, define the ≥20-cycle/≥90%-score promotion threshold's sample size per archetype, not just per agent, since creative/biopharma archetypes will be data-sparse initially.

**Recommendation: APPROVE for Phase 1–2, conditional on Phase 3 not shipping until RSI weights are calibrated against at least one real non-software domain workspace.** The abstraction is sound; the risk is overclaiming determinism in the taxonomy layer and under-specifying RSI weight provenance before gating real autonomy promotions on it.

### agy
[model=default; version=1.5.4]

**Last completed task:** Drafted autonomous fleet orchestrator and organogram designer design spec ([40aeb9ac](file:///Users/nikhilsoman/dev/synlynk/.worktrees/feat-agy-autonomous-fleet-organogram-spec/docs/superpowers/specs/2026-11-10-autonomous-fleet-orchestrator-and-organogram-designer-design.md))  
**Next task:** Decide Panel: Autonomous Fleet Orchestrator, Archetype Abstraction & Visual Organogram Designer evaluation

---

### Panel Evaluation: Horizon 3 Platform Foundation

1. **6 Universal Archetypes & 1:N Cardinality:** **Sound & Resilient.** The 6 archetypes (`orchestrator`, `strategist`, `director`, `creator`, `inspector`, `custodian`) cleanly decouple invariant lifecycle mechanics from superficial job titles. The 1:N cardinality solves title-lock, enabling multi-specialist pipelines across software, film (`Hitchcock`), video (`Vdowrx`), and biopharma (`Rxcc`) without semantic leakage.
2. **Deterministic Resource Inference:** **High Operational Value.** Grounding configurations in SFIA 8/9, APQC, and NAICS translates established industry competencies into deterministic tuples (scoped filesystem globs, MCP tools, and verification contracts). This eliminates "blank canvas" onboarding paralysis in FTUE and enforces predictable blast radiuses during BAU.
3. **Autonomy Ladder & RSI Circuit Breakers:** **Robust Safety Architecture.** Grounding autonomy progression in empirical telemetry ($A_{\text{proposal}} \ge 90\%$, $R_{\text{rework}} \le 5\%$, $V_{\text{verification}} \ge 95\%$) operationalizes Google Research's Harness² framework. Crucially, the asymmetric governance model—cryptographic human authorization required for L1 $\to$ L2 $\to$ L3 promotion paired with automated, unilateral circuit-breaker demotion upon failure—guarantees runtime containment.
4. **Vizor Organogram Designer:** **Architecturally Cohesive.** An offline-first HTML/SVG node-graph canvas preserves Synlynk’s zero-cloud-dependency invariant while providing an intuitive spatial mental model for delegation, review gates, and escalation. The graph compiler serializing visual topology directly to `state.db` and agent charters eliminates configuration drift.
5. **Roadmap & Empirical Usage Gates:** **Controlled Horizon 3 Evolution.** Future expansion should evolve from local workspaces to federated cross-workspace delegation and sovereign cloud swarms. Fleet promotion must be governed by empirical gates: minimum sample size $N \ge 30$ task cycles, unhandled error ceiling $\le 2\%$, and a human override frequency $\le 5\%$ over 14 rolling days.

---

### Definitive Recommendation

**Position: Strongly Approve for Immediate Implementation.** The design spec ([`40aeb9ac`](file:///Users/nikhilsoman/dev/synlynk/.worktrees/feat-agy-autonomous-fleet-organogram-spec/docs/superpowers/specs/2026-11-10-autonomous-fleet-orchestrator-and-organogram-designer-design.md)) delivers the foundational abstraction required for Horizon 3 multi-domain autonomy without introducing technical debt or architectural bloat. I recommend ratifying the spec and immediately proceeding to Phase 1 schema migration and archetype core implementation.

### codex
[model=default; version=codex-cli 0.167.0]

## Assessment

1. **Six archetypes and 1:N cardinality — conditionally sound.**  
The six archetypes are a useful control-plane abstraction across Software, Hitchcock, Vdowrx, and Rxcc because they describe execution responsibilities rather than job titles. The 1:N model is essential: multiple creators, inspectors, or orchestrators are normal. However, the abstraction will leak if lifecycle contracts encode software assumptions such as TDD, merges, worktrees, or “technical architecture.” Contracts should remain capability-neutral, with domain-specific policies layered underneath. Also define composition rules: an agent may need multiple capabilities, while an archetype should remain its primary accountability.

2. **Deterministic resource inference — useful, but only as recommendation.**  
SFIA, APQC, and NAICS provide strong vocabulary and onboarding defaults, but they cannot deterministically infer safe tools, prompts, or filesystem scopes from taxonomy alone. Codes are broad, versioned, and context-sensitive. Treat inference as a signed, explainable baseline requiring workspace-policy validation, least-privilege review, and human confirmation for write-capable tools or paths. Never allow taxonomy output to grant authority directly.

3. **Autonomy ladder and RSI — directionally correct, operationally incomplete.**  
L1→L2→L3 is safer than a binary flag, and automatic demotion is appropriate. Yet proposal acceptance is a weak metric: humans may rubber-stamp work, tasks may be easy, and telemetry can be gamed by selection effects. Promotion needs stratified workloads, severity-weighted failures, confidence intervals, budget ceilings, rollback drills, and cooldowns. Twenty successful cycles is insufficient for high-impact autonomy.

4. **Vizor — correct interface for the MVP.**  
An offline-first SVG/HTML graph suits transparency, portability, and disconnected environments. It should provide schema validation, undo/versioning, deterministic graph compilation, keyboard accessibility, and a textual export for auditability. Do not make the canvas the sole source of truth; treat it as a projection over signed manifests and database state.

## Recommendation

**Approve as a Horizon 3 foundation, with conditions.** Gate implementation on capability-neutral contracts, policy-mediated inference, and stronger empirical promotion criteria. Suggested gates are 100+ stratified L2 cycles before L3 eligibility, zero unresolved critical safety incidents, <2% rollback/rework for low-risk work, <0.5% severe failures, ≥95% first-pass verification, and human override rates below 10% across three independent workload bands. Advance to federation or cloud swarms only after replicated workspaces demonstrate these thresholds for 500+ cycles, with measured cross-tenant isolation and rollback reliability.

### grok
[model=default; version=grok 1.0.70 (f50904eaee6c) [stable]]

I'll read the committed design spec and judge the five decisions against how synlynk actually runs fleets.**Amend, then adopt.** The six archetypes and the earned-autonomy ladder are the right Horizon 3 core. The SFIA/APQC/NAICS inference engine and the “RSI” framing are not safe to build as specified.

**Archetypes.** Orchestrator, strategist, director, creator, inspector, and custodian, with many agents per archetype, can cover software, Hitchcock, Vdowrx, and Rxcc as a closed dispatch enum. The contracts leak as written: creator is locked to TDD, director folds architecture into requirements, and continuity or compliance is forced through TEST. Keep one primary archetype, allow one secondary hat, and leave the current ten software roles as seeds. Lifecycle steps must come from the domain profile, not the archetype row.

**Inference.** Several cited codes are not real SFIA skills, SFIA does not cover film or clinical work, and SFIA/APQC wording is licensed. NAICS classifies establishments, so it cannot choose MCP servers or write paths. Use versioned, in-repo domain packs. Suggest tools and paths; require a conductor to confirm every write grant. Automatic scoping from a skill code is an authorization bug.

**Ladder.** L1 advisory, L2 human-gated dispatch, and L3 autonomous execution is sound if promotion stays human-only and demotion is automatic. Treat the formula as a reliability score: weights are undefined, and 90/5/95 will not hold outside mature software. Sentinel or an inspector must write the ledger, not the agent being scored. Domain caps are mandatory — Rxcc stays at L2 regardless of score. Trip token runaway and repeated failure of the same wave. Do not demote on a generic merge conflict. In v0.31, only TPM may be L3-eligible.

**Vizor.** Store delegation, review_gate, and escalation as the source of truth. Ship a tree and an inspection drawer first. Add the offline SVG canvas only after the tree proves too clumsy. Save-and-apply must show a policy diff and use the same human authorization as promotion.

**Gates.** Leave federation, cloud swarms, and multi-tenant charts out of this horizon. Enable L3 only after 20 TPM cycles, zero self-promotions, a passed demotion drill, and a human override rate of 25% or less. Require two non-software workspaces, 30 L2 cycles each, false demotion under 10%, and zero bad path grants before any later expansion. Use n≥20, rework ≤15% to suggest L2, and ≤8% over the last 20 cycles for L3 eligibility.

**Recommendation.** Approve only with these amendments. Build the archetype schema, the role-seed map, and the TPM ladder with domain caps and sentinel demotion. Replace the taxonomic engine with local profile packs, and defer the freeform canvas and every cross-workspace feature until those gates are measured.

## Synthesis
## Synthesis

All four panelists converge on the core shape: six domain-neutral archetypes with 1:N cardinality, and a human-gated autonomy ladder with automatic demotion, are the right Horizon 3 primitives. They diverge sharply on the taxonomic-grounding claim and on how much empirical rigor gates autonomy promotion before this ships.

**Archetypes.** Approved by all four as the correct abstraction, but Codex and Grok both flag the same leak: the current contracts bake software-specific mechanics (TDD, merges, worktrees) into archetype definitions rather than keeping archetypes capability-neutral with domain-specific lifecycle packs layered underneath. Grok's specific example — `creator` locked to TDD, `director` conflating architecture with requirements — is concrete enough to require a fix before Phase 1 schema lock. Resolution: ship the six-archetype enum now, but lifecycle steps must load from a domain profile, not from the archetype row itself; allow a secondary archetype hat per agent.

**Resource inference.** This is where the panel actually disagrees, not just adds nuance. Claude and Codex caution that "deterministic" overclaims a curated heuristic table. Grok goes further with a specific, serious objection: several cited SFIA/APQC/NAICS codes don't do the job claimed (SFIA doesn't cover film/clinical domains, NAICS classifies establishments not tasks, and licensing on SFIA/APQC wording is a real constraint), and calls automatic tool/path scoping from a skill code an **authorization bug**, not a convenience feature. This is the most load-bearing disagreement and Grok's framing wins on specificity: no taxonomy lookup may grant write-capable tool or filesystem authority unconfirmed. Resolution: rename the mechanism from "deterministic inference" to "suggested baseline, human-confirmed grant" — versioned in-repo domain packs seed suggestions; a conductor/human must confirm any write-capable grant. This is a scope cut, not a rejection of the taxonomy layer as documentation.

**Autonomy ladder + RSI.** Directionally approved by all four. But Codex and Grok both note the promotion metrics (90/5/95, proposal-acceptance as a reliability proxy) are too easily gamed and too uniform across domains with wildly different risk profiles (Rxcc vs. Hitchcock). Grok's addition is the sharpest operational constraint: the RSI ledger must be written by a non-self-interested component (sentinel/inspector), not the agent being scored, and domain-specific caps apply regardless of score (e.g., Rxcc stays capped at L2). Resolution: adopt this — automatic demotion write-path goes through sentinel/inspector, not self-report; L3 eligibility restricted to TPM only at launch; per-domain caps are configuration, not an exception process.

**Vizor organogram canvas.** Unanimous approval of offline-first HTML/SVG as consistent with synlynk's local-first posture. Codex and Grok add that the canvas must be a projection over `state.db`/signed manifests, not the source of truth, and Grok suggests shipping a simpler tree/inspection view first, adding the freeform canvas only once a tree view proves insufficient. Reasonable sequencing refinement, not a blocker — doesn't change Phase 1-2 scope.

**Roadmap/gates.** All four want tighter empirical gating than loose defaults. Codex and Grok both supply concrete numeric floors (stratified multi-domain cycles, override-rate ceilings, demotion-drill requirements) well above a casual 20-cycle bar. Federation/cloud swarms/multi-tenant org charts should explicitly stay out of scope for this horizon, gated behind replicated non-software-workspace evidence.

Decision: **Approve the design spec for Phase 1–2 implementation (archetype schema + autonomy ladder core + Vizor view) with three binding amendments before any code lands**: (1) archetype lifecycle contracts must be capability-neutral with domain-specific packs, not software mechanics baked into the archetype row; (2) the SFIA/APQC/NAICS layer is reclassified from "deterministic inference" to a human-confirmed suggestion baseline — no automatic grant of write-capable tools or path scopes from taxonomy lookup alone; and (3) RSI scoring/demotion is written by sentinel/inspector (never agent self-report), L3 eligibility is restricted to the TPM reference implementation only at launch, and per-domain autonomy caps (e.g., Rxcc ≤ L2) are mandatory configuration. Phase 3 (cross-domain RSI-gated promotion) and all federation/cloud-swarm/multi-tenant work remain blocked until two non-software workspaces each clear ≥30 stratified L2 cycles with sub-10% human override rate and zero self-promotion incidents, per Codex's and Grok's empirical floors.

## Decision
Decision: **Approve the design spec for Phase 1–2 implementation (archetype schema + autonomy ladder core + Vizor view) with three binding amendments before any code lands**: (1) archetype lifecycle contracts must be capability-neutral with domain-specific packs, not software mechanics baked into the archetype row; (2) the SFIA/APQC/NAICS layer is reclassified from "deterministic inference" to a human-confirmed suggestion baseline — no automatic grant of write-capable tools or path scopes from taxonomy lookup alone; and (3) RSI scoring/demotion is written by sentinel/inspector (never agent self-report), L3 eligibility is restricted to the TPM reference implementation only at launch, and per-domain autonomy caps (e.g., Rxcc ≤ L2) are mandatory configuration. Phase 3 (cross-domain RSI-gated promotion) and all federation/cloud-swarm/multi-tenant work remain blocked until two non-software workspaces each clear ≥30 stratified L2 cycles with sub-10% human override rate and zero self-promotion incidents, per Codex's and Grok's empirical floors.

> Signatures: see 2026-11-10-decide-panel-autonomous-fleet-orchestrat.json
