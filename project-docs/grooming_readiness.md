# Workspace Owner Grooming Readiness Matrix

**Date:** 2026-11-17  
**Authority:** DECIDE [`dec-4e81b29a`](decisions/2026-11-11-decide-panel-roadmap-prioritization-and-backlog-sweep.md) & Ratified Sequence: **`2 > 3 > 1`**  
**Purpose:** Provides the workspace owner with full provenance visibility and plan-level intervention levers across all 6 pre-generated draft packages before task dispatch.

---

## 1. Executive Readiness Overview

| Horizon | Milestone | Thematic Arc | Governing Strategy / Decision | Spec Status | Plan Status | Grooming Traffic Light |
| :---: | :---: | :--- | :--- | :---: | :---: | :---: |
| **H1** | **`v0.38.1`** | Roadmap Studio v2: Interactive Drag/Drop Controls | [`dec-approve-studio`](decisions/2026-11-15-approve-roadmap-studio-design-pr-5286-do.md) | 🟢 Approved | 🟢 Landed | 🟢 **Ready for Build** |
| **H2** | **`v0.39.0`** | Theme 6: The Cloud Wedge, NATS Relay & Swarms | [`dec-4e81b29a`](decisions/2026-11-11-decide-panel-roadmap-prioritization-and-backlog-sweep.md) | 🟢 Approved | 🟡 Drafting | 🟡 **Needs Plan Review** |
| **H2.1** | **`v0.39.1`** | Theme 6 Fast-Follow: Hetzner Cloud Runner & Vertical Swarm Host | [gh:#5360](https://github.com/nikhilsoman/synlynk/issues/5360) | 🟢 Approved | 🟢 Drafting | 🟢 **Ready for Plan Review** |
| **H3** | **`v0.40.0`** | Track 4: Intent-Based Engineering & IBPD Phase 3 | [`dec-f8835ba3`](decisions/2026-11-14-round-2-evaluation-context-round-1-dec-7.md) | 🟢 Approved | 🟡 Drafting | 🟡 **Needs Plan Review** |
| **H4** | **`v0.41.0`** | Theme 2: Sovereign Silicon & Local Model Parity | [`dec-4e81b29a`](decisions/2026-11-11-decide-panel-roadmap-prioritization-and-backlog-sweep.md) | 🟡 In Strategy | 🔴 Needed | 🟠 **Needs Tech Spec** |
| **H5** | **`v0.42.0`** | Theme 5: Ambient Co-Pilot & DevEx CLI Consolidation | [`dec-4e81b29a`](decisions/2026-11-11-decide-panel-roadmap-prioritization-and-backlog-sweep.md) | 🟡 Partial | 🔴 Needed | 🟠 **Needs Tech Spec** |
| **H6** | **`v0.43.0`** | Theme 7: Synaptic AI Capability Index & Global Oracle | [`dec-4e81b29a`](decisions/2026-11-11-decide-panel-roadmap-prioritization-and-backlog-sweep.md) | 🟢 Approved | 🔴 Needed | 🟡 **Needs Plan Review** |

---

## 2. Detailed Milestone Package Grooming

### Horizon 1: `v0.38.1` — Roadmap Studio v2: Interactive Drag/Drop Controls & Visual Proposal Protocol
* **Active Status:** `open` (Tracking Issue: [gh:#5338](https://github.com/nikhilsoman/synlynk/issues/5338))
* **Governing Goal:** `goal-e3840370` (Vizor Master Control Plane & Interactive HUD)
* **Design Specs:**
  - `docs/superpowers/specs/2026-11-15-roadmap-studio-visual-proposal-ui-design.md`
  - `docs/superpowers/specs/2026-11-16-roadmap-studio-v2-theming-provisional-ux-design.md`
* **Implementation Plans:**
  - `docs/superpowers/plans/2026-11-15-roadmap-studio-visual-proposal.md`
  - `docs/superpowers/plans/2026-11-16-roadmap-studio-v2-theming-provisional-ux.md`
* **Target Code Subsystems:**
  - `synlynk/viz/roadmap_studio.py` (Client-side HTML5 drag/drop events, spatial sorting)
  - `synlynk/viz/server.py` (Route handling for `/approve`, `/hold`, `/revise`, `/drop`, `/reorder`, `/pin`)
  - `synlynk/tpm_sweep.py` (Dynamic git bookends, thematic clustering)
  - `synlynk/viz_serve.py` (Fix non-interactive EOFError)
  - `synlynk/viz/home.py` & `banner.py` (Nav alert badge and deep-linking)
* **Constituent Tasks:**
  1. `story-058d77e0`: Live Spatial Drag/Drop & Card Reordering (`frontend`, `agy`)
  2. `story-8f3a9102`: Route Validation & Write-Path Hardening (`qa`, `claude`)
  3. `story-7d4e5129`: TPM Engine Dynamic Bookends & Thematic Clustering (`dev`, `codex`)
  4. `story-c822fd03`: Vizor Non-Interactive Server Resilience (`backend`, `codex`)
  5. `story-d4b40958`: Status Banner & Proposal Alert Deep-Linking (`frontend`, `agy`)
* **Workspace Owner Intervention Levers:**
  - Drag-over insertion visual indicator styling (accent line vs placeholder box).
  - Optimistic UI timing (immediate card reorder vs server-ack animation).
  - Warning badge threshold for pinned constituents exceeding 5 stories.

---

### Horizon 2: `v0.39.0` — Theme 6: The Cloud Wedge Shell, NATS Relay Mesh & Swarm Execution Runners
* **Active Status:** `held` (Draft package in `approval_tickets`, visible in Roadmap Studio)
* **Governing Goal:** `goal-bfc37035` / `goal-ef42902a`
* **Strategy & Decisions:**
  - Strategy: `synlynk.com` Platform Vision & Cloud Wedge Architecture
  - Decision: `project-docs/decisions/2026-11-11-decide-panel-roadmap-prioritization-and-backlog-sweep.md`
* **Design Specs:**
  - `docs/superpowers/specs/2026-10-12-personal-hosted-relay-design.md` (NATS relay hub)
  - `docs/runbooks/state-db-disaster-recovery.md` (#1686 remote ephemeral host protocol)
* **Target Code Subsystems:**
  - `synlynk/relay_hub.py` (NATS client & leased locks)
  - `.github/workflows/remote-node.yml` (GitHub Actions ephemeral host launcher)
  - `synlynk/swarm.py` (Multi-agent swarm coordination)
* **Constituent Tasks:**
  1. `story-c97f7c16`: Remote node from a GitHub Action (`dev`)
  2. `story-9069164d`: Trigger the remote node from GitHub Actions (`devops`)
  3. `story-18c543ac`: DR restore verification script on remote node (`devops`)
  4. `story-8c6090e0`: Personal-use hosted relay: opt-in NATS hub bridging local relay brokers (`infra`)
  5. `story-2cabd5ae`: synlynk.com platform vision: accounts, entitlements, hosted infra (`architect`)
* **Workspace Owner Intervention Levers:**
  - AWS instance sizing for the ephemeral runner (e.g. `c6i.xlarge` vs Spot `t4g`).
  - GitHub Actions issue trigger label naming (e.g. `run-remote-node` vs `synlynk-remote`).
  - Auth token secret storage and rotation strategy for NATS mesh.

---

### Horizon 2.1: `v0.39.1` — Theme 6 Fast-Follow: Hetzner Cloud Swarm Runner Driver & Vertical Milestone Host Orchestration
* **Active Status:** `planned` (Tracking Issue: [gh:#5360](https://github.com/nikhilsoman/synlynk/issues/5360); Paired Monetization Epic: [gh:#5359](https://github.com/nikhilsoman/synlynk/issues/5359))
* **Governing Goal:** `goal-d5323df6` (Theme 6: Ephemeral Swarm Execution Infrastructure Foundation)
* **Strategy & Decisions:**
  - Strategy: `synlynk.com` Platform Vision & Cloud Wedge Architecture
  - Design Spec: `docs/superpowers/specs/2026-11-18-swarm-execution-infrastructure-and-hetzner-runner-design.md` (Approved, PR #5361)
* **Target Code Subsystems:**
  - `synlynk/runners/hetzner.py` (New: `HetznerRunnerDriver` over stdlib HTTP REST API)
  - `synlynk/runners/manager.py` (Driver registration & lifecycle watchdog supervision)
  - `synlynk/swarm.py` (Vertical Swarm Host dynamic sizing & NATS task queue drainer)
  - `synlynk/cli.py` (`synlynk swarm lease` commands)
* **Constituent Tasks:**
  1. `HetznerRunnerDriver` scaffolding, schema & stdlib HTTP client (`backend`)
  2. Server provisioning, dynamic host sizing (`cpx21`/`cpx31`/`cpx51`), and mock unit tests (`backend`)
  3. Watchdog timers (OS cloud-init, shell trap, client supervisor) and scale-to-zero teardown (`backend`)
  4. Vertical Swarm Host git worktree parallelism and NATS bundle sync (`backend`)
  5. CLI wiring (`synlynk swarm lease`) and FinOps telemetry event emission (`backend`)
  6. Full regression verification suite (`testing`)
* **Workspace Owner Intervention Levers:**
  - Hetzner Cloud location selection (Nuremberg `nbg1` default vs Falkenstein `fsn1` / Hillsboro `hil`).
  - Default server type for unmeasured epics (`cpx31` vs `cpx51`).
  - Cloud-init base distribution (`ubuntu-24.04` vs `debian-12`).

---

### Horizon 3: `v0.40.0` — Track 4: Intent-Based Engineering, Activity Taxonomy & Roadmap Drift Governance (IBPD Phase 3)
* **Active Status:** `held` (Draft package in `approval_tickets`, visible in Roadmap Studio)
* **Governing Goal:** `goal-18372f86` / `goal-8f64eff5`
* **Strategy & Decisions:**
  - Decision: `project-docs/decisions/2026-11-14-round-2-evaluation-context-round-1-dec-7.md` (CTO/Enterprise & IBPD Tier-3 Pivot)
* **Design Specs:**
  - `docs/superpowers/specs/2026-11-13-intent-based-engineering-and-roadmap-drift-governance-design.md`
  - `docs/superpowers/specs/2026-11-13-fully-derived-roadmap-approach-c-design.md`
* **Target Code Subsystems:**
  - `synlynk/intent.py` (New: shared intent capture layer across terminal, Vizor, and comment polling)
  - `synlynk/governs_gate.py` (Hard enforcement of Intent → Goal → PR chain)
  - `synlynk/taxonomy.py` (Consolidated 58-command taxonomy schema)
  - `synlynk/doctor.py` (`synlynk roadmap check` decision↔arc drift gate)
* **Constituent Tasks:**
  1. `story-7fd63985`: IB-PMEO intent decomposition & activity taxonomy framework spec (`architect`)
  2. `story-intent-cap`: `synlynk intent capture` primitive (`dev`)
  3. `story-rd-check`: `synlynk roadmap check` drift gate (`qa`)
  4. `story-04734534`: Dual-tracking drift reconciliation: collapse to `state.db`-only (`pm`)
  5. `story-43346243`: COMMAND_TAXONOMY module & full 58-command classification (`dev`)
* **Workspace Owner Intervention Levers:**
  - Syntax of the capture CLI (e.g. `synlynk intent capture "<text>"` vs `synlynk intent "<text>"`).
  - Strictness of `synlynk roadmap check` (fail-closed CI gate vs advisory sentinel).
  - Scope of command taxonomy collapse (which ~15 commands form the permanent Core).

---

### Horizon 4: `v0.41.0` — Theme 2: Sovereign Silicon, Local oMLX / vLLM Driver Parity & Zero-Cost Routing
* **Active Status:** `held` (Draft package in `approval_tickets`, visible in Roadmap Studio)
* **Governing Goal:** `goal-8d34c416` (Sovereign Silicon Deep Local Model Parity)
* **Strategy & Decisions:**
  - Strategy: `docs/strategy/deepseek-harness-and-over-the-horizon-expansion.md`
  - Decision: `project-docs/decisions/2026-11-11-decide-panel-roadmap-prioritization-and-backlog-sweep.md`
* **Target Code Subsystems:**
  - `synlynk/models.py` (Discovered local model endpoints: Ollama, vLLM, Apple Silicon MLX)
  - `synlynk/greenfield/fleet_probe.py` (Local GPU & RAM hardware profiling)
  - `synlynk/harness/` (Local harness runner adapters)
* **Constituent Tasks:**
  1. `story-d01ffd5a`: Productize local/sovereign path beyond Hermes roster (`dev`)
  2. `story-9a29872b`: Local Harness Operationalization: adapter parity & hot-swappable models (`infra`)
  3. `story-4ba2b5c8`: Graduated local-routing pilot & isolated Aider evaluation boundary (`qa`)
  4. `story-c7064c40`: Synlynk Model Hub: Meta Muse GA & Local oMLX Harness (`dev`)
  5. `story-fea8c2d0`: Local harness automated benchmarking & zero-cost telemetry gates (`devops`)
* **Workspace Owner Intervention Levers:**
  - Local model quantization targets (4-bit vs 8-bit quantized weights).
  - Hardware floor requirements (e.g. Apple Silicon 32GB Unified RAM vs NVIDIA 16GB VRAM).
  - Automatic fallback latency cap (when to fall back to cloud models if local token generation drops below 15 tok/s).

---

### Horizon 5: `v0.42.0` — Theme 5: Ambient Co-Pilot, Fenced Companion v2.1 REPL & DevEx CLI Taxonomy Consolidation
* **Active Status:** `held` (Draft package in `approval_tickets`, visible in Roadmap Studio)
* **Governing Goal:** `goal-85656c82` (Developer Experience & Fenced Companion)
* **Design Specs:**
  - `docs/superpowers/specs/2026-10-31-companion-v2-design.md`
* **Target Code Subsystems:**
  - `synlynk/companion.py` (At-the-fence engine, streaming terminal REPL)
  - `synlynk/taxonomy.py` (Maturity-tiered command taxonomy)
  - `docs/reference/commands.md` (Auto-generated command reference)
* **Constituent Tasks:**
  1. `story-6f97c5a0`: Fenced Companion v2.1: interactive CLI sounding board (`synlynk companion chat` REPL) (`frontend`)
  2. `story-e1eb9005`: Consolidate ~58 commands into maturity-tiered GOVERNS taxonomy (`architect`)
  3. `story-126d706f`: Auto-generate reference documentation from taxonomy (`docs`)
  4. `story-e00c8d29`: Track 2: CLI Surface & Taxonomy consolidation into Core vs Packs split (`dev`)
  5. `story-a4479016`: Review and prune user-visible command complexity (`pm`)
* **Workspace Owner Intervention Levers:**
  - Terminal REPL interactive persona and context window size.
  - Command naming and alias deprecations (e.g. keeping `synlynk status` vs `synlynk watch`).
  - Terminal OSC 8 hyperlink behaviors across macOS Terminal vs iTerm2 vs VS Code.

---

### Horizon 6: `v0.43.0` — Theme 7: Synaptic AI Capability Index, Edge Pre-Flight Routing Oracle & Public Benchmark Crawler
* **Active Status:** `held` (Draft package in `approval_tickets`, visible in Roadmap Studio)
* **Governing Goal:** `goal-aa48c456` (Synaptic AI Capability Index & Global Routing Oracle)
* **Design Specs:**
  - `docs/superpowers/specs/2026-10-19-synaptic-ai-capability-index-gtm-design.md`
  - `docs/superpowers/specs/2026-09-02-subscription-cost-amortization-and-true-up-design.md`
* **Target Code Subsystems:**
  - `synlynk/capability.py` (Empirical capability matrix and rating index)
  - `synlynk/benchmark/` (Benchmark testbed crawler)
  - `synlynk/quota.py` (Dynamic cost multiplier and reservation governor)
* **Constituent Tasks:**
  1. `story-d5323df6`: Autonomous Capability Crawler & Index Distribution (`infra`)
  2. `story-d4887a2b`: Dynamic Model Catalog Window & Open SFIA Taxonomy (`pm`)
  3. `story-9e58e25c`: Edge pre-flight routing oracle (<20ms latency bound) (`dev`)
  4. `story-a0c6843b`: Dispatch always resolves live model catalog with real cost/capability data (`dev`)
  5. `story-fcb2fdeb`: Quota burn-rate weights and dynamic multiplier governor (`dev`)
* **Workspace Owner Intervention Levers:**
  - Public SFIA benchmark attribution policy (>1% threshold).
  - Pre-flight routing cache TTL (how long an edge routing decision is cached before re-evaluating).
  - Maximum monthly token crawler budget.
