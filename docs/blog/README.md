# synlynk Blog Series: Building the OS for Multi-Agent Development

A post-mortem / build diary documenting the design choices, strategic pivots, and technical decisions behind synlynk — from first commit to the OS for multi-agent development.

## Series Index

| Post | Title | PR | Date |
|---|---|---|---|
| [00](./00-why-polyglot-harness.md) | Why We Need a Polyglot Harness | — | 2026-06-09 |
| [01](./01-the-project-that-built-synlynk.md) | The Project That Built synlynk | — | 2026-06-09 |
| [02](./02-pr1-v0.2.0-the-kernel.md) | PR #1 — v0.2.0: Laying the Kernel | [#1](https://github.com/nikhilsoman/synlynk/pull/1) | 2026-05-17 |
| [03](./03-pr3-v0.2.1-correctness-patch.md) | PR #3 — v0.2.1: The Correctness Tax | [#3](https://github.com/nikhilsoman/synlynk/pull/3) | 2026-05-17 |
| [04](./04-pr23-24-v0.2.2-attribution.md) | PR #23/#24 — v0.2.2: Attribution in a Polyglot World | [#23](https://github.com/nikhilsoman/synlynk/pull/23), [#24](https://github.com/nikhilsoman/synlynk/pull/24) | 2026-05-20 |
| [05](./05-pr26-v0.3.0-multi-agent-foundation.md) | PR #26 — v0.3.0: The Multi-Agent Foundation | [#26](https://github.com/nikhilsoman/synlynk/pull/26) | 2026-06-03 |
| [06](./06-pr27-v0.4.0-autonomy-driver.md) | PR #27 — v0.4.0: The Autonomy Driver | [#27](https://github.com/nikhilsoman/synlynk/pull/27) | closed (not merged) |
| [07](./07-pr28-architecture-pivot.md) | PR #28 — The Architecture Pivot | [#28](https://github.com/nikhilsoman/synlynk/pull/28) | 2026-06-09 |
| [08](./08-pr29-v0.3.1-sentinel-observability.md) | PR #29 — v0.3.1: When the OS Learns to Self-Diagnose | [#29](https://github.com/nikhilsoman/synlynk/pull/29) | 2026-06-10 |
| [09](./09-pr30-e2e-test-suite.md) | PR #30 — The E2E Safety Net | [#30](https://github.com/nikhilsoman/synlynk/pull/30) | 2026-06-10 |
| [10](./10-brainstorm-hybrid-workgroup-imperatives.md) | The Four Imperatives — Redesigning synlynk's Core Contracts | — | 2026-06-14 |
| [11](./11-pr39-v0.4.0-hybrid-workgroup-bootstrap.md) | PR #39 — v0.4.0: The Hybrid Workgroup Bootstrap | [#39](https://github.com/nikhilsoman/synlynk/pull/39) | 2026-06-14 |
| [12](./12-pr42-v0.6.0-job-control.md) | PR #42 — v0.6.0: Job Control + Model-Aware Capability Engine | [#42](https://github.com/nikhilsoman/synlynk/pull/42) | 2026-06-14 |
| [13](./13-v0.4.1-instruction-reach.md) | v0.4.1 — Instruction Reach: Context Injection Across Every IDE | TBD | 2026-06-17 |
| [14](./14-v0.4.2-task-status-model.md) | v0.4.2 — Task Status Model | TBD | — |
| [15](./15-pr-v0.7.0-static-scan-quality.md) | v0.7.0 — Static Scan Quality | TBD | — |
| [16](./16-pr-capability-dogfood.md) | Capability Dogfood | TBD | — |
| [17](./17-pr-codex-headless-dispatch.md) | Codex Headless Dispatch | TBD | — |
| [18](./18-pr52-v0.8.0-support-engineer-agent.md) | PR #52 — v0.8.0: Support Engineer Agent | [#52](https://github.com/nikhilsoman/synlynk/pull/52) | — |
| [19](./19-v0.9.0-kernel-fixes.md) | PR #53 — v0.9.0: Kernel Fixes + Package Split | [#53](https://github.com/nikhilsoman/synlynk/pull/53) | 2026-06-21 |
| [20](./20-post-v0.9.0-install-init-hardening.md) | Post v0.9.0 — The Gap Between Shipping and Working | hotfix | 2026-06-22 |
| [21](./21-pr-v092-team-onboarding-consensus.md) | PRs — v0.9.2: Team Onboarding + Consensus | TBD | 2026-06-22 |
| [22](./22-pr56-57-58-v0.9.3-async-daemon.md) | PRs #56/#57/#58 — v0.9.3: synlynk Goes Always-On | [#56](https://github.com/nikhilsoman/synlynk/pull/56), [#57](https://github.com/nikhilsoman/synlynk/pull/57), [#58](https://github.com/nikhilsoman/synlynk/pull/58) | 2026-06-23 |
| [23](./23-fix-dispatch-context-scoping.md) | P0 Fix: Dispatch Context Scoping | [#59](https://github.com/nikhilsoman/synlynk/pull/59) | 2026-06-24 |
| [24](./24-pr31-v0.9.4-context-dispatch-relay.md) | PR #60 — v0.9.4: Context, Dispatch, and Relay | [#60](https://github.com/nikhilsoman/synlynk/pull/60) | 2026-06-24 |
| [25](./25-pr64-v0.9.7-grok-agent-support.md) | PR #64 — v0.9.7: Grok Agent Support | [#64](https://github.com/nikhilsoman/synlynk/pull/64) | 2026-06-26 |
| [26](./26-pr68-v0.9.8-pipx-packaging.md) | PR #68 — v0.9.8: pipx Packaging | [#68](https://github.com/nikhilsoman/synlynk/pull/68) | 2026-06-27 |
| [27](./27-pr69-v0.9.8-synlynk-doctor.md) | PR #69 — v0.9.8: synlynk doctor | [#69](https://github.com/nikhilsoman/synlynk/pull/69) | 2026-06-27 |
| [28](./28-pr70-v0.9.8-health-lifecycle.md) | PR #70 — v0.9.8: Health + Lifecycle | [#70](https://github.com/nikhilsoman/synlynk/pull/70) | 2026-06-27 |
| [29](./29-pr78-bs5-phase1-scaffold.md) | PR #78 — BS-5: Website Phase 1 Scaffold | [#78](https://github.com/nikhilsoman/synlynk/pull/78) | — |
| [30](./30-pr78-bs5-phase2-agy-templates.md) | PR #78 — BS-5: Website Phase 2 Agy Templates | [#78](https://github.com/nikhilsoman/synlynk/pull/78) | — |
| [31](./31-pr78-bs5-phase2-grok-carousel.md) | PR #78 — BS-5: Website Phase 2 Grok Carousel | [#78](https://github.com/nikhilsoman/synlynk/pull/78) | — |
| [32](./32-pr78-bs5-phase3-grok-canvas.md) | PR #78 — BS-5: Website Phase 3 Grok Canvas | [#78](https://github.com/nikhilsoman/synlynk/pull/78) | — |
| [33](./33-pr78-bs5-phase3-agy-subpages.md) | PR #78 — BS-5: Website Phase 3 Agy Subpages | [#78](https://github.com/nikhilsoman/synlynk/pull/78) | — |
| [34](./34-pr82-bs14-harness-compatibility.md) | PR #82 — BS-14: Harness Compatibility System | [#82](https://github.com/nikhilsoman/synlynk/pull/82) | 2026-07-01 |
| [35](./35-pr89-v0.10.0-bs17-scan-wizard.md) | PR #89 — v0.10.0: synlynk scan + wizard FTUE | [#89](https://github.com/nikhilsoman/synlynk/pull/89) | 2026-07-01 |
| [36](./36-prTBD-bs18-migrate.md) | BS-18: synlynk migrate — state.db import | — | 2026-07-01 |
| [37](./37-prTBD-v010-readme.md) | v0.10.0: README overhaul | — | 2026-07-01 |
| [38](./38-pr97-v0.10.1-release-command.md) | PR #97–#99 — Job summaries, synlynk release, synlynk status | [#97](https://github.com/nikhilsoman/synlynk/pull/97) | 2026-07-02 |
| [39](./39-prTBD-bs21-vizor.md) | PR #101 — BS-21 Vizor: Local Browser Dashboard | [#101](https://github.com/nikhilsoman/synlynk/pull/101) | 2026-07-03 |
| **[40](./40-v010-developer-preview.md)** | **v0.10.0 — Developer Preview (Named Release)** | [#89–#102](https://github.com/nikhilsoman/synlynk/releases/tag/v0.10.0) | **2026-07-03** |
| [41](./41-prTBD-bs13-workspace-hud.md) | BS-13 Workspace HUD | TBD | 2026-07-03 |
| [42](./42-pr110-bs16-ecosystem-status.md) | PR #110 — BS-16 Ecosystem Status | [#110](https://github.com/nikhilsoman/synlynk/pull/110) | 2026-07-04 |
| [43](./43-pr113-bs22-vizor-efficiency.md) | PR #113 — BS-22 Vizor Efficiency Tab | [#113](https://github.com/nikhilsoman/synlynk/pull/113) | 2026-07-04 |
| [44](./44-pr114-116-tc2-agy-dispatch-fix.md) | PRs #114–#116 — The TC-2 Agent Dispatch Fix Arc | [#114](https://github.com/nikhilsoman/synlynk/pull/114), [#115](https://github.com/nikhilsoman/synlynk/pull/115), [#116](https://github.com/nikhilsoman/synlynk/pull/116) | 2026-07-05 |
| [45](./45-pr117-bs13-observatory.md) | PR #117 — Live Job Observatory | [#117](https://github.com/nikhilsoman/synlynk/pull/117) | 2026-07-05 |
| [46](./46-pr118-bs22-vizor-efficiency.md) | PR #118 — BS-22: Vizor Gets Its Eyes | [#118](https://github.com/nikhilsoman/synlynk/pull/118) | 2026-07-05 |
| [47](./47-pr119-bs12-agent-autonomy-bridge.md) | PR #119 — BS-12: The Agent Autonomy Bridge | [#119](https://github.com/nikhilsoman/synlynk/pull/119) | 2026-07-05 |
| **[48](./48-v011-agent-ecosystem-operational-layer.md)** | **v0.11.0 — The Agent Ecosystem Operational Layer (Named Release)** | [v0.11.0](https://github.com/nikhilsoman/synlynk/releases/tag/v0.11.0) | **2026-07-05** |
| [49](./49-prTBD-bs8-goal-hierarchy.md) | BS-8: The Business Goal Layer | TBD | 2026-07-11 |
| [50](./50-prTBD-governs-stage-rollout.md) | GOVERNS: Rolling Out the Seven-Stage Vocabulary | TBD | 2026-07-11 |
| [51](./51-prTBD-vizor-goals-panel.md) | Vizor Gets a Goals Panel | TBD | 2026-07-11 |
| [54](./54-prTBD-fix-dispatch-ready-jobs-unification.md) | Queue Path Uses Shared `dispatch_agent` (#190) | TBD | 2026-07-12 |
| [56](./56-pr244-measurement-ledger-phase2-codex-adapter.md) | PR #244 — Measurement Ledger Phase 2: The Codex Structured-Output Adapter | [#244](https://github.com/nikhilsoman/synlynk/pull/244) | 2026-07-14 |
| [59](./59-pr252-measurement-ledger-phase2-claude-adapter.md) | PR #252 — Measurement Ledger Phase 2: The Claude Structured-Output Adapter | [#252](https://github.com/nikhilsoman/synlynk/pull/252) | 2026-07-15 |
| [60](./60-pr256-measurement-ledger-phase2-agy-adapter.md) | Measurement Ledger Phase 2: The Agy (Gemini) Structured-Output Adapter | [#256](https://github.com/nikhilsoman/synlynk/pull/256) | 2026-07-15 |
| [100](./100-pr770-classifier-corroboration.md) | PR #770 — Teaching the Classifier to Check Its Work First | [#770](https://github.com/nikhilsoman/synlynk/pull/770) | 2026-08-07 |
| [61](./61-pr257-measurement-ledger-phase2-grok-adapter.md) | Measurement Ledger Phase 2: The Grok Structured-Output Adapter (and Closing Epic #210) | [#257](https://github.com/nikhilsoman/synlynk/pull/257) | 2026-07-15 |
| [62](./62-pr258-vizor-cost-flagging.md) | Closing Epic #210: Flagging Estimated vs. Actual Cost in the Vizor Effort & Cost Tab | [#258](https://github.com/nikhilsoman/synlynk/pull/258) | 2026-07-15 |
| [63](./63-pr259-status-rates-updated-at.md) | Closing v0.12.0: Surfacing rates_updated_at in synlynk status | [#259](https://github.com/nikhilsoman/synlynk/pull/259) | 2026-07-15 |
| **[64](./64-v012-measurement-and-reliability.md)** | **v0.12.0 — Measurement & Reliability (Named Release)** | [v0.12.0](https://github.com/nikhilsoman/synlynk/releases/tag/v0.12.0) | **2026-07-15** |
| [65](./65-whats-new-v012-getting-started.md) | What's New in v0.12.0 — And How to Get Started | — | 2026-07-15 |
| [66](./66-pr293-agent-quota-tracking-291.md) | PR #293 — agent_quotas finally gets real usage (#291) | [#293](https://github.com/nikhilsoman/synlynk/pull/293) | 2026-07-16 |
| [67](./67-pr292-fix-probe-model-version.md) | PR #292 — Fix Tier-2 Model Probe (#287) | [#292](https://github.com/nikhilsoman/synlynk/pull/292) | 2026-07-16 |
| [68](./68-pr328-live-command-selftest.md) | PR #328 — Live Command Selftest: Does synlynk Actually Work in a Real Repo? | [#328](https://github.com/nikhilsoman/synlynk/pull/328) | 2026-07-18 |
| [69](./69-pr-capability-sweep-taxonomy.md) | Capability Sweep + Industry Taxonomy — Calibrating Agents Against Real Skill Axes | TBD | 2026-07-19 |
| [70](./70-prTBD-gitattributes-project-docs-union.md) | PR #383 — .gitattributes union merge for project-docs churn | [#383](https://github.com/nikhilsoman/synlynk/pull/383) | 2026-07-19 |
| [71](./71-prTBD-gh-write-routing-and-review-discipline.md) | Docs — GitHub write routing (Grok only) + PR Review Discipline identity caveat | [#432](https://github.com/nikhilsoman/synlynk/pull/432) | 2026-07-21 |
| [72](./72-v013-discoverability-and-accounting.md) | v0.13.0 — Discoverability & Accounting | [#274–#440](https://github.com/nikhilsoman/synlynk/releases/tag/v0.13.0) | 2026-07-22 |
| [73](./73-pr463-dispatch-stacking-ground-truth-gate.md) | PR #463 — Dispatch Stacking + Ground-Truth Merge Gate | [#463](https://github.com/nikhilsoman/synlynk/pull/463) | 2026-07-23 |
| [74](./74-pr475-dispatch-base-branch-agy-warning.md) | PR #475 — Dynamic PR Base Resolution + Silent Agy No-Op Warning | [#475](https://github.com/nikhilsoman/synlynk/pull/475) | 2026-07-24 |
| [75](./75-pr479-agy-jetski-rca.md) | PR #479 — The Agy Jetski Investigation: An RCA With No Fix | [#479](https://github.com/nikhilsoman/synlynk/pull/479) | 2026-07-24 |
| [76](./76-pr476-brace-expansion-cve.md) | PR #476 — Closing Dependabot Alert #7: brace-expansion CVE-2026-13149 | [#476](https://github.com/nikhilsoman/synlynk/pull/476) | 2026-07-24 |
| [77](./77-pr517-per-role-github-identity.md) | PR #517 — Per-Role GitHub App Identity for Dispatched Agents (#423) | [#517](https://github.com/nikhilsoman/synlynk/pull/517) | 2026-07-25 |
| [78](./78-pr535-cross-process-token-redaction.md) | PR #535 — Cross-Process Token Redaction for GitHub App Installation Tokens (#524) | [#535](https://github.com/nikhilsoman/synlynk/pull/535) | 2026-07-25 |
| [79](./79-pr536-doctor-health-checks-wiring.md) | PR #536 — Wiring HEALTH_CHECKS Into the Real synlynk doctor CLI Path (#525) | [#536](https://github.com/nikhilsoman/synlynk/pull/536) | 2026-07-25 |
| [80](./80-pr542-state-engine-pr1-db-canonical.md) | PR #542 — State Engine PR1: DB-Canonical Roadmap, Memory, and Costs | [#542](https://github.com/nikhilsoman/synlynk/pull/542) | 2026-07-26 |
| [81](./81-pr549-live3-content-recovery-rca.md) | PR #549 — LIVE-3: Recovering What a Merge Conflict Actually Deleted | [#549](https://github.com/nikhilsoman/synlynk/pull/549) | 2026-07-26 |
| [82](./82-pr584-doctor-baseline-schema-parity.md) | PR #584 — #339: When "Green Across the Board" Meant the Checks Weren't Running | [#584](https://github.com/nikhilsoman/synlynk/pull/584) | 2026-07-29 |
| [83](./83-pr588-stale-sop-detection.md) | PR #588 — #583: Teaching synlynk to Notice Its Own Instructions Went Stale | [#588](https://github.com/nikhilsoman/synlynk/pull/588) | 2026-07-29 |
| [84](./84-pr589-codex-sandbox-flag-regression.md) | PR #589 — When #339's Own Fix Broke Every Codex Dispatch | [#589](https://github.com/nikhilsoman/synlynk/pull/589) | 2026-07-29 |
| [85](./85-pr591-stale-sop-newline-spacing.md) | PR #591 — The Blank Line That Broke a Markdown Header | [#591](https://github.com/nikhilsoman/synlynk/pull/591) | 2026-07-30 |
| [86](./86-pr592-claude-md-regeneration.md) | PR #592 — Finally, the CLAUDE.md Regeneration | [#592](https://github.com/nikhilsoman/synlynk/pull/592) | 2026-07-30 |
| [82](./82-pr587-harness-compatibility-capability-design.md) | PR #587 — Harness Compatibility & Capability: A Design Spec That Corrected Itself | [#587](https://github.com/nikhilsoman/synlynk/pull/587) | 2026-07-30 |
| [83](./83-prTBD-codex-approval-flag-correction.md) | PR #TBD — Codex Approval Flag Correction | TBD | 2026-07-30 |
| [84](./84-pr600-team-py-timeout-config.md) | PR #600 — Team Panel Queries Get Per-Agent Timeout Overrides | [#600](https://github.com/nikhilsoman/synlynk/pull/600) | 2026-07-30 |
| [84](./84-pr599-grok-flag-mapping.md) | PR #599 — Grok Flag Mapping: Real Permission Translation in `_permissions_to_flags` | [#599](https://github.com/nikhilsoman/synlynk/pull/599) | 2026-07-30 |
| [85](./85-pr599-grok-flag-mapping.md) | PR #599 — Grok Flag Mapping: Real Permission Translation in `_permissions_to_flags` | [#599](https://github.com/nikhilsoman/synlynk/pull/599) | 2026-07-30 |
| [86](./86-prTBD-remediation-audit-log.md) | PR #TBD — Phase 3: Remediation Audit Log | TBD | 2026-07-30 |
| [87](./87-pr606-scan-repo-requirements.md) | PR #606 — `_scan_repo_requirements`: Presence-Only Repo Requirement Discovery | [#606](https://github.com/nikhilsoman/synlynk/pull/606) | 2026-07-30 |
| [88](./88-prTBD-doctor-fix-agy.md) | PR #TBD — Phase 4: synlynk doctor --fix agy | TBD | 2026-07-30 |
| [89](./89-pr614-dispatch-preflight-gate.md) | PR #614 — Dispatch Preflight Capability Gate | [#614](https://github.com/nikhilsoman/synlynk/pull/614) | 2026-07-31 |
| [90](./90-pr587-capability-drift-regression-classification.md) | PR #587 — Harness Capability Drift & Regression Classification | [#587](https://github.com/nikhilsoman/synlynk/pull/587) | 2026-08-01 |
| [97](./97-pr697-local-agent-parity-config.md) | PR #697 — Starter-tier Guardrails & Local Agent A/B Test Harness | [#697](https://github.com/nikhilsoman/synlynk/pull/697) | 2026-08-03 |
| [98](./98-pr715-local-agent-ab-results.md) | PR #715 — Local Agent A/B Test Results | [#715](https://github.com/nikhilsoman/synlynk/pull/715) | 2026-08-03 |
| [99](./99-pr731-synlynk-ux-1.0-tui-vizor-uxcore.md) | PR #731 — Synlynk UX 1.0: TUI + Vizor on Shared uxcore | [#731](https://github.com/nikhilsoman/synlynk/pull/731) | 2026-08-05 |
| [100](./100-prTBD-receipt-protocol.md) | The Receipt Protocol — Detection-Only Delivery Confirmation for Dispatched Tasks | TBD | 2026-08-07 |
| [101](./101-pr762-windowed-sentinel-crit.md) | Windowed sentinel_crit — stop lifetime logs from keeping ops RED | [#762](https://github.com/nikhilsoman/synlynk/pull/762) | 2026-08-07 |
| [102](./102-pr772-jobs-reap.md) | jobs reap — kill zombie running rows | [#772](https://github.com/nikhilsoman/synlynk/pull/772) | 2026-08-07 |
| [103](./103-pr778-scope-violation-enforcement.md) | Scope Violation Enforcement — Making --scope-paths Mean Something | [#778](https://github.com/nikhilsoman/synlynk/pull/778) | 2026-08-08 |
| [104](./104-prTBD-safe-caller-construction.md) | Safe Caller Construction — Documenting the Path That Already Existed | [#783](https://github.com/nikhilsoman/synlynk/pull/783) | 2026-08-08 |
| [105](./105-pr816-quota-aware-dispatch-reservation.md) | PR #816 — Quota-Aware Dispatch Reservation | [#816](https://github.com/nikhilsoman/synlynk/pull/816) | 2026-08-08 |
| [106](./106-pr824-829-ux1.0-field-trial-readiness.md) | PRs #824–#830 — UX 1.0 Field Trial Readiness: From Shipped to Trusted | [#824](https://github.com/nikhilsoman/synlynk/pull/824), [#825](https://github.com/nikhilsoman/synlynk/pull/825), [#826](https://github.com/nikhilsoman/synlynk/pull/826), [#827](https://github.com/nikhilsoman/synlynk/pull/827), [#829](https://github.com/nikhilsoman/synlynk/pull/829), [#830](https://github.com/nikhilsoman/synlynk/pull/830) | 2026-08-08 |
| [107](./107-pr835-context-mode-telemetry.md) | Context-mode telemetry — measuring right-sized context | [#835](https://github.com/nikhilsoman/synlynk/pull/835) | 2026-08-09 |


| [108](./108-pr854-fresh-base-ref.md) | Fresh --base — stop dispatching against stale main | [#854](https://github.com/nikhilsoman/synlynk/pull/854) | 2026-08-09 |
| [109](./109-pr857-gh-write-fail-closed.md) | GH-write fail-closed — no silent personal keyring | [#857](https://github.com/nikhilsoman/synlynk/pull/857) | 2026-08-09 |
| [110](./110-pr867-daemon-jobs-gtv.md) | Daemon jobs GTV — Epic A1 status truth | [#867](https://github.com/nikhilsoman/synlynk/pull/867) | 2026-08-09 |
| [111](./111-pr868-cost-completeness.md) | Cost completeness — Epic A2 / #752 | [#868](https://github.com/nikhilsoman/synlynk/pull/868) | 2026-08-09 |
| [112](./112-pr874-cold-start-phase2-canon-baseline.md) | cold-start Phase 2 — The Canon Baseline | [#874](https://github.com/nikhilsoman/synlynk/pull/874) | 2026-08-09 |
| [113](./113-pr880-agent-vs-harness-terminology.md) | PR #880 — Agent vs Harness: Phase 0 of the Roles & Charters Roadmap | [#880](https://github.com/nikhilsoman/synlynk/pull/880) | 2026-08-10 |
| [114](./114-chore-identity-slug-override.md) | Untangling Repo Name from Product Name — the `identity_slug` override | TBD | 2026-08-12 |
| [115](./115-fix910-identity-init-resume-confirm.md) | Resume identity init at install confirmation instead of restarting | [#912](https://github.com/nikhilsoman/synlynk/pull/912) | 2026-08-12 |
| [115](./115-chore-governs-event-contract-extension.md) | GOVERNS Event-Contract Extension — Two New Event Types for the Autonomous Ops Release Gates | [#922](https://github.com/nikhilsoman/synlynk/pull/922) | 2026-08-13 |
| [116](./116-v0.13.1-operational-reliability-patch.md) | v0.13.1 — The Release That Stayed a Patch | TBD | 2026-08-13 |
| [117](./117-pr1003-agent-roles-phase1-cli.md) | PR #1003 — Agent-Roles-Charters Phase 1: Giving Workspace Agents a CLI | [#1003](https://github.com/nikhilsoman/synlynk/pull/1003) | 2026-08-16 |
| [118](./118-pr993-agent-harness-rename.md) | PR #993 — Freeing `agent` from `harness` | [#993](https://github.com/nikhilsoman/synlynk/pull/993) | 2026-08-16 |
| **[119](./119-v0.14.0-truth-and-identity.md)** | **v0.14.0 — Truth in the Pipe, Identity for the Agents (Named Release)** | [v0.14.0](https://github.com/nikhilsoman/synlynk/releases/tag/v0.14.0) | **2026-08-16** |
| [120](./120-pr1022-agent-roles-phase1-followups.md) | PR #1022 — Agent-Roles-Charters Phase 1 Follow-Ups: Closing the Footguns | [#1022](https://github.com/nikhilsoman/synlynk/pull/1022) | 2026-08-17 |
| [121](./121-pr1030-agent-roles-phase2-memory-gated-learning.md) | PR #1030 — Agent-Roles-Charters Phase 2: Making Capability Grants Mean Something | [#1030](https://github.com/nikhilsoman/synlynk/pull/1030) | 2026-08-18 |
| [122](./122-pr1074-1075-gh-write-reliability-and-broker-design.md) | PR #1074 / #1075 — GitHub-Write Reliability, and the Spec for the Next Step | [#1074](https://github.com/nikhilsoman/synlynk/pull/1074), [#1075](https://github.com/nikhilsoman/synlynk/pull/1075) | 2026-08-19 |
| [123](./123-pr1082-1089-qa-merge-gate-live5.md) | PRs #1082–#1089 — Shipping the QA Merge Gate, and the Bug It Found on the Way | [#1082](https://github.com/nikhilsoman/synlynk/pull/1082), [#1083](https://github.com/nikhilsoman/synlynk/pull/1083), [#1084](https://github.com/nikhilsoman/synlynk/pull/1084), [#1086](https://github.com/nikhilsoman/synlynk/pull/1086), [#1088](https://github.com/nikhilsoman/synlynk/pull/1088), [#1089](https://github.com/nikhilsoman/synlynk/pull/1089) | 2026-08-21/22 |
| [124](./124-pr1100-1101-qa-completion-tracker-and-merge-restricted-classes.md) | PRs #1100–#1101 — Completion Tracker + Merge-Restricted-Classes Gate Mode | [#1100](https://github.com/nikhilsoman/synlynk/pull/1100), [#1101](https://github.com/nikhilsoman/synlynk/pull/1101) | 2026-08-22 |
| [125](./125-pr1110-gh-write-identity-hardening.md) | PR #1110 — gh-write Identity Hardening: Phase 1 Closeout | [#1110](https://github.com/nikhilsoman/synlynk/pull/1110) | 2026-08-23 |
| **[126](./126-pr1122-v0.15.0-workspace-policy-layer.md)** | **v0.15.0 — The Workspace Policy Layer (Named Release)** | [#1122](https://github.com/nikhilsoman/synlynk/pull/1122) | **2026-08-23** |
| **[127](./127-pr1125-1127-v0.16.0-autonomous-loop.md)** | **v0.16.0 — The Autonomous Loop (Named Release)** | [#1125](https://github.com/nikhilsoman/synlynk/pull/1125), [#1127](https://github.com/nikhilsoman/synlynk/pull/1127) | **2026-08-23** |
| **[128](./128-pr1137-1151-v0.17.0-ticket-driven-approval-auto-resume.md)** | **v0.17.0 — Ticket-Driven Approval Auto-Resume (Named Release)** | [#1137](https://github.com/nikhilsoman/synlynk/pull/1137), [#1138](https://github.com/nikhilsoman/synlynk/pull/1138), [#1139](https://github.com/nikhilsoman/synlynk/pull/1139), [#1141](https://github.com/nikhilsoman/synlynk/pull/1141), [#1151](https://github.com/nikhilsoman/synlynk/pull/1151) | **2026-08-24** |
| **[129](./129-v0.18.0-dispatch-reliability-and-qa-merge-gate.md)** | **v0.18.0 — Dispatch Reliability & QA Merge-Gate Authority (Named Release)** | — | **2026-08-28** |
| [130](./130-pr1245-doctor-pr-review-cycles-check.md) | PR #1245 — Doctor Learns to Watch Its Own Reviewers | [#1245](https://github.com/nikhilsoman/synlynk/pull/1245) | 2026-08-29 |
| [131](./131-pr1239-multiauthor-book-part0-part1.md) | PR #1239 — The Book Gets Co-Authors: Part 0 + Part I, v0.3-DRAFT | [#1239](https://github.com/nikhilsoman/synlynk/pull/1239) | 2026-08-29 |
| [133](./133-prTBD-daemon-worktree-state-paths.md) | Daemon State Belongs to the Repository, Not the Worktree | TBD | 2026-08-29 |
| [134](./134-pr1271-codex-direct-gh-write-network-access.md) | PR #1271 — Direct Codex GitHub-Write Network Access via Config Override | [#1271](https://github.com/nikhilsoman/synlynk/pull/1271) | 2026-08-29 |
| [135](./135-pr1275-codex-full-harness-parity.md) | PR #1275 — Granting Codex Full Harness Parity Across Review and GitHub-Write Tasks | [#1275](https://github.com/nikhilsoman/synlynk/pull/1275) | 2026-08-30 |
| [136](./136-pr1279-grok-headless-permission-mode.md) | PR #1279 — Eliminating Grok Headless Execution Cancellation via --always-approve | [#1279](https://github.com/nikhilsoman/synlynk/pull/1279) | 2026-08-30 |
| [137](./137-pr1286-agy-headless-parity.md) | PR #1286 — Eliminating Agy Headless 5m Timeout, Enabling Plan Mode, and Capturing Prompt Cache Telemetry | [#1286](https://github.com/nikhilsoman/synlynk/pull/1286) | 2026-08-30 |
| [138](./138-pr1288-claude-harness-alignment.md) | PR #1288 — Aligning Claude Baseline Roles with PM/Deploy Governance | [#1288](https://github.com/nikhilsoman/synlynk/pull/1288) | 2026-08-30 |
| [139](./139-pr1282-daemon-reexec-fork-safety.md) | PR #1282 — Eliminating Daemon Re-Exec Fork Desync via Fork Safety | [#1282](https://github.com/nikhilsoman/synlynk/pull/1282) | 2026-08-30 |
| [140](./140-pr1306-harness-vs-workspace-agent-separation.md) | PR #1306 — Standardizing Harness vs. Workspace Agent Separation Across CLI Flags, Configs, and Docs | [#1306](https://github.com/nikhilsoman/synlynk/pull/1306) | 2026-08-30 |
| [141](./141-pr1308-grok-codex-cwd-protection.md) | PR #1308 — Fleet Parity: Enforce --cwd for Grok and -C for Codex with Working-Directory Protection | [#1308](https://github.com/nikhilsoman/synlynk/pull/1308) | 2026-08-30 |
| [142](./142-pr1309-instruction-file-preflight-and-receipt-verification.md) | PR #1309 — Fleet Parity: Instruction File Preflight Check and Closed-Loop Receipt Verification | [#1309](https://github.com/nikhilsoman/synlynk/pull/1309) | 2026-08-30 |
| [143](./143-pr1310-agy-stitch-mcp-integration.md) | PR #1310 — Fleet Parity: Agy Stitch MCP Integration, Diagnostics, and Prompt Guidance | [#1310](https://github.com/nikhilsoman/synlynk/pull/1310) | 2026-08-31 |
| [144](./144-pr1318-harden-harness-instructions-todo-state-db.md) | PR #1318 — Hardening: Prohibit Direct todo.md Hand-Edits Across Harness Instruction Templates | [#1318](https://github.com/nikhilsoman/synlynk/pull/1318) | 2026-09-01 |
| [150](./150-pr1303-qa-app-administration-permission.md) | PR #1303 — Grant Administration:Write Permission to Merge Roles in GitHub App Manifests | [#1303](https://github.com/nikhilsoman/synlynk/pull/1303) | 2026-09-01 |
| [151](./151-pr1319-readme-sync-test-synthetic-fixture.md) | PR #1319 — Decouple README Sync Validator Unit Tests from Live Repo Root | [#1319](https://github.com/nikhilsoman/synlynk/pull/1319) | 2026-09-01 |
| [152](./152-pr1320-dispatch-gh-write-false-positives.md) | PR #1320 — Tighten _task_requires_gh_write() Auto-Detection Heuristic | [#1320](https://github.com/nikhilsoman/synlynk/pull/1320) | 2026-09-01 |
| [153](./153-pr1321-roles-fix-repairs-sops.md) | PR #1321 — Repair Stale & Missing SOP Sections during synlynk roles --fix | [#1321](https://github.com/nikhilsoman/synlynk/pull/1321) | 2026-09-01 |
| [154](./154-pr1322-fix-blog-post-103-frontmatter.md) | PR #1322 — Fix YAML Frontmatter in Blog Post 103 | [#1322](https://github.com/nikhilsoman/synlynk/pull/1322) | 2026-09-02 |

## Per-PR Post Template

From here forward, each PR gets a post following this structure:

```markdown
---
title: "PR #N — <theme>"
date: YYYY-MM-DD
series: "Building the OS for Multi-Agent Development"
post: N
pr: "#N"
merged: YYYY-MM-DD (or status: open)
---

## The Broader Goal at the End of the Previous PR
[What was the stated/understood goal before this work started?]

## Strategic Shifts in This PR (if any)
[What changed in the broader strategy? What moved the goalpost and why?]

## What This PR Shipped
[Deep technical description: commands, key implementation decisions, data structures, test approach]

## Brainstorm Visuals Used
[Links to any HTML brainstorm files in docs/brainstorm/ that informed decisions in this PR]

## What This Achieved on the Path to Autonomy
[Specific ways this PR advances the eventual goal of autonomous multi-agent dispatch]

## Strategic Note: The Goal at the End of This PR
[The new goalpost, as understood after this PR's decisions]
```

## Related Docs

- Brainstorm visuals: `../brainstorm/`
- Design specs: `../superpowers/specs/`
- Gap analysis: `../superpowers/2026-06-07-arc-gap-analysis.md`
- Unified roadmap: `../superpowers/specs/2026-06-06-synlynk-unified-roadmap.md`
