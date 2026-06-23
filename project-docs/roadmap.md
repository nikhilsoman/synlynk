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
| **v0.8.1** | Agent Ecosystem Foundation | `agents_enabled` opt-in gate · lifecycle engine (per-story lifecycle_instances + tasks tables) · capability matrix · ROI tracking · unified `.agents/` config · Support Engineer refactored onto foundation | 📋 Planned | Aug 2026 |
| **v0.8.2** | TPM Agent + Release Agent | Lifecycle runner · wave dispatch · cross-story aggregation · `synlynk tpm` · release pipeline · `synlynk release` | 📋 Planned | Aug 2026 |
| **v0.8.3** | Marketing Intern + PM Agent | Communicator archetype — blog/release notes/social · Orchestrator archetype — growth signals, story routing, sprint pulse | 📋 Planned | Sep 2026 |
| **v0.8.4** | Docs Keeper + Security Guard + Compliance Officer | Maintainer + Communicator — convention drift, docs staleness, dep vulns, secret leaks, CVEs | 📋 Planned | Sep 2026 |
| **v0.9.0** | Kernel Fixes | Scoped context · task→file mapping · verify contract · per-agent framing · Ed25519 wired · anti-gaming baseline (sample-count cap) | ✅ Shipped | June 2026 |
| **v0.9.1** | Install Hardening + Docs Migration | Install broken after package split fixed · `_docs_dir()` configurable · `--docs-dir` flag on init · smart doc migration from existing content | ✅ Shipped | June 2026 |
| **v0.9.2** | Team Onboarding + Consensus | `synlynk join` · team digest · write-arbitration · token budgets · `synlynk decide` | 📋 Planned | July 2026 |
| **v0.9.3** | Async Daemon | `synlynk daemon` · launchd/systemd · job queue · HTTP context server localhost:27471 | ✅ Shipped | June 2026 |
| **v0.9.4** | Workgroup Relay | WSS/443 relay · 3 deployment modes (LAN/Cloudflare Tunnel/VPS) · revolving host protocol | 📋 Planned | Aug 2026 |
| **v0.10.0** | Multi-Repo Workspace | `synlynk workspace init/join` · cross-repo epics · workspace relay scope | 📋 Planned | Aug 2026 |
| **v1.0.0** | Community Layer: Local Workgroup + Public Launch | Workgroup protocol · signed capability ledger · SME archetype · game-resistant scoring · pipx/Homebrew · synlynk.com · public blog | 📋 Planned | Sep 2026 |
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
| Synlynk Autopilot | Agent army as eyes & ears at every community level | 🚀 In Progress (v0.8.x) | `docs/superpowers/specs/2026-06-21-synlynk-roadmap-realignment-design.md` |
| Community Layer | Local workgroup → team → enterprise → domain communities | 📋 v1.0.0 | Same |
| Public Presence | synlynk.com · public blog (Marketing Intern) · contributor blog in GitHub | 📋 v1.0.0 | Same |
| Server-Side Strategy | Relay prototype v0.9.3 → community server v1.1 → Tokq v1.3 | 📋 Articulated, implement v1.1+ | Same |
