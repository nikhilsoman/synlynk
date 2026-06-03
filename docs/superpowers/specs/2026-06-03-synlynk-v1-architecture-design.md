# synlynk v1.0 Architecture Design

**Date:** 2026-06-03
**Status:** Draft — pending user review
**Session:** Brainstorm — rxcc practices → synlynk v1.0 release plan
**Covers:** Agent comms, identity model, competency model, TUI/management interface, v1.0 autonomy model, scaling path to enterprise

---

## 1. Design Decisions (locked)

### 1.1 Inter-agent communication — v1.0

**Decision: GitHub Issues + GitHub Projects v2 (B+A combined)**

- The GitHub Issue is the unit of work AND the audit/instruction thread
- The GitHub Projects v2 board is the coordination layer (who owns what, what state it's in)
- `synlynk start <issue-id>` claims the item: moves board column to In Progress, sets Agent field via GraphQL, posts WIP signal to room
- Agents comment on issues for handoff notes; board column movement is the coordination primitive
- No new infrastructure required for v1.0

**Rationale:** Maps exactly to how rxcc already operates. Every protocol we've proven in rxcc (LIVE-N issues, PR discipline, board routing) plugs straight in.

### 1.2 Future comms — v1.x → v2.0 → Enterprise

**Decision: SQLite → Context Server with Rooms → NATS leaf nodes**

Three-phase evolution, same abstraction at every tier:

| Phase | Transport | When |
|---|---|---|
| v1.x | SQLite WAL (`~/.synlynk/state.db`) | Solo — replaces file-watching |
| v2.0 | stdlib HTTP/WebSocket Context Server (SQLite-backed) | Solo+ — rooms, scoped context, WIP signal |
| Team+ | NATS leaf node → hub | Team/Enterprise — replicated rooms, RBAC |

**The room abstraction is the stable interface.** Transport is swappable. Agents subscribe to rooms; synlynk delivers scoped context slices. The monolithic `context.md` is replaced by room-scoped snapshots.

**Rooms are named as NATS subjects from day one** (`rxcc.feat.di7`, `rxcc.live-issues`, `rxcc.deploy`) so the naming survives the transport upgrade without migration.

**Message format:** MessagePack at every tier — binary, ~40% smaller than JSON, no schema lock-in, NATS payload-agnostic.

### 1.3 Enterprise scaling — NATS JetStream

NATS leaf node architecture maps to the 3-layer org hierarchy natively:

- **Layer 1 (Solo):** synlynk daemon IS the leaf node, minus the network hop (SQLite is the local JetStream)
- **Layer 2 (Team):** leaf nodes connect upstream to a team NATS hub (self-hosted or Synadia Cloud)
- **Layer 3 (Enterprise):** hub connects to org-level JetStream cluster — durable, replicated, multi-region, SSO-gated

The local Solo daemon we build in v1.x becomes a NATS leaf node by configuration in Team tier. Agent-facing API does not change.

### 1.4 Identity model

**Decision: `{role, competency-vector, scope, engine-tag, owner}` — no biological/synthetic gate**

```json
{
  "sub": "claude.nikhil",
  "role": "implementer",
  "competency": {
    "backend": 0.95, "frontend": 0.60, "infra": 0.80,
    "data": 0.70, "testing": 0.75, "security": 0.65
  },
  "scope": ["rxcc.feat.>", "rxcc.live.>"],
  "engine": "claude-sonnet-4-6",
  "owner": "nikhil"
}
```

**Rules:**
- `engine` is an audit tag, never drives access decisions
- `is_human` field does not exist — authority derives from `role`, not biological status
- "Human must approve deployments" is implemented as `role: deploy-authority required` — today only humans hold that role; the gate is portable
- Full-stack threshold: all competency dimensions ≥ org-configured threshold (default 0.75). An agent meets it or it doesn't — no special flag.

### 1.5 Competency as vector, not label

Competency is a `{dimension: score}` map, not an enum. Scores are derived from verifiable history: PRs merged cleanly, incidents caused (negative), room history depth, test pass rate, peer review acceptance.

**Synthetic agents achieve full-stack by default** once room history is deep enough across all domains — no cognitive load constraint. A well-funded synthetic agent with broad room subscriptions will have a fuller competency vector than most biological specialists.

**synlynk's true value proposition:** It is a **context funding mechanism**. Rooms accumulate the structured history that builds agent competency profiles. Deeper, broader rooms → higher competency scores → more capable agents. The depth of a team's room history is the org's competitive moat.

### 1.6 Management interface

**Decision: `synlynk` (no-arg) opens the TUI. All panels in one command.**

- **Technology:** Textual (Python) — rich interactive terminal, CSS-like styling, composable widgets
- **`synlynk`** with no args opens the TUI. Existing subcommands (`init`, `checkpoint`, `exec`, `watch`, `status`) continue to work as before.
- **Extensible:** Panels are Textual widgets. New panels can be added without touching core. Plugin architecture from the start.
- **Principle:** Everything operationally relevant is visible from here — no separate commands needed to see what synlynk knows.

---

## 2. v1.0 Autonomy Model

### 2.1 The model

```
Human: roadmap · design · implementation plans (sole authority)
          ↓
Claude: breaks plans into GitHub tickets → assigns to board → routes to agents
          ↓
Agents (Claude + AntiGravity + Codex): implement from tickets autonomously
          ↓
Claude: all deployments — with owner approval gate
          ↓
Human: merges PRs · approves deployments · reviews board
```

### 2.2 Invariants

1. Human is the sole authority on roadmap, design decisions, implementation plans
2. Plans are broken into GitHub tickets by Claude — one ticket per agent per task, never bundled
3. Each ticket has: domain label (→ agent routing), implementation spec, acceptance criteria, branch name
4. Agents work on independent branches, open PRs — never commit directly to master
5. PR peer review: circular (Claude → AntiGravity reviews → Codex reviews → Claude reviews)
6. Deployments: Claude executes, owner approves — `role: deploy-authority` gate in synlynk
7. rxcc is not disrupted at any point — synlynk changes are applied via worktrees, validated before merging

### 2.3 `synlynk start <issue-id>` — the autonomy driver

This is the command that drives autonomous inter-agent communication:

```
synlynk start <issue-id> [--context <extra>]
```

What it does:
1. Reads issue body + labels from GitHub
2. Reads active rooms relevant to this issue (scoped context slice)
3. Sets board: Agent field + Status = In Progress via GraphQL
4. Posts WIP claim to room (`{type: "wip-claim", issue: N, agent: "claude.nikhil", branch: "feat/...""}`)
5. Injects: issue body + context slice + agent instructions + handoff history
6. Launches the agent session

On session end:
1. Agent posts handoff message to room with structured payload
2. Board moves to In Review, Peer Reviewer set
3. Next agent's `synlynk start` picks up the handoff from room history

---

## 3. TUI — Panel Architecture

### 3.1 Five core panels (v0.4.0)

| Panel | Contents | Key actions |
|---|---|---|
| **Dashboard** | Budget gauge, active rooms, sentinel alerts, recent activity log | — |
| **Board** | Live GH Projects v2 kanban, routing rules display | `n` new issue, `enter` open, `r` refresh |
| **Agents** | Edit CLAUDE/GEMINI/AGENTS/AntiGravity.md, diff vs template, competency bars | `e` edit, `d` diff, `r` reload |
| **Memory** | Searchable decision log (project-docs/memory.md + room history) | `/` search, `e` edit, `a` append |
| **Messages** | Room browser, decoded MessagePack viewer, export | `/` filter room, `d` decode, `x` export JSON |

### 3.2 Solo+ additions (v1.x)

| Panel | Contents |
|---|---|
| **Competency** | Per-agent radar, full-stack threshold, score history, room subscription map |
| **Rules** | Routing rules editor (domain → agent), approval gates, competency thresholds |
| **Rooms** | Subscribe/unsubscribe, view history depth, purge old entries, room search |
| **Files** | Context bridge path browser, raw file viewer for any project-docs file |
| **Config** | All synlynk config: GH Projects v2 board/field/option IDs, budget limits, watch interval, agent credentials |

### 3.3 Extensibility

- Each panel is a Textual `Screen` subclass
- Panels register themselves via a `PANELS` registry in `synlynk_ui.py`
- Third-party panels: drop a Python file in `~/.synlynk/panels/` — auto-discovered at startup
- Panel manifest specifies: name, shortcut key, min synlynk version, required config keys

---

## 4. Templates — What `synlynk init` Generates (v0.3.0)

### 4.1 Agent instruction files generated

| File | For | New in v0.3.0? |
|---|---|---|
| `CLAUDE.md` | Claude Code | Enriched (was bare) |
| `GEMINI.md` | Gemini CLI | Enriched (was bare) |
| `AGENTS.md` | Codex | **New** |
| `AntiGravity.md` | Google AGY CLI | **New** |
| `AI_INSTRUCTIONS.md` | Universal fallback | Enriched |
| `.cursorrules` | Cursor | Minimal (unchanged) |

### 4.2 What enriched templates contain (generic, non-project-specific)

All four main agent files gain:

- **Domain ownership** — parameterized table (`TODO: fill domains for this agent`)
- **Git worktree-first policy** — never commit to master, worktree per feature
- **Branch naming per agent** — `feat/<agent-prefix>/<description>`
- **Commit trailer per agent** — `Co-Authored-By: <engine> <noreply>`
- **Live issues SOP** — `[LIVE-N]` numbering, severity table, RCA doc path pattern
- **Mid-session anti-amnesia** — Phase 1 every ~25K tokens, Phase 2 every ~5K tokens
- **Mandatory 4-doc discipline** — roadmap + devlog + costs + memory, mid-session update rules
- **GitHub Projects v2 integration block** — GraphQL mutation templates with `TODO: PROJECT_ID` / `TODO: FIELD_ID` placeholders
- **`synlynk start` as session driver** — reference to autonomous workflow

### 4.3 `synlynk init` flags

```
synlynk init [--force] [--org ORG] [--repo REPO] [--project-id ID]
             [--agents claude,agy,codex] [--mode solo|team]
```

`--project-id` fills the GitHub Projects v2 GraphQL mutations with real values at init time. Without it, templates get `TODO:` placeholders.

---

## 5. Release Roadmap (revised)

| Release | Theme | Key deliverables |
|---|---|---|
| **v0.3.0** | Multi-agent foundation | Enriched templates (CLAUDE/GEMINI/AGENTS/AntiGravity.md), live issues SOP, worktree policy, mid-session protocol, `synlynk init` flags, CHANGELOG + README + site update |
| **v0.4.0** | Autonomy driver | `synlynk start <issue>`, GH Projects v2 native board sync, WIP signal in rooms (SQLite), `synlynk` TUI (5 core panels, Textual) |
| **v0.5.0** | Context funding | SQLite Context Server, room subscriptions, scoped context slices replace monolithic context.md, competency tracking |
| **v0.6.0** | Solo+ management | Competency panel, Rules panel, Rooms panel, Files panel, Config panel (all GH Projects v2 config from TUI), extensible panel registry |
| **v1.0.0** | Full autonomy | Complete autonomy model (human→plan→tickets→agents→PR→deploy), NATS-ready credential schema, trust scores, release automation, migration command |

---

## 6. What Stays Project-Specific (Never in Public Templates)

- GitHub Project ID, field IDs, option IDs (parameterized via `--project-id`)
- Tech stack (Next.js, Prisma, FHIR, LOINC, etc.)
- rxcc encryption engineering practice
- AWS/DPDP compliance specifics
- Agent confidence ratings for a specific workgroup
- Per-repo agent assignment history

---

## 7. rxcc Preservation (Imperative)

- All synlynk changes are developed on feature branches in the synlynk repo
- synlynk is applied to rxcc only after v0.3.0 is validated and released
- `synlynk init --force` in rxcc must merge, not blindly overwrite — v0.3.0 needs to add a preview/diff step before writing. rxcc-specific content (real GH Project IDs, tech stack, encryption practice) must survive the merge.
- rxcc's existing CLAUDE.md and GEMINI.md are the source of truth for what the enriched templates should contain — no rxcc-specific detail moves into the public template
- Rollback plan: rxcc has CLAUDE.md and GEMINI.md in git — any bad `init --force` is a `git checkout` away

---

## 8. Open Questions (not blocking v0.3.0)

1. Does AntiGravity.md replace GEMINI.md, or do both exist? (AGY CLI vs Gemini CLI are different products)
2. `synlynk` no-arg: if Textual is not installed, should it fall back to `synlynk status` output or error with install instructions?
3. Trust score computation: purely from synlynk-observable history (PRs, rooms) or does it accept external signal (CI pass rate via GitHub Actions API)?
4. Panel plugin discovery: `~/.synlynk/panels/` (user-global) + `.synlynk/panels/` (project-local) — or just one location?
