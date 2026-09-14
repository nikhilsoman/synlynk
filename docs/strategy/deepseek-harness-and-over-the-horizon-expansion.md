# DeepSeek Harness (DSH) & Over-the-Horizon Strategic Expansion

**Document:** `docs/strategy/deepseek-harness-and-over-the-horizon-expansion.md`  
**Governing Goal:** `goal-c7113f58` ("Over-the-Horizon Strategic Expansion: DeepSeek Harness (DSH/Cordis) Plugin Architecture, ACP Headless Transport & Herdr Multi-Pane Cockpit")  
**Linked Stories:** `story-b75cb3e7` (DSH Plugin & Cordis Spec), `story-541995f4` (ACP Transport), `story-2348ac34` (Active Herdr Cockpit)  
**Date:** 2026-09-14  
**Author:** Agy (`@agy`, AntiGravity)  
**Status:** PROPOSED & PARKED (Post-v1.0 Over-the-Horizon Expansion Epic)  

---

## 1. Executive Summary & Strategic Horizon

As Synlynk approaches its v1.0.0 Developer Preview Launch (01 October 2026), its core positioning as the **measurement, governance, and control plane for multi-agent software engineering** is solidified. Synlynk orchestrates workspace state (`state.db`), maintains situational context (`.synlynk/context.md`), enforces git worktree boundaries, and assigns Living Charters across diverse execution harnesses (`claude`, `codex`, `agy`, `grok`, `muse`).

This document records the architectural research and strategic expansion roadmap for integrating **DeepSeek Harness (`dsh`)**, transitioning **Herdr** into an active multi-pane cockpit, and federating heterogeneous agent ecosystems (Warp, Antigravity, Replit, Emergent).

These opportunities are parked under `goal-c7113f58` for post-v1.0 execution, ensuring zero distraction from the immediate v0.21.0 FTUE Onboarding release.

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                           OVER-THE-HORIZON EXPANSION TOPOLOGY                                    │
│                                                                                                  │
│   SYNLYNK CONTROL PLANE (GOVERNANCE & ARBITRATION)                                               │
│   • state.db (Stories, Goals, Capabilities, DAGs)                                                │
│   • .synlynk/context.md (Continuous Situational Awareness)                                       │
│   • Git Worktree-First Isolation & Snapshot Rollback                                             │
│   • Living Charters & GitHub App Role Security (@syn-qa[bot], @syn-pm[bot])                      │
│                                                                                                  │
│                     │                                              │                             │
│       VECTOR A: COMPUTE & DISPATCH                   VECTOR B: COCKPIT & SURFACES                │
│                     ▼                                              ▼                             │
│   DEEPSEEK HARNESS (DSH / CORDIS)                ACTIVE HERDR SUPERVISOR                         │
│   • Everything-is-a-Plugin Microkernel           • synlynk herdr init (4-Pane Terminal Cockpit)  │
│   • Headless ACP JSON-RPC Transport              • Interactive worker monitoring & live PTY      │
│   • @synlynk/dsh-plugin ecosystem bridge         • Multi-agent side-by-side airtime              │
│   • Multi-Harness subagents (Claude Code/Codex)  • Strict opt-in (HERDR_ENV=1 guard)             │
│                                                                                                  │
│                     │                                              │                             │
│                     └──────────────────────┬───────────────────────┘                             │
│                                            ▼                                                     │
│                        HETEROGENEOUS AGENT FEDERATION                                            │
│                        • Warp: Native .warp/workflows & Warp AI MCP                              │
│                        • Antigravity: Native skills & 1M-2M context priming                      │
│                        • Replit: replit.nix runtime & embedded Vizor canvas                      │
│                        • Emergent: Ephemeral cloud microVM worker dispatch                       │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Technical Dissection: DeepSeek Harness (`deepseek-ai/deepseek-harness`)

### A. The Core Monorepo & Cordis Microkernel
DeepSeek Harness (`dsh`) is an open-source agent runtime developed by DeepSeek AI, powered by **Cordis** (an Inversion-of-Control microkernel for spatiotemporal composability).

Unlike vendor-locked, monolithic agent CLIs (Claude Code, OpenAI Codex CLI, Gemini CLI), **`dsh` has no privileged core**. Every capability—the agent loop, the tool execution pipeline, session logging, process sandboxing, LLM streaming, and subagent orchestration—is implemented as a plugin mounted on the Cordis dependency injection context (`ctx`).

| Monorepo Package | Responsibility | Cordis Key |
| :--- | :--- | :--- |
| `packages/core/agent-loop/` | Multi-turn driver, request assembly, cancellation escalation | `ctx.agentLoop` |
| `packages/core/tools/` | Scoped tool registry & guarded pipeline (`pre-execute` ➔ `execute` ➔ `post-execute`) | `ctx.tools` |
| `packages/core/session/` | Append-only `SessionEvent` log (`session.vN.jsonl.zstd`). Model-visible means logged. | `ctx.sessions` |
| `packages/core/system-prompt/` | Dynamic prompt-section assembly & tool-schema generation | `ctx.systemPrompt` |
| `packages/mcp/mcp-client/` | Model Context Protocol (MCP) bridge attaching external tool servers | `ctx.mcp` |
| `packages/subagent/` | Subagent drivers: `subagent-claude-code`, `subagent-codex`, `subagent-acp` | `ctx.subagent` |
| `packages/sandbox/` | Filesystem & subprocess isolation backends (local, Docker, eBPF) | `ctx.sandbox` |
| `packages/acp/` | Agent Control Protocol: Headless JSON-RPC automation daemon | `ctx.acp` |
| `packages/llm/` | Pluggable model adapters (DeepSeek, Claude, OpenAI, Local models) | `ctx.llm` |
| `packages/bundle/` | Layered runtime boot profiles (`dsh-base`, `dsh-headless`, `dsh-acp-app`) | N/A |

### B. Core Architectural Superpowers of `dsh`
1. **The Capability Seam Pattern:** Every capability is divided into a *Service Definition* (TypeScript interface on `ctx`), a *Service Provider* (concrete implementation), and a *Consumer* (tool or agent turn). Swapping `ctx.sandbox` moves the entire execution environment to a container without changing a single line of prompt logic.
2. **Subagent Bridges for Claude Code & Codex:** `dsh` already ships with `packages/subagent/subagent-claude-code` and `subagent-codex`, allowing a `dsh` agent to delegate turns to Claude Code and Codex SDK queries within isolated subprocess contexts.
3. **Agent Control Protocol (ACP):** `dsh --profile acp` provides a typed, bidirectional JSON-RPC 2.0 protocol over `stdio` or sockets, eliminating the need for orchestrators to scrape unbuffered terminal output or fight OS signal propagation.
4. **Vibrant Plugin Ecosystem:** Over 11,000 public community plugins exist under GitHub's `dsh-plugin` topic.

---

## 3. The 4 Strategic Integration Vectors for Synlynk

### Vector 1: `dsh` as a First-Class Compute Harness (`synlynk dispatch dsh`)
- **Status Today:** Synlynk dispatches away workers to proprietary vendor CLIs (`claude`, `codex`, `agy`, `grok`, `muse`). Each requires custom flag mapping, permission bypass hacks (`--always-approve`, `--permission-mode`), and brittle token-scraping regexes.
- **The Upgrade:** Add `dsh` as an official harness in `synlynk/_constants.py` and `synlynk/dispatch.py`.
- **Execution Mode:** Dispatched via `dsh --profile headless --task "..."` inside an isolated git worktree.
- **Model Flexibility:** Through `dsh`'s `ctx.llm`, Synlynk can dispatch DeepSeek-R1 (commercial API or local Ollama/oMLX), Claude 3.5 Sonnet, or GPT-4o through a single unified harness interface.
- **Telemetry Truth:** `dsh` outputs structured token, reasoning token (`reasoning_content`), and cache hit metrics directly in JSON, eliminating regex scraping.

### Vector 2: The Official Synlynk Plugin (`@synlynk/dsh-plugin`)
- **Concept:** Publish `@synlynk/dsh-plugin` to npm and GitHub (`dsh-plugin`).
- **Functionality:**
  1. `agent/pre-step` hook injects `.synlynk/context.md` into the agent's system prompt before each turn.
  2. `tools/pre-execute` hook enforces Worktree-First discipline, blocking direct writes to `todo.md` or git commits to `main`.
  3. `ctx.tools` registers Synlynk primitives (`synlynk_checkpoint`, `synlynk_story_done`).
  4. `session/event` hook streams execution metrics directly to `state.db` and `project-docs/costs.md`.
- **Ecosystem Wedge:** Any of the thousands of developers using DeepSeek Harness can run:
  ```bash
  dsh plugin add @synlynk/dsh-plugin
  ```
  Their agent is immediately governed by Synlynk workspace rules, state persistence, and cost tracking.

### Vector 3: Eliminating Subprocess Hazards via ACP (Agent Control Protocol)
- Replace raw OS `subprocess.Popen` with typed JSON-RPC communication targeting `dsh --profile acp`.
- Solves historic daemon-worker issues (#1498, #1572):
  - **Graceful Cancellation:** Cancelling a stuck job invokes `agent/turn-stopping` in `dsh`, terminating subprocess trees without leaving orphaned zombie PIDs.
  - **Real-Time Streaming:** Streams tool calls, model reasoning, and file diffs directly to Synlynk's Vizor observatory without terminal buffering latency.

### Vector 4: Cross-Harness Subagent Federation
- Leverage `dsh` as an **In-Process Multi-Harness Subagent Hub**.
- A single `dsh` worker operating in a worktree can dynamically delegate surgical tasks to Claude Code or Codex subagents while maintaining a single, unified turn log and cost ledger.

---

## 4. Active Herdr Multi-Pane Cockpit (`synlynk herdr init`)

### Current State
Synlynk currently enforces the **Herdr Workspace Protocol** as a passive documentation SOP in `AGENTS.md` and `GEMINI.md`.

### Over-the-Horizon Transformation
Transform Herdr from a passive rule into an active **terminal cockpit supervisor**:

1. **One-Click Workspace Spawning (`synlynk herdr init`):**
   - Automatically generates a 4-pane Herdr workspace layout:
     - **Pane 1 (Conductor):** Interactive session with Home Conductor (Agy or Claude).
     - **Pane 2 (Observatory):** Live `synlynk watch` / HUD monitoring daemon status and active stories.
     - **Pane 3 (Telemetry & Logs):** Real-time log streamer (`synlynk logs -f <job-id>`) tailing running away workers.
     - **Pane 4 (Operator Shell):** Clean terminal shell for the human developer.
2. **Interactive Dispatch Mode (`synlynk dispatch --interactive --pane`):**
   - For complex tasks requiring human-in-the-loop oversight (e.g. interactive debugging or visual verification), Synlynk commands Herdr to spawn the worker in a visible pane, allowing the operator to observe and provide input.
3. **Strict Invariant Preservation:**
   - Remains 100% opt-in: guarded by `test "${HERDR_ENV:-}" = 1`. If unset, Synlynk operates headlessly without Herdr.

---

## 5. Heterogeneous Agent Ecosystem Federation

| Platform | Integration Architecture | Value Proposition |
| :--- | :--- | :--- |
| **Warp** | Native `.warp/workflows/synlynk.yaml` + Warp AI MCP Server | Command-palette autocomplete for all Synlynk CLI verbs and Warp AI status querying. |
| **Antigravity IDE** | Native Skill Pack (`skills/synlynk/`) + 1M–2M Context Priming | Deep repo-wide analytical autonomy without mid-session context compaction. |
| **Replit** | Declarative `replit.nix` daemon service + Embedded Vizor Canvas Extension | Zero-setup cloud development with 3-View Canvas embedded in the Replit editor. |
| **Emergent** | Remote MCP Gateway + Cloud MicroVM Worker Dispatch | Scalable, ephemeral cloud sandboxes for massive parallel swarm refactors. |

---

## 6. Phasing & Milestone Parking

| Horizon | Milestone | Target Deliverable | Governing Stories |
| :--- | :--- | :--- | :--- |
| **Active Focus** | **v0.21.0** | FTUE Onboarding Journey & Visual Workspace (Pillars 1–6) | Active Worktree |
| **Near Horizon** | **v0.22.0** | `dsh` Headless Compute Harness Adapter (`synlynk dispatch dsh`) | `story-b75cb3e7` |
| **Near Horizon** | **v0.23.0** | Active Herdr Cockpit Orchestrator (`synlynk herdr init`) | `story-2348ac34` |
| **Target GA** | **v1.0.0** | Public Developer Preview Launch (`synlynk` on pipx/PyPI) | `goal-85656c82` |
| **Post-GA** | **v1.1.0** | `@synlynk/dsh-plugin` Cordis Ecosystem Release | `story-b75cb3e7` |
| **Post-GA** | **v1.2.0** | Agent Control Protocol (ACP) Daemon Transport | `story-541995f4` |

---

## 7. Decision Attribution

- **Consensus Decision:** Recorded under `goal-c7113f58` with stories `story-b75cb3e7`, `story-541995f4`, and `story-2348ac34`.
- **Contributors:** Agy (`@agy`, AntiGravity), Nikhil Soman (`@nikhilsoman`).
