
## 2026-07-03
### Shipped
- brainstorm(BS-21): Vizor — browser-based local workspace dashboard; 5 iterations of Gantt visual companion (v1–v5), 2 tube map variants [ux]
- design: Vizor Gantt v5 locked — stage zoom drill-down, SVG pencil note icons (5 states), right-aligned task names in accordion rows, light/dark/system theming, agent avatars on stage bars [ux]
- docs: brainstorm HTML files committed to `docs/brainstorm/bs21-vizor/` [docs]
- spec: BS-21 Vizor design spec written (`docs/superpowers/specs/2026-07-03-bs21-vizor-design.md`) [docs]
- plan: BS-21 implementation plan written (T1-T12, 12 tasks across Codex/Agy/Grok) [docs]
- feat(BS-21): `synlynk viz` command — CLI scaffold, FTUE, VizorHandler, `--serve/--generate/--open/--stop` flags [cli]
- feat(BS-21): `generate_viz_data()` — reads `state.db` (roadmap_arcs, roadmap_phases, stories, cost_entries) + telemetry.json + sentinel.md + viz-notes.json into unified data dict [cli]
- feat(BS-21): 6 HTML generators — index/shell (left nav, iframe), Gantt (v5 port, accordion drill-down, stage bars, note modal), Architect Map (tube map SVG / setup prompt), User Journeys (split-pane), Effort & Cost (SVG bar charts), Efficiency (agent cards, sentinel timeline, recent runs) [cli]
- feat(BS-21): note system — `POST /note` → `viz-notes.json` → injected into `generate_context()` for bidirectional visual→AI annotation loop [cli]
- feat(BS-21): live JS polling every 60s + browser reload banner + Web Notifications on manifest change [cli]
- fix(BS-21): agent inflation (stories.phase values leaking as agent names) — tightened filter to known agents only [cli]
- fix(BS-21): missing page headers on Journeys + Effort views [ux]
- test: 21 tests across `test_viz.py` + `test_viz_serve.py` [test]
- docs(blog): post 39 — BS-21 Vizor [blog]
- **PR #101 merged · `synlynk viz` live on main** [release]
- docs: roadmap updated — BS-21 ✅ Shipped, BS-6 superseded [roadmap]

### Agents used
- Claude: PM, brainstorm (all 5 Gantt + 2 tube map iterations), spec, plan, visual review, fixes
- Codex: T1 scaffold, T2 data extraction, T3 shell (fallback), T4 Gantt (fallback), T7 effort, T8 efficiency, T9 note context injection, T10 live JS, T11 integration tests, T12 blog post
- Agy: T5 tube map (+ bundled T6 journeys)

## 2026-07-01
### Shipped
- feat(BS-17): `synlynk scan` + `synlynk init --wizard` FTUE onboarding — PR #89 merged [cli]
- feat(BS-18): `synlynk migrate` — state.db source of truth — PR #90 merged [cli]
- feat(BS-19): `synlynk launch` FTUE task picker + 6-cycle SDLC rename — PR #94 merged [cli]
- feat(BS-12a): `synlynk roles` subcommand + `roles` config default + doctor fence check — PR #95 merged [cli]
- chore(packaging): VERSION single source of truth + pipx-aware upgrade — PR #91 merged [packaging]
- docs(readme): v0.10.0 overhaul — PR #92 merged [docs]
- release: **v0.10.0 cut** — gh release create v0.10.0 [release]
- feat(BS-18): `synlynk migrate` — state.db as permanent source of truth; `project-docs/` moves to `.synlynk/project-docs/`; 5 new DB tables (memory_entries, roadmap_arcs, roadmap_phases, cost_entries, devlog_entries); immediate write-through on every DB write; DR sync via local cloud-synced folder; `--dry-run`, `--recover`, `--setup-dr` flags; 28 tests (616 total); PR #90 merged [cli]

### Agents used
- Codex: BS-18 T1-T4+T7 (DB schema, parsers, infra helpers, cmd_migrate, CLI wiring)
- Grok: BS-18 T5+T6 (write-through hooks, _generate_context_from_db, context routing)
- Agy: BS-18 T8 (E2E integration test) + blog post 36

## 2026-06-29
### Resolved (checkpoint)
- feat: synlynk v0.2.0 — watch daemon, checkpoint, status command, context compaction [cli]
- fix: synlynk v0.2.1 — correctness patch [cli]
- fix: resolve GitHub username and upgrade check via gh CLI [cli]
- chore: bump version to 0.2.2 [docs]
- feat: synlynk v0.3.0 — multi-agent foundation [cli]
- chore: 2026-06-07 design session docs — state-db, identity, workspace, arc gap analysis [docs]
- feat: synlynk v0.3.1 — sentinel + observability hardening [cli]
- test: synlynk E2E test suite — black-box CLI coverage [test]
- docs: Hybrid Workgroup design spec, brainstorm visuals, and blog post 10 [docs]
- docs: v0.4.0 Hybrid Workgroup Bootstrap — implementation plan [docs]
- docs: fix Tokq memory unit schema — file-grain → state.db view-grain [docs]
- feat: v0.4.0 — Hybrid Workgroup Bootstrap [cli]
- feat: v0.5.0 capability engine — model-aware routing, quality signals, score/story CLI [cli]
- fix: normalize quality_auto by present-signal weights (closes #43) [cli]
- docs: synlynk quick start guides [docs]
- feat: v0.6.0 capability engine — tier 2 probe, verifier parsing, pr check, org_domain_tags [cli]
- feat: v0.4.1 — Instruction Reach (Cursor, Copilot, Windsurf + drift detection) [cli]
- feat: v0.4.2 task status model — 5-state todo.md [cli]
- fix: sync VERSION to 0.6.1 — stop perpetual upgrade prompt [cli]
- feat: v0.7.0 Static Scan Quality — source architecture in every exec context [cli]
- AGY dispatch: autopilot gap analysis — unanswered questions and decision blockers [docs]
- Codex dispatch: add Capability Ledger section to synlynk status output [cli]
- Code review PR #50: capability dogfood — backfill, dispatch fixes, ledger in status [cli]
- Code review PR #50 by Codex: capability dogfood backfill, dispatch fixes, ledger in status [cli]
- Code review PR #51: codex exec headless dispatch fix [cli]
- AGY review of PR #51: codex exec headless dispatch [cli]
- Codex review of PR #51: codex exec headless dispatch [cli]
- T1: SQLite Canon — stories.status + _generate_todo_md + _import_todo_to_stories [backend]
- T2: Per-agent context profiles — .agents/<agent>.json + dispatch merge + agent configure cmd [backend]
- T3: synlynk jobs SQLite read + --watch + _preflight_dispatch + --context-mode CLI flag [backend]
- T4: Relay wire protocol — SynlynkRelay SSE broker + relay start/broadcast CLI [infra]
- T5: Sentinel VERIFY_SKIP pattern + _extract_compliance_tags [backend]
- dispatch: write job context to .synlynk/contexts/<job_id>.md not global context.md [dispatch]
- BS-5: brainstorm — standalone synlynk website (design-first, beyond functional) [web]

## 2026-07-01
### BS-17 FTUE Scan + Wizard — Wave 1–4 complete (mid-session checkpoint)
Wave execution per plan `docs/superpowers/plans/2026-07-01-bs17-scan-wizard.md`.

**Completed tasks:**
- A-1: `find_git_roots` + `fingerprint_stack` (Codex)
- A-2: `scan_skills` + `detect_home_harness` + `parse_context_sections` (Codex)
- A-3: `run_workspace_scan` interface contract (Codex) — 8-key ScanResult dict
- A-4: `write_workspace_config` + `generate_structured_context` (Codex)
- A-5: Extended `cmd_scan()` with `--refresh/--add/--remove/--dry-run/--workspace` + scan subparser (Codex)
- A-6: End-to-end smoke test for `synlynk scan --dry-run` (Codex)
- B-1+B-2: TUI primitives + landing + harness screens (Grok)
- B-3: Topology picker + workspace 2ab/2c multi-repo sub-flow (Grok)
- B-4: Skills, agents, roles screens (Grok)
- B-5: `_wiz_screen_launch` + `wizard_init` orchestrator + `--wizard` flag (Grok)

**In progress (Wave 5):**
- B-6: Wizard subprocess smoke test (Grok, job-1b3a6fa8)
- C-1+C-2: Integration tests for scan + wizard (Agy, job-7b8582ef)

**Test count progression:** 551 → 562 (A-1–A-3) → 567 (A-4+A-5) → 572 (B-3 merge) → 573 (A-6) → 579 (B-4+B-5)

**Key fix applied 3x:** Grok dispatch `--yes` → `--always-approve` (agents keep reverting it when rewriting `_VERB_MAP_SEED`/`AGENT_CAPABILITY_BASELINES`).

⚠️ **Compaction watch:** After Wave 5 gate, dispatch Wave 6 (Agy C-3 blog post), then open PR.

## 2026-07-01 (session end)
### BS-17 FTUE Scan + Wizard — All Waves Complete, PR #89 Open

All 6 waves executed to plan. Final state:

**Wave 5 gate (post-compaction):**
- Resolved GEMINI.md stash-pop merge conflict (timestamp only, took newer)
- Confirmed Grok B-6 complete (test already in HEAD, 588 confirmed on main)
- Confirmed Agy C-1+C-2 complete (integration tests committed on main)
- 588 tests pass on main

**Wave 6:**
- Agy C-3 blog post written: `docs/blog/35-pr89-v0.10.0-bs17-scan-wizard.md`
- `story-v010-wizard` + `story-v010-scan` marked `[x]` in todo.md

**Gate 6 (PR open):**
- PR #89: https://github.com/nikhilsoman/synlynk/pull/89
- Branch: `feat/bs17-scan-wizard` → `main`
- 37 new tests (551 → 588), all passing

## 2026-07-03 — v0.10.0 daily-driver stories shipped (PRs #97, #98, #99)

**Dispatched** 3 v0.10.0 daily-driver stories to agents (2× Codex + 1× Agy), all completed 726 tests passing.

**Shipped** 3 separate PRs:

- **PR #97** `feat/v010-jobsummary` — `_write_job_summary`, `_format_job_summary`, `_job_summary_path`; wired into `_reconcile_jobs` + `_reconcile_daemon_jobs`; `cmd_jobs --summary <id>` to read back structured close-out files from `.synlynk/logs/`
- **PR #98** `feat/v010-release` — `cmd_release [--version X.Y.Z] [--minor] [--dry-run]`; reads/bumps VERSION, prepends CHANGELOG.md, writes dated blog stub under `docs/blog/`, prints named-release checklist; blog post: `docs/blog/38-pr97-v0.10.1-release-command.md`
- **PR #99** `feat/v010-status` — `cmd_status --platform`; 8 helper functions (`_load_telemetry_events`, `_parse_status_timestamp`, `_humanize_ago`, `_load_platform_*`, `_print_platform_*`); three-section dashboard (Harness Compliance, Drift Sentinels, Budget Pulse); exits 1 on any alert/budget breach

**PR split approach**: changes were uncommitted on main; used Python to construct valid per-story `@@` header sub-hunks from the mixed hunk 7 (which contained both `cmd_release` and status helpers). Conflict on status PR (after release merged) resolved via 3-way: kept `cmd_release` from HEAD + status helpers from branch.

**v0.10.0 status**: all P0 stories shipped (T1–T6 in prior sessions) + 3 daily-driver stories shipped today. 726 tests. Ready for named release.
