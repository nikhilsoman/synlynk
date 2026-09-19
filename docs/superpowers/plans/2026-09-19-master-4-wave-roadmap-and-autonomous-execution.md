# Master Implementation Plan: 4-Wave Release Schedule & Autonomous Fleet Execution

- **Tracking Stories:**
  - Wave 1 (01 Oct 2026): [`story-ffb0f3e6`](file:///Users/nikhilsoman/dev/synlynk/project-docs/todo.md) (`[Wave 1 - 01 Oct] Synlynk Personal Dev Preview v1.0.0 (Local-Only, 9-Pillar Stabilization)`) linked to `goal-85656c82`
  - Wave 2 (08 Oct 2026): [`story-f6782d57`](file:///Users/nikhilsoman/dev/synlynk/project-docs/todo.md) (`[Wave 2 - 08 Oct] Synlynk Teams Relay (Peer-to-Peer Mesh, Distributed Leases & Conflict Preemption)`) linked to `goal-ef42902a`
  - Wave 3 (15 Oct 2026): [`story-f4dbf2ce`](file:///Users/nikhilsoman/dev/synlynk/project-docs/todo.md) (`[Wave 3 - 15 Oct] Synlynk Teams Server (Hosted Collaboration Hub, Multi-Tenant RBAC & W9 Hosted Vizor)`) linked to `goal-d8cb407d`
  - Wave 4 (22 Oct 2026): [`story-c7064c40`](file:///Users/nikhilsoman/dev/synlynk/project-docs/todo.md) (`[Wave 4 - 22 Oct] Synlynk Model Hub (Meta Muse GA, Local oMLX Harness & Universal Provider Aggregators)`) linked to `goal-56d4beee`
- **Author / Lead Conductor:** Agy (Antigravity CLI) [@agy]
- **Approver:** Nikhil Soman [@nikhilsoman]
- **Date:** 2026-09-19
- **Status:** Approved / Ready for Autonomous Execution

---

## 1. Master Release Horizon & Milestone Schedule

```
========================================================================================
WAVE 1: 01 OCT 2026 — SYNLYNK PERSONAL (DEV PREVIEW v1.0.0)
Focus: Zero-Dependency, Local-Only Stability, Flawless Developer Experience (9 Pillars)
Tracking Story: story-ffb0f3e6  ·  Governing Goal: goal-85656c82
========================================================================================
- [P1] First-Class Model Selection & Graphify AST blast-radius cost routing.
- [P2] Rich Local Vizor & World View (localhost:8585): Product, Logical, Infra, and World views.
- [P3] Deep Brownfield Onboarding (`synlynk init --brownfield`) & 4-point readiness.
- [P4] Magic PR Engine: Instant first win in < 5 minutes.
- [P5] Sovereign Multi-Home Co-Conductor Parity, Dynamic Handover (Drain-to-Boundary) & App-Token Isolation.
- [P6] Autonomous Agent Work Discovery & Backlog Triage (`synlynk backlog triage`).
- [P7] Autonomous PM Ecosystem Sweeps & Tier 2 Opportunity Radar (`synlynk pm sweep`).
- [P8] Autonomous Architect Footprint Watchdog & External Boundary Resilience Audit.
- [P9] Autonomous Marketing Two-Tier Blog & Doc Bundle Publishing (HTML/PDF/EPUB).
- [State] Single canonical SQLite state resolver with fail-closed lock recovery.

========================================================================================
WAVE 2: 08 OCT 2026 — SYNLYNK TEAMS RELAY (PEER-TO-PEER MESH)
Focus: Distributed Workgroup Coordination Without Centralized Infrastructure
Tracking Story: story-f6782d57  ·  Governing Goal: goal-ef42902a
========================================================================================
- [P2P Relay] Ephemeral peer-to-peer event bus over WebSocket/NATS (`synlynk relay send/tail`).
- [Distributed Leases] Rolling 30-minute task leases with heartbeat un-stranding in state.db.
- [AST Mesh Conflict Preemption] Graphify sibling worktree overlap detector (`synlynk mesh`).
- [Fractal 3-Tier Identity] Full attribution for <@user, role, harness> across peer commits & PRs.
- [Shared Telemetry Rollup] Cross-workgroup cost and token burn visualization.

========================================================================================
WAVE 3: 15 OCT 2026 — SYNLYNK TEAMS SERVER (HOSTED COLLABORATION HUB)
Focus: Centralized Multi-Tenant Workspace Infrastructure & W9 Hosted Vizor
Tracking Story: story-f4dbf2ce  ·  Governing Goal: goal-d8cb407d
========================================================================================
- [Hosted Vizor] Multi-user control plane with OAuth2 role-based access control (W9).
- [Central State Sync] Encrypted state synchronization and remote daemon arbitration.
- [Fleet Quotas] Centralized billing, shared API key pooling, and enterprise rate-limiting.
- [Audit & Compliance] Tamper-evident attestation logs for all autonomous PR reviews and merges.

========================================================================================
WAVE 4: 22 OCT 2026 — SYNLYNK MODEL HUB & PROVIDER AGGREGATOR
Focus: Universal Model Accessibility & Local Weight Execution
Tracking Story: story-c7064c40  ·  Governing Goal: goal-56d4beee
========================================================================================
- [Meta Muse CLI] Full GA integration with verified subagent tool orchestration.
- [Local oMLX Harness] Zero-cloud local model inference (Llama-3, Qwen-2.5, DeepSeek-Coder).
- [Universal Aggregator] API-key BYO provider adapters (OpenRouter, LiteLLM, Ollama, vLLM).
- [Empirical Spike Harness] Reusable multi-model benchmark suite (`synlynk spike eval`).
========================================================================================
```

---

## 2. Wave 1 (01 Oct 2026): 11-Day Autonomous Execution Plan

### Sprint Phase 1 (Sep 19 – Sep 22): Engine Foundation & Model Routing
- **Task 1.1 (Pillar 1 - Model First-Class Dispatch):**
  - Implement tripartite routing in `synlynk/dispatch.py` separating Workspace Agent Role, Harness Sandbox, and Model Selection.
  - Wire Graphify AST impact score (`synlynk impact`) into complexity-aware model tiering:
    - Tier 1 (Leaf edits): Flash / Haiku / GPT-4o-mini
    - Tier 2 (Multi-file refactors): Sonnet / GPT-4o / Gemini 1.5 Pro
    - Tier 3 (Specs / Reasoning): o1 / o3-mini / Claude 3.5 Sonnet / Gemini Pro
  - Assigned: `codex` (`--task-type cli-plumbing`)
- **Task 1.2 (Pillar 5 - Sovereign Multi-Home & Drain-to-Boundary):**
  - Codify Sovereign Multi-Home protocol across `CLAUDE.md`, `GEMINI.md`, `AGENTS.md`, `GROK.md`.
  - Implement `synlynk/handover.py` calculating predictive quota runway and safe task drain horizons upon home switch.
  - Verify worktree App-token isolation tests pass without host keyring fallback.
  - Assigned: `agy` (`--task-type templates`) + `codex` (`--task-type tests`)

### Sprint Phase 2 (Sep 23 – Sep 26): Core Control Plane & Brownfield Wow
- **Task 2.1 (Pillar 2 - Vizor World View Extractor & Concentric Radar UI):**
  - Implement `extract_world_nodes()` in `synlynk/viz_views.py` detecting outbound APIs (Stripe, OpenAI, Twilio, S3), inbound webhooks, IdPs, and compliance gates.
  - Implement `generate_world_html()` in `synlynk/viz.py` rendering the Concentric Radar SVG visualization with interactive node drawer.
  - Assigned: `agy` (`--task-type content`) + `grok` (`--task-type canvas`)
- **Task 2.2 (Pillar 3 - Deep Brownfield Ingestion Engine):**
  - Implement `synlynk init --brownfield` reverse-engineering test commands, package managers, linters, and git churn.
  - Auto-synthesize living `project-docs/roadmap.md`, `memory.md`, and `todo.md`.
  - Assigned: `codex` (`--task-type cli-plumbing`)
- **Task 2.3 (Pillar 4 - Magic PR Engine):**
  - Build 5-minute first-win scan in `synlynk heal --magic` discovering circular imports, stale doc links, and missing unit tests.
  - Auto-generate test-attested PR with AST blast-radius graph.
  - Assigned: `codex` (`--task-type cli-plumbing`)

### Sprint Phase 3 (Sep 27 – Sep 30): Autonomous Operations & Charters
- **Task 3.1 (Pillar 6 - Autonomous Backlog Triage & Living Triggers):**
  - Implement `synlynk backlog triage` converting raw GitHub issues into linked stories in `state.db`.
  - Wire automated QA claiming upon new PR creation.
  - Assigned: `codex` (`--task-type cli-plumbing`)
- **Task 3.2 (Pillars 7 & 8 - Autonomous PM Sweeps & Architect Watchdog):**
  - Implement `synlynk pm sweep` plotting opportunity nodes on Ring 3 of the World View radar.
  - Implement Architect watchdog in `synlynk doctor` checking memory RSS, stale worktrees, and outbound dependency SPOFs.
  - Assigned: `claude` (`--task-type pm`) + `codex` (`--task-type refactor`)
- **Task 3.3 (Pillar 9 - Marketing Release Engine):**
  - Automate two-tier blog sync (`synlynk marketing sync-pr <pr>`) and standalone doc bundle compilation (HTML/PDF/EPUB).
  - Assigned: `agy` (`--task-type content`)

### Sprint Phase 4 (Sep 30 – Oct 01): Release Freeze & GA Tagging
- **Task 4.1:** Full regression suite execution across Python 3.10 and 3.12 (target: 3,000+ tests green).
- **Task 4.2:** 4-point readiness attestation in `synlynk doctor --readiness`.
- **Task 4.3:** Release ceremony, PyPI build tag, and public announcement.

---

## 3. Autonomous Fleet Allocation Matrix

| Task Area | Primary Harness | Assigned Role | Isolation / Permission |
| :--- | :--- | :--- | :--- |
| **CLI plumbing, State DB, Tests** | `codex` | `dev` / `qa` | `workspace-write`, `-C <worktree>` |
| **Vizor HTML/SVG UI, Templates, Docs** | `agy` | `designer` / `marketing` | `workspace-write`, `--mode plan/act` |
| **PM Sweeps, Architecture RFCs, Specs** | `claude` | `pm` / `architect` | `workspace-write`, `--role pm` |
| **Interactive JS Canvas, Benchmarks** | `grok` | `dev` | `workspace-write`, `--always-approve` |
| **PR Verification & Merge Gates** | `codex` / `qa` | `qa` | `workspace-write`, `--requires-gh-write` |

---

## 4. Verification & Quality Gates

Every dispatched task must satisfy the **Strict 5-Point Quality Gate** before merge:
1. **TDD Coverage:** Reproduction/unit test written and passing.
2. **Impact Attestation:** `synlynk pr check --impact-attested` clean.
3. **Identity Attestation:** 3-tier attribution trailer (`Co-Authored-By`) and role App token present.
4. **Non-Authoring Review:** Reviewed and approved by an independent QA agent or peer.
5. **Worktree Hygiene:** Branch deleted and worktree pruned cleanly after merge.
