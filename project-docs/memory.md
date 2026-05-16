# synlynk Memory

## Decisions
- **Naming:** Finalized project name as **synlynk** (replacing Project Pulse). [@nikhilsoman]
- **Structure:** Uses `/project-docs` for core records and `/project-docs/devlogs` for attribution. [@nikhilsoman]
- **Collaborative Logic:** Team Mode is a first-class citizen, requiring attribution tags `[@username]`. [@nikhilsoman]
- **Delivery:** Single-command bootstrap via `install.sh`. [@nikhilsoman]
- **Tiered Strategy:** 
    - **Free/Solo:** Optimized dev workflow for CLIs (Claude/Gemini/Codex). Focus on Context, Project, Cost, Model, Skill, and Environment management.
    - **Paid/Team:** Hierarchical team scope with roll-up observability for leadership. [@nikhilsoman]
- **Architectural Vision:** synlynk as a "Context Switchboard" (CLI/Daemon) using MCP and wrappers to provide state to stateless AI engines across CLIs and IDEs. [@nikhilsoman]
- **Shipping Strategy:** Incremental "Lite" (File-based) -> "Full" (Daemon-based) Free tier progression. [@nikhilsoman]
- **Auto-Update:** Binary and template updates must be seamless and baked into the CLI (`synlynk upgrade`). [@nikhilsoman]

## Architectural Resolutions
- **Concurrency:** Use an **Append-Only Event Log** for devlogs and tasks. The synlynk daemon reconciles the log into the markdown "view" to prevent file-locking conflicts during multi-agent execution.
- **Frictionless Telemetry:** Use shell aliases (e.g., `alias claude='synlynk exec claude'`) during `synlynk init` to capture telemetry without changing user habits.
- **"Vibe" Calculation:** Focus on **Git Diff Velocity** and **Terminal Loop Detection** for S:H ratio, avoiding invasive LSP tracking in the Lite tier.
- **Sentinel Authority:** In Lite tier, the Sentinel injects "Context Warnings" into the `.synlynk/context.md` file. In Full tier, it can send `SIGINT` to the wrapper process to stop loops.
- **Privacy:** Aggregate **Metadata & Vectors** (latencies, token counts, task status) for team rollups, never raw code.
- **Context Compaction:** Implement an "Active vs. Archive" model. `.synlynk/context.md` will only compile *active* tasks and the *current* sprint's devlogs. Older logs (e.g., `devlogs/archive/2026-Q1.md`) are excluded from the main context block to save tokens but remain available on disk for specific RAG/grep queries if the AI needs historical context.
- **Sub-Agent Routing:** Main agents receive the full `.synlynk/context.md` "Switchboard Snapshot". When a main agent delegates to a sub-agent (e.g., `codebase_investigator`), it must pass a *task-scoped* slice of context rather than the global state. synlynk will support this by generating specialized sub-views (e.g., `.synlynk/context_tests.md`) or relying on the main agent to filter the context during delegation.

## Conventions
- **Attribution:** All `memory.md` entries in Team Mode MUST have `[@username]`.
- **Session Protocol:** 3-row start (Last Task, Next Task, Collaborator Status).
- **Automation:** The AI maintains these docs without user prompting.

## Visual Identity Concepts
- **Core Metaphor:** The "Context Switchboard" and "Universal Link."
- **Keywords:** Seamless, Orchestration, Persistent, AI-Native, Modern.
- **Iconography:** Geometric links, abstract switchboard circuits, or a "Pulse" wave integrated with a chain link.
- **Color Palette:** Deep Space Blue (Background/Primary), Electric Cyan (Primary Action/Link), Pulse Green (Telemetry/Success).
