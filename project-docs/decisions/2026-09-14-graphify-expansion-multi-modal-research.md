<!-- generated - source of truth is state.db -->
---
decision_id: dec-17f044f8
topic: "Graphify Expansion: Multi-Modal Research Sweeps, Reusable Spike Evaluation Harness, and Fleet-Wide Knowledge Mesh"
date: 2026-09-14
panel: [claude, agy]
status: approved
---

## Topic
Graphify Expansion: Multi-Modal Research Sweeps, Reusable Spike Evaluation Harness, and Fleet-Wide Knowledge Mesh

## Panel Inputs

### claude
## Analysis

The three workstreams sit at very different points on the build-vs-validate spectrum, and bundling them under one "expansion" label obscures that.

**Multi-Modal Research Sweeps** is the highest-risk, highest-variance item — it presumes we already know what signal we're sweeping for across modalities (text/image/audio/etc.), but nothing in the current roadmap has validated that cross-modal research is a bottleneck users hit today. This smells like a capability in search of a use case.

**Reusable Spike Evaluation Harness** is the opposite: low-risk, high-leverage infrastructure. Every dispatched job we run (Codex, Grok, Agy) already produces ad hoc spike results that get manually eyeballed for pass/fail. A standardized harness — consistent scoring, consistent artifact format, replayable — pays for itself immediately in review time and reduces the "trust job-status alone" failure mode that's bitten this project repeatedly (job-status false negatives, Grok's silent no-ops). This is the one item that improves *existing* operations rather than adding new surface area.

**Fleet-Wide Knowledge Mesh** is architecturally the most expensive — it implies a shared memory/context layer across all harnesses (Claude, Agy, Grok, Codex), which is a genuine multi-repo, multi-agent-identity problem (see the ongoing worktree GitHub-App gap and daemon CWD-relative path issues — we don't yet reliably synchronize *simpler* state across worktrees). Attempting a knowledge mesh before those foundational sync bugs are closed risks building an abstraction on a shaky floor.

Sequencing matters more than scope here: the harness gives near-term ROI and de-risks evaluation of the other two; the mesh depends on infra maturity we don't have yet; the multi-modal sweeps have no validated demand signal.

**Recommendation:** Ship the Reusable Spike Evaluation Harness now as a standalone, scoped PR. Defer the Knowledge Mesh until the worktree/daemon state-sync issues are resolved and treat it as its own brainstorm-gated spec. Do not greenlight Multi-Modal Research Sweeps without first identifying a concrete user-facing gap it closes — absent that, it's scope creep dressed as expansion.

### agy
**Last Completed:** Perform structured technical code review of PR #51 (Codex Headless Dispatch)  
**Next Task:** Refine decision flow templates for agents (from [todo.md](file:///Users/nikhilsoman/.gemini/antigravity-cli/scratch/synlynk/project-docs/todo.md#L7))

---

### Analysis: Graphify Expansion

The proposed Graphify expansion—spanning Multi-Modal Research Sweeps, a Reusable Spike Evaluation Harness, and a Fleet-Wide Knowledge Mesh—targets the systemic challenge of agentic amnesia and fragmented, redundant exploratory research across autonomous fleets.

**Key Strengths & Architectural Merits:**
- **Multi-Modal Research Sweeps:** Expanding knowledge extraction beyond static ASTs to architectural diagrams, execution traces, and telemetry bridges the divide between code syntax and runtime reality.
- **Reusable Spike Evaluation Harness:** Standardizing evaluation criteria replaces subjective, ad-hoc spike assessments with deterministic, automated scoring benchmarks.
- **Fleet-Wide Knowledge Mesh:** Federating cross-session learnings into a shared topological graph turns isolated agent inquiries into compounding organizational intelligence.

**Technical Risks & Trade-offs:**
- **Ingestion Overhead & Token Inflation:** Unrestricted multimodal indexing risks ingestion latency bottlenecks and excessive token costs.
- **Graph Bloat & Stale Edges:** Rapidly evolving codebases cause semantic drift unless rigorous TTL and eviction semantics govern node lifecycles.
- **Harness Rigidity:** Imposing an overly heavyweight harness on early spikes may dampen exploratory agility and prototype velocity.

### Recommendation & Position

I recommend **conditional approval with staged rollout sequencing**. The engineering team should immediately build and deploy the **Reusable Spike Evaluation Harness** to establish deterministic performance and quality baselines. Next, integrate **Multi-Modal Research Sweeps** under strict schema-guided, lazy-extraction constraints to control compute and token spend. Finally, gate full federation into the **Fleet-Wide Knowledge Mesh** behind an eventual-consistency, read-heavy model with automated cache eviction before enabling fleet-wide write synchronization. This phased approach captures high-value empirical benchmarking early while insulating the fleet from graph corruption and cost sprawl.

## Synthesis
## Synthesis

Both panelists converge on the same core structural point despite different framings: these three workstreams carry radically different risk profiles and shouldn't be greenlit as a single "expansion." Claude's analysis is sharper on sequencing rationale — it ties the recommendation to concrete, already-documented project failure modes (job-status false negatives, Grok silent no-ops, worktree GitHub-App sync gaps, daemon CWD-relative path bugs) rather than treating the three items abstractly. Agy's response, while identifying real technical risks (token inflation, graph bloat/stale edges, harness rigidity), proposes running all three roughly in parallel under "staged constraints" rather than actually deferring the two higher-risk items — that's a softer sequencing than the evidence supports.

The Reusable Spike Evaluation Harness is the one item with a validated, present-day problem to solve: this project already runs ad hoc dispatched spikes (Codex/Grok/Agy) that get manually eyeballed, and the memory record shows repeated pain from trusting job-status alone. A standardized, replayable scoring harness directly addresses that and requires no new architectural surface.

The Fleet-Wide Knowledge Mesh depends on cross-worktree/cross-harness state sync that this project has not yet gotten right for far simpler cases (the worktree GitHub-App gap, daemon persistence gap #1228 are both still open). Building a shared memory layer on top of unresolved foundational sync bugs is premature — Claude's point stands, and Agy's "eventual-consistency, read-heavy" mitigation doesn't remove the need to fix the floor first.

Multi-Modal Research Sweeps has no demonstrated demand signal in the current roadmap. Agy's proposed mitigation (schema-guided, lazy-extraction constraints) manages cost but doesn't answer the prior question of whether this capability closes any actual gap users hit — per this project's own product-identity test ("does this close an intent-transmission gap"), that check hasn't been done.

**Decision:** Ship the Reusable Spike Evaluation Harness now as a standalone, scoped PR (brainstorm → spec → plan per this project's standing sequence). Defer the Fleet-Wide Knowledge Mesh until the worktree GitHub-App and daemon state-sync issues are closed, then re-open it as its own brainstorm-gated spec. Do not greenlight Multi-Modal Research Sweeps until a concrete user-facing gap is identified and documented — file it as a research/discovery ticket, not an implementation task, in the interim.

## Decision
**Decision:** Ship the Reusable Spike Evaluation Harness now as a standalone, scoped PR (brainstorm → spec → plan per this project's standing sequence). Defer the Fleet-Wide Knowledge Mesh until the worktree GitHub-App and daemon state-sync issues are closed, then re-open it as its own brainstorm-gated spec. Do not greenlight Multi-Modal Research Sweeps until a concrete user-facing gap is identified and documented — file it as a research/discovery ticket, not an implementation task, in the interim.

> Signatures: see 2026-09-14-graphify-expansion-multi-modal-research.json
