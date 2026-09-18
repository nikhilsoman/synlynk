# Feature Release Priorities & Milestone Roadmap

- **Governing Goals:** `goal-85656c82` (Developer Experience 1.0), `goal-8f64eff5` (Platform Health), `goal-bde24050` (State & Job Truth), `goal-90e73dfd` (GOVERNS Lifecycle), `goal-250b6fb2` (Fleet Parity), `goal-c7113f58` (Over-the-Horizon Strategic Expansion)
- **Target Launch:** **01 October 2026 (v1.0.0 Developer Preview Launch)**
- **Last Updated:** 2026-09-14

---

## 1. Release Milestone Horizon

| Milestone | Target Horizon | Focus & Scope | Release Gate / Status |
| :--- | :--- | :--- | :--- |
| **v0.18.0** | 2026-08-30 | Dispatch reliability, QA merge-gate authority, Codex parity, Grok headless approval. | **SHIPPED** (2,346 tests) |
| **v0.19.0** | 2026-09-11 | Layered release protocol (`unstable`/`staging`/`main`), autonomous unattended DAG loop (`synlynk run --milestone <M>`), daemon lifecycle recovery, absolute App key paths, dual-ledger state sync. | **SHIPPED** (2,734 tests) |
| **v0.20.0** | 2026-09-18 | Visual Workspace, Autonomous Onboarding & Fleet Resilience: BS-6 Vizor views (Product, Logical, Infra), In-browser GitHub App role creation wizard, scope-bounded sparse worktrees (`git sparse-checkout --cone`), 4-point readiness matrix in `synlynk doctor --readiness`, Meta Muse CLI harness adapter. | **SHIPPED** (2,792 tests) |
| **v0.21.0** | 2026-09-25 | **Visual, Cross-Environment & Autonomous Onboarding (FTUE):** Zero-terminal onboarding, Cursor/Windsurf/VS Code/Warp/Antigravity/Replit/Emergent native surface binding, Greenfield starter sandbox ("syn-ping") & Behind-the-Curtain tour, Brownfield 3D discovery & confirm chips, 1-click GitHub App role provisioning, and First Real Win PR in < 5 minutes. | **SHIPPED** (PR #1574) |
| **v0.22.0** | 2026-09-28 | **Graphify AST Knowledge Graph Substrate, Multi-Repo Mesh & Spike Harness:** 1-click tool installer (`synlynk tool install`), commit staleness anchor, Vizor Logical View embed, 4 role-specific skills, JIT context packs (`synlynk pack`), blast-radius calculator (`synlynk impact`), attested PR gate (`synlynk pr check --impact-attested`), circular import detector (`synlynk heal --cycles`), federated multi-repo mesh (`synlynk mesh`), and reusable spike evaluation engine (`synlynk spike eval`). | **SHIPPED** (PR #1579, 2,978 tests) |
| **v1.0.0** | **2026-10-01** | **Developer Preview Public Launch (Time-to-Wow):** 15-minute zero-risk onboarding pipeline, signed GA release on PyPI/pipx, full documentation release, commercial marketing launch. | Target GA Release |
| **v1.1.0** | Q4 2026 | Cross-workgroup team collaboration, community relay server, multi-tenant quota arbitration. | Post-GA |
| **v1.2.0** | Q1 2027 | Enterprise workspace: microVM kernel sandboxing (Bubblewrap/eBPF), SCIP semantic code graph, EdenFS monorepo scaling. | Post-GA |
| **v1.3.0+** | 2027 | **Over-the-Horizon Expansion (`goal-c7113f58`):** DeepSeek Harness (`dsh`) Cordis plugin architecture, ACP headless transport, and Synlynk Cockpit: Active Herdr 4-pane terminal orchestration (`story-0127066f` / `synlynk herdr init`). | Parked Strategic Epic |

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

- [ ] Cross-repo App scope remains parked; the local durable-role App-material doctor/readiness guard is tracked by the child PR for #914.
- [x] Readiness CI compatibility: Point 1 retains the `role_tokens` checkpoint ID while reporting durable App-material failures.

DR hardening remains in sustainment: encrypted provider-neutral package export is
implemented; the cross-machine restore drill is pending access to a second
machine.
