# synlynk: Public Repository Launch & GTM Plan
**Date:** June 4, 2026  
**Status:** Strategy Proposal / Launch Manual  

---

## 1. Preparing the Repository for Public Release

To transition synlynk from a private development environment to a public open-source project, the repository must be prepared for contributors, maintainers, and community security.

### A. Repository Structure & Configuration
1. **GitHub Organization Layout:**
   * **`README.md`:** Must clearly explain the core thesis (the "Context Switchboard"), list installation steps (`install.sh`), and define CLI commands.
   * **`CONTRIBUTING.md`:** Define code standards, local setup steps (venv, pytest), and the PR submission guidelines.
   * **`CODEOWNERS`:** Place at `.github/CODEOWNERS` to automatically route reviews to maintainers for specific areas (e.g., `/bin/` changes to backend maintainers, `.github/` to DevOps).
2. **Issue & PR Templates:**
   * Create `.github/issue_template/bug_report.md` and `feature_request.md` to prevent unstructured spam issues.
   * Configure `.github/PULL_REQUEST_TEMPLATE.md` to force contributors to verify tests pass and declare any user-segment impacts.
3. **Repository Clean-up (Crucial Pre-flight Checklist):**
   * Review all files currently in version control. Remove local caching (`__pycache__`, `.pytest_cache`, `.venv`).
   * Verify a robust `.gitignore` is active at the project root:
     ```gitignore
     # Python
     __pycache__/
     *.py[cod]
     .pytest_cache/
     .venv/
     
     # synlynk local states
     .synlynk/state
     .synlynk/watch.pid
     .synlynk/watch.log
     .synlynk/telemetry.json
     .synlynk/sentinel.md
     
     # Local Developer Docs
     project-docs/devlogs/*
     !project-docs/devlogs/README.md
     project-docs/costs.md
     ```

---

## 2. Separate Release Tiers (Single-Codebase Configuration Model)

To keep the project maintainable, **do not maintain separate branches or forks for each tier.** Instead, maintain a single codebase (`bin/synlynk.py`) that adapts to the user's intent purely through CLI parameters and configuration flags.

```
                      ┌────────────────────────────────────────┐
                      │              synlynk CLI               │
                      └───────────────────┬────────────────────┘
                                          │
                  ┌───────────────────────┼───────────────────────┐
                  │                       │                       │
         [--agents claude]     [--agents claude,agy,codex]    [--project-id PJ_XXX]
                  │                       │                       │
                  ▼                       ▼                       ▼
            Tier 1: Solo           Tier 2: Solo+           Tier 3: Solo++
           (Single Agent)          (Multi-Agent)           (Orchestrated)
```

### Tier A: Solo (Core Release)
* **Goal:** A simple context bridge for developers using a single, primary AI coding CLI.
* **Capabilities:** 
  * Compiles `.synlynk/context.md` from `project-docs/`.
  * Generates an engine-specific instruction template (`CLAUDE.md`, `GEMINI.md`, or `AGENTS.md`) tailored to their active tool.
  * Tracks manual costs in `costs.md`.
* **Execution:**
  ```bash
  synlynk init --agents claude
  ```

### Tier B: Solo+ (Unified Multi-Agent Release)
* **Goal:** Coordinate multiple distinct AI engines working under a single user's local account.
* **Capabilities:**
  * Bootstraps instruction sets for Claude Code (`CLAUDE.md`), AGY/Gemini CLI (`GEMINI.md`), and Codex (`AGENTS.md`) simultaneously.
  * Enforces the circular peer-review structure (Claude $\rightarrow$ AntiGravity $\rightarrow$ Codex $\rightarrow$ Claude) locally.
  * Launches the background watcher daemon (`synlynk watch start`) to automatically rebuild context slices when local files shift.
* **Execution:**
  ```bash
  synlynk init --agents claude,agy,codex
  ```

### Tier C: Solo++ (Orchestrated GitHub Projects Release)
* **Goal:** Fully orchestrate multi-agent tasks using GitHub Projects v2 as a Kanban state machine.
* **Capabilities:**
  * Integrates GraphQL mutations directly into CLI triggers.
  * Running `synlynk start <issue-id>` claims tasks on the board, sets statuses, assigns the agent field, and posts WIP signals.
  * Circular peer assignment is updated automatically on the GitHub board when local sessions close.
* **Execution:**
  ```bash
  synlynk init --agents claude,agy,codex --project-id <BOARD_NODE_ID>
  ```

---

## 3. Security and Anti-Spam Best Practices

Releasing open-source AI tooling introduces unique security considerations, particularly around automated pull requests and prompt injection attacks.

1. **GHA Workflow Permission Hardening:**
   * Always explicitly declare permissions in GitHub Action workflows (`.github/workflows/ci.yml`). Never use default wide permissions:
     ```yaml
     permissions:
       contents: read
       pull-requests: read
     ```
   * **Crucial:** Never run untrusted code from PR forks on triggers like `pull_request_target`. Malicious contributors can modify tests or scripts to steal your repository's secrets (like your OpenAI or Anthropic API keys).
2. **Secret Scanning & Guardrails:**
   * Enable GitHub Secret Scanning (free for public repos) to catch accidental check-ins of API keys.
   * Add a validation script to pre-commit checks to verify no `PROJECT_ID` or custom API credentials exist in code files before push.
3. **Branch Protection:**
   * Require at least one approving review on `main` before merge.
   * Enforce status checks (e.g., all 63 unit tests in `pytest` must pass) before branch merges.
4. **Contributor Moderation & Anti-Spam:**
   * Use GitHub's **Interaction Limits** to restrict comments and PRs to users who have been on GitHub for at least 24 hours, mitigating bot spammers.
   * Explicitly tag PRs with labels (`invalid`, `spam`) to count toward spam limits and trigger automatic account flags.

---

## 4. GTM & Public Launch Announcements

### A. Hacker News Launch Guide (Show HN)
* **Target Timing:** Tuesday or Wednesday morning (between 9:00 AM and 11:30 AM EST) to capture peak traffic.
* **Post Title:** `Show HN: Synlynk – Keep your AI coding agents in sync across CLI sessions`

#### Introduction Post (Write-up)
> **Show HN: synlynk**
> 
> I built synlynk because I was tired of "context amnesia" when working with stateless AI coding tools. 
> 
> Today, I use Claude Code for terminal implementation, Gemini CLI for heavy refactoring and documentation, and Codex for test generation. But switching between them meant copying and pasting state, rebuilding task lists, or losing important architectural decisions I had already aligned on.
> 
> To solve this, I built synlynk: a zero-dependency, local-first context switchboard written purely in Python stdlib. It acts as a local state-bridge. At the start of any CLI session, it parses a human-editable `project-docs/` folder (roadmap, active tasks, memory) and writes a compacted snapshot to `.synlynk/context.md` that all agents are instructed to read. It tracks costs manually in a standardized table, and includes a "Flatline Sentinel" to prevent agents from getting stuck in infinite command loops that run up your bill.
> 
> We've been using it to build synlynk itself—coordinating task checkoffs and circular code reviews across Claude, AntiGravity, and Codex. 
> 
> I'd love to hear your feedback on how you manage state across different AI coding CLIs!
> 
> GitHub: https://github.com/nikhilsoman/synlynk

---

### B. Product Hunt Launch Guide
* **Tagline:** `The context switchboard for Claude Code, Gemini CLI & Codex`
* **Topic Tags:** `Developer Tools`, `Artificial Intelligence`, `Open Source`

#### Maker's Introduction & Description
> Hi hunters! 🚀
> 
> AI coding assistants are extremely powerful, but they are fundamentally stateless. If you use multiple tools to stay within API rate limits or leverage different model strengths, you run into the "context gap."
> 
> synlynk is an open-source context switchboard that coordinates your local workspace so Claude, Gemini, and Codex can work together on the same projects without collision.
> 
> Here is how you can use synlynk:
> 
> **1. Solo User (Single Agent)**
> * **Benefit:** Keep a clean context bridge and checklist for your primary assistant. Never lose progress when clearing a chat session.
> * **Prerequisites:** Python 3.8+ and your favorite coding CLI (e.g., Claude Code).
> * **To start:** `synlynk init --agents claude`
> 
> **2. Solo+ User (Unified Multi-Agent Workspace)**
> * **Benefit:** Run multiple specialized agents (e.g., Claude for backend, Gemini/AGY for documentation, Codex for testing) under a single workspace. Includes a local watcher daemon to compile context slices automatically as you save code files.
> * **Prerequisites:** At least two AI coding CLIs installed locally.
> * **To start:** `synlynk init --agents claude,agy,codex && synlynk watch start`
> 
> **3. Solo++ User (Orchestrated Board Board)**
> * **Benefit:** Complete kanban orchestration. synlynk links your terminal CLI sessions to your GitHub Projects v2 board, automatically moving cards to "In Progress," assigning agents, and posting WIP signals to origin.
> * **Prerequisites:** GitHub CLI (`gh`) configured with `project` scope, and a GitHub Projects v2 board.
> * **To start:** `synlynk init --agents claude,agy,codex --project-id <BOARD_ID>`
> 
> Let us know what agent workflows you'd like to see supported next!
