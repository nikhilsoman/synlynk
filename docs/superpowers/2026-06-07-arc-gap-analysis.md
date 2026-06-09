# synlynk Arc Gap Analysis — 2026-06-07

**Status:** Checkpoint — two major brainstorms complete, gap analysis before implementation planning

---

## What We Have

Three major design sessions as of 2026-06-07:

1. **Unified Roadmap** (2026-06-06) — OS framing, SQLite→NATS arc, Tokq convergence, 5 Tokq bridge gaps resolved
2. **State DB & Agentic PM** (2026-06-07) — state.db schema, Agentic PM hierarchy, migration path
3. **Agent Identity, Dispatch & Entitlements** (2026-06-07) — Ed25519 identity, roles, profiles, dispatch modes, entitlements

Specs:
- `docs/superpowers/specs/2026-06-06-synlynk-unified-roadmap.md`
- `docs/superpowers/specs/2026-06-07-synlynk-state-db-agentic-pm-design.md`
- `docs/superpowers/specs/2026-06-07-agent-identity-dispatch-design.md`

---

## Milestone-Wise Gap Analysis

### v0.4.0 — Trio Protocol
**Status: READY for implementation plan.**

The Trio Protocol spec is complete and approved. No outstanding design gaps. Implement immediately.

Covers: conventions.md, Trio pipeline (Architect→Builder→Verifier), constraint propagation, context injection.

---

### v0.5.0 — State DB + Identity Bootstrap
**Status: SCOPE COLLISION — needs 30-min reconciliation brainstorm before implementation plan.**

Current roadmap assigns to v0.5.0:
- `synlynk migrate` (state.db creation, project-docs/ migration)
- Full Agentic PM schema (arcs, phases, epics, stories, events, memory, agent_quotas, costs, config, external_refs)
- `synlynk identity init` (Ed25519 keypair, agent_uuid)
- `roles`, `agent_profiles`, `entitlements` tables seeded at init
- `synlynk profile probe`

**Gap 1 (blocking): v0.5.0 scope too large for a single milestone.**

The identity/role/entitlements schema additions are conceptually tied to the dispatch work (v0.6.0) more than to the state.db migration. Options:
- v0.5.0 = state.db migration only (migrate + core PM schema + context bridge update)
- v0.5.1 = identity bootstrap (Ed25519 + roles + profiles + entitlements seeded — no dispatch logic yet)

Need to decide: does identity seed at first migration, or is it a separate init step? Answer determines whether v0.5.0 and v0.5.1 can be safely split.

---

### v0.6.0 — Dispatch + Worker
**Status: 3 design gaps before implementation plan.**

**Gap 2: Constraint vs. entitlement boundary.**

`generate_context()` currently injects a constraint block from `conventions.md`. The entitlements spec introduces a separate sandboxing layer enforced at exec time. These two mechanisms need a unified boundary:
- Are constraints (from conventions.md) a subset of entitlements? Or a parallel system?
- Who enforces what? (synlynk wrapper vs. the agent itself via injected instructions)
- What happens if they conflict?

**Gap 3: Story state machine unification.**

State DB spec defines `stories.status` with implicit transitions. Dispatch spec defines inbox/claim/done transitions. These need to be merged into one explicit state machine with defined transitions and who triggers each:
- `pending` → `dispatched` (daemon/dispatch writes inbox)
- `dispatched` → `claimed` (worker claims inbox row)
- `claimed` → `in_progress` (exec starts)
- `in_progress` → `done` | `failed` | `blocked`

Each transition: who can trigger it, what event is emitted, what validation runs.

**Gap 4: `synlynk run` vs. `synlynk dispatch` overlap.**

Current CLI has `synlynk exec <agent>` (manual, with context injection). Dispatch spec introduces `synlynk dispatch` (automated, reads ready stories from state.db) and `synlynk worker --role <role>` (claim + exec loop). The boundary between manual exec and dispatch needs explicit definition — when does a user use `exec` vs. `dispatch`, and can the same story be both manually run and auto-dispatched?

---

### v0.7.0 — Persistent Daemon + HTTP Context Server + Email Bridge + Review TUI
**Status: 2 design gaps before implementation plan.**

**Gap 5: HTTP Context Server API design.**

The infrastructure arc moves from file-based context (`.synlynk/context.md`) to an HTTP Context Server on localhost (v0.7). The API surface is undesigned:
- What endpoints? (GET /context/project, GET /context/story/:id, POST /context/update?)
- Auth? (localhost-only, no auth? or token?)
- How does `generate_context()` in `exec_command()` change? (HTTP call instead of file read)
- Streaming or batch? (impacts latency of `synlynk exec`)
- How does the daemon serve and the worker consume?

**Gap 6: Review TUI design.**

v0.7.0 includes a Review TUI for human approval flows (the `synlynk story approve <id>` path). Design gaps:
- Terminal UI library choice (curses? prompt_toolkit? rich? — must stay zero-dep until Tokq Alpha)
- What does the approval screen show? (story text, done_criteria, estimated cost, affected paths, dispatch_log history)
- Keyboard flow: approve / hold / reassign / view full context
- How does the TUI interact with the daemon? (poll inbox? daemon push to TUI socket?)

---

### v0.8.0 — Open Context Protocol + MCP Server + Scheduling + Email Reply Parsing
**Status: 2 design gaps before implementation plan.**

**Gap 7: Open Context Protocol (OCP) spec.**

The "Ecosystem Interface" OS layer is undesigned at the protocol level. OCP is the public API that third-party tools (GStack, SuperPowers, OpenClaw) use to talk to synlynk. Gaps:
- Protocol format: HTTP REST? stdio? NATS pub/sub? (must be compatible with MCP conventions)
- What operations does OCP expose? (read context, write memory, create story, query state)
- Versioning strategy (OCP v1 should be stable — breaking changes need a major version bump)
- How does the MCP server wrap OCP? (MCP is a transport adapter, not the protocol itself)

**Gap 8: MCP server design.**

The MCP server is synlynk's MCP-protocol adapter for Claude Code and other MCP hosts. Gaps:
- Which MCP tools does synlynk expose? (list-stories, get-context, add-memory, approve-story, etc.)
- How does the MCP server start/stop? (synlynk daemon launches it? separate command?)
- stdio vs. SSE transport? (Claude Code currently supports both; stdio simpler for local)
- Authentication: how does a remote MCP client prove it's authorized to write to this project's state.db?

---

### v0.9.0 — Team Safety + Network Identity
**Status: 2 design gaps, both depend on v0.8.0 completion.**

**Gap 9: Team safety model.**

Multi-user state.db in team mode raises safety questions unaddressed by the single-user entitlements model:
- SQLite WAL handles concurrent reads. What about concurrent writes? (optimistic locking? serialized writes via daemon?)
- In team mode, whose entitlements govern a dispatched story? (the dispatching human's? the role's?)
- How do per-user competency scores work when multiple humans share the same project?
- What constitutes a "conflicting dispatch"? (two agents writing the same file simultaneously)

**Gap 10: Network identity + multi-project keypair.**

v0.9.0 brings Ed25519 signatures to events. Gap: one keypair per project (.synlynk/identity.key) means agents working across multiple projects have N identities. For Tokq Alpha, the cloud needs a stable machine-level identity. Design options unresolved:
- Machine keypair at `~/.synlynk/identity.key` shared across projects
- Project keypair as current spec says, with a Tokq-managed aggregation layer
- Hybrid: machine identity for cloud auth, project identity for local audit

---

### v1.0.0 — NATS + Packaging
**Status: 2 design gaps, defer until v0.9.0 is in flight.**

**Gap 11: NATS leaf node schema.**

NATS replaces state.db inbox as the cross-machine dispatch address at v1.0. Subject schema undesigned:
- Subject naming: `synlynk.<project_id>.<role>` confirmed, but message format is not
- JetStream vs. core NATS? (JetStream for at-least-once delivery; core for fire-and-forget)
- How does the NATS leaf node connect to the Tokq hub? (auth, TLS, subject mapping)
- Message envelope: does the NATS message carry the full story or just the story_id?

**Gap 12: Packaging + distribution.**

synlynk stays single-file through v1.0, but Tokq Alpha introduces the `cryptography` dependency. Packaging gaps:
- How does `pip install synlynk[tokq]` install the optional dep while preserving zero-dep for local use?
- PyPI packaging: sdist + wheel for the single file? Or a thin wrapper package?
- `install.sh` vs. `pip install` for the primary install path — which is canonical at v1.0?
- Homebrew formula: when does it ship, and who maintains it?

---

## Gap Priority Table

| Priority | Gap | Blocking? | Session type | Estimate |
|---|---|---|---|---|
| 1 | v0.5.0 scope split | Blocks v0.5.0 impl plan | Reconciliation (30 min) | ~30 min |
| 2 | Constraint vs. entitlement boundary | Blocks v0.6.0 impl plan | Design brainstorm | ~45 min |
| 3 | Story state machine unification | Blocks v0.6.0 impl plan | Design brainstorm | ~30 min |
| 4 | `synlynk run` vs. `dispatch` overlap | Blocks v0.6.0 impl plan | Design brainstorm | ~20 min |
| 5 | HTTP Context Server API | Blocks v0.7.0 impl plan | Full brainstorm | ~60 min |
| 6 | Review TUI design | Blocks v0.7.0 impl plan | Full brainstorm | ~45 min |
| 7 | Open Context Protocol spec | Blocks v0.8.0 impl plan | Full brainstorm | ~90 min |
| 8 | MCP server design | Blocks v0.8.0 impl plan | Full brainstorm | ~60 min |
| 9 | Team safety model | Blocks v0.9.0 impl plan | Full brainstorm | ~60 min |
| 10 | Network identity / multi-project keypair | Blocks v0.9.0 impl plan | Design brainstorm | ~30 min |
| 11 | NATS leaf node schema | Defer to v0.9.0 in-flight | Full brainstorm | ~60 min |
| 12 | Packaging + distribution | Defer to v0.9.0 in-flight | Design brainstorm | ~30 min |

---

## Immediate Next Steps

1. **Now:** Write implementation plan for v0.4.0 (Trio Protocol) — spec is complete, no gaps
2. **Next session:** Gaps 1–4 reconciliation (v0.5.0 scope split + v0.6.0 design questions) — can likely cover all four in one 2-hour session
3. **After that:** Write implementation plans for v0.5.0 and v0.6.0 in parallel
4. **Then:** Gap 5 + 6 brainstorm (HTTP Context Server + Review TUI) → v0.7.0 plan
