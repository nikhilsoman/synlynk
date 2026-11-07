<!-- generated - source of truth is state.db -->
---
decision_id: dec-7a2b0e91
topic: "Authoritative Roadmap for Public Developer Preview Release and Progressive Evolution toward Two Paradigms: (2a) The Full-Stack Builder and (2b) The Autonomous Emerging Organisation"
date: 2026-11-07
panel: [claude, agy, codex, grok]
status: approved
---

## Topic
How should Synlynk be stabilized, packaged, and positioned for an authoritative public release (Developer Preview) to validate Paradigm 2a (The Full-Stack Builder: a single biological agent assembling a synthetic team to build complete products), while establishing the technical and governance foundation for Phase 2 (Paradigm 2b: The Autonomous Organisation emerging from policy directives and goals leveraging swarms, multi-agent fleets, and enterprise resources)?

## Panel Inputs

### claude
[model=claude-3-7-sonnet; role=architect/pm]

**Analysis & Perspective: The Progression from Full-Stack Builder to Autonomous Org**

Paradigm 2a (The Full-Stack Builder) and Paradigm 2b (The Autonomous Organisation) are not competing architectures; they are sequential phases of organizational emergence. A fully autonomous organisation (2b) cannot exist stably without first mastering the atomic unit of collaboration: a biological agent directing specialized synthetic roles through explicit policy, verified evidence, and unambiguous handoffs (2a).

Synlynk's core breakthrough over the past 5 months is the realization that generalist chat agents fail at complex engineering, whereas specialized roles (PM, Architect, TPM, Dev, QA, Maintainer) bound by charters, state machines, and verification contracts succeed. For individual developers, Synlynk transforms a solo programmer into a complete software engineering organization. To validate this hypothesis with real users, Synlynk must be released publicly without commercial friction.

However, enterprise adoption requires the exact same foundational guarantees: predictability, auditability, secret safety, and policy compliance. An enterprise will not deploy an autonomous swarm (2b) unless it can observe and control the role boundaries established in (2a).

Therefore, Phase 1 must focus single-mindedly on delivering an unassailable "Full-Stack Builder" experience. The public release must make a developer feel the immediate leverage of an assembled fleet in their first 15 minutes. Once real developer feedback validates role coordination, Phase 2 can expand to enterprise swarms, multi-tenant policy registries, and autonomous goal fulfillment.

**Position:** Commit to a two-phase roadmap. Phase 1 proves Paradigm 2a via a friction-free public Developer Preview focused on single-user multi-agent leverage. Phase 2 extends this substrate into Paradigm 2b for enterprise teams and autonomous multi-agent organizations.

### agy
[model=gemini-3.8-flash; role=frontend/onboarding]

**Analysis & Perspective: The First 15 Minutes to Wow and Ergonomic Cohesion**

The greatest risk to Synlynk's public debut is not lack of capability, but cognitive overload and installation friction. Over 5 months of rapid evolution, Synlynk has accumulated immense power, but also operational complexity: multiple CLI verbs, internal jargon (GOVERNS, FTUE, DECIDE, SOPs), and historical artifacts sitting in the working tree.

To prove Paradigm 2a, Synlynk must deliver an undeniable "Time-to-Wow" under 15 minutes. An individual developer or enterprise evaluator should install Synlynk, run a single command (`synlynk new` for greenfield or `synlynk onboard` for brownfield), and immediately witness their fleet awaken:
1. The PM synthesizes the executive brief and maps goals.
2. The Architect evaluates tech stacks and presents trade-offs via interactive DECIDE panels.
3. The TPM breaks goals into verifiable tasks.
4. Dev and QA execute under test-driven verification.

To achieve this, Phase 1 must strip away internal scaffolding:
- Clean the repository root of internal cost and audit logs.
- Deliver a unified, beautiful terminal UX (hyperlinks, formatted summary cards, clear progress spinners).
- Provide a crystal-clear "Quickstart Guide" that focuses entirely on the user's journey from idea to working software.

**Position:** Synlynk's public release must be ergonomic, self-healing, and approachable. Make `synlynk new` and `synlynk start` the premier entry points for the Full-Stack Builder, establishing instant credibility before introducing deeper enterprise orchestration.

### codex
[model=codex-cli-0.163.0; role=core-systems/cli-plumbing]

**Analysis & Perspective: Engineering Hermeticity, Packaging, and Ground-Truth Stability**

From a systems engineering perspective, Synlynk cannot achieve widespread adoption or enterprise credibility until its execution environment is completely hermetic. The divergence between Agy's release reporting and Claude's audit highlighted a critical vulnerability: Synlynk has operated in an "editable install inside worktrees" paradigm that leaks host environment assumptions and causes crash-loops when ephemeral worktrees are pruned (LIVE-30).

For Synlynk to be installed by thousands of outside developers and run in corporate CI or dev machines:
1. **Packaging Hermeticity (LIVE-30 Option 1):** Synlynk must be packaged as a standalone, non-editable wheel or pipx installation. Long-lived daemons (Vizor) and dispatch child processes must resolve against a permanent, worktree-independent interpreter environment.
2. **Deterministic Green Test Suite:** The test suite must pass 100% on a pristine machine without requiring loose permissions on `~/.synlynk` or ambient credentials. Host-dependent paths in `synlynk/doctor.py` and `synlynk/product_store.py` must be strictly virtualized under tests.
3. **Single Source of Truth:** `state.db` must remain the definitive authority, with on-demand view projections (`todo.md`, `roadmap.md`, `costs.md`) rendered without file-lock contention or git-drift false positives.

Building Phase 2's distributed swarms on an unstable local substrate would compound technical debt. Stabilizing the core execution engine now ensures that both individual builders (2a) and autonomous enterprise swarms (2b) inherit bulletproof reliability.

**Position:** Require 100% packaging hermeticity, zero test failures on clean clones, and worktree-independent process execution as non-negotiable gates for the Developer Preview release.

### grok
[model=grok-1.0.70; role=infra/capability-routing]

**Analysis & Perspective: Policy-Driven Autonomy and Capability Growth**

Paradigm 2b posits that an autonomous organization emerges from a set of policy directives and goals, leveraging any available resources (biological, AI models, tools, infra). This requires a dynamic capability engine rather than hardcoded agent pipelines.

Synlynk's architecture already contains the seeds of this future:
- Dynamic capability probing (`synlynk probe`) assessing harness competence.
- Dual-ledger cost and quota tracking separating subscriptions from meter-draining API tokens.
- Role charters that define what an agent is permitted to touch and who must review it.

To prepare for Phase 2 while launching Phase 1:
1. **Policy as the Control Plane:** In both indie and enterprise modes, the human operator defines the policy directives (budget caps, branch protection, security boundaries, sign-off thresholds). Synlynk's engine must autonomously select the optimal harness (Claude, Codex, Agy, Grok, or local models) based on proven empirical capability.
2. **Autonomous Capability Expansion:** The platform should monitor its own execution, recognize when an agent struggles with a task type, and dynamically adjust routing or recommend charter evolution.
3. **Enterprise Resource Boundaries:** Phase 1 must establish clean separation between secrets, credentials, and dispatch worktrees so enterprises can trust Synlynk with proprietary codebases.

**Position:** Ground the public release on explicit policy directives and cost transparency. Ensure Phase 1 provides full visibility into agent actions, paving the way for autonomous enterprise swarm orchestration in Phase 2.

## Synthesis
The panel unanimously converges on a cohesive, two-phase strategy that directly validates Paradigms 2a and 2b:

1. **Strategic Progression (2a → 2b):** Paradigm 2a (The Full-Stack Builder) is the necessary crucible for Paradigm 2b (The Autonomous Organisation). Individual developers and small engineering pods will stress-test role charters, verification contracts, and multi-agent coordination. Once these atomic interactions are proven stable in public hands, Phase 2 scales them into multi-tenant, policy-governed autonomous enterprise swarms.
2. **Immediate Stability Prerequisite:** The public Developer Preview cannot launch on paper claims. It requires:
   - Completion of LIVE-30 Option 1 (hermetic standalone wheel/pipx installation).
   - Zero test failures across the full test suite on clean environments.
   - Elimination of root directory clutter and consolidation of operational documentation.
3. **The User Journey:** The initial product experience must center around empowering a single builder with a synthetic engineering team (PM, Architect, TPM, Dev, QA) via `synlynk new` and `synlynk start`, guided by transparent DECIDE panels and verified through test-driven delivery.

## Decision
Adopt the Authoritative Master Roadmap for Synlynk:
- **Phase 1: The Full-Stack Builder (v0.29.0 Developer Preview Launch)** — Hermetic packaging, bulletproof local execution, zero-cost public release, frictionless 15-minute onboarding, and empirical validation of Paradigm 2a with independent developers and tech leads.
- **Phase 2: The Autonomous Organisation (v1.0.0+ Enterprise & Swarm Expansion)** — Multi-tenant workspace synchronization, remote swarm runners, dynamic capability crawling, and policy-driven autonomous goal execution (Paradigm 2b).

> Signatures: see 2026-11-07-authoritative-roadmap-for-public-release-and-two-paradigms.json
