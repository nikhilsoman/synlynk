# Roadmap (generated - source of truth is state.db)
# Edit via: synlynk roadmap add | Do NOT hand-edit this file

## v0.1–v0.3.0 — Kernel + Filesystem [shipped] (target: June 2026)

exec · telemetry · flatline · budget · project-docs ledger · enriched templates


## v0.3.1 — Sentinel + Observability [shipped] (target: June 2026)

Token scraping · zombie/stall/quota/loop detection · burn rate · context bloat · sentinel severity + ack


## v0.4.0–v0.4.2 — Hybrid Workgroup + Instruction Reach + Task Status [shipped] (target: June 2026)

IPC · dispatch · job store · init wizard · IDE reach · SHA manifest · drift detection · 5-state task model


## v0.5.0–v0.6.1 — Capability Engine + Job Control [shipped] (target: June 2026)

Model-aware routing · 3D domain taxonomy · quality signals · SQLite WAL · constraint propagation · `synlynk story/score`


## v0.7.0 — Static Scan Quality [shipped] (target: June 2026)

Language-agnostic source scanner · `## Source Architecture` injection · `synlynk scan` · 369 tests


## v0.8.0 — Support Engineer Agent [shipped] (target: June 2026)

Maintainer archetype #1 · 5 signal collectors · 7/30-day dedup · foreground investigation · GH issue filing · draft fix PRs · `.agents/` config system


## v0.8.1–v0.8.4 — Agent Fleet (deferred) [deferred] (target: Post-GA)

TPM · Release · Marketing Intern · PM · Docs Keeper · Security Guard — full Autopilot fleet. Requires v1.0.0 community layer. Tracked as goals goal-0b891b5f / goal-f424fc4c rather than a v0.8.x slot.


## v0.9.0 — Kernel Fixes [shipped] (target: June 2026)

Scoped context · task→file mapping · verify contract · per-agent framing · Ed25519 wired · anti-gaming baseline (sample-count cap)


## v0.9.1 — Install Hardening + Docs Migration [shipped] (target: June 2026)

Install broken after package split fixed · `_docs_dir()` configurable · `--docs-dir` flag on init · smart doc migration from existing content


## v0.9.2 — Team Onboarding + Consensus [shipped] (target: June 2026)

`synlynk join` · team digest · write-arbitration · token budgets · `synlynk decide`


## v0.9.3 — Async Daemon [shipped] (target: June 2026)

`synlynk daemon` · launchd/systemd · job queue · HTTP context server localhost:27471


## v0.9.4 — Context / Dispatch / Relay [shipped] (target: June 2026)

SQLite-primary task state · per-agent context profiles (`.agents/<agent>.json`) · `synlynk jobs` SQLite read + `--watch` · pre-flight gate · HTTP SSE relay broker (`synlynk relay start/broadcast`) · VERIFY_SKIP sentinel · dispatch CWD + `--dangerously-skip-permissions` scoped to dispatch_flags


## v0.9.5 — Health Pulse [superseded]

Absorbed into v0.9.8 — all content (doctor, exit, repair, sync) landed in PR #70


## v0.9.6 — Exit + Repair + Sync [superseded]

Absorbed into v0.9.8 — OB-13/14/15/16/17 all shipped together


## v0.9.7 — Grok Agent Support [shipped] (target: June 2026)

Grok as first-class fourth agent peer · `AGENT_CAPABILITY_BASELINES["grok"]` · GROK.md template + `_INSTRUCTION_TARGETS` · init wizard expansion · `_inject_grok_rules()` exec context injection via `--rules` · dispatch `--always-approve` fallback · `extract_tokens` nested JSON pattern · 15 new tests · 488 total


## v0.9.8 — Health Pulse + Lifecycle [shipped] (target: Jun 2026)

`synlynk exit` · `synlynk repair` · `synlynk sync` · `_strip_synlynk_section()` · dry-run by default · `SYNLYNK_HANDOFF.md` write · closes OB-13–17 · 13 new tests · 524 total


## v0.9.9 — LIVE-1 Fixes + Harness Compatibility System (BS-14) [shipped] (target: Jul 2026)

**Phase 1 — LIVE-1 hardening:** Agy `--non-interactive` baseline fix (caused 6h silent hang) · Grok `--always-approve` removed from dispatch path · `_check_job_stall()`: per-agent timeout + SIGKILL + `STALL_NO_OUTPUT` sentinel · `_preflight_dispatch()`: flag validation + network socket check → `HARNESS_PREFLIGHT_FAIL` sentinel · **Phase 2 — Harness Compatibility:** 5 new `state.db` tables (`harness_baselines`, `harness_records`, `harness_verb_map`, `harness_command_palette`, `harness_version_history`) · `synlynk probe` (version fingerprint → fast-path → upsert → palette scan → fence write) · `synlynk doctor` TC-1–TC-4 compliance suite · 64-row Command Interoperability Matrix · `_upsert_harness_fence()` · `HARNESS_VERSION_DRIFT` sentinel · `harness` + `model` in `.agents/<agent>.json` · PR #82 · 503 tests


## v0.10.0 — Developer Preview [shipped] (target: Jul 2026)

**Scope: installable + daily driver.** P0: `pyproject.toml` + `pipx install git+<url>` · first-run polish (`synlynk help`, actionable errors) · README overhaul · `synlynk migrate` (project-docs/ → state.db, git rm --cached, gitignore). P1: BS-12a agent role formalization · `synlynk release` Ship cycle stub (VERSION bump + CHANGELOG + blog stub) · `synlynk status` platform health (harness compliance + agent availability + budget pulse). P2: job completion summary (post-dispatch UX). BS-19 `synlynk launch` task picker · BS-20 deep scan pipeline · BS-21 `synlynk viz` browser dashboard.


## v0.11.0 — Agent Ecosystem Operational Layer [shipped] (target: Jul 2026)

`chore/modularise-init` (`__init__.py` 11K→1.5K, 5 modules extracted) · BS-16 `synlynk status` + `--json` ecosystem snapshot · TC-2 fix arc · BS-13 `synlynk watch --live` + Vizor Observatory tab · BS-22 Vizor Efficiency (R/W/T bars + cycle matrix + radar SVGs) · BS-12 Agent Autonomy Bridge (permission grants + harness config + handoff protocol + doctor wizard + SOP codification) · 868 tests


## v0.12.0 — Trust & Cost-Aware Routing [shipped] (target: Jul 2026)

Fable H0 gate: "every number synlynk displays is either structurally sourced or visibly labeled as an estimate." Measurement Ledger Hardening epic (#210) — provenance-tagged `cost_entries` (Phase 1, PR #236/#241/#242), per-agent structured-output adapters replacing regex token-scraping for all four agents (Phase 2, PR #244/#245 Codex, #252 Claude, #256 Agy, #257 Grok), Vizor Effort & Cost tab estimated-vs-actual flagging (#258, PR #264), and `synlynk status` surfacing `rates_updated_at` (#259, PR #266). Epic #210 fully closed 2026-07-15. See **Measurement Ledger Hardening** row below for full epic status.


## v0.13.0 — State Engine Tier 1 [shipped]

SQLite-canonical project-docs, GOVERNS events, dual-ledger write-through. Followed by v0.13.1 operational reliability patch.


## v1.0.0 — GA: Community Layer + Public Launch [planned] (target: post-preview)

Distinct from 1.0.0 Developer Preview. Workgroup protocol · signed capability ledger · SME archetype · pipx/Homebrew PyPI · synlynk.com (BS-5). Sequencing: after preview tag; Wave 3/4 deliver the hosted and model-hub slices.


## v1.1.0 — Cross-Workgroup (Team Level) [planned] (target: Q4 2026)

Relay → community server · cross-workgroup epics · agent entitlements


## v1.2.0 — Enterprise Workspace [planned] (target: Q1 2027)

Cross-team · org-level governance agents · enterprise entitlements


## v1.3.0 — Domain/Discipline Communities [planned] (target: Q2 2027)

Broader communities · Tokq convergence · MCP / Open Context Protocol


## epic-job-truth-2026-08 — Job Truth + GH-write Identity (Epic A/B) [shipped] (target: 2026-08)

Plan: docs/superpowers/plans/2026-08-09-job-truth-and-gh-write-epics.md. A0–A3 and B0/B1 shipped. B3 MCP/review reliability deferred. Linked goal-bde24050 marked done 2026-09-25.

- [x] A0 windowed sentinel_crit (#751 / PR #762) (P1) <!-- story:story-issue-762 -->
  ops scoreboard no longer CRITICAL-flooded by ancient sentinel.md lines
- [x] A0 jobs reap + auto-reap STALL/TIMEOUT (#753 / PR #772) (P1) <!-- story:story-issue-772 -->
  zombie running jobs reaped; timed_out path
- [x] Companion: context_mode/bytes telemetry (PR #835) (P2) <!-- story:story-issue-835 -->
  persist context_mode + context_bytes on jobs/costs
- [x] Companion: fresh --base origin tip (#832 / PR #854) (P1) <!-- story:story-issue-854 -->
  dispatch --base main fetches origin before branch create
- [x] B0/B1 GH-write fail-closed + role Apps (#569 / PR #857, #859) (P0) <!-- story:story-issue-857 -->
  fail-closed without App token; GH_TOKEN + GH_CONFIG_DIR isolation; Apps provisioned
- [x] A1 daemon_jobs GTV on reconcile (#331/#579 / PR #867) (P0) <!-- story:story-issue-867 -->
  terminal status matches process+git; zombie_running ops finding
- [x] A2 cost completeness for terminal jobs (#752 / PR #868) (P0) <!-- story:story-issue-868 -->
  jobs_missing_cost ops finding + ensure cost_entries on preferred-summary path
- [x] A3 fill dispatch_context home|headless (#740) (P1) <!-- story:story-issue-740 -->
  PR #926 shipped real home|headless detection
- [x] B2 Codex sandbox / GH-write routing (#577) (P2)
  Closed as investigation-complete (2026-08-13): root-caused to Codex workspace-write sandbox blocking api.github.com egress structurally, not an identity/token bug. Recommended B2-A fail-closed routing design, not yet implemented as code.
- [-] B3 MCP/review reliability with real identity (#659) (P2)
  reduce cancel/flake once B1 identity is the primary control

## Future Expansions — Workspace-level (multi-repo) agent identities [planned] (target: TBD)

gh:#914 — cross-repo App scope (single App installed on multiple repos), cross-repo ticket implications, workspace-level shared GitHub Projects V2 board, and broader operational implications of cross-repo Agent access under one identity_slug workspace (e.g. vdowrx). Builds on the isolated per-repo identity model (docs/superpowers/specs/2026-08-11-autonomous-ops-program-design.md) and the identity_slug naming override (PR #912/#910). Not yet scoped — brainstorm/design spec required before implementation per Brainstorm-First Policy.


## v0.13.1 — Operational reliability patch: GOVERNS events, rollback, DB-canonical docs, TC-6 gh-auth doctor [shipped]

Patch release (rescoped from planned v0.14.0 minor — Agent/Harness terminology Phase 0 and Quota-Aware Dispatch Reservation held back as incomplete/inactive per PM review 2026-08-13). Ships GOVERNS event-contract extension (#922), init/migrate/upgrade rollback (Leg 1+2), State Engine PR1, doctor TC-6 gh-auth check (#928), B3 cancellation RCA (#929/#714).


## v0.15.0 — Workspace Policy Layer [shipped] (target: 2026-08-23)

Two-tier policy.json (workspace defaults + repo overrides), check_authority() gates on dispatch/release/roadmap/goal actions, synlynk policy check-merge/sync-branch-protection/show commands. Branch protection live-verified on synlynk's own repo (gh:#1122, plan docs/superpowers/plans/2026-08-23-workspace-policy-and-autonomous-loop.md, Tasks 1-9). Precedes v0.16.0 Autonomous Loop (Tasks 10-13).


## 1.0.0 — Developer Preview Public Launch [planned] (target: 2026-10-01)

Public GitHub tag v1.0.0 is NOT cut yet. Ceremony: synlynk.com collateral, HN/Product Hunt (#1515), book excerpt (#1514). Wave 1 implementation is done; this arc is the launch event.

- [ ] P0 Foundation and reset (P0)
  Reconcile main/origin, stale worktrees, daemon/runtime, sentinel noise, and release blockers. Establish a clean baseline and freeze non-launch work.
- [ ] P0 Install and first-win path (P0)
  Validate pipx/install.sh or chosen distribution, zero-risk init, dependency checks, browser handoff, and a timed fresh-project-to-first-dispatch journey under 15 minutes.
- [ ] P0 Existing-project intelligence (P0)
  Make scan/deep-scan produce an evidence-backed project brief: architecture, health, risks, directional approaches, and discussion-ready recommendations without user involvement.
- [ ] P0 Vizor onboarding and GitHub App flow (P0)
  Decide and implement browser-first onboarding: local Vizor bootstrap, secure GitHub App creation/configuration handoff, callback/token boundaries, and CLI fallback. Validate whether browser flow materially reduces setup friction.
- [ ] P0 Autonomous goal-forming brainstorm (P0)
  Let Synlynk lead a bounded brainstorm from project evidence to a small set of durable goals, with user reserved only for strategic approval gates and explicit commitments.
- [ ] P1 End-to-end autonomy field trial (P1)
  Run fresh-install trials across representative repositories; measure time-to-wow, successful project brief generation, brainstorm completion, dispatch/review truth, recovery, and user drop-off.
- [ ] P0 Release candidate and announcement (P0)
  Cut v1.0.0 developer preview, publish install/docs/demo assets, prepare HN and Product Hunt copy, verify support/rollback/runbook, obtain final human launch approval, then announce.

## v0.19.0 — Foundation, State Reconciliation & Platform Health [shipped] (target: 2026-09-11)

Named release v0.19.0. Dual-ledger sync, daemon lock recovery, probe --no-fence.

- [x] Layered Branching Topology (unstable, staging, main) (P0)
  Establish 4-tier release branches and CI workflow gating
- [x] Control Plane Hardening & Dual-Ledger Sync (#1535, #1537) (P0)
  Dual-ledger write-through sync and daemon stale lock recovery
- [x] Probe Cleanliness & Orphan Worktree Triage (#1538, #1487) (P0)
  Probe --no-fence flag to prevent doc churn; triage 48 orphaned branches

## v0.16.0 — Autonomous Loop & Self-Healing [shipped] (target: 2026-08-27)

Background daemon supervision, zombie job reconciliation, automated gap remediation (synlynk heal)


## v0.17.0 — Ticket-Driven Approval Auto-Resume [shipped] (target: 2026-08-29)

Approval tickets in state.db, non-blocking milestone execution loop, auto-resume past approval gates


## v0.18.0 — Role GitHub Apps & QA Merge Gate Authority [shipped] (target: 2026-08-31)

Role GitHub App integration (synlynk gh --role), block-only QA merge gate, Codex GitHub-write parity, Agy prompt cache telemetry


## v0.20.0 — BS-6 Workspace Views & Deep Repo Intelligence [shipped] (target: 2026-09-19)

Named release v0.20.0. BS-6 visualizer, unattended milestone loop, deep scan brief, event-driven launch DAG.

- [x] Unattended Milestone Execution Loop (synlynk run --milestone) (P0)
  DAG-driven story runner across isolated worktrees without chat pauses
- [x] Asynchronous Escalations via Assigned GitHub Issues (P0)
  File assigned issues to @nikhilsoman when blocked; auto-skip to parallel stories
- [x] BS-6 Workspace Views & Real-time Canvas (#1539) (P0)
  SVG diagram generator and terminal/browser visualizer canvas
- [x] Harness Specialization & Diagnostic Circuit Breakers (P1)
  Role matrix routing + >3 turn diagnostic churn auto-handoff

## v1.0.0-rc1 — 15-Minute First Win Field Trials & Zero-Risk Install [planned] (target: 2026-10-01)

pipx distribution, 15-min wow journey across 3 target repos, browser Vizor onboarding, autonomous goal brainstorm, test suite runtime remediation (#1492). Aligned with 1.0.0 Developer Preview date.

- [ ] Zero-Risk Packaging & Standalone Distribution (pipx) (P0)
  Single-command installable package without environment conflicts
- [ ] Autonomous Existing-Project Deep Scan & Brief (P0)
  Evidence-backed architecture, health, and risks brief without human steering
- [ ] 15-Minute Time-to-Wow Field Trials Across 3 Target Repos (P0)
  End-to-end trials measuring install-to-first-PR in <15 minutes
- [ ] Test Suite Runtime Remediation (#1492) (P0)
  pytest-xdist parallel test execution to drop CI runtime below 180s

## v0.21.0 — Autonomous Multi-Home & Teams Relay Mesh [shipped] (target: 2026-09-23)

Wave 1 remaining pillars + Wave 2 P2P relay, distributed leases, AST mesh collision, 3-tier identity. CHANGELOG v0.21.0.


## v0.22.0 — Multi-Workspace Vizor Hub & Resilient State Isolation [shipped] (target: 2026-09-24)

Named release v0.22.0. Multi-workspace hub UI, HEAD routing, DB_PATH guard, sandbox migration resilience. PRs #1758–#1761.


## v0.23.0 — Graphify Auto-Extraction & Vizor Unified Canvas [shipped] (target: 2026-09-25)

scan --deep / upgrade auto-extract; synlynk mesh federated graphs; Vizor graphify.html + clustered Architect/Logical canvas. PR #1777. GOVERNS board + dual-pivot Gantt #1771.


