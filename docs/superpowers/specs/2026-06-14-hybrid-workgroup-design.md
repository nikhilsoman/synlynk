# synlynk — Hybrid Workgroup Design
**Date:** 2026-06-14  
**Session:** Imperatives gap analysis → two-spec design  
**Status:** Approved for implementation planning  
**Produces:** Two implementation specs — Bootstrap (v0.4.0) and PM Engine + Command Centre (v0.5.0–v0.9.0)

---

## 1. Framing

This design session started from a gap analysis between synlynk's current roadmap and four strategic imperatives:

1. synlynk as the **context bridge** for every agent in a repo
2. **Intelligent `synlynk init`** — semantic discovery, agent onboarding, task allocation
3. **GitHub Projects V2** as external PM surface
4. **Migration from project-docs to SQLite** as the canonical state store

The analysis revealed three under-specified areas: intelligent init, agent/team discovery, and PM layer ownership. This document specifies the design decisions made to close those gaps.

---

## 2. Locked Architectural Decisions

### 2.1 Hybrid Workgroup — Core Unit

The term **Hybrid Workgroup** replaces "team" and "solo" as synlynk's core unit of organisation.

| Term | Definition |
|---|---|
| Hybrid Workgroup | 1+ humans + multiple AI agents sharing a synlynk workspace |
| Solo Hybrid Workgroup | 1 human + multi-AI (Claude + Gemini + Codex) |
| Team Hybrid Workgroup | Multi-human + multi-AI across machines/network |

"Solo" no longer implies single-agent. Even a solo developer gets Claude + Gemini + Codex in parallel — that **is** the first magic moment of `synlynk init`.

**Release scope for multi-human support:** v0.4.0–v0.6.0 support Solo Hybrid Workgroups only (one human + multi-AI on one machine). Team Hybrid Workgroup support (multi-human sync) arrives at v0.7.0 via the event-log daemon, maturing to NATS at v1.0.

### 2.2 Experience Model

| Context | Surface |
|---|---|
| Local dev + local hybrid team | Terminal TUI (curses) — A |
| Cross-team collaboration | Cloud surface (GitHub Projects V2 / Jira / Linear) — C |

The experience is always terminal-native locally. Cloud is the sync projection layer, never the canonical source.

### 2.3 PM Layer — state.db is Canonical

Option A from the evaluation: `~/.synlynk/workspaces/<name>/state.db` is the source of truth. The architectural invariant holds: **state never branches**. External PM tools (GitHub Projects V2, Jira, Linear) are async outbox projections via the `external_refs` table.

The **Async Outbox Gateway** pattern:
- Agent writes story state to state.db immediately (sub-millisecond)
- Daemon queues async sync to external PM APIs (non-blocking)
- External signals (webhooks/polls) are translated to signed `external_signal` events and applied to state.db
- If GitHub API is down, agent execution never blocks

**Conflict resolution default (human signal wins):** When an external PM signal and a local agent update target the same story within the same sync window, the external signal takes precedence. Rationale: a human changing a ticket status on GitHub/Jira is an intentional override, not a race condition. The agent's write is preserved as an `event` log entry but the story's canonical status is set by the external signal. This default can be overridden per-story via a `conflict_policy` field in `external_refs` (e.g., `agent_wins` for fully autonomous stories). Refined in Spec 2 implementation planning.

### 2.4 Interface Positioning — Detachable Command Centre (C + B)

synlynk is a **detachable command centre** with integrated launcher primitives. It is neither purely invisible infrastructure nor a walled garden that competes with native tool UX.

**Control Plane (synlynk TUI):** Dispatching, multi-agent status, capability/quota mapping, PM board, PR review/approval, sentinel alerts.

**Data Plane (native tool UX):** Code editing, interactive brainstorming, local test execution in Claude CLI / Gemini / Codex / Cursor / Windsurf / Opencode / Emergent / etc.

**Four Launch Primitives** (bridge between planes):

| Command | Action |
|---|---|
| `synlynk open ide --story <id>` | Opens configured editor at agent's worktree path |
| `synlynk open web --story <id>` | Opens external PM URL (GH Projects, Jira, Linear) via `external_refs` |
| `synlynk shell --story <id>` | Spawns subshell inside agent's worktree with injected env; daemon resumes on exit |
| `synlynk launch <agent> --story <id>` | Starts agent CLI in story worktree with pre-loaded `context-<agent>.md`; captures telemetry on exit |

**Detach/attach flow:**
```
$ synlynk          ← attach to Hybrid Workgroup
▶ dispatching claude  → story #14
▶ dispatching gemini  → story #15
Ctrl+D             ← detach; agents keep running in background
$ claude           ← user works in native UX
$ synlynk          ← re-attach; see what happened
```

**Shell mode is a permanent parallel track.** `synlynk dispatch`, `synlynk jobs`, `synlynk logs`, `synlynk shell` are first-class CLI commands at every release. The TUI is additive, never a replacement. Power users can run a full Hybrid Workgroup from their existing shell with no UX layer switching.

### 2.5 Init Intelligence — Two-Pass

`synlynk init` uses a two-pass approach:

1. **Static pass (always):** git log parsing, README extraction, file tree analysis → structured skeleton of roadmap.md / memory.md / todo.md. Works offline, zero cost, before any agent is configured. This is **best-effort**: repos without structured commit conventions (Conventional Commits, etc.) will produce a lower-quality skeleton. The wizard surfaces this caveat: "Skeleton generated from git history — results vary by commit style. Review before proceeding."
2. **LLM enrichment (opt-in):** After static pass, synlynk offers: "I found 3 services and 47 commits — want me to ask Claude to synthesise a roadmap?" If accepted, logged as a cost event. Produces a narrative first-draft rather than a structured skeleton.

### 2.6 Agent Discovery — Two-Layer

**Layer 1 — Local scan:**
synlynk scans for installed agent CLIs using configurable discovery paths (defaults: `~/.claude/`, `~/.gemini/`, Cursor settings, Codex profiles; overridable in `.synlynk/config.json` under `agent_discovery_paths`). For each candidate, a **functional check** is run (`claude --version`, `gemini --version`, etc.) to confirm the CLI is installed and executable. Only agents that pass the functional check are presented as part of the Hybrid Workgroup. Agents found but not functional are shown separately with a "configure API key" hint. Infers capability baselines from known CLI × model mappings.

**Layer 2 — Cloud directory (always nudged, never required):**
The v0.4.0 init wizard always shows a nudge step: "Add a second human collaborator" or "Share this workspace with your team." At v0.4.0 this is a placeholder that surfaces the concept and captures intent (email/synlynk ID). A functional cloud registry (Tokq-backed at v1.0, or standalone earlier) backs this step once built — timing deferred to implementation planning. The sharing nudge itself is the **viral trigger**; the registry is the infrastructure that fulfils it.

Cold-start routing: round-robin across all detected agents until 3 samples per (agent × phase × domain). Score decay: recency-weighted, half-life = 10 tasks. Seeded baselines from a capability registry (known Claude/Gemini/Codex strengths) augment empirical scoring from day 0.

---

## 3. Two-Spec Plan

### Spec 1 — Hybrid Workgroup Bootstrap (v0.4.0)

**Scope:**
- Intelligent `synlynk init` TUI wizard (curses, progressive)
- Two-pass semantic discovery (static skeleton → LLM enrichment opt-in)
- Agent/CLI discovery → capability profiles
- Magic Moment 1: "You have Claude + Gemini + Codex"
- Magic Moment 2: `synlynk dispatch <agent> --story <id>` runs agents in background from shell, right now
- Shell-native dispatch: `synlynk dispatch`, `synlynk jobs`, `synlynk logs`
- PID tracking in `.synlynk/jobs.json` (no daemon required)
- `synlynk shell --story <id>` and `synlynk launch <agent> --story <id>`
- Cloud directory nudge in wizard ("add more agents / share workspace")

**Technical notes:**
- Non-interactive agent modes only at v0.4.0: `claude --print`, `gemini --quiet`, `codex run` — no PTY needed
- `tee`-based stdout capture (already in v0.3.1) extended to background jobs
- `.synlynk/jobs.json`: `[{id, agent, story_id, pid, worktree, started_at, status}]`
- **PID reconciliation on startup:** On every `synlynk` invocation (any subcommand), before reading `jobs.json`, synlynk checks each recorded PID via `os.kill(pid, 0)`. PIDs that raise `ProcessLookupError` are marked `failed` with `ended_at = now`. This prevents stale jobs surviving across reboots or external kills.
- Context injection per agent: `.synlynk/context-<agent>.md` generated by `generate_context()` with agent-scoped view
- Single-file / zero-pip-dep constraint holds
- **`synlynk dispatch` vs `synlynk run --trio`:** These are distinct commands with distinct semantics. `synlynk dispatch <agent> --story <id>` dispatches a single agent to a single story in background — the atomic unit. `synlynk run --trio` dispatches three independent parallel jobs (one per detected Architect/Builder/Verifier role) simultaneously — a convenience wrapper over three `dispatch` calls, not a sequential pipeline. The sequential Architect→Build→Verify pipeline with handoff artifacts (`task-packet.md` → `build-notes.md` → `verify-report.md`) is the Trio Protocol spec (v0.4.0 Trio Bootstrap), a separate feature from parallel dispatch.

**Release target:** v0.4.0

---

### Spec 2 — PM Engine + Detachable Command Centre (v0.5.0–v0.9.0)

**Scope:**
- `state.db` migration (`synlynk migrate`) — project-docs/ → Arc/Phase/Epic/Story/Event schema
- TUI kanban board (Arc → Phase → Epic → Story columns)
- Detach/attach protocol (`Ctrl+D` detach, `synlynk` re-attach)
- Async outbox gateway — state.db writes → GitHub Projects V2 / Jira / Linear (non-blocking)
- External signal ingestion (webhook/poll → signed `external_signal` events → state.db)
- `synlynk open ide` and `synlynk open web` primitives
- Agent capability routing (capability score → quota headroom → cost)
- Ed25519 agent identity (pulled forward from v0.9.0 to v0.5.0)
- Persistent daemon (v0.7.0) — multiplexer: dispatch loop, outbox queue, sentinel watch, HTTP context server
- Full curses TUI with tmux-style pane switchboard (v0.9.0)
- Cross-team event-log sync (v0.7.0 → NATS at v1.0)
- **Zero-pip-dep constraint:** Holds through v1.0. NATS transport uses an inlined pure-Python NATS client (no pip install required) as decided in memory.md. The `cryptography` package is the single planned exception, introduced at Tokq Alpha as `pip install synlynk[tokq]` — optional, never required for local-only use.

**Roadmap alignment:**

| Release | Spec 2 deliverable |
|---|---|
| v0.5.0 | state.db migration, capability routing, Ed25519 identity, async outbox stub |
| v0.6.0 | Job control, constraint propagation, `synlynk open ide/web` |
| v0.7.0 | Persistent daemon, HTTP context server, proto-TUI (`synlynk attach`) |
| v0.9.0 | Full curses TUI, tmux pane switchboard, team safety |

---

## 4. Visual Companion

Three diagrams produced during this session, committed to `docs/brainstorm/hybrid-workgroup-imperatives/`:

| File | Content |
|---|---|
| `interface-positioning.html` | A/B/C interface positioning models with pros/cons |
| `architecture.html` | Full system architecture: control plane, data plane, daemon, state.db, two-spec plan |
| `dispatch-evolution.html` | Shell-native dispatch in v0.4.0 → daemon v0.7.0 → TUI v0.9.0 evolution; two magic moments |

---

## 5. What This Changes in the Roadmap

| Area | Before | After |
|---|---|---|
| `synlynk init` | Creates blank template files | TUI wizard with semantic scan + magic moment |
| Agent discovery | Not specified | Local CLI scan → capability profiles → cloud directory nudge |
| v0.4.0 scope | Trio Protocol (conventions + pipeline) | Trio Protocol + shell-native dispatch + init wizard |
| Interface model | Not specified | Detachable command centre; shell mode permanent |
| PM layer | state.db planned for v0.5.0 | Unchanged; async outbox pattern added |
| Cold-start routing | Round-robin (empirical only) | Seeded from capability registry + empirical scoring |
| "Solo" definition | One developer | One human + multi-AI (Hybrid Workgroup) |

---

## 6. Open Questions (deferred to implementation planning)

1. **Multi-repo init:** When `synlynk init` discovers a linked repo (via git submodules, workspace config, or GitHub org match), does the semantic scan span repos or stay local?
2. **Capability registry seed data:** What does synlynk ship as known baseline competencies for Claude/Gemini/Codex? Who maintains this and how does it update?
3. **PTY wrapper for interactive agents:** Non-interactive mode ships in v0.4.0. Full interactive agent panes (for `synlynk launch` in interactive mode) need PTY — deferred to v0.7.0 daemon.
4. **Onboarding wizard depth:** Does the TUI wizard run every time on a fresh repo, or only when no `.synlynk/` exists? Behaviour on partial init?
5. ~~**Async outbox conflict resolution**~~ — resolved in §2.3: human signal wins by default; overridable per-story via `conflict_policy` in `external_refs`.
