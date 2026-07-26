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
| 2026-07-19 21:52 | grok | 1 | 80193/25883 | [est] $0.6288 | exec: grok job job-9c2473b... |
| 2026-07-19 22:21 | codex | 1 | 12708919/90366 | [est] $39.4822 | exec: codex job job-cd3f72... |
| 2026-07-20 23:07 | grok | 1 | 41391/5102 | [est] $0.2007 | $0.2007 | exec: grok job job-8f6c042... |
| 2026-07-20 23:07 | agy | 1 | 33930/1252 | [est] $0.1206 | $0.1206 | exec: agy job job-030a7340 |
| 2026-07-20 23:07 | agy | 1 | 119321/3948 | [est] $0.4172 | $0.4172 | exec: agy job job-7e4081ad |
| 2026-07-20 23:07 | agy | 1 | 48608/1846 | [est] $0.1735 | $0.1735 | exec: agy job job-92b80d27 |
| 2026-07-20 23:07 | codex | 1 | 536934/13417 | [est] $1.8121 | $1.8121 | exec: codex job job-cb0cab... |
| 2026-07-20 23:07 | grok | 1 | 26507/3260 | [est] $0.1284 | $0.1284 | exec: grok job job-1b952a5... |
| 2026-07-20 23:07 | codex | 1 | 692276/6073 | [est] $2.1679 | $2.1679 | exec: codex job job-8383ca... |
| 2026-07-18 | nikhil | ~8 | ~67K/~3.2K | ~$0.25 | PM session: `synlynk decide` panel consult (codex+agy+grok) on pre-dogfooding-week blocking/non-blocking triage — re-logged after this row was lost to an unstashed `git reset --hard` on main; estimate covers both the intended run and an accidental double-run (background timeout mishap caused the panel to fire twice, 8 real agent CLI calls total, only one decision record survived on disk since both runs shared an identical filename slug) — see #346 (decide has no budget guard/dedup) |
| 2026-07-19 10:07 | codex | 1 | 7832814/86435 | [est] $24.7950 | exec: codex job job-72eb95... |
| 2026-07-19 10:37 | codex | 1 | 1070384/19458 | [est] $3.5030 | exec: codex job job-871b84... |
| 2026-07-20 01:22 | grok | 1 | 5000/2000 | [est] $0.0450 | exec: grok job job-c1dfaef... |
| 2026-07-20 01:24 | agy | 1 | 428404/37150 | [est] $1.8425 | exec: agy job job-a338459e |
| 2026-07-20 07:49 | agy | 1 | 200437/10404 | [est] $0.7574 | exec: agy job job-ce511d78 |
| 2026-07-20 21:35 | codex | 1 | 1257739/16128 | [est] $4.0151 | exec: codex job job-0a193c... |
| 2026-07-20 21:35 | agy | 1 | 81505/1349 | [est] $0.2647 | exec: agy job job-4cb54c47 |
| 2026-07-20 21:40 | grok | 1 | 36218/5785 | [est] $0.1954 | exec: grok job job-3b38792... |
| 2026-07-22 09:11 | grok | 1 | 39030/4746 | [est] $0.1883 | exec: grok job job-d1fe5a3... |
| 2026-07-22 09:12 | grok | 1 | 70431/7752 | [est] $0.3276 | exec: grok job job-f312219... |
| 2026-07-25 09:49 | agy | 1 | 5000/1500 | [est] $0.0375 | backfill: jetski repro test #1 (grant-based flag, job-960141f6) — success, no jetski repro |
| 2026-07-25 09:49 | agy | 1 | 5000/1500 | [est] $0.0375 | backfill: jetski repro test #2 (grant-based flag, settings.json removed, job-8bdc9484) — success, no jetski repro |
| 2026-07-25 09:49 | agy | 1 | 6000/1800 | [est] $0.0450 | backfill: jetski repro test #3 (harness_overrides matching rxcc config, job-9d04920e) — success, no jetski repro |
| 2026-07-25 09:49 | agy | 1 | 4000/500 | [est] $0.0195 | backfill: jetski repro test #4 attempt (forced command-tool use, job-f570bc1a) — failed on transient network error, inconclusive, retried |
| 2026-07-25 09:49 | agy | 1 | 6000/2000 | [est] $0.0480 | backfill: jetski repro test #4 retry (forced command-tool use, job-26c14922) — success, no jetski repro |
| 2026-07-25 09:49 | codex | 1 | 8000/1500 | [est] $0.0465 | backfill: PR check job-7edd3a56 — wrong-syntax instruction (pr check <N> invalid), redispatched |
| 2026-07-25 09:49 | codex | 1 | 10000/2000 | [est] $0.0600 | backfill: PR #479 check (job-452cb8a3) — sandbox DB-open limitation, ground-truthed clean outside sandbox |
| 2026-07-25 09:49 | codex | 1 | 10000/2000 | [est] $0.0600 | backfill: PR #476 check (job-06b9635a) — sandbox DB-open limitation, ground-truthed clean outside sandbox |
| 2026-07-25 09:49 | claude | 1 | 45000/12000 | [est] $0.3150 | backfill: PM-level native work — agy jetski investigation repro design/analysis, RCA doc write-up, PR #479/#476 review+merge coordination — not captured by dispatch telemetry |
| 2026-07-22 12:52 | grok | 1 | 5000/2000 | [est] $0.0450 | $0.0450 | exec: grok job job-1e5fbdb... |
| 2026-07-22 13:38 | codex | 1 | 5550187/63256 | [est?] $17.5994 | $17.5994 | exec: codex job job-2d1027... |
| 2026-07-22 15:20 | grok | 1 | 124997/19183 | [est] $0.6627 | $0.6627 | exec: grok job job-c5a2c5c... |
| 2026-07-22 17:37 | codex | 1 | 31498355/124793 | [est?] $96.3670 | $96.3670 | exec: codex job job-b87c2d... |
| 2026-07-22 17:53 | grok | 1 | 59182/7035 | [est] $0.2831 | $0.2831 | exec: grok job job-c8de7fd... |
| 2026-07-24 18:50 | codex | 1 | 5000/2000 | [est] $0.0450 | $0.0450 | exec: codex job job-a839d1... |
| 2026-07-24 18:50 | codex | 1 | 5000/2000 | [est] $0.0450 | $0.0450 | exec: codex job job-b6bbeb... |
| 2026-07-25 19:19 | codex | 1 | 2067044/18542 | [est?] $6.4793 | $6.4793 | exec: codex job job-e88634... |
| 2026-07-25 19:19 | grok | 1 | 29280/1169 | [est] $0.1054 | $0.1054 | exec: grok job job-6eaeee0... |
| 2026-07-25 19:19 | grok | 1 | 29196/2714 | [est] $0.1283 | $0.1283 | exec: grok job job-d094d99... |
| 2026-07-25 20:54 | grok | 1 | 29624/1368 | [est] $0.1094 | $0.1094 | exec: grok job job-531e56b... |
| 2026-07-25 20:54 | codex | 1 | 5000/2000 | [est] $0.0450 | $0.0450 | exec: codex job job-455be5... |
| 2026-07-25 20:54 | claude | 1 | 5000/2000 | [est] $0.0450 | $0.0450 | exec: claude job job-7bbcb... |
| 2026-07-25 20:54 | grok | 1 | 100004/30608 | [est] $0.7591 | $0.7591 | exec: grok job job-1e212ed... |
| 2026-07-25 20:54 | grok | 1 | 30703/3220 | [est] $0.1404 | $0.1404 | exec: grok job job-778e4be... |
| 2026-07-25 20:54 | grok | 1 | 25873/1085 | [est] $0.0939 | $0.0939 | exec: grok job job-4de3341... |
| 2026-07-25 20:59 | codex | 1 | 1132572/9837 | [est] $3.5453 | $3.5453 | exec: codex job job-64eed1... |
| 2026-07-25 21:04 | grok | 1 | 25369/1777 | [est] $0.1028 | $0.1028 | exec: grok job job-bfb205a... |
| 2026-07-25 21:21 | codex | 1 | 2211598/18958 | [est?] $6.9192 | $6.9192 | exec: codex job job-c051d1... |
| 2026-07-25 21:29 | codex | 1 | 929727/6071 | [est] $2.8802 | $2.8802 | exec: codex job job-0f9a4b... |
| 2026-07-25 21:22 | codex | 1 | 3732215/41679 | [est?] $2.99 | $2.99 | exec: codex job job-6bd241... (backfill: completion only surfaced via `synlynk jobs`, not a live dispatch print — see [[feedback: cost-capture auto-gap]]) |
| 2026-07-25 21:32 | grok | 1 | 39237/3511 | [est] $0.17 | $0.17 | exec: grok job job-554610... (backfill: nested worktree job, not visible to top-level `synlynk logs`/auto-capture) |
| 2026-07-25 21:49 | codex | 1 | 796237/7141 | [est] $2.4958 | $2.4958 | exec: codex job job-d05571... |
| 2026-07-25 21:52 | grok | 1 | 29686/4052 | [est] $0.1498 | $0.1498 | exec: grok job job-77bca9b... |
| 2026-07-25 23:16 | codex | 1 | 4305991/34681 | [est?] $13.4382 | $13.4382 | exec: codex job job-faf642... |
| 2026-07-25 23:42 | codex | 1 | 637615/13477 | [est?] $2.1150 | $2.1150 | exec: codex job job-b5df15ce (#530 .gitignore fix impl; committed locally, could not push — no GitHub egress in sandbox; formula-estimated, no total_cost_usd in log) |
| 2026-07-25 23:53 | grok | 1 | 31016/2555 | [est] $0.1314 | $0.1314 | exec: grok job job-e6a66ce6 (#530 push + PR #533 open) |
| 2026-07-26 00:05 | agy | 1 | 92089/8934 | [est] $0.4103 | $0.4103 | exec: agy job job-0d3b2b0f (PR #533 non-authoring review, COMMENT approve checklist) |
| 2026-07-26 00:17 | grok | 1 | 27667/1211 | [est] $0.1012 | $0.1012 | exec: grok job job-da38baad (PR #533 merge, SHA 8804111b; completion never auto-surfaced — worktree removed before a later dispatch could reprint it) |
