# Implementation Plan: Generalized Vizor BS-6 Views, Dynamic Centrality LOD & Deep Interactive UX

**Spec:** [`docs/superpowers/specs/2026-09-27-vizor-bs6-generalized-views-and-deep-ux-design.md`](docs/superpowers/specs/2026-09-27-vizor-bs6-generalized-views-and-deep-ux-design.md)  
**Governing Goal:** `goal-e3840370` (*Consolidated Vizor Master Control Plane*)  
**Status:** In Progress  

---

## Tasks Overview

| Task | Description | Target Files | Verification Tests |
|:---|:---|:---|:---|
| **Task 1** | Dynamic Top-K Centrality LOD Engine & Test Default-Off Filter | `synlynk/viz.py`, `synlynk/viz_views.py` | `tests/test_viz_dynamic_lod.py` |
| **Task 2** | Logical View: Layered HLD Stack, LLD Model & Interactive Sequence Player | `synlynk/viz.py` (`logical.html`) | `tests/test_viz_logical_view.py` |
| **Task 3** | Product View: User Journeys, Screen/CLI Catalog & Terminal Personas | `synlynk/viz.py` (`product.html`) | `tests/test_viz_product_view.py` |
| **Task 4** | Infra View: Host-Local Runtime Boundary vs. Outbound AI Cloud Egress | `synlynk/viz.py` (`infra.html`) | `tests/test_viz_infra_view.py` |
| **Task 5** | World View: 3-Ring Concentric Ecosystem Radar & Fallback Extraction | `synlynk/viz.py`, `synlynk/viz_views.py` | `tests/test_viz_world_radar.py` |
| **Task 6** | Universal Target Codebase Scanner & Multi-Language Fixture Coverage | `synlynk/viz_views.py` | `tests/test_viz_generic_scanner.py` |

---

### Task 1: Dynamic Top-K Centrality LOD Engine & Test Default-Off Filter

- **Files:** `synlynk/viz.py`, `synlynk/viz_views.py`
- **Tests:** `tests/test_viz_dynamic_lod.py`
- **Steps:**
  1. Write failing test in `tests/test_viz_dynamic_lod.py` validating dynamic percentile threshold derivation for target graphs and default-off test filter at L0/L1.
  2. Implement `calculate_dynamic_lod_tiers` and inject into `_enrich_graphify_html` in `synlynk/viz.py`.
  3. Verify test passes and commit.

---

### Task 2: Logical View: Layered HLD Stack, LLD Model & Interactive Sequence Player

- **Files:** `synlynk/viz.py` (`generate_logical_html`)
- **Tests:** `tests/test_viz_logical_view.py`
- **Steps:**
  1. Write failing test in `tests/test_viz_logical_view.py` validating that `logical.html` renders:
     - Tab 1: Layered HLD Architecture Stack (Presentation, Orchestration, Domain, Persistence, Egress).
     - Tab 2: LLD Component Interaction Diagram.
     - Tab 3: Interactive Sequence Flow Player with selectable lifecycle flows (Unattended Loop, AST Drift, GOVERNS FSM, SSE Relay).
  2. Implement `generate_logical_html` and `_generate_logical_svg` in `synlynk/viz.py`.
  3. Verify test passes and commit.

---

### Task 3: Product View: User Journeys, Screen/CLI Catalog & Terminal Personas

- **Files:** `synlynk/viz.py` (`generate_product_html`), `synlynk/viz_views.py` (`extract_product_nodes`)
- **Tests:** `tests/test_viz_product_view.py`
- **Steps:**
  1. Write failing test in `tests/test_viz_product_view.py` verifying interactive user journey flows, discovered screens/routes, and harness terminal persona cards.
  2. Implement `generate_product_html` in `synlynk/viz.py` and enrich `extract_product_nodes` in `synlynk/viz_views.py`.
  3. Verify test passes and commit.

---

### Task 4: Infra View: Host-Local Runtime Boundary vs. Outbound AI Cloud Egress

- **Files:** `synlynk/viz.py` (`generate_infra_html`), `synlynk/viz_views.py` (`extract_infra_nodes`)
- **Tests:** `tests/test_viz_infra_view.py`
- **Steps:**
  1. Write failing test in `tests/test_viz_infra_view.py` verifying dual-zone layout: Host-Local machine runtime (daemons, state DBs, worktrees, keys) vs Outbound External Cloud AI (Anthropic, OpenAI, Google, xAI, GitHub) + security badges.
  2. Implement `generate_infra_html` in `synlynk/viz.py` and enrich `extract_infra_nodes` in `synlynk/viz_views.py`.
  3. Verify test passes and commit.

---

### Task 5: World View: 3-Ring Concentric Ecosystem Radar & Fallback Extraction

- **Files:** `synlynk/viz.py` (`generate_world_html`), `synlynk/viz_views.py` (`extract_world_nodes`)
- **Tests:** `tests/test_viz_world_radar.py`
- **Steps:**
  1. Write failing test in `tests/test_viz_world_radar.py` verifying 3-ring concentric radar SVG layout and non-empty fallback extraction on clean/fresh repos.
  2. Implement `generate_world_html` with radar rendering in `synlynk/viz.py` and fallback heuristics in `synlynk/viz_views.py`.
  3. Verify test passes and commit.

---

### Task 6: Universal Target Codebase Scanner & Multi-Language Fixture Coverage

- **Files:** `synlynk/viz_views.py`
- **Tests:** `tests/test_viz_generic_scanner.py`
- **Steps:**
  1. Create multi-language fixtures (Fastify/Node.js web app, Go CLI tool, Python Django service) and assert all 5 BS-6 views extract meaningful nodes and edges.
  2. Run full regression suite (`pytest`) to ensure 100% green across all 3,300+ tests.
  3. Review, create PR, approve via QA role, and squash-merge to `main`.
