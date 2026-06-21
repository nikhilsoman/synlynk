# synlynk Roadmap Realignment — Design Spec

**Date:** 2026-06-21  
**Status:** Approved — produced by workgroup consensus (Claude + AGY + Codex + Nikhil)  
**Supersedes:** `docs/superpowers/specs/2026-06-06-synlynk-unified-roadmap.md`  
**Decision record:** This document is the first formal Decision record in the synlynk project.

---

## Context

After v0.8.0 (Support Engineer Agent), the team paused to realign the roadmap around six strategic priorities:

1. Team edition — multi-human networking, not billing tiers
2. Multi-repo onboarding with strong mature-project context
3. Token budget visibility from spec through PR merge
4. Agent army as the eyes and ears of the community stack
5. Community territory as the defensible moat
6. Public presence independent of GitHub

AGY and Codex reviewed the strategic direction in parallel before this spec was written. Their key findings are incorporated below and marked **[AGY]** / **[Codex]** where they shaped decisions.

---

## Four Tracks

All work from here runs on four parallel tracks:

| Track | Focus | Owner |
|---|---|---|
| 🧱 Core Product | Onboarding · context quality · token budgets · value visibility | Engineering |
| 🤝 Community Layer | Workgroup → Team → Enterprise → Domain | Engineering + Design |
| 🌐 Public Presence | synlynk.com · public blog · contributor blog | Marketing Intern (Autopilot) |
| ☁️ Server-Side Strategy | Articulate v0.9.3; implement from v1.1 | Architecture |

---

## Agent Archetype Model

Agents are the eyes and ears at every level of the community stack. Four archetypes, expandable as the platform grows:

### Archetypes

| Archetype | Trigger | Role |
|---|---|---|
| 🔧 **Maintainers** | Schedule · push · CI | Proactive health monitoring, SOP maintenance, self-healing |
| 📣 **Communicators** | Release · merge · schedule | Content, marketing, community voice — publish outward |
| 🎯 **Orchestrators** | Story events · signals · budget thresholds | Work management, routing intelligence, cross-agent coordination |
| 🧠 **SMEs** | Domain tag · file path · explicit `synlynk consult` | Deep domain expertise — reactive consultation, can proactively flag domain risk |

### Context portability

The same archetype deployed at different levels behaves differently based on scope. A Support Engineer in the synlynk repo monitors synlynk's health. The same archetype deployed in a customer's workgroup monitors their project's health. The `.agents/<name>.json` config + deployment level define what it monitors and who it communicates with.

### Deployment levels

| Level | Maintainers monitor | Communicators send to | Orchestrators manage |
|---|---|---|---|
| 🏠 Workgroup | Tests, sentinel, telemetry, per-repo costs, open issues | GitHub repo, PR descriptions, project blog, devlogs | Stories, epics, routing, token budget per story |
| 👥 Team | Cross-repo health, integration failures, shared capability drops | Team channels, cross-repo digest, public changelog | Cross-repo epics, team token budgets, cross-workgroup routing |
| 🏢 Enterprise | Org-wide cost burn, compliance, security posture | Leadership dashboards, org blog, compliance reports | Org portfolio, cross-team budget allocation, agent entitlements |
| 🌐 Domain/Community | Domain health signals, community adoption, best-practice drift | Public community channels, domain newsletters, Tokq marketplace | Convention packages, shared routing intelligence |

### SME archetype — trigger model

SMEs differ from Maintainers in trigger model (pull, not push):
- Story tagged `engg:security` → Security SME invoked
- PR touches `auth/**` → Security SME reviews
- `synlynk consult security-sme "<question>"` — explicit invocation
- SME can also proactively flag when its domain appears at risk

SME requires: event bus + domain-tag subscription model + non-mutating "review/comment" job role. **Deferred to v1.0.0.** [Codex: this is a new concept, not a config tweak — needs new job model primitives]

---

## Version Arc

### v0.8.x — Agent Series (parallel track, running alongside v0.9.x)

Agents trigger via GitHub Actions + crontab (v0.8.1–0.8.4) and via daemon once v0.9.2 ships.

| Version | Agent | Archetype | Key signals |
|---|---|---|---|
| v0.8.0 ✅ | Support Engineer | Maintainer | Tests, sentinel, telemetry, capability drop, GitHub issues |
| v0.8.1 | Security Guard | Maintainer | Dep vulns, secret leaks, CVEs |
| v0.8.2 | Marketing Intern | Communicator | Blog posts, release notes, social copy |
| v0.8.3 | PM Agent | Orchestrator | Growth signals, story routing, sprint pulse |
| v0.8.4 | Compliance Officer + Docs Keeper | Maintainer + Communicator | Convention drift, docs staleness |

---

### v0.9.0 — Kernel Fixes + Package Split (Week 1)

**[Codex] Highest-leverage release in the entire roadmap. Every agent dispatch is degraded without this.**

- `generate_context(scope=task)` — scoped context, pulled from v1.3.0. Currently falls back silently to full context for every dispatch (bin/synlynk.py ~line 2955). Affects every agent.
- Task → file-path mapping injected into dispatch prompt
- Verify contract (`pytest tests/test_x.py`) injected per dispatch so agents know "done"
- Per-agent dispatch framing: Codex prompt ≠ Claude stdin ≠ AGY `--print` arg. Currently identical plaintext for all agents causing silent context loss. [AGY: different truncation/escaping per CLI]
- Wire Ed25519 signing into `_write_capability_rating` — sig column exists but signing not wired. [AGY]
- Anti-gaming baseline in quality scoring — `quality_auto` formula (35% test-pass + 30% build + 35% inverse-rework) is gameable by trivial passing tests. Add minimum complexity threshold. [AGY]
- **Package split:** `bin/synlynk.py` → `synlynk/` package with clean module boundaries (db/story/score · scan/context · instruction-files · dispatch/jobs · sentinel · daemon). Do this before the agent series lands — every new agent PR is a merge conflict in a single 4000-line file. [Codex]

---

### v0.9.1 — Team Onboarding + Consensus Framework (Week 2)

**Immediate use case: Superagents monorepo, 4-5 people, varying AI toolkits (Gemini + Codex baseline, Claude for some).**

- `synlynk join` — new member onboards to existing project in 60 seconds:
  1. Source scan discovers existing architecture, conventions, README
  2. Generates rich AI context files (CLAUDE.md, GEMINI.md, AGENTS.md) informed by what's already there — not blank templates
  3. Seeds per-member devlog
  4. Presents team digest: who's active, what's in-progress, what just shipped
  5. Recommends first task from todo.md
- `synlynk team status` — team digest on demand
- Pull-before-write arbitration: conflict warn on concurrent edits (not a hard block — social contract with mechanism)
- Token budgets at story creation: `synlynk story add` prompts for `estimated_tokens`
- PR merge audit: Support Engineer compares estimated vs actual and posts delta to PR description
- **`synlynk decide "<topic>" --panel claude,agy,codex [--record]`** — consensus decision command:
  - Convenes specified panel (agents + humans)
  - Records each participant's input
  - Synthesizes into a signed **Decision record** in `project-docs/decisions/YYYY-MM-DD-<slug>.md`
  - Decision record: immutable, append-only, Ed25519-signed by all participants, linked to resulting artifacts (spec, roadmap, todo)
  - A Decision is a peer to Epic in the PM hierarchy — deliberation producing direction, not work items
  - This roadmap realignment is the first Decision record retroactively created

---

### v0.9.2 — Async Daemon (Week 3)

- `synlynk daemon start/stop/status/restart`
- launchd (macOS) / systemd (Linux) integration — managed service, survives reboots
- Job queue in `state.db` — persist across daemon restarts, crash recovery from last completed phase
- HTTP context server on `localhost:27471` — standardized, localhost-only, invisible to corporate firewalls
- Scheduled agent dispatch — replaces crontab entries; agents now trigger on daemon schedule
- **v0.8.1–v0.8.4 agent series fully unblocked from this release** — schedule-triggered Maintainers now have a real daemon

---

### v0.9.3 — Workgroup Relay (Week 4)

#### Design principles

1. **Relay is stateless.** Events stored in each member's `state.db`. Relay routes, never persists. Migration between modes = update one URL.
2. **Transport: WebSocket Secure (WSS) over port 443.** Only port universally allowed through corporate firewalls and DPI. How Figma, Linear, Slack do real-time.
3. **Daemon port 27471 is localhost-only.** Never visible to network. Corporate firewalls don't see it.
4. **Local-first offline resilience.** Members work offline, queue events in `state.db`, flush on reconnect — identical to git offline workflow.

#### Three deployment modes (same protocol throughout)

**Mode 1 — LAN (day 1, self-hosted):**
- `synlynk relay start` on any member's machine
- mDNS auto-discovery (Bonjour/Avahi, port 5353) — zero config, same as printers/AirPlay on corporate LAN
- Self-signed TLS cert auto-generated; port 8443 (non-root) or 443
- Remote members on corporate VPN appear on same subnet → auto-discover relay
- Internal LAN traffic almost never firewalled between peers

**Mode 2 — Cloudflare Tunnel (hybrid teams, WFH without VPN):**
- Host runs `cloudflared tunnel` alongside `synlynk relay start`
- Outbound-only connection to Cloudflare edge — **no inbound ports opened**
- Corporate firewalls allow outbound 443 universally
- Team gets public HTTPS endpoint (custom domain or `*.workers.dev`)
- Free tier; migration to VPS = update Cloudflare Tunnel config, same public URL
- Alternative: Tailscale private mesh (for teams already on Tailscale)

**Mode 3 — VPS (always-on, no single-host dependency):**
- Relay on Fly.io / Hetzner / Railway; Let's Encrypt TLS auto-managed
- `synlynk relay connect wss://relay.yourteam.com`
- All daemons connect outbound to 443 — firewall transparent
- Fly.io free tier covers 4-10 person team; Hetzner €4/mo for dedicated
- **Graduation path:** LAN → Cloudflare Tunnel → VPS (same protocol, change one URL)

#### Revolving host protocol

Any active member can be host. Relay bootstraps from any online member's state (stateless relay, state is in member DBs).

`synlynk relay handover <member>` sequence:
1. Old host broadcasts signed `RELAY_HANDOVER` event (new URL, new host identity, timestamp)
2. 10-minute grace period — old relay stays alive, proxies laggard connections to new relay
3. All daemons reconnect, acknowledge with signed `RELAY_CONNECTED`
4. Old relay shuts down after grace period OR when all members confirmed
5. **Degraded-mode warning:** any daemon not confirmed within 5 min gets a loud local alert

**Rule: no silent host changes.** A member going offline mid-session triggers degraded-mode warning to all, not a silent failure.

---

### v0.10.0 — Multi-Repo Workspace

- `synlynk workspace init` — create named workspace, register first repo
- `synlynk workspace join <name>` — add current repo to existing workspace
- Cross-repo Epic spanning multiple repos; Stories have `repo_id` FK
- Shared context slice: workspace summary injected alongside per-repo context
- Relay extended to workspace scope — all repos share one relay
- Support Engineer monitors all repos in workspace

---

### v1.0.0 — Community Layer: Local Workgroup + Public Launch

- **Workgroup protocol:** shared, signed capability ledger across humans + agents + autopilots
- **SME archetype** + event bus (domain-tag subscriptions, file-path triggers, non-mutating review role)
- **Game-resistance hardened** in capability scoring (anti-trivial-test gaming, minimum complexity threshold, review-weighted scoring)
- All three autopilot classes at workgroup level (Maintainers + Communicators + Orchestrators)
- Stable CLI contract, `synlynk migrate` for pre-1.0 projects
- pipx + Homebrew distribution
- **Public launch** (HN + Product Hunt)
- **synlynk.com** live on independent hosting (not GitHub Pages) — supports interactivity + community onboarding
- **Public blog** live — maintained by Marketing Intern Autopilot, richer graphically, public audience
- Contributor blog stays in `docs/blog/` — PR-by-PR technical updates, current posts remain

---

### v1.1.0+ — Community Expansion (server-side enters here)

| Version | Theme |
|---|---|
| v1.1.0 | Cross-workgroup (team level) — relay graduates to community server; agent entitlements |
| v1.2.0 | Enterprise workspace (cross-team) — org-level governance agents |
| v1.3.0 | Domain/discipline communities — Tokq convergence; MCP / Open Context Protocol |

**Server-side product strategy:** articulated in this doc, implemented incrementally from v1.1. The v0.9.3 relay is the prototype — learnings from running it at workgroup scale inform the v1.1 community server design. No server-side implementation before v1.1.

---

## The Real Moat

**[AGY]** "Shared capability ledger + cost attribution" is not defensible — it's a SQLite table anyone can replicate. The defensible asset is the **accumulated routing graph**: which agent/model, at which version, succeeded on which (engg × org × industry × phase) cell, decayed over time. A proprietary dataset that compounds and can't be cloned.

But it only becomes a moat if:
1. It is **signed** (Ed25519 per rating — wired in v0.9.0)
2. It is **game-resistant** (anti-trivial-test formula — hardened in v0.9.0 + v1.0.0)
3. It is **large** (data network effect — grows with every workgroup)

**[Codex]** The per-agent output quality — scoped context + verify contract — is what determines whether any dispatched agent produces one-shot results or flails. This is the kernel fix that makes everything on top of it worth building.

---

## Relay Ownership Model (decided 2026-06-21)

**Decision: Hybrid (C), community-first.**

The community relay (B) is the default experience for all users. Self-provisioned VPS (A) is gated behind an enterprise/exception flag. Users should never need to think about VPS hosting.

### Three relay tiers

| Tier | Default? | Who | What |
|---|---|---|---|
| **Community Relay** | ✅ Default | All workgroups | `synlynk relay join` → `relay.synlynk.com` · namespaced · WSS/443 · Fly.io hosted by synlynk |
| **LAN / CF Tunnel** | Fallback | Local or VPN teams | Day-1 prototype mode; graduates to community relay via `synlynk relay upgrade` |
| **Self-Provisioned VPS** | 🔒 Gated | Enterprise / exceptions | Requires `--enterprise` flag or exception token; synlynk ships ready-made `fly.toml` |

### Feature gate design

- v0.9.3: `synlynk relay join` already points at `relay.synlynk.com` but shows graceful "launching with v1.0 — using LAN mode now" until server is live. Zero UX change at v1.0 launch.
- v1.0.0: Community relay goes live on Fly.io. Self-host gated.
- v1.1.0+: Community relay graduates to community server with team-level namespaces.

### Why community-first

- Every workgroup on the community relay contributes to the routing graph (signed, game-resistant) — the real moat.
- Self-provisioned relay fragments the network. Users who need it (regulated industries, air-gapped) get it via the enterprise gate.
- Fly.io is the recommended VPS for self-hosted path: $3–5/mo, WSS/443 trivial, global Anycast, ready-made `fly.toml`.

---

## Deferred

| Item | Deferred to | Reason |
|---|---|---|
| Async daemon | v0.9.2 (pulled forward from v0.8.0) | Needed for schedule-triggered agents |
| HTTP context server | v0.9.2 | Bundled with daemon |
| MCP / Open Context Protocol | v1.3.0 | Needs server to serve it from |
| SME archetype | v1.0.0 | Needs event bus + new job model |
| ~~VPS deep-dive~~ | ✅ Resolved | Fly.io for community relay + self-host; Hetzner as budget enterprise option |

---

## Public Presence Strategy

- **synlynk.com:** Independent hosting (not GitHub Pages). Supports interactivity and community onboarding. Targets v1.0.0 launch.
- **Public blog:** Maintained by Marketing Intern (Autopilot). Richer graphically. Public consumption — product updates, tutorials, community stories.
- **Contributor blog (`docs/blog/`):** Stays in GitHub. PR-by-PR technical updates written by contributors. All current posts remain here. These are the developer changelog, not the marketing channel.
- Blog bifurcation: the two blogs have different audiences, cadences, and owners.
