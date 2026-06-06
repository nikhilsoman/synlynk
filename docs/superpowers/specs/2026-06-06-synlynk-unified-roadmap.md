# synlynk: Unified Roadmap — v0.4.0 → v1.0.0 + Tokq Convergence

**Date:** 2026-06-06  
**Status:** Approved — supersedes all prior proposal docs  
**Author:** Nikhil Soman + Claude Sonnet 4.6 (brainstorm session)

---

## 1. Positioning

**synlynk is the OS for multi-agent development.**

Not a skill package. Not a context injector. Not a SaaS dashboard. An operating system layer that
sits beneath every AI tool you use and gives them persistent memory, structured coordination, and a
stable shared substrate — the same things a real OS gives to processes.

The tier model (Solo / Team / Enterprise) is retired. The OS framing replaces it. There are no
tiers, only increasing depth of capability as you move up the stack.

---

## 2. Architecture: Two Interlocked Models

The design is the intersection of two independently valid architectures that turn out to describe
the same product from different angles.

### 2.1 The OS Layer Model (user-visible surface)

```
┌─────────────────────────────────────────────────────────┐
│  Applications  SuperPowers · GStack · HermesAgent · etc  │
├─────────────────────────────────────────────────────────┤
│  Ecosystem     Open Context Protocol (v0.8)              │
│  Interface     synlynk context --for <tool>              │
│                synlynk checkpoint --from <tool>          │
├─────────────────────────────────────────────────────────┤
│  Shell         synlynk run / dispatch / review / TUI     │
│                synlynk daemon / schedule / queue         │
├─────────────────────────────────────────────────────────┤
│  Scheduler     Capability Engine — capability.json       │
│                Recency-weighted routing by (agent,phase, │
│                domain). Learns. Adapts. Explains itself. │
├─────────────────────────────────────────────────────────┤
│  IPC           conventions.md · constraint propagation   │
│                Trio: Architect → Build → Verify          │
│                Handoff artifacts between phases          │
├─────────────────────────────────────────────────────────┤
│  Filesystem    project-docs/ ledger: memory, roadmap,    │
│                todo, costs, devlogs, conventions         │
├─────────────────────────────────────────────────────────┤
│  Kernel        exec · telemetry · flatline · budget      │
│                ← SHIPPED: v0.1 – v0.3.0 ✓               │
└─────────────────────────────────────────────────────────┘
```

### 2.2 The Infrastructure Arc (hidden implementation backbone)

Running beneath each release is a progressive infrastructure migration. This arc never breaks the
user-facing CLI surface — it is a refinement of what stores and transports state under the hood.

```
Flat files (.json / .md)          ←  v0.3 (current)
     ↓
SQLite WAL                         ←  v0.5–v0.6
  · job state machine
  · capability scores
  · telemetry ring buffer
  · single-writer, concurrent reads, fast queries
     ↓
HTTP Context Server (local daemon)  ←  v0.7
  · daemon serves context on localhost
  · MCP server reads from it
  · ecosystem tools read from it
  · no file I/O for consumers
     ↓
NATS Leaf Node                      ←  v1.0 (schema defined)
  · Synlynk instance joins Tokq cluster
  · context sync, job dispatch, memory replication
    over named NATS subjects
  · MessagePack encoding at Tokq boundary
     ↓
Tokq Cloud Layer                    ←  Tokq Alpha (Q3 2026)
  · NATS hub receives leaf streams
  · Distributed agent identity (Ed25519)
  · Zero-knowledge memory replication
  · Gas tank, knowledge marketplace
```

These two models are the same product. The OS Layer Model is the UX. The Infrastructure Arc is the
engine underneath it. Every release advances both.

---

## 3. The Tokq Convergence

**Tokq** (January 2026) was the original vision: a distributed, agent-first memory marketplace
with zero-knowledge encryption, cryptographic agent identity, and a knowledge economy (70/30
creator split). It was built top-down — cloud-scale infrastructure without a client layer.

**synlynk** (May 2026) was the stepping stone: a local-first, zero-dependency tool that solves
the real friction of today (cross-session context loss, multi-agent coordination overhead) while
the world catches up to the Tokq vision. It was built bottom-up.

They meet in the middle:

| Layer | synlynk provides | Tokq provides |
|---|---|---|
| Storage | project-docs/ ledger, SQLite WAL | Distributed encrypted memory store |
| Transport | File I/O → HTTP server → NATS leaf | NATS hub, MessagePack streams |
| Identity | UUID + Ed25519 keypair (v0.9) | Agent registration, signature auth, on-chain reputation |
| Memory schema | Defined mapping: project-docs/ → memory units (v1.0) | CRUD, versioning, session scoping, access control |
| Encryption | Local ZK encrypt before send (Tokq Alpha) | Stores ciphertext only — never holds decryption keys |
| Economics | costs.md = local ops ledger (unchanged) | Gas tank = Tokq cloud ops ledger (separate, additive) |
| Standards | conventions.md per project | `synlynk publish` → Tokq marketplace collection (Tokq Alpha) |
| Distribution | synlynk init = Tokq onboarding event | — |

v1.0 defines the bridge schema and local identity. Tokq Alpha activates the connection. Both
products survive independently; the cloud layer is additive, never required to use synlynk locally.

### 3.1 Memory Unit Schema (Gap 2 — resolved)

This defines how synlynk's local state maps to Tokq's FR-2/FR-3 memory unit structure. Required
before Tokq Alpha can be built.

| Tokq field | synlynk source | Notes |
|---|---|---|
| `agent_id` | `.synlynk/identity.json` → `agent_uuid` | Set at `synlynk identity init` |
| `session_id` | Git remote URL (or SHA of `git rev-parse --show-toplevel` if no remote) | Stable per repo |
| `client_id` | `.synlynk/config.json` → `project_id` (set at `synlynk init`) | User-facing project name |
| `memory_id` | `sha256(session_id + filename + version_counter)` | Deterministic; enables idempotent sync |
| `encrypted_data` | Full file content of each `project-docs/*.md` file, AES-256-GCM encrypted | One memory unit per file |
| `metadata.title` | Filename without extension (e.g., `memory`, `conventions`, `roadmap`) | |
| `metadata.tags` | `[@username]` attributions extracted from file content | |
| `metadata.version` | Monotonic counter incremented on each `synlynk sync` write | |
| `metadata.expires` | None by default; configurable via `synlynk tokq set-ttl <file> <days>` | |

**Granularity decision:** One memory unit per project-docs/ file (not per paragraph, not per
decision entry). This keeps sync simple: a `synlynk sync` push serializes 5–8 files into 5–8
memory units. Retrieval is a single list-by-session_id call followed by 5–8 reads.

### 3.2 Ledger Boundary — costs.md vs. Gas Tank (Gap 5 — resolved)

These are two separate ledgers that coexist permanently. Neither replaces the other.

- **costs.md** (local) — tracks all synlynk CLI operations: exec invocations, Trio pipeline job
  costs, token extraction from AI CLI output. Exists whether or not Tokq is connected. Human-
  readable Markdown. Updated by `update_costs()` after every exec.
- **Gas tank** (Tokq cloud) — tracks all Tokq cloud operations: memory unit storage, retrieval,
  marketplace subscriptions, earnings from published collections. Managed by Tokq. Queryable via
  `synlynk tokq balance`. Denominated in USD equivalent (crypto converted at transaction time).

When Tokq Alpha connects, `synlynk sync` operations deduct from the gas tank. Local exec
operations continue tracking to costs.md. A `synlynk tokq balance` command shows the gas tank
without requiring any migration of historical costs.md data.

---

## 4. Ecosystem Coexistence

synlynk does not compete with GStack, SuperPowers, HermesAgent, OpenClaw, or NmoClaw. These are
Applications layer tools. synlynk is the OS they run on.

Each tool, when invoked inside a synlynk-initialized repo, can opt in to the Open Context Protocol
(v0.8) with two commands:

```bash
# Tool reads synlynk state before starting
synlynk context --for superpowers   # writes .synlynk/context-superpowers.md

# Tool writes back what it learned
synlynk checkpoint --from superpowers --notes "confirmed auth pattern, see memory.md L34"
```

No SDK. No integration fee. Any tool adds this in < 10 lines. What each integrated tool gets for
free: persistent cross-session state, scoped context (not the whole ledger, just what's relevant),
task manifest awareness, active constraint list, cost attribution.

The protocol spec will be published as a standalone document at v0.8 so any tool team can
implement it independently.

---

## 5. The Release Staircase

Each release is usable on its own. Each unlocks a capability the previous release could not provide.
No dead releases.

---

### v0.4.0 — Conventions + Trio Bootstrap

**OS Layer:** IPC — Inter-agent communication established  
**Infrastructure:** Flat files (unchanged)  
**Theme:** First time coordination feels automatic

**Ships:**
- `project-docs/conventions.md` — generated at `synlynk init`, always injected into every agent's
  context alongside memory/roadmap/todo. The shared rules layer: CI patterns, naming conventions,
  constraints, anything that must be true for all agents.
- `synlynk trio init` — configure three named agent slots (Architect, Build, Verify). Writes
  `.synlynk/trio.json`. Slots hold: agent CLI command, model, domain weights, session flags.
- `synlynk run "<task>"` — foreground Architect→Build→Verify pipeline. Blocks until all three
  phases complete. Human reviews the bundle. Phase artifacts written to `.synlynk/jobs/<id>/`.
- Domain keyword inference — scans task description for domain signals (frontend/backend/infra/
  testing/docs). Tags the job. Feeds cold-start routing.
- Round-robin cold-start routing — first 3 samples per domain assigned round-robin to build a
  diverse capability dataset.
- `synlynk doctor` — diagnoses misconfigured trio.json, missing conventions.md, unreachable agent
  CLIs, schema drift.
- Scan + maturity detection — already implemented in unreleased commits; ships here officially.

**Unlock:** `synlynk run "implement login endpoint"` runs Architect → Build → Verify with a single
command. Human reviews the output bundle. Agents coordinate through structured handoffs instead of
shared chat history.

---

### v0.5.0 — Capability Engine

**OS Layer:** Scheduler — data-driven routing  
**Infrastructure:** SQLite WAL replaces scattered .json files (capability scores, telemetry ring)  
**Theme:** synlynk learns which agent is best at what

**Ships:**
- `capability.json` replaced by `capability` table in `.synlynk/state.db` (SQLite WAL). Schema:
  `(agent, phase, domain, score, sample_count, last_updated)`. Recency-weighted formula:
  `score = Σ(rating × decay^age) / Σ(decay^age)` where `decay` defaults to 0.85 per task.
- Data-driven routing activates after 3 samples per (agent, phase, domain) tuple.
- `synlynk score show` — tabular view of current routing matrix by domain.
- `synlynk score add <job-id> <phase> <rating 1-5>` — manual rating after review.
- `synlynk score reset [--agent A] [--domain D]` — reset specific routing weights.
- `synlynk trio status` — current routing assignments with score and sample count.
- `synlynk cost add` — structured cost entry (replaces manual costs.md row editing).
- Shell completions generated for zsh / bash / fish via `synlynk completions <shell>`.
- Config validation with clear error messages on malformed trio.json or config.json.

**Unlock:** After 5–10 tasks, routing is data-driven. If Gemini consistently scores higher on
infrastructure tasks, it gets infrastructure tasks. No configuration required. The routing matrix
is visible and correctable. SQLite WAL means job queries are fast regardless of telemetry volume.

---

### v0.6.0 — Job Control + Constraints

**OS Layer:** IPC layer complete — constraints propagate, context scopes  
**Infrastructure:** SQLite WAL extended to job state machine + event log  
**Theme:** One command freezes all agents during a stability window

**Ships:**
- `synlynk constraint add "<text>" [--expires DATE]` — appends to `constraints` table in state.db,
  immediately injected into every subsequent `synlynk context` output. No more manually updating
  CLAUDE.md, GEMINI.md, AGENTS.md.
- `synlynk constraint remove <id>` / `synlynk constraint list` — manage active constraints.
- Job state machine in SQLite: `pending → architect:running → architect:done → build:running →
  build:done → verify:running → verify:done → awaiting_review → accepted | rejected`.
- `synlynk status [<job-id>]` — current state for active or recent jobs.
- `synlynk cancel <job-id>` — interrupt active job at next safe boundary.
- `synlynk retry <job-id> [--from <phase>]` — restart from a specific phase.
- `synlynk context --task <N>` / `--changed` — scoped context slices (only what's relevant).
- `synlynk next` — recommends next task from todo.md based on status and priority.
- Auto-retry on phase failure: retry with next-best agent for that domain, once. Then halt.
- Handoff artifact format locked: Architect writes `task-packet.md`, Build writes `build-notes.md`,
  Verify reads both and writes `verify-report.md`. Consistent across all jobs.

**Unlock:** `synlynk constraint add "pre-launch stability: no schema changes" --expires 2026-07-01`
propagates to every agent immediately. Zero manual file updates. One source of truth.

---

### v0.7.0 — Async Pipeline + Daemon

**OS Layer:** Shell — background execution  
**Infrastructure:** HTTP Context Server starts; daemon serves context over localhost  
**Theme:** Submit a task, walk away, come back to a review bundle

**Ships:**
- `synlynk daemon start | stop | restart | status` — persistent background process managed via
  launchd (macOS) / systemd (Linux). Stores PID and socket path in `.synlynk/daemon.json`.
- `synlynk dispatch "<task>"` — async job submission. Returns a job ID immediately. Daemon runs the
  pipeline in the background.
- Full job state machine persisted in SQLite (from v0.6); daemon resumes from last completed phase
  artifact on crash/restart.
- **HTTP Context Server** — daemon binds to `localhost:27471` (configurable). Endpoints:
  - `GET /context` — full compiled context.md equivalent
  - `GET /context?for=<tool>` — tool-scoped context
  - `GET /jobs` — active and recent jobs
  - `POST /checkpoint` — tool writes back state
  - `GET /constraints` — active constraint list
  MCP server reads from this. Ecosystem tools read from this. No file I/O for consumers.
- `synlynk review [<job-id>]` — interactive TUI review bundle. Navigate Architect → Build → Verify
  artifacts, rate phases, accept or reject. Keyboard-driven (curses).
- `synlynk schedule add "<task>" --cron "<expr>"` — registers a scheduled job via OS-native
  launchd/cron. Daemon executes on schedule.
- `synlynk queue add "<task>"` / `synlynk queue run` — batch queue for overnight execution.
- Daemon crash recovery: resumes from last completed phase artifact in `.synlynk/jobs/<id>/`.

**Unlock:** `synlynk dispatch "refactor the auth module"` → close the laptop. Daemon runs the
full pipeline overnight. Morning: `synlynk review` opens the TUI. The HTTP Context Server means
ecosystem tools no longer need to read project-docs/ directly.

---

### v0.8.0 — Open Context Protocol + Ecosystem

**OS Layer:** Ecosystem interface  
**Infrastructure:** HTTP Context Server (shipped in v0.7) is now the public interface  
**Theme:** Every tool in your stack gets synlynk's memory — without changing how you use them

**Ships:**
- **Open Context Protocol spec published** — a standalone Markdown document describing the two
  endpoints (`GET /context?for=<tool>` and `POST /checkpoint`) and the context file schema.
  Any tool integrates in < 10 lines with no SDK dependency.
- `synlynk context --for <tool>` — CLI shorthand that calls the HTTP server and writes a
  tool-scoped context file to `.synlynk/context-<tool>.md`. For tools that read files, not HTTP.
- `synlynk checkpoint --from <tool> [--notes "<text>"]` — CLI shorthand for writing back to state.
- **SuperPowers native integration** — a SuperPowers skill that reads `GET /context` at session
  start. Brainstorms are grounded in real project decisions automatically.
- **GStack context bridge** — GStack personas open with synlynk context loaded. Personas don't
  start cold.
- **MCP server** — `synlynk mcp start` exposes context as a Model Context Protocol tool. Any
  MCP-compatible IDE agent (Cursor, Windsurf, VS Code Continue) can call it as a tool during
  inference.
- GitHub Actions sync gateway — CI step that posts job summary back via `POST /checkpoint` so
  non-adopting teammates contribute to state without installing synlynk.

**Unlock:** HermesAgent, OpenClaw, NmoClaw no longer collide because they all see the same task
manifest and active constraints. SuperPowers brainstorms know what decisions have already been
made. GStack personas remember the last session.

---

### v0.9.0 — Review TUI + Team Safety + Agent Identity

**OS Layer:** Shell — polished review UX; team safety guarantees; Tokq bridge prep begins  
**Infrastructure:** JSONL append-only event log backs project-docs/ views; local identity generated  
**Theme:** Review 3 phases of agent work in 60 seconds; team mode is production-safe; identity ready for Tokq

**Ships:**
- **Full curses TUI** — launched by `synlynk review`. Navigate phase artifacts (←/→), rate quality
  (1–5 keys), accept phase (a) or reject (r) with reason. All keyboard, no mouse required.
- Per-job cost roll-up: sum of all phase API costs displayed in review header and in costs.md.
- Cost-weighted scoring option: phases that cost more are weighted more heavily in capability score
  updates.
- Budget alerts at job level (not just session level) — interrupt job if per-job estimate exceeds
  configured `limit_usd_per_job`.
- **Append-only JSONL event log** (`.synlynk/events.jsonl`) — every write to project-docs/ is
  recorded as a structured event. project-docs/ becomes a generated view over the event log.
  Eliminates merge conflicts: two agents writing simultaneously produce two events, not a conflict.
- Pull-before-write guardrail: daemon checks event log head before any write. Surfaces conflicts
  before they land.
- Attribution validation in team mode: rejects commits to project-docs/ that lack `[@username]`
  attribution markers.
- Local team rollups: `synlynk team status` shows per-agent job totals, open blockers, last
  activity timestamp, and attribution compliance rate.
- Textual TUI option (Python Textual framework) — richer panel layout for Rooms (named workspaces
  for multi-project or multi-branch setups). Behind `--ui textual` flag; default remains curses.
- **`synlynk identity init`** (Gap 1 — Agent Identity, FR-1) — generates a local agent identity
  and writes `.synlynk/identity.json`:
  ```json
  {
    "agent_uuid": "<uuid4>",
    "public_key": "<ed25519-pubkey-hex>",
    "public_key_fingerprint": "<sha256-hex>",
    "created_at": "<iso8601>",
    "git_user": "<git config user.name>",
    "git_email": "<git config user.email>"
  }
  ```
  Key generation uses `ssh-keygen -t ed25519` via subprocess (stdlib-safe; available on macOS and
  Linux). Private key stored at `.synlynk/identity.key` with `chmod 600`. Public key registered
  with Tokq at first `synlynk tokq connect`.
- `synlynk identity show` — display current identity (UUID + fingerprint; never the private key).
- `synlynk identity rotate` — generate new keypair, archive old. Old public key stays registered
  with Tokq for read access to existing memory units; new key takes over for writes.
- `synlynk init` updated to call `synlynk identity init` automatically if no identity exists.

**Unlock:** Review TUI + team safety as before. Identity generation means every developer now has a
local cryptographic identity that Tokq Alpha can immediately use — no identity setup step at bridge
connection time.

---

### v1.0.0 — Stable OS + Tokq Bridge Ready

**OS Layer:** Stable platform API  
**Infrastructure:** NATS leaf node schema defined; ready for Tokq Alpha  
**Theme:** Installable from package managers. The foundation Tokq builds on.

**Ships:**
- **Frozen CLI contract** — any breaking change requires a `synlynk migrate` step and a
  MIGRATION.md entry. Semver respected from here.
- **pipx distribution** — `pipx install synlynk`. `pipx upgrade synlynk`.
- **Homebrew tap** — `brew install nikhilsoman/tap/synlynk`.
- `synlynk migrate` — detects schema version of `.synlynk/` and `project-docs/` and upgrades
  in-place. Safe to run on any pre-1.0 project.
- Cross-platform CI matrix: macOS (Intel + Apple Silicon) + Ubuntu LTS. All 47+ tests pass on
  all targets.
- Complete docs: CLI reference, project-docs/ schema reference, Open Context Protocol spec,
  Trio Protocol design, Infrastructure Arc reference.
- **NATS leaf node schema defined** — `.synlynk/tokq.json` holds: leaf server address, subject
  prefix, Ed25519 public key (from `.synlynk/identity.json`). Schema frozen at v1.0. Tokq Alpha
  reads it. No NATS dependency required locally — schema is inert until Tokq connects.
- **Memory unit schema published** (Gap 2 — Memory Unit Schema, FR-2/FR-3) — the mapping defined
  in Section 3.1 is frozen and published as a standalone spec (`docs/tokq-memory-unit-schema.md`).
  Tokq Alpha implements against it. `synlynk sync --dry-run` shows exactly what would be sent
  without connecting, so developers can inspect the serialization before Tokq Alpha ships.
- **Ledger boundary formalized** (Gap 5 — costs.md / Gas Tank, FR-6) — `synlynk tokq balance`
  command stub implemented (returns "Tokq not connected" until Alpha). Clarifies the boundary:
  costs.md tracks local ops permanently; gas tank tracks Tokq cloud ops. No migration.
- Public launch (Hacker News, Product Hunt) — stable enough to recommend to a colleague.

**Unlock:** Install from a package manager. `synlynk` is a dependency teams can take on. Every
developer has a local identity. The memory unit schema is frozen and public. Tokq Alpha knows
exactly what to connect to because everything is waiting for it.

---

### Tokq Alpha — Cloud Bridge + ZK Encryption + Marketplace

**OS Layer:** Cloud bridge active — synlynk becomes a node in the Tokq network  
**Infrastructure:** NATS leaf→hub connection live; `cryptography` package introduced as optional dep  
**Theme:** Local memory goes cloud. conventions.md becomes a publishable product.

This is the first release where synlynk requires an optional external dependency (`cryptography`
package) — but only for users who connect to Tokq. Local-only use remains zero-dependency.

**Ships:**
- **`synlynk tokq connect`** — authenticates agent identity with Tokq using Ed25519 signature
  challenge-response. Registers public key from `.synlynk/identity.json`. Writes connection token
  to `.synlynk/tokq.json`. One-time per identity.
- **Zero-Knowledge Encryption layer** (Gap 3 — FR-4, P0) — client-side encryption before any data
  leaves the machine. Implementation:
  - Uses `cryptography` package (explicit `pip install synlynk[tokq]` or `pipx inject synlynk cryptography`)
  - Each project-docs/ file encrypted with AES-256-GCM
  - Encryption key derived from Ed25519 private key using HKDF-SHA256
  - Tokq cloud stores only ciphertext — cannot decrypt. Verified: if Tokq is compromised, memory
    units are useless without the local private key.
  - Key rotation (`synlynk identity rotate`) re-encrypts all memory units with new key.
- **`synlynk sync`** — serializes project-docs/ into Tokq memory units per the Section 3.1 schema,
  encrypts each, pushes via NATS leaf node. Incremental: only pushes files changed since last sync
  (detected via SHA256 comparison against stored version hash in state.db).
- **`synlynk sync --pull`** — retrieves memory units from Tokq, decrypts, and merges into local
  project-docs/. Conflict resolution: event log timestamp wins (latest write wins per file).
- **`synlynk tokq balance`** — displays gas tank balance, recent transactions, and earning summary.
- **Auto-sync** — daemon (from v0.7) gains a `--tokq-sync-interval` option. Runs `synlynk sync`
  in background on a configurable schedule (default: every 30 minutes when daemon is running).
- **`synlynk publish`** (Gap 4 — conventions.md → Marketplace, FR-5/FR-7) — packages
  `project-docs/conventions.md` (or any specified file) as a Tokq marketplace collection:
  ```bash
  synlynk publish conventions \
    --title "React + FastAPI team conventions" \
    --tags react,fastapi,ci,typescript \
    --price 9.99/month \
    --license cc-by-4.0
  ```
  Validates metadata completeness (title, tags ≥ 3, license), encrypts with a publish key
  (separate from private memory key — public subscribers can decrypt), pushes to Tokq marketplace.
  Returns a listing URL and collection ID.
- **`synlynk subscribe <collection-id>`** — subscribes to a published conventions collection.
  Downloads and merges into local `project-docs/conventions.md` under a `## Subscriptions` section.
  Gas tank auto-deducts subscription fee.
- **`synlynk tokq earnings`** — shows revenue from published collections: subscriber count,
  monthly earnings, 70/30 split breakdown.

**Unlock:** Your project memory survives machine loss, is accessible from any machine with the
same private key, and is shareable with teammates (who have their own identities and read access).
Your conventions.md can earn passive income. The Jan 2026 Tokq vision is now operational.

---

## 6. Release Cadence Targets

| Release | Theme | Target |
|---|---|---|
| v0.4.0 | Conventions + Trio Bootstrap | July 2026 |
| v0.5.0 | Capability Engine | August 2026 |
| v0.6.0 | Job Control + Constraints | September 2026 |
| v0.7.0 | Async Pipeline + Daemon | October 2026 |
| v0.8.0 | Open Context Protocol | November 2026 |
| v0.9.0 | Review TUI + Team Safety | December 2026 |
| v1.0.0 | Stable OS + Tokq Bridge Ready | Q1 2027 |
| Tokq Alpha | Cloud Bridge + ZK Encryption + Marketplace | Q3 2027 |
| Tokq GA | Full marketplace GA, multi-cloud replication, enterprise | Q4 2027 |

Dates are targets, not commitments. Each release ships when it's genuinely usable — never
artificially gated to a calendar date, never shipped in a state that requires the next release to
be useful.

---

## 7. What This Supersedes

The following documents are archived to `docs/archive/`. They contain useful historical context
but no longer represent active decisions:

| Document | Why archived |
|---|---|
| `docs/proposals/consolidated-product-roadmap.md` | Replaced by this doc. Tier model (Solo/Team/Enterprise) retired. |
| `docs/proposals/multi-agent-implementation-plan.md` | Partially executed. SQLite/NATS/Textual TUI arc absorbed above. |
| `docs/proposals/agy-synlynk-opportunity-arch-review.md` | Ecosystem analysis superseded by Open Context Protocol design. |
| `docs/proposals/public-launch-plan.md` | Launch is now v1.0.0, not a standalone event. |
| `docs/proposals/synlynk-agent-workers-assessment.md` | Worker architecture superseded by Trio Protocol. |
| `docs/proposals/synlynk-agent-workers-git-managed.md` | Same. |
| `docs/proposals/2026-06-01-synlynk-polyglot-agent-protocol-bootstrap.md` | Superseded by Open Context Protocol in v0.8. |
| `docs/proposals/synlynk-agent-perf.md` | Performance observations absorbed into capability engine design. |

The following documents remain active:

| Document | Role |
|---|---|
| `docs/superpowers/specs/2026-06-01-synlynk-trio-protocol-design.md` | Canonical Trio Protocol spec — implementation reference for v0.4.0 |
| `docs/superpowers/specs/2026-06-06-synlynk-unified-roadmap.md` | This document — the single source of truth |
| `docs/tokq/Tokq_ Marketplace of Agentic Memory.md` | Tokq PRD — remains active as the cloud layer spec |
| `docs/superpowers/specs/2026-06-01-github-projects-v2-board-integration-design.md` | Active — GitHub Projects integration ships in v0.6.0 job tracking |

---

## 8. Single-File Constraint

synlynk is and must remain a single Python file (`bin/synlynk.py`) with zero external dependencies.
This is a hard constraint:

- No `requirements.txt`, no `pip install`, no virtual environment required.
- SQLite via Python stdlib `sqlite3` — no ORM.
- HTTP context server via `http.server` or `socketserver` — no framework.
- NATS leaf node connection via `socket` / stdlib only, OR a vendored pure-Python NATS client
  inlined directly into `bin/synlynk.py` (< 500 lines). No `pip install nats-py`.
- Textual TUI (v0.9 optional) is the one exception: behind `--ui textual`, requires
  `pip install textual` explicitly documented. Default curses TUI uses stdlib only.

The single-file constraint is what makes `curl | python3` distribution possible and what keeps
`synlynk init` the lowest-friction entry point in the ecosystem.
