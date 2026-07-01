---
title: "PR #TBD — v0.10.0: synlynk scan + wizard FTUE"
date: 2026-07-01
series: "Building the OS for Multi-Agent Development"
post: 35
pr: "#TBD"
merged: status: open
---

# PR #TBD — v0.10.0: synlynk scan + wizard FTUE

## The Broader Goal at the End of the Previous PR

At the close of the T6 / v0.9.2 release (the Agent Ecosystem scaffolding stories), the broader goal was to make synlynk the first tool a developer runs when landing in any repository. It should seamlessly understand the workspace topology, recommend specific agents, and offer a guided, friction-free first-time experience. However, a significant gap remained: `synlynk init` acted as a blunt, destructive overwrite of project configuration files, and a dedicated workspace-level command like `synlynk scan` did not yet exist.

## Strategic Shifts in This PR

BS-17 closes this First-Time User Experience (FTUE) gap entirely in a single, unified pull request. The development strategy featured a key architectural shift: two parallel streams of implementation—**Codex** building the workspace scanner, and **Grok** designing the terminal user interface (TUI) wizard. 

Both agents worked independently against a strict, pre-defined interface contract (the 8-key `ScanResult` dictionary) that decoupled the data extraction boundary from the presentation layer. Once both systems matured, they were integrated in Wave 5. This represented the first operational test of the multi-agent parallel dispatch pattern, demonstrating that independent AI agents can develop components concurrently and successfully integrate them.

## What This PR Shipped

### Standalone Workspace Scanner (`synlynk scan`)

This PR introduces the new `synlynk scan` command, which provides a re-runnable workspace analysis. It runs silently in about 2 seconds, fingerprints the development environment, and populates the workspace database.

Key technical capabilities shipped:
* **Topology Detection:** Walks directories to find Git roots, identifying single-repo, monorepo (packages, apps, services), or multi-repo structures.
* **Stack Fingerprinting:** Heuristic-based detection across 14 file signals to infer stack labels (e.g., `pyproject.toml` → Python, `tsconfig.json` → TypeScript, `next.config.*` → Next.js, `Dockerfile` → Docker, `Cargo.toml` → Rust, etc.).
* **Harness & Agent Discovery:** Detects available home harnesses (e.g., Claude, Gemini, Codex, Grok, Aider) via `PATH` lookups and process parent checks.
* **Skills Scan:** Discovers active synlynk skills and plugins by searching standard locations such as `~/.claude/plugins/cache/` or `~/.config/gstack/`.
* **Structured Context Generation:** Parses existing contextual files (`README.md`, `CLAUDE.md`, `GEMINI.md`, `AGENTS.md`) and updates [context.md](file:///Users/nikhilsoman/dev/synlynk/.synlynk/context.md) with a clean, structured output format.
* **Output Configuration:** Writes configuration state to `.synlynk/workspaces/<name>/config.json`.
* **CLI Subcommand Flags:**
  * `--refresh` to force re-run detection on the existing workspace.
  * `--add <path>` to append a new repository path to the workspace.
  * `--remove <path>` to remove a repository path from the workspace config.
  * `--dry-run` to output scan results without writing config files or `context.md`.
  * `--workspace <name>` to specify the target workspace configuration.

### Interactive Onboarding TUI (`synlynk init --wizard`)

For new projects, `synlynk init` defaults to a guided onboarding experience using a typeform-style Terminal User Interface (TUI). This interface is built purely with Python's standard library (`termios`/`tty`), requiring zero third-party dependencies.

The onboarding process flows through 8 screens:
1. **Landing:** Wordmark animation and brand introduction explaining the concept of synaptic links.
2. **Harness check:** Scan and verify installed harnesses (`claude`, `gemini`, etc.).
3. **Topology picker:** Interactive selection between Single Repo, Monorepo, or Multi-Repo layouts.
4. **Workspace name + picker (Multi-Repo sub-flow):** Screen 2ab/2c for naming workspaces, selecting nearby repositories, adding custom paths, and confirming paths.
5. **Skills review:** Explains how synlynk runs alongside external skill packs (e.g., Superpowers, GStack).
6. **Agents:** Visual list of discovered agent CLIs and their capabilities.
7. **Roles:** Screen to assign agents to roles (PM, Code Review, Implementation, etc.) and write directive role blocks.
8. **Launch:** A cheat sheet printing the 6 essential commands to start dispatching jobs.

> [!IMPORTANT]
> To guarantee a safe onboarding experience, the wizard adheres to a strict **commit-on-complete** pattern. No state or configuration writes occur before Screen 6 (Confirm). Pressing Ctrl-C at any step exits cleanly and leaves the project in a zero-state condition.

### The ScanResult Interface Contract

To lock down the integration boundary between scanner (Codex) and wizard (Grok), we established an 8-key `ScanResult` contract:
1. `workspace_name` (str): Unique workspace identifier.
2. `topology` (str): Inferred layout (`single`, `monorepo`, or `multi`).
3. `repos` (list): Discovered repositories containing paths, stack labels, and README excerpts.
4. `harnesses` (list): Installed harnesses found in `PATH`.
5. `agents` (list): Available agent CLIs.
6. `skills` (list): Discovered skill plugins and versions.
7. `home_harness` (str): Pre-selected default harness.
8. `scanned_at` (str): ISO 8601 timestamp of the scanning run.

### Comprehensive Test Coverage

To verify correctness across both flows, we added **37 new tests**, bringing the project test suite from 551 to 588 tests.
* **9 A-series scan tests** covering path resolution, stack label heuristics, config updates, and dry-run guarantees. (See [test_workspace_scan.py](file:///Users/nikhilsoman/dev/synlynk/tests/test_workspace_scan.py))
* **6 B-series wizard unit tests** validating terminal rendering, single-keystroke inputs, and transition states. (See [test_wizard.py](file:///Users/nikhilsoman/dev/synlynk/tests/test_wizard.py))
* **9 B-series wizard integration tests** verifying full flows and Ctrl-C zero-state behavior under agent dispatch (Agy C-1/C-2).
* **1 A-6 CLI smoke test** running the scanner interface E2E.
* **1 B-6 subprocess smoke test** simulating interactive inputs to the wizard.
* **11 general integration tests** for multi-repo workspace linking, addition, and subtraction logic.

## Brainstorm Visuals Used

Decisions regarding screen transitions, progress indicators, and the multi-repo sub-flow were guided by visual design mocks located in the [bs17-ftue-onboarding](file:///Users/nikhilsoman/dev/synlynk/docs/brainstorm/bs17-ftue-onboarding/) brainstorm directory:
* [wizard-landing.html](file:///Users/nikhilsoman/dev/synlynk/docs/brainstorm/bs17-ftue-onboarding/wizard-landing.html) — Branding, S-glyph ASCII layout, and product introduction mockup.
* [intro.html](file:///Users/nikhilsoman/dev/synlynk/docs/brainstorm/bs17-ftue-onboarding/intro.html) — Layout styling and typography configurations.
* [wizard-steps.html](file:///Users/nikhilsoman/dev/synlynk/docs/brainstorm/bs17-ftue-onboarding/wizard-steps.html) — Flow progression dot trail designs.
* [multirepo-flow.html](file:///Users/nikhilsoman/dev/synlynk/docs/brainstorm/bs17-ftue-onboarding/multirepo-flow.html) — Sequence logic for the 2ab/2c multi-repo workspace configuration.
* [multirepo-2ab.html](file:///Users/nikhilsoman/dev/synlynk/docs/brainstorm/bs17-ftue-onboarding/multirepo-2ab.html) — Visual layout for name input fields and checkboxed repository picker panels.
* [wizard-v3.html](file:///Users/nikhilsoman/dev/synlynk/docs/brainstorm/bs17-ftue-onboarding/wizard-v3.html) — Dynamic rendering specs for skills, agent cards, and role definition tables.

## What This Achieved on the Path to Autonomy

By shipping BS-17, synlynk transitions from a developer tool to a cohesive environment harness:
1. **Under 2 Minutes from Zero to Setup:** Developers can now onboard a project immediately, without writing complex config files.
2. **Structured Machine Visibility:** The `scan` command provides a structured, predictable view of project architecture, directories, and stack heuristics. When an agent is dispatched, it reads a clean [context.md](file:///Users/nikhilsoman/dev/synlynk/.synlynk/context.md) map instead of a raw directory printout.
3. **No Blunt Overwrites:** Replacing the old `init` overwrites with the safe, re-runnable scanner means users never lose project context when updating settings.

## Strategic Note: The Goal at the End of This PR

With onboarding and topology scans fully resolved, the next major milestone is **BS-13: Live Job Observatory**. 

As we scale up the multi-agent dispatch loop, we need immediate, real-time visibility into what the agents are executing. The next step is instrumenting the job runner to stream Server-Sent Events (SSE) from the background daemon. This will enable front-end surfaces (including terminals and web pages) to watch Codex, Grok, and Agy collaborate live in a single terminal pane, making agent orchestration fully observable.
