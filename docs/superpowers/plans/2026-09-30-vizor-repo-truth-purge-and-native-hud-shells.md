# Vizor Repo-Truth Purge & Native View HUD Shells Implementation Plan (Spec 2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate cross-repo data leakage and broken 404 fallbacks across Vizor views (`product.html`, `tube.html`, `logical.html`, `infra.html`, `world.html`). Dynamically discover local UI mockups from `.superpowers/brainstorm/` and monorepo packages, replace 404 iframe in Architect Map (`tube.html`) with an interactive glassmorphic HUD shell, and enforce strict repository truth for all workspaces.

**Architecture:** Refactor projection extractors in `synlynk/viz_views.py` (`extract_product_nodes`, `extract_infra_nodes`, `extract_world_nodes`) to inspect workspace topology dynamically (Docker, compose, Prisma, `.env.example`, `.superpowers/brainstorm/`, monorepo `apps/*`), completely removing hardcoded Synlynk-specific daemons, CLI paths, and journeys. Update `synlynk/viz.py` to render native glassmorphic HUD shells instead of raw 404 iframes when code graph artifacts are missing.

**Tech Stack:** Python 3.10+, SQLite3 (WAL mode), HTML5/CSS3 (Glassmorphic Design), `pytest`.

**Spec:** [`docs/superpowers/specs/2026-09-30-vizor-repo-truth-purge-and-native-hud-shells-design.md`](file:///Users/nikhilsoman/dev/synlynk/docs/superpowers/specs/2026-09-30-vizor-repo-truth-purge-and-native-hud-shells-design.md)

---

## Global Constraints

- **Strict Repo Truth:** Under no circumstances may Synlynk internal daemons (Vizor :8721, Relay :27472, StateDB, LLM egress) appear in views for other repositories (such as `rxcc`).
- **Zero 404 Errors:** Missing artifacts (e.g. `graphify.html`) must render a native glassmorphic HUD shell with an actionable trigger, never a browser 404 page in an iframe.
- **Dynamic Prototype Discovery:** Local UI prototypes in `.superpowers/brainstorm/*/content/*.html` and `.superpowers/brainstorm/ux-screenshots/` must be automatically indexed as interactive preview screens.
- **Backward Compatibility:** Synlynk's own workspace views must continue to render correctly by discovering its own components dynamically rather than through static hardcoding.

---

### Task 1: TDD Verification Suite for Repo Truth & Mock Discovery

**Files:**
- Create: `tests/test_vizor_repo_truth.py`

**Test Cases:**
- `test_extract_infra_nodes_arbitrary_repo_no_synlynk_leakage`: Confirms an arbitrary repo with a Dockerfile and Redis does not contain Synlynk daemons (:8721, :27472, StateDB).
- `test_extract_product_nodes_discovers_brainstorm_prototypes`: Confirms HTML mockups in `.superpowers/brainstorm/` are indexed as screen nodes.
- `test_extract_product_nodes_discovers_monorepo_apps`: Confirms `apps/web` and `apps/api` are extracted and Synlynk onboarding journeys are absent.
- `test_extract_world_nodes_no_synlynk_source_paths`: Confirms no node references `synlynk/dispatch.py` or `synlynk/gh.py` on external repos.

- [ ] **Step 1: Write the failing tests**
- [ ] **Step 2: Run pytest to verify failures against current hardcoded implementation**

---

### Task 2: Dynamic Infrastructure Discovery & Daemon Purge

**Files:**
- Modify: `synlynk/viz_views.py:500-580` (`extract_infra_nodes`)
- Test: `tests/test_vizor_repo_truth.py`

**Implementation:**
- Scan `docker-compose*.yml`, `compose*.yaml` for declared services, ports, and container dependencies.
- Scan `Dockerfile*` in root and `apps/*` for exposed ports and images.
- Scan `prisma/schema.prisma`, `models.py`, or database configurations.
- Scan `.env.example` / `.env` for outbound external service endpoints.
- Purge hardcoded Synlynk daemon list (lines 511-539).
- If zero infra files exist, emit a clean "Host-Local / Zero-Cloud Dependencies" architecture card.

- [ ] **Step 1: Implement dynamic infra & egress scanner in `extract_infra_nodes`**
- [ ] **Step 2: Verify `test_extract_infra_nodes_arbitrary_repo_no_synlynk_leakage` passes**

---

### Task 3: Dynamic Monorepo, Screen & UI Prototype Discovery

**Files:**
- Modify: `synlynk/viz_views.py:264-335` (`extract_product_nodes`)
- Test: `tests/test_vizor_repo_truth.py`

**Implementation:**
- Check for monorepo patterns (`pnpm-workspace.yaml`, `package.json` workspaces, `apps/`, `packages/`).
- Discover HTML prototypes in `.superpowers/brainstorm/*/content/*.html` and screenshots in `.superpowers/brainstorm/ux-screenshots/`.
- Register each mockup with title, relative path, and interactive preview route.
- Purge hardcoded `synlynk/cli.py` reference (line 289) and hardcoded Synlynk journeys (lines 304-312).
- Synthesize archetype-appropriate default journeys if no `docs/journeys/` exist.

- [ ] **Step 1: Implement monorepo and brainstorm mockup discovery in `extract_product_nodes`**
- [ ] **Step 2: Verify `test_extract_product_nodes_discovers_brainstorm_prototypes` and `test_extract_product_nodes_discovers_monorepo_apps` pass**

---

### Task 4: Native Glassmorphic Empty HUD Shell for Architect Map (`tube.html`)

**Files:**
- Modify: `synlynk/viz.py:generate_tube_html`
- Create: `tests/test_vizor_architect_hud.py`

**Implementation:**
- Check if `.synlynk/graphify-out/graphify.html` or `graph.json` exists in the target repo.
- If missing, do NOT emit an `<iframe>` pointing to the missing file.
- Instead, render a native glassmorphic HUD:
  - Dark obsidian background with subtle pulsing SVG lattice.
  - Status badge: `STATUS: AWAITING_AST_INDEXING`.
  - Explanatory copy and 1-click trigger button calling `POST /w/<slug>/api/scan` (with SSE progress listener) and displaying CLI command `synlynk scan --deep`.

- [ ] **Step 1: Write test asserting empty HUD shell renders when graph missing**
- [ ] **Step 2: Implement native glassmorphic HUD in `generate_tube_html`**
- [ ] **Step 3: Verify test passes**

---

### Task 5: True Ecosystem Radar & World Purge

**Files:**
- Modify: `synlynk/viz_views.py:620-720` (`extract_world_nodes`)
- Test: `tests/test_vizor_repo_truth.py`

**Implementation:**
- Purge static `synlynk/` source paths from `ring2_catalog`.
- Discover external integrations dynamically from the repo's `.env.example`, `.env`, and dependencies.
- Populate Ring 1 (Internal Services), Ring 2 (Core Integrations), and Ring 3 (Ecosystem & Partners) based strictly on workspace truth.

- [ ] **Step 1: Refactor `extract_world_nodes` to parse workspace-specific integrations**
- [ ] **Step 2: Verify all tests in `tests/test_vizor_repo_truth.py` pass**

---

### Task 6: Multi-Workspace Live Validation & Regression Suite

**Files:**
- Create: `tests/test_vizor_rxcc_truth.py`

**Verification:**
- Run full view generation against both `synlynk` and `rxcc` (if present) or complex synthetic fixtures.
- Verify:
  - Board cards load properly in both workspaces.
  - `rxcc` shows its own apps and UI mockups, zero Synlynk journeys.
  - `rxcc` Infra View shows its own Prisma/containers/ports, zero Synlynk daemons.
  - Architect Map renders the glassmorphic HUD with zero 404 iframe errors.
- Ensure all existing board and vizor tests pass without regression.

- [ ] **Step 1: Run comprehensive test suite**
- [ ] **Step 2: Commit all changes and verify clean git status**
