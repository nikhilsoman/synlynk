# synlynk: Trio Protocol — Design Specification

**Date:** 2026-06-01  
**Status:** Approved — ready for implementation planning  
**Author:** Claude Sonnet 4.6 (brainstorm session with Nikhil Soman)

---

## 1. Context and Evidence Base

This specification defines the rearchitecture of synlynk from a context injector into a
**workgroup orchestrator** for a solo human developer coordinating a trio of AI agents. The design
is grounded in:

- **synlynk current state:** v0.2.2, single-file Python CLI (`bin/synlynk.py`), context injector +
  telemetry + flatline sentinel. Roadmap targets v0.3.0 → v1.0.0 as a "stable Lite" file-based tool.
- **Three hybrid workgroup studies** in `/docs/` — participant-observer analyses of the RxCC.me team
  (1 human, Claude, Gemini, Codex) across ~294 merged PRs, providing empirical failure modes and
  product recommendations.

---

## 2. Assessment: Original Roadmap vs. RxCC Study Observations

### What the Roadmap Gets Right

The v0.3.0 → v1.0.0 staircase is a disciplined engineering progression: fix correctness, nail cost
tracking, reduce context noise, add team-safety, then stabilize. The "Lite → Full" tiering is the
right incremental bet. The v0.5.0 "Scoped context" phase is the most prescient item — all three
studies converge on context asymmetry as the team's biggest daily friction.

### Where the Roadmap Diverges from Study Findings

| Roadmap assumption | Study finding | Gap |
|---|---|---|
| synlynk is a context injector that improves solo workflow | The critical need is cross-agent coordination — shared state, handoff context, constraint propagation | Roadmap never becomes a coordinator |
| Cost/telemetry tracking is the primary value | What's missing is **agent capability tracking** — which agent is actually good at what | Wrong primary metric |
| Team mode is the multi-agent story (v0.6.0) | Multi-agent coordination is needed now for a solo dev with 3 agents — it is not a team feature | Multi-agent delayed too long |
| Context noise is the problem | Context **asymmetry** is the real problem — agents don't share project knowledge | Scoped context solves the wrong dimension |
| v1.0 is a stable file-based Lite tool | The studies describe a need for a persistent coordination substrate accessible to multiple agents | File-based Lite cannot be the destination |

**The core gap:** the roadmap builds a better solo dev assistant. The studies describe a workgroup
coordinator. The solo human + 3 agents use case is exactly where they converge — but only if
synlynk makes the leap from context injector to orchestrator.

### Cross-Agent Study Synthesis: Four Shared Failure Modes

All three studies independently identified the same four failure modes in the RxCC team:

1. **Context asymmetry** — one agent (Claude) carries rich cross-session memory; the others start
   cold every session. Every CI convention violation traces back to this.
2. **Memory asymmetry** — one agent holds all institutional knowledge; single point of knowledge
   failure with no secondary holder.
3. **Manual coordination overhead** — the human is forced into a message-passer role between agents
   who cannot communicate directly.
4. **No constraint propagation** — organizational constraints (embargoes, stability windows) must be
   manually injected into each agent config file separately.

---

## 3. Design Decisions

| Decision | Choice | Reasoning |
|---|---|---|
| Role assignment | **Emergent from usage** — no predefined roles | synlynk tracks performance empirically; routing is earned by data, not assumed by vendor identity |
| Primary interaction | **Autonomous dispatch** — human describes task, synlynk decomposes and routes | Human reviews at the end, not per sub-task |
| Execution model | **Hybrid: lightweight daemon (async) + foreground streaming (sync)** | Two modes sharing identical core infrastructure |
| Domain tagging | **Keyword inference** from job description; `--domain` overrides | Zero-dependency, good enough for 80% of dispatches |
| Cold-start routing | **Round-robin** across all slots until 3 samples per domain | Systematically generates diverse score data |
| Review UX | **Interactive TUI** (curses-based) | Navigate phases, rate, accept/reject in one gesture |
| Phase failure | **Auto-retry once** with next-best agent, then halt and notify | Reduces human interruption for transient failures |
| Verify phase nature | **Fully agent-driven** — Verify agent decides what to run | Maximal flexibility; agent tools injected as suggestions |
| Score decay | **Recency-weighted**, configurable half-life (default: 10 tasks) | Agent improvement surfaces in routing within ~3–4 new jobs |
| Scheduled autonomy | **OS-native (launchd/cron) + agent-native (Claude routines + equivalents)** | Leverages existing harness infrastructure; no 24x7 system required |

---

## 4. Core Primitives

### 4.1 The Trio

Three named agent slots configured by the human at project init. Not Claude/Gemini/Codex hardcoded —
slots with names the human assigns. Stored in `.synlynk/trio.json`.

```json
{
  "schema_version": 1,
  "score_halflife_tasks": 10,
  "test_cmd": "pytest",
  "slots": {
    "A": { "name": "my-claude", "exec": "claude" },
    "B": { "name": "my-gemini", "exec": "gemini" },
    "C": { "name": "my-codex",  "exec": "codex"  }
  }
}
```

`test_cmd` is optional. When present, it is injected into the Verify agent's context as a suggested
test runner command — the agent may run it, extend it, or choose a different approach. No initial
domain affinity hints — cold-start uses round-robin, data drives routing after 3 samples.

### 4.2 The Job

Unit of work. Created on `synlynk dispatch` or `synlynk run`. Has a domain tag, a description, and
flows through up to 3 phases. Persists in `.synlynk/jobs/<job-id>/` across terminal sessions and
machine sleeps.

### 4.3 The Phase Pipeline

Every job moves through a canonical 3-stage pipeline:

| Phase | Purpose | Input | Output artifact |
|---|---|---|---|
| **Architect** | Task packet: spec, acceptance criteria, scope, non-goals, handoff instructions | project context + job description | `task-packet.md` |
| **Build** | Execute the implementation | context + `task-packet.md` | code changes + `build-notes.md` |
| **Verify** | Agent-driven validation — runs tests, reads code, checks correctness | context + `task-packet.md` + `build-notes.md` | `verify-report.md` |

Phases are skippable for trivial tasks:
```bash
synlynk dispatch --phases build "fix typo in auth error message"
```

The human receives a **Review Bundle** at the end — all three artifacts in one interactive TUI view.

### 4.4 The Score

Per-`(agent, phase, domain)` composite score. Drives routing after 3 samples. Stored in
`.synlynk/capability.json`.

**Recency-weighted formula** (half-life = `score_halflife_tasks`):

```
For N samples ordered oldest → newest, sample i has age = (N-1-i):

  weight_i    = 0.5 ^ (age / halflife)

  raw_score_i = (quality_i                        # 0–10, human-rated
                + (10 if correct_i else 0)         # binary correctness
                + rework_penalty_i) / 2            # none=0, minor=−1, major=−3

  score = Σ(weight_i × raw_score_i) / Σ(weight_i)    # result: 0–10 scale
```

Score below 3.0 treated as insufficient signal → falls through to round-robin for that slot.

---

## 5. Two Execution Modes

Both modes share identical core infrastructure: trio config, capability engine, keyword inference,
handoff context, job artifacts, review TUI. The difference is the execution model only.

```
                    ┌─────────────────────────────────────┐
                    │           SHARED CORE                │
                    │  trio.json  ·  capability.json       │
                    │  conventions.md  ·  constraint layer │
                    │  keyword inference  ·  score engine  │
                    │  handoff context  ·  job artifacts   │
                    │  review TUI                          │
                    └──────────────┬──────────────────────┘
                                   │
               ┌───────────────────┴───────────────────────┐
   ┌───────────▼──────────┐               ┌────────────────▼──────────┐
   │  CANDIDATE 1         │               │  CANDIDATE 2              │
   │  Async Mode          │               │  Sync Mode                │
   │  synlynk dispatch    │               │  synlynk run              │
   │  synlynk daemon      │               │  synlynk schedule         │
   │  Persistent daemon   │               │  synlynk queue            │
   │  Human walks away    │               │  No daemon                │
   │  Review later        │               │  Human present            │
   └──────────────────────┘               └───────────────────────────┘
```

Mode is per-invocation, not per-project. Both write to the same job directory. The capability engine
learns from both modes equally.

### 5.1 Async Mode (Candidate 1)

A watchman-style persistent daemon (no TCP port, Unix domain socket only, ~5MB resident):
- Owns the job queue and phase state machine
- Survives terminal closes by persisting all state to disk
- Spawns agent CLI subprocesses via existing `exec_command()` infrastructure
- Notifies via terminal bell + `synlynk status` polling

**Job state machine:**
```
pending
  → architect:running → architect:done
  → build:running     → build:done
  → verify:running    → verify:done
  → awaiting_review
  → [synlynk review accept|reject <job-id>]
  → closed
```

### 5.2 Sync Mode (Candidate 2)

Foreground process, no daemon. Phases flow automatically, streaming agent output to terminal.
Human watches; `Ctrl+C` pauses and drops into an interrupt prompt:

```
[synlynk] Build phase interrupted.
Options: [c]ontinue  [r]edirect to different agent  [a]dd note to next phase
         [s]kip to Verify  [q]uit
```

Choosing `[a]dd note` prompts for free text. The note is appended to the handoff doc injected into
the next phase's context — e.g., "the upload endpoint must handle multipart/form-data, not JSON."
Choosing `[r]edirect` presents the list of available slots and re-runs the current phase with the
chosen agent, using the same handoff context.

Review TUI opens immediately when the pipeline completes.

### 5.3 Scheduled Autonomy (Candidate 2 extension)

**OS-native** (cross-agent recurring work — launchd on Mac, cron on Linux):
```bash
synlynk schedule add "nightly-coverage" --at "22:00" --daily \
  "dispatch --phases build,verify 'run test coverage sweep'"
synlynk schedule list
synlynk schedule remove "nightly-coverage"
```
OS wakes a synlynk process at the scheduled time; it runs queued jobs and exits. No persistent
process required.

**Agent-native** (delegates to agent harness's own scheduler):
```bash
synlynk schedule add "weekly-review" --at "Monday 09:00" --via claude \
  "review architecture decisions and update roadmap"
synlynk schedule add "daily-lint" --at "08:00" --via gemini \
  "scan frontend components for accessibility issues"
```
`--via claude` creates a Claude Code routine with synlynk's context pre-injected. The agent harness
manages the schedule; synlynk provides the context layer. Results land in `.synlynk/jobs/` the same
way as any other dispatch.

**Queue mode** (manual overnight batches):
```bash
synlynk queue add "implement feature X"     # adds to pending queue, does not run
synlynk queue list
synlynk queue run                           # short-lived process, empties queue, exits
```

---

## 6. Context Architecture

### 6.1 Handoff Context Between Phases

Each phase agent receives progressively richer context:

| Phase | Context injected |
|---|---|
| Architect | base `context.md` + job description |
| Build | base `context.md` + `task-packet.md` |
| Verify | base `context.md` + `task-packet.md` + `build-notes.md` |

`generate_context()` gains two new parameters: `agent_slot` (agent-specific context shaping) and
`handoff_doc` (phase-specific injected artifact). Both default to `None` for backwards compatibility
with existing `synlynk exec` usage.

### 6.2 Shared Conventions Layer

`synlynk init` generates `project-docs/conventions.md` — human-maintained file of project rules
(CI conventions, TypeScript patterns, domain boundaries, anything an agent consistently gets wrong).
`generate_context()` always injects it for every agent on every invocation. Not optional, not scoped.

Addresses the #1 recurring failure in the RxCC studies: the CI paths filter omission appearing
independently in Gemini and Codex PRs because neither had access to convention knowledge held only
in Claude's memory.

### 6.3 Constraint Layer

```bash
synlynk constraint add "stability-embargo" --reason "pre-launch" --expires 2026-06-15
synlynk constraint remove "stability-embargo"
synlynk constraint list
```

Active constraints are injected as a first-class warning block at the top of every agent's context,
not buried in `memory.md`. One command propagates to all three agents simultaneously. The daemon
re-injects constraints on every phase start; sync mode re-injects on every `run` invocation.

### 6.4 Domain Keyword Inference

| Domain | Trigger keywords |
|---|---|
| `frontend` | ui, component, react, next, css, style, page, view, layout, modal, form, button |
| `backend` | api, fhir, database, db, migration, endpoint, auth, jwt, server, fastify, route, schema |
| `infra` | pulumi, aws, docker, deploy, ci, workflow, ecs, s3, cloudfront, pipeline |
| `testing` | test, coverage, jest, pytest, e2e, integration, unit, spec |
| `data` | etl, loinc, taxonomy, mapping, transform |
| `docs` | readme, documentation, changelog, roadmap, guide |

Multi-keyword hits → highest-count domain wins. Zero hits → `backend` fallback. `--domain` always
overrides inference.

---

## 7. Full CLI Interface

```bash
# Trio configuration
synlynk trio init                                    # interactive: name 3 slots, set exec commands
synlynk trio status                                  # show slots + current routing assignments

# Async dispatch (Candidate 1)
synlynk dispatch "implement FHIR patient upload"     # Architect → Build → Verify, daemon-managed
synlynk dispatch --phases build "fix auth error"     # skip Architect + Verify
synlynk dispatch --domain backend "..."              # override keyword inference

# Sync run (Candidate 2)
synlynk run "implement FHIR patient upload"          # foreground, streaming, Ctrl+C to pause
synlynk run --phases build "fix auth error"

# Job management
synlynk status                                       # all in-flight jobs + daemon state
synlynk status <job-id>                              # specific job progress + phase assignments
synlynk cancel <job-id>
synlynk retry <job-id> --phase build                 # re-run phase with same agent
synlynk retry <job-id> --phase build --agent B       # re-run with specific slot

# Review (interactive TUI)
synlynk review <job-id>                              # open TUI: navigate phases, rate, accept/reject
synlynk review list                                  # jobs awaiting human review

# Capability engine
synlynk score show                                   # full (agent × phase × domain) matrix
synlynk score show --agent A                         # single agent view
synlynk score add --agent A --phase build --domain frontend --quality 8 --rework none --correct
synlynk score reset --agent A --phase build --domain frontend

# Constraints
synlynk constraint add "name" --reason "..." --expires 2026-06-15
synlynk constraint remove "name"
synlynk constraint list

# Scheduling (Candidate 2)
synlynk schedule add "name" --at "22:00" --daily "dispatch '...'"        # OS-native
synlynk schedule add "name" --at "Monday 09:00" --via claude "..."       # agent-native
synlynk schedule list
synlynk schedule remove "name"

# Queue (Candidate 2)
synlynk queue add "description"
synlynk queue list
synlynk queue run

# Daemon (Candidate 1)
synlynk daemon start | stop | restart | status

# Existing commands — unchanged
synlynk init        # extended: also generates project-docs/conventions.md
synlynk exec        # still works for direct single-agent invocation
synlynk upgrade     # unchanged
synlynk doctor      # extended: checks daemon health, trio config, conventions.md presence
```

---

## 8. Data Model

```
.synlynk/
  trio.json              # slot definitions, score_halflife_tasks
  capability.json        # scored samples per (agent, phase, domain)
  daemon.pid             # daemon process ID (async mode only)
  daemon.sock            # Unix domain socket (async mode only)
  jobs/
    <job-id>/
      job.json           # domain, phases, agent assignments, timestamps, status
      task-packet.md     # Architect output → Build input
      build-notes.md     # Build agent output → Verify input
      verify-report.md   # Verify agent output → Review Bundle
      review-bundle.md   # TUI-rendered synthesis (generated at review time)
      architect-raw.log  # raw agent subprocess output (each phase)
      build-raw.log
      verify-raw.log
  context.md             # existing: generated context snapshot
  sentinel.md            # existing: active alerts
  telemetry.json         # existing: rolling 100-entry log
  config.json            # existing: budget limits
  state                  # existing: watching/active/stopped

project-docs/
  conventions.md         # NEW: always-injected shared conventions (human-maintained)
  memory.md              # existing
  roadmap.md             # existing
  todo.md                # existing
  costs.md               # existing (extended: per-job cost rows)
  devlogs/               # existing
```

**`capability.json` schema:**
```json
{
  "A": {
    "architect": {
      "backend": [
        { "quality": 9, "rework": "none", "correct": true, "ts": 1748736000 }
      ]
    }
  }
}
```

---

## 9. Error Handling

| Failure mode | Response |
|---|---|
| Phase agent exits non-zero or empty output | Auto-retry once with next-best-scored agent for that (phase, domain). Record quality=0 for failed attempt. If retry also fails → halt at that phase, notify via `synlynk status`. |
| Flatline detected (3 consecutive identical exits) | Existing sentinel logic; halt job, write to `sentinel.md`, notify. |
| Daemon crash (async mode) | On next `synlynk` invocation, check `daemon.pid` liveness. If dead, auto-restart; in-progress jobs resume from last completed phase artifact. |
| Domain inference tie | Pick highest-count domain. Alphabetical tiebreak. Always overrideable with `--domain`. |
| Score below threshold (< 3.0) for all slots on a phase | Fall through to round-robin for that assignment. |
| `trio.json` missing | `synlynk dispatch` and `synlynk run` fail fast: `"Run 'synlynk trio init' first."` |
| Agent-native schedule unavailable (e.g. Claude not authenticated) | Fail with clear message: `"--via claude requires an active Claude Code session. Run 'claude' to authenticate."` |

---

## 10. Migration from Current synlynk

**No breaking changes to:**
- `project-docs/` core structure (roadmap, todo, memory, costs, devlogs)
- `synlynk exec` — still works for direct single-agent invocation
- `synlynk init` — extended, not replaced
- `synlynk upgrade` — unchanged
- `.synlynk/config.json`, `telemetry.json`, `state` — all preserved

**Additive changes only:**
- `generate_context()` gains `agent_slot=None` and `handoff_doc=None` parameters
- `.synlynk/` gains: `trio.json`, `capability.json`, `jobs/`
- `project-docs/` gains: `conventions.md` (generated at init, human-maintained thereafter)
- `synlynk init` generates `conventions.md` if not present (idempotent)

---

## 11. Revised Roadmap

| Phase | Goal | Key Deliverables |
|---|---|---|
| **v0.2.x** | Correctness foundation | Current work — exit codes, parser, dead code removal |
| **v0.3.0** | Trio Bootstrap + Sync MVP | `synlynk trio init`, `trio.json`, `synlynk run` (Candidate 2, foreground, no daemon), keyword inference, round-robin cold-start, `conventions.md` generated at init, `doctor` extended |
| **v0.4.0** | Capability Engine | `capability.json`, `synlynk score` commands, recency-weighted routing, per-domain score display, routing decisions logged to telemetry |
| **v0.5.0** | Async Mode + Full Pipeline | Daemon, `synlynk dispatch`, full Architect → Build → Verify with handoff context injection, auto-retry on failure, `synlynk status` / `cancel` / `retry` |
| **v0.5.1** | Context Architecture | `synlynk constraint` propagation to all agent contexts, agent-scoped `generate_context()`, conventions always injected |
| **v0.6.0** | Scheduled Autonomy | OS-native schedule (launchd/cron), agent-native schedule (`--via claude` and equivalents), `synlynk queue` |
| **v0.7.0** | Review TUI + Cost Observability | Full curses-based review TUI, per-job cost roll-up across all phases, budget alerts at job level, cost-weighted scoring option |
| **v1.0.0** | Stable Trio | Freeze CLI/schema, pipx/Homebrew packaging, migration command, cross-platform compat, full docs |

**Explicitly deferred (post-v1.0):**
- Multi-human team collaboration
- Remote sync / cloud backend
- Web UI / dashboard
- LLM-based task auto-decomposition (human provides description; synlynk routes phases by domain tag)

---

*Spec complete. Reviewed and approved by Nikhil Soman, 2026-06-01.*  
*Next step: implementation planning via `superpowers:writing-plans` skill.*
