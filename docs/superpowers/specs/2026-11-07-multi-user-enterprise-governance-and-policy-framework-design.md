# Multi-User & Enterprise Governance and Policy Framework Design

**Status:** Approved  
**Date:** 2026-11-07  
**Decision Reference:** [`project-docs/decisions/2026-11-07-authoritative-roadmap-for-public-release-and-two-paradigms.md`](file:///Users/nikhilsoman/dev/synlynk/project-docs/decisions/2026-11-07-authoritative-roadmap-for-public-release-and-two-paradigms.md) (ID: `dec-7a2b0e91`)  
**Linked Goals:**
- `goal-2c19bbad`: Enterprise team workspace sync architecture and centralized multi-tenant governance
- `goal-b1f1a8bf`: Unified sandbox provider architecture and secret boundary enforcement for multi-agent fleets
- `goal-bd5eaa14`: Safe autonomous operations (claims, leases, containment, and audit)
- `goal-issue-2412`: Operationalize autonomous GOVERNS SDLC (governance, agent ownership, and cost provenance)
- `goal-0b891b5f`: Multi-role autonomous fleet orchestration

---

## 1. Executive Summary & Purpose

Synlynk's evolution from a single-operator full-stack builder harness (Paradigm 2a) into an enterprise-grade multi-agent autonomous organization (Paradigm 2b) requires a rigorous, non-bypassable governance framework. 

This document defines:
1. **Cascading Policy Inheritance:** How global enterprise rules enforce strict compliance, security, and cost bounds across nested workspaces.
2. **Federated Sovereign Governance:** How biological human authority remains sovereign at each scope while synthetic agents act strictly as advisors and executors.
3. **Dual-Plane Organizational Hierarchy:** The clean decoupling of human business accountability from synthetic execution pipelines.
4. **Append-Only Merkle Decision Ledger:** A cryptographically signed (Git + Ed25519) provenance ledger that replaces speculative blockchain overhead with mathematical, audit-grade verification.

---

## 2. Cascading Policy Inheritance (Constitutional Control Plane)

In multi-user and enterprise environments, policy is not a passive configuration file; it is a **fail-closed constitutional boundary**. 

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Enterprise Root Policy (`.synlynk/enterprise-policy.json`)│
│    • Approved Model Registries (e.g. Zero-Retention only)   │
│    • Hard Organization Budget Ceilings ($/month & alerts)   │
│    • Mandatory Compliance Scanners & Secret Redactors       │
│    • Global Branch Protection & Merge Authority Matrix      │
└──────────────────────────────┬──────────────────────────────┘
                               │ (Inherited & Non-Overridable)
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. Team / Department Policy (`.synlynk/team-policy.json`)   │
│    • Department Token Quotas & Cloud Runner Allocations     │
│    • Code Domain Ownership (e.g. Core vs. Frontend vs. Ops) │
│    • Mandatory Cross-Harness Review Gates (e.g. QA ≠ Dev)   │
└──────────────────────────────┬──────────────────────────────┘
                               │ (Inherited & Refined)
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. Workspace / Project Policy (`.synlynk/policy.json`)      │
│    • Project Goals, Task DAGs, and Role Charters            │
│    • Sprint-Specific Budgets & DECIDE Panel Quorums         │
└─────────────────────────────────────────────────────────────┘
```

### The Non-Overridable Invariant Rule
* **Tightening Allowed:** A child workspace may declare stricter rules than its parent (e.g., requiring 90% test coverage when enterprise mandates 80%).
* **Loosening Forbidden:** A child workspace can **never** bypass, relax, or disable a parent rule (e.g., an individual developer cannot enable unapproved models, disable secret redaction, or increase cloud spend beyond team allocation).

---

## 3. Federated Sovereign Governance Model

Sovereignty is the exclusive domain of biological agents. Synthetic agents (LLMs, CLIs, swarms) are strictly executors and advisors.

### Scopes of Authority Matrix

| Governance Scope | Sovereign Authority (Biological) | Autonomous Framework (Synthetic) | Escalation Boundary |
| :--- | :--- | :--- | :--- |
| **Enterprise / Org Tier** | **Enterprise Sponsor (CTO / Founder)**<br>Sole authority over global budget, provider whitelists, and corporate policies. | Audits fleet-wide cost burn, security compliance, and vendor drift across all teams. | Unhandled compliance breaches, global budget exhaustion. |
| **Team / Product Tier** | **Team Lead / Product Owner**<br>Sole authority over sprint goal prioritization and domain task allocation. | Proposes task DAGs, tracks PR velocity, detects capability drift across harnesses. | Goal scope creep, inter-team merge conflicts, sprint budget drift. |
| **Workspace Tier** | **Individual Builder (Developer / PM)**<br>Directs the synthetic fleet for their assigned goal/feature. | Implements TDD cycles, runs multi-agent DECIDE debates, executes code. | Architectural dilemmas, schema changes, unexpected test failures. |
| **Synthetic Fleet Tier** | **No Sovereign Authority** | Synthesizes proposals, runs tests, drafts PRs, and signs DECIDE inputs. | **Cannot** merge PRs, expand budgets, or alter policy files without human signature. |

---

## 4. Dual-Plane Organizational Hierarchy

Synlynk resolves the tension between flat agent swarms and enterprise structure by establishing two distinct, cooperating planes:

```
  BIOLOGICAL PLANE                                SYNTHETIC EXECUTION PLANE
  (Human Accountability & Value Intent)           (Role-Bound Verification & Build)
┌───────────────────────────────────┐           ┌───────────────────────────────────┐
│     Enterprise Sponsor / Board    │           │           Synthetic PM            │
│     • Defines company mission     │◄─Briefs───┤  • Synthesizes executive briefs   │
│     • Allocates capital & limits  │           │  • Tracks empirical goal progress │
└─────────────────┬─────────────────┘           └─────────────────┬─────────────────┘
                  │                                               │
                  ▼                                               ▼
┌───────────────────────────────────┐           ┌───────────────────────────────────┐
│        Team / Tech Leads          │           │        Synthetic Architect        │
│     • Owns technical domains      │◄─Designs──┤  • Drafts system blueprints       │
│     • Resolves strategic dilemmas │           │  • Convenes DECIDE consensus panels│
└─────────────────┬─────────────────┘           └─────────────────┬─────────────────┘
                  │                                               │
                  ▼                                               ▼
┌───────────────────────────────────┐           ┌───────────────────────────────────┐
│        Individual Builders        │           │      Synthetic TPM, Dev, QA       │
│     • Biological domain experts   │◄─Skeletons┤  • Atomic task decomposition      │
│     • Directs synthetic pod       │           │  • Test-driven code & PR review   │
└───────────────────────────────────┘           └───────────────────────────────────┘
```

1. **Biological Plane (Why & What):** Humans define intent, budget, trade-offs, and final acceptance.
2. **Synthetic Execution Plane (How & Verification):** Agents operate through strict role charters (PM $\rightarrow$ Architect $\rightarrow$ TPM $\rightarrow$ Dev $\rightarrow$ QA $\rightarrow$ Maintainer) governed by `state.db`.

---

## 5. Append-Only Merkle Decision Ledger (No Web3 / DAO Bloat)

Synlynk rejects public blockchain DAOs (avoiding token speculation, gas fees, latency, and public IP leaks) in favor of a **Git-backed, Cryptographically Signed Merkle Ledger**:

### 1. Cryptographic Signatures (Ed25519 / GPG)
* Every participating harness signs its analysis in a DECIDE panel.
* Every human sovereign signs goal promotions and policy updates using their standard git commit signing key (SSH/GPG).
* Records are stored in `project-docs/decisions/YYYY-MM-DD-<slug>.json` and mirrored in `state.db`.

### 2. Full Provenance & Auditability (SOC2 / ISO27001 Ready)
When an enterprise audit occurs, Synlynk generates an unbreakable provenance receipt:
* **The Directive:** Which human authorized the goal.
* **The Debate:** Exact reasoning, trade-offs, and dissenting views from Claude, Codex, Agy, and Grok.
* **The Code:** Git commit SHAs, author attribution trailers, and reviewer signatures.
* **The Verification:** Passing test execution logs, coverage diffs, and lint proofs.

---

## 6. Implementation Milestones

* **Milestone 1 (Phase 1): Local Signed Policy & Decision Ledger**
  * Local `.synlynk/policy.json` schema validation with sponsor signature check.
  * Formalized DECIDE panel JSON receipts with SHA-256 integrity hashes.
* **Milestone 2 (Phase 2): Federated Enterprise Control Plane**
  * Remote policy sync over HTTPS/NATS relay (`goal-2c19bbad`).
  * Cryptographic team membership verification and secret boundary enforcement (`goal-b1f1a8bf`).
  * Ephemeral cloud runner drivers (AWS Spot / Kubernetes) with strict sandbox containment (`goal-bd5eaa14`).
