# Autonomous Fleet Orchestrator, Archetype Abstraction & Visual Organogram Designer

**Date:** 2026-11-10  
**Status:** Approved (Ratified via Decide Panel dec-4a53a2ee with 3 Binding Amendments)  
**Authors:** Agy (Gemini) with Nikhil Soman  
**Target Release:** `v0.31.0` (Horizon 3 Platform Foundation)  
**Parent Goals:** `goal-f424fc4c` (TPM / Orchestrator Agent), `goal-06758149` (Full Workspace Agent Fleet), `goal-658aa384` (Agent Studio Phase 2)

---

## 1. Executive Summary & Strategic Intent

Synlynk's Horizon 2 established an operational 10-role taxonomy for software engineering, append-only charter auditing, and an offline-first Agent Studio (`v0.30.0`). However, two architectural limitations constrain Synlynk from realizing its Horizon 3 platform vision:

1. **Static, Domain-Locked Role Model:** Agent roles are currently hardcoded around software engineering titles (`tpm`, `dev`, `qa`, `pm`). When Synlynk operates in creative media (`Hitchcock` film production), video workflows (`Vdowrx`), or clinical biopharma (`Rxcc`), these software-specific concepts leak and break down.
2. **Binary Autonomy & Lack of RSI Gating:** Agents are either purely manual or blindly autonomous. There is no graduated progression that allows an agent to earn autonomy through measured reliability, nor is there a circuit breaker to demote an erratic agent.
3. **Flat List vs. Organogram Architecture:** Workspace roles are represented as isolated cards rather than an organizational graph reflecting delegation lines, reporting relationships, and quality inspection checkpoints.

This specification unifies these capabilities into an architectural leap:
- **Decoupled Archetype Engine:** 6 universal organizational archetypes (`orchestrator`, `strategist`, `director`, `creator`, `inspector`, `custodian`) with **1:N cardinality**, allowing a workspace to field multiple specialized agents per archetype.
- **3D Taxonomic Grounding (SFIA 8/9 + APQC + NAICS):** Standardizing competencies across industries, enabling deterministic inference of tools, MCP servers, permissions, and file scopes.
- **RSI-Gated Autonomy Ladder (L1 → L2 → L3):** Grounded in Google Research's Harness² (*Propose → Probe → Compose*), tracking empirical telemetry to gate progression from Advisory to Autonomous execution.
- **Vizor Visual Organogram Designer:** An interactive node-graph canvas where conductors design reporting structures, assign archetypes, attach tools, and compile visual workflows directly into executable charters.

---

## 2. The 6 Core Universal Archetypes

An **Archetype** is an invariant behavioral primitive defining the execution lifecycle, input contracts, and output obligations of an agent, completely agnostic of industry or job title.

> **Binding Amendment 1 (dec-4a53a2ee):** Archetype definitions are strictly capability-neutral. Concrete execution steps, conventions (e.g. TDD, AST analysis, video codec checks), and artifacts load from versioned **Domain Profile Packs**, not from the archetype core enum.

```
┌────────────────────────────────────────────────────────────────────────┐
│                      THE 6 UNIVERSAL ARCHETYPES                        │
├─────────────────┬──────────────────┬───────────────────────────────────┤
│ Archetype       │ Primary Function │ Capability-Neutral Contract       │
├─────────────────┼──────────────────┼───────────────────────────────────┤
│ 1. orchestrator │ Coordination &   │ Ingests raw inputs → clusters     │
│                 │ Wave Assembly    │ into tasks → builds dependency    │
│                 │                  │ graph → dispatches waves → tracks │
├─────────────────┼──────────────────┼───────────────────────────────────┤
│ 2. strategist   │ Vision & Scope   │ Sets strategic intent → aligns    │
│                 │ Prioritization   │ roadmap → gates scope changes     │
├─────────────────┼──────────────────┼───────────────────────────────────┤
│ 3. director     │ Technical/System │ Authors design specs → structural │
│                 │ Architecture     │ contracts → gates plan execution  │
├─────────────────┼──────────────────┼───────────────────────────────────┤
│ 4. creator      │ Implementation & │ Receives task briefs → executes   │
│                 │ Asset Crafting   │ asset builds / implementation     │
├─────────────────┼──────────────────┼───────────────────────────────────┤
│ 5. inspector    │ Verification &   │ Conducts independent review → runs│
│                 │ Quality Assurance│ verification audits → gates advance│
├─────────────────┼──────────────────┼───────────────────────────────────┤
│ 6. custodian    │ Substrate Health │ Workspace hygiene, state integrity,│
│                 │ & Infrastructure │ maintenance, and delivery sync    │
└─────────────────┴──────────────────┴───────────────────────────────────┘
```

### 1:N Archetype-to-Agent Cardinality & Secondary Hats

1. **1:N Cardinality:** A workspace is **never constrained to one agent per archetype**. A single archetype can be instantiated across multiple specialized agents operating in distinct disciplines:
```
Archetype: creator (Implementation & Asset Crafting)
 ├── Agent: @editor          (Discipline: Video editing & timeline assembly)
 ├── Agent: @animator        (Discipline: 3D skeletal rigging & keyframes)
 └── Agent: @sound-designer  (Discipline: DSP scripting, Foley audio mixing)

Archetype: orchestrator (Coordination & Wave Assembly)
 ├── Agent: @prod-coordinator(Discipline: Production schedule & call sheets)
 └── Agent: @post-supervisor (Discipline: VFX vendor waves & render queue)
```

2. **Secondary Archetype Hats:** In small workspaces or lean teams, an agent carries a primary archetype and an optional **`secondary_hat`** (e.g., a technical founder carrying `primary_archetype="director"` with `secondary_hat="strategist"`).

---

## 3. 3D Taxonomy & Suggested Resource Baselines

Every agent instance is formally indexed by the tuple:
$$\text{Agent} = (\text{Archetype}, \text{SFIA Discipline}, \text{Industry Domain})$$

> **Binding Amendment 2 (dec-4a53a2ee):** The taxonomy layer is reclassified from "deterministic inference" to **"suggested baseline, human-confirmed grant."** Taxonomy codes (SFIA 8/9, APQC, NAICS) provide standardized vocabulary, onboarding suggestions, and prompt templates. **Under no circumstances does taxonomy lookup automatically grant write-capable tools or filesystem access.** All write authorities and path scopes require explicit human confirmation.

### Domain Profiles & Crosswalk

| Industry / Workspace | Agent Role Title | Base Archetype | Primary SFIA Code | Secondary SFIA Codes |
| :--- | :--- | :--- | :--- | :--- |
| **Software / SaaS** (`synlynk`) | `@tpm` | `orchestrator` | `PGMT` (Programme Mgmt) | `PRMG` |
| | `@architect` | `director` | `REQM` (Requirements) | `ARCH` |
| | `@dev` | `creator` | `PROG` (Software Dev) | `DBDS`, `VISU` |
| | `@qa` | `inspector` | `TEST` (Testing) | `BURM` |
| | `@maintainer`| `custodian` | `ITOP` (IT Ops) | `NTAS` |
| **Film & Creative** (`Hitchcock`) | `@prod-coordinator` | `orchestrator` | `PRMG` (Project Mgmt) | `MUDI` |
| | `@showrunner` | `strategist` | `PROD` (Product/Content) | `BUSA` |
| | `@cinematographer` | `director` | `VISU` (Visual Design) | `GRAP` |
| | `@animator` | `creator` | `ANIM` (Animation) | `ICDV` |
| | `@editor` | `creator` | `MUDI` (Multimedia) | `COMM` |
| | `@sound-designer` | `creator` | `SNDD` (Sound Design) | `MUDI` |
| | `@continuity-supervisor` | `inspector` | `TEST` (Verification) | `REQM` |
| **Video Production** (`Vdowrx`) | `@post-supervisor` | `orchestrator` | `PRMG` (Project Mgmt) | `MUDI` |
| | `@colorist` | `creator` | `VISU` (Visual Styling) | `MUDI` |
| | `@audio-engineer` | `creator` | `SNDD` (Audio Engineering)| `MUDI` |
| **Biopharma / Healthcare** (`Rxcc`)| `@trial-coordinator`| `orchestrator` | `PRMG` (Project Mgmt) | `BURM` |
| | `@protocol-lead` | `director` | `REQM` (Regulatory Specs)| `BURM` |
| | `@biostatistician`| `creator` | `DATM` (Data Science) | `PROG` |
| | `@compliance-auditor` | `inspector` | `BURM` (Compliance/Audit)| `TEST` |

### Suggested Baselines & Human-Confirmed Scoping Engine

During onboarding (FTUE) or agent creation (BAU), Synlynk inspects `(Archetype, SFIA, Domain Pack)` to **suggest**:

1. **Suggested Tools & MCP Servers (Draft Baseline):**
   - `creator + SNDD`: Recommends `ffmpeg`, `sox`, and `audiosuite-mcp`.
   - `creator + ANIM`: Recommends `blender-mcp`, `usd-toolset`, and GPU render hooks.
   - `creator + PROG`: Recommends language runtimes, package managers, and AST indexers.
   - `orchestrator + PRMG`: Recommends issue trackers, schedule drivers, and wave calculators.
2. **Suggested Path Scoping:**
   - Visual suggestions are pre-filled in Vizor (e.g. `@sound-designer` suggested paths: `assets/audio/**`, `scenes/soundtrack/**`).
   - Conductor explicitly checks/approves write permissions before grants are committed.
3. **Domain Verification Assertions:**
   - Software: Exit code 0 test passes and lint checks.
   - Multimedia/Film: Codec compliance, resolution checks, and 0 dropped frames.
   - Biopharma: Protocol compliance checklist and regulatory signature verification.

---

## 4. The Autonomy Evolutionary Ladder (L1 → L2 → L3)

Autonomy is an earned operational state governed by an **Autonomy Maturity Model**:

```
 Level 1: Advisory (Mode 3)       Level 2: Gated (Mode 1)        Level 3: Autonomous (Mode 2)
─────────────────────────────    ─────────────────────────────   ────────────────────────────
• Read-only observation          • Autonomous intake & triage    • Autonomous wave dispatch
• Ingests issues / signals       • Assembles wave proposals      • Autonomous task execution
• Generates status rollups       • Requires Human/Conductor      • Hard safety gates only
• Suggests dispatch proposals      approval to dispatch            (architect, budget, 2x fail)
```

> **Binding Amendment 3 (dec-4a53a2ee):**
> 1. **Non-Self-Interested Ledger:** The RSI reliability ledger and demotion tripwires are recorded strictly by a non-self-interested runtime (`sentinel` / `inspector`), **never by agent self-report**.
> 2. **L3 Launch Boundary:** At initial launch (`v0.31.0`), **Level 3 (Autonomous Execution) eligibility is restricted exclusively to the `@tpm` reference orchestrator**. All other agents remain at L1 or L2.
> 3. **Mandatory Domain Autonomy Caps:** High-risk domains carry permanent configuration ceilings (e.g., `Rxcc` clinical trials are hard-capped at $\le L2$ regardless of numerical RSI score).

### The RSI (Recursive Self-Improvement) Reliability Engine

In accordance with Harness² (arXiv:2610.14224), each agent's track record is tracked in `state.db` by the Sentinel/Inspector monitor:

$$\text{RSI Score} = w_1 \cdot A_{\text{proposal}} + w_2 \cdot (1 - R_{\text{rework}}) + w_3 \cdot V_{\text{verification}} - w_4 \cdot \Delta_{\text{cost}}$$

Standard Calibrated Weights (Phase 1 Baseline):
- $w_1 = 0.30$ (Proposal acceptance rate)
- $w_2 = 0.35$ (Low rework rate, where $R_{\text{rework}} \le 15\%$ for L2, $\le 8\%$ for L3)
- $w_3 = 0.25$ (First-pass verification rate $\ge 95\%$)
- $w_4 = 0.10$ (Budget cost stability)

### Promotion & Demotion Invariants
1. **Promotions are strictly user-authorized:** No agent can ever self-promote. The Sentinel surfaces promotion eligibility when empirical gates are cleared, but promotion requires cryptographic human confirmation.
2. **Demotions are automatic & immediate:** Sentinel automatically trips and demotes an L3 agent to L2 upon:
   - `TOKEN_CIRCUIT_BREAKER_TRIPPED`
   - 2x consecutive failed QA verification cycles on the same wave
   - Unhandled blast-radius or worktree corruption
   Demotions immediately halt autonomous execution and notify the human conductor.

### Gated Promotion & Circuit-Breaker Demotion
1. **Promotions are strictly user-authorized:** When an agent's RSI score crosses the readiness threshold (e.g., $N \ge 20$ successful cycles with $\ge 90\%$ score), Vizor displays an **"Eligible for Autonomy Promotion"** indicator. The conductor explicitly confirms promotion.
2. **Demotions are automatic (Circuit Breakers):** If an agent operating at Level 3 triggers:
   - `TOKEN_CIRCUIT_BREAKER_TRIPPED` (runaway token burn)
   - 2x consecutive failed QA verification cycles on the same wave
   - Unhandled merge conflict or worktree corruption
   The runtime immediately **demotes the agent to Level 2 (Gated)**, halts autonomous execution, and notifies the human conductor.

---

## 5. Vizor Visual Organogram & Workflow Designer

Under `STATUS > Organogram` (and embedded in `Agent Studio`), Vizor provides an interactive, offline-first node-graph canvas:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ VIZOR / AGENT STUDIO: WORKFLOW & ORGANOGRAM DESIGNER                                   │
├────────────────────────────────────────────────────────────────────────────────────────┤
│  [+ Add Agent]  [Templates: Film Production ▼]  [Auto-Layout]  [Save & Apply Charters] │
│                                                                                        │
│        ┌────────────────────────┐                                                      │
│        │ @showrunner            │ (strategist · PROD)                                  │
│        │ Autonomy: L3           │                                                      │
│        └───────────┬────────────┘                                                      │
│                    │ (approves premise & milestones)                                   │
│                    ▼                                                                   │
│        ┌────────────────────────┐         ┌────────────────────────┐                   │
│        │ @prod-coordinator      │◄───────►│ @continuity-supervisor │ (inspector · TEST)│
│        │ (orchestrator · PRMG)  │         │ (verifies quality)     │                   │
│        │ Autonomy: L2 (Gated)   │         └───────────▲────────────┘                   │
│        └───────────┬────────────┘                     │                                │
│                    │ (dispatches work waves)          │ (reviews draft cut)            │
│            ┌───────┴───────┬──────────────┐           │                                │
│            ▼               ▼              ▼           │                                │
│      ┌───────────┐   ┌───────────┐  ┌───────────┐     │                                │
│      │ @animator │   │  @editor  ├──┴───────────┴─────┘                                │
│      │ (ANIM)    │   │  (MUDI)   │  │ @sound-des│ (SNDD)                               │
│      └───────────┘   └───────────┘  └───────────┘                                      │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ Selected Node: @editor                                                                 │
│ • Archetype: creator   • SFIA: MUDI (Multimedia Design)   • Autonomy Level: L2 (Gated) │
│ • Suggested Tools: [x] ffmpeg-cli  [x] davinci-mcp  [ ] blender-mcp                    │
│ • Scoped Paths: /footage/**, /timeline/**, /cuts/**                                    │
│ • RSI Readiness Score: 88% (4/5 stars) → Next Level unlock in 6 tasks                  │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### Canvas Capabilities
1. **Interactive Graph Topology:**
   - **Nodes:** Display Name (`@editor`), Archetype Badge (`creator`), SFIA tag (`MUDI`), Autonomy Level (`L2`), Durability.
   - **Edges (Workflow Connections):**
     - `delegation`: Upstream orchestrator dispatches tasks to downstream creators.
     - `review_gate`: Output must be inspected by an inspector before stage advance.
     - `escalation`: Ambiguities route upstream to strategist or director.
2. **Inspection & Attachment Drawer:**
   - Select any node to view/edit mandate, attach inferred MCP tools/code blocks, customize scoped paths, and review RSI telemetry.
3. **FTUE vs. BAU Workflows:**
   - **FTUE:** Selecting an industry template (e.g., *Film Studio*, *Full-Stack SaaS*, *Data Pipeline*) generates a pre-wired organogram with standard archetypes and SFIA disciplines.
   - **BAU:** Conductors add new agents on the fly, drag connection lines, and adjust autonomy levels as the team scales.
4. **Graph Compiler:**
   - Compiles the visual canvas directly into `state.db` records (`workspace_agents`, `charters`, `agent_edges`), serializing `.agents/<name>.json` configs and updating dispatch policies.

---

## 6. Database Schema & Data Models

### Migrations to `state.db`

```sql
-- Core Archetypes (immutable reference table)
CREATE TABLE IF NOT EXISTS agent_archetypes (
    archetype_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    lifecycle_contract TEXT NOT NULL,
    description TEXT NOT NULL
);

INSERT OR IGNORE INTO agent_archetypes VALUES
('orchestrator', 'Orchestrator', 'intake_cluster_plan_dispatch_track', 'Coordinates workflow waves and dependencies'),
('strategist',   'Strategist',   'vision_align_prioritize_gate',       'Maintains roadmap, intent, and scope gates'),
('director',     'Director',     'architect_specify_contract_gate',    'Defines technical specs and execution contracts'),
('creator',      'Creator',      'brief_build_tdd_verify',             'Hands-on asset creation and implementation'),
('inspector',    'Inspector',    'review_regression_gate_merge',       'Quality assurance, compliance, and non-author review'),
('custodian',    'Custodian',    'prune_sync_maintain_release',        'Substrate health, workspace hygiene, and release packaging');

-- Update workspace_agents to bind Archetype, SFIA, and Autonomy
ALTER TABLE workspace_agents ADD COLUMN archetype_id TEXT REFERENCES agent_archetypes(archetype_id);
ALTER TABLE workspace_agents ADD COLUMN sfia_disciplines TEXT; -- JSON array of SFIA codes (e.g. ["MUDI", "ANIM"])
ALTER TABLE workspace_agents ADD COLUMN industry_domain TEXT;   -- NAICS/APQC code
ALTER TABLE workspace_agents ADD COLUMN autonomy_level TEXT DEFAULT 'L1_ADVISORY'; -- L1_ADVISORY, L2_GATED, L3_AUTONOMOUS
ALTER TABLE workspace_agents ADD COLUMN rsi_readiness_score REAL DEFAULT 0.0;

-- Workflow Edges in the Organogram
CREATE TABLE IF NOT EXISTS agent_workflow_edges (
    edge_id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    source_agent_id TEXT NOT NULL REFERENCES workspace_agents(agent_id),
    target_agent_id TEXT NOT NULL REFERENCES workspace_agents(agent_id),
    edge_type TEXT NOT NULL CHECK(edge_type IN ('delegation', 'review_gate', 'escalation')),
    properties_json TEXT,
    created_at TEXT NOT NULL
);

-- RSI Telemetry Ledger
CREATE TABLE IF NOT EXISTS rsi_evaluations (
    eval_id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL REFERENCES workspace_agents(agent_id),
    cycle_timestamp TEXT NOT NULL,
    proposals_count INTEGER DEFAULT 0,
    proposals_accepted INTEGER DEFAULT 0,
    rework_count INTEGER DEFAULT 0,
    verification_passes INTEGER DEFAULT 0,
    estimated_cost REAL DEFAULT 0.0,
    actual_cost REAL DEFAULT 0.0,
    calculated_score REAL NOT NULL,
    circuit_breaker_tripped INTEGER DEFAULT 0,
    notes TEXT
);
```

---

## 7. Execution Architecture: The TPM Agent as Reference Orchestrator

The software engineering `@tpm` agent serves as the canonical reference implementation of the `orchestrator` archetype:

```
                  ┌────────────────────────────────────────┐
                  │          TPM WAKE CYCLE (Cron)         │
                  └──────────────────┬─────────────────────┘
                                     │
                 ┌───────────────────┴───────────────────┐
                 ▼                                       ▼
     [Level 1: Advisory Mode]                [Level 2/3: Gated/Autonomous]
     • Scans raw GitHub issues               • Scans raw GitHub issues
     • Deduplicates & clusters               • Deduplicates & clusters
     • Maps to open goals/milestones         • Maps to open goals/milestones
     • Emits Proposal Rollup to Vizor        • Drafts reproduction specs & plans
     • Zero dispatch / zero writes           • Ambiguity Gating:
                                               - Missing Goal → Escalate to @architect
                                               - Tier-3 Complexity → Escalate to @pm
                                             • Wave Assembly & Dispatch:
                                               - L2: Awaits human click in Vizor Board
                                               - L3: Autonomously dispatches wave
```

---

## 8. Phased Implementation Sequence

Per Decide Panel ratification (`dec-4a53a2ee`), implementation is partitioned into clear delivery horizons:

### Immediate Milestone (`v0.31.0` — Core Substrate & TPM Autopilot)
- **Phase 1: Archetype Schema, Secondary Hats & Domain Packs (`synlynk/archetypes.py`, `synlynk/domain_packs.py`)**
  - Implement `agent_archetypes`, `agent_workflow_edges`, and `rsi_evaluations` tables in `state.db`.
  - Add `primary_archetype`, `secondary_hat`, `autonomy_level`, and `domain_autonomy_caps` to `synlynk/charter_schema.py`.
  - Ship in-repo versioned domain packs (`synlynk/domain_packs/software.json`, `hitchcock.json`, `rxcc.json`) defining domain lifecycle steps and suggested tool baselines.
- **Phase 2: Autonomy Ladder Core, Sentinel Demotion & TPM Integration (`synlynk/autonomy.py`, `synlynk/tpm_sweep.py`)**
  - Wire L1/L2/L3 state transitions with human confirmation gates.
  - Implement Sentinel-driven automatic demotion circuit breakers in `synlynk/sentinel.py`.
  - Restrict L3 eligibility strictly to `@tpm` orchestrator.
- **Phase 3: Vizor Organogram & Workflow Inspector (`synlynk/viz/organogram.py`)**
  - Offline-first HTML/SVG node-tree & inspection drawer in Vizor.
  - Interactive reporting edge and review-gate visualization with human confirmation diff for write grants.

### Future Milestones (Gated on Empirical Evidence)
- **Phase 4: Multi-Domain Cross-Role Autonomy Promotion (Gated)**
- **Phase 5: Cross-Workspace Federation & Cloud Swarm Runners (Horizon 3+)**

---

## 9. Empirical Usage Gates & Safety Invariants

| Evolution Milestone | Scope | Empirical Usage Gate to Unlock |
| :--- | :--- | :--- |
| **v0.31.0 Substrate** | Archetype schema, TPM L1/L2/L3, Vizor organogram view | Zero regression across 10 software agent roles; 100% testbed pass. |
| **Phase 4: Cross-Domain Autonomy** | Multi-agent L2/L3 promotion across non-software workspaces (Hitchcock, Rxcc) | • $\ge 20$ successful TPM cycles<br>• Zero self-promotion incidents<br>• Human override rate $\le 25\%$<br>• Passed automated demotion drill |
| **Horizon 3+: Federation & Cloud Swarms** | Cross-workspace state federation, multi-tenant charts, AWS Spot runners | • $\ge 2$ independent non-software workspaces<br>• $\ge 30$ stratified L2 cycles per workspace<br>• Human override rate $< 10\%$<br>• Zero unconfirmed write-path escapes |

### Safety Invariants
1. **No Self-Promotion:** An agent can never self-promote. All L1 $\to$ L2 and L2 $\to$ L3 promotions require cryptographic human confirmation.
2. **Sentinel-Owned Demotion:** Automatic demotions are executed unilaterally by the `sentinel` / `inspector` monitor, never by agent self-report.
3. **No Unconfirmed Write Grants:** Taxonomy codes and domain packs provide suggestions only. All write-capable tools and filesystem paths require explicit human confirmation.
4. **Mandatory Domain Ceilings:** Domains with safety/regulatory sensitivity (`Rxcc`) are hard-capped at $\le L2$.
5. **Offline-First Guarantee:** All Vizor organogram projections and SVG rendering run 100% host-local without internet or CDN dependencies.
