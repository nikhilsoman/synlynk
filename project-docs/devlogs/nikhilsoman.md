
## 2026-07-30
### Harness Compatibility & Capability (PR #587 plan) — all 7 phases merged

**Shipped**, all onto `dispatch/claude/job-a7eb31f5` per plan `docs/superpowers/plans/2026-07-30-harness-compatibility-capability.md`:

- **PR #598** — Phase 1: Codex `--ask-for-approval` baseline flag fix (`synlynk/_constants.py`).
- **PR #599** — Phase 2: Grok flag mapping (`_permissions_to_flags` in `synlynk/dispatch.py`).
- **PR #600** — Phase 7: configurable `_run_agent_sync` panel-query timeout, per-agent override (`synlynk/team.py`).
- **PR #607** — Phase 3: remediation audit log foundation — `remediation_actions` table + `cmd_remediation_log` (`synlynk/db.py`).
- **PR #606** — Phase 5: `_scan_repo_requirements` presence-only artifact scan (`synlynk/probe.py`), not yet wired into preflight.
- **PR #612** — Phase 4: `synlynk doctor --fix agy` — JSON patch diff vs `~/.gemini/antigravity-cli/settings.json`, write-only-on-`--yes`, every write logged via Phase 3's audit log.
- **PR #614** — Phase 6: preflight capability gate in `dispatch_agent()` — four-way branch (stale/failing/no-coverage-required/no-coverage-optional), `_probe_results_trustworthy()` correctly hardcoded to return `False` (blocked on #578/#580 unmerged), Phase 5 presence-vs-declared wiring, new generic `--requires <capability>` flag generalizing `--requires-gh-write`.

**Deferred (correctly, per plan)**: Phase 4b (`UNVERIFIED_CAPABILITY` telemetry tag) remains unscheduled — hard-blocked on issue #419 landing.

**Process finding — filed as issue #616**: every Codex-authored PR in this stack (4/4: #606, #607, #612, #614) opened against GitHub base `main` instead of the requested stack base, despite the dispatch CLI's own preflight correctly verifying the worktree base before spawning. Root cause not yet confirmed (likely a `gh pr create` fallback path inside Codex's sandbox that can't reach `api.github.com` for the real base). Fixed each time by routing a Grok dispatch to `gh pr edit --base` + resolve resulting conflicts — same pattern as the existing GitHub-write routing SOP (#426), just extended to cover base-branch correction, not only review/merge. Recommend the dispatch wrapper itself retarget the base immediately after Codex creates a PR (outside the sandbox), rather than relying on the reviewing agent to catch it each time.

All PRs reviewed by a non-authoring agent (Grok) per PR Review Discipline, using the sanctioned COMMENT-approve fallback (#423) since all dispatched agents share one GitHub identity.

## 2026-07-11
### Epic #137 close-out — Fleet Dispatch Scheduler v1 shipped, v2 deferred to a tracked goal

**Shipped:**

- **PR #156** — Fleet dispatch scheduler v1: `stories.priority`/`readiness` columns, `synlynk story ready/draft` gate, `synlynk/scheduler.py` (`_compute_schedule_plan`, `_enqueue_plan`, fleet-level in-batch headroom accounting, `MAX_STORY_RETRIES=2` retry/reassignment), `synlynk schedule [--execute] [--max-stories N]` CLI. Implemented by Grok from an 8-task TDD plan I authored (`docs/superpowers/plans/2026-07-11-fleet-dispatch-scheduler.md`); diff + tests reviewed independently before merge. CI baseline failure signature confirmed unchanged (5 known environment-specific tests) — no regression.
- **PR #157** — Roadmap Cross-Cutting Epics update (docs-only, separate branch per discipline): epic #137–141 marked Shipped; new "Fleet Scheduler v2 (deferred)" row created, backed by a formal `synlynk goal create` record (`goal-d38e3c83`, deadline 2026-08-10) rather than a prose TODO — bin-packing around reset windows, persistent quota-blocking history, and GOVERNS-aware readiness gate v2 are gated on 30 days of real v1 production data before being scoped into stories.
- Blog post 52 written covering both PRs as one epic-close narrative.

**Epic #137 (capability-matrix hardening) is now fully closed**: capability score (#139) → quota headroom gate (#141 base, PR #148/#151/#152/#154) → cost tie-break (#140) → batch scheduler (#141 optimizer, PR #156) are all shipped code, matching the 2026-06 token-budget design end to end.

## 2026-07-05
### BS-13 Live Job Observatory

**Shipped:**

- **PR #117** — BS-13 shipped as PR #117: Live Job Observatory (observatory.py snapshot builder, synlynk watch --live observatory panel, viz Observatory tab, 837 tests passing).

## 2026-07-04
### BS-22 Vizor Ecosystem Status Data Integration

**Shipped:**

- **Branch** `feat/bs22-vizor-efficiency` — Enriched the Vizor Efficiency tab (`synlynk/viz.py`) with BS-16 ecosystem status data.
- Built a Headless efficiency banner with skeleton placeholder styling.
- Built a Capacity Table rendering relative progress bars for Claude, Agy, Codex, and Grok read/write/tool/ctx limits.
- Built a Cycle Capability Matrix displaying support state for all 6 SDLC phases (Dream, Plan, Work, Ship, Maintain, Engage) using inline SVG icons.
- Built a Fleet Header displaying attached count and current dispatch mode pill.
- Added 7 tests under `tests/test_vizor_efficiency.py` validating string presence, capacities rendering, cycle presence, dispatch modes, placeholder fallbacks, and dictionary wiring in `generate_viz_data()`.

### BS-13 Workspace HUD + Upgrade Path Audit

**Shipped (4 PRs):**

- **PR #105** `chore/bs13-hud-spec` — BS-13 design spec (`docs/superpowers/specs/2026-07-03-bs13-workspace-hud-design.md`), brainstorm visuals (`docs/brainstorm/bs13-workspace-hud/` — 4 HTML files), implementation plan (10 tasks, Codex+Grok split) [docs]
- **PR #106** `feat/bs13-workspace-hud` — `synlynk watch` + `synlynk watch --live`; `synlynk/hud.py` (JobSnapshot, FrameBuffer, HUDRenderer, LiveRenderer — 357L stdlib-only); `cycle` field added to dispatch_agent + job records; 30 tests; blog post #41. Codex: tasks 1-3+7-8 (data layer, renderer base, CLI wiring, error states). Grok: tasks 4-6+9 (layout components, integration tests). Codex review found 4 issues — 3 fixed before merge (refreshed Ns ago, show_all dead code, blog TBD→#106). Daemon HTTP enrichment deferred. [feat]
- **PR #107** `fix/upgrade-path` — 4 upgrade bugs: `_detect_install_type()` pipx detection via `shutil.which` + `PIPX_HOME`; `install.sh` curl downloads all 6 modules; `_ver_tuple()` semver comparison; migrate hint post-upgrade. 8 tests. [fix]
- **PR #108** `fix/upgrade-path-b` — 2 remaining upgrade bugs: `install.sh` deprecation notice; `_warn_stale_script_install()` called at end of `upgrade()`; `_get_pipx_source()` reads `pipx_metadata.json`; pipx local-path → force reinstall from GitHub tag. 21 total upgrade tests. [fix]

**Roadmap:** BS-13 marked ✅ Shipped; roadmap priority recap done

**Agent workflow notes:**
- Codex committed to main twice (git refs lockfile) — fixed by branching after the fact, resetting main
- Codex review via dispatch effective: found 4 real issues in 3 minutes
- Upgrade deep-dive pattern: read install.sh + `_detect_install_type` + `_run_upgrade` + pipx_metadata.json together

**Test count:** 791 passing (up from ~760 pre-session)

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

## 2026-07-06 — Four-POV strategic evaluation + company roadmap

- Wrote `docs/strategy/2026-07-06-four-pov-evaluation-and-company-roadmap.md` — evaluation of goals/architecture/execution from 4 POVs (AI-coding dev, AI-company exec, enterprise tech exec, systems architect) + open-core company roadmap (Epics 0–6).

## 2026-07-11/12 — Dispatch reliability triage: #160, #161, #162 all shipped

Reviewed the rxcc dispatch-reliability handoff note (`docs/handoffs/dispatch-reliability-rxcc-2026-07-11.md`), triaged three distinct problems into GitHub issues, and shipped fixes for all three via the full brainstorm → spec → plan → dispatch → verify → merge cycle.

**#161 — Codex worktree git-ref writes blocked (PR #163):** `dispatch_agent()` now resolves `git rev-parse --path-format=absolute --git-common-dir` and appends `--add-dir <path>` to Codex's sandbox flags. Dispatched to Codex (job-27eeabde), diff matched plan exactly.

**#160 — stale `dispatch --help` agent list (PR #164):** Help text and `choices=` now derive from `sorted(AGENT_CAPABILITY_BASELINES)` instead of a hand-maintained string that had drifted (missing `grok`). Brainstormed with `AskUserQuestion`, spec + plan written and committed on `chore/dispatch-help-agent-list-design`, dispatched to Codex (job-3d3596da), diff matched plan exactly.

**#162 — no signal distinguishing harness-internal timeout from real stall (PR #165):** Three rxcc Agy dispatch failures all died with identical `Error: timeout waiting for response` at unrelated task stages (~500–600s) — pointed to a fixed-duration timeout inside the agy binary itself, not a task failure or synlynk's own 30-min stall detector (which never fired — the failures all had active output well before 30 min). Added `HARNESS_TIMEOUT_PATTERNS` (mirrors `QUOTA_PATTERNS`) tagging matching dead jobs with a `HARNESS_INTERNAL_TIMEOUT` sentinel alert, and generalized `_check_job_stall()` from "log is empty" to "log stopped advancing" (mtime staleness vs. `stall_timeout_minutes`, replacing the old `started_at`/`elapsed_minutes` gating that made the stall-kill path unreachable once any output existed).

Two design decisions locked via `AskUserQuestion`: (1) scope = detection + stall-generalization (not full heartbeat instrumentation — declined as unjustified complexity for this issue's priority); (2) pattern-matching convention = phrase list mirroring `QUOTA_PATTERNS`, not a single hardcoded string.

**Scheduled dispatch:** used `CronCreate` (one-shot, `30 0 12 7 *`) to fire the #162 dispatch at a specific future wall-clock time per user request, since the plan was ready before the user wanted it executed.

**Notable: the #162 dispatch job itself hit the exact bug it fixes.** Codex's job (job-f26fa30c) died `FAILED (exit -1)` at ~500s — right after finishing the implementation and running `pytest` (956 passed, per its own log) but before committing. Work survived uncommitted in the worktree; verified the diff matched the plan exactly (`git diff main <dispatch-branch>`), ran the full suite locally (956 passed), then committed and pushed manually rather than losing the work or re-dispatching. First-hand confirmation the failure mode isn't `agy`-specific.

All three PRs' CI showed only the same 5 known pre-existing baseline failures (`test_detect_install_type_pip/script/unknown`, `test_run_tc4_skips_flag_only_command_templates`, `test_upgrade_auto_installs_new_version` — env-specific, confirmed present on `main` independent of these changes) — merged all three with `--delete-branch`.

**Result:** #160, #161, #162 all closed. PRs #163, #164, #165 merged.
- Key calls: reject native-harness pivot in favor of structured-interface adapters (Agent SDK/JSON/ACP); enforcement plane before enterprise sales; CLA + license split before v1.0 GA; provisionals on sentinels/permission-translation/handoff before further blog disclosure.

## 2026-07-07 to 2026-07-08 — Job Lifecycle Ground-Truth Verification epic (#128, #129, #127, #126)

**Design:** `docs/superpowers/specs/2026-07-07-job-lifecycle-verification-design.md` — dispatch/job layer wrote state and trusted it, with no independent check against git/process/filesystem reality. Four issues, one root cause. Sequenced dispatch, do-not-parallelize: #128 → #129 → #127 → #126.

**Shipped, in order:**

- **PR #130** (#128) — per-job `git worktree` isolation: `dispatch_agent()` creates `worktrees/<job_id>` on branch `dispatch/<agent>/<job_id>`, `cwd=worktree_path` instead of the shared invoking-shell cwd. First attempt regressed 49 tests by adding `git init` into the autouse `isolated_db` fixture; redispatched with root-cause diagnosis, fixed via opt-in `git_worktree_repo` fixture + autouse `stub_dispatch_worktree` stub pattern (now the template for every dispatch touching this fixture).
- **PR #131** (#129) — `_reconcile_jobs()` cross-checks git state (`_inspect_worktree_git_state()`) instead of treating a missing exit sentinel as automatic failure; new `"failed_unverified"` status; `_check_job_stall()` extends grace period on detected git activity before SIGKILLing a silent-but-working job.
- **PR #132** (#127) — real `files_touched` via `git diff --name-only <merge-base> HEAD` + `git status --short --porcelain`, replacing hardcoded `[]`; new shared `_resolve_worktree_base_commit()` reused by both `_worktree_files_touched()` and `_inspect_worktree_git_state()`; job summaries list up to 20 files with a "+N more" suffix.
- **PR #133** (#126) — `cmd_migrate()` prints resolved `DB_PATH`; `_migrate_import()` fails loud (`MigrationImportError`, exit non-zero, skips `git rm --cached`/sentinel/commit) when a non-empty source lands 0 rows. **Three dispatch rounds** — two real bugs caught via manual repro before merge, not caught by the dispatched job's own tests: (1) first attempt hard-aborted on `todo.md` files with only `priority:`-tagged rows (no `gh:` tag) because it compared inserted count against raw parsed count instead of *attempted* count; (2) second attempt fixed that but the failure-detection loop raised on the first failing source only, silently omitting other simultaneously-failing sources from the error message. Third attempt fixed both, confirmed via direct repro scripts before opening the PR.

**Process note:** every PR — diff independently reviewed (dispatch.py/`__init__.py`/db.py + conftest.py fixture safety check), full test suite run independently (never trusted the job's self-reported OK), CI failures cross-checked against `main`'s own baseline before merging (same 6 pre-existing/environment-specific failures every time: pipx install-type detection ×3, TC-4 template matching, upgrade auto-install, stale `test_version_is_0100`).

**Follow-up:** filed **#134** — cleanup issue for the 6 pre-existing CI failures (sev3, CI hygiene only), so they stop needing a manual main-baseline diff on every future PR.

**Epic complete.** All four issues shipped to main.

## 2026-07-12 — Vizor Architect Map v2: static tube map → live workspace-repo graph (PR #167)

Executed the approved 8-task plan (`docs/superpowers/plans/2026-07-11-vizor-architect-map-v2.md`) via Subagent-Driven Development — fresh Codex dispatch per task, two-stage review (spec compliance then code quality) before each merge, all sequential.

**What shipped:** `generate_tube_html()` replaced end-to-end by `generate_architect_map_html()` — nodes now come from `cfg["repos"]` (not a hand-authored `vizor-tube.json` nobody ever generated), typed edges from new `.synlynk/vizor-workspace-map.json`, and a hand-rolled ~60-line vanilla-JS force-directed layout (circular init, 200 iterations, inverse-square repulsion + linear attraction, clamped 900×620 canvas — no D3/CDN, matches Vizor's self-contained-HTML constraint). Side drawer per node: path, stack labels, GitHub link, dispatch action, Gantt-jump (`postMessage`), and active-dream count. New IDE-style collapsible file-tree sub-view sourced from a new `_query_repo_file_tree()` DB helper (reuses `synlynk scan --deep` data, no filesystem walk at render time). Two new POST routes (`/dispatch`, `/architect-map/view-pref`). Retired all `--setup-tube`/`vizor-tube.json` references from docs and code; added a conditional "Workspace Map Update Protocol" to `CLAUDE.md`.

**Schema-mismatch pre-empt (Task 8):** the plan's own self-review flagged that its draft assumed a `stories.repo_path` column that doesn't exist in production (`synlynk/__init__.py`'s `CREATE TABLE stories` has no such column, and a separate `status`/`stage` column-name mismatch already existed between `viz.py`'s query and the real schema — pre-existing, out of scope, not touched). Verified via `grep` before writing the dispatch prompt, then embedded the correct fallback directly: real active-dream count for single-repo workspaces, `0` for every repo once 2+ repos exist (no attribution signal without `repo_path`).

**One nested fix-job precedent reused:** Task 5's implementer hit a transient `git commit` lock error mid-run; a nested fix job dispatched from inside the stalled worktree resolved it and caught a real bug (inverted `!window._treeRendered` condition making the tree view permanently unreachable) in the same pass.

10 commits landed on `chore/vizor-architect-map-v2-design`, blog post 53 committed in-branch per protocol (renumbered from 52 post-merge — an earlier PR #156/#157 also claimed 52 while I was working from stale context), PR #167 opened and merged into `main` (`23a5800`). CI's `test (3.12)` failure on the PR was the same 5 known pre-existing baseline failures tracked in #134 (confirmed identical on `main`'s own concurrent run) — commented on #134 with the additional confirmation rather than opening a duplicate live issue; correctly Sev3/CI-hygiene, not a live issue. 940 tests passing (up from 934 pre-PR).

- Key calls: force-directed over tube-map-auto-layout or grid/catalog (standard shape for this problem, Backstage/Grafana precedent, avoids 45°/90°-routing engineering cost); dream-count attribution scoped down from the original spec's dream+agent+last-commit ask to just dream count, single-repo-only, rather than guess at unbuilt `repo_path` plumbing.

## 2026-07-19 — Two plans landed same session: Capability Sweep + Industry Taxonomy (PR #367), Payment-Model-Aware Cost Accounting (PR #374)

Executed both plans via Subagent-Driven Development in the same session — fresh Codex/Grok dispatch per task, spec-compliance + code-quality review before each merge, Claude doing PM/review only per the locked role split.

**Capability Sweep + Industry Taxonomy (`chore/capability-sweep-taxonomy-design`, PR #367, squash `86bb57a`):** static NAICS/APQC/SFIA lookup tables, `synlynk capability sweep` calibration command with a $10 cost guardrail, `capability_baseline.json` package-bundled seed data for cold-start `capability_ratings`, and a PR review-cycle quality multiplier (geometric decay, GitHub-only v1). Took three review rounds: round 1 found `_apply_review_cycle_multiplier` wasn't idempotent (fixed with a tracking table + guard); round 2 found the baseline seed wrote SFIA/APQC codes into columns that real organic job routing queries with a completely different free-text vocabulary — silently invisible to cold-start routing — plus a packaging gap (`capability_baseline.json` lived outside the installable package, so pip/pipx/install.sh never shipped it). Round 3 verified both fixes independently (re-ran the routing query by hand, confirmed the package-data manifest) and merged. 1258 tests passing.

**Payment-Model-Aware Cost Accounting (`chore/payment-model-accounting-design`, PR #374, squash `8596351`):** `payment_models` config, `credit_grants` ledger table, `resolve_payment_value()` branching on subscription/credit-grant/pay-as-you-go, `synlynk credit grant` CLI, `costs.md`'s single cost column split into api-equivalent + actual-dollars-spent with mode tags, and a per-agent "Payment Models" rollup in `check_budgets()`'s Budget Pulse. While reviewing the task spec for wiring `resolve_payment_value()` into `update_costs()`, I found — before dispatch, not after — that the new `costs.md` column layout would break `parse_costs_md()`'s hardcoded column index, making the budget gate read the inflated api-equivalent figure instead of real spend; wrote the fix myself into the dispatch prompt alongside the plan's own text. A full-branch review pass after all six tasks landed (something none of the per-task reviews had done) caught two further bugs: subscription overage billed the full cumulative excess every call instead of just the marginal excess added that call, and multi-grant credit consumption drained one grant and billed the overshoot as cash instead of chaining into the agent's other unexpired grants. Both fixed with regression tests (hand-traced by the re-reviewer against the original repro numbers) before the second review round merged. 1277 tests passing. A synlynk dispatch auto-finalization side effect opened a stray PR against the branch mid-cycle despite the reviewer's explicit "do not merge" verdict on round 1 — closed without merging.

- Key calls: dispatching an independent whole-branch reviewer *after* all per-task reviews complete, not just relying on task-by-task review, is what caught both the taxonomy-vocabulary mismatch and the overage/credit billing bugs — neither was visible when each task's diff was reviewed in isolation. Worth keeping as standard practice for any plan with more than ~4 tasks touching the same subsystem.

## 2026-07-23 — Dispatch Stacking + Ground-Truth Merge Gate (PR #463)

Executed the 9-task plan for `docs/superpowers/specs/2026-07-22-dispatch-stacking-ground-truth-gate-design.md` via Subagent-Driven Development, each task dispatched as its own `synlynk dispatch codex` job from `chore/dispatch-stacking-ground-truth-gate-design`, Claude doing PM/review/merge only per the locked role split.

**Dispatch Stacking + Ground-Truth Gate (`chore/dispatch-stacking-ground-truth-gate-design`, PR #463, squash `de86676`):** dispatch jobs now stack on the current feature branch's tip by default instead of always branching off stale `origin/main` (`dispatch.stacking` config, `--base` override); job worktrees anchor to the resolved base's exact tip SHA at creation, recorded as `base_branch`/`base_sha` on the job record; a harness-run test-suite gate (`dispatch.gate_suite_cmd`) judges merge-eligibility from ground truth — `suite_result.failed > 0` forces `needs_fix`, never a silent `completed`; STALE_BASE detection via `git merge-base --is-ancestor` flags jobs whose base advanced before merge; `synlynk jobs`/`synlynk logs` summaries render `base:`/`suite:` lines across all four call sites. Integration test proves two sequential dispatched jobs stack with zero merge conflicts; a second test exercises the gate end-to-end against a worktree seeded with a real failing suite, no mocking of the gate function itself. 1345 tests passing, 2 skipped.

Ground-truth verification caught real problems during the build, not just after: 3 of the 9 dispatched jobs (Task 7's `job-a61fcd91` plus two earlier ones) were self-reported `PERMISSION_DENIED` by `synlynk jobs` despite being fully correct, complete, committed work — only caught by checking `git log`/`git diff --stat` directly inside each job's own worktree instead of trusting the summary. Filed issue #461 mid-session to track this as a standing pattern rather than a one-off. Task 7's dispatch prompt initially cited stale line numbers from the plan doc (pre-dating Tasks 5-6 landing) — caught and corrected before dispatch by grepping actual current call sites. Tasks 8+9 landed as one combined commit instead of two (a `git checkout -- <branch> -- <two files>` staged both at once) — assessed harmless and left as-is rather than unwound.

- Key calls: this feature was built using the dispatch mechanism it improves — 9 Codex jobs dispatched under the *old* pre-fix stacking behavior — which is exactly why ground-truth verification mattered so much doing it; the false-PERMISSION_DENIED rate observed while building the fix is itself the strongest evidence for why the fix (and issue #461) is needed. Backfilled this devlog entry and the accompanying blog post (`docs/blog/73-pr463-dispatch-stacking-ground-truth-gate.md`) after merge, not during — a process gap flagged directly by Nikhil; going forward, do the surrounding PM bookkeeping (devlog, blog, cost capture, project-docs sync) at natural pause points during multi-task dispatch execution, not deferred to a post-hoc backfill.

## 2026-07-24 — Dispatch reliability trio: PR #475, #479 (RCA), #476 (CVE) + housekeeping backfill

Three small, independent PRs landed off the back of a failed `agy` dispatch reported by a separate rxcc-repo session, plus a same-day docs-only follow-up closing the bookkeeping gap they left open.

**PR #475 (`10387db`):** two dispatch-pipeline reliability fixes surfaced by the rxcc failure report — `_maybe_open_worktree_pr` hardcoded `gh pr create --base main`, breaking on any repo whose default branch isn't literally `main` (now resolves via `origin/HEAD` symbolic-ref with a fallback chain); and headless `agy` dispatch with no write/run permissions granted silently produced a clean-looking no-op instead of a warning (now warns loudly instead of failing silently).

**PR #479 (`92d254a`, docs-only):** investigated a more specific rxcc report — Antigravity CLI's own "jetski" auto-deny for the command/shell tool, four of rxcc's mitigation attempts all failing identically. Per explicit instruction, reproduced locally *before* speccing any fix: 4 dispatched `agy` jobs on the confirmed-identical machine/install/`agy` version (1.1.6), covering every permission-granting path synlynk has (`--grant`, `.agents/agy.json` harness-overrides matching rxcc's exact config, with/without a global `~/.gemini/settings.json` grant, one forcing the specific "command" tool) — zero repro across all four. Wrote `docs/rca/2026-07-24-agy-jetski-headless-permission-investigation.md` closing the investigation as a likely transient Antigravity CLI auth/session-state issue (unexamined `jetski_state.pbtxt` token flagged as the lead suspect), not a synlynk dispatch bug. No spec, no code change.

**PR #476 (`75078a8`):** routine Dependabot alert #7 fix — `brace-expansion` 1.1.15 → 1.1.16 in `website/package-lock.json` (CVE-2026-13149, transitive via `minimatch`/`@11ty/eleventy`), integrity hash cross-checked against the live npm registry before merge. Full 1378/1380-test suite green.

All three PR checks were dispatched to Codex for the required non-authoring reviewer step; every single one hit the same known Codex-sandbox `sqlite3.OperationalError: unable to open database file` limitation on `synlynk pr check` — ground-truthed clean (exit 0, all model versions attested) by re-running the identical command directly outside the sandbox each time. Also corrected a wrong assumption carried into this session: `synlynk pr check` takes **no PR-number argument** — it's a local attestation check against whatever commit is currently checked out in the worktree, not `synlynk pr check <pr#>`.

**Same-day housekeeping backfill (`chore/blog-cost-housekeeping-pr475-479-476`):** none of #475/#479/#476 had blog posts drafted at PR-open time despite the standing per-PR policy — backfilled as posts 74–76. Discovered mid-backfill that `synlynk cost log` (the manual/native-work cost path) only inserts into the SQLite `cost_entries` table via `_insert_cost_row` — it does **not** append to `project-docs/costs.md`, while `parse_costs_md()` (what `check_budgets()` and `synlynk status` actually read) only reads the `.md` file. The two cost ledgers are silently unreconciled — a real gap, not something introduced this session, and not fixed here (out of scope for a docs backfill). Worked around it by hand-appending matching rows to `costs.md` alongside the `cost log` DB entries so this session's spend is visible in both places. Also confirmed via `_resolve_db_path()` that `state.db` is keyed by an MD5 hash of the **git-common-dir root**, not the worktree path — all worktrees of this repo share one DB (the N6 fix from the previous session), which is why cost entries logged from a fresh worktree still landed in the same ledger as the main checkout's.

- Key calls: reproduce-before-spec discipline (explicit user instruction) prevented writing an engineering fix for a bug that couldn't be shown to exist in this repo's code — worth keeping as standard practice for any cross-session bug report, not just this one. The costs.md/cost_entries reconciliation gap should get its own issue rather than being fixed ad hoc inside a housekeeping PR.

## 2026-07-25 — #496 capability-router crash root-caused and fixed (PR #508), cost-capture + rate-mismatch follow-ups filed (#510)

Investigated #496 (`sqlite3.OperationalError: no such column: discipline` in `_capability_candidates_for_story()`) via `superpowers:systematic-debugging`, Claude doing root-cause investigation and PM/dispatch only per the locked role split.

**Root cause, confirmed by direct reproduction against a live `state.db`, not theorized:** `capability_scores` is a SQL VIEW (`_DB_SCORES_VIEW`, `synlynk/__init__.py:960-980`), applied via `CREATE VIEW IF NOT EXISTS` inside a `try/except sqlite3.OperationalError: pass  # view already exists with same definition` in `synlynk/db.py:290-293`. That comment is false — `IF NOT EXISTS` is a silent no-op when the view already exists on disk, regardless of whether its definition matches the current `_DB_SCORES_VIEW` string, and never raises `OperationalError` in that case. A `discipline` column (plus `role`/`stage`) was added to the view's SELECT/GROUP BY in a later commit; any `state.db` initialized before that commit kept the old 6-column view forever, with nothing to drop-and-rebuild it. Verified directly against this repo's own `state.db` (`~/.synlynk/projects/13267207/state.db`, stale 6-column view) and via a scan of all local project DBs: 984 of 3862 had the stale view. Related contributing factor: a `schema_version` table exists (`__init__.py:802`) but is never read or written anywhere — no real migration-versioning mechanism exists to guard against this kind of drift.

**Fix (PR #508, squash `0308639`):** `synlynk/db.py` now does `DROP VIEW IF EXISTS capability_scores` followed by unconditional recreation from `_DB_SCORES_VIEW` on every `_get_db()` migration pass — self-heals regardless of on-disk staleness, safe since it's a view (no data loss to `capability_ratings`). New regression test `tests/test_agent_quota_tracking.py::test_fix_stale_capability_scores_view_missing_discipline_column` seeds a stale pre-migration view and asserts the rebuild. Dispatched to Codex (`job-dcaf37b0`, `story-0ba62064`); job self-reported `FAILED_UNVERIFIED` but the worktree held a correct, complete commit — same known false-negative pattern as #202/#461, verified independently (full suite 1379 passed, 2 skipped) before proceeding. Review + merge routed to Grok per PR Review Discipline (Codex authored, can't be its own reviewer) using the sanctioned #423 COMMENT-review fallback (`gh pr review --approve` fails on shared dispatch identity) — `synlynk pr check` passed, merged squash, confirmed `MERGED`/issue auto-closed directly against the GitHub API rather than trusting the job's self-report.

**Cost-capture gap, narrower root cause than #496's own comment thread suggested:** backfilling cost entries for this session's 4 dispatch jobs found 2 of 4 missing from `project-docs/costs.md`'s auto-capture — but one was the `FAILED_UNVERIFIED` codex job (fits the existing hypothesis) and the other was a cleanly-exited (`OK`, exit 0) Grok job whose completion was only ever surfaced via `synlynk logs --job`, never re-surfaced by a subsequent `synlynk dispatch` call. The two jobs that *did* get auto-captured were both swept up as a side effect of a later `synlynk dispatch` invocation printing their completion block — suggesting auto-capture triggers on `dispatch`'s own completion-detection path, not on every possible way a job's completion gets displayed. Backfilled both via `synlynk cost log` (sanctioned manual path). While backfilling, found the manual path's hardcoded flat rate (`$0.003/1K in + $0.015/1K out`, from `update_costs()`) produced $6.64 for the codex job vs. the $1.69 the live dispatch wrapper itself reported at completion for the identical token counts — a ~4x discrepancy. Filed as **#510** (separate from, but related to, the costs.md/cost_entries divergence already documented in #496's comment thread) rather than folded into an existing issue, since it's a distinct failure mode (wrong dollar figure on entries that DO land, vs. entries that don't land at all).

- Key calls: reproducing the crash directly against a live `state.db` (not just reading code) both confirmed the root cause beyond doubt and surfaced the actual blast radius (984/3862 local project DBs affected) — worth doing whenever a bug report's traceback points at a schema/DB-shape mismatch, not just tracing the code path. Treating `FAILED_UNVERIFIED` as "verify before discarding" rather than "verify before trusting success" continues to pay off — this is now confirmed across #202/#461/this session, a stable enough pattern to stop re-deriving each time.

## 2026-07-25 — PR #515 reviewed/merged, #202 (stale job-status display bug) root-caused, fixed, and merged (PR #519)

**PR #515** (the #496-session devlog/costs backfill from the entry above) went through its own PR Review Discipline before merging: dispatched to Codex as non-authoring reviewer (`job-64eed1af`) — `synlynk pr check` passed, diff scope confirmed docs-only, full suite green (1379/2). Grok (`job-bfb205a6`, `--requires-gh-write`) posted the #423 COMMENT-review fallback and squash-merged. Independently confirmed `MERGED` + branch deletion against the GitHub API rather than trusting job status — both jobs' own `.summary` files subsequently showed `unknown` on a later `synlynk jobs --all` poll despite being genuinely complete, another live instance of the stale-status bug this pushed us to tackle next.

**#202** ("`synlynk jobs --all` shows stale FAILED/0-touched status for a job that actually completed successfully") — root cause confirmed by rereading current `synlynk/jobs.py` against the issue's own prior investigation (line numbers had shifted from 3 to 4 `_write_job_summary()` call sites since #192/#199, pattern unchanged): `_reconcile_jobs()` (jobs.json-based) and `_reconcile_daemon_jobs()` (state.db `daemon_jobs`-based) are two independent reconcilers that both write to the same per-job `.summary` file with no ordering guarantee or "don't downgrade a terminal status" guard. `_reconcile_daemon_jobs()`'s call site (~jobs.py:1433) hardcodes `files_touched=[]` and falls back to reading a `<log>.exit` file for `exit_code` — but that file gets `os.remove()`d by whichever reconciler reads it first, so a second pass over the same job_id finds nothing, `exit_code` stays `None` (formatted as `-1`), and it silently overwrites an already-correct `OK (exit 0), N touched` summary with `FAILED (exit -1), 0 touched`.

**Fix (PR #519, squash `e2c1ff6`):** dispatched to Codex (`job-6bd24177`, `synlynk/dispatch.py`) — `_write_job_summary()` now refuses to overwrite an existing terminal summary (`OK`/`FAILED` with a real files-touched count) when the incoming write has empty `files_touched` and an ambiguous `exit_code` (`None`/`-1`). New regression test seeds a correct terminal summary, drives `_reconcile_daemon_jobs()` over a dead-PID job (simulating the exact race), asserts the summary survives. Codex self-reported `FAILED_UNVERIFIED` — same precedent as #202/#461/#508 — but the worktree held a real pushed commit; independently verified via `git log`/`git diff --stat origin/main...HEAD` (clean, only `synlynk/dispatch.py` + the test file) and a full local suite run (1380 passed, 2 skipped, one more than baseline from the new test) before proceeding. Codex also stopped short of opening the PR itself (known "agents don't reliably finish their own git steps" gap) — opened **PR #519** directly rather than re-dispatching, since `gh pr create` on an already-pushed branch is PM/deploy housekeeping, not implementation. Grok (`job-554610f7`, dispatched from inside the `job-6bd24177` worktree — its job state lived nested under that worktree's own `.synlynk/`, not the top-level one, worth remembering for next time a job is dispatched from inside another job's worktree) posted the #423 approve checklist and squash-merged; confirmed `MERGED` + branch deletion + review comment directly against the GitHub API.

**Cost-capture backfill:** two jobs from this arc were missing from `costs.md`'s auto-capture — `job-6bd24177` (the #202 fix itself, $2.99, 3.7M in/42K out — a large token count from extensive investigation reading) and `job-554610f7` (the nested-worktree PR #519 review/merge, $0.17). Both fit the already-documented #510 pattern (completion surfaced only via `synlynk jobs`/nested logs, never re-printed by a subsequent top-level `synlynk dispatch` call) — hand-appended with `[est?]` markers rather than re-litigating #510 in a new issue.

- Key calls: the mandatory "`git pull origin main --ff-only` after every merge" rule (documented in [[feedback: synlynk dispatch branches off local main]]) got skipped between PR #515 and PR #519's merge — caught it before dispatching #202's fix (local `main` was still 2 commits behind), stashed the pending auto-captured cost rows, pulled, and popped rather than losing them. A reminder that this step needs to become habitual at every merge boundary, not just recalled when something looks off.

## 2026-07-25/26 — Issue #423 (per-role GitHub identity) arc fully closed: PRs #517/#535/#536/#537/#539

**PR #517** shipped the core per-role GitHub App identity feature (design/plan already committed in prior sessions). This session finished it: verified and integrated Codex's fix for a real leak Codex's own independent review (`job-c051d151`) caught — `requires_gh_write` dispatch only *set* `GH_TOKEN` on successful mint, never cleared an inherited personal token on failure (job-0f9a4bef → `dd462d1`) — plus a py3.8 CI break (`tuple[Path,Path,Path]` PEP 585 syntax in `team.py`, fixed directly with `from __future__ import annotations` since it was one-line and already-precedented elsewhere in the repo). Merged, then filed two deliberate follow-ups from the PR's own Security Review rather than bundling them in: **#524** (cross-process token redaction was a no-op) and **#525** (`synlynk doctor`'s real CLI path never ran `HEALTH_CHECKS`).

**#524/#525 investigation:** #525 turned out to have two intentional, separately-tested `cmd_doctor()` code paths rather than a simple oversight — resolved the design question ("add a flag, or run both in sequence?") via `AskUserQuestion` before dispatching, rather than guessing. Both fixes dispatched to Codex in parallel (job-67052f14 for #524, job-a6115feb for #525).

**#524 → PR #535 — caught a real bug in the dispatched diff before merge.** Spec said the redaction cache belongs at `.synlynk/token_redaction_cache.json`; the dispatched code hardcoded `synlynk/token_redaction_cache.json` (missing the leading dot — the actual package source dir). The job's own new tests used the identical wrong path in their `tmp_path` fixtures, so `pytest` was green despite the defect. Only caught because running the full suite in the real integration worktree (not the job's `tmp_path`) left an untracked `synlynk/token_redaction_cache.json` visible in `git status`. Fixed directly (one-line path correction + 3 matching test-path fixes), disclosed explicitly in the PR body, full suite re-run green (1413 passed, 2 skipped). See [[feedback]] for the generalized lesson this produced.

**#525 → PR #536 — matched spec exactly, no fix needed.** Integration hit an unrelated merge conflict in `tests/test_agent_quota_tracking.py` against issue #526's already-merged fix (`6b57600`, same file, unrelated feature) — resolved by keeping both new tests side by side. Full suite green (1410 passed, 2 skipped).

Both PRs reviewed via the sanctioned #423 COMMENT-checklist fallback (self-authored — `gh pr review --approve` always fails as self-approval) and merged squash. Job worktrees/dispatch branches cleaned up after integration.

**Housekeeping caught after merge, not before:** both dispatch jobs' actual costs ($9.34 est for job-67052f14, $6.27 est for job-a6115feb) weren't auto-captured to `costs.md` — same pattern as the #510-adjacent gap documented earlier this month (completion surfaced via manual `gh pr view`/`.summary` polling, not a subsequent live `synlynk dispatch` call). Logged via `synlynk cost log` (DB) + manually backfilled matching rows into `costs.md` (PR #537, docs-only). Also found and reverted the usual dispatch-noise pair (`GEMINI.md` harness-stamp bump, `project-docs/todo.md` wiped to near-empty via stale state.db regen) and cleaned up 27 leftover stub `worktrees/job-*` directories (just orphaned prompt `.md` files, no real checkouts) — later confirmed already fixed upstream via a separately-merged PR #530 (`worktrees/` added to root `.gitignore`).

**Blog posts #78/#79** (PR #539, docs-only) drafted for PR #535/#536 per the Blog Post Protocol — flagged as overdue mid-session (should have gone out with/immediately after each PR) rather than skipped silently.

**Roadmap sync (this entry's own PR, `chore/roadmap-423-closed`):** the `can_gh_write` Capability Routing row in `project-docs/roadmap.md` still said "issue #423's identity half stays open" — stale as of PR #517. Updated that row and added a new **Per-Role GitHub App Identity** row documenting the full #423 arc as shipped.

- Key calls: treating the roadmap's stale "#423 stays open" note as worth fixing on sight, not just as background noise, once explicitly asked "anything else to capture" — a good trigger question for surfacing exactly this kind of doc drift before it misleads a future session.

## 2026-07-26 — PR #528 verified merged, #530 (.gitignore worktree gap) fixed and merged (PR #533)

Verified **PR #528** (the #526 stale-`.exit`-marker-race fix from the previous session) was cleanly `MERGED` against the GitHub API directly — approve comment posted, branch deleted. Confirmed the `--requires-gh-write` env-var stripping from #517 didn't regress anything: `gh` on this machine authenticates via its own stored `gh auth login` session, not `GH_TOKEN`/`GITHUB_TOKEN`, so stripping those env vars was a no-op here.

**#530** (`.gitignore` has `.worktrees/` dot-prefixed but the repo's actual dir is `worktrees/`, no dot — the gap PR #528 hit live) dispatched to Codex for the one-line fix. Codex made the correct commit (`74f455a`, branch `fix/gitignore-worktrees-530`) but its sandbox has zero network egress to `github.com` — confirmed via DNS resolution failure in shell, Node `fetch`, and the GitHub connector's write calls all being cancelled, even with a PAT sitting in `GITHUB_PERSONAL_ACCESS_TOKEN` env — so it could not push or open a PR. Re-dispatched to Grok, pointed at the existing commit in Codex's worktree; since worktrees of the same repo share one object database, Grok referenced `74f455a` directly with no need to redo the edit, pushed, and found `synlynk-dispatch`'s own auto-finalization wrapper had already opened **PR #533** — cleaned up the title/body. Agy reviewed as non-authoring reviewer (posted a formal `COMMENT` review with an approve checklist — contrary to the standing #426 assumption that Agy can't complete GitHub-write actions headless, this one went through; confirmed directly via `gh pr view 533 --json reviews`, not just trusted the job's self-report). Grok merged (squash `8804111b`), confirmed `MERGED` against the GitHub API.

**Cost-capture gap, another instance:** none of this arc's 4 dispatch jobs (`job-b5df15ce` codex, `job-e6a66ce6` grok, `job-0d3b2b0f` agy, `job-da38baad` grok) landed in `.synlynk/telemetry.json` with cost data — confirmed by grepping telemetry directly, each entry was bare `{"type": "dispatch", ...}` with no completion/cost fields. Backfilled all 4 via `synlynk cost log` plus hand-appended matching rows to `costs.md` (same workaround as prior sessions — `cost log` only writes `cost_entries` in the DB, `costs.md` is what `check_budgets()`/`status` actually read; still unreconciled per #481). New wrinkle worth remembering: removed the job worktrees for hygiene *before* running `cost log`, and a completely unrelated `synlynk cost log --help` invocation afterward re-triggered a stale completion print for `job-da38baad` — `UNKNOWN/exit unknown/$0.00/0 touched` — because the reconciler had nothing left to read once the worktree was gone. Not a #202 regression (that fix guards against downgrading an existing *terminal* summary; this case never had one written before the worktree disappeared), but it means: **capture/backfill costs before removing job worktrees, not after.**

- Key calls: didn't take Codex's own end-of-turn "done" narration at face value for the GitHub-write steps — it correctly self-reported the blocker (network egress) rather than falsely claiming success, and the follow-up dispatch to Grok explicitly named the existing commit/branch so no rework happened. Also didn't assume the #426 Agy-can't-do-GH-writes memory was still accurate without checking — it wasn't, this time; memory entries about agent capability constraints should get re-verified against the live job outcome rather than treated as permanent fact.
## 2026-07-26 — Cost/capability report (PR #541), open-PR backlog triage (24 closed), #521/#529 review (PR #560), LIVE-3 discovered mid-session

**Cost/capability report (PR #541):** built a last-50 `cost_entries` report directly from `state.db` rather than hand-assessment. Found discipline/SFIA tagging only covers 8/50 rows (the rest are `legacy_unknown`, pre-taxonomy — not a join bug), though those 8 account for 96% of cost. Also confirmed `stories.discipline` is a mixed column (real SFIA codes + un-migrated legacy strings) despite `_taxonomy_crosswalk_state.completed=1` — 86/184 story rows still `legacy_unmapped=1`, worth its own follow-up issue. No thinking-token/tool-use-count column exists anywhere in the schema; Codex logs only print a combined `tokens used` total, and roughly half of job logs (127/263) have no raw `.log` transcript to scrape as a fallback.

**Open-PR backlog triage:** 38 PRs had accumulated open, mostly dispatch exhaust from 2026-07-24/25 sessions. Closed 24:
- 10 `agent-github-identity-design` plan-task PRs superseded once #517 shipped the whole feature directly (branches now conflict with `main`)
- 7 review-report wrapper PRs whose target PR was already merged (nothing left to land)
- 2 malformed dispatch artifacts (`REPRO_TEST*.txt` permission-probe leftovers)
- 5 more (#497/#500/#503/#506/#518) confirmed via `git merge-base --is-ancestor` to be fully absorbed into the #521→#529 commit chain

**#521 vs #529 (PR #560):** what looked like two competing ~2,100-line fixes for the same migrate/rollback bug turned out to be a linear chain — #529's HEAD is a direct git descendant of #521's HEAD, so #521 is fully contained and was closed with no loss. #529 itself is NOT ready to merge: checked out its HEAD into a scratch worktree (no CI had run on the branch at all) and the full suite had 4 failures, including `test_scenario_migrate_failure_injection_triggers_rollback` — the exact scenario the PR claims to fix. It also bundles ~2,100 lines of `state-engine-pr1` rearchitecture (DB-generated `roadmap.md`/`costs.md`, doc archiving, new `synlynk roadmap add` command, `check_budgets()` reading `cost_entries` instead of the `.md` file) well past its stated scope. Findings written up and posted as PR comments on both.

**LIVE-3, discovered mid-session, already resolved autonomously:** while reviewing #521/#529, found that the same `state-engine-pr1` rearchitecture had *also* been merged independently via PR #542, and its merge-conflict resolution (Grok, non-authoring reviewer) had deleted 13 files with no DB regeneration path — `decisions/*.json`, `devlogs/*.md`, `memory.md`, `repo-evaluation-report.md`, and this session's own cost-capability report. The background dispatch pipeline caught it, filed issue #547 (Sev1), wrote the RCA, and shipped recovery PR #549 — all merged before I even finished #521/#529's review. Nothing was permanently lost (git object store retained everything via the pre-merge commit); the gap was between merge and detection, not data destruction. Reconciled local `main` (was 3 commits behind, had a stray untracked duplicate of the RCA file and a stale uncommitted `costs.md` edit — that file is no longer git-tracked as of #542's DB-canonicalization, confirmed via `git ls-files`).

**Note for next session:** `project-docs/costs.md` is no longer git-tracked (moved to DB-backed generation under `.synlynk/`, gitignored). The Cost Capture Protocol's "append actual cost to `project-docs/costs.md`" step should now read as `synlynk cost log` only — the manual `.md`-append path from this session's earlier entries is obsolete.

- Key calls: verifying #529's test suite directly in a scratch worktree rather than trusting the PR description's "fixed" framing caught a real regression before it could be merged — same "verify job/PR self-report against ground truth" discipline that's paid off repeatedly this month (#202/#461/#496), applied here one layer up at the PR-review stage rather than the job-completion stage. The `git merge-base --is-ancestor` check for collapsing apparent PR "duplicates" into a real supersession chain is a reusable triage technique worth reaching for first whenever multiple open PRs claim overlapping scope.

## 2026-08-08 — UX 1.0 field trial: Phase 4 gate opened, trial window started

Executed the UX 1.0 field-trial-readiness plan's 5 dispatchable tasks (Phase 1 checklist verification, Phase 2 journey map, Phase 3a/3b/3c terminal tips / Vizor banner / Slack cross-links), reviewed each as non-authoring reviewer, and merged all to `main`: PR #824 (FTUE fix, closes #822), #825 (journey map), #826 (Vizor banner), #827 (Slack cross-links), #829 (terminal tip producer, re-dispatched after job-3999dc07 self-aborted on a stale `--base main` resolution — confirmed the re-dispatch landed correctly on top of GOVERNS's merged `NudgeData`/`_print_pending_nudges`).

**Phase 4 gate conditions confirmed:** surface checklist's only Fail row (#822) re-verified against both originally-affected projects (rxcc, cc-videoreframing — `synlynk viz --serve < /dev/null` no longer crashes, serves 200) and closed; Tasks 3/4/5 merged to main; GOVERNS Tasks 6/9 confirmed present (`class NudgeData` in `synlynk/fencing.py`, `_print_pending_nudges` in `synlynk/dispatch.py`).

**Fresh pipx install cut:** `pipx install --force git+https://github.com/nikhilsoman/synlynk.git@main` — `--version` string stays `0.13.0` (expected, no Named Release has bumped it yet per CLAUDE.md policy), confirmed the install is genuinely fresh by checking `synlynk/ux_nudges.py` (today's Task 3 merge) is present in the pipx venv's site-packages.

**Trial window starts today, 2026-08-08.** Subject projects: rxcc, cc-videoreframing, playblazer-ng, synlynk-on-itself. Daily real usage across all 4 projects and all 3 surfaces (TUI, Vizor, Slack) per the spec's Sustain-stage check — not a passive wait. Exit criteria: no Sev1/Sev2 live issue against the 3 surfaces for the duration of an open window (no fixed end date; resets on any Sev1/Sev2 until resolved and re-verified), closes only when the bug bar is clean and Nikhil signs off. On successful exit: Named Release Policy kicks in (CHANGELOG, VERSION bump, `gh release create`, roadmap row, blog post, one-sentence pitch).

**Known non-blocking gap carried into the trial:** TUI panels, Vizor write routes (`/dispatch`, `/approve`, `/kill`), capability-manifest gating, and `subscribe()` live updates remain "Not yet verified" in the surface checklist — genuinely require a live interactive session or in-flight job to test safely, explicitly deferred as a non-blocking follow-up by the checklist's own design (matches the plan's Phase 1 intent). playblazer-ng has no `.synlynk/` directory yet (not onboarded) — its 4-project daily-usage requirement can't start until it's onboarded; flag this as the first thing to resolve once the trial is live.

- Key calls: re-verified the #822 fix against real repro conditions (both originally-affected projects, headless stdin, actual HTTP 200 check) rather than trusting the merged PR's own test suite as sufficient evidence for closing the checklist's Fail row — the checklist's own header explicitly requires real-project exercise, not synthetic runs. Local `main` was 5 commits behind `origin/main` after this session's own merges (worktree-based sessions don't auto-pull the primary checkout) — caught before it caused a stale-base repeat of the same bug that hit job-3999dc07 earlier in this session.

## 2026-08-09 — PR #830/#831 closed out, playblazer-ng onboarded (PR #4), journey map interactive verification complete

**PR #830** (Phase 4 gate docs — completed surface checklist + trial-start devlog entry) reviewed non-authoring and squash-merged to `main`. **PR #831** (combined blog post covering PRs #824–#830 as one theme, `docs/blog/106-pr824-829-ux1.0-field-trial-readiness.md`) written, reviewed, merged — deliberately one post for the whole plan execution rather than 6 separate ones, a disclosed scope call to avoid redundant noise. Filed **issue #832** for the recurring `synlynk dispatch --base main` stale-ref bug (job-3999dc07 vs the working job-729771ed re-dispatch), after confirming no existing duplicate.

**playblazer-ng onboarded to synlynk (PR #4, `Dialify/playblazer-ng`):** ran `synlynk init --dry-run` then the real `init` — purely additive, added `.synlynk/`, CLAUDE.md/GEMINI.md/AGENTS.md/AI_INSTRUCTIONS.md harness fences, and `project-docs/`. Correctly separated onboarding-generated changes from a pre-existing, uncommitted user edit to the root `roadmap.md` (left untouched, not mine to commit). Confirmed that repo's own CLAUDE.md carries the same PR Review Discipline (non-authoring review, COMMENT-review fallback per #423) before applying it there. Got explicit user go-ahead before pushing/opening a PR on a different-org repo. Closes the last blocker noted in PR #830's devlog entry — all 4 trial-window subject projects (rxcc, cc-videoreframing, synlynk, playblazer-ng) now have `.synlynk/`.

**Journey map interactive verification (closes the non-blocking gap disclosed in PR #825's review):** served `docs/brainstorm/ux-journey-map/` locally (`python3 -m http.server`, since Chrome MCP tooling blocks `file://` navigation) and drove it end-to-end via `claude-in-chrome`. Confirmed all 7 journeys render distinct, correct simulated content on their default TUI surface, and did a full 3-way surface-toggle check (TUI / Vizor Dashboard / Slack Notifier) on two journeys (#01 and #07) — all switches clean, zero console errors across the whole pass. Hit a recurring transient `"Cannot access a chrome-extension:// URL of different extension"` error on screenshot/click calls partway through; a fresh tab group (`tabs_context_mcp` with `createIfEmpty`) cleared it, and `read_page`'s accessibility-tree snapshot worked throughout even when screenshots didn't, so verification continued on that instead of stalling. Server process killed and tab closed at the end.

- Key calls: didn't force screenshot-only verification when it started erroring — switched to `read_page` (still ground-truth DOM content, not a guess) rather than declaring the check blocked or silently skipping the remaining journeys. Treated the two full-matrix samples (#01, #07) plus a clean default-render pass on the other 5 as sufficient evidence rather than mechanically driving all 21 combinations — same proportionate-sampling judgment call as elsewhere in this project, disclosed rather than silently assumed.

## 2026-08-09 — Issues #846/#847 resolved (PRs #851/#850), #848 guide shipped (PR #853)

**#846/#847 (TUI approve/kill keybindings, Slack notifier event/port mismatches):** both dispatched to Codex earlier this session (`job-2d041ef4`, `job-81e7724f`), independently verified rather than trusting job self-report — full test suites re-run directly in each worktree (1791 passed/2 skipped; 1789 passed/2 skipped), CI confirmed green on all 3 Python versions, both diffs read in full. Two anomalies run down rather than waved through: the `GEMINI.md` touch in both worktrees was the harness's own routine `verified:` timestamp bump (harmless), and the apparent duplicate `tests/test_notifier_slack.py`/`tests/test_slack_notifier.py` pair turned out to already coexist on `main` pre-dispatch (not an agent-created orphan). Both PR bodies were auto-generated without a GitHub closing keyword (`Fix GitHub issue #846:` rather than `Fixes #846`) — edited to add `Fixes #N` before merge, confirmed both issues actually closed post-merge rather than assumed. Reviewed via the sanctioned #423 COMMENT-checklist fallback, squash-merged (PR #851, PR #850). Devlog/blog for this arc landed in PR #852 (docs-only, left open for the user's own merge decision — not self-merged).

**#848 ("Watching Synlynk @Work" guide, PR #853):** content dispatched to Agy (`job-94bd0c6b`, $1.40, 126s) against a fully code-grounded task spec — exact TUI keybindings from `synlynk/tui.py`, exact Vizor port (`8721`) and flags from `synlynk/viz.py`, exact Slack event names from `synlynk/notifiers/slack.py`, with specific callout-class-to-content mapping so the doc would reuse the existing design language rather than reinvent it. Review found one real bug (three `<td>` elements inside a bare `<ul>`, no table — invalid HTML) and fixed it directly rather than re-dispatching, since it was a 3-line single-file correction. Everything else held: zero `<img>` tags (CSS-mockup-only, per explicit user-confirmed direction after a design-system audit showed none of the 3 existing docs use real screenshots), all 5 callout classes correctly used, port `8721` correct throughout.

**PDF rendering, no in-repo tooling:** confirmed no wkhtmltopdf/weasyprint/puppeteer exists anywhere in the repo — the 3 existing doc PDFs are static committed binaries with no reproducible build step. Rendered via headless Chrome (`--headless --print-to-pdf`) against a local `python3 -m http.server` (the `claude-in-chrome` MCP tool blocks `file://` navigation, same limitation hit during the journey-map verification the day before). Output: 9 pages (matches target), 1.14MB, visually spot-checked by rendering cover + TUI-keybindings pages to PNG and inspecting directly — both matched the design system with accurate content. `vNEXT` version placeholder filled with the actual shipped version (`v0.13.0`, from `synlynk/_constants.py`) before merge.

**PR #853** was auto-opened by the dispatch finalizer with a generic title (`fix: ## Permissions (job-94bd0c6b)`) — title/body rewritten to describe the actual shipped work, `Closes #848` added for auto-close. Reviewed via the #423 COMMENT-checklist fallback (CI green on all 3 Python versions, `synlynk pr check` passed), squash-merged. Blog post (`docs/blog/101-pr853-watching-synlynk-guide.md`) committed in the same branch per protocol. Worktree and local dispatch branch cleaned up post-merge.

- Key calls: treating a dispatch job's "OK (exit 0)" self-report as a starting point, not proof, paid off again here — the invalid `<td>`-in-`<ul>` markup would have shipped broken list rendering on the live docs page if not caught in direct diff review. Fixing a small, single-file markup bug directly rather than re-dispatching kept the review loop fast without compromising the division-of-labor policy (the bug was a mechanical correction, not new implementation work).
