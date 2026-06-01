# synlynk: Trio Protocol — Design Document

**Date:** 2026-06-01  
**Status:** Draft — design phase in progress (Section 1 + 2 approved, Sections 3–7 pending)  
**Session:** Brainstorm — roadmap vs. RxCC study synthesis → rearchitecture for solo human + 3 agents

---

## 1. Context and Evidence Base

This document captures the design session for rearchitecting synlynk to serve a solo human worker
coordinating a "friendly trio" of AI agents. The design is grounded in:

- **synlynk current state:** v0.2.2, single-file Python CLI (`bin/synlynk.py`), context injector +
  telemetry + flatline sentinel. Roadmap targets v0.3.0 → v1.0.0 as a "stable Lite" file-based tool.
- **Three hybrid workgroup studies** (`docs/claude-human-agent-hybrid-workgroup-study.md`,
  `docs/codex-human-agent-hybrid-workgroup-study.md`,
  `docs/synlynk-gemini-human-agent-hybrid-workgroup-study.md`) — participant-observer analyses of
  the RxCC.me team (1 human, Claude, Gemini, Codex) across ~294 merged PRs.

---

## 2. Assessment: Original Roadmap vs. RxCC Study Observations

### What the Roadmap Gets Right

The v0.3.0 → v1.0.0 staircase is a disciplined engineering progression: fix correctness, nail cost
tracking, reduce context noise, add team-safety, then stabilize. The "Lite (file-based) → Full
(daemon-based)" tiering is the right incremental bet. The v0.5.0 "Scoped context" phase is the most
prescient item — all three studies converge on context asymmetry as the team's biggest daily friction.

### Where the Roadmap Diverges from Study Findings

| Roadmap Assumption | Study Finding | Gap |
|---|---|---|
| synlynk is a context injector that improves solo workflow | The team's critical need is cross-agent coordination — shared state, handoff context, constraint propagation | Roadmap never becomes a coordinator; stays a wrapper |
| Cost/telemetry tracking is a primary value | What's missing is **agent capability tracking** — which agent is actually good at what | Wrong primary metric |
| Team mode is the multi-agent story (v0.6.0) | Multi-agent coordination is needed now for a solo dev using 3 agents — it's not a team feature, it's a solo power-user feature | Multi-agent delayed too long |
| Context noise is the problem to solve | Context **asymmetry** is the real problem — agents don't all share the same project knowledge | Scoped context solves the wrong dimension |
| v1.0 is a "stable Lite" file-based tool | The studies describe a need for a persistent coordination substrate — memory that survives sessions, accessible to multiple agents | File-based Lite cannot be the destination |

**The core gap:** The roadmap is building a better solo dev assistant. The studies describe a team
that needs a better workgroup coordinator. The solo human + 3 agents use case is where these converge
— but only if synlynk makes the leap from context injector to orchestrator.

### Key Study Findings (cross-agent synthesis)

All three studies independently identified the same four failure modes:

1. **Context asymmetry** — Claude carries rich cross-session memory; Gemini and Codex start cold
   every session. Every CI convention violation (paths filter omission, missing AGENTS.md) traces
   back to this.
2. **Memory asymmetry** — One agent (Claude) holds all institutional knowledge; no secondary
   knowledge holder. A single point of knowledge failure.
3. **Manual coordination overhead** — the human is forced into a message-passer role because agents
   cannot directly communicate. Coordination scales with agent count as a bottleneck.
4. **No constraint propagation** — organizational risk context (embargoes, stability windows) must be
   manually injected into each agent's config file separately.

The Gemini study named the architecture pattern: the team operates a **"Blackboard Pattern"** —
externalized shared state that all agents read. The recommendation is to move the Blackboard from
flat markdown files into a native synlynk-managed substrate.

---

## 3. Design Decisions (agreed in session)

| Decision | Choice | Reasoning |
|---|---|---|
| Role assignment model | **Emergent from usage** (no predefined roles) | synlynk tracks performance empirically; user assigns roles over time based on observed data, not vendor defaults |
| Primary interaction gesture | **Autonomous dispatch** — human describes task, synlynk decomposes and routes | Human reviews at the end, not per-sub-task |
| Execution model | **Hybrid: lightweight daemon + CLI subprocesses** | Daemon for persistent job state; actual agent invocation stays as CLI subprocess (existing exec_command infrastructure). No full server stack. |

---

## 4. Core Architecture: The Trio Protocol

### The Four Primitives

**1. The Trio**

Three named agent slots configured by the human at project init. Not Claude/Gemini/Codex hardcoded —
slots with names the human assigns. Each slot declares: CLI invocation command, display name, optional
initial domain affinity hint. Stored in `.synlynk/trio.json`.

```json
{
  "slots": {
    "A": { "name": "my-claude", "exec": "claude", "hint": null },
    "B": { "name": "my-gemini", "exec": "gemini", "hint": null },
    "C": { "name": "my-codex",  "exec": "codex",  "hint": null }
  }
}
```

**2. The Job**

The unit of work. Created when the human runs `synlynk dispatch`. A Job has a domain tag, a
description, and flows through up to 3 phases. Each job persists in `.synlynk/jobs/<job-id>/` with
full artifact history. Jobs survive terminal closes and machine sleeps.

**3. The Phase**

Every Job moves through a canonical 3-stage pipeline:

| Phase | Purpose | Input | Output |
|---|---|---|---|
| **Architect** | Generate task packet: spec, acceptance criteria, scope boundaries, explicit non-goals, handoff instructions for Build | project context + job description | `task-packet.md` |
| **Build** | Execute the implementation | context + `task-packet.md` | code changes + `build-notes.md` |
| **Verify** | Test and review — finds what Build missed | context + `task-packet.md` + `build-notes.md` | `verify-report.md` |

The human sees a **Review Bundle** at the end: all three artifacts in one structured view. One review
gesture, not three separate agent outputs to locate.

Phases are skippable for trivial tasks:
```bash
synlynk dispatch --phases build "fix typo in auth error message"
```

**4. The Score**

A per-`(agent, phase, domain)` composite score that drives routing. Built from: quality rating (1-10),
rework needed (none/minor/major), correctness pass/fail. Minimum 3 samples before it drives routing —
cold start uses configurable defaults. Stored in `.synlynk/capability.json`.

```
score(slot-A, Build, backend) = weighted_avg(quality, correctness, inverse_rework)
```

### The Daemon

A watchman-style persistent process:
- Minimal footprint (~5MB resident), no TCP port, Unix domain socket only
- Owns the job queue and phase state machine
- Survives terminal closes by persisting all state to disk
- Spawns agent CLI subprocesses via existing `exec_command()` infrastructure
- Notifies via terminal bell + `synlynk status` polling

**Job state machine:**
```
pending
  → architect:running → architect:done
  → build:running → build:done
  → verify:running → verify:done
  → awaiting_review
  → [synlynk review accept|reject <job-id>]
  → closed
```

**Daemon commands:**
```bash
synlynk daemon start | stop | status
synlynk dispatch "implement FHIR patient upload"   # creates job, enters queue
synlynk status                                      # view in-flight jobs
synlynk review <job-id>                            # open review bundle
```

### The Shared Conventions Layer

`synlynk init` generates `project-docs/conventions.md` — a human-maintained file of hard-won project
rules (CI conventions, TypeScript patterns, domain boundaries, anything an agent consistently gets
wrong). `generate_context()` always injects it for every agent, on every invocation. Not optional,
not scoped — every agent gets it every time.

This directly addresses the #1 recurring failure in the RxCC studies: the CI paths filter omission
appearing independently in both Gemini and Codex PRs because neither had access to the convention
knowledge stored only in Claude's memory.

### The Constraint Layer

```bash
synlynk constraint add "stability-embargo" --reason "pre-launch" --expires 2026-06-15
synlynk constraint remove "stability-embargo"
synlynk constraint list
```

When a constraint is active, the daemon injects it into every agent's context as a first-class
warning block — not buried in `memory.md`. One command propagates to all three agents simultaneously.
Eliminates the need to manually update CLAUDE.md, GEMINI.md, and AGENTS.md separately.

### Context Handoff Between Phases

Each phase agent receives increasingly rich context:
- **Architect:** base `context.md` + job description
- **Build:** base `context.md` + `task-packet.md` (Architect output)  
- **Verify:** base `context.md` + `task-packet.md` + `build-notes.md`

`generate_context()` gains two new parameters: `agent_slot` (for agent-specific context shaping) and
`handoff_doc` (phase-specific injected artifact).

### The Capability Engine

Routing decisions:
```
route(phase, domain) → argmax Score(slot, phase, domain) over all slots
```

Commands:
```bash
synlynk score add --agent A --phase build --domain frontend --quality 8 --rework none
synlynk score show                  # display full capability matrix
synlynk score show --agent A        # single agent view
```

Auto-scoring hooks (future):
- PR passes CI with no review comments → auto-increment quality for Build score
- Verify phase finds Build errors → decrement Build score for that agent

---

## 5. Revised Roadmap

### Original → New Phase Mapping

| Original Phase | Original Goal | New Status | Why |
|---|---|---|---|
| v0.2.x (current) | Correctness patch | **Keep as-is** | Foundation must be solid before building on it |
| v0.3.0 | Reliable solo workflow | **Merged into v0.3 + Trio Bootstrap** | Doctor, completions, config validation still valid; daemon foundation added here |
| v0.4.0 | Cost/accountability | **Reprioritized** — per-job cost, not per-session | Per-dispatch cost (3 phases combined) more useful than per-session tracking |
| v0.5.0 | Scoped context | **Pulled forward + redesigned** as Handoff Context system | Scoped context IS per-phase handoff injection; solves context asymmetry, not just noise |
| v0.6.0 | Team-safe docs | **Largely replaced** by daemon job management | Append-only event log and conflict-safe writes are now the daemon's job queue |
| v1.0.0 | Stable Lite | **Redefined** — "Lite" means Trio Protocol, local-only, no cloud sync | File-backed, daemon-local |

### New Phase Sequence

| Phase | Goal | Key Deliverables |
|---|---|---|
| **v0.2.x** | Correctness foundation | Current work — exit codes, parser fixes, dead code removal |
| **v0.3.0** | Reliable solo + Trio Bootstrap | `synlynk trio init`, `trio.json` schema, daemon foundation, `synlynk dispatch` MVP (single-phase Build, no routing), doctor/completions |
| **v0.4.0** | Empirical Capability Engine | `capability.json`, `synlynk score` commands, routing by composite score, per-domain score display |
| **v0.5.0** | Full Trio Protocol | Architect/Build/Verify pipeline, handoff context injection, Review Bundle, phase skip shortcuts |
| **v0.5.1** | Context Architecture | `conventions.md` always injected, `synlynk constraint` propagates to all agents, agent-scoped context generation |
| **v0.6.0** | Cost & Observability | Per-job cost roll-up across 3 phases, budget alerts at job level, cost-weighted scoring |
| **v1.0.0** | Stable Trio | Freeze CLI/schema, pipx/Homebrew packaging, migration command, full docs, cross-platform compat |

### What Gets Deferred (explicitly)

- Multi-human team collaboration → v1.x
- Remote sync / cloud backend → post-v1.0
- LLM-based task auto-decomposition → not needed for Trio Protocol (human provides description,
  synlynk routes phases by domain tag)
- Web UI / dashboard → post-v1.0

---

## 6. Migration from Current synlynk

The existing `exec_command()`, `generate_context()`, and telemetry infrastructure all survive — they
become the execution substrate the daemon runs on top of.

**Breaking changes:**
- `generate_context()` gains `agent_slot` and `handoff_doc` parameters (backwards compatible with defaults)
- `.synlynk/` gains: `trio.json`, `capability.json`, `jobs/`, `daemon.pid`, `daemon.sock`
- `project-docs/` gains: `conventions.md` (generated at init, human-maintained thereafter)

**No breaking changes to:**
- `project-docs/` core structure (roadmap, todo, memory, costs, devlogs)
- `synlynk exec` command — still works for direct single-agent invocation
- `synlynk init` — extended, not replaced
- `synlynk upgrade` — unchanged

---

## 7. Open Design Questions (to be resolved in next session)

1. **Domain tagging UX** — Does the human always supply `--domain`, or does synlynk infer from the
   description? Keyword matching vs. a lightweight LLM classify call.
2. **Cold-start routing defaults** — What are the sensible defaults for `score(slot, phase, domain)`
   before any data exists? Random rotation? Human-specified initial affinity in `trio.json`?
3. **Review bundle format** — Is the bundle a synthesized markdown file the human opens, or does
   `synlynk review <job-id>` open an interactive TUI that lets the human annotate each phase?
4. **Phase handoff failures** — If the Build agent fails (non-zero exit, empty output), does the
   Verify phase still run? Does the daemon retry? What is the retry policy?
5. **Verify phase nature** — Is Verify always a code-reading/review agent task, or can it invoke
   actual test runners (pytest, jest) and parse results as part of the verification?
6. **Score decay** — Should scores decay over time (older data weighted less) or accumulate flat?
   Recency bias is important if an agent has improved (or the human has started using it differently).

---

*Design session in progress. Next: resolve open questions, then write implementation plan via
`superpowers:writing-plans` skill.*
