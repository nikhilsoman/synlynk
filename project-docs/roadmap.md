# Feature Release Priorities & Milestone Roadmap

- **Governing Goals:** `goal-85656c82` (Developer Experience 1.0), `goal-8f64eff5` (Platform Health), `goal-bde24050` (State & Job Truth), `goal-90e73dfd` (GOVERNS Lifecycle), `goal-250b6fb2` (Fleet Parity)
- **Target Launch:** **01 October 2026 (v1.0.0 Developer Preview Launch)**
- **Last Updated:** 2026-09-11

---

## 1. Release Milestone Horizon

| Milestone | Target Horizon | Focus & Scope | Release Gate / Status |
| :--- | :--- | :--- | :--- |
| **v0.18.0** | 2026-08-30 | Dispatch reliability, QA merge-gate authority, Codex parity, Grok headless approval. | **SHIPPED** (2,346 tests) |
| **v0.19.0** | 2026-09-11 | Layered release protocol (`unstable`/`staging`/`main`), autonomous unattended DAG loop (`synlynk run --milestone <M>`), daemon lifecycle recovery, absolute App key paths, dual-ledger state sync. | **SHIPPED** (2,734 tests) |
| **v0.20.0** | 2026-09-18 | Visual Workspace, Autonomous Onboarding & Fleet Resilience: BS-6 Vizor views (Product, Logical, Infra), In-browser GitHub App role creation wizard, scope-bounded sparse worktrees (`git sparse-checkout --cone`), 4-point readiness matrix in `synlynk doctor --readiness`, Meta Muse CLI harness adapter. | **IN PLANNING / EXECUTION** |
| **v0.21.0** | 2026-09-25 | Fleet Swarm Engine & Memory Compaction: Ephemeral cloud swarm runners (#1341), prompt cache telemetry true-up, automatic mid-session context compaction, living charter adaptation loops. | Planned |
| **v1.0.0** | **2026-10-01** | **Developer Preview Public Launch (Time-to-Wow):** 15-minute zero-risk onboarding pipeline, signed GA release on PyPI/pipx, full documentation release, commercial marketing launch. | Target GA Release |
| **v1.1.0** | Q4 2026 | Cross-workgroup team collaboration, community relay server, multi-tenant quota arbitration. | Post-GA |
| **v1.2.0** | Q1 2027 | Enterprise workspace: microVM kernel sandboxing (Bubblewrap/eBPF), SCIP semantic code graph, EdenFS monorepo scaling. | Post-GA |

---

## 2. Milestone v0.20.0 Breakdown (Current Milestone)

### Cluster A: Visual Workspace Views, Role Setup Wizard & Marketing Release Ceremony
- [x] **BS-6 Views in Vizor:** Product view (routes/screens), Logical view (module hierarchy/symbols), and Infra view (containers/deployables) per approved spec (#1539, PR #1556).
- [x] **1-Click GitHub App Onboarding Wizard & Role Studio:** Living charters, 1-click archetype selector, and in-browser role provisioning API (PR #1556).
- [x] **Visual Worktree Sweep Tooling:** Interactive audit panel in Vizor Observatory with 1-click prune for safe/orphaned worktrees (#1346, #1350, #1479, PR #1556).
- [x] **Marketing Release Ceremony Automation:** Continuous GitHub README maintenance, synlynk.com (`website/`) site refresh, and compilation/export of the 3 Synlynk Doc bundles (Quick Start, Official Manual, Command Ref HTML & PDF) dispatched by PM/TPM upon named release (#1557).

### Cluster B: Worktree Lifecycle & Rebase Concurrency
- [ ] **Adaptive Scope-Bounded Sparse Worktrees:** `worktree.mode: sparse` using `git sparse-checkout --cone` for `.synlynk/` + scoped paths (#1389, #1390, #1391).
- [ ] **Sibling Branch Auto-Pruning:** Auto-pruning patch-equivalent ancestor branches upon PR squash-merge (#1348).
- [ ] **Multi-Task Lineage Tracking:** Recording `superseded_by` relationships across stacked dispatches (#1347).
- [ ] **Deterministic Build Timestamp Freezing:** Configuring `SOURCE_DATE_EPOCH` for reproducible test caches (#1349).

### Cluster C: Fleet Diagnostic Truth & Concurrency Resilience
- [ ] **Consolidated 4-Point Readiness Matrix:** Unified attestation in `synlynk doctor --readiness` and Vizor (#1521).
- [ ] **Grok Write Sandbox Canary Validation:** Fail-closed write probe before Grok dispatch (#1522).
- [ ] **Post-Claim Story Un-Stranding:** Automatic timeout reclamation of abandoned in-progress stories (#1507).
- [ ] **SQLite Concurrency & Busy-Timeout Tuning:** Standardizing WAL mode and 30s busy-timeout across all connections (#1503).

### Cluster D: Next-Gen Harness Onboarding (Meta Muse)
- [ ] **Meta Muse CLI Adapter:** First-class dispatch adapter in `synlynk/dispatch.py` with closed-loop receipt check (#1508).
- [ ] **Muse Capability Scoring & Probe:** Registered in taxonomy, probe, and baseline matrix.
- [ ] *(Deferred)* DeepSeek harness evaluation parked until local harness maturation.
