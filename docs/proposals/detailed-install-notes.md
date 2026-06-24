# synlynk: Detailed Installation & Setup Guides
**Date:** June 4, 2026  
**Status:** User Guide / Documentation Proposal  

This guide provides step-by-step setup instructions for three common developer environments.

---

## Guide 1: Solo Dev + 1 AI Coding CLI (Single Assistant Setup)

**Best for:** Developers who want to keep a clean, local task checklist and architectural memory for a single preferred assistant (e.g., Claude Code, Gemini CLI, or Codex), ensuring context is never lost when closing or clearing terminal chat sessions.

### 1. Prerequisites
* **Python:** Python 3.8 or higher.
* **Git:** Installed and configured in the local workspace.
* **Your Coding CLI:** Ensure your target assistant is installed globally, for example:
  * Claude Code: `npm install -g @anthropic-ai/claude-code`

### 2. Download and Bootstrap
Navigate to your repository root and install synlynk:
```bash
# Download and install synlynk locally using the bootstrapper
curl -sSL https://raw.githubusercontent.com/nikhilsoman/synlynk/main/install.sh | bash
```

### 3. Initialize the Repository
Initialize synlynk and configure it to output instructions *only* for your active engine. Replace `claude` with `agy` or `codex` as appropriate:
```bash
synlynk init --agents claude --mode solo
```
This bootstraps:
* `project-docs/` containing `todo.md`, `roadmap.md`, `memory.md`, and `costs.md`.
* `CLAUDE.md` containing the custom instructions for the agent (or `GEMINI.md`/`AGENTS.md` respectively).
* `.synlynk/config.json` containing default local configurations.

### 4. Shell Profile Integration
To ensure telemetry is captured and context is compiled automatically, add a wrapper alias to your shell profile (`~/.zshrc` or `~/.bashrc`):
```bash
# Add alias to intercept tool invocations
alias claude="synlynk exec -- claude"
```
Reload your terminal: `source ~/.zshrc` (or equivalent).

### 5. Standard Session Loop
1. **Start Session:** Type `claude`. synlynk automatically updates `.synlynk/context.md` before launching. The agent will read this file and summarize its last completed task and next active step.
2. **Commit Work:** Code, test, and mark off tasks with `[x]` in `project-docs/todo.md`.
3. **Task Boundary Checkpoint:** Run `synlynk checkpoint` at task boundaries to archive completed items to your devlog and refresh active context.
4. **End Session:** Type `synlynk status` to review spend and active items, write your devlog, and close the session.

---

## Guide 2: Solo Dev + 1+ AI Coding CLIs (Multi-Agent Setup)

**Best for:** Developers switching between specialized local engines (e.g., Claude for backend development, Gemini/AGY for documentation, Codex for testing) who need to preserve a single, shared context state on the same machine.

### 1. Prerequisites
* **OS:** macOS or Linux (required for the Unix `os.fork()` watch daemon).
* **Python:** Python 3.8 or higher.
* **AI Tooling:** Install your set of target CLIs locally.

### 2. Download and Initialize
Navigate to your repository and initialize all three instruction files simultaneously:
```bash
# Install the CLI utility
curl -sSL https://raw.githubusercontent.com/nikhilsoman/synlynk/main/install.sh | bash

# Initialize with multi-agent templates
synlynk init --agents claude,agy,codex --mode solo
```
This generates `CLAUDE.md`, `GEMINI.md`, and `AGENTS.md` (for Codex) in your repository root, ensuring all three engines conform to the same workspace rules, branch prefixes, and file boundaries.

### 3. Shell Profile Integration
Register wrapper aliases for all three tools in your shell profile configuration (`~/.zshrc` or `~/.bashrc`):
```bash
alias claude="synlynk exec -- claude"
alias agy="synlynk exec -- agy"
alias codex="synlynk exec -- codex"
```
Reload your profile: `source ~/.zshrc`.

### 4. Fire up the Watcher Daemon
To keep context snapshots dynamically updated when switching between terminal windows or tools, start the polling watch daemon:
```bash
synlynk watch start
```
The daemon runs in the background. If you edit `todo.md` or `memory.md` in your editor or via one tool, the daemon automatically updates the shared context snapshot `.synlynk/context.md` within 30 seconds.

### 5. Multi-Agent Session Loop
1. Launch `claude` to write backend logic, then exit.
2. Launch `agy` to write user docs or compile project metrics. It immediately reads the updated `.synlynk/context.md` containing the devlog records Claude just appended.
3. Launch `codex` to read the updated code logic and write tests on a `feat/codex/*` branch.
4. Run `synlynk checkpoint` to sync all completed tasks across your devlogs.

---

## Guide 3: Solo Dev + 1+ AI CLIs + GitHub Projects v2 (Orchestrated Setup)

**Best for:** Developers who want a full, automated Kanban orchestration workflow. Running commands claims tasks on your board, assigns the active agent field, posts WIP comments to GitHub, and sets up review routing.

### 1. Prerequisites
* **OS:** macOS or Linux.
* **AI Tooling:** AI coding CLIs installed.
* **GitHub CLI:** The official `gh` CLI installed and authenticated.
* **API Permission:** Your GitHub API token must have the `project` scope enabled.

### 2. Verify GitHub CLI Scopes
Ensure you have the required token permissions:
```bash
# Check current authentication status
gh auth status

# Force refresh the token and request the project API scope
gh auth refresh -s project
```

### 3. Create or Fetch your Project Board
Create your project board at user level (`@me`) or organization level:
```bash
# Create a new project board and copy the returned project number (e.g., 3)
gh project create --owner "@me" --title "AI Workgroup Kanban"

# Link this project board to your current repository
gh project link 3 --owner "@me" --repo "my-repo-name"

# Retrieve the GraphQL Node ID of the board (needed for synlynk integration)
gh project view 3 --owner "@me" --format json | jq -r .id
# Example output: PVT_kwDOA18z8s4AF3xy
```

### 4. Create the Status Options (GraphQL Mapping)
Create the Status single-select column on your board to handle agent states:
```bash
gh project field-create 3 --owner "@me" \
  --name "Status" \
  --data-type "SINGLE_SELECT" \
  --single-select-options "Todo,In Progress,In Review,Approved,Done"
```

### 5. Initialize synlynk with Board Identifiers
Configure synlynk in your repository using the GraphQL project ID, organization metadata, and the full agent set:
```bash
synlynk init \
  --agents claude,agy,codex \
  --mode solo \
  --org "my-github-username" \
  --repo "my-repo-name" \
  --project-id "PVT_kwDOA18z8s4AF3xy"
```
This saves the project parameters to `.synlynk/config.json` and inserts the specific GraphQL queries directly into `CLAUDE.md`, `GEMINI.md`, and `AGENTS.md`.

### 6. Orchestrated Workcycle
1. Configure aliases (`claude`, `agy`, `codex`) and start the watcher: `synlynk watch start`.
2. Locate your assigned issue number on the board (e.g., Issue `#12`).
3. Run the session start wrapper:
   ```bash
   synlynk start 12
   ```
   Under the hood, synlynk:
   * Moves the card to **In Progress** on your board.
   * Assigns the `Agent` field (e.g., `Claude`) via GraphQL.
   * Posts a WIP comment to the GitHub issue.
   * Launches your terminal agent session.
4. When finished, your agent commits, pushes, and opens a PR. The project board updates to **In Review** and assigns the designated peer agent as reviewer.
5. Merge the approved pull request on GitHub to complete the loop.
