# Competitive Landscape

_Last swept: 2026-08-24 (seed — migrated from docs/proposals/competitor-comparison-analysis.md)_

## Segment: solo indie devs building with AI agents
Competitors: Superpowers, GStack

### Capability Gaps
| Capability | synlynk | Superpowers | GStack | Gap |
|---|---|---|---|---|
| State & Memory | A durable, human-and-AI readable ledger (`project-docs/`) with dynamic snapshots | Local checklist directories (`.superpowers/brainstorm`) storing raw task files | Short-term CLI history and session-scoped local context | No — synlynk ahead |
| Tool/CLI Lock-in | Tool-Agnostic<br>Seamlessly bridges Claude, Gemini, Codex, and Cursor | Locked into the specific agent shell running the superpowers skill | Brittle integration<br>Heavily optimized for Claude Code and slash commands | No — synlynk ahead |
| Multi-Agent Coordination | Active Multi-Agent Orchestration via shared event logs and Projects v2 | Basic task division<br>Spawns simple sequential sub-agents | Single-agent execution that shifts between virtual personas sequentially | No — synlynk ahead |
| Safety & Loop Control | Flatline Sentinel: heuristically detects and blocks infinite loop failures | None<br>Runs plans continuously until execution exits | Pre-configured shell command blocking (e.g., preventing `rm -rf`) | No — synlynk ahead |
| Cost & Budget Auditing | Budget Pulse: local cost tracking, request counting, and limit warnings | None<br>No awareness of token counts or financial spend | None<br>Cost is tracked on the provider's billing dashboard | No — synlynk ahead |

### Marketing Gaps
| Positioning vector | synlynk | Superpowers | GStack | Gap |
|---|---|---|---|---|
| Core Value Proposition | Multi-agent context switchboard, state continuity, and quota safety | Runnable custom task plans and sub-agent automation within a specific repo | Virtual engineering team structure (CEO, EM, QA, Reviewer) for Claude Code | No — synlynk ahead |
| UI Ergonomics | Rich Terminal UI (TUI) dashboard with panels for tasks, memory, and logs | Raw CLI output and markdown files | Interactive shell prompts and headless browser visual checks | No — synlynk ahead |
