# Feature Release Priorities & Milestone Roadmap

- **Governing Goals:** `goal-85656c82` (Developer Experience 1.0), `goal-8f64eff5` (Platform Health), `goal-bde24050` (State & Job Truth), `goal-90e73dfd` (GOVERNS Lifecycle), `goal-250b6fb2` (Fleet Parity), `goal-c7113f58` (Over-the-Horizon Strategic Expansion), `goal-f0489be9` (Vizor World View & Ecosystem Radar)
- **Target Launch:** **01 October 2026 (v1.0.0 Developer Preview Launch)**
- **Last Updated:** 2026-09-19

---

## 1. Release Milestone Horizon

| Milestone | Target Horizon | Focus & Scope | Release Gate / Status |
| :--- | :--- | :--- | :--- |
| **v0.18.0** | 2026-08-30 | Dispatch reliability, QA merge-gate authority, Codex parity, Grok headless approval. | **SHIPPED** (2,346 tests) |
| **v0.19.0** | 2026-09-11 | Layered release protocol (`unstable`/`staging`/`main`), autonomous unattended DAG loop (`synlynk run --milestone <M>`), daemon lifecycle recovery, absolute App key paths, dual-ledger state sync. | **SHIPPED** (2,734 tests) |
| **v0.20.0** | 2026-09-18 | Visual Workspace, Autonomous Onboarding & Fleet Resilience: BS-6 Vizor views (Product, Logical, Infra), In-browser GitHub App role creation wizard, scope-bounded sparse worktrees (`git sparse-checkout --cone`), 4-point readiness matrix in `synlynk doctor --readiness`, Meta Muse CLI harness adapter. | **SHIPPED** (2,792 tests) |
| **v0.21.0** | 2026-09-25 | **Visual, Cross-Environment & Autonomous Onboarding (FTUE):** Zero-terminal onboarding, Cursor/Windsurf/VS Code/Warp/Antigravity/Replit/Emergent native surface binding, Greenfield starter sandbox ("syn-ping") & Behind-the-Curtain tour, Brownfield 3D discovery & confirm chips, 1-click GitHub App role provisioning, and First Real Win PR in < 5 minutes. | **SHIPPED** (PR #1574) |
| **v0.22.0** | 2026-09-28 | **Graphify AST Knowledge Graph Substrate, Multi-Repo Mesh & Spike Harness:** 1-click tool installer (`synlynk tool install`), commit staleness anchor, Vizor Logical View embed, 4 role-specific skills, JIT context packs (`synlynk pack`), blast-radius calculator (`synlynk impact`), attested PR gate (`synlynk pr check --impact-attested`), circular import detector (`synlynk heal --cycles`), federated multi-repo mesh (`synlynk mesh`), and reusable spike evaluation engine (`synlynk spike eval`). | **SHIPPED** (PR #1579, 2,978 tests) |
| **v1.0.0** | **2026-10-01** | **[Wave 1] Developer Preview Launch (Synlynk Personal):** Zero-dependency local stability, 9 pillars (Model First-Class, World View, Brownfield Ingestion, Magic PR, Multi-Home Conductor). | Active Sprint (`story-ffb0f3e6`) |
| **v1.1.0** | **2026-10-08** | **[Wave 2] Synlynk Teams Relay (Peer-to-Peer Mesh):** Ephemeral P2P event bus, distributed task leases, sibling AST conflict preemption, 3-tier identity attribution. | Scheduled Wave (`story-f6782d57`) |
| **v1.2.0** | **2026-10-15** | **[Wave 3] Synlynk Teams Server (Hosted Collaboration Hub):** Centralized multi-tenant workspace, hosted W9 Vizor with RBAC, encrypted state sync, fleet quotas. | Scheduled Wave (`story-f4dbf2ce`) |
| **v1.3.0** | **2026-10-22** | **[Wave 4] Synlynk Model Hub & Provider Aggregator:** Meta Muse GA integration, Local oMLX inference harness, BYO API-key aggregators, empirical spike harness. | Scheduled Wave (`story-c7064c40`) |
| **v1.4.0+** | 2027 | **Over-the-Horizon Expansion (`goal-c7113f58`):** DeepSeek Harness (`dsh`) Cordis plugin architecture, ACP headless transport, and Synlynk Cockpit: Active Herdr 4-pane terminal orchestration (`story-0127066f` / `synlynk herdr init`). | Parked Strategic Epic |

---

## 2. Milestone v0.20.0 Breakdown (Current Milestone)

### Cluster A: Visual Workspace Views, Role Setup Wizard & Marketing Release Ceremony
- [x] **BS-6 Views in Vizor:** Product view (routes/screens), Logical view (module hierarchy/symbols), and Infra view (containers/deployables) per approved spec (#1539, PR #1556).
- [x] **1-Click GitHub App Onboarding Wizard & Role Studio:** Living charters, 1-click archetype selector, and in-browser role provisioning API (PR #1556).
- [x] **Visual Worktree Sweep Tooling:** Interactive audit panel in Vizor Observatory with 1-click prune for safe/orphaned worktrees (#1346, #1350, #1479, PR #1556).
- [x] **Marketing Release Ceremony Automation:** Continuous GitHub README maintenance, synlynk.com (`website/`) site refresh, and compilation/export of the 3 Synlynk Doc bundles (Quick Start, Official Manual, Command Ref HTML & PDF) dispatched by PM/TPM upon named release (#1557).

### Cluster B: Worktree Lifecycle & Rebase Concurrency
- [x] **Adaptive Scope-Bounded Sparse Worktrees:** `worktree.mode: sparse` using `git sparse-checkout --cone` for `.synlynk/` + scoped paths (#1389, #1390, #1391, PR #1558).
- [x] **Sibling Branch Auto-Pruning:** Auto-pruning patch-equivalent ancestor branches upon PR squash-merge (#1348, PR #1558).
- [x] **Multi-Task Lineage Tracking:** Recording `superseded_by` relationships across stacked dispatches (#1347, PR #1558).
- [x] **Deterministic Build Timestamp Freezing:** Configuring `SOURCE_DATE_EPOCH` for reproducible test caches (#1349, PR #1558).

### Cluster C: Fleet Diagnostic Truth & Concurrency Resilience
- [x] **Consolidated 4-Point Readiness Matrix:** Unified attestation in `synlynk doctor --readiness` and Vizor (#1521).
- [x] **Grok Write Sandbox Canary Validation:** Fail-closed write probe before Grok dispatch (#1522).
- [x] **Post-Claim Story Un-Stranding:** Automatic timeout reclamation of abandoned in-progress stories (#1507).
- [x] **SQLite Concurrency & Busy-Timeout Tuning:** Standardizing WAL mode and 30s busy-timeout across all connections (#1503).

### Cluster D: Next-Gen Harness Onboarding (Meta Muse)
- [x] **Meta Muse CLI Adapter:** First-class dispatch adapter in `synlynk/dispatch.py` with closed-loop receipt check (#1508, PR #1560).
- [x] **Muse Capability Scoring & Probe:** Registered in taxonomy, probe, and baseline matrix (PR #1560).
- [ ] *(Deferred)* DeepSeek harness evaluation parked until local harness maturation.

### Cluster E (LIVE-12): Autonomous Marketing Surface Remediation & Dual-Treatment Engine
- [x] **Phase 1 (Surface Remediation):** Prepend canonical YAML frontmatter across all 61 un-frontmattered blog posts, refresh `website/src/features.njk` to v0.20.0 matrix, author strategic release post #197, and execute v0.20.0 release ceremony (`README.md` 2,804 tests + `release.json`).
- [x] **Phase 2 (CI & Preflight Quality Gate):** Enforce `validate_all_blog_posts()` in `synlynk pr check` and `tests/test_marketing.py`; harden `website/.eleventy.js` with defensive date fallback preventing mtime leaks.
- [x] **Phase 3 (Autonomous PR Trigger & Two-Tier Blog):** Add `synlynk marketing sync-pr <pr>` and post-merge GitHub Action workflow; deploy two-tier blog view on `synlynk.com/blog` (Featured Named Release strategic communication vs Per-PR build diary).
- [x] **Phase 4 (Automated PDF & EPUB Compilation):** Automate headless Chrome PDF and Pandoc EPUB generation for Quick Start, Official Manual, Command Reference, and Book manuscript (`the-supervised-machine`) during release ceremonies and mirror to website assets.

### Cluster F: Safe Fleet Parity Migration Engine & In-Browser Role Provisioning (v0.20.1)
- [x] **Point 3 Policy Authority Bugfix:** Resolves false-positive readiness failure for standard 2-tier overrides in `readiness.py` and expands `test_readiness_matrix.py`.
- [x] **Architectural Design Spec Approved:** `docs/superpowers/specs/2026-09-12-safe-fleet-parity-migration-engine-design.md` detailing Worktree-Isolated Shadow Engine (`synlynk heal --parity`) and `synlynk viz` in-browser 6-role GitHub App manifest provisioning.
- [x] **Core Parity Engine Implementation (`synlynk/parity.py`):** Stack detection, AST/fence parser, worktree-isolated migration runner, and `synlynk doctor` fleet parity check (`_hc_fleet_parity`).
- [x] **`synlynk viz` Role Provisioning Web Flow:** `/onboarding/roles` UI with GitHub App manifest redirect, loopback auth callback, credentials writer, and live 4-point readiness self-test attestation (`/api/readiness/live`).
- [x] **Fleet Parity Upgrades:** Executed safe worktree-isolated migration playbooks across `cc-videoreframing`, `playblazer-ng`, and `hitchcock` without modifying main branches.

### Cluster G: Graphify AST Knowledge Graph Substrate, Multi-Repo Mesh & Spike Evaluation Harness (v0.22.0)
- [x] **Phase 1 (Core AST Provider & Vizor Embed):** 1-click tool installer (`synlynk tool install`), commit staleness anchor (`built_at_commit`), Vizor Logical View Graphify call graph embed, and FTUE Onboarding Wizard recommendation (PR #1579).
- [x] **Phase 2 (Role-Specific Charter Skills & Context Packs):** 4 materialized skills in `.synlynk/skills/`, living charter adaptation in `synlynk/charters.py`, and JIT AST context pack synthesis (`synlynk pack`) with prompt injection (PR #1579).
- [x] **Phase 3 (High-Leverage Commands & Verification Gates):** Blast-radius impact calculator (`synlynk impact`), graph-attested PR verification gate (`synlynk pr check --impact-attested`), and circular import healer (`synlynk heal --cycles`) (PR #1579).
- [x] **Phase 4 (Multi-Repo Mesh & Spike Evaluation Harness):** Federated multi-repo knowledge mesh aggregator (`synlynk mesh`) and reusable empirical spike evaluation harness (`synlynk spike eval`) (PR #1579).

### Daemon liveness Wave 1 (#1588)

- [x] Verified #1573's false-`already running` fix and added the dead-PID status/start regression test; targeted daemon tests pass.

### Workspace identity slice (#914)

- [x] W0-W3 and bounded W4/W6 slices are on main; W5 specialist type resolution/effective skills merged in PR #1690 (2026-09-19).
- [x] W7 runtime/swarm identity acceptance merged in PR #1691 (2026-09-19); duplicate product/type App initialization now fails closed and worker env is PEM-free.
- [x] W8 pack onboarding/organigram expansion merged in PR #1692 (2026-09-19); software-product, studio, and agency packs plus explicit connector isolation are on main.
- [ ] Cross-repo App scope remains parked; hosted W9 Vizor remains a fail-closed placeholder with no OAuth/hosting per handoff.
- [x] Readiness CI compatibility: Point 1 retains the `role_tokens` checkpoint ID while reporting durable App-material failures.

DR hardening remains in sustainment: encrypted provider-neutral package export is
implemented; the cross-machine restore drill is pending access to a second
machine.

Control-plane hygiene (2026-09-19): two definitively merged worktrees were
removed and stale Git metadata pruned; 71 worktrees remain intentionally
unremoved because they are dirty or their PR state is not currently verifiable.
The malformed legacy repo-local `.synlynk/state.db` was quarantined with its
WAL/SHM sidecars; the canonical product ledger passed integrity checks. Sentinel
noise was reduced from 824 to 160 by clearing only historical receipt/version/
tool-pressure classes. Cost/token and other diagnostic alerts remain retained.

Follow-up (2026-09-19): GitHub-backed classification removed the next safe
merged batch; remaining worktrees are intentionally preserved because they are
open-PR, dirty, detached-with-commits, or no-PR branches with unique content.
Capability sweep and the non-live fleet matrix are green. Live selftest
registry isolation is fixed in PR #1693; merge is pending CI and QA-gate
resolution. Grok/Muse probe health and local oMLX configuration remain
operator-level environment work, not product-state recovery.

---

## 3. Milestone v1.0.0 (01 Oct 2026) — 11-Day Stabilization & 9-Pillar Plan

### Pillar 1: First-Class Model Selection & Graphify Cost Routing (`goal-85656c82`)
- Decouple Model Family from Harness runtime across all CLI dispatches.
- Graphify AST blast-radius complexity scoring (`synlynk impact`) driving dynamic cost tiering (Flash/Haiku for leaf edits $\to$ Sonnet/GPT-4o for refactors $\to$ o1/Pro for specs).

### Pillar 2: Rich Local Vizor & World View Control Plane (`goal-vizor-personal`, `goal-f0489be9`)
- 4-Perspective Vizor Dashboard on `localhost:8585` (Product View, Logical AST View, Infra View, and **World View**).
- **World View Tier 1 Code Truth Extraction (`synlynk/viz_views.py`):** Ingests outbound API clients, inbound webhook listeners, identity providers (IdPs), and compliance boundaries.
- **Concentric Radar Layout (SVG):** Visualizes Product Core at center $\to$ Ring 1 (Live Code Truth) $\to$ Ring 2 (Standby Integrations) $\to$ Ring 3 (Ecosystem Opportunities).

### Pillar 3: Deep Brownfield Project Onboarding (`synlynk init --brownfield`)
- Zero-terminal reverse-engineering of legacy test suites, linters, package managers, and commit churn.
- Autonomous synthesis of living `roadmap.md`, `memory.md`, and `todo.md` project documentation.

### Pillar 4: Magic PR Engine (< 5 Minute Time-to-Wow)
- Zero-risk initial scan generating verified, test-attested quick-win PRs (cycle healing, doc repair, test coverage).

### Pillar 5: Fleet Parity, Dynamic Handover & Token Isolation (`goal-250b6fb2`)
- **Dynamic Handover Drain-to-Boundary:** Outgoing Home Conductor marks `DRAINING`, finishing in-flight tasks cleanly before session stop; incoming Home claims next task without split-brain collisions.
- **Worktree Product Identity & App-Token Isolation:** Fixed worktree slug derivation via `git-common-dir` root, locked explicit `"identity_slug": "synlynk"` in config, and strictly fail-closed on role App token absence.

### Pillar 6: Autonomous Agent Work Discovery & Triage
- Proactive ingestion of GitHub issues and local discovery backlog into ready stories (`synlynk backlog triage`).
- Living charter triggers for automated QA PR claiming and Architect complexity audits.

### Pillar 7: Autonomous PM Sweeps & Ecosystem Opportunity Radar (`goal-f0489be9`)
- `synlynk pm sweep` scans competitor capabilities and adjacent market integrations.
- Tier 2 PM Radar Playbook: Proactively plots opportunity nodes on Ring 3 of the World View with 1-click `synlynk story create`.

### Pillar 8: Autonomous Architect Boundary Resilience & Modularity Watchdog (`goal-f0489be9`, `goal-8f64eff5`)
- Watchdog auditing disk footprint, worktree cleanup, memory/RSS usage, and WAL concurrency.
- Tier 2 Architect Boundary Playbook: Audits World View outbound dependencies for SPOF risks, missing circuit breakers, and egress security.

### Pillar 9: Active Marketing Agent Charter & Doc Publishing
- Autonomous two-tier blog sync (`synlynk marketing sync-pr <pr>`) and release note maintenance.
- Automated compilation of Quick Start, Official Manual, and CLI Reference into standalone HTML/PDF/EPUB assets.
