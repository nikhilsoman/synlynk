# Unified Onboarding, Sovereign Identity & Fenced Companion Specification

**Status:** Approved  
**Date:** 2026-11-07  
**Goal:** `goal-85656c82` (Unified Developer Journey & Sovereign Onboarding)  
**Supersedes/Extends:** `docs/superpowers/specs/2026-11-05-greenfield-guided-onboarding-design.md`  
**Decision Reference:** [`project-docs/decisions/2026-11-07-authoritative-roadmap-for-public-release-and-two-paradigms.md`](file:///Users/nikhilsoman/dev/synlynk/project-docs/decisions/2026-11-07-authoritative-roadmap-for-public-release-and-two-paradigms.md)

---

## 1. Executive Summary & Intent

This specification establishes the authoritative onboarding protocol for Synlynk. It provides a cohesive, inspiring, and friction-free experience across single-builder greenfield exploration, brownfield enterprise adoption, and multi-team organizations.

It formalizes:
1. **The Synlynk Invariants** (attributing Isaac Asimov's Laws in-screen).
2. **Accessible Terminology:** Replacing cold biological/synthetic framing with intuitive **Human Operator & Digital Teammate** vocabulary.
3. **The Harness vs. Agent Demarcation:** Clarifying the relationship between execution engines and role personas.
4. **Domain & Archetype Specialization:** Tailoring the agent fleet to the workspace's technical domain and organizational hierarchy.
5. **Agent Charters & Recursive Self-Improvement (RSI):** The `Probe → Prose → Compose` evolution loop.
6. **Sovereign Key & Recovery Setup:** Generating root cryptographic authority before workspace divergence.
7. **The Divergent Paths:** Distinct Genesis flows for Greenfield (ideation-to-roadmap) and Brownfield (scan-to-remediation).
8. **Team/Enterprise Hierarchy Discovery:** Cascading policy sync and personal role assignment.
9. **The Fenced Companion:** The ambient, sandboxed Synlynk presence in terminal, IDE, and web surfaces.

---

## 2. Terminology & Conceptual Foundation

### 2.1 Human vs. AI Terminology in User-Facing UX
While internal architecture documentation tracks physical compute models (`res:biological` vs. `res:synthetic`), all user-facing terminal copy, UI labels, and documentation will use clear, dignified, and collaborative terminology:

* **Primary Pair (Recommended for UX/CLI):** **Human Operator** (or **Human Partner**) & **Digital Teammates** (or **Digital Fleet**).
* **Organizational Pair (for Multi-User/Enterprise):** **Sponsor / Lead** & **Autonomous Roles**.
* **Task Pair (for Task Execution):** **Director** & **Specialist**.

### 2.2 The Harness vs. Agent Demarcation
Onboarding explicitly demystifies this distinction:
* **The Harness (The Engine):** The underlying execution runtime and LLM driver (`Claude`, `Codex`, `Agy/Gemini`, `Grok`, `local/oMLX`). It provides raw reasoning, context windows, and execution pipes.
* **The Agent (The Role & Persona):** The structured job archetype (`PM`, `Architect`, `TPM`, `Dev`, `QA`, `Maintainer`). An agent possesses an explicit **Charter**, persistent memory, authorized tool boundaries, and verification contracts.
* *Analogy:* The Harness is the jet engine; the Agent is the pilot certified for a specific mission flight plan.

---

## 3. The 10-Stage Unified Onboarding Flow

```
                      THE UNIFIED GENESIS PROTOCOL
                      
  ┌─────────────────────────────────────────────────────────────────┐
  │ 1. Welcome & The Synlynk Invariants (Attributed to Asimov)      │
  ├─────────────────────────────────────────────────────────────────┤
  │ 2. Conceptual Foundation (Harnesses vs. Digital Roles)          │
  ├─────────────────────────────────────────────────────────────────┤
  │ 3. Workspace Domain & Org Position (Archetype Recommendations)  │
  ├─────────────────────────────────────────────────────────────────┤
  │ 4. Agent Charter Briefing & RSI Loop (Probe ──► Prose ──► Compose)│
  ├─────────────────────────────────────────────────────────────────┤
  │ 5. Sovereign Key Generation & 12-Word Recovery Phrase           │
  └────────────────────────────────┬────────────────────────────────┘
                                   │
                    Divergence Gate │ (Workspace Type)
                  ┌────────────────┴────────────────┐
                  ▼                                 ▼
  ┌───────────────────────────────┐ ┌───────────────────────────────┐
  │ 6A. Greenfield Genesis        │ │ 6B. Brownfield Discovery      │
  │ • PM vision interview         │ │ • AST & dependency scanner    │
  │ • Architect blueprint         │ │ • Test ratio calculation      │
  │ • DECIDE consensus panel      │ │ • Executive Brief generation  │
  │ • Goal 1 & initial roadmap    │ │ • Tech debt remediation goal  │
  └───────────────┬───────────────┘ └───────────────┬───────────────┘
                  │                                 │
                  └────────────────┬────────────────┘
                                   ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │ 7. Team & Enterprise Discovery (Org Hierarchy & Policy Sync)    │
  ├─────────────────────────────────────────────────────────────────┤
  │ 8. The Fenced Companion Awakening (Terminal Statusline & Vizor) │
  └─────────────────────────────────────────────────────────────────┘
```

---

### Detailed Stage Specifications

#### Stage 1: Welcome & The Synlynk Invariants
Displays the four non-negotiable rules governing all digital teammates:
1. **Invariant 0 (Organizational Integrity):** A digital teammate will never compromise repository security, leak credentials, or cause financial or operational damage to the project.
2. **Invariant 1 (Sovereign Primacy):** The Human Operator holds sole legislative and prioritization authority. Digital teammates propose and advise; humans decide.
3. **Invariant 2 (Evidence Over Assertions):** No task, bugfix, or release is marked complete without verified, reproducible evidence (passing tests, clean CI, diff proofs).
4. **Invariant 3 (Resource Stewardship):** Digital teammates must minimize token waste and respect declared budget and quota limits.
*Footnote:* *¹ Derived from and inspired by Isaac Asimov’s Laws of Robotics.*

#### Stage 2: Conceptual Foundation (Harnesses & Digital Teammates)
Probes local systems for available harnesses (`claude`, `codex`, `agy`, `grok`, `omlx`). Explains how Synlynk automatically routes work to the most competent and cost-effective engine.

#### Stage 3: Workspace Domain & Organizational Position
Prompts the operator to select their domain and organizational positioning:
* **Domain Options:** Full-Stack Web, Backend Distributed Systems, Mobile (iOS/Android), AI/ML & Data Engineering, Systems & CLI Plumbing, Embedded/Firmware.
* **Hierarchical Position:** Standalone Exploration, Core Enterprise Platform, Customer-Facing Product, Shared Internal Tooling.
* **Archetype Recommender:** Automatically proposes the optimal initial fleet (e.g., Mobile selects `Mobile Architect`, `iOS/Android Dev`, `UX Designer`, `Release Specialist`).

#### Stage 4: Agent Charters & Recursive Self-Improvement (RSI)
Briefs the operator on Charter guarantees:
* **Authority Boundary:** Exact thresholds where an agent must pause and ask for human approval.
* **Functional Scope:** Specific filesystem subtrees the agent is permitted to edit.
* **Tool & Secret Redaction:** Strict sandboxing preventing unauthorized network or environmental leakage.
* **The RSI Loop (Probe → Prose → Compose):**
  * **Probe:** Measures empirical harness quality and failure modes across real tasks.
  * **Prose:** Autonomously authors refined Standard Operating Procedures (SOPs) based on observed friction.
  * **Compose:** Integrates winning patterns into updated agent charters and durable templates.

#### Stage 5: Sovereign Key & Recovery Phrase Generation
* Generates an `Ed25519` keypair stored in `.synlynk/identity/`.
* Displays a 12-word cryptographic recovery phrase for off-machine backup.
* Links the key to the operator's Git commit signature. This key becomes the Root Authority for all future policy and goal sign-offs.

#### Stage 6: The Divergence Point
* **6A. Greenfield (`synlynk new`):**
  * PM awakens for a 3-question vision interview.
  * Architect generates a system design blueprint.
  * DECIDE panel debates an initial architectural dilemma.
  * TPM generates Goal 1 and initial tasks.
* **6B. Brownfield (`synlynk onboard`):**
  * Deep scanner extracts AST and dependency topology.
  * Assesses test-to-code ratio and vulnerability surface.
  * PM generates an Executive Brief (`project-docs/brief.md`).
  * Establishes Goal 1 as High-Risk Test Remediation or Technical Debt Consolidation.

#### Stage 7: Team & Enterprise Hierarchy Discovery
* Detects upstream Git remote and checks for `.synlynk/enterprise-policy.json`.
* Prompts the user for their organizational role (Enterprise Sponsor, Team Lead, Individual Builder).
* Establishes the non-overridable policy boundary.

#### Stage 8: Awakening the Fenced Companion
* Launches the lightweight background companion service.
* Injects the ambient statusline into the terminal (displaying active goal, burn rate, and health).
* Activates Vizor observatory on port 33333 (`http://localhost:33333`).
* Enforces the sandbox fence: companion operates strictly in observe/assist mode and cannot execute unauthorized writes.
