# Synlynk Cockpit: Active Herdr 4-Pane Terminal Orchestration Specification

**Document:** `docs/superpowers/specs/2026-09-14-synlynk-cockpit-herdr-orchestration.md`  
**Story ID:** `story-0127066f` (`Synlynk Cockpit: Active Herdr 4-pane terminal orchestration (synlynk herdr init)`)  
**Governing Goal:** `goal-c7113f58` ("Over-the-Horizon Strategic Expansion: DeepSeek Harness Plugin Architecture, ACP Headless Transport & Herdr Multi-Pane Cockpit")  
**Target Release:** Post-v1.0 (Standalone Advanced Developer Experience Epic)  
**Author / Conductor:** Agy (`@agy`, AntiGravity)  
**Collaborators:** Claude (`@claude`), Codex (`@codex`), Grok (`@grok`), Nikhil Soman (`@nikhilsoman`)  
**Status:** SPECIFICATION APPROVED (Decoupled from FTUE Onboarding Track)  

---

## 1. Executive Summary & Problem Statement

### The Problem
When running multi-agent software engineering in terminal environments, developers face two unpalatable extremes:
1. **Blind Headless Dispatches:** Dispatched agents (`synlynk dispatch <harness>`) run detached in the background. The developer must poll `synlynk jobs` or manually `synlynk logs <job-id>`, losing real-time visibility into the agent's chain-of-thought, tool invocations, and test execution.
2. **Terminal Interleaving Chaos:** If multiple agents or daemons share a single terminal window, log streams, user prompts, git outputs, and sentinel alerts clobber one another, making verification impossible.

### The Synlynk Cockpit Solution
The **Synlynk Cockpit** transforms [Herdr](https://github.com/herdrdev/herdr) (Apache-2.0) from a passive markdown SOP into an **active terminal workspace orchestrator**. Running a single command:
```bash
synlynk herdr init
```
automatically launches or attaches to an optimized **4-Pane Terminal Cockpit**, dedicating specialized real estate to the Home Conductor, Workspace HUD, Worker Log Streamer, and Operator Shell.

```
┌───────────────────────────────────────────────────┬───────────────────────────────────┐
│ PANE 1: HOME CONDUCTOR (Interactive Session)      │ PANE 2: LIVE HUD & SENTINEL       │
│ • Active Harness: Agy (1M-2M context) or Claude   │ • Command: synlynk watch          │
│ • Roles: PM + TPM + Architect                     │ • Real-time job burn rate & queue │
│ • Primary driver of Unattended Milestone Loop     │ • Sentinel alerts & active locks  │
│                                                   │                                   │
├───────────────────────────────────────────────────┼───────────────────────────────────┤
│ PANE 3: AWAY WORKER STREAMER (Real-Time Logs)     │ PANE 4: OPERATOR SHELL            │
│ • Command: synlynk logs -f <active-job-id>        │ • Clean zsh/bash operator prompt  │
│ • Live tool-calls, AST diffs, and pytest output   │ • Pre-primed synlynk gh-shim      │
│ • Switches dynamically as new jobs dispatch       │ • Manual git audits & interventions│
└───────────────────────────────────────────────────┴───────────────────────────────────┘
```

---

## 2. Structural & Architectural Independence

### Strict Decoupling from FTUE Onboarding
- **FTUE Onboarding (`v0.21.0`):** Focuses on universal surface discovery (Cursor, Windsurf, VS Code, Warp, Antigravity, Replit, Emergent), non-destructive rule generation, 3D discovery, and achieving the First Real Win PR in $< 5$ minutes without requiring terminal proficiency.
- **Synlynk Cockpit (`story-0127066f` / `goal-c7113f58`):** Focuses on advanced, heavy-duty terminal multi-agent concurrency. It is completely decoupled from the FTUE flow and tracked under its own milestone.

---

## 3. Detailed Component Architecture

### A. The Cockpit Initializer: `synlynk herdr init`
1. **Environment Preflights:**
   - Detects if `herdr` CLI binary is installed via `shutil.which("herdr")`. If absent, outputs clear remediation:
     ```text
     Herdr is required for the Synlynk Multi-Pane Cockpit.
     Install Herdr via: npm install -g @herdrdev/cli (or brew install herdr)
     Reference: https://github.com/herdrdev/herdr
     ```
   - Checks if shell is already inside Herdr via `test "${HERDR_ENV:-}" = 1`.
2. **Workspace & Tab Provisioning:**
   - Automatically names or creates a Herdr workspace matched to the synlynk workspace: `synlynk/<project-name>`.
   - Creates a dedicated tab: `[Cockpit] <project-slug>`.
3. **4-Pane Layout Composition:**
   - Splits the terminal grid into a 2x2 asymmetric viewport:
     - **Top-Left (60% width, 60% height):** Starts the interactive Home Conductor session (`agy` or `claude`) with `.synlynk/context.md` injected.
     - **Top-Right (40% width, 60% height):** Starts `synlynk watch` for real-time workspace HUD telemetry.
     - **Bottom-Left (60% width, 40% height):** Starts `synlynk logs -f --active` tailing the most recent active dispatched job.
     - **Bottom-Right (40% width, 40% height):** Drops into an interactive developer shell with `~/.synlynk/gh-shim` primed in `PATH`.

### B. Live Worker Viewport: `synlynk dispatch --pane`
When dispatching headless away workers, developers can pass `--pane` or `--interactive`:
```bash
synlynk dispatch codex --task "implement issue #1580" --pane
```
- Instead of detaching silently into a background PID, Synlynk calls Herdr to split or create an ephemeral pane in the Herdr Cockpit.
- Labels the pane with `<session_id> / <job_id> / <harness_name>`.
- The human operator can watch the dispatched agent execute shell commands, run tests, and format diffs live without touching the Home Conductor pane.
- Automatically closes or keeps open on completion based on `--leave-pane-open` flag.

### C. Herdr Workspace Protocol Safeguards
All Cockpit commands strictly enforce the established Herdr Workspace Protocol:
1. **Precondition Guard:** `test "${HERDR_ENV:-}" = 1` checked before issuing any Herdr socket calls.
2. **Pane Isolation:** Never reuses another active session's pane; always provisions a fresh pane or tab with proper labels.
3. **Clean Teardown:** `synlynk herdr stop` safely closes the HUD and log streamers while leaving the operator shell intact.

---

## 4. Verification & Testing Strategy

1. **Unit Testing (`tests/test_herdr_cockpit.py`):**
   - Mock `shutil.which` and `subprocess.run` to verify CLI command generation for Herdr layout creation.
   - Assert correct pane dimensions, commands, and environment variables are emitted.
   - Test graceful error handling when `herdr` is not installed or `HERDR_ENV` is unset.
2. **Integration Testing:**
   - Verify `synlynk dispatch --pane` invokes Herdr pane creation when running inside Herdr.
   - Assert failure-closing behavior if Herdr execution encounters errors.

---

## 5. Roadmap & Story Tracking

- **Story ID:** `story-0127066f`
- **Goal:** `goal-c7113f58` (Over-the-Horizon Strategic Expansion)
- **Phase:** `Cockpit`
- **Stage:** `open`
- **Next Steps:** Once FTUE Onboarding v0.21.0 merges, prepare the implementation plan for `story-0127066f` to implement `synlynk/cockpit.py` and register the `synlynk herdr` CLI subcommands.
