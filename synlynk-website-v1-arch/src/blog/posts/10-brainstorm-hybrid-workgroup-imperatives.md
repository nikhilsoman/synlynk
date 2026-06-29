---
title: "The Four Imperatives — Redesigning synlynk's Core Contracts"
date: 2026-06-14
series: "Building the OS for Multi-Agent Development"
post: 10
pr: "—"
type: brainstorm
merged: —
tags: posts
excerpt: "Four gaps surfaced between v0.4.0 and the fully autonomous multi-agent future: instruction reach, static scan quality, an untested capability ledger, and a too-binary task status model. This session redesigned all four into slotted minor releases."
---

## The Broader Goal at the End of the Previous PR

After PR #30 (the E2E test suite), synlynk had a hardened v0.3.1 with 140 passing tests, a restored token extraction pipeline, and a fully spec'd roadmap through v1.0. The stated goalpost was to start implementation planning for v0.4.0 — the Trio Protocol (Architect → Build → Verify pipeline, `synlynk run`).

## Strategic Shifts in This Session

Before writing a single line of v0.4.0 code, we ran a hard gap analysis: how consistent is the current roadmap with what synlynk actually needs to be?

The answer was **~65% aligned, with three material gaps**:

1. `synlynk init` creates blank template files. It should be an intelligent onboarding agent that semantically reads the repo and discovers who's already there.
2. "Agent discovery" and "Hybrid Workgroup formation" weren't specified anywhere in the roadmap.
3. GitHub Projects V2 was named as a PM surface without resolving who owns the canonical data — synlynk or GitHub.

Answering those three questions forced a set of foundational design decisions that will shape every release from v0.4.0 to v1.0. This post documents what we decided and why.

---

## What This Session Designed

### Decision 1: The Hybrid Workgroup is the Core Unit

We retired "solo" and "team" as meaningful distinctions. The right unit is the **Hybrid Workgroup**: one or more humans plus multiple AI agents sharing a synlynk workspace.

A solo developer with Claude + Gemini + Codex running in parallel isn't alone. They have a Hybrid Workgroup. The distinction that matters is whether the human side has one person (Solo Hybrid Workgroup) or many (Team Hybrid Workgroup, spanning machines and network).

This reframe changes the product story: synlynk's job is to **form and operate the Hybrid Workgroup**, not just wrap individual AI tool invocations.

---

### Decision 2: Two Magic Moments in v0.4.0

`synlynk init` becomes a curses TUI wizard with two moments of genuine surprise:

**Magic Moment 1 — "You have a Hybrid Workgroup"**

The wizard scans for installed agent CLIs (`.claude/`, `.gemini/`, Cursor settings, Codex profiles) and presents the capability map:

```
✓ Claude Code  — capability: Architect, Builder
✓ Gemini CLI   — capability: Builder, Verifier
✓ Codex        — capability: Builder

You have a 3-agent Hybrid Workgroup.
Quota problems: solved. Let's assign roles.
```

Most developers have never considered running Claude + Gemini + Codex together. They've been hitting quota walls and working around them one tool at a time. This is the moment they realise the constraint was never technical — it was a missing coordination layer.

**Magic Moment 2 — Parallel dispatch from your shell**

Immediately after init, a developer can run:

```bash
$ synlynk run --trio
▶ Architect (claude) → generating task-packet.md
▶ Builder   (gemini) → implementing feat/auth-fix
▶ Verifier  (codex)  → running tests on story#13
```

Three agents, three stories, in parallel, from the shell. No extra tooling. No daemon. No TUI required. This ships in v0.4.0 using non-interactive agent modes (`claude --print`, `gemini --quiet`) and PID tracking in `.synlynk/jobs.json`. The existing `tee`-based stdout capture from v0.3.1 is extended to background jobs.

---

### Decision 3: Intelligent Init — Two-Pass Semantic Discovery

`synlynk init` stops generating blank templates. It runs a two-pass semantic scan:

**Pass 1 (static, always):** git log parsing, README extraction, file tree analysis → structured skeleton of `roadmap.md`, `memory.md`, `todo.md`. Works offline, zero cost, before any agent is configured.

**Pass 2 (LLM enrichment, opt-in):** After the static pass, synlynk offers:
> "I found 3 services and 47 commits — want me to ask Claude to synthesise a roadmap from this?"

If accepted, logged as a cost event. Produces a narrative first-draft rather than a structured skeleton. The opt-in gate matters: synlynk never spends tokens without asking.

---

### Decision 4: state.db is Canonical — External PM Tools are Async Projections

After evaluating three PM layer options, Option A wins with no meaningful competition:

> `~/.synlynk/workspaces/<name>/state.db` is the source of truth. External PM tools are asynchronously synced representation layers.

The architectural argument is tight: the core invariant ("state never branches") requires a local, always-available store. GitHub Projects V2 has 500ms+ latency per GraphQL call, breaks offline, can't store Ed25519 signatures natively, and forces synlynk's agentic PM hierarchy (Arc/Phase/Epic/Story with token budgets and capability routing) into a human-centric sprint/point model.

The **Async Outbox Gateway** pattern resolves the sync challenge without violating the invariant:

```
Agent writes → state.db (immediate, sub-millisecond)
                   ↓
              Daemon reads outbox queue
                   ↓
         GitHub Projects / Jira / Linear API
         (async, retried if rate-limited or down)
```

External PM changes flow back as signed `external_signal` events applied to state.db. Agent execution never blocks on network.

This means GitHub Projects V2, Jira, and Linear become **bring-your-own display layers** — not owners of data. Teams can use whatever PM tool they prefer; synlynk stays consistent underneath.

---

### Decision 5: The Detachable Command Centre

The interface positioning question was the most strategically important of the session. Three options considered:

**[See: `docs/brainstorm/hybrid-workgroup-imperatives/interface-positioning.html`]**

- **A — Invisible OS:** Background daemon, zero interface gravity. Users never see synlynk during agent work. Forgettable.
- **B — Launcher Hub:** synlynk TUI is your home base; you launch everything from it. Strong gravity but fights developer muscle memory.
- **C — Detachable Command Centre:** synlynk is the home base *and* can be detached. You start from synlynk, dispatch agents, then `Ctrl+D` and go back to Cursor/Claude CLI/whatever you prefer. Re-attach anytime.

**We chose C, with B's launcher primitives integrated.**

The control plane / data plane separation:

| Plane | Surface | What happens here |
|---|---|---|
| Control | synlynk TUI | Dispatch, PM board, capability/quota map, sentinel, PR review |
| Data | Native tool UX | Code editing, interactive brainstorming, local test execution |

The bridge between planes is four launch primitives:

```bash
synlynk open ide --story 42      # opens editor at agent's worktree
synlynk open web --story 42      # opens GitHub/Jira/Linear ticket
synlynk shell --story 42         # subshell inside worktree (human unblocks agent)
synlynk launch claude --story 42 # starts Claude CLI with pre-loaded context
```

**Shell mode is a permanent parallel track.** `synlynk dispatch`, `synlynk jobs`, `synlynk logs` are first-class CLI commands at every release. The TUI is additive. Developers who live in their terminal and never want to switch UX layers get the full Hybrid Workgroup from their existing shell.

---

### The Full Architecture

**[See: `docs/brainstorm/hybrid-workgroup-imperatives/architecture.html`]**

```
┌─────────────────────────────────────────────────────────┐
│  CONTROL PLANE — synlynk TUI                            │
│  Home · Board · Agents · Costs · Sentinel               │
│  Ctrl+D detach  ·  $ synlynk re-attach                  │
└────────────────────┬────────────────────────────────────┘
                     │ 4 launch primitives
┌────────────────────▼────────────────────────────────────┐
│  DAEMON (v0.7.0 — persistent multiplexer)               │
│  Dispatch Loop · Async Outbox · Sentinel · HTTP:27471   │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│  state.db  (canonical, never branches)                  │
│  Arc · Phase · Epic · Story · Event · agent_profiles    │
│  external_refs → GitHub Projects / Jira / Linear        │
└─────────────────────────────────────────────────────────┘
```

---

### The Evolution Path

**[See: `docs/brainstorm/hybrid-workgroup-imperatives/dispatch-evolution.html`]**

The same shell commands get more capable at each release:

| Release | What's new | What's unchanged |
|---|---|---|
| v0.4.0 | Shell-native dispatch, PID tracking, init wizard, two magic moments | No daemon needed |
| v0.5.0–v0.6.0 | state.db replaces jobs.json, capability routing, Ed25519 identity, async outbox | Same shell UX |
| v0.7.0 | Persistent daemon, HTTP context server, proto-TUI (`synlynk attach`) | Shell mode still works |
| v0.9.0 | Full curses TUI, tmux-style pane switchboard | Shell mode still works |

Shell mode never gets deprecated. It's the base layer that always works — on CI, in a headless remote, in any environment that can't render curses.

---

## Two-Spec Plan

This session's output is a two-spec implementation plan:

**Spec 1 — Hybrid Workgroup Bootstrap** (v0.4.0)  
Init wizard + semantic discovery + agent discovery + two magic moments + shell-native dispatch  
Design doc: `docs/superpowers/specs/2026-06-14-hybrid-workgroup-design.md`

**Spec 2 — PM Engine + Detachable Command Centre** (v0.5.0–v0.9.0)  
state.db migration + TUI kanban + async outbox gateway + detach/attach + full daemon + curses TUI  
Implementation planned across four releases.

---

## What This Achieved on the Path to Autonomy

The path to autonomous multi-agent dispatch requires three things to exist: agents that can be addressed individually, a coordination layer that routes work between them, and a PM system that agents can read and write. This session locked the design for all three. v0.4.0 now has a precise scope with two high-impact deliverables that users will feel immediately — not infrastructure they'll appreciate later.

## The New Goalpost

Ship v0.4.0 with two magic moments: the Hybrid Workgroup discovery screen and parallel `synlynk dispatch` from the shell. Every developer who runs `synlynk init` should finish with three agents running in background, context injected, costs tracked — before they've written a single line of code for their project.
