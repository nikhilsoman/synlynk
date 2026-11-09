# Authoritative Roadmap & Capabilities Strategic Reconciliation

- **Date:** 2026-11-08
- **Milestone Context:** Developer Preview v0.29.0 Post-Release / v0.30.0 Roadmap Realignment
- **Author:** Agy (AntiGravity / Gemini)
- **Status:** Ratified via Decide Panel `dec-71b3e9a5`

---

## 1. Executive Summary & Inventory Accounting

A comprehensive cross-subsystem audit was conducted across the file-based knowledge repository, SQLite state store (`state.db`), and active worktrees. The ledger reflects:

| Subsystem / Artifact | Total Count | Active / Open | Completed / Done | Superseded / Parked |
| :--- | :--- | :--- | :--- | :--- |
| **Stories (`state.db`)** | **2,343** | 861 (`open`) + 33 (`execute`) + 126 (`visualize`) | 1,280 (`sustain`) + 13 (`release`) + 26 (`notify`) | 4 (`goal`) |
| **Goals (`state.db`)** | **71** | 49 (`active`) | 15 (`done`) | 7 (`superseded`) |
| **Design Specs (`docs/superpowers/specs/`)** | **307** | — | — | — |
| **Implementation Plans (`docs/superpowers/plans/`)** | **270** | — | — | — |
| **Decision Records (`project-docs/decisions/`)** | **83** | — | 83 approved | — |
| **Active GitHub Issues** | **#5163 – #5175** | 6 open priority tickets | 6 merged PRs in v0.29.0 | — |

---

## 2. Deep Dive: Accounting for "Misplaced" Strategic Capabilities

Four high-value capability areas were specced and partially prototyped, but became stranded across feature worktrees during the rapid v0.26–v0.29 sprint to ship the Developer Preview:

### 2.1 Local Harness Onboarding (Ollama / MLX / oMLX)
* **Design Specs:**
  - `docs/superpowers/specs/2026-10-16-local-harness-operationalization-design.md`
  - `docs/superpowers/specs/2026-10-20-local-pilot-rebaseline-design.md`
  - `docs/superpowers/specs/2026-10-21-local-pilot-operational-resume-design.md`
* **Implementation Plans:**
  - `docs/superpowers/plans/2026-10-21-local-pilot-operational-resume.md`
* **Current State:**
  - `synlynk status` marks local execution as `local: unavailable`.
  - The driver exists in `scripts/local_pilot_run.py`, but automatic probe and dispatch (`synlynk dispatch local`) fail because the local profile qualification worktree (`feat/qualify-local-harness-profiles`) was never merged into `main`.
* **Action to Unblock:**
  - Rebase and merge `feat/qualify-local-harness-profiles` into `main`.
  - Wire `Ollama` / Apple Silicon `MLX` socket detection into `synlynk probe local`.

### 2.2 Muse Harness Onboarding
* **Design Specs:**
  - `docs/superpowers/specs/2026-10-23-muse-capability-readiness-design.md`
* **Implementation Plans:**
  - `docs/superpowers/plans/2026-10-23-muse-capability-readiness.md`
  - `docs/superpowers/plans/2026-09-11-cluster-d-muse-harness-onboarding.md`
* **Current State:**
  - Detected during `synlynk init`, but reported as `✗ muse — check API key / install`.
  - Target milestone was `v0.27.3` (`Cross-harness onboarding verification including Muse`), which was deferred during the v0.28 truth ledger sprint.
* **Action to Unblock:**
  - Implement the Muse execution adapter in `synlynk/dispatch.py` following the approved spec.
  - Add Muse test fixtures to `tests/test_muse_harness.py`.

### 2.3 OpenRouter BYOK (Bring Your Own Key)
* **Design Specs & Plans:**
  - `docs/superpowers/plans/2026-10-04-openrouter-dispatch.md`
  - Goal: `story-ec2802d6` (`BS-15: Harness independence — home/away paradigm, OpenRouter direct API`)
* **Current State:**
  - OpenRouter is already hooked as a fallback execution engine in `synlynk/openrouter.py`.
  - However, the user-facing BYOK setup wizard is missing from `synlynk configure`.
* **Action to Unblock:**
  - Add `synlynk configure --openrouter-key` and expose OpenRouter model mapping in `.synlynk/config.json`.

### 2.4 Swarms & Cloud Autonomous Execution
* **Design Specs & Plans:**
  - `docs/superpowers/specs/2026-10-18-governs-autonomy-control-plane-design.md`
  - `docs/superpowers/specs/2026-09-02-ephemeral-swarm-cloud-runners-design.md`
  - Goal: `story-d5323df6` (`Autonomous Capability Crawler & AWS Spot Docker Swarm Driver`)
* **Current State:**
  - The local autonomous loop (leased worktrees, circuit breakers, `tpm_sweep.py`, GitHub approvals) is functional.
  - Multi-node cloud swarm execution was parked under post-v0.29 enterprise cloud infrastructure.
* **Action to Unblock:**
  - Re-activate `story-d5323df6` as part of the `synlynk.com` platform infrastructure roadmap.

---

## 3. The Three-Horizon Strategic Roadmap

```mermaid
flowchart TD
    subgraph H1["Horizon 1: Developer Preview Hardening (v0.29.x) — 100% COMPLETE ✅"]
        H1_FTUE["1. FTUE & Sentinel Defect Fixes (#5166-#5170)"]
        H1_Vizor["2. Vizor Kanban Goal Column Refactor (#5175)"]
        H1_VM["3. Clean-Canvas Verification in OrbStack VM"]
    end

    subgraph H2["Horizon 2: Fleet Expansion & Agent Studio (v0.30.0) — ACTIVE 📍"]
        subgraph H2_P1["Tier 1: Core Foundation & Local Silicon"]
            H2_Seams["1. Agent Studio Phase 1: 10-Role Taxonomy, Audit & Seams (goal-658aa384)"]
            H2_Local["2. Local MLX & Ollama Harness Qualification (feat/qualify-local-harness-profiles)"]
        end
        subgraph H2_P2["Tier 2: Studio HUD & Fleet Onboarding"]
            H2_Studio["3. Agent Studio Phases 2-4: Vizor BAU Editor, Lifecycle & FTUE Wizard"]
            H2_Muse["4. Muse Execution Adapter & OpenRouter BYOK Wizard"]
        end
        subgraph H2_P3["Tier 3: Capability Registry & Tool-Use Governance"]
            H2_Registry["5. Agent Studio Phases 5-8: Capability Registry, Trust Gate & TPM Tool Migration"]
        end
    end

    subgraph H3["Horizon 3: Cloud Swarms & Platform Vision (v1.0.0)"]
        H3_Platform["1. synlynk.com Accounts & Dynamic Shell (Spec 2026-10-23)"]
        H3_Telemetry["2. Opt-in Anonymous Telemetry & BigQuery Ingestion"]
        H3_Index["3. Public Synaptic AI Capability Index"]
        H3_Swarm["4. Ephemeral AWS Spot Docker Swarm Runners"]
    end

    H1 --> H2_P1 --> H2_P2 --> H2_P3 --> H3
```

### Horizon 1: Developer Preview Hardening (v0.29.x — 100% Complete ✅)
* **Goal:** Zero friction for any developer from `pipx install synlynk` to their first completed merge.
* **Deliverables:**
  1. Fix `synlynk status` missing database crash ([#5166](https://github.com/nikhilsoman/synlynk/issues/5166) — Merged in PR #5177).
  2. Fix `synlynk migrate` untracked files crash ([#5167](https://github.com/nikhilsoman/synlynk/issues/5167) — Merged in PR #5174).
  3. Fix `.synlynk/instructions.json` timestamp churn ([#5168](https://github.com/nikhilsoman/synlynk/issues/5168) — Merged in PR #5173).
  4. Fix `CONTEXT_BUILD_DEGRADED` invalid SQL query ([#5169](https://github.com/nikhilsoman/synlynk/issues/5169) — Merged in PR #5172).
  5. Fix `VIZOR_DAEMON_CRASHLOOP` launchd environment resolution ([#5170](https://github.com/nikhilsoman/synlynk/issues/5170) — Merged in PR #5182).
  6. Fix Vizor Kanban board Goal column & GitHub linking ([#5175](https://github.com/nikhilsoman/synlynk/issues/5175) — Merged in PR #5184).
  7. End-to-end verification on clean Ubuntu 24.04 VM (`synlynk-preview`).

### Horizon 2: Fleet Expansion & Agent Studio (v0.30.0 — Active Sprint 📍)
* **Goal:** Complete harness parity across cloud providers and zero-cost local silicon, anchored by audited, interactive Agent Role Management ("Agent Studio").
* **Anchor Deliverables & Priority Sequencing:**
  1. **Tier 1 (Core Foundation & Local Silicon — Immediate P0):**
     - **Agent Studio Phase 1 (`goal-658aa384` / gh:#5185):** Activate 10-role taxonomy (`secops`, `infra-devops`, promoted `maintainer`), immutable/append-only charter audit trail with actor attribution, `capability_ratings` task-type seeding, and Horizon 3 forward-compat seams (`workspace_id`, `identity_binding`).
     - **Local MLX / Ollama Driver (`feat/qualify-local-harness-profiles`):** Rebase local pilot worktree and wire zero-cost local silicon execution into `synlynk dispatch local`.
  2. **Tier 2 (Studio HUD & Fleet Onboarding — P1):**
     - **Agent Studio Phases 2–4:** Replace Vizor's dead charter UI with the live BAU charter editor, implement role lifecycle (deprecation/merge + GitHub App identity revocation), and ship the 5-step FTUE onboarding wizard.
     - **Muse & OpenRouter BYOK:** Implement Muse execution adapter in `synlynk/dispatch.py` and deliver `synlynk configure --openrouter-key` setup wizard.
  3. **Tier 3 (Capability Registry & Tool-Use Governance — P2):**
     - **Agent Studio Phases 5–8:** Implement the unified Capability Registry (native code hooks + MCPs + Skills), ship the third-party trust/dedup gate, and migrate `tpm`'s GitHub sync into agent-role tool-use.

### Horizon 3: Cloud Swarms & Platform Vision (v1.0.0 — Platform Milestone)
* **Goal:** Launch `synlynk.com` platform services, hosted relay, and public capability benchmarks.
* **Deliverables:**
  1. Deploy `synlynk.com` dynamic shell, user accounts, and workspace registry per Spec `2026-10-23` (leveraging Horizon 2's `workspace_id` and `identity_binding` seams).
  2. Deploy the Opt-In Anonymous Telemetry pipeline (GA4 + BigQuery).
  3. Publish the live public **Synaptic AI Capability Index**.
  4. Launch ephemeral cloud swarm runners on AWS Spot Docker.
