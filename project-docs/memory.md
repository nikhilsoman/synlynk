# synlynk Memory

## Roadmap Realignment (decided 2026-06-21 — workgroup consensus: Claude + AGY + Codex + Nikhil)
- **Tiers are permanently off.** "Team edition" = networked collaboration features, not billing tiers. [@nikhilsoman]
- **Agent archetypes:** Four types — Maintainers (schedule-triggered, self-healing) · Communicators (release-triggered, outward publishing) · Orchestrators (story/signal-triggered, work management) · SMEs (domain-tag/file-path-triggered, reactive expertise). Same archetype deployed at different levels (workgroup → team → enterprise → domain) behaves differently by scope.
- **Context portability principle:** The `.agents/<name>.json` config + deployment level define what an agent monitors and who it communicates with. Archetype is the pattern; context gives it purpose.
- **Kernel fix is highest priority [Codex/AGY]:** `generate_context(scope=task)` silently falls back to full context (bin/synlynk.py ~line 2955, deferred to v1.3.0 — PULLED to v0.9.0). Every agent dispatch is degraded without scoped context.
- **Package split before agent series [Codex]:** bin/synlynk.py at ~4000 lines is a merge conflict timebomb. Split into `synlynk/` package in v0.9.0 before more agents land.
- **Capability ledger integrity [AGY]:** Ed25519 sig column exists but signing not wired into `_write_capability_rating`. Wire in v0.9.0. `quality_auto` formula is gameable — anti-gaming baseline in v0.9.0, hardened in v1.0.0.
- **Real moat [AGY]:** Not "shared capability ledger" (anyone can clone a SQLite table). The moat is the accumulated routing graph — which agent/model/version succeeded on which (engg × org × industry × phase) cell, decayed over time. Only defensible if signed, game-resistant, and large.
- **Relay design:** Stateless WSS relay on port 443. Three modes: LAN (mDNS auto-discovery) → Cloudflare Tunnel (no open ports, firewall-transparent) → VPS (always-on). Revolving host: any active member can be host, relay bootstraps from any online member. Loud handover protocol (signed broadcast, 10-min grace, degraded-mode warning). Daemon on localhost:27471 only.
- **Relay ownership model (decided 2026-06-21):** Community-first hybrid. Community relay (relay.synlynk.com, Fly.io hosted by synlynk) is the DEFAULT for all users — `synlynk relay join`. Self-provisioned VPS is gated behind `--enterprise` flag or exception token (for regulated industries / air-gapped). LAN/CF Tunnel stays as fallback/prototype. `synlynk relay join` points at relay.synlynk.com even in v0.9.3 (graceful "launching with v1.0" message until server is live). Fly.io is the recommended VPS for enterprise self-host path. Northflank for v1.1+ community server.
- **Consensus decision framework:** `synlynk decide "<topic>" --panel <agents>` — first-class command. Produces signed Decision record in `project-docs/decisions/`. A Decision is a peer to Epic in the PM hierarchy.
- **VPS deep-dive (resolved 2026-06-21):** Fly.io ($3–5/mo) for community relay + enterprise self-host. Hetzner (€4.51/mo) as budget enterprise option for teams with ops expertise. E2B/Modal ruled out (ephemeral sandboxes, not relay). Koyeb ruled out (acquired by Mistral). Bedrock AgentCore / Azure Foundry Hosted Agents are AI-native but designed for agent session management, not relay hosting — overkill. No purpose-built agentic relay platform exists yet.
- **Spec:** `docs/superpowers/specs/2026-06-21-synlynk-roadmap-realignment-design.md`

## Positioning (decided 2026-06-06)
- **Name:** synlynk — "The OS for multi-agent development." [@nikhilsoman]
- **Framing:** Not a context injector, skill package, or SaaS dashboard. An OS layer beneath every
  AI tool, giving agents persistent memory, structured coordination, and a stable shared substrate.
- **Tier model retired:** Solo/Team/Enterprise tiers replaced by the OS layer model — one product,
  increasing capability as you move up the stack.

## Workspace & Multi-Repo (decided 2026-06-07)
- **Workspace = unit of organization above a repo.** One product = one workspace, N repos. Solo dev = one workspace, one repo — structurally identical, invisible to user. [@nikhilsoman]
- **Storage:** `~/.synlynk/workspaces/<name>/state.db` — one DB per workspace. Repos are a dimension (`repos` table + `repo_id` FK on stories/events/costs), not separate DBs.
- **Identity: machine-level.** `~/.synlynk/identity.key` — one Ed25519 keypair per person per machine. Shared across all workspaces. Replaces per-project keypair. Closes Gap 10 entirely.
- **Init: repo-first, auto-promoted.** `synlynk init` creates workspace transparently. `synlynk workspace join <name>` adds a second repo. Auto-detects via GitHub org match.
- **Cross-repo Epics: first-class.** One Epic spans N repos. Stories have `repo_id` FK. Architect context = full epic cross-repo view. Builder/Verifier = workspace shared + repo slice.
- **Team sync: event-log via shared git repo (not export/import).** Daemon pushes new events to per-member branch every 5 min. Others pull and apply. Max drift ≈ 5 min. Conflict-free (events are append-only). Becomes NATS at Tokq Alpha — same event format, different transport.
- **Simulated team:** switch `git config user.name` — events record different git_user, all signed by same machine key. Full cost/activity attribution per simulated member. No extra infra.
- **Spec:** `docs/superpowers/specs/2026-06-07-synlynk-workspace-multi-repo-design.md`

## Agent Identity, Dispatch & Entitlements (decided 2026-06-07)
- **Identity is two-layered:** Local Identity (Ed25519 keypair, agent_uuid — cryptographic anchor, machine-scoped) + Role (primary entitlement unit) + Agent Profile (fitness function: CLI × model × environment × competency_scores). [@nikhilsoman]
- **Roles:** Architect (docs only, no src writes), Builder (implements, can branch/PR), Verifier (tests/audits). Custom roles via `synlynk role add`.
- **Dispatch modes:** A=daemon (persistent, primary), B=self-chain (agent completion re-evaluates), C=one-shot `synlynk dispatch` (universal fallback — no daemon needed), D=agent-native scheduling (`use_native_scheduling` flag).
- **Dispatch address:** `inbox` table in state.db (v0.5–v0.7), NATS subject (v1.0+). Logical address: `synlynk://<project_id>/roles/<role>/inbox`.
- **Human-agent bridge:** Email (send-only SMTP, v0.7.0). Approval via `synlynk story approve <id>` CLI. Gmail reply parsing deferred to v0.8.0.
- **Entitlements are two layers:** Authorization (gate before dispatch) + Sandboxing (constraints while running). Merge to main is always approval-required — no threshold can override.
- **Ed25519 identity pulled forward:** From v0.9.0 to v0.5.0. Every dispatch_log row and completed event is signed. Audit trail is non-repudiable.
- **Cron design:** One `synlynk dispatch` cron, not per-agent. Per-role frequency via multiple `schedules` entries with different `filter` values.
- **Spec:** `docs/superpowers/specs/2026-06-07-agent-identity-dispatch-design.md`

## Brainstorm Session Map (updated 2026-06-27)
- **BS-1** ✅ Done — Initial architecture / OS framing
- **BS-2** ✅ Done — Onboarding + Mode Taxonomy
- **BS-3** ~~queued~~ → **retired** (2026-06-27): AB-11/12/13 (conflict taxonomy + instruction coexistence) folded into BS-7. No standalone BS-3 session.
- **BS-4** — Command Audit + Autopilot Trigger Map. Queued pre-GA, not this weekend.
- **BS-5** — Website redesign (story-048f5fe5). Saturday PM this weekend.
- **BS-6** — OKF alignment + `synlynk viz` three-view visualization (story-f5513a93). Sunday AM.
- **BS-7** — Skill Pack Interop + Benchmarks + **AB-11 conflict taxonomy** (story-bs7-interop). Sunday AM/PM. Benchmark execution week of 2026-06-30.
- **BS-8** ✅ Spec done (2026-06-27) — Harness Capability Awareness + Loop-Native Dispatch. `synlynk probe` + `dispatch_loop()` + stuck consult. Three stories: story-bs8-probe, story-bs8-loop, story-bs8-consult. Target v0.10.1. Spec: `docs/superpowers/specs/2026-06-27-bs8-harness-capability-awareness-loop-dispatch-design.md`
- **BYOA** — Parked post-dev-preview (Ollama, OpenCode/OpenRouter, DeepSeek).

## State DB & Agentic PM (decided 2026-06-07)
- **Core invariant:** State never branches. All worktrees share one `~/.synlynk/projects/<key>/state.db` where `<key>` = 8-char MD5 of `git rev-parse --git-common-dir/..` (repo root). [@nikhilsoman] Implemented v0.4.1.
- **project-docs/ retired:** Markdown files become gitignored. state.db is primary. Context bridge unchanged — agents still see `.synlynk/context.md`.
- **Agentic PM hierarchy:** Project → Arc → Phase → Epic → Story → Event. Replaces time/capacity anchoring with dependency/verification anchoring.
  - **Arc** — strategic direction (pivot/archive/merge). The layer missing from every PM tool.
  - **Phase** — structural backbone (capability gate, rarely changes; was: roadmap row).
  - **Epic** — one implementation plan (`writing-plans` output = one Epic + N Stories).
  - **Story** — one agent task unit with `done_criteria` and `depends_on` graph.
  - **Event** — append-only universal log (replaces devlogs; devlog is a filtered view).
- **Token budget replaces story points:** `estimated_tokens` on stories. Routing: capability → quota headroom → cost. `agent_quotas` table tracks per-agent limits.
- **Costs fully attributed:** `costs` table gains `story_id / epic_id / phase_id` FKs — can now answer "what did Phase v0.5.0 cost?"
- **Platform sync:** `external_refs` table maps Arc/Phase/Epic/Story → GitHub/Jira/Linear. state.db is canonical; platforms are views.
- **GitHub Projects V2 — agentic-first decision (2026-06-27):** [@nikhilsoman] The board is a human-readable projection of state.db, not the source of truth. Agents never write to the board directly. synlynk owns the push via `synlynk sync --board github` (post-v0.10.0). The current `--project-id` flag on `synlynk init` stamps a placeholder into agent instruction files for agents to manually invoke GraphQL if needed — that is the *only* live artifact; no bidirectional sync exists yet. Do not expand GitHub Projects V2 surface area before `external_refs` is implemented.
- **Migration:** `synlynk migrate` (ships v0.5.0) — parses project-docs/, populates state.db, untracks with `git rm --cached`.
- **Next:** Agent identity, addressability, scheduling, entitlements — separate brainstorm.
- **Spec:** `docs/superpowers/specs/2026-06-07-synlynk-state-db-agentic-pm-design.md`

## Architecture — OS Layer Model (decided 2026-06-06)
Bottom to top: Kernel → Filesystem → IPC → Scheduler → Shell → Ecosystem Interface → Applications.
- **Kernel + Filesystem:** SHIPPED (v0.3.0) — exec, telemetry, flatline, budget, project-docs/
- **IPC:** v0.4.0 — conventions.md, Trio pipeline, constraint propagation
- **Scheduler:** v0.5.0 — capability engine, SQLite-backed routing, state.db for all project state
- **Shell:** v0.7.0 — daemon, dispatch, async pipeline
- **Ecosystem Interface:** v0.8.0 — Open Context Protocol, MCP server
- **Applications:** GStack, SuperPowers, HermesAgent, OpenClaw, NmoClaw run ON synlynk, not beside it

## Architecture — Infrastructure Arc (decided 2026-06-06)
Flat files (v0.3) → SQLite WAL (v0.5–v0.6) → HTTP Context Server on localhost (v0.7) →
NATS leaf node schema defined (v1.0) → NATS leaf→hub live (Tokq Alpha). [@nikhilsoman]
- SQLite via stdlib `sqlite3`. HTTP via stdlib `socketserver`. NATS via inlined pure-Python client.
- Single-file constraint (`bin/synlynk.py`, zero pip deps) holds through v1.0.
- Exception: Tokq Alpha introduces `cryptography` package as `pip install synlynk[tokq]`. Local-only
  use remains zero-dependency forever.

## Tokq Convergence (decided 2026-06-06)
- **Tokq** (Jan 2026) = distributed agent memory marketplace (same author). Cloud/network layer.
- **synlynk** (May 2026) = local OS client. Built as the stepping stone toward Tokq.
- **Relationship:** synlynk is the local OS. Tokq is the cloud layer above it. Both survive
  independently. Cloud is additive, never required.
- **Bridge sequence:** v0.9 generates Ed25519 identity → v1.0 freezes memory unit schema + NATS leaf
  schema → Tokq Alpha connects, adds ZK encryption + sync + marketplace.
- **Distribution insight:** Tokq's original distribution problem (no client, no install base) is
  solved by synlynk. Every `synlynk init` = a Tokq onboarding event.

## Tokq Bridge Decisions (decided 2026-06-06)

**Agent Identity (FR-1):**
- `synlynk identity init` — generates UUID + Ed25519 keypair via `ssh-keygen` subprocess.
- Writes `.synlynk/identity.json` (UUID + public key fingerprint) + `.synlynk/identity.key` (chmod 600).
- Ships in v0.9.0. Auto-called from `synlynk init`.

**Memory Unit Schema (FR-2/3):**
- One Tokq memory unit per `project-docs/` file (not per paragraph).
- `session_id` = git remote URL (or SHA of repo path if no remote).
- `client_id` = `project_id` from `.synlynk/config.json`.
- `memory_id` = `sha256(session_id + filename + version_counter)` — deterministic, idempotent sync.
- Schema frozen at v1.0, published as `docs/tokq-memory-unit-schema.md`.

**Zero-Knowledge Encryption (FR-4):**
- Client-side AES-256-GCM. Key derived from Ed25519 private key via HKDF-SHA256.
- Tokq stores only ciphertext. Cannot decrypt. Ships in Tokq Alpha.

**Ledger Boundary (FR-6):**
- `costs.md` = local ops ledger (exec, Trio pipeline). Permanent. Never replaced.
- Gas tank = Tokq cloud ops ledger (memory CRUD, marketplace). Separate. Additive.
- `synlynk tokq balance` shows gas tank. `costs.md` shows local ops. Both coexist forever.

**Conventions → Marketplace (FR-5/7):**
- `synlynk publish conventions` — packages `conventions.md` as a Tokq collection with pricing.
- `synlynk subscribe <id>` — subscribes, gas tank auto-deducts. 70/30 revenue split.
- Ships in Tokq Alpha.

## Open Context Protocol (decided 2026-06-06)
Two commands are the entire integration surface:
- `synlynk context --for <tool>` — generate tool-scoped context, write to `.synlynk/context-<tool>.md`
- `synlynk checkpoint --from <tool>` — tool writes back what it learned to project state
Any tool integrates in < 10 lines. No SDK. No fee. Published spec at v0.8.
HTTP Context Server (v0.7, `localhost:27471`) is the underlying transport.
[@nikhilsoman]

## Instruction Reach (shipped v0.4.1, 2026-06-17)
- **7 tracked instruction targets:** CLAUDE.md (html), GEMINI.md (html/agy), AGENTS.md (html/codex), `.cursor/rules/synlynk.mdc` (none — synlynk owns whole file), `.github/copilot-instructions.md` (html), `.windsurfrules` (hash), `AI_INSTRUCTIONS.md` (html/universal).
- **`_INSTRUCTION_TARGETS`** is the single source of truth: `(path, tool, marker_style, detection_fn)`. Guards for conditional targets (`cursor`, `copilot`) are derived from `detection_fn` — no duplicate dict anywhere.
- **Three marker styles:** `html` = `<!-- synlynk:start version="..." tool="..." -->` / `<!-- synlynk:end -->`; `hash` = `# synlynk:start` / `# synlynk:end`; `none` = synlynk owns whole file.
- **SHA manifest** at `.synlynk/instructions.json` — tracks section SHA (not whole-file SHA) per target. User edits outside markers never trigger false drift events.
- **Drift detection:** `_check_instruction_drift()` hooked into `exec_command()`. Fires `INSTRUCTION_DRIFT` sentinel once per change (deduplicates by updating manifest SHA immediately after firing). Reset via `synlynk instructions update` or `synlynk instructions ack`.
- **AGY replaces Gemini CLI:** `"gemini"` removed from baselines, discovery, probe patterns. Trio is now claude/agy/codex. GEMINI.md template is AGY-only.

## Trio Protocol Core Decisions (decided 2026-06-01, ships v0.4.0)
- Phase artifacts: `task-packet.md` (Architect) → `build-notes.md` (Build) → `verify-report.md` (Verify)
- Roles emergent from usage: empirical scoring, no hardcoded vendor mapping
- Cold-start: round-robin until 3 samples per (agent, phase, domain)
- Score decay: recency-weighted, half-life = 10 tasks (configurable)
- Phase failure: auto-retry once with next-best agent, then halt
- Full spec: `docs/superpowers/specs/2026-06-01-synlynk-trio-protocol-design.md`

## Load-Bearing Schema Contracts
- **costs.md:** 6 columns — `| Date | User | Requests | Tokens (In/Out) | Estimated Cost (USD) | Summary |`
  Cost at `parts[5]`. Parser in `parse_costs_md()`. Do not add columns without updating the parser.
- **exec exit code:** `exec_command()` returns child exit code as int. `main()` calls `sys.exit()`
  with it. Never swallow non-zero. Flatline triggers after 3 consecutive non-zero same-command exits.
- **Attribution:** All `memory.md` and `devlogs/` entries in team mode MUST have `[@username]`.
- **conftest.py:** Fixtures must mirror the real costs.md 6-column schema at all times. `isolated_db` autouse fixture redirects `synlynk.DB_PATH` to a per-test temp path — every test gets its own `state.db`, no cross-test DB pollution.

## Superseded Decisions
- ~~Tier model (Solo/Team/Enterprise)~~ → retired 2026-06-06. Replaced by OS layer model.
- ~~"Context Switchboard" framing~~ → retired 2026-06-06. Replaced by "OS for multi-agent development."
- ~~Lite → Full progression~~ → retired. Replaced by v0.4→v1.0 staircase + Tokq cloud layer.

## Conventions
- Attribution: `[@username]` on all team-mode entries.
- Session protocol: read last 3 devlog entries at session start. Surface any open threads.
- AI maintains these docs without user prompting at natural pause points.
- PR Reviews: When reviewing a pull request, only comment with observations and suggestions. Do not make code fixes on the branch or commit changes directly; the original author must implement corrections to learn and retain ownership.
