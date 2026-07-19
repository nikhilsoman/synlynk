
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
