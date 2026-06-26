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
| **v0.9.5** | Health Pulse | Silent per-command auditor: version nudge · onboarding completeness · agent profiles · identity key · team pulse · `synlynk doctor` command · registry-based `HealthCheck` dataclass · condition-gated + time-gated suppression | 📋 Planned | Jul 2026 |
| **v0.9.6** | Exit + Repair + Sync | `synlynk exit` — reverse all onboarding actions, generate handoff doc, leave repo synlynk-free · `synlynk repair` — exit + rebuild from handoff doc · `synlynk sync` — propagate new init artifacts to existing repos without re-init (daemon plist, relay config, `.agents/` profiles, updated instruction sections) · dry-run by default, --confirm to execute | 📋 Planned | Jul 2026 |
| **v0.9.7** | Grok Agent Support | Grok as first-class fourth agent peer · `AGENT_CAPABILITY_BASELINES["grok"]` · GROK.md template + `_INSTRUCTION_TARGETS` · init wizard expansion · `_inject_grok_rules()` exec context injection via `--rules` · dispatch `--always-approve` fallback · `extract_tokens` nested JSON pattern · 15 new tests · 488 total | ✅ Shipped | June 2026 |
| **v0.9.8** | Health Pulse + Lifecycle | `synlynk doctor` · registry-based `HealthCheck` · version nudge · onboarding completeness · agent profile gaps · identity key status · `synlynk exit` / `repair` / `sync` (OB-13–17) | 📋 Planned | Jul 2026 |
| **v0.10.0** | **Developer Preview** | Named Release milestone · `pipx install git+<url>` support · `pyproject.toml` packaging · first-run polish · README overhaul · `synlynk viz` product view (BS-6) · HN + dev.to launch post | 📋 Planned | Jun/Jul 2026 |
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

## Cross-Cutting Epics

Design and engineering work that spans multiple version milestones. These epics run in parallel with the version arc above — they are not tied to a single release.

| Epic | Theme | ID Range | Status | Drives |
| :--- | :--- | :--- | :--- | :--- |
| **DevX** | Context-layer migration · task tracking canon · dispatch observability · usage model clarity | DevX-1–4 | ✅ Complete — shipped in v0.9.4 | v0.9.4 relay design, `generate_context()` hybrid read |
| **Command Audit** | 9-dimension command health review · stdlib OTel tracer · `synlynk telemetry` · hook wiring · autopilot trigger map | CA-0–9 | 📋 Planned — v0.9.4 scope | OTel infrastructure, CA-4/CA-5 ship with relay |
| **Agent Behaviour** | Instruction attach + compliance measurement · sentinel non-adherence patterns · per-agent variance · cross-mode adherence dataset · agent-encounters-synlynk conflict taxonomy · instruction coexistence strategy · authority framing study | AB-0–14 | 📋 Planned — AB-11/12/13 added 2026-06-24 from Agy rxcc conflict observation; starts with AB-11 (conflict taxonomy) in BS-3 brainstorm | v1.0 IDE integration argument, capability ratings, instruction coexistence |
| **Onboarding** | `synlynk doctor` · agent availability state machine · mode taxonomy rewrite · progressive init · join vs resume split · multi-repo stopgap · `synlynk exit` · `synlynk repair` · `synlynk sync` | OB-0–17 | 📋 Planned — OB-7/OB-9 patch in v0.9.4, full rewrite post-v0.9.4; OB-13/14/15 (exit+repair) and OB-16/17 (sync) in v0.9.6 | First-run success metrics, `synlynk agents` subcommand, lifecycle completeness |
| **Website Redesign** | Standalone design-first site — replace current functional/docs-dump with a product-story-led experience; visual identity, hero narrative, feature storytelling | BS-5 | 📋 Brainstorm queued (story-048f5fe5) | Public launch readiness, v1.0 community layer |
| **Skill Pack Interoperability + Benchmarks** | Prove synlynk enhances (not fights) skill packs (Superpowers, GStack, GSD, Everything-ClaudeCode) · 4-round benchmark: base → skill packs → synlynk → synlynk+skill packs · Token bloat reduction via context scoping · Coexistence with `synlynk:start/end` instruction blocks · Narrative: "coordination OS + domain expertise modules = better together" · Benchmark results as pre-launch asset | BS-7 | 📋 Brainstorm queued 2026-06-28/29 — benchmark execution week of 2026-06-30 | Dev preview launch narrative; AB-11 instruction coexistence; community/plugin ecosystem |
| **Project Intelligence: OKF + Visualization** | Expanded scope: OKF alignment (frontmatter in project-docs, `synlynk export --okf`, interop with Obsidian/MkDocs) · Three-view viz (`synlynk viz`): **Product view** (UX screen graph, consumer-centric) · **Logical view** (component breakdown) · **Infra view** (network + cloud stack) · Cytoscape.js self-contained HTML approach (stolen from OKF viz.html) · New POV for dev onboarding — break free from code-tree-only project understanding; anyone-can-be-a-dev narrative | BS-6 | 📋 Brainstorm queued 2026-06-27 (story-f5513a93) — pre-session: dispatch Agy to write `docs/okf_assessment.md`; consolidate with Claude assessment | `synlynk workspace` (v0.10.0), dev adoption, public launch narrative |
