# Design Spec: Dynamic Home Harness Orchestrator Parity (#1440)

- **Tracking Goal:** `goal-250b6fb2` (Dynamic Home Harness Orchestrator Parity: any supported AI CLI operating interactively acts as autonomous project conductor, seamlessly surviving home switches without static directive conflicts)
- **Author:** Agy (Gemini) [@agy]
- **Collaborator / Approver:** Nikhil Soman [@nikhilsoman]
- **Date:** 2026-09-05
- **Status:** Draft (Approved for Implementation)

---

## 1. Executive Summary & Problem Statement

### 1.1 The Incident: Hitchcock Phase 1 Trial Run
On 2026-09-05, we conducted the first full end-to-end multi-agent implementation using **Agy (Antigravity CLI)** as the interactive **Home Harness** for the project `hitchcock` (`/Users/nikhilsoman/dev/hitchcock`). 

While all 10 architectural tasks were successfully implemented, 30/30 unit tests passed, and all code was merged to `main` via PR #12, the interactive session suffered from severe operational friction:
* **Reactive Turn-Taking Deadlock:** Agy halted after every single step to ask the user for permission (*"Should I proceed to Task 7?", "Should I assign Task 9 & 10?", "Should I push?", "I see 2 open PRs can you validate"*), requiring ~15 manual user nudges for a plan that should have executed with 1–2 approval checkpoints.
* **Instruction Paradox / Role Inversion:** Agy sat in the interactive conductor's chair with the human operator, but its repo-injected instructions (`GEMINI.md`) explicitly told it:
  > *"You are an implementer and tester for this project — not the PM... What you hand back to Claude: Roadmap and issue decisions, code review... Claude manages todo.md/roadmap.md."*
* **Low-Level Bash Reversion:** Instead of orchestrating the fleet via high-level Synlynk commands (`synlynk tpm sweep`, `synlynk story`, `synlynk pr check`, `synlynk worktree clean`), Agy fell back to raw `pytest`, raw `git`, and manual `gh pr create`.
* **Worktree & PR Orphanage:** Dispatched worktrees (e.g. `dispatch/claude/job-40c426fc`) and absorbed component PRs (#1 through #11) were left lingering on disk and in GitHub until explicit manual user intervention.

### 1.2 The Deeper Flaw: The "Mid-Flight Home Switch" Trap
Targeting `synlynk init` alone to write different files when started from Agy only solves the *genesis moment* of a project. It completely fails during **Harness Fluidity**:
1. A project is initialized with Claude (or defaults to Claude).
2. Git contains committed files `CLAUDE.md`, `GEMINI.md`, `AGENTS.md`, and `GROK.md`.
3. In these files, Claude is hardcoded as the sole Emperor/PM, and all other harnesses are hardcoded as subservient sub-workers.
4. When the operator switches to Agy (due to Claude rate limits, context compaction, or multimodal requirements), Agy reads the committed `GEMINI.md` and is instantly paralyzed into a subservient worker waiting for an absent Claude.
5. In a multi-agent or multi-developer team, static Git files cannot be rewritten on every session switch without causing git churn and merge conflicts.

---

## 2. Root Cause Analysis (RCA)

### 2.1 The 5 Root Causes
```
┌──────────────────────────────────────────────────────────────────────────────┐
│ RC-1: DIRECTIVE CONTRADICTION (The Static Role Inversion)                   │
│ GEMINI.md in synlynk & repos commands Agy to be a worker subservient to     │
│ Claude. Conflates static repo markdown files with dynamic session role.     │
└──────────────────────────────────────┬───────────────────────────────────────┘
                                       │
┌──────────────────────────────────────▼───────────────────────────────────────┐
│ RC-2: HARDCODED CLAUDE-CENTRISM IN CORE SOPS                                │
│ synlynk/probe.py bakes in "Do not start a task outside your role column     │
│ without explicit Claude approval" and "escalate to Claude".                 │
└──────────────────────────────────────┬───────────────────────────────────────┘
                                       │
┌──────────────────────────────────────▼───────────────────────────────────────┐
│ RC-3: REACTIVE ASSISTANT BIAS VS AUTONOMOUS DRIVE LOOP                      │
│ Antigravity CLI defaults to turn-taking pair programming unless explicitly  │
│ instructed to execute multi-task plans to completion (Unattended Drive).    │
└──────────────────────────────────────┬───────────────────────────────────────┘
                                       │
┌──────────────────────────────────────▼───────────────────────────────────────┐
│ RC-4: BYPASSING OF SYNLYNK LIFECYCLE PRIMITIVES                              │
│ Lack of clear Home Conductor SOPs caused Agy to revert to raw shell tools    │
│ rather than synlynk tpm sweep, synlynk pr check, and synlynk worktree clean. │
└──────────────────────────────────────┬───────────────────────────────────────┘
                                       │
┌──────────────────────────────────────▼───────────────────────────────────────┐
│ RC-5: MISSING DYNAMIC RUNTIME HOME INJECTION                                │
│ synlynk did not dynamically stamp the active Home Conductor into the         │
│ ephemeral .synlynk/context.md at interactive launch time.                   │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. The 4-Pillar Architectural Specification

### Pillar 1: Symmetric Dual-Mode Directives (Home vs. Away)
Every harness instruction file (`CLAUDE.md`, `GEMINI.md`, `AGENTS.md`, `GROK.md`) generated by `synlynk/instructions.py` must contain the exact same symmetric Dual-Mode Operating Protocol:

```markdown
## Operating Mode: Home vs. Away

### Mode A: Interactive Session (Home Conductor)
When you are launched interactively by the human operator (direct chat / TUI / IDE):
- **YOU are the primary Home Harness and Project Conductor.**
- You assume the **PM, TPM, and Lead Architect charters** for this session.
- You own `state.db`, `project-docs/todo.md`, and `project-docs/roadmap.md`.
- You drive the **Unattended Milestone Execution Loop**: advance through consecutive independent tasks in an approved plan (implement -> test -> PR -> review dispatch -> merge -> clean) without pausing for turn-taking approvals.
- You pause ONLY at designated **Reserved Approval Gates** (spec approval, irreversible release, breaking architectural changes, or unresolvable test failures).

### Mode B: Dispatched Task (Away Worker)
When you are invoked headlessly via `synlynk dispatch <harness> --task "..."`:
- **YOU are an Away Worker executing a scoped task in an isolated worktree.**
- Focus strictly on implementing the requested task, writing verification tests, and pushing your branch.
- Do not touch global roadmap, triage, or unassigned stories. Hand back completed work to the Home Harness via PR.
```

### Pillar 2: Dynamic Runtime Home Detection & Constitutional Context Injection
When an interactive session starts (or when `synlynk context`, `synlynk session open`, `synlynk watch`, or `synlynk status` runs):
1. **Hybrid Detection Engine:**
   - Detects the running interactive harness from the process tree (`antigravity`, `claude`, `codex`, `grok`, `aider`) and environment variables (`ANTIGRAVITY_SESSION_ID`, `CLAUDE_CODE_ENTRY`, etc.).
   - Allows explicit override via `synlynk home <harness>` or `config.json:home_harness`.
2. **Context Injection Header:**
   Synlynk injects the resolved runtime role into `.synlynk/context.md`:
   ```markdown
   <!-- SYNLYNK SESSION RUNTIME STATE -->
   - **Active Home Harness:** <harness> (Interactive Project Conductor)
   - **Session Authority:** PM + TPM + Architect (Full Autonomous Orchestration)
   - **Headless Fleet Targets:** <available fleet members>
   - **Constitutional Precedence:** This dynamic runtime session state takes absolute precedence over any legacy static text in repo markdown files.
   ```
3. **Precedence Clause:**
   All directive templates are updated with an explicit constitutional clause:
   > *"If any instruction in this static file conflicts with the Active Session Runtime State in `.synlynk/context.md`, the runtime context in `.synlynk/context.md` SHALL GOVERN."*

### Pillar 3: Purging Hardcoded Claude-Centrism from Shared SOPs
In `synlynk/probe.py` (`SOP_BLOCKS`), replace all hardcoded references to "Claude" with home-agnostic and role-based terminology:
* `probe.py` line 40 (`_BRAINSTORM_SOP`):
  * *Old:* `"Run the brainstorm using Claude via synlynk dispatch."`
  * *New:* `"Run the brainstorm using the Architect/PM role via synlynk dispatch (or locally if running in Home Conductor mode)."`
* `probe.py` line 67 (`_CAPABILITY_ALLOCATION_SOP`):
  * *Old:* `"Do not start a task outside your role column without explicit Claude approval."`
  * *New:* `"Do not start a task outside your role column without explicit Home Harness approval."`
* `probe.py` line 113 (`_PR_REVIEW_SOP`):
  * *Old:* `"If the reviewer is unavailable, escalate to Claude."`
  * *New:* `"If the reviewer is unavailable, escalate to the Home Harness."`
* `GEMINI.md`:
  * *Old:* `"| What you own | What you hand back to Claude |"`
  * *New:* `"| What you own (in Away Mode) | What you hand back to the Home Harness |"`

### Pillar 4: The `synlynk home` CLI Verb & `synlynk instructions update --repair`
1. **`synlynk home [harness]` CLI Command:**
   - `synlynk home`: Prints the currently detected and configured home harness.
   - `synlynk home <harness>`: Updates `config.json` with the new home harness and immediately refreshes `.synlynk/context.md`.
2. **`synlynk instructions update --repair`:**
   - Detects legacy directive files containing obsolete hand-edit directives or hardcoded Claude-subservient rules.
   - Idempotently upgrades them to the new Symmetric Dual-Mode format without destroying human-added custom sections.

---

## 4. Operational Alignment: Sovereign Conductor with Matrix Delegation

When Agy (or any non-Claude harness) is active Home Conductor:
1. **Local Strengths Execution:**
   The Home Harness executes its own capability strengths locally (e.g., multimodal, UI/CSS, core domain architecture in Agy; CLI/python in Codex; infra/canvas in Grok).
2. **Autonomous Matrix Delegation:**
   Tasks outside its core strength or requiring isolated worktree verification are dispatched autonomously via `synlynk dispatch <target>` without stopping to ask user permission.
3. **Unattended Milestone Drive:**
   The loop advances:
   `Pick Task -> (Implement Locally OR Dispatch Worker) -> Run Verification -> Open PR -> Dispatch Non-Authoring Review -> Merge & Clean Worktree -> Checkpoint -> Next Task`
   stopping only at designated **Reserved Approval Gates**.

---

## 5. Acceptance Criteria (Verification Matrix)

- [ ] **AC-1: Symmetric Dual-Mode Directives in Template Engine:**
  `synlynk/instructions.py` generates `CLAUDE.md`, `GEMINI.md`, `AGENTS.md`, and `GROK.md` with the unified Mode A (Home) vs Mode B (Away) specification.
- [ ] **AC-2: Zero Hardcoded Claude-Centrism in `synlynk/probe.py`:**
  `grep -in "Claude approval" synlynk/probe.py` and `grep -in "escalate to Claude" synlynk/probe.py` return zero matches.
- [ ] **AC-3: Dynamic Runtime Home Injection in `.synlynk/context.md`:**
  `synlynk context` detects running harness and stamps `Active Home Harness` with constitutional precedence.
- [ ] **AC-4: `synlynk home` Command Functional:**
  `synlynk home` displays active home, `synlynk home agy` sets home in config and refreshes context.
- [ ] **AC-5: Instructions Repair Upgrades Legacy Files:**
  `synlynk instructions update --repair` replaces legacy subservient sections in existing repos.
- [ ] **AC-6: Full Test Suite Green:**
  All existing and new unit tests pass cleanly in pytest.
