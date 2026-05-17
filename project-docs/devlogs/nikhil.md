# Devlog - Nikhil Soman

## 2026-05-17
### Session: v0.2.1 Correctness Patch
- **Activity:** Received and evaluated external code review feedback on v0.2.0.
- **Review Findings:** Confirmed 5 bugs: exit code not propagated from `exec_command`, `parse_costs_md` reading wrong column (parts[6] vs parts[5]), `install.sh` version drift (1.2.0-lite vs 0.2.0), 3 dead functions never called, sparse `.gitignore`. Also stale roadmap.md.
- **TDD:** Wrote failing tests first for exit code propagation and costs schema mismatch before touching production code. Updated `conftest.py` fixture to match real `costs.md` 6-column schema.
- **Fixes shipped:** All 6 0.2.1 items — exit code propagation, costs parser column, dead code removal (`log_telemetry`, `extract_tokens`, `update_costs`), install.sh version, .gitignore expansion, roadmap refresh.
- **Milestone:** v0.2.1 merged to main via PR#3. 47 tests passing. `synlynk exec python3 -c 'sys.exit(7)'` now correctly exits 7 in shell.
- **Next:** v0.3.0 — subprocess CLI tests, checkpoint idempotency, `synlynk doctor`, shell completions.

## 2026-05-16
### Session: Product Definition Brainstorming
- **Activity:** Stepped back from implementation to define the long-term vision for synlynk.
- **Key Outcome:** Defined a two-tier strategy (Free/Solo and Paid/Team/Enterprise).
- **Solo Tier Vision:** A "Context Switchboard" for AI developers that manages context, projects, costs, models, and environments across various CLIs (Claude Code, Gemini, etc.) and IDEs (Cursor, VS Code).
- **Architectural Shift:** Moving from a simple template repository to a lightweight Local Context CLI/Daemon that uses MCP (Model Context Protocol) and wrapper scripts to maintain state across different AI engines.
- **Interoperability:** Focus on seamless context hand-offs between different AI tools (e.g., starting in Claude Code and finishing in Cursor).
- **Strategy Shift:** Adopted a "Lite vs Full" Free tier approach. Lite focuses on file-based context and shell wrappers; Full introduces the LCP Daemon and MCP Server.
- **Resolved Grilling Points:** 
    - Concurrency via Append-Only logs.
    - Telemetry via shell aliases.
    - Hallucination detection via process wrappers and context injection.
    - Shipping frequently with a built-in `upgrade` path.
- **Activity:** Created public README.md and scaffolded the initial `synlynk` CLI (v1.2.0-lite) in Python.
- **Milestone:** Established final brand identity as **synlynk**.
- **Activity:** Implemented `synlynk init` command in `bin/synlynk.py`.
- **Verification:** Verified `init` command successfully creates `project-docs/`, `.synlynk/`, and all template markdown files in a test environment.
- **Activity:** Implemented `synlynk exec` command in `bin/synlynk.py`.
- **Feature:** `exec` command now generates a unified `.synlynk/context.md` snapshot and captures execution telemetry (duration).
- **Verification:** Verified `exec` successfully aggregates project-docs and wraps terminal commands.
- **Activity:** Implemented `synlynk upgrade` simulation (auto-update path foundation).
- **Activity:** Added frictionless alias recommendations to `synlynk init` to encourage telemetry adoption.
- **Verification:** Verified `upgrade` and `init` (with tips) via manual execution.
- **Activity:** Implemented `install.sh` for global installation of the `synlynk` CLI to `~/.synlynk/bin`.
- **Feature:** Added a shebang to `bin/synlynk.py` to allow direct execution.
- **Verification:** Verified `install.sh` correctly installs the binary and provides PATH configuration instructions.
- **Activity:** Refined AI instructions in `GEMINI.md` and `CLAUDE.md` to prioritize the `.synlynk/context.md` snapshot.
- **Activity:** Implemented telemetry logging to `.synlynk/telemetry.json` (timestamp, command, duration, exit_code).
- **Activity:** Implemented the "Flatline" Sentinel (v0.1) to detect and flag 3 consecutive command failures.
- **Verification:** Verified telemetry and Sentinel detection via manual loop simulation in a test environment.
- **Activity:** Automated multi-environment PATH setup in `install.sh` for zsh, bash, and fish.
- **Feature:** `install.sh` now intelligently appends the `PATH` export to shell configuration files if not already present.
- **Milestone:** synlynk Lite installation is now a seamless "one-click" experience.
- **Activity:** Implemented token count extraction from CLI output in `synlynk exec`.
- **Feature:** `exec` now parses stdout for token patterns (Claude, Gemini, etc.) and automatically updates `project-docs/costs.md`.
- **Feature:** Added real-time cost estimation and session summary display after each command execution.
- **Feature:** Expanded `costs.md` to track Request Counts and aligned the template with professional observability standards.
- **Feature:** Implemented "Budget Pulse" in `exec_command` to show cumulative request totals alongside session costs.
- **Feature:** Added `.synlynk/config.json` for per-project budget configuration (USD and Request limits).
- **Feature:** Implemented runtime Budget Alerts (80% warning, 100% critical) for both cost and request counts.
- **Verification:** Verified request counting and pulse display via repeated command execution in a test environment.
- **Activity:** Standardized "Interoperability Protocol" by adding `AI_INSTRUCTIONS.md` and `.cursorrules` to the `init` templates.
- **Milestone:** synlynk Lite now supports "Quota-Hopping" across Claude, Gemini, Cursor, and Codex-based tools with shared context snapshots.
- **Verification:** Verified token parsing and cost logging via simulated CLI output.
- **Activity:** Discussed and defined architectural strategies for Context Compaction (Active vs. Archive) and Sub-Agent Context Routing (Task-scoped views).
- **Milestone:** Core "Lite Tier" infrastructure is verified and documented. Next phase focuses on token extraction and scaling strategies.
