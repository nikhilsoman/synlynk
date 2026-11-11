---
decision_id: dec-4e81b29a
topic: "Authoritative Master Roadmap Thematic Prioritization (4 -> 1 -> 3 -> 6 -> 2 -> 5 -> 7), Comprehensive Spec/Plan/Backlog Sweep, and Stale/Superseded Asset Retirement"
date: 2026-11-11
panel: [claude, agy, codex, grok]
status: approved
primary_goal: goal-2458-master-roadmap
governing_loop: goal-eacab0dc
target_milestone: v0.32.2
prior_decisions:
  - dec-9b41a7c3
  - dec-f34a2f5f
  - dec-7a2b0e91
---

# DECIDE Panel dec-4e81b29a: Authoritative Roadmap Thematic Re-Prioritization & Comprehensive Asset Sweep

## Executive Summary

On 2026-11-11, the multi-harness consensus panel (**Claude**, **Agy**, **Codex**, **Grok**) convened to evaluate Nikhil Soman's proposed re-prioritization of the Synlynk Master Roadmap:

$$\mathbf{Theme\ 4 \longrightarrow Theme\ 1 \longrightarrow Theme\ 3 \longrightarrow Theme\ 6 \longrightarrow Theme\ 2 \longrightarrow Theme\ 5 \longrightarrow Theme\ 7}$$

### Core Strategic Thesis
Activating **Theme 4 (TPM Autonomous Operations & Human-in-the-Loop Cadence)** first establishes the autonomous self-driving engine. Once TPM runs on an advisory loop packaging releases and processing `/approve` comments via GitHub issues, the operator (Nikhil) is freed from manual turn-by-turn task dispatching and can focus entirely on high-leverage architectural brainstorms for roadmap gaps.

The panel unanimously **approves the proposed order with two strategic synchronization notes**, completes an exhaustive sweep of all existing specifications, plans, and backlog items, and ratifies the formal retirement of obsolete and superseded assets.

---

## 1. Thematic Alignment & Code Proximity Matrix

The table below maps the 7 strategic themes against existing code maturity, active specifications, and open backlog stories:

| Theme | Focus & Scope | Existing Code Proximity | Governing Specs & Plans | Active Story IDs / GH Issues |
| :--- | :--- | :--- | :--- | :--- |
| **Theme 4: TPM Autonomous Operations & Human-in-the-Loop** | Autonomous TPM sweep daemon, release proposal generator, GitHub comment parsing (`/approve`), Asimov invariants. | **85% Mature.** `synlynk/tpm_sweep.py`, `synlynk/daemon.py`, PR #5207 shipped. | `docs/strategy/road-to-autonomous-ops.md`, `dec-9b41a7c3` | `story-issue-1793`, `story-adb0f757`, `story-issue-2412` |
| **Theme 1: Zero-Drift Governance & Document Mesh** | Sub-3k context packager, DocGraph sidecar indexer, fail-closed spec linter (`synlynk spec lint`), dual-lock document guard. | **80% Mature.** `synlynk/pack.py`, `synlynk/docgraph.py`, PR #5201, PR #5205 shipped. | `docs/superpowers/specs/2026-11-10-sub-3k-context-packager-design.md`, `dec-9b41a7c3` | `story-issue-1786` (#4372), `story-issue-1615` (#4338) |
| **Theme 3: FinOps, Burn-Rate & Multi-Agent Telemetry** | Dual-ledger telemetry (estimated vs. actual), dynamic burn-rate multipliers, quota reservations, Bookkeeper role. | **70% Mature.** `synlynk/cost.py`, `synlynk/fencing.py`, `synlynk/quota.py` exist. | `docs/superpowers/specs/2026-09-02-subscription-cost-amortization-and-true-up-design.md` | `story-1a8afcc1`, `story-ded28a2b`, `story-ae1b3cda` (#3916), `story-3271d873` |
| **Theme 6: The Cloud Wedge & Swarm Infrastructure** | `synlynk.com` Phase 0-4 (S3/CloudFront shell, Aurora v2 accounts, NATS relay hub, AWS Spot swarm runners). | **40% Mature.** Static website in `website/`, relay hub in `synlynk/relay_hub.py`, Pulumi IaC scaffolds. | `docs/superpowers/specs/2026-10-12-personal-hosted-relay-design.md`, `synlynk.com` 5-Phase Cloud Spec | `story-issue-1900`, `story-issue-2176`, `story-issue-1726` |
| **Theme 2: Sovereign Silicon & Local Model Parity** | Local AI drivers (vLLM, Ollama, DGX Spark, Apple Silicon MLX), zero-cost classification, multi-GPU routing. | **65% Mature.** Gateway discovery in `synlynk/greenfield/fleet_probe.py`, `synlynk/models.py`. | `dec-9b41a7c3`, `docs/strategy/deepseek-harness-and-over-the-horizon-expansion.md` | `story-dee3f03a`, `story-5e2d2db2`, `story-7e19365d` |
| **Theme 5: Ambient Co-Pilot, Fenced Companion & DevEx** | Fenced Companion v2.1, interactive CLI sounding board (`synlynk companion chat`), Vizor companion drawer, Discord/Slack bridge. | **60% Mature.** At-the-fence engine in `synlynk/companion.py` (v0.29.0), 4-part anatomy, OSC 8 links. | `docs/superpowers/specs/2026-10-31-companion-v2-design.md`, `goal-85656c82` | `story-6f97c5a0` (#3009), `story-bs12-bridge` |
| **Theme 7: Synaptic AI Capability Index & Global Oracle** | Edge pre-flight routing oracle (<20ms), autonomous capability crawler, public SFIA benchmark portal. | **35% Mature.** Capability matrix in `synlynk/capability.py`, benchmark harness in `synlynk/benchmark/`. | `docs/superpowers/specs/2026-10-19-synaptic-ai-capability-index-gtm-design.md` | `story-9e58e25c`, `story-d4887a2b`, `story-d5323df6` |

---

## 2. Multi-Harness Panel Analysis & Recommendations

### Claude (Architect / Systems Strategist)
* **Position:** **Strongly Approve `4 -> 1 -> 3 -> 6 -> 2 -> 5 -> 7`.**
* **Rationale:** The biggest operational bottleneck in Synlynk to date has been human turn-taking friction: waiting for the operator to review PRs, update roadmaps, and dispatch individual tasks. Theme 4 eliminates this friction. By establishing the TPM `L1_ADVISORY` autonomous loop first, the engine proposes releases, Nikhil reviews and approves via GitHub comments, and dispatches proceed automatically.
* **Synchronization Precaution:** Theme 4 cannot operate cleanly in a vacuum without Theme 1 (Zero-Drift Knowledge Mesh). Fortunately, the core of Theme 1 (Sub-3k Packager and DocGraph) was already merged in `v0.32.0` and `v0.32.1`. Moving Theme 1 immediately after Theme 4 completes the closed-loop governance cycle: TPM dispatches tasks using sub-3k context packs and verifies specs via `synlynk spec lint`.

### Agy (Frontend / QA & Autonomy Engine)
* **Position:** **Strongly Approve.**
* **Rationale:** From the human experience standpoint, separating concerns between **Roadmap Authoring (Human / Brainstorming)** and **Roadmap Execution (TPM / Autonomous Fleet)** is the exact definition of Paradigm 2a transition. 
* **Key Tactical Recommendation:** For Theme 5 (Fenced Companion), we should extract a lightweight **Interactive Sounding Board CLI (`synlynk companion chat`)** early. Because `synlynk/companion.py` already has stage/segment inference and domain vocabulary, adding a streaming terminal REPL provides Nikhil with an ambient co-pilot during brainstorms while TPM executes the background roadmap.

### Codex (CLI Plumbing & Core Engine Subsystems)
* **Position:** **Strongly Approve.**
* **Rationale:** Code proximity dictates this exact order. Theme 4 (`tpm_sweep.py`) is already 85% complete after PR #5207. Theme 1 (`docgraph.py`, `pack.py`) is 80% complete. Theme 3 (`cost.py`, burn rate) is 70% complete with migrations already drafted in `story-1a8afcc1`. Executing `4 -> 1 -> 3` establishes an unshakeable local core before jumping into Cloud Wedge infrastructure (Theme 6).
* **Backlog Audit:** The `state.db` backlog has accumulated dozens of legacy stories from August and September that have either been completely solved by modern modules or superseded by architectural shifts. Codex strongly advocates for a clean purge of these dead backlog items during the Theme 4 sweep.

### Grok (Infra, Canvas & Network / Relay)
* **Position:** **Approve with Sovereign Silicon Note.**
* **Rationale:** Placing Theme 6 (Cloud Wedge) ahead of Theme 2 (Sovereign Silicon) is commercially astute because it establishes the public face of Synlynk (`synlynk.com`), user accounts, and remote relay infrastructure. 
* **Tactical Warning:** Ensure that Sovereign Silicon (Theme 2) does not fall too far behind. Because local models (Ollama, vLLM, Apple Silicon) incur zero API costs, qualifying local models for routine TPM advisory sweeps and doc indexing significantly reduces the token bill during autonomous operations.

---

## 3. Comprehensive Asset Sweep: Superseded & Stale Items

The panel conducted an exhaustive audit of all specs in `docs/superpowers/specs/`, strategy documents in `docs/strategy/`, and backlog stories in `state.db`. The following items are declared **Superseded or Stale** and are formally retired:

### Category A: Superseded Specifications
1. **`docs/superpowers/specs/2026-07-20-state-engine-tiered-design.md`:**
   - *Status:* **SUPERSEDED.** Replaced by SQLite WAL primary architecture (`state.db`) and single-writer leased locks (`synlynk/wal_ledger.py`).
2. **`docs/superpowers/specs/2026-06-27-bs8-harness-capability-awareness-loop-dispatch-design.md`:**
   - *Status:* **SUPERSEDED.** Replaced by empirical capability routing (`synlynk/capability.py`) and dispatch gate (`synlynk/dispatch.py`).
3. **`docs/superpowers/specs/2026-06-21-synlynk-roadmap-realignment-design.md`:**
   - *Status:* **OBSOLETE.** Reflects pre-v0.10.0 June 2026 baseline. Superseded by `dec-9b41a7c3`.
4. **`docs/superpowers/specs/2026-08-31-agy-stitch-mcp-integration-design.md`:**
   - *Status:* **SUPERSEDED.** Absorbed directly into the modern MCP server bridge (`synlynk/relay_hub.py`).
5. **`docs/superpowers/specs/2026-09-04-distributed-sync-research.md`:**
   - *Status:* **SUPERSEDED.** Distributed multi-master SQLite research superseded by NATS-backed single-writer relay hub architecture (`goal-ef42902a`).

### Category B: Stale Strategy Documents
1. **`docs/strategy/2026-07-12-fable-deep-review-and-strategic-roadmap.md`:**
   - *Status:* **HISTORICAL ARCHIVE.** Reflects July 2026 competitive landscape prior to the emergence of multi-agent CLI harnesses.
2. **`docs/strategy/2026-08-15-two-imperatives-roadmap.md`:**
   - *Status:* **SUPERSEDED.** Replaced by `dec-7a2b0e91` (Two Paradigms) and `dec-9b41a7c3` (Authoritative Master Roadmap).
3. **`docs/strategy/2026-07-06-four-pov-evaluation-cost-breakup.md`:**
   - *Status:* **ARCHIVE.** Early token cost projections prior to empirical ledger tracking.

### Category C: Dead / Superseded Backlog Stories in `state.db`
The panel recommends marking the following open stories in `state.db` as `status: superseded` or `status: archived`:
1. `story-bs7-interop` (BS-7: skill pack interoperability) — Superseded by Universal Archetypes and Domain Profile Packs (`v0.31.0`).
2. `story-ab6a0586` (BS-9: Trio Orchestration Demo) — Superseded by continuous verification testbed suites (`tests/testbed/`).
3. `story-e3a3170a` (BS-10: PulseScape glassmorphic dashboard) — Absorbed into Vizor Observatory (`synlynk/viz/`).
4. `story-fda756fd` (BS-11: MCP Registry contribution) — Obsolete after Anthropic standardized modelcontextprotocol ecosystem.
5. `story-360c0d73` & `story-dda00e7b` (Reconcile stranded project-docs drift in stale worktrees) — Resolved by current zero-drift engine.

---

## 4. Ratified Operational Sequencing

$$\boxed{
\begin{aligned}
\mathbf{Theme\ 4} & : \text{TPM Autonomous Operations \& Human-in-the-Loop Cadence (v0.32.2)} \\
\mathbf{Theme\ 1} & : \text{Zero-Drift Governance \& Constitutional Spec Linter (v0.32.3)} \\
\mathbf{Theme\ 3} & : \text{FinOps Dual-Ledger Accounting \& Burn-Rate Governor (v0.32.4)} \\
\mathbf{Theme\ 6} & : \text{The Cloud Wedge (synlynk.com Phase 0 Shell \& Accounts) (v0.33.0)} \\
\mathbf{Theme\ 2} & : \text{Sovereign Silicon Deep Local Model Integration (v0.34.0)} \\
\mathbf{Theme\ 5} & : \text{Ambient Co-Pilot & Fenced Companion v2.1 Multi-Surface Suite (v0.35.0)} \\
\mathbf{Theme\ 7} & : \text{Synaptic AI Capability Index Public GTM \& Edge Oracle (v0.36.0)}
\end{aligned}
}$$

### Immediate Next Step
Execute **Theme 4 Finalization (`v0.32.2`)**:
1. Connect TPM sweep daemon loop to evaluate unassigned ready stories against the roadmap.
2. Implement comment command listener for `/approve`, `/revise`, `/hold`.
3. Auto-archive superseded stories (`story-bs7-interop`, `story-ab6a0586`, `story-e3a3170a`, `story-fda756fd`).
