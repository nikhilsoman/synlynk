# Project Costs Tracking

> All entries marked `~` are estimates. Verify actuals at claude.ai/settings/usage.  
> Pricing: Sonnet 4.6 — cache $0.30/MTok · input $3.00/MTok · output $15.00/MTok  
> Token split assumption: cache_read 40% · input 40% · output 20%

## Running Estimate

| Tier | Sessions | Est. Cost Each | Subtotal |
| :--- | :--- | :--- | :--- |
| Light (~50K tokens) | 10 | ~$0.25–0.50 | ~$3.50 |
| Medium (~150K tokens) | 12 | ~$0.65–1.50 | ~$12.00 |
| Heavy (~400K tokens) | 8 | ~$1.75–3.00 | ~$18.00 |
| Very Heavy / Subagent (~800K tokens) | 7 | ~$3.50–6.00 | ~$28.00 |
| **Total** | **37** | | **~$61.50** |

---

## Session Log

| Date | User | Requests | Tokens (~In / ~Out) | Est. Cost (USD) | Summary |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 2026-05-16 | nikhil | ~40 | ~80K / ~40K | ~$1.80 | Product definition brainstorm · brand identity · v1.2.0-lite bootstrap (init, exec, upgrade, install, telemetry, flatline, token extraction, budget alerts) |
| 2026-05-17 | nikhil | ~60 | ~120K / ~60K | ~$2.70 | v0.2.0 redesign (WatchDaemon, checkpoint, status, context compaction) · lite tier + website design specs · v0.2.1 correctness patch (TDD, 47 tests, PR #3) |
| 2026-05-18 | nikhil | ~8 | ~15K / ~8K | ~$0.17 | Codex integration planning + roadmap docs |
| 2026-05-20 | nikhil | ~10 | ~20K / ~10K | ~$0.22 | GitHub username + upgrade check fix (PR #23) · v0.2.2 version bump (PR #24) |
| 2026-05-23 | nikhil | ~25 | ~50K / ~25K | ~$0.52 | 11ty landing page + build log · site workflow + package-lock |
| 2026-05-30 | nikhil | ~8 | ~15K / ~8K | ~$0.17 | rxcc WoW observations + cross-repo standards distribution proposal |
| 2026-06-01 | nikhil | ~30 | ~80K / ~35K | ~$1.30 | Trio Protocol rearchitecture brainstorm · visual companion · spec committed |
| 2026-06-03 | nikhil | ~50 | ~120K / ~55K | ~$2.18 | v0.3.0 multi-agent foundation (PR #26 merged) · v1.0 architecture brainstorm · brainstorm visuals saved |
| 2026-06-06 | nikhil | ~60 | ~160K / ~70K | ~$3.10 | Unified Roadmap brainstorm (full day) · competitive positioning · Tokq convergence · release staircase · 5 Tokq PRD gaps closed · 6 visual companion files |
| 2026-06-07a | nikhil | ~35 | ~90K / ~40K | ~$1.63 | State DB + Agentic PM design brainstorm · schema verified · spec committed |
| 2026-06-07b | nikhil | ~35 | ~90K / ~40K | ~$1.63 | Agent identity, dispatch, entitlements brainstorm · 4 dispatch modes · Ed25519 pulled forward · gap analysis |
| 2026-06-07c | nikhil | ~25 | ~60K / ~28K | ~$1.10 | Workspace + multi-repo design brainstorm · event-log sync · cross-repo epics · spec + PR #28 |
| 2026-06-10 | nikhil | ~100 | ~250K / ~120K | ~$5.55 | v0.3.1 Sentinel + Observability (9 features, 40 new tests, PR #29) · E2E test suite (17 tests, PR #30) · first full subagent-driven session |
| 2026-06-14a | nikhil | ~30 | ~80K / ~35K | ~$1.46 | v0.6.0 Job Control R2 critical bug fix + merge (PR #42) · Quick Start Guide v0.6.0 PDF |
| 2026-06-14b | nikhil | ~120 | ~320K / ~150K | ~$6.71 | v0.4.0 Hybrid Workgroup Bootstrap · 14 tasks subagent-driven · 183 tests · Tokq memory unit schema fix (PR #37) |
| 2026-06-17a | nikhil | ~110 | ~300K / ~140K | ~$6.10 | v0.4.1 Instruction Reach · 10 tasks subagent-driven · section marker system · SHA manifest · DB_PATH fix · 265 tests (PR #45) |
| 2026-06-17b | nikhil | ~20 | ~40K / ~18K | ~$0.78 | Quick Start Guide v0.4.1 PDF · v0.4.2 Task Status Model (7 new tests, PR #46) · v0.6.1 version sync fix (PR #47) |
| 2026-06-20 | nikhil | ~90 | ~240K / ~110K | ~$5.17 | v0.7.0 Static Scan Quality · language-agnostic scanner · 65 new tests · GitHub release · PR #49 |
| 2026-06-21a | nikhil | ~35 | ~90K / ~40K | ~$1.63 | Roadmap realignment brainstorm · community layer · agent archetypes · relay VPS deep-dive |
| 2026-06-21b | nikhil | ~120 | ~320K / ~150K | ~$6.71 | v0.8.0 Support Engineer Agent · 5 signal collectors · cron install · GH issue filing · fix PRs · PR #52 |
| 2026-06-21c | nikhil | ~110 | ~300K / ~140K | ~$6.10 | v0.9.0 Kernel Fixes · hybrid dispatch 7 tasks (Claude+AGY+Codex) · scoped context · Ed25519 · anti-gaming cap · package split · PR #53 |
| 2026-06-21d | nikhil | ~25 | ~60K / ~28K | ~$1.10 | Post-v0.9.0 hotfixes · install hardening · configurable docs dir · init doc migration |
| 2026-06-22a | nikhil | ~20 | ~50K / ~22K | ~$0.97 | Invisible-state spec brainstorm · Quick Start Guide v0.9.1 regeneration |
| 2026-06-22b | nikhil | ~55 | ~140K / ~65K | ~$2.82 | v0.9.2 design spec + implementation plan · Wave 1 dispatch (T1–T3) + merges |
| 2026-06-22c | nikhil | ~60 | ~160K / ~75K | ~$3.38 | Wave 2 dispatch (T4–T6) + merges · Release Agent brainstorm + spec · v0.9.2 shipped |
| 2026-06-23 | nikhil | ~65 | ~170K / ~80K | ~$3.60 | TPM Agent brainstorm + spec · lifecycle-as-first-class-entity model · agent design principles · v0.8.x epic regrouped · brainstorm visuals saved |
