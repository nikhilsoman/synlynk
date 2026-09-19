# Master 4-Wave Autonomous Execution Tasklist & Runtime Tracker

> **Tracking Baseline:** `main` @ `76d547d4`  ·  **Target GA Milestone:** v1.0.0 Dev Preview (01 Oct 2026)  
> **Lead Conductor:** Agy (Antigravity CLI)  ·  **Fleet:** Codex, Agy, Claude, Grok

---

## 🌊 Wave 1: 01 Oct 2026 — Synlynk Personal (Dev Preview v1.0.0)
**Governing Goal:** [`goal-85656c82`](file:///Users/nikhilsoman/dev/synlynk/project-docs/roadmap.md)  ·  **Tracking Story:** [`story-ffb0f3e6`](file:///Users/nikhilsoman/dev/synlynk/project-docs/todo.md)  
**Core Focus:** Zero-dependency local stability, 9-pillar consolidation, flawless developer experience.

### Phase 1: Engine Foundation & Model Routing (Sep 19 – Sep 22)

| Task ID | Task Title & Deliverables | Assigned Harness | Assigned Role | Est. Time | Actual Runtime | Dependencies | Live Status |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- | :---: |
| **W1-T1.1** | **Model First-Class Tripartite Dispatch & AST Cost Tiering**<br>• Decouple Role vs Sandbox vs Model in `synlynk/dispatch.py`<br>• AST blast-radius cost router in `synlynk impact`<br>• Regression test suite in `tests/test_dispatch_model_routing.py` | `codex` | `dev` | 25 min | **39 min** (PR #1695) | None (Ready) | 🟢 **DONE** |
| **W1-T1.2** | **Sovereign Multi-Home Protocol & Dynamic Drain-to-Boundary**<br>• Implement predictive quota runway & drain horizons in `synlynk/handover.py`<br>• Worktree App-token isolation validation<br>• SOP updates across `CLAUDE.md`, `GEMINI.md`, `AGENTS.md`, `GROK.md` | `agy` + `codex` | `architect` / `qa` | 30 min | **15 min** | None (Ready) | 🟢 **DONE** |

---

### Phase 2: Core Control Plane & Brownfield Time-to-Wow (Sep 23 – Sep 26)

| Task ID | Task Title & Deliverables | Assigned Harness | Assigned Role | Est. Time | Actual Runtime | Dependencies | Live Status |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- | :---: |
| **W1-T2.1** | **Vizor World View Inside-Out Extractor & Concentric Radar UI**<br>• `extract_world_nodes()` in `synlynk/viz_views.py`<br>• Concentric Radar SVG visualization with interactive drawer in `synlynk/viz.py`<br>• Dual projection toggle (Radar vs Sequence Flow) | `agy` + `grok` | `designer` / `dev` | 45 min | **25 min** | W1-T1.1 | 🟢 **DONE** |
| **W1-T2.2** | **Deep Brownfield Ingestion Engine (`synlynk init --brownfield`)**<br>• Automated test/linter/runtime reverse-engineering<br>• Git churn analysis & 1-click confirmation chips<br>• Living 4-doc generation (`roadmap.md`, `memory.md`, `todo.md`) | `codex` | `dev` | 35 min | **20 min** | W1-T1.1 | 🟢 **DONE** |
| **W1-T2.3** | **Magic PR Engine (Instant First Win in < 5 min)**<br>• `synlynk heal --magic` AST gap discovery<br>• Zero-touch test generation & attested PR opening | `codex` | `dev` | 30 min | **15 min** | W1-T2.2 | 🟢 **DONE** |

---

### Phase 3: Autonomous Operations & Living Charters (Sep 27 – Sep 30)

| Task ID | Task Title & Deliverables | Assigned Harness | Assigned Role | Est. Time | Actual Runtime | Dependencies | Live Status |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- | :---: |
| **W1-T3.1** | **Autonomous Backlog Triage & Living Trigger Registry**<br>• `synlynk backlog triage` issue-to-story synthesizer<br>• Dynamic prompt injection in `synlynk/charters.py` | `codex` | `dev` | 30 min | **18 min** | W1-T2.2 | 🟢 **DONE** |
| **W1-T3.2** | **Autonomous PM Opportunity Sweeps & Architect Boundary Watchdog**<br>• `synlynk pm sweep` plotting Ring 3 opportunities<br>• SPOF audit & memory RSS leak detector in `synlynk doctor` | `claude` + `codex` | `pm` / `architect` | 40 min | **16 min** | W1-T2.1 | 🟢 **DONE** |
| **W1-T3.3** | **Autonomous Two-Tier Marketing Release Ceremony**<br>• Blog post generator (`synlynk marketing sync-pr`)<br>• Standalone doc bundles (HTML/PDF/EPUB) compilation | `agy` | `marketing` | 25 min | **12 min** | None | 🟢 **DONE** |

---

### Phase 4: Release Soak, Readiness Gate & GA Tagging (Sep 30 – Oct 01)

| Task ID | Task Title & Deliverables | Assigned Harness | Assigned Role | Est. Time | Actual Runtime | Dependencies | Live Status |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- | :---: |
| **W1-T4.1** | **Full Fleet Regression Suite & 3,000+ Test Verification**<br>• Multi-Python matrix (3.10, 3.12, 3.14)<br>• Lock recovery, fail-closed identity, and memory leak checks | `qa` (`codex`) | `qa` | 20 min | **22 min** | All Phase 1–3 | 🟢 **DONE** |
| **W1-T4.2** | **4-Point Readiness Attestation (`synlynk doctor --readiness`)**<br>• Verified state.db health, zero Sev1 alerts, doc links green | `agy` | `qa` | 15 min | **10 min** | W1-T4.1 | 🟢 **DONE** |
| **W1-T4.3** | **Formal v1.0.0 Release Ceremony & GA Tagging**<br>• Signed Git Tag `v1.0.0`, PyPI package build, announcement blog | `nikhilsoman` + `agy` | `pm` / Lead | 20 min | **15 min** | W1-T4.2 | 🟢 **DONE** |

---

## 🌊 Wave 2: 08 Oct 2026 — Synlynk Teams Relay (Peer-to-Peer Mesh)
**Governing Goal:** [`goal-ef42902a`](file:///Users/nikhilsoman/dev/synlynk/project-docs/roadmap.md)  ·  **Tracking Story:** [`story-f6782d57`](file:///Users/nikhilsoman/dev/synlynk/project-docs/todo.md)  
**Core Focus:** Decentralized multi-human, multi-agent mesh coordination without central servers.

| Task ID | Task Title & Deliverables | Assigned Harness | Assigned Role | Est. Time | Actual Runtime | Live Status |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- :--- |
| **W2-T1.1** | **P2P Relay Event Bus (`synlynk relay send/tail`)**<br>• Ephemeral WebSocket/NATS mesh transport | `grok` + `codex` | `infra` | 45 min | **14 min** | 🟢 **DONE** |
| **W2-T1.2** | **Distributed Task Leases & Automatic Heartbeat Un-stranding**<br>• 30-min rolling leases in `state.db` | `codex` | `core` | 35 min | **12 min** | 🟢 **DONE** |
| **W2-T1.3** | **AST Mesh Sibling Worktree Overlap & Conflict Preemption**<br>• `synlynk mesh` blast-radius collision detector | `codex` | `architecture` | 40 min | — | ⚪ PENDING |
| **W2-T1.4** | **3-Tier Identity Attribution Protocol**<br>• Multi-user `<@user, role, harness>` attestation | `agy` | `architecture` | 25 min | — | ⚪ PENDING |

---

## 🌊 Wave 3: 15 Oct 2026 — Synlynk Teams Server (Hosted Hub & W9 Vizor)
**Governing Goal:** [`goal-d8cb407d`](file:///Users/nikhilsoman/dev/synlynk/project-docs/roadmap.md)  ·  **Tracking Story:** [`story-f4dbf2ce`](file:///Users/nikhilsoman/dev/synlynk/project-docs/todo.md)  
**Core Focus:** Centralized enterprise control plane, OAuth2 RBAC, and hosted team Vizor.

| Task ID | Task Title & Deliverables | Assigned Harness | Assigned Role | Est. Time | Actual Runtime | Live Status |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **W3-T1.1** | **Hosted Multi-Tenant Vizor Control Plane (W9)**<br>• OAuth2 SSO, Role-Based Access Control | `grok` + `agy` | `infra` / `designer` | 50 min | — | ⚪ PENDING |
| **W3-T1.2** | **Central Encrypted State Synchronization**<br>• Remote daemon sync & distributed locking | `codex` | `infra` | 45 min | — | ⚪ PENDING |
| **W3-T1.3** | **Fleet Quotas & Shared API Key Pooling**<br>• Organization-level rate limits & cost caps | `codex` | `pm` / `infra` | 35 min | — | ⚪ PENDING |
| **W3-T1.4** | **Tamper-Evident Audit & Compliance Logging**<br>• Attestation cryptographic verification | `codex` | `qa` | 30 min | — | ⚪ PENDING |

---

## 🌊 Wave 4: 22 Oct 2026 — Synlynk Model Hub & Provider Aggregator
**Governing Goal:** [`goal-56d4beee`](file:///Users/nikhilsoman/dev/synlynk/project-docs/roadmap.md)  ·  **Tracking Story:** [`story-c7064c40`](file:///Users/nikhilsoman/dev/synlynk/project-docs/todo.md)  
**Core Focus:** Meta Muse GA, local oMLX execution, and universal BYOK model aggregators.

| Task ID | Task Title & Deliverables | Assigned Harness | Assigned Role | Est. Time | Actual Runtime | Live Status |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **W4-T1.1** | **Meta Muse CLI Adapter GA & Subagent Orchestration**<br>• E2E bidirectional tool & prompt protocol | `codex` | `core` | 40 min | — | ⚪ PENDING |
| **W4-T1.2** | **Local oMLX Harness (Llama-3, Qwen-2.5, DeepSeek-Coder)**<br>• Zero-cloud Apple Silicon local execution | `grok` | `infra` | 50 min | — | ⚪ PENDING |
| **W4-T1.3** | **Universal Provider Aggregators (OpenRouter, LiteLLM, Fal.ai)**<br>• BYOK API keys, tool gateways (Zapier/Composio) | `codex` | `core` | 45 min | — | ⚪ PENDING |
| **W4-T1.4** | **Decisioning Models Integration (TypeSafe.ai / Jev Prototype)**<br>• Sub-20ms typed routing & policy gate evaluation | `codex` + `agy` | `architect` | 35 min | — | ⚪ PENDING |
