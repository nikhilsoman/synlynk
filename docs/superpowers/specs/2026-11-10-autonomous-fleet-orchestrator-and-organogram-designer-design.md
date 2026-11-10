# Autonomous Fleet Orchestrator, Archetype Abstraction & Visual Organogram Designer

**Date:** 2026-11-10  
**Status:** Draft — Ready for Decide Panel  
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

```
┌────────────────────────────────────────────────────────────────────────┐
│                      THE 6 UNIVERSAL ARCHETYPES                        │
├─────────────────┬──────────────────┬───────────────────────────────────┤
│ Archetype       │ Primary Function │ Core Lifecycle Contract           │
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
│                 │ Asset Crafting   │ asset builds / coding via TDD     │
├─────────────────┼──────────────────┼───────────────────────────────────┤
│ 5. inspector    │ Verification &   │ Conducts non-author review → runs │
│                 │ Quality Assurance│ regression audits → gates merges  │
├─────────────────┼──────────────────┼───────────────────────────────────┤
│ 6. custodian    │ Substrate Health │ Prunes worktrees/scratch → policy │
│                 │ & Infrastructure │ sync → manages release artifacts  │
└─────────────────┴──────────────────┴───────────────────────────────────┘
```

### 1:N Archetype-to-Agent Cardinality

A workspace is **never constrained to one agent per archetype**. A single archetype can be instantiated across multiple specialized agents operating in distinct disciplines:

```
Archetype: creator (Implementation & Asset Crafting)
 ├── Agent: @editor          (SFIA: MUDI - Video editing & timeline assembly)
 ├── Agent: @animator        (SFIA: ANIM - 3D skeletal rigging & keyframes)
 └── Agent: @sound-designer  (SFIA: SNDD - DSP scripting, Foley audio mixing)

Archetype: orchestrator (Coordination & Wave Assembly)
 ├── Agent: @prod-coordinator(SFIA: PRMG - Production schedule & call sheets)
 └── Agent: @post-supervisor (SFIA: PRMG - VFX vendor waves & render queue)
```

---

## 3. 3D Taxonomy & Deterministic Resource Inference

Every agent instance is formally indexed by the tuple:
$$\text{Agent} = (\text{Archetype}, \text{SFIA Discipline}, \text{Industry Domain})$$

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

### Deterministic Tool & Resource Inference Engine

During onboarding (FTUE) or agent creation (BAU), Synlynk inspects `(Archetype, SFIA)` to deterministically recommend:

1. **Tool & MCP Bindings:**
   - `creator + SNDD`: Recommends `ffmpeg`, `sox`, and `audiosuite-mcp`.
   - `creator + ANIM`: Recommends `blender-mcp`, `usd-toolset`, and GPU render hooks.
   - `creator + PROG`: Recommends language runtimes, package managers, and AST indexers.
   - `orchestrator + PRMG`: Recommends issue trackers, calendar/schedule drivers, and wave calculators.
2. **Filesystem Path Scoping:**
   - Path patterns automatically default to the agent's discipline (e.g. `@sound-designer` is granted write access to `assets/audio/**` and `scenes/soundtrack/**`, read-only to `scenes/video/**`).
3. **Verification Contracts:**
   - `inspector + TEST`: Requires zero-exit code test passes.
   - `inspector + MUDI`: Requires codec compliance, resolution checks, and 0 dropped frames.

---

## 4. The Autonomy Evolutionary Ladder (L1 → L2 → L3)

Autonomy is not a static binary flag. It is an earned state governed by an **Autonomy Maturity Model**:

```
 Level 1: Advisory (Mode 3)       Level 2: Gated (Mode 1)        Level 3: Autonomous (Mode 2)
─────────────────────────────    ─────────────────────────────   ────────────────────────────
• Read-only observation          • Autonomous intake & triage    • Autonomous wave dispatch
• Ingests issues / signals       • Assembles wave proposals      • Autonomous task execution
• Generates status rollups       • Requires Human/Conductor      • Hard safety gates only
• Suggests dispatch proposals      approval to dispatch            (architect, budget, 2x fail)
```

### The RSI (Recursive Self-Improvement) Scoring Engine

In accordance with Harness² (arXiv:2610.14224), each agent maintains an empirical track record stored in `state.db`:

$$\text{RSI Score} = w_1 \cdot A_{\text{proposal}} + w_2 \cdot (1 - R_{\text{rework}}) + w_3 \cdot V_{\text{verification}} - w_4 \cdot \Delta_{\text{cost}}$$

Where:
- $A_{\text{proposal}}$ = Proposal acceptance rate ($\ge 90\%$ required for promotion).
- $R_{\text{rework}}$ = Percentage of dispatched tasks requiring manual rollback or immediate re-work ($\le 5\%$).
- $V_{\text{verification}}$ = First-pass QA verification rate ($\ge 95\%$).
- $\Delta_{\text{cost}}$ = Budget variance (|actual - estimated| / estimated).

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

## 8. Phased Implementation Plan

- **Phase 1: Database Migration & Archetype Core (`synlynk/archetypes.py`)**
  - Implement `agent_archetypes`, `agent_workflow_edges`, and `rsi_evaluations` tables.
  - Extend `synlynk/charter_schema.py` to validate `archetype_id`, `sfia_disciplines`, and `autonomy_level`.
- **Phase 2: Deterministic Taxonomy & Resource Inference (`synlynk/taxonomy_inference.py`)**
  - Connect SFIA 8/9 taxonomy dictionary to recommended MCP tools, permissions, and file patterns.
  - Implement CLI helper `synlynk agent recommend-tools --sfia <CODE>`.
- **Phase 3: RSI Scoring & Autonomy Ladder Engine (`synlynk/rsi.py`)**
  - Track cycle proposals, rework events, and verification outcomes.
  - Implement circuit-breaker demotion hook in `synlynk/sentinel.py`.
- **Phase 4: Vizor Organogram Designer Canvas (`synlynk/viz/organogram.py`)**
  - Implement visual node-graph canvas using offline SVGs/HTML5 canvas with interactive drag-and-drop.
  - Provide domain templates: Full-Stack SaaS, Film Studio (Hitchcock), Video Production (Vdowrx).
  - Add Inspection Drawer with live charter editing, tool attachment, and RSI status.
- **Phase 5: TPM Orchestrator Evolution & End-to-End Verification**
  - Wire `synlynk/tpm_sweep.py` into the L1/L2/L3 autonomy engine.
  - Comprehensive unit and integration test suite across all 6 archetypes.

---

## 9. Verification & Safety Contracts

1. **Non-Regressive Software Baseline:** Existing 10 software agent roles remain 100% operational as default seeds under their corresponding archetypes.
2. **Offline-First Guarantee:** The Organogram Designer in Vizor operates completely host-local with zero cloud CDN dependencies.
3. **Safety Invariant:** An agent can never self-promote to Level 2 or Level 3. Promotions require cryptographic/explicit human authorization. Circuit-breaker demotions are unilateral and deterministic.
