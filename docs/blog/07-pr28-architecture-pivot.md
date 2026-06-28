---
title: "PR #28 — The Architecture Pivot: Designing the Rest of the OS"
date: 2026-06-09
series: "Building the OS for Multi-Agent Development"
post: 7
pr: "#28"
merged: 2026-06-09
tags: posts
excerpt: "Four design specs, thirteen brainstorm screens, and twelve identified arc gaps. The 2026-06-07 session designed the state DB, agent identity, workspace model, and a complete gap analysis for v0.5–v1.0. The flat-file era ends here."
---

# PR #28 — The Architecture Pivot: Designing the Rest of the OS

**PR:** [chore: 2026-06-07 design session docs — state-db, identity, workspace, arc gap analysis](https://github.com/nikhilsoman/synlynk/pull/28)  
**Merged:** 2026-06-09  
**Contents:** 4 design specs, 13 brainstorm HTML screens, memory + devlog updates, unified roadmap

---

## The Broader Goal at the End of v0.4.0

By v0.4.0, the goal was: autonomous issue pickup and board management. The `synlynk start` command was the first real autonomy primitive. The harness could act on behalf of the user without step-by-step direction.

But the flat-file architecture — `project-docs/roadmap.md`, `todo.md`, `memory.md`, `costs.md`, `devlogs/` — was showing its limits. Multiple worktrees could not safely write to the same files. There was no queryable state. The agentic PM hierarchy had no representation. Agent identity was a GitHub login, not a cryptographic anchor. The workspace concept (one product, multiple repos) had no model at all.

v0.4.0 needed to land before the architecture could be redesigned. This PR is the design.

---

## The Strategic Shift: From File-Based to State-Based

The most important architectural decision in this session is stated as a hard invariant:

> **State never branches. All worktrees share `~/.synlynk/projects/<project_id>/state.db`.**

This is a complete reversal of the file-based model, where each worktree checks out its own copy of `project-docs/`. The flat files work for human-maintained content (decisions written with deliberate thought). They do not work for machine-maintained state (task status, cost accumulation, agent telemetry) where concurrent writes from multiple worktrees produce merge conflicts.

SQLite WAL (Write-Ahead Logging) mode allows concurrent readers and one writer at a time, with readers never blocking the writer. A `~/.synlynk/` location (outside the git worktree) means the database is shared across all worktrees for a given project. A single authoritative state store, accessible from anywhere, with no git-related conflicts.

This shift also enables the second major architectural decision: `project-docs/` is retired at v0.5.0. The human-readable docs that were the primary state store become generated views over state.db, gitignored, and not committed. The ledger moves into the database. The context bridge (`.synlynk/context.md`) remains unchanged — it is still a generated artifact that agents read, but now computed from SQL queries rather than file concatenation.

<figure class="brainstorm-visual">
  <iframe src="/assets/brainstorm/architecture-pivot/architecture-pivot-state-db.html" title="The Architecture Pivot — Flat Files to SQLite" loading="lazy" frameborder="0"></iframe>
  <figcaption>The Architecture Pivot — Flat Files to SQLite</figcaption>
</figure>

---

## The Four Design Specs

### 1. State DB & Agentic PM

**Spec:** `docs/superpowers/specs/2026-06-07-synlynk-state-db-agentic-pm-design.md`

The agentic PM hierarchy that replaces `todo.md` and `roadmap.md`:

```
Arc        — strategic direction (pivot/archive/merge). The layer missing from all PM tools.
  Phase    — structural backbone (was: roadmap row)
    Epic   — one implementation plan (output of the writing-plans skill)
      Story — one agent task: done_criteria + depends_on graph
        Event — append-only universal log
```

The `Arc` level is the novel contribution. Every PM tool has epics and stories. None has the strategic meta-layer: "we pivoted from X to Y because of Z." The arc captures product direction changes with the reasoning attached, making them first-class historical artifacts rather than buried commit messages.

`Story` is the atomic unit of dispatch: a task with explicit `done_criteria`, a `depends_on` graph for sequencing, an `estimated_tokens` budget, and an `assigned_agent` FK into the agent registry. Stories are routed by capability → quota → cost (in that priority order). Token budget replaces story points — it is the quantity that actually matters for autonomous dispatch.

The cost attribution model gains four new FK columns: `story_id`, `epic_id`, `phase_id`, `arc_id`. Every dollar spent is attributable to a specific story in a specific epic in a specific phase. This makes per-feature cost reporting possible for the first time.

The `agent_quotas` table tracks per-agent spending limits within a project — the mechanism that prevents runaway autonomous execution before human review.

**Migration:** `synlynk migrate` (v0.5.0) parses `project-docs/` into `state.db` and untracks the files with `git rm --cached`. One-way, one-time, versioned.

### 2. Agent Identity, Dispatch & Entitlements

**Spec:** `docs/superpowers/specs/2026-06-07-agent-identity-dispatch-design.md`

**Brainstorm visuals:** 
- [Identity Evolution](../brainstorm/v1-architecture/identity-evolution.html) — the progression from agent-tied-to-human → role+competency+scope → capability graph
- [Competency as Vector](../brainstorm/v1-architecture/competency-model.html) — why synthetic agents achieve full-stack as a default and what synlynk's role is

The identity model is **two-layered**:

**Local Identity** — a machine-level Ed25519 keypair at `~/.synlynk/identity.key`, one per person per machine. Shared across all workspaces. Generates a stable `agent_uuid` for each agent slot. This is the cryptographic anchor: all `dispatch_log` rows and completed story events are signed by this key.

Ed25519 was pulled forward from v0.9.0 to v0.5.0 because the case for it became clear: non-repudiable audit trails from day one. A harness that enables autonomous agent actions must have a cryptographic record of who authorized what. Without signatures, the audit log is a text file that anyone can edit.

**Role** — the primary entitlement unit. Three roles: Architect, Builder, Verifier. Roles are stable; they do not change per-session. Agent profiles are dynamic (fitness scores, model version, environment health).

**Four dispatch modes:**

| Mode | Description | When |
|---|---|---|
| A | Daemon persistent listener | Default when daemon is running |
| B | Self-chain (completion re-evaluates) | Multi-step autonomous chains |
| C | `synlynk dispatch` one-shot | Universal fallback; always works |
| D | Agent-native scheduling | When the agent CLI has its own scheduling (Claude Code routines) |

Mode A fails → Mode C always works. The fallback chain is the safety net.

**Entitlements: two layers**

Authorization gates before dispatch:
- `auto` — dispatch immediately
- `approval` — wait for human `synlynk story approve <id>`
- `hold` — pause all dispatch for this story
- `reject` — block permanently

Merge to main is always `approval` — no threshold or override exists for this gate.

Sandboxing constrains while running:
- Token ceiling per story (hard kill above limit)
- Time ceiling (daemon kills process on timeout)
- Network ACLs (block external calls for security-sensitive tasks)
- Path ACLs (restrict file access to project directory)

### 3. Workspace & Multi-Repo

**Spec:** `docs/superpowers/specs/2026-06-07-synlynk-workspace-multi-repo-design.md`

**Brainstorm visuals:**
- [Inter-Agent Communication](../brainstorm/v1-architecture/agent-comms.html) — the GitHub Issues + Projects v2 board-as-IPC model and its evolution
- [Future Comms](../brainstorm/v1-architecture/future-comms.html) — SQLite → Context Server → NATS leaf node progression

**Workspace = one product, N repos.** `~/.synlynk/workspaces/<name>/state.db` is the single state store for all repos in the product. Repos are a `repo_id` dimension within one DB, not separate DBs.

The key design constraint: `synlynk init` in repo #1 creates a workspace transparently (solo = invisible to the user; team = named). `synlynk workspace join <name>` adds repo #2. Auto-detection from GitHub org match makes the common case (same org, same product) zero-configuration.

**Cross-repo Epics** are first-class: a Story has a `repo_id` FK. An Epic spans multiple repos by default. The Architect's context view = full epic across all repos. Builder and Verifier context = workspace shared conventions + repo-specific slice.

**Team sync: event-log via shared git repo.** Per-member branches in a shared git repo, daemon pushing every 5 minutes. Maximum drift between members: ~5 minutes. This is a deliberate choice over a sync endpoint: no new infrastructure, observable history, and the same event format that becomes NATS subjects at Tokq Alpha.

**Simulated team for solo developers.** Switch `git config user.name` to simulate teammates (Gaurav, Kunal). Events record the different git user, same machine key. Full attribution per simulated team member — useful for testing multi-agent dynamics before bringing a real team member online.

### 4. Arc Gap Analysis

**Document:** `docs/superpowers/2026-06-07-arc-gap-analysis.md`

12 design gaps identified across v0.4.0–v1.0.0, prioritized by blocking relationship:

| Priority | Gap | Blocks |
|---|---|---|
| 1 | v0.5.0 scope split | Next impl plan |
| 2 | Constraint vs. entitlement boundary | v0.6.0 |
| 3 | Story state machine unification | v0.6.0 |
| 4 | `synlynk run` vs. `dispatch` overlap | v0.6.0 |
| 5 | HTTP Context Server API | v0.7.0 |
| 6 | Review TUI design | v0.7.0 |
| 7 | Open Context Protocol spec | v0.8.0 |
| 8 | MCP server design | v0.8.0 |
| 9 | Team safety model | v0.9.0 |
| 10 | Network identity / multi-project keypair | v0.9.0 |
| 11 | NATS leaf node schema | v1.0.0, defer |
| 12 | Packaging + distribution | v1.0.0, defer |

Gap #1 (v0.5.0 scope split) is the immediate blocker: the current v0.5.0 spec combines SQLite migration, agent identity, Ed25519, capability routing, and the full PM hierarchy in one release. That is too large. Before writing the v0.5.0 implementation plan, this gap must be resolved into a specific scope split.

**Immediately ready:** v0.4.0 Trio Protocol implementation (no gaps — all design decisions are locked).

---

## The Brainstorm Session: 13 Screens

The v1.0 architecture brainstorm (2026-06-03) produced 7 HTML pages:

| Screen | Topic | Key decision |
|---|---|---|
| [Index](../brainstorm/v1-architecture/index.html) | Session overview | 6-screen survey of all design decisions |
| [Agent Comms](../brainstorm/v1-architecture/agent-comms.html) | Inter-agent communication | GitHub Issues + Projects v2 (B+A) for v1.0 |
| [Future Comms](../brainstorm/v1-architecture/future-comms.html) | Transport evolution | SQLite → Context Server → NATS (same room abstraction at every tier) |
| [Enterprise Scale](../brainstorm/v1-architecture/enterprise-scale.html) | NATS JetStream architecture | 3-tier: Solo daemon = NATS leaf, Team = NATS hub, Enterprise = JetStream cluster |
| [Identity Evolution](../brainstorm/v1-architecture/identity-evolution.html) | Identity model | Role + competency + scope; no biological/synthetic gate |
| [Competency Model](../brainstorm/v1-architecture/competency-model.html) | Competency as vector | Synthetic agents achieve full-stack as default when context-funded |
| [TUI Evolution](../brainstorm/v1-architecture/tui-evolution.html) | Management interface | TUI (Textual) → Web portal → Enterprise admin console |

The GitHub Projects v2 integration brainstorm (2026-06-01) added 4 more screens covering approaches, context, design architecture, and command design — all available at `docs/brainstorm/github-projects-v2/`.

---

## The Competency Vector: synlynk as Context Funding

The competency model brainstorm produced the reframe that is now central to synlynk's product story:

> synlynk is not a "context injector." It is a **context funding mechanism** — the infrastructure that accumulates room history, structures it, and delivers it to agents at retrieval speed.

A biological specialist is constrained by cognitive load. A synthetic agent has no cognitive load constraint; its ceiling is context depth × breadth × retrieval speed. A well-funded synthetic agent — one with deep, structured room history across all domains — achieves full-stack competency as a default.

The competency vector per agent:

```json
{
  "sub": "claude.nikhil",
  "role": "implementer",
  "competency": {
    "backend":  0.95,
    "frontend": 0.60,
    "infra":    0.80,
    "data":     0.70,
    "testing":  0.75,
    "security": 0.65
  },
  "context_funded_by": ["rxcc.feat.>", "rxcc.live.>", "rxcc.deploy.>"]
}
```

Scores are derived from: PRs merged cleanly per domain, incidents caused (negative signal), room history depth per subject, test pass rate, peer review acceptance rate.

This frames synlynk's entire product arc: from context injector (v0.1) to context funding infrastructure (v1.0) to the local client of a distributed context marketplace (Tokq Alpha). Each release increases the depth and breadth of context available to agents; each increase in context depth expands the effective competency of the agents that synlynk runs.

---

## The Revised Roadmap

The unified roadmap that emerged from this session:

| Version | Theme | Infrastructure | Target |
|---|---|---|---|
| v0.4.0 | Conventions + Trio Bootstrap | Flat files | Jul 2026 |
| v0.5.0 | Capability Engine | SQLite WAL | Aug 2026 |
| v0.6.0 | Job Control + Constraints | SQLite extended | Sep 2026 |
| v0.7.0 | Async Pipeline + Daemon | HTTP Context Server | Oct 2026 |
| v0.8.0 | Open Context Protocol | HTTP server (public) | Nov 2026 |
| v0.9.0 | Review TUI + Team Safety | JSONL event log | Dec 2026 |
| v1.0.0 | Stable OS + Tokq Bridge Ready | NATS leaf node schema | Q1 2027 |
| Tokq Alpha | Cloud Bridge | NATS + MessagePack | Q3 2027 |

---

## What This Achieved on the Path to Autonomy

This PR is a design document, not a code change. But design documents that lock architecture decisions are the prerequisite for implementations that compound correctly.

What was locked:

1. **The state DB invariant.** State never branches. All worktrees share one DB. This is the architectural decision that makes reliable autonomous dispatch possible — you cannot safely dispatch from multiple worktrees without a single authoritative state store.

2. **The cryptographic identity.** Ed25519 keypairs, signed events. Autonomous actions leave a non-repudiable audit trail. Without this, the dispatch log is a claim. With it, it is a proof.

3. **The entitlement model.** Authorization + sandboxing as two separate layers. The gate (approve/auto/hold/reject) is separate from the constraint (token ceiling, time ceiling, path ACLs). This layering makes the safety model legible and testable.

4. **The workspace model.** One product = one state DB. Cross-repo Epics as first-class. This is what makes synlynk a platform rather than a per-repo tool.

5. **The 12 arc gaps.** Knowing what is not yet designed is as valuable as knowing what is. The gap analysis is a forcing function: no implementation plan for v0.5.0 can be written until Gap #1 (scope split) is resolved. This prevents over-engineering a release before its dependencies are ready.

---

## Strategic Note: The Goal at the End of This PR

> **The OS for multi-agent development.** synlynk = local OS client. Tokq = distributed backend. Both survive independently; cloud is additive. v1.0 in Q1 2027 defines the NATS leaf schema; Tokq Alpha connects to it in Q3 2027.

The flat-file era ends with v0.4.0. The state-DB era begins at v0.5.0. The architecture is complete enough to be implemented sequentially, release by release, with each release independently useful and the path forward never requiring a rewrite.

The human is still in the loop at every release — as approver, reviewer, and the final merge gate. But the loop gets shorter with each release. v0.4.0: human says "start 42." v0.6.0: human says "run this feature." v0.8.0: agents publish context they produced; other agents consume it without human mediation. v1.0: human reviews the result of an autonomous sprint. Tokq Alpha: the sprint runs across machines, teams, and time zones.

That is the arc. synlynk is the OS that makes it possible.

---

*Next posts in this series will cover each PR from here forward — one post per PR, drafted as part of the synlynk development workflow.*
