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


## v1.0.0 — GA: The Tokq Network & Commercial Launch [planned] (target: 2027-01-15)

Public commercial launch, P2P Agent Compute Rental, Tokq Decentralized Intelligence & Skill Marketplace, Proof of Real Work settlement, and Native Mobile/Data Platform domains

- [ ] P2P Agent Compute & Subscription Rental (Airbnb for AI Engineering) (P0)
  Monetize idle Apple Silicon compute and enterprise model subscriptions
- [ ] Tokq Decentralized Intelligence & Skill Marketplace (P0)
  Exchange for verified domain blueprints, AST graphs, datasets, and compliance charters
- [ ] Proof of Real Work (PoUW) Settlement Layer (P0)
  Dual-layer settlement: local credit ledger to L2 USDC micro-settlement
- [ ] Native Mobile & Data Platform Domain Expansion (P1)
  Specialized blueprints and AST tools for iOS (SwiftUI), Android (Jetpack), and dbt/SQL
- [ ] GitHub Open Source Infrastructure, Positioning & Docs Overhaul (P1)
  Contributor templates, community discussions, and comprehensive positioning refresh

## v1.1.0 — Cross-Workgroup (Team Level) [planned] (target: Q4 2026)

Relay → community server · cross-workgroup epics · agent entitlements

- [ ] GOVERNS Autonomous SDLC: Stage Progression, Charters, Attribution & Review Provenance (#2412) (P0) <!-- story:story-ee4529d9 -->
  Durable synthesis of 2026-09-27, 2026-10-02, 2026-10-16 deep reviews: fail-closed gates, stage policies, receipts contract, and role skill binding.
- [ ] Evidence-Gated Autonomy Dial & Supervised Gate Enforcement (P0)
  Enforce supervisor approval before auto-execution to prevent unreviewed daemon dispatches.
- [ ] Swarm Worker Leases & Distributed Worktree Locking (P1)
  Distributed lease manager preventing git index lock collisions during concurrent multi-agent sweeps.
- [ ] Multi-Repo Polyrepo Mesh & Personal Relay Federation (P1)
  Personal-use hosted NATS relay bridging local broker across devices and multi-repo boundaries (goal-f4ce526a).

## v1.2.0 — Enterprise Workspace [planned] (target: Q1 2027)

Cross-team · org-level governance agents · enterprise entitlements

- [ ] Role-Based Client IP Isolation & Ephemeral Worktree Boundary (P0)
  Air-gapped context packs and client repository isolation per engagement (dec-85a5a151).
- [ ] Multi-Account Delivery Playbook Factory & Template Library (P1)
  Reusable engagement accelerators, APQC/SFIA cross-account taxonomy mappings.
- [ ] SOC 2 Type II Security & Compliance Pack (P0)
  Encrypted telemetry redactor, immutable signed audit logs, and credential boundary.
- [ ] Tenant Workspace Policy Synchronization (P1)
  Central policy enforcement across customer accounts without manual drift.
- [ ] Human-in-the-Loop Change Control & Milestone Gating (P0)
  Formal stakeholder sign-offs for fixed-price, outcome-based, and regulated deliveries.

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


## 1.0.0 — Superseded: Developer Preview Public Launch (legacy alias) [superseded]

Superseded by the active v0.27.2-v0.27.5 daily stable stream under parent #2458. No separate v1.0.0 preview tag, RC/DEV/PROD channel, or public launch requirement is planned. The separate future GA arc v1.0.0 remains distinct.

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
- [ ] P0 Mandatory Architectural Invariants (Round 1 Consensus) (P0)
  Enforce 5 mandatory invariants from dec-20260927-round-1: (1) Effect-verified completion with non-empty diff & passed tests; (2) Hard in-flight token circuit breakers; (3) Fail-closed capability-probed routing; (4) One ledger, one writer state.db WAL; (5) Compressed default surface (Role+Harness, 3-5 stage GOVERNS). Release-blocking gate for v1.0.0 Dev Preview.

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

## v1.0.0-rc1 — Superseded: 15-Minute First Win Field Trials & Zero-Risk Install [superseded]

The RC tag is retired. First-win/onboarding work is scheduled in v0.27.1-v0.27.3; there is no parallel RC/DEV/PROD channel. Parent #2458; gated Developer Preview is v0.27.5 on 2026-11-06.

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


## v0.23.1 — Pre-Release Hygiene & Service Persistence [shipped] (target: 2026-10-04)

Worktree lifecycle cleanup (#1886), daemon service auto-install prompt (#1883), and ~25 ghost issue burndown

- [x] Stale Worktree Lifecycle GC (#1886) (P0)
  Prune leftover probe worktrees and auto-reap on doctor/dispatch
- [x] Daemon Auto-Install Service Prompt (#1883) (P0)
  Prompt and install launchd/systemd service during init and doctor
- [x] Ghost Issue Burndown (~25 remediated issues closed) (P1) <!-- story:story-9cbe4cf7 -->
  Systematically verify and close issues already fixed by recent PRs

## v0.24.0 — The Autonomous Platform, Boardroom & Concierge [shipped] (target: 2026-10-12)

Self-management core, Board governance, Jev AST decisioning, swarms, concierge, and turnkey add-ons

- [x] Tri-Modal Autonomy Dial (manual/supervised/autonomous) (P0) <!-- story:story-v024-t01-autonomy-dial -->
  Seamless switching across CLI, Vizor toggle, and local config
- [x] Board Governance Protocol & Vizor Boardroom HUD (P0) <!-- story:story-v024-t02-board-governance -->
  Nikhil Soman as Genesis Sponsor with veto power and milestone approval gates
- [x] Executable Agent Charters & Authority Matrix (P0) <!-- story:story-v024-t04-agent-charters -->
  Machine-readable charters in .synlynk/charters/ defining autonomous operating bounds
- [x] Jev Sub-20ms AST Decision Model (#1712) (P0) <!-- story:story-v024-t05-jev-engine -->
  Offline graph topological routing and merge gating before model dispatch
- [x] Parallel Worktree Swarms Engine (P1) <!-- story:story-v024-t06-swarm-engine -->
  Concurrent multi-agent execution DAGs with zero lock collisions
- [x] The Concierge Agent (synlynk concierge) (P1) <!-- story:story-v024-t07-concierge-agent -->
  Interactive feature ingress guide synthesizing structured GitHub issues and proposals
- [x] Turnkey Plug & Play Add-ons Engine (synlynk addon) (P1) <!-- story:story-v024-t08-addon-bundles -->
  Pre-vetted bundles for quality, security, and observability
- [x] Extended BYOK Product Registry (.synlynk/registry.json) (P1) <!-- story:story-v024-t09-byok-registry -->
  Configurable integration surface with encrypted local secrets vault
- [x] Autonomous Maintainer Zero-Issue Burndown Driver (P1) <!-- story:story-v024-t10-maintainer-burndown -->
  Continuous sweeping of open GitHub issues, driving open bugs to zero

## v0.25.0 — Sovereign Silicon: Local oMLX Fleet [deferred]

Deferred until after the first Developer Preview stable tag. Local harness (oMLX/Aider) is not a v0.25.x-v0.27.5 release gate; re-evaluate after Dev Preview. Parent #2458; related tickets #2525 and #2533.

- [ ] Local oMLX / Aider Harness Integration (#1710) (P0)
  Real subprocess dispatch to local MLX models (Llama-3, Qwen-2.5, DeepSeek)
- [ ] Apple Silicon Hardware Tier & Health Prober (P1)
  synlynk local doctor health check and hardware memory tier allocation
- [ ] Offline Zero-Cloud AST Tier-0 Routing (P1)
  Automatic fallback and tier-0 cost routing for self-hosted models

## v0.26.0 — Daemon reliability [planned] (target: 2026-10-28)

Daily stable gate: daemon restart, cancellation, recovery, scan containment, replay and stop idempotence are evidence-tested. Revalidate #2464 and #1884; #2477 stays closed without a new reproduction. Legacy provider/OpenRouter/Fal.ai/driver phase rows under this arc are not part of the daemon gate and remain non-authoritative pending freshness disposition via #2535 by the Oct 27 ticket lock. Parent #2458; release epic #2468; goals goal-bd5eaa14, goal-06758149, goal-eacab0dc.

- [ ] Universal Provider Aggregator Integration (#1711) (P0)
  BYOK gateway with provider fallback chains and latency optimization
- [ ] OpenRouter Single-Key Routing (DeepSeek, Qwen, Frontier) (P0)
  Unified access to top Chinese and open-weight models via single key
- [ ] Fal.ai Generative Media Provider Adapter (P1)
  Multimodal asset and media generation bridge
- [ ] Specialist 3rd-Party Driver Agents (@supabase, @vercel) (P1)
  Dedicated driver roles for cloud infrastructure automation

## v0.27.0 — VS Code and OpenVSX listing [planned] (target: 2026-11-01)

Daily stable gate: developer-surface listing/publication, install, update and dispatch smoke tests pass (#2103). Legacy Muse-GA and cross-harness review/cost phases under this arc are candidates for freshness disposition through #2535; they do not delay the listing gate absent a demonstrated dependency. Parent #2458; release epic #2471; goals goal-e3840370 and goal-85656c82.

- [ ] Meta Muse CLI Adapter GA Promotion (P0)
  Full promotion from experimental to first-class peer in fleet baseline
- [ ] Heterogeneous 5-Way Cross-Harness PR Review Routing (P1)
  Rotational non-author review across Claude, Codex, Agy, Grok, and Muse
- [ ] Muse Structured Output & Cost Ledger Integration (P1)
  Verified token extraction and dual-ledger cost reporting for Muse

## v0.25.2 — Stability baseline and accumulated PR reconciliation [shipped] (target: 2026-10-23)

Shipped 2026-10-23. Tag v0.25.2 is 4df4390da18d22070605d0cec6c4ddce11569863 and is origin/main. GitHub Release https://github.com/nikhilsoman/synlynk/releases/tag/v0.25.2 was published 2026-10-23T09:32:22Z by synlynk-synlynk-pm[bot]; it is not a draft and not a prerelease. Release metadata is #2549. Closed in this tag: #2448, #2449, #2450, #2291, and #2441, with catalog fix #2548. Already merged: #2530/#2539, #2532/#2538, #2537/#2544, and #2447/#2518. Muse onboarding stays on v0.25.3 (#2466). Local stays deferred (#2534). Parent #2458; release epic #2465; goals goal-3ef62232 and goal-005ea87d.

- [x] Daemon health fixes (gh:#2261, gh:#2288) (P0) <!-- story:story-e73fac9e -->
  Dormant re-exec bug + crash on stale worktree cwd blocking --requires-gh-write dispatch.
- [x] Wire daemon poll loop to autonomy pass (Task 4, gh:#2262) (P1) <!-- story:story-f67acd86 -->
  Daemon poll loop never calls _autonomy_pass(); backlog->schedule pipeline only runs via manual CLI today.
- [x] Cross-harness live discovery and explicit model validation (#2291) (P0) <!-- story:story-issue-2291 -->
  Delivery story is goal-3ef62232 and ticket #2291. Exit: supported harnesses reject stale explicit model IDs before a provider call.
- [x] Canonical harness-model data cleanup (#2447) (P0) <!-- story:story-f5d725cc -->
  Delivery story is goal-3ef62232 and ticket #2447. Exit: corrupted execution-log rows cannot contaminate harness model state.
- [x] Model candidate ingestion and freshness reliability (#2448) (P0) <!-- story:story-60eea2c4 -->
  Delivery story is goal-3ef62232 and ticket #2448. Exit: ingestion and timestamps preserve an auditable current catalog.
- [x] Authoritative resolution and catalog allowlist (#2449) (P0) <!-- story:story-a846f2a5 -->
  Delivery story is goal-3ef62232 and ticket #2449. Exit: resolution selects authoritative allowed sources only.
- [x] Fleet-wide model resolution invariants (#2450) (P0) <!-- story:story-54758ff8 -->
  Delivery story is goal-3ef62232 and ticket #2450. Exit: invariant tests cover model resolution across the supported fleet.

## v1.0.0-preview — Superseded: v1.0.0 Developer Preview [superseded]

Superseded by the gated v0.27.5 Developer Preview stable tag on 2026-11-06 under parent #2458. Do not cut a separate v1.0.0-preview tag or channel. Re-triage remaining stories using #2535 and the daily dependency sweep; no legacy phase row is implementation authority.

- [x] Phase 1A: Substrate Hardening & Hygiene (P0)
  Worktree fleet pruning, state.db vacuum (<30MB), sentinel 7-day TTL cleanup, and GenericAPIAdapter all complete.
- [x] Phase 1B: State & Task Drift Remediation across state.db, project-docs & PR Merges (#2413) (P0) <!-- story:story-ada9a71f -->
  Unify canonical state.db resolution, sprint-aware todo.md ordering, automated PR merge phase progression, and doctor drift audits.
- [x] Phase 2A: Open SFIA 8/9 Taxonomy & Historical Capability Backfill (P0)
  PR #2434 merged. SFIA 8/9 classifier, 1% attribution window, and backfill of 3,170 historical tasks across 102 active models.
- [x] Phase 2B & 2C: Synaptic AI Capability Index Public Service, Prompt Oracle & Preflight MCP (P0) <!-- story:story-5eecdf01 -->
  PR #2435 merged. Universal pre-flight routing engine, cryptographic capability pack export, glassmorphic Prompt Oracle UI, and @synlynk/preflight-mcp.
- [ ] Phase 2D: Standalone AWS Spot Docker Capability Crawler & Calibration Ranker (P0)
  Continuous public repo contribution & model evaluation loop running on AWS spot instances with dedicated budget (goal-aa48c456).
- [ ] Thin VS Code Client Extension Packaging & Marketplace Release (P0)
  Zero-dependency engine, Workspace Trust, native diff review, Doctor diagnostics, and VSIX packaging workflow (feat/agy/vscode-extension-design).
- [ ] Fast-Path Solo Dispatch Mode for Single-File Edits (P1)
  Low-overhead single-agent execution bypassing multi-agent review ceremony for low-risk, single-file tasks.
- [ ] 3-Agent Swarm Concurrency Trial (P1)
  Verify concurrent multi-agent execution DAGs across isolated leased worktrees with zero lock contention.
- [ ] Phase 3: Release Gate & Launch (P0)
  v1.0.0-rc1 tagging, PyPI Trusted Publishing, 4,500+ test suite pass, 15-min time-to-wow screencast, and milestone synthesis blog.

## v0.25.3 — Muse and model-capacity readiness [shipped] (target: 2026-10-24)

Daily stable gate: onboard Muse with authenticated, allowlisted, low-privilege execution; validate model catalog, capability and cost evidence across core harnesses. Quota truth may follow later in the cycle. Parent #2458; release epic #2466; goals goal-adb60ccc, goal-079e2f37, goal-eacab0dc.

Shipped 2026-10-24. Tag v0.25.3 is ce28b3b4f1ef2eda3432b706441d8d6187ac14b5 and is origin/main. GitHub Release https://github.com/nikhilsoman/synlynk/releases/tag/v0.25.3 was published by Nikhil (`gh release create`, native PM-session). Closed in this tag: #2554/#2562 (Muse implement/test readiness), #2552/#2560 (Codex tier-collapse fix), #2551/#2563 (`dispatch_rework_rate` replacing inert `pr_review_cycles`), #2170/#2570 (silent `quality_verified` fallback detection), #2567/#2568 (calibration diff base-SHA fix), #2553/#2564 (daemon pidfile crash fix). Quota/capacity truth for Muse and Grok deferred to a separately-scoped capability sweep, gh:#2576 — not addressed in this tag. Merged via PR #2575, non-authoring cross-harness (Codex) review+merge per the Hardened PR Review Policy. Parent #2458; release epic #2466.


## v0.25.4 — Accurate job status and completion evidence [planned] (target: 2026-10-25)

Daily stable gate: accurate, auditable job status and completion evidence, including GitHub-write outcomes. Revalidate #2138, #2139, #2309 and #2530 against current main. Folded in 2026-10-24: #2547 ([Epic] Harness velocity: RSI loops) — its timing/telemetry investigation across Claude/Codex/Agy/Grok/Muse in home and headless modes is evidence toward this release's job-status/completion-evidence gate, not a separate code change. #2547 itself keeps running independently and is not to be redirected or merged into other in-flight work; this entry only gives it a landing release so it isn't an untracked loose thread. Parent #2458; release epic #2467; goals goal-079e2f37, goal-9ef9a965, goal-eacab0dc.


## v0.26.1 — Workspace-agent charter and role operations [planned] (target: 2026-10-29)

Daily stable gate: workspace-agent charters, authority, SOPs and GOVERNS adherence are signed off and exercised; address #2305 where needed for enforceable role procedures. Parent #2458; release epic #2469; goals goal-eacab0dc, goal-a222b393, goal-06758149.


## v0.26.2 — Safe autonomous operations [planned] (target: 2026-10-30)

Daily stable gate: enforce claims/leases at work-start paths (#2511/#2528); approval, containment, audit and recovery controls pass before broader autonomy. Parent #2458; release epic #2470; goals goal-bd5eaa14 and goal-eacab0dc.


## v0.27.1 — Quickstart and onboarding first win [planned] (target: 2026-11-02)

Daily stable gate: fresh-project journeys reach a verified first dispatch in under 15 minutes; revise #1515/#2472 scope to exclude deferred public-announcement requirements. Parent #2458; release epic #2472; goals goal-e47ee312, goal-85656c82, goal-9ef9a965.


## v0.27.2 — Onboarding clarity and recovery [planned] (target: 2026-11-03)

Daily stable gate: install/update failure paths, prerequisites, harness choice and common errors are explained and verified end to end. Parent #2458; release epic #2473; goals goal-9ef9a965 and goal-85656c82.


## v0.28.0 — Swarms and Universal Gateway [planned]

Post-Preview scope; intentionally undated. Bounded swarm, gateway, lease, budget, containment and evidence controls. Do not block the first Developer Preview. Parent #2458; release epic #2474; goals goal-256d17d6, goal-8d34c416, goal-005ea87d.


## v0.28.1 — Capability crawler, index and GTM [planned]

Post-Preview scope; intentionally undated. Reproducible, privacy-safe, sample-floor-gated capability evidence and GTM surface. Parent #2458; release epic #2475; goals goal-aa48c456 and goal-20bb3987.


## v0.29.0 — Residual backlog consolidation [planned]

Post-Preview scope; intentionally undated. Triage residual candidates, promote/archive/hold with evidence, and record the human Dev Preview follow-up decision. Parent #2458; release epic #2476; goal goal-51c4be3f.


## v0.25.5 — CI and release-integrity stabilization [planned] (target: 2026-10-26)

Daily stable gate: resolve or evidence non-blocking dispositions for self-test/CI race #2527/#2526, release-doc count drift #2522, and generated command-doc/sparse-checkout blocker #2320. Parent #2458; release epic #2467.


## v0.25.6 — Stability closeout and ticket lock [planned] (target: 2026-10-27)

Daily stable gate: close GOVERNS/model/cost/job-truth stability review; every selected story has a goal, release epic and current ticket; all 94 ticketless candidates receive a linked or explicit deferred/archive disposition. Use governed phase-update ticket #2535; do not edit canonical DB rows directly. Parent epic #2458; milestone #14; goal goal-9ef9a965.


## v0.26.3 — End-to-end autonomous operating day [planned] (target: 2026-10-31)

Daily stable gate: workspace-agent roles plan, claim, dispatch, monitor, recover and produce truthful evidence for one bounded roadmap task; revalidate #2262 and adjacent job-orphan issues. Parent #2458; release epic #2470.


## v0.27.3 — Cross-harness onboarding verification [planned] (target: 2026-11-04)

Daily stable gate: five independent fresh-project journeys pass from install to useful, evidence-backed result, including Muse. Parent #2458; release epics #2471-#2473.


## v0.27.4 — Developer Preview acceptance run [planned] (target: 2026-11-05)

Daily stable gate: GOVERNS, model catalog/capability/cost, job-status truth, workspace-agent autonomy and quickstart/onboarding pass together. Parent #2458; release epics #2471-#2473.


## v0.27.5 — Developer Preview stable release gate [planned] (target: 2026-11-06)

Daily stable tag is the Developer Preview only when the v0.27.4 acceptance evidence is green and no unresolved release-blocking Sev1/Sev2 defect remains. Human release authority remains required. Parent #2458; release epics #2471-#2473.


