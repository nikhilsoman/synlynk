---
goal: goal-a222b393
epic: "#2470"
milestone: v0.26.9
arc: governance
---

# Implementation Plan: Workspace Ceremonies Canon & Harness² Recursive Skill Synthesis

**Status:** Proposed  
**Date:** 2026-10-28  
**Author:** Agy (Home Conductor) & Nikhil Soman  
**Governing Goal:** `goal-a222b393` (*Agent Charter Framework: Composable Roles, Capabilities & Autonomous Persona Evolution*)  
**Parent Epic:** #2458 | **Milestone Epic:** #2470 | **RSI Epic:** #2547  
**Design Specification:** `docs/superpowers/specs/2026-10-28-workspace-ceremonies-canon-and-skill-synthesis-design.md`  
**Reference Protocol:** `docs/process/release-implementation-protocol.md`  

---

## 1. Overview & Architectural Scope

This implementation plan delivers **v0.26.9** ("Workspace Ceremonies Canon & Harness² Recursive Skill Synthesis"), realizing the dual-recursion Propose-Probe-Compose loop across 5 tracked stories:

| Database ID | Story Key | Title | Domain | Role |
| :--- | :--- | :--- | :---: | :---: |
| `story-f0088dee` | `story-docs-graph-sidecar` | Graphify Markdown AST & Docs Graph Sidecar (`synlynk scan --docs`) | Backend | Architect |
| `story-ca522d5e` | `story-ceremony-miner` | Heuristic Ceremony Discovery & Motif Miner | Backend | Architect |
| `story-eb9bfa85` | `story-ceremony-oracle-test` | Empirical Ceremony Discovery Benchmark Spike | Testing | QA |
| `story-6ab8cb96` | `story-ceremony-canon` | Workspace Ceremonies Canon & Onboarding Engine Integration | Backend | Architect |
| `story-6ff70a5e` | `story-release-conductor` | Inaugural Reference Ceremony: `release-conductor` Skill | Frontend | PM |

---

## 2. Story Breakdown & Step-by-Step Implementation

### Story 1: `story-f0088dee` — Graphify Markdown AST & Docs Graph Sidecar

- **Objective:** Extend `synlynk scan` to support `--docs`, extracting action-sequence graphs from markdown devlogs, specs, plans, and commit summaries into `.synlynk/graphify-out/docs-graph.json`.
- **Target Files:**
  - `synlynk/docs_graph.py`: Core parser transforming markdown AST into directed NetworkX graphs.
  - `synlynk/scan.py` / `synlynk/cli.py`: Wire CLI flag `synlynk scan --docs` and `--refresh-docs-graph`.
  - `tests/test_docs_graph.py`: Hermetic unit and integration tests.
- **Node & Edge Taxonomy:**
  - Nodes: `Action` (shell/CLI calls, e.g. `synlynk pr check`, `git worktree add`), `Gate` (invariants, e.g. `test_four_point_attribution`), `Artifact` (specs, plans, releases), `Role` (`pm`, `qa`, `architect`, etc.).
  - Edges: `FOLLOWED_BY` (sequential execution), `PERFORMED_BY` (role attribution), `VERIFIED_WITH` (gate relationship).
- **Verification:**
  - `pytest tests/test_docs_graph.py -v`
  - `python3 bin/synlynk.py scan --docs --output /tmp/test-docs-graph.json`

---

### Story 2: `story-ca522d5e` — Heuristic Ceremony Discovery & Motif Miner

- **Objective:** Implement warm-traversal motif discovery over `docs-graph.json` to identify repeated action chains ($n \ge 3$) that represent emergent rituals.
- **Target Files:**
  - `synlynk/ceremonies.py`: Path analysis engine, frequency counting, and candidate skill templating.
  - `synlynk/cli.py`: Subcommand `synlynk ceremonies discover` / `synlynk ceremonies propose`.
  - `tests/test_ceremony_miner.py`: Motif mining validation on synthetic and historical graphs.
- **Algorithm & Logic:**
  - Compute directed walk sub-paths of length $L \in [3, 8]$.
  - Filter sub-paths with occurrence count $\ge 3$ across distinct sessions/files.
  - Compute dominant `PERFORMED_BY` role for each motif.
  - Propose candidate skill name, description (Tier 0), and execution checklist (Tier 1).
- **Verification:**
  - `pytest tests/test_ceremony_miner.py -v`
  - `python3 bin/synlynk.py ceremonies discover --min-frequency 3`

---

### Story 3: `story-eb9bfa85` — Empirical Ceremony Discovery Benchmark Spike

- **Objective:** Blind validation benchmark testing whether the motif miner autonomously discovers the 3 canonical Synlynk engineering rituals:
  1. The 6-Phase Release Protocol (`release-conductor`)
  2. The Sentinel Alert Triage Ritual (`sentinel-triage`)
  3. The Worktree Cleanup / Salvage Ceremony (`worktree-salvage`)
- **Target Files:**
  - `tests/test_ceremony_discovery_spike.py`: Empirical verification benchmark reading historical corpus.
- **Success Criteria:**
  - Ingestion of `project-docs/devlogs/*.md`, `docs/superpowers/specs/*.md`, and recent git log history.
  - Top 3 discovered candidate motifs match the target rituals with $\ge 90\%$ step overlap.
- **Verification:**
  - `pytest tests/test_ceremony_discovery_spike.py -s -v`

---

### Story 4: `story-6ab8cb96` — Workspace Ceremonies Canon & Onboarding Engine

- **Objective:** Integrate the ceremony catalog into workspace onboarding (`synlynk init` / `synlynk onboard`), generating workspace-tailored skills into `.synlynk/skills/` and updating agent charter frontmatter.
- **Target Files:**
  - `synlynk/onboarding.py`: Seed `.synlynk/skills/` based on detected workspace stack and active agent roles.
  - `synlynk/charters.py`: Update agent markdown charters with bound ceremony skill declarations.
  - `tests/test_ceremonies_canon_onboarding.py`: Verification that fresh workspaces receive correct ceremonies.
- **Verification:**
  - `pytest tests/test_ceremonies_canon_onboarding.py -v`

---

### Story 5: `story-6ff70a5e` — Inaugural Reference Ceremony: `release-conductor` Skill

- **Objective:** Codify the 6-phase release lifecycle into the production reference skill `.synlynk/skills/release-conductor/SKILL.md` bound to `pm` and `tpm` roles.
- **Target Files:**
  - `.synlynk/skills/release-conductor/SKILL.md`: 3-tier progressive disclosure skill definition (~600 tokens).
  - `.synlynk/agents/pm.md`: Bind `release-conductor` in charter YAML frontmatter skills list.
  - `.synlynk/agents/tpm.md`: Bind `release-conductor` in charter YAML frontmatter skills list.
  - `docs/process/release-implementation-protocol.md`: Canonical reference standard.
  - `tests/test_release_conductor_skill.py`: Validate syntax, schema compliance, and token budget.
- **Token Budget Contract:**
  - Frontmatter (Tier 0): $< 50$ tokens.
  - Execution Checklist (Tier 1): $< 650$ tokens.
  - References (Tier 2): Linked externally to `docs/process/release-implementation-protocol.md`.
- **Verification:**
  - `pytest tests/test_release_conductor_skill.py -v`
  - `python3 bin/synlynk.py release --check-docs --role pm`

---

## 3. Invariants & Quality Gates

1. **Four-Point Attribution:** Every design spec, plan, and test must satisfy `tests/test_four_point_attribution.py`.
2. **Attribution Trailer:** Every commit must include `Co-Authored-By: Agy (Gemini) <noreply@antigravity.dev>` (or appropriate dispatch harness trailer).
3. **No Prompt Bloat:** Skills must strictly adhere to the 3-tier progressive disclosure contract. Total prompt injection per dispatch must not exceed 800 tokens for skill overhead.
4. **Hermetic Worktrees:** Feature execution occurs in isolated git worktrees (`.worktrees/feat-<agent>-<topic>`).
5. **Non-Author PR Review:** PRs must be reviewed and merged by non-authoring agents in compliance with `.synlynk/policy.json` (`merge_authority`).

---

## 4. Execution Readiness Checklist

- [x] Canonical Release Implementation Protocol authored (`docs/process/release-implementation-protocol.md`).
- [x] Design specification authored and verified with 4-point frontmatter (`docs/superpowers/specs/2026-10-28-workspace-ceremonies-canon-and-skill-synthesis-design.md`).
- [x] Target release `v0.26.9` allocated and documented in `project-docs/roadmap.md`.
- [x] 5 milestone stories created and linked to `goal-a222b393` in `state.db`.
- [x] `project-docs/todo.md` synchronized.
- [x] Implementation plan written with verified four-point attribution frontmatter.
