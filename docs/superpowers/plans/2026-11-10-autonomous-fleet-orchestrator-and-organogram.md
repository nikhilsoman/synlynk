# Autonomous Fleet Orchestrator, Archetype Abstraction & Visual Organogram Designer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Implement the Phase 1–2 Horizon 3 platform foundation: 6 universal archetypes, secondary hats, in-repo domain packs, 3-tier autonomy ladder with Sentinel-owned circuit breakers, TPM L1/L2/L3 autopilot, and Vizor Organogram view.

**Architecture:** Decouple agent roles from software titles into 6 capability-neutral archetypes stored in SQLite (`state.db`). Layer domain-specific lifecycle steps and suggested tool baselines via versioned in-repo domain packs. Implement an earned autonomy state machine (L1 Advisory $\to$ L2 Gated $\to$ L3 Autonomous) where promotions require human confirmation and demotions are executed automatically by the Sentinel monitor. Project organograms and workflow edges into an offline-first Vizor HTML/SVG canvas.

**Tech Stack:** Python 3.12+, SQLite 3 (WAL mode), pytest, Vanilla HTML5/CSS/SVG (Vizor offline-first canvas).

**Spec:** `docs/superpowers/specs/2026-11-10-autonomous-fleet-orchestrator-and-organogram-designer-design.md` (ratified in `dec-4a53a2ee`).

## Global Constraints

- Archetype definitions must remain strictly capability-neutral; software mechanics (TDD, merges) must not be hardcoded in the archetype enum.
- No taxonomy lookup (SFIA/APQC/NAICS) may automatically grant write-capable tools or filesystem access without explicit human confirmation.
- The RSI reliability ledger and circuit-breaker demotion tripwires must be written by a non-self-interested runtime (`sentinel` / `inspector`), never agent self-report.
- L3 (Autonomous Execution) is restricted exclusively to the `@tpm` reference orchestrator at initial release.
- Per-domain autonomy ceilings are mandatory configuration (`Rxcc` hard-capped at $\le L2$).
- Zero regression across the existing 10 software agent roles.
- Vizor organogram canvas must operate 100% offline-first with zero external CDN dependencies.

---

### Task 1: Database Migration & Archetype Core Substrate

**Files:**
- Create: `synlynk/archetypes.py`
- Modify: `synlynk/db.py:2200-2400`
- Test: `tests/test_archetypes.py`

**Interfaces:**
- Consumes: `synlynk.db._get_db()`
- Produces: `ensure_archetype_schema(conn)`, `list_archetypes(conn)`, `get_archetype(conn, archetype_id)`

- [x] **Step 1: Write failing tests for archetype schema and initial records**
Create `tests/test_archetypes.py` verifying:
1. `agent_archetypes`, `agent_workflow_edges`, and `rsi_evaluations` tables are created with proper schemas.
2. The 6 capability-neutral archetypes (`orchestrator`, `strategist`, `director`, `creator`, `inspector`, `custodian`) are seeded.
3. `workspace_agents` table has `archetype_id`, `secondary_hat`, `sfia_disciplines`, `autonomy_level`, and `domain_autonomy_caps` columns.

- [x] **Step 2: Run test to confirm failure**
Run `pytest tests/test_archetypes.py` and confirm `ModuleNotFoundError: No module named 'synlynk.archetypes'`.

- [x] **Step 3: Implement `synlynk/archetypes.py` and wire into `synlynk/db.py`**
Implement:
- `ARCHETYPE_DEFINITIONS`: Dictionary containing the 6 universal capability-neutral archetypes.
- `ensure_archetype_schema(conn)`: Executes table creation DDL and seeds archetypes.
- Column additions to `workspace_agents` in `synlynk/db.py` migration handler.

- [x] **Step 4: Run tests and ensure pass**
Run `pytest tests/test_archetypes.py -v` and verify all tests pass.

- [x] **Step 5: Commit changes**
`git add synlynk/archetypes.py synlynk/db.py tests/test_archetypes.py && git commit -m "feat(archetypes): implement core archetype schema and database migrations"`

---

### Task 2: Charter Schema Extension & In-Repo Domain Packs

**Files:**
- Create: `synlynk/domain_packs.py`
- Create: `synlynk/domain_packs/software.json`
- Create: `synlynk/domain_packs/hitchcock.json`
- Create: `synlynk/domain_packs/rxcc.json`
- Modify: `synlynk/charter_schema.py:10-90`
- Test: `tests/test_domain_packs.py`
- Test: `tests/test_charter_schema_archetypes.py`

**Interfaces:**
- Consumes: `synlynk.archetypes.ARCHETYPE_DEFINITIONS`
- Produces: `load_domain_pack(domain_id)`, `validate_charter_with_archetype(charter_dict)`, `get_suggested_tool_baseline(domain_id, archetype_id, sfia_codes)`

- [x] **Step 1: Write failing tests for domain packs and charter validation**
Create `tests/test_domain_packs.py` asserting:
1. `software.json`, `hitchcock.json`, and `rxcc.json` load with valid structure (domain metadata, lifecycle stages, suggested tool baselines).
2. `get_suggested_tool_baseline` returns suggestions marked strictly `requires_confirmation=True`.
3. `synlynk/charter_schema.py` validates `primary_archetype`, optional `secondary_hat`, and enforces `domain_autonomy_caps`.

- [x] **Step 2: Run tests to confirm failure**
Run `pytest tests/test_domain_packs.py tests/test_charter_schema_archetypes.py`.

- [x] **Step 3: Implement domain packs and charter schema updates**
1. Create `synlynk/domain_packs/{software,hitchcock,rxcc}.json` with domain-specific lifecycle definitions and suggested tools.
2. Implement `synlynk/domain_packs.py` with loader and suggestion resolver.
3. Update `synlynk/charter_schema.py` to validate archetypes, secondary hats, and domain caps.

- [x] **Step 4: Run tests and confirm passing**
Run `pytest tests/test_domain_packs.py tests/test_charter_schema_archetypes.py -v`.

- [x] **Step 5: Commit changes**
`git add synlynk/domain_packs* synlynk/charter_schema.py tests/test_domain_packs.py tests/test_charter_schema_archetypes.py && git commit -m "feat(domain_packs): add versioned domain packs and archetype charter validation"`

---

### Task 3: Autonomy Evolutionary Ladder & Sentinel-Owned Circuit Breakers

**Files:**
- Create: `synlynk/autonomy.py`
- Modify: `synlynk/sentinel.py:150-250`
- Modify: `synlynk/cli.py`
- Test: `tests/test_autonomy_ladder.py`

**Interfaces:**
- Consumes: `synlynk.db._get_db()`, `synlynk.sentinel`
- Produces: `get_agent_autonomy_level(agent_id)`, `promote_agent_autonomy(agent_id, target_level, authorized_by)`, `demote_agent_autonomy(agent_id, reason, tripped_by)`

- [x] **Step 1: Write failing tests for Autonomy Ladder and circuit breakers**
Create `tests/test_autonomy_ladder.py` asserting:
1. Default autonomy level is `L1_ADVISORY`.
2. Agent self-promotion is rejected; promotion requires explicit `authorized_by="human"`.
3. High-risk domain (`rxcc`) cannot be promoted past `L2_GATED`.
4. Only `@tpm` is eligible for `L3_AUTONOMOUS` in `v0.31.0`.
5. Sentinel tripwire (`TOKEN_CIRCUIT_BREAKER_TRIPPED` or 2x QA verification failure) immediately demotes agent from L3 to L2 and records event in `rsi_evaluations`.

- [x] **Step 2: Run tests to confirm failure**
Run `pytest tests/test_autonomy_ladder.py`.

- [x] **Step 3: Implement `synlynk/autonomy.py` and Sentinel integration**
Implement:
1. `AutonomyLevel` enum: `L1_ADVISORY`, `L2_GATED`, `L3_AUTONOMOUS`.
2. `promote_agent_autonomy` with cryptographic/human-signed validation.
3. `demote_agent_autonomy` triggered by Sentinel patterns.
4. Hook in `synlynk/sentinel.py` calling demotion when circuit breakers trip.
5. CLI subcommand: `synlynk autonomy {status,promote,demote}`.

- [x] **Step 4: Run tests and verify pass**
Run `pytest tests/test_autonomy_ladder.py -v`.

- [x] **Step 5: Commit changes**
`git add synlynk/autonomy.py synlynk/sentinel.py synlynk/cli.py tests/test_autonomy_ladder.py && git commit -m "feat(autonomy): implement 3-tier autonomy ladder and sentinel circuit breakers"`

---

### Task 4: TPM Orchestrator Autonomous Wake Cycle

**Files:**
- Modify: `synlynk/tpm_sweep.py:110-157`
- Modify: `synlynk/tpm.py`
- Test: `tests/test_tpm_autonomy.py`

**Interfaces:**
- Consumes: `synlynk.autonomy.get_agent_autonomy_level("tpm")`
- Produces: `run_tpm_wake_cycle(dry_run=False)` honoring L1, L2, and L3 autonomy levels

- [x] **Step 1: Write failing tests for TPM autonomy levels**
Create `tests/test_tpm_autonomy.py` asserting:
1. In `L1_ADVISORY`: TPM ingests raw issues, clusters them, outputs status proposal, but executes zero dispatch and creates zero PR branches.
2. In `L2_GATED`: TPM ingests issues, drafts reproduction specs, marks tasks ready, but requires human approval before invoking `dispatch_agent`.
3. In `L3_AUTONOMOUS`: TPM autonomously dispatches ready waves for routine tier-1/tier-2 tasks, halting only on hard gates (missing goal, tier-3 ambiguity).

- [x] **Step 2: Run tests to confirm failure**
Run `pytest tests/test_tpm_autonomy.py`.

- [x] **Step 3: Update `synlynk/tpm_sweep.py`**
Inspect TPM's configured autonomy level from `synlynk/autonomy.py`:
- In L1: Skip `run_sweep_pass()` and emit structured JSON proposal summary.
- In L2: Generate approval tickets before dispatching.
- In L3: Autonomously dispatch ready stories.

- [x] **Step 4: Run tests and verify pass**
Run `pytest tests/test_tpm_autonomy.py -v`.

- [x] **Step 5: Commit changes**
`git add synlynk/tpm_sweep.py tests/test_tpm_autonomy.py && git commit -m "feat(tpm): wire TPM wake cycle into 3-tier autonomy engine"`

---

### Task 5: Vizor Organogram & Workflow Inspector View

**Files:**
- Create: `synlynk/viz/organogram.py`
- Modify: `synlynk/viz/server.py:80-150`
- Modify: `synlynk/viz/nav.py`
- Test: `tests/test_viz_organogram.py`

**Interfaces:**
- Consumes: `synlynk.archetypes.list_archetypes()`, `synlynk.db._get_db()`
- Produces: `generate_organogram_html(data, port)`, routes `/w/<slug>/organogram` and `/w/<slug>/api/organogram`

- [x] **Step 1: Write failing tests for Organogram view rendering and API**
Create `tests/test_viz_organogram.py` asserting:
1. `/w/<slug>/organogram` returns valid offline HTML5/SVG without external CDN scripts.
2. Renders nodes with Archetype badges, SFIA tags, and Autonomy levels.
3. Renders workflow edges (`delegation`, `review_gate`).
4. `/w/<slug>/api/organogram` returns JSON graph topology.

- [x] **Step 2: Run tests to confirm failure**
Run `pytest tests/test_viz_organogram.py`.

- [x] **Step 3: Implement `synlynk/viz/organogram.py` and register routes in `server.py`**
1. Implement offline SVG-based tree/graph layout in `synlynk/viz/organogram.py`.
2. Add inspection drawer with live charter viewing, suggested tool confirmation checkboxes, and autonomy level indicator.
3. Register route `/organogram` in `synlynk/viz/server.py` and add to `synlynk/viz/nav.py`.

- [x] **Step 4: Run tests and verify pass**
Run `pytest tests/test_viz_organogram.py -v`.

- [x] **Step 5: Commit changes**
`git add synlynk/viz/organogram.py synlynk/viz/server.py synlynk/viz/nav.py tests/test_viz_organogram.py && git commit -m "feat(vizor): add offline-first organogram and workflow inspector"`

---

### Task 6: End-to-End Testbed Verification & Non-Regression Gate

**Files:**
- Create: `tests/test_fleet_orchestrator_e2e.py`
- Modify: `.github/workflows/test.yml`

**Interfaces:**
- Validates the entire pipeline from Archetype schema $\to$ Domain pack $\to$ Autonomy ladder $\to$ TPM execution $\to$ Vizor projection.

- [x] **Step 1: Write End-to-End integration test suite**
Create `tests/test_fleet_orchestrator_e2e.py` validating:
1. Non-regression: All 10 existing software roles (`pm`, `architect`, `tpm`, `dev`, `designer`, `qa`, `marketing`, `maintainer`, `secops`, `infra-devops`) initialize and validate properly.
2. Domain pack loading for non-software domains (`hitchcock`, `rxcc`).
3. Autonomous demotion drill: Simulating a token runaway event triggers Sentinel and successfully demotes TPM from L3 to L2.
4. Human authorization barrier: Unverified promotion attempts fail closed.

- [x] **Step 2: Run the full test suite**
Run `pytest tests/test_archetypes.py tests/test_domain_packs.py tests/test_autonomy_ladder.py tests/test_tpm_autonomy.py tests/test_viz_organogram.py tests/test_fleet_orchestrator_e2e.py -v`.

- [x] **Step 3: Run existing regression tests**
Run `pytest tests/test_charter_schema.py tests/test_support_engineer.py tests/test_tpm_sweep.py -v` to confirm zero regression on existing fleet operations.

- [x] **Step 4: Commit changes**
`git add tests/test_fleet_orchestrator_e2e.py && git commit -m "test(fleet): add end-to-end integration test suite and non-regression verification"`
