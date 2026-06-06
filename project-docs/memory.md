# synlynk Memory

## Positioning (decided 2026-06-06)
- **Name:** synlynk — "The OS for multi-agent development." [@nikhilsoman]
- **Framing:** Not a context injector, skill package, or SaaS dashboard. An OS layer beneath every
  AI tool, giving agents persistent memory, structured coordination, and a stable shared substrate.
- **Tier model retired:** Solo/Team/Enterprise tiers replaced by the OS layer model — one product,
  increasing capability as you move up the stack.

## Architecture — OS Layer Model (decided 2026-06-06)
Bottom to top: Kernel → Filesystem → IPC → Scheduler → Shell → Ecosystem Interface → Applications.
- **Kernel + Filesystem:** SHIPPED (v0.3.0) — exec, telemetry, flatline, budget, project-docs/
- **IPC:** v0.4.0 — conventions.md, Trio pipeline, constraint propagation
- **Scheduler:** v0.5.0 — capability engine, SQLite-backed routing
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
- **conftest.py:** Fixtures must mirror the real costs.md 6-column schema at all times.

## Superseded Decisions
- ~~Tier model (Solo/Team/Enterprise)~~ → retired 2026-06-06. Replaced by OS layer model.
- ~~"Context Switchboard" framing~~ → retired 2026-06-06. Replaced by "OS for multi-agent development."
- ~~Lite → Full progression~~ → retired. Replaced by v0.4→v1.0 staircase + Tokq cloud layer.

## Conventions
- Attribution: `[@username]` on all team-mode entries.
- Session protocol: read last 3 devlog entries at session start. Surface any open threads.
- AI maintains these docs without user prompting at natural pause points.
