---
title: "The Project That Built synlynk: RxCC.me and the Hybrid Workgroup"
date: 2026-06-09
series: "Building the OS for Multi-Agent Development"
post: 1
tags: posts
excerpt: "synlynk did not start with a product thesis. It started with a recurring pain: one human, three AI tools, no shared state, and a live medical product that could not afford coordination failures."
---

# The Project That Built synlynk

synlynk was not designed from first principles. It was extracted from a real workgroup running a real product, after three separate AI agents independently analyzed that workgroup and converged on the same four failure modes.

---

## The RxCC.me Workgroup

RxCC.me is a regulated medical records SaaS. The product handles patient health records — ingested via WhatsApp or direct camera capture, processed by OCR and LLM extraction, stored as FHIR R4 resources in PostgreSQL, and shared with physicians via secure time-bound links. The regulatory surface includes the India DPDP Act, with US HIPAA and SMART on FHIR expansion in planning.

The team:

| Role | Party | Primary domain |
|------|-------|----------------|
| Founder / Technical Lead | Nikhil Soman (human) | Product direction, spec approval, merge gate, deploy approval |
| Primary agent | Claude Code (Sonnet 4.6) | Backend, infra, auth, FHIR, compliance, planning, review, memory |
| Frontend worker | Gemini CLI (2.5 Pro) | Frontend UI, data viz, research, autonomous execution |
| Test worker | Codex CLI | API integration tests, unit test infrastructure |

This is not a team of equals. It is a **principal–agent–specialist hierarchy** with an atypical property: the agents have persistent instruction contexts (CLAUDE.md, GEMINI.md, AGENTS.md) and, in Claude's case, persistent cross-session memory — making them partial substitutes for organizational memory that would otherwise require human staff.

The product's risk model shaped everything. A correctness bug in RxCC.me is not a UX degradation — it is potential medical harm. The risk tolerance is near-zero, which forced the workgroup to develop coordination mechanisms that most teams running AI tools have never needed.

---

## The Coordination Stack

The team coordinates across five stacked layers, each serving a different time horizon:

| Layer | Mechanism | Horizon | Who maintains |
|-------|-----------|---------|---------------|
| Strategic | `roadmap.md` → GitHub Issues / Programme Board | Weeks–months | Human sets, Claude updates |
| Tactical | GitHub Issues with domain/priority labels | Days | Human creates, agents pick up |
| Operational | Feature branches + PRs | Hours | Agents |
| Session | CLAUDE.md / GEMINI.md / AGENTS.md context files | Per session | Human writes, agents obey |
| Institutional | `~/.claude/projects/rxcc/memory/*.md` | Cross-session | Claude writes and reads |

The most architecturally novel element is Layer 5. No other tool in the current ecosystem provides this: Claude maintains a persistent, project-scoped knowledge graph — agent allocation policy, embargo state, GitHub project field IDs, capability ratings, git workflow rules — that survives session boundaries. Gemini and Codex have no equivalent. Each Gemini session starts cold; its behavioral constraints are carried entirely in GEMINI.md.

This asymmetry — one agent with institutional memory, two agents cold-starting every session — is the system's most significant structural vulnerability.

---

## The Attribution Pipeline

Work flows through a fully traced provenance chain:

```
Issue created
  → domain label auto-applied
  → routing comment suggests agent + branch convention
  → agent picks up (feat/claude/, feat/gemini/, test/codex/)
  → PR opened
  → agent:* label applied via CI workflow
  → human reviews
  → merge closes issue
  → board card moves to Done
```

Three-layer attribution — git user.name, Co-Authored-By trailer, branch prefix — creates redundant audit trails across git history, GitHub UI, and the programme board. Branch prefixes are machine-readable, so CI applies labels without human intervention. This is the mechanism that keeps the board current.

Over ~294 merged PRs, this pipeline generated enough attribution data to measure per-agent performance empirically. That data became the evidence base for synlynk's capability routing design.

---

## The Four Living Documents

The RxCC workgroup maintains four documents in real-time throughout every session:

- **roadmap.md** — strategic priorities and status
- **devlogs/** — per-session agent notes, timestamped and attributed
- **costs.md** — per-session token and dollar cost, per agent
- **memory.md** — architectural decisions with `[@username]` attribution

These are not documentation artifacts. They are a **cognitive exoskeleton** — externalized state that compensates for the fundamental statelessness of AI sessions. The devlog entries (S-001 through S-033) read as a project history that would survive the loss of any individual agent's context.

The costs file is the most underrated element. Most teams running AI agents have no per-task cost attribution. RxCC has it, session by session, agent by agent. This creates the financial visibility that synlynk's Budget Pulse was designed to formalize.

---

## The Three Studies

In May 2026, three different AI agents — Claude, Gemini, and Codex — were each asked to analyze the RxCC.me workgroup independently, without seeing each other's analyses. The evidence base: ~294 merged PRs, 8 agent-worker PRs under formal assessment, full session protocols, cross-session memory corpus, devlog entries S-001 through S-033, and the capability assessment tracker.

Three agents, three analytical frameworks, zero coordination between them.

They converged on the same four failure modes.

---

## The Four Shared Failure Modes

### 1. Context Asymmetry

Claude carries rich cross-session memory. Gemini and Codex start cold every session. Every CI convention violation — branch naming, commit trailer format, scope boundary — traces back to this asymmetry. The agent that violated the convention was simply not the agent that remembered it.

The fix is not to give Gemini memory. The fix is to make the shared conventions live in a place that is not any agent's memory — a shared, persistent, tool-agnostic ledger.

### 2. Memory Asymmetry

Claude is the single holder of all institutional knowledge: the embargo state, the FHIR data model decisions, the GitHub project field IDs, the capability ratings, the US expansion planning state. If Claude is unavailable or its context is lost, there is no secondary holder.

This is a single point of knowledge failure. In an org with human staff, it would be called a "bus factor of 1." In a hybrid workgroup, it is a design flaw in the memory architecture.

### 3. Manual Coordination Overhead

Agents cannot communicate directly. Claude knows what Gemini should do next. Gemini cannot read that. The human becomes the message-passing layer — copy-pasting context from Claude's output to Gemini's input, manually propagating handoff notes, manually updating the board when one agent's work creates a dependency for another's.

This is the bottleneck that `synlynk start` and the eventual Trio Protocol are designed to eliminate. The human should be the product owner, not the network packet.

### 4. No Constraint Propagation

Organizational constraints — embargoes, stability windows, scope restrictions — are injected into Claude's memory and CLAUDE.md. But Gemini has its own GEMINI.md and no mechanism for receiving constraint updates from Claude's memory. A constraint added to Claude's context after a session boundary is invisible to Gemini until the human manually updates GEMINI.md.

This is the most dangerous failure mode for a regulated product. An embargo that exists in Claude's memory but not in Gemini's GEMINI.md is an embargo that fails when the next Gemini session runs.

<figure class="brainstorm-visual">
  <iframe src="/assets/brainstorm/product-origin/failure-modes-mapping.html" title="The 4 Failure Modes That Built synlynk" loading="lazy" frameborder="0"></iframe>
  <figcaption>The 4 Failure Modes That Built synlynk</figcaption>
</figure>

---

## From Failure Modes to Product Requirements

The studies' conclusions mapped directly to synlynk's product requirements:

| Failure mode | synlynk requirement |
|---|---|
| Context asymmetry | Shared, tool-agnostic context ledger (`project-docs/`, eventually `state.db`) |
| Memory asymmetry | Harness-maintained institutional memory, not agent-maintained |
| Manual coordination overhead | Autonomous dispatch: `synlynk run`, `synlynk start`, Trio Protocol |
| No constraint propagation | Constraint primitives: `conventions.md` injected into all agent contexts at exec time |

These are not features added after the initial design. They are the initial design, derived from observing a real team's failure modes across hundreds of PRs.

---

## The Broader Implications

The studies also surfaced something beyond the specific failure modes: the **documentation-as-distributed-memory** pattern.

Because agents lack persistent episodic memory across sessions, markdown files act as an externalized hippocampus. `roadmap.md` is strategic memory. `memory.md` is semantic memory (architectural decisions, never regressed). `devlogs/` is episodic memory (sequential audit trail: what Agent A did in session N, visible to Agent B in session N+1). `costs.md` is resource memory.

This documentation architecture is not a workaround. It is the correct answer to the statelessness problem for the current generation of AI tools. synlynk's job is to make it automatic, consistent, and queryable — and eventually to replace the flat-file implementation with SQLite while preserving all the same human-readable guarantees.

The studies also surfaced the competency vector model — the observation that synthetic agents are not constrained by cognitive load the way biological specialists are. A well-funded synthetic agent (one with deep, structured context across all domains) achieves full-stack competency as a default. The ceiling for a synthetic agent is not intelligence; it is **context funding**. synlynk's rooms, eventually, are the context-funding mechanism. The deeper the room history, the more competent the agent.

That framing — synlynk as context funding infrastructure, not just a context injector — is what drove the OS metaphor and the long-arc roadmap through Tokq.

---

*Next: [PR #1 — v0.2.0: Laying the Kernel](./02-pr1-v0.2.0-the-kernel.md) — the first working implementation: watch daemon, checkpoint, context compaction, 46 tests.*
