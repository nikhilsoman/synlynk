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
| [60](./60-prTBD-measurement-ledger-phase2-agy-adapter.md) | Measurement Ledger Phase 2: The Agy (Gemini) Structured-Output Adapter | TBD | 2026-07-15 |


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
