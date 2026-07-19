# Project Costs Tracking

> All entries marked `~` are estimates. Verify actuals at claude.ai/settings/usage.  
> Pricing: Sonnet 4.6 — cache $0.30/MTok · input $3.00/MTok · output $15.00/MTok  
> Token split assumption: cache_read 40% · input 40% · output 20%
> Payment-mode-aware accounting (`payment_mode` / `actual_usd`) begins 2026-07-19. Earlier entries predate this and are not directly comparable.

## Running Estimate

| Tier | Sessions | Est. Cost Each | Subtotal |
| :--- | :--- | :--- | :--- |
| Light (~50K tokens) | 10 | ~$0.25–0.50 | ~$3.50 |
| Medium (~150K tokens) | 13 | ~$0.65–1.75 | ~$13.73 |
| Heavy (~400K tokens) | 9 | ~$1.75–3.00 | ~$20.25 |
| Very Heavy / Subagent (~800K tokens) | 8 | ~$3.50–6.00 | ~$31.50 |
| **Total** | **41** | | **~$68.98** |

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
| 2026-06-28 | agy | ~1 | ~50K / ~5K | ~$0.25 | BS-5 website redesign (Phase 2): tagline hero, relief, how it works, feature spotlight templates, macros, and CSS design system |
| 2026-06-28 | agy | ~10 | ~15K / ~2K | ~$0.08 | BS-5 docs sidebar scroll-spy implementation with IntersectionObserver |

| 2026-06-30 | nikhil | ~10 | ~30K / ~15K | ~$0.50 | Implement story-bs14-sentinel-stall (per-job stall check inside _reconcile_jobs with config default) and added TDD test |
| 2026-07-01 | nikhil | ~150 | ~320K / ~160K | ~$3.90 | BS-17 final merge (PR #89) + BS-18 full cycle: brainstorm → spec → plan → 4 agent waves (Codex T1-T7, Grok T5-T6, Agy T8) → PR #90 merged; 616 tests; state.db source of truth shipped |
| 2026-07-04/05 | nikhil | ~200 | ~200K / ~90K | ~$4.00 | TC-2 preflight fix arc (PRs #114–116): logs summary, zombie recon, flag baseline correction, _run_tc2 root-cause fix, 837 tests · BS-13 Live Job Observatory (PR #117): observatory.py, watch --live panel, viz Observatory tab, Agy R1+R2 reviews · blog posts 42–45 with brainstorm screenshots · 11 agent dispatches (Agy ×8, Grok ×3, Codex ×1) |
| 2026-07-11 | nikhil | ~180 | ~250K / ~110K | ~$4.50 | Epic #137 close-out: fleet dispatch scheduler design + 8-task plan authored, dispatched to Grok, diff+test review, PR #156 merged (scheduler.py, story ready/draft gate, batch headroom accounting) · PR #157 (roadmap update + deferred v2 goal `goal-d38e3c83`) merged · blog post 52 · devlog + memory housekeeping |
| 2026-07-11/12 | nikhil | ~150 | ~230K / ~100K | ~$4.10 | Dispatch-reliability triage: #160/#161/#162 filed from rxcc handoff note, each through full brainstorm→spec→plan→dispatch→verify→merge cycle · PR #163 (Codex worktree --add-dir fix), PR #164 (dispatch --help agent list derived from AGENT_CAPABILITY_BASELINES), PR #165 (HARNESS_TIMEOUT_PATTERNS + mtime-based `_check_job_stall`) all merged · scheduled a one-shot CronCreate dispatch · live-caught #162's own bug during its fix's dispatch job (Codex died at ~500s pre-commit) and recovered the work manually · PR #166 devlog+memory housekeeping merged |
| 2026-07-15 13:39 | codex | 1 | 5000/2000 | [est] $0.0450 | exec: codex job job-52aea3... |
| 2026-07-15 13:39 | agy | 1 | 5000/2000 | [est] $0.0450 | exec: agy job job-ca4f171c |
| 2026-07-15 15:04 | codex | 1 | 5000/2000 | [est] $0.0450 | exec: codex job job-3c6aeb... |
| 2026-07-15 15:04 | agy | 1 | 5000/2000 | [est] $0.0450 | exec: agy job job-837c036c |
| 2026-07-15 15:07 | codex | 1 | 751784/8342 | [est] $2.3805 | exec: codex job job-48d58a... |
| 2026-07-15 | nikhil | ~90 | ~90K / ~20K | ~$0.57 | Issue #259: brainstorm+design spec (rates_updated_at surfacing), implementation plan authoring, self-review, independent diff+test verification of dispatched Task 1 (Codex job-48d58abb), full-suite regression pass, blog post 63 |
| 2026-07-15 | nikhil | ~40 | ~110K / ~35K | ~$0.86 | v0.12.0 release prep: PR #267 CI verify + merge, roadmap-shipped memory sync, gh-authoritative audit of 71 PRs merged since v0.11.0 (`gh pr list`, caught merge-commit PRs a commit-subject grep missed), VERSION bump 0.11.0→0.12.0, full CHANGELOG [0.12.0] entry rewrite (5 epics, dedup of old detail blocks), full-suite regression pass (1140 passed/2 skipped), release blog post 64 |
| 2026-07-15 19:32 | agy | 1 | 453303/32863 | [est] $1.8529 | exec: agy job job-a1ef0192 |
| 2026-07-15 19:32 | grok | 1 | 48960/8627 | [est] $0.2763 | exec: grok job job-dbfc48c... |
| 2026-07-15 19:32 | agy | 1 | 242381/18525 | [est] $1.0050 | exec: agy job job-0b627f6f |
| 2026-07-15 19:50 | codex | 1 | 6223528/119074 | [est] $20.4567 | exec: codex job job-f9804c... |
| 2026-07-15 20:01 | grok | 1 | 81218/27634 | [est] $0.6582 | exec: grok job job-2327f65... |
| 2026-07-17 09:17 | codex | 1 | 3916492/33996 | [est?] $12.2594 | exec: codex job job-d63c4c... |
| 2026-07-17 11:40 | codex | 1 | 1709555/41215 | [est] $5.7469 | exec: codex job job-5164f9... |
| 2026-07-17 11:40 | codex | 1 | 451445/4976 | [est] $1.4290 | exec: codex job job-05915c... |
| 2026-07-17 11:40 | codex | 1 | 3293151/46046 | [est?] $10.5701 | exec: codex job job-b2a31b... |
| 2026-07-17 13:56 | codex | 1 | 5000/2000 | [est] $0.0450 | exec: codex job job-096098... |
| 2026-07-17 13:56 | codex | 1 | 791808/32623 | [est] $2.8648 | exec: codex job job-94c25e... |
| 2026-07-17 14:04 | codex | 1 | 477401/7643 | [est] $1.5468 | exec: codex job job-b693c4... |
| 2026-07-17 14:11 | codex | 1 | 881861/17042 | [est] $2.9012 | exec: codex job job-dc844b... |
| 2026-07-17 14:30 | codex | 1 | 3615064/41038 | [est?] $11.4608 | exec: codex job job-616098... |
| 2026-07-17 14:42 | codex | 1 | 2338749/31865 | [est?] $7.4942 | exec: codex job job-ede207... |
| 2026-07-17 14:56 | codex | 1 | 3377411/26123 | [est?] $10.5241 | exec: codex job job-453760... |
| 2026-07-17 15:14 | codex | 1 | 1401974/46797 | [est] $4.9079 | exec: codex job job-6edba9... |
| 2026-07-17 15:28 | codex | 1 | 557675/11916 | [est] $1.8518 | exec: codex job job-d0919d... |
| 2026-07-17 15:47 | codex | 1 | 1686766/23007 | [est] $5.4054 | exec: codex job job-69b29d... |
| 2026-07-17 | nikhil | ~130 | ~160K / ~80K | ~$1.73 | PM session: reviewed+merged PR #305, executed Tasks 2-6 of dispatch-job-comms-fence plan end-to-end — per-task dispatch/verify/merge loop (PRs #309-#313), caught+fixed Task 3's inverted context_mode bug and Task 4's unauthorized fencing.py rewrite via redispatch, caught+fixed Task 5's duplicate-cost-display defect via direct inline patch to the open PR branch, full-suite verification before every merge, roadmap+devlog housekeeping (PR #314), memory sync |
| 2026-07-17 17:14 | codex | 1 | 1488238/16240 | [est] $4.7083 | exec: codex job job-ddb9d1... |
| 2026-07-19 11:16 | grok | 1 | 72117/23525 | [est] $0.5692 | $0.5692 | exec: grok job job-1005b68... |
| 2026-07-19 02:20 | grok | 1 | 78592/12807 | [est] $0.4279 | exec: grok job job-894b141... |
| 2026-07-19 08:37 | grok | 1 | 95674/18168 | [est] $0.5595 | exec: grok job job-b0f6351... |
| 2026-07-19 18:19 | grok | 1 | 55108/13337 | [est] $0.3654 | exec: grok job job-ba37d19... |
| 2026-07-19 18:29 | codex | 1 | 1755379/33297 | [est] $5.7656 | exec: codex job job-23ae07... |
| 2026-07-19 18:39 | codex | 1 | 5016184/63676 | [est] $16.0037 | exec: codex job job-232f8c... |
| 2026-07-19 18:39 | codex | 1 | 5244012/82989 | [est] $16.9769 | exec: codex job job-28a513... |
| 2026-07-19 18:39 | grok | 1 | 79832/4971 | [est] $0.3141 | exec: grok job job-c665401... |
| 2026-07-19 18:39 | agy | 1 | 126462/6242 | [est] $0.4730 | exec: agy job job-a59f065a |
| 2026-07-19 18:39 | grok | 1 | 30890/5376 | [est] $0.1733 | exec: grok job job-ff55de1... |
| 2026-07-19 18:45 | grok | 1 | 40541/4716 | [est] $0.1924 | exec: grok job job-84c70ec... |
| 2026-07-19 19:13 | codex | 1 | 2397650/42480 | [est] $7.8302 | exec: codex job job-366142... |
| 2026-07-19 19:13 | codex | 1 | 4380755/40964 | [est] $13.7567 | exec: codex job job-50f26b... |
| 2026-07-19 19:26 | grok | 1 | 52379/6581 | [est] $0.2559 | exec: grok job job-0a06859... |
| 2026-07-19 19:26 | grok | 1 | 53394/5232 | [est] $0.2387 | exec: grok job job-c5cd905... |
| 2026-07-19 20:08 | codex | 1 | 1841654/29189 | [est] $5.9628 | exec: codex job job-251378... |
| 2026-07-19 20:08 | grok | 1 | 72083/3862 | [est] $0.2742 | exec: grok job job-9ef770b... |
| 2026-07-19 20:31 | codex | 1 | 708744/11516 | [est] $2.2990 | $2.2990 | exec: codex job job-953ae0... |
| 2026-07-19 20:43 | grok | 1 | 42612/5379 | [est] $0.2085 | $0.2085 | exec: grok job job-28e71a3... |
| 2026-07-19 20:54 | codex | 1 | 618322/17188 | [est] $2.1128 | $2.1128 | exec: codex job job-f94bf1... |
| 2026-07-19 21:00 | grok | 1 | 26746/4155 | [est] $0.1426 | $0.1426 | exec: grok job job-1837111... |
