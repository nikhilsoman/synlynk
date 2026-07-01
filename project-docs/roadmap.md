# synlynk Roadmap

**Positioning:** The OS for multi-agent development.  
**Realignment spec:** `docs/superpowers/specs/2026-06-21-synlynk-roadmap-realignment-design.md`  
**Realigned:** 2026-06-21 (workgroup consensus: Claude + AGY + Codex + Nikhil)

## Version Arc

| Version | Theme | OS Layer | Status | Target |
| :--- | :--- | :--- | :--- | :--- |
| v0.1–v0.3.0 | Kernel + Filesystem | exec · telemetry · flatline · budget · project-docs ledger · enriched templates | ✅ Shipped | June 2026 |
| v0.3.1 | Sentinel + Observability | Token scraping · zombie/stall/quota/loop detection · burn rate · context bloat · sentinel severity + ack | ✅ Shipped | June 2026 |
| v0.4.0–v0.4.2 | Hybrid Workgroup + Instruction Reach + Task Status | IPC · dispatch · job store · init wizard · IDE reach · SHA manifest · drift detection · 5-state task model | ✅ Shipped | June 2026 |
| v0.5.0–v0.6.1 | Capability Engine + Job Control | Model-aware routing · 3D domain taxonomy · quality signals · SQLite WAL · constraint propagation · `synlynk story/score` | ✅ Shipped | June 2026 |
| v0.7.0 | Static Scan Quality | Language-agnostic source scanner · `## Source Architecture` injection · `synlynk scan` · 369 tests | ✅ Shipped | June 2026 |
| v0.8.0 | Support Engineer Agent | Maintainer archetype #1 · 5 signal collectors · 7/30-day dedup · foreground investigation · GH issue filing · draft fix PRs · `.agents/` config system | ✅ Shipped | June 2026 |
| **v0.8.1–v0.8.4** | Agent Fleet (deferred) | TPM · Release · Marketing Intern · PM · Docs Keeper · Security Guard — full Autopilot fleet. Requires v1.0.0 community layer (workgroup protocol, signed ledger) to be meaningful. Renumbered → v1.1.x–v1.2.x. | 📦 Deferred → v1.1–1.2 | Post-GA |
| **v0.9.0** | Kernel Fixes | Scoped context · task→file mapping · verify contract · per-agent framing · Ed25519 wired · anti-gaming baseline (sample-count cap) | ✅ Shipped | June 2026 |
| **v0.9.1** | Install Hardening + Docs Migration | Install broken after package split fixed · `_docs_dir()` configurable · `--docs-dir` flag on init · smart doc migration from existing content | ✅ Shipped | June 2026 |
| **v0.9.2** | Team Onboarding + Consensus | `synlynk join` · team digest · write-arbitration · token budgets · `synlynk decide` | ✅ Shipped | June 2026 |
| **v0.9.3** | Async Daemon | `synlynk daemon` · launchd/systemd · job queue · HTTP context server localhost:27471 | ✅ Shipped | June 2026 |
| **v0.9.4** | Context / Dispatch / Relay | SQLite-primary task state · per-agent context profiles (`.agents/<agent>.json`) · `synlynk jobs` SQLite read + `--watch` · pre-flight gate · HTTP SSE relay broker (`synlynk relay start/broadcast`) · VERIFY_SKIP sentinel · dispatch CWD + `--dangerously-skip-permissions` scoped to dispatch_flags | ✅ Shipped | June 2026 |
| ~~**v0.9.5**~~ | ~~Health Pulse~~ | Absorbed into v0.9.8 — all content (doctor, exit, repair, sync) landed in PR #70 | 📦 Retired → v0.9.8 | — |
| ~~**v0.9.6**~~ | ~~Exit + Repair + Sync~~ | Absorbed into v0.9.8 — OB-13/14/15/16/17 all shipped together | 📦 Retired → v0.9.8 | — |
| **v0.9.7** | Grok Agent Support | Grok as first-class fourth agent peer · `AGENT_CAPABILITY_BASELINES["grok"]` · GROK.md template + `_INSTRUCTION_TARGETS` · init wizard expansion · `_inject_grok_rules()` exec context injection via `--rules` · dispatch `--always-approve` fallback · `extract_tokens` nested JSON pattern · 15 new tests · 488 total | ✅ Shipped | June 2026 |
| **v0.9.8** | Health Pulse + Lifecycle | `synlynk exit` · `synlynk repair` · `synlynk sync` · `_strip_synlynk_section()` · dry-run by default · `SYNLYNK_HANDOFF.md` write · closes OB-13–17 · 13 new tests · 524 total | ✅ Shipped | Jun 2026 |
| **v0.9.9** | LIVE-1 Fixes + Harness Compatibility System (BS-14) | **Phase 1 — LIVE-1 hardening:** Agy `--non-interactive` baseline fix (caused 6h silent hang) · Grok `--always-approve` removed from dispatch path · `_check_job_stall()`: per-agent timeout + SIGKILL + `STALL_NO_OUTPUT` sentinel · `_preflight_dispatch()`: flag validation + network socket check → `HARNESS_PREFLIGHT_FAIL` sentinel · **Phase 2 — Harness Compatibility:** 5 new `state.db` tables (`harness_baselines`, `harness_records`, `harness_verb_map`, `harness_command_palette`, `harness_version_history`) · `synlynk probe` (version fingerprint → fast-path → upsert → palette scan → fence write) · `synlynk doctor` TC-1–TC-4 compliance suite · 64-row Command Interoperability Matrix · `_upsert_harness_fence()` · `HARNESS_VERSION_DRIFT` sentinel · `harness` + `model` in `.agents/<agent>.json` · PR #82 · 503 tests | ✅ Shipped | Jul 2026 |
| **v0.10.0** | **Developer Preview** | Named Release milestone · `pipx install git+<url>` support · `pyproject.toml` packaging · first-run polish · README overhaul · `synlynk viz` product view (BS-6) · HN + dev.to launch post | 📋 Planned | Jul/Aug 2026 |
| **v1.0.0** | **GA: Community Layer + Public Launch** | Workgroup protocol · signed capability ledger · SME archetype · game-resistant scoring · pipx/Homebrew PyPI · synlynk.com (BS-5) · Multi-repo workspace | 📋 Planned | Sep 2026 |
| **v1.1.0** | Cross-Workgroup (Team Level) | Relay → community server · cross-workgroup epics · agent entitlements | 📋 Planned | Q4 2026 |
| **v1.2.0** | Enterprise Workspace | Cross-team · org-level governance agents · enterprise entitlements | 📋 Planned | Q1 2027 |
| **v1.3.0** | Domain/Discipline Communities | Broader communities · Tokq convergence · MCP / Open Context Protocol | 📋 Planned | Q2 2027 |

## Agent Archetype Model

Four archetypes, deployed at any community level:

| Archetype | Trigger | Examples |
| :--- | :--- | :--- |
| 🔧 Maintainers | Schedule · push · CI | Support Engineer ✅ · Security Guard · Compliance Officer · Incident Responder |
| 📣 Communicators | Release · merge · schedule | Marketing Intern · Docs Keeper · Changelog Publisher · Community Manager |
| 🎯 Orchestrators | Story events · signals · budget thresholds | PM Agent · Growth Scout · Sprint Captain · Budget Sentinel |
| 🧠 SMEs | Domain tag · file path · `synlynk consult` | Security SME · Architecture SME · Performance SME · Data SME |

## Strategic Initiatives

| Initiative | Theme | Status | Spec |
| :--- | :--- | :--- | :--- |
| Synlynk Autopilot | Agent fleet (TPM, Marketing, PM, Docs, Security) as autonomous eyes & ears | 📋 Post-GA (v1.1+) — requires community layer workgroup protocol | `docs/superpowers/specs/2026-06-21-synlynk-roadmap-realignment-design.md` |
| Community Layer | Local workgroup → team → enterprise → domain communities | 📋 v1.0.0 | Same |
| Public Presence | synlynk.com · public blog (Marketing Intern) · contributor blog in GitHub | 📋 v1.0.0 | Same |
| Server-Side Strategy | Relay prototype v0.9.3 → community server v1.1 → Tokq v1.3 | 📋 Articulated, implement v1.1+ | Same |
| GitHub Projects V2 Board Sync | state.db is canonical; board is a human-readable projection. `synlynk sync --board github` pushes story status via `external_refs` table. Agents never write to the board directly. Current `--project-id` flag is a placeholder only — no bidirectional sync exists yet. Implement post-v0.10.0. | 📋 Post-v0.10.0 | memory.md: "GitHub Projects V2 — agentic-first decision" |

## Cross-Cutting Epics

Design and engineering work that spans multiple version milestones. These epics run in parallel with the version arc above — they are not tied to a single release.

| Epic | Theme | ID Range | Status | Drives |
| :--- | :--- | :--- | :--- | :--- |
| **DevX** | Context-layer migration · task tracking canon · dispatch observability · usage model clarity | DevX-1–4 | ✅ Complete — shipped in v0.9.4 | v0.9.4 relay design, `generate_context()` hybrid read |
| **Command Audit** | 9-dimension command health review · stdlib OTel tracer · `synlynk telemetry` · hook wiring · autopilot trigger map | CA-0–9 | 📋 Planned — v0.9.4 scope | OTel infrastructure, CA-4/CA-5 ship with relay |
| **Agent Behaviour** | Instruction attach + compliance measurement · sentinel non-adherence patterns · per-agent variance · cross-mode adherence dataset · agent-encounters-synlynk conflict taxonomy · instruction coexistence strategy · authority framing study | AB-0–14 | 📋 AB-11/12/13 folded into BS-7 (2026-06-27); **BS-14 brainstorm pulled forward to next session (2026-06-28)** — LIVE-1 (#81) surfaced concrete harness incompatibilities (Agy stdout hang, Grok flag contamination, 6h stall no sentinel) accelerating this from pre-GA to immediate | v1.0 IDE integration argument, capability ratings, instruction coexistence |
| **Onboarding** | `synlynk doctor` · agent availability state machine · mode taxonomy rewrite · progressive init · join vs resume split · multi-repo stopgap · `synlynk exit` · `synlynk repair` · `synlynk sync` | OB-0–17 | 📋 Planned — OB-7/OB-9 patch in v0.9.4, full rewrite post-v0.9.4; OB-13/14/15 (exit+repair) and OB-16/17 (sync) in v0.9.6 | First-run success metrics, `synlynk agents` subcommand, lifecycle completeness |
| **Website Redesign** | Standalone design-first site — replace current functional/docs-dump with a product-story-led experience; visual identity, hero narrative, feature storytelling | BS-5 | 🎨 Design complete (2026-06-27) — full-page mockup + isometric motherboard diagram approved; implementation next session (~1 week) | Public launch readiness, v1.0 community layer |
| **Skill Pack Interoperability + Benchmarks** | Prove synlynk enhances (not fights) skill packs (Superpowers, GStack) · 4-round benchmark: base → Superpowers → synlynk → synlynk+Superpowers · GStack in conflict taxonomy (Phase 0 validation) · `flatline` as benchmark target · `git-drift` as coexistence enforcement artifact · Narrative: "coordination OS + domain expertise modules = better together" · Benchmark results as HN launch asset | BS-7 | 🎨 Design complete (2026-06-27) — spec: `docs/superpowers/specs/2026-06-27-bs7-skill-pack-interoperability-design.md` · Phase 0 validation + benchmark execution week of 2026-06-30 | Dev preview launch narrative; AB-11 instruction coexistence; community/plugin ecosystem |
| **Trio Orchestration Demo** | Scripted qualitative showcase: Demo 1 — state continuity across quota swap (Claude→Agy) · Demo 2 — Flatline Sentinel vs. GStack/Superpowers loop · Demo 3 — parallel dispatch + Ed25519 signed consensus · Token/cost scorecard · Proposal: `docs/proposals/demo-projects/showcase_project_proposal.md` | BS-9 | 📋 Brainstorm queued | Dev preview launch video/blog; v0.10.0 narrative |
| **PulseScape** | End-to-end product built by the agent team: glassmorphic real-time dashboard · SSE relay event stream · Ed25519 consensus panel · 6-session build across frontend (canvas/CSS), backend (FastAPI + SQLite), QA · branch safety proof · Proposal: `docs/proposals/demo-projects/end_to_end_product_proposal.md` | BS-10 | 📋 Brainstorm queued | Showcase artifact; v1.0.0 community layer demo |
| **MCP Registry Contribution** | Project Context + Todo MCP Server for `modelcontextprotocol/servers` — any MCP-compliant client (Claude Code, Cursor, Windsurf) reads/writes synlynk project state natively via tool calls · Proposal: `docs/proposals/demo-projects/public_utility_proposals.md` | BS-11 | 📋 Brainstorm queued | Ecosystem distribution; v1.0.0 community layer |
| **Public Utilities** | Standalone pip-installable tools extracted from synlynk primitives: `flatline` (loop circuit-breaker) · `git-drift` (instruction drift auditor, pre-commit hook) · `git-connectome` (codebase dep graph → self-contained HTML, feeds `synlynk viz`) · All three independently useful with zero synlynk dependency | — | 📋 Design in BS-7 (git-drift) + BS-6 (git-connectome); `flatline` standalone spec pending | Pre-launch community assets; HN/dev.to launch hooks |
| **Project Intelligence: OKF + Visualization** | Expanded scope: OKF alignment (frontmatter in project-docs, `synlynk export --okf`, interop with Obsidian/MkDocs) · Three-view viz (`synlynk viz`): **Product view** (UX screen graph, consumer-centric) · **Logical view** (component breakdown) · **Infra view** (network + cloud stack) · Cytoscape.js self-contained HTML approach (stolen from OKF viz.html) · New POV for dev onboarding — break free from code-tree-only project understanding; anyone-can-be-a-dev narrative | BS-6 | 📋 Brainstorm queued 2026-06-27 (story-f5513a93) — pre-session: dispatch Agy to write `docs/okf_assessment.md`; consolidate with Claude assessment | `synlynk workspace` (v0.10.0), dev adoption, public launch narrative |
| **Harness Compatibility** | Goal: synlynk equally effective regardless of entry harness · headless execution contract per agent (stdout flushing, PTY vs pipe, network deps) · per-agent dispatch flag map in `.agents/<agent>.json` · compliance test suite · `STALL_NO_OUTPUT` sentinel · `HARNESS_PREFLIGHT_FAIL` sentinel · `HARNESS_VERSION_DRIFT` sentinel · Command Interoperability Matrix · instruction fence · palette scan | BS-14 | ✅ **Shipped** — PR #82 merged 2026-07-01 · v0.9.9 · 503 tests · blog post 34 | Cross-harness parity; LIVE-1 closed; `synlynk probe` + `synlynk doctor` TC-1–TC-4 |
| **Live Job Observatory** | htop/mtop-style `synlynk watch` for every running job across repos, refreshed in near real time (~10s); group by repo and stage, show elapsed time plus cost, tokens, and requests; terminal and web boards share one read-only monitoring model, with top-level links out to the relevant terminal/web target only | BS-13 | 📝 Spec drafted — `docs/superpowers/specs/2026-06-28-bs13-live-job-observatory-design.md` | `synlynk watch`, `synlynk viz`, multi-repo monitoring |
