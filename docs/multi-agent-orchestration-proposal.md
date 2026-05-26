# Synlynk — Multi-Agent Orchestration Proposal

**Date:** 2026-05-22  
**Status:** Draft  
**Author:** Nikhil Soman  

---

## 1. The Problem: Invisible Seams

A solo developer using Claude Code, Gemini CLI, and Codex today faces a coordination problem that no individual AI tool solves:

- Each agent operates with its own isolated context window. When you switch from Claude to Gemini, you rebuild context from scratch or paste it manually.
- There is no shared understanding of *who is doing what* — both Claude and Gemini might pick up the same task, or no agent picks it up because each assumes the other will.
- There are no domain boundaries enforced — Claude ends up doing frontend work, Gemini writes infra code, and the results clash.
- Handoffs between agents are informal ("hey Gemini, Claude left off here") rather than structured — so the receiving agent misses decisions, half-finished reasoning, and known dead-ends.
- Costs are tracked per tool, not per task or per agent — so you can't tell what a feature actually cost across the whole team.

Synlynk v0.2 solved the **single-agent context problem**: shared `project-docs/`, `synlynk exec`, and `context.md` snapshots mean one developer with one AI tool never loses state. The next frontier is the **multi-agent coordination problem**: making a three-agent team (Claude + Gemini + Codex) feel like a single coherent unit amplifying one developer's output.

---

## 2. The Vision: Synlynk as the Orchestration Bus

Synlynk becomes the **local orchestration layer** between a solo developer and a team of AI agents. The developer sets direction; Synlynk routes work to the right agent, manages isolated workspaces, tracks progress on a shared board, and manages handoffs — so every agent picks up exactly where the last one stopped.

```
Developer
    │
    ▼
synlynk assign / start / handoff
    │
    ├─── Claude      (backend · infra · architecture · security)
    ├─── Gemini      (frontend · data research · UI/UX)
    └─── Codex       (tests · migrations · boilerplate)
    │
    ▼
GitHub Projects Board  ←──────────────────────────────────────
    (Agent, Status, Priority auto-synced at every lifecycle point)
```

The developer's only new habit: `synlynk start --issue N` instead of `claude` or `gemini`. Everything else — routing, board updates, worktree creation, context injection, handoffs — is handled by Synlynk.

---

## 3. How the RxCC SOP Maps to Synlynk

The rxcc project established a manual SOP in this session:

| Manual step today | Synlynk command |
|---|---|
| Find issue, determine domain label, identify right agent | `synlynk assign --issue N` |
| Run 3 GraphQL mutations to set Agent + Status on board | (automatic inside `start`) |
| Apply `agent:claude` label | (automatic inside `assign`) |
| Create worktree `feat/claude/<slug>` | (automatic inside `start`) |
| Set `OTP_STUB_ENABLED=false` + `pulumi config set ...` | Captured as task context in handoff note |
| PR body includes `Closes #N` | (templated by `synlynk pr`) |
| Board moves to In Review / Done | (via `pr-status.yml` GitHub Action already in place) |

A full rxcc session under Synlynk orchestration looks like:

```bash
# Developer looks at the board, picks issue #156 (backend task)
synlynk assign --issue 156
# → reads domain:backend label → routes to Claude
# → sets GitHub Projects: Agent=Claude, Status=Todo
# → posts routing comment on issue
# → prints: "Assigned to Claude. Run: synlynk start --issue 156"

synlynk start --issue 156
# → verifies domain:backend → Claude
# → sets Status=In Progress on board
# → creates git worktree at .claude/worktrees/feat-claude-<slug>/
# → generates scoped context.md: only this issue + related tasks + memory
# → launches: claude
#   (Claude reads context, sees its task, works, commits, exits)

# After Claude finishes — a test suite is needed
synlynk handoff --issue 156 --to codex
# → runs synlynk checkpoint (archives completed steps)
# → writes .synlynk/handoffs/156-to-codex.md with:
#     - what was built, which files changed, what tests are missing
#     - open questions Claude flagged
# → prints: "Ready. Run: synlynk start --issue 156 --agent codex"

synlynk start --issue 156 --agent codex
# → creates worktree test/codex/<slug>/
# → injects context.md + handoff note
# → launches: codex
#   (Codex reads the handoff, writes tests, commits, exits)

# Frontend companion issue #157 (Gemini's domain)
synlynk assign --issue 157     # domain:frontend → Gemini, board updated
synlynk start --issue 157      # worktree feat/gemini/<slug>, launches gemini

# Gemini opens PR; pr-status.yml sets Status=In Review automatically
# PR merges; pr-status.yml sets Status=Done automatically
```

---

## 4. New Capabilities Required

### 4.1 `synlynk assign [--issue N] [--agent <name>]`

Routes an issue to the right agent. If `--agent` is omitted, infers from the issue's `domain:*` label.

**What it does:**
1. Reads GitHub Issue labels via `gh` CLI
2. Looks up domain → agent in `.synlynk/config.json` routing table
3. Sets GitHub Projects board: Agent field + Status = Todo
4. Applies `agent:*` label to issue
5. Posts routing comment (branch prefix, commit trailer)
6. Updates `project-docs/agent-manifest.md` with the assignment

**Lite-tier fallback (no GitHub):** reads domain from `todo.md` task metadata; writes assignment to `agent-manifest.md` only.

---

### 4.2 `synlynk start --issue N [--agent <name>]`

Claims a task, sets up a workspace, injects scoped context, launches the right agent.

**What it does:**
1. Confirms agent assignment (from `agent-manifest.md` or `--agent` override)
2. Sets board Status = In Progress
3. Creates a git worktree at `.claude/worktrees/<prefix>-<slug>/` (or `.synlynk/worktrees/` for non-Claude agents)
4. Generates a **scoped** `context.md` — this issue + its dependencies + relevant memory entries only (not the full project context)
5. Writes `.synlynk/agent-state/<agent>.json` with current task ID, worktree path, start time
6. Locks the worktree path against other agents (writes `.synlynk/locks/<worktree>.lock`)
7. Launches the agent CLI with `synlynk exec <agent-cmd>`

**Conflict detection:** if another agent has an active lock on an overlapping set of files, `start` warns before proceeding.

---

### 4.3 `synlynk handoff --issue N --to <agent>`

Structured task handoff between agents.

**What it does:**
1. Runs `synlynk checkpoint` to archive completed steps
2. Reads the git diff in the current worktree to summarise what changed
3. Writes `.synlynk/handoffs/<issue>-to-<agent>.md`:
   ```markdown
   ## Handoff: Issue #N → <agent>
   **From:** Claude (feat/claude/<slug>)
   **Completed:** <list of commits>
   **What was built:** <auto-generated from commit messages>
   **Files changed:** <git diff --stat>
   **Open questions / known issues:** <from sentinel.md + any flagged comments>
   **Next steps:** <remaining todo items from the issue>
   ```
4. Updates `agent-manifest.md` — reassigns issue to target agent
5. Sets board Agent = <target agent>
6. Pushes the current worktree branch (so the next agent can see the commits)
7. Releases the worktree lock
8. Prints: exact `synlynk start` command for the next agent

---

### 4.4 `synlynk team [status]`

Multi-agent dashboard — extends the existing `synlynk status` command.

```
━━━ Active Agents ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 Claude    feat/claude/india-sms-otp    #156  In Progress  42m
 Gemini    —                            —     Idle
 Codex     —                            —     Idle

━━━ Queue ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 #157  [Gemini]  UI: family invite flow       domain:frontend  P1
 #158  [Codex]   Tests: auth hardening        domain:testing   P2
 #159  [Claude]  Infra: SES prod access       domain:infra     P1

━━━ Pending Handoffs ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 #156  Claude → Codex (tests)   ready to start

━━━ Budget ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 Claude $3.20 / $10.00  Gemini $0.00 / $5.00  Codex $0.00 / $3.00
```

---

### 4.5 `synlynk pr [--issue N]`

Creates a GitHub PR from the current worktree with the right body template:

```bash
synlynk pr --issue 156
# → gh pr create --title "feat: <issue title>"
#   --body "Closes #156\n\n## Summary\n...\n\n## Test Plan\n..."
# → sets board Status = In Review (same as pr-status.yml, but immediate)
```

---

## 5. Architecture Changes

### 5.1 New files

```
project-docs/
  agent-manifest.md     # Which agent owns which issue right now
                        # Format: | Issue | Title | Agent | Status | Worktree |

.synlynk/
  agent-state/
    claude.json         # { "issue": 156, "worktree": "...", "started_at": "..." }
    gemini.json
    codex.json
  handoffs/
    156-to-codex.md     # Structured handoff notes (append-only)
  locks/
    feat-claude-india-sms.lock  # Worktree lock files (contain agent + issue + timestamp)
```

### 5.2 Config additions

`.synlynk/config.json` gains a `routing` block:

```json
{
  "schema_version": 2,
  "budget": { "limit_usd": 10.0, "limit_requests": 100 },
  "routing": {
    "backend":  { "agent": "claude",  "branch_prefix": "feat/claude",  "cmd": "claude" },
    "infra":    { "agent": "claude",  "branch_prefix": "feat/claude",  "cmd": "claude" },
    "mobile":   { "agent": "claude",  "branch_prefix": "feat/claude",  "cmd": "claude" },
    "design":   { "agent": "claude",  "branch_prefix": "feat/claude",  "cmd": "claude" },
    "frontend": { "agent": "gemini",  "branch_prefix": "feat/gemini",  "cmd": "gemini" },
    "data":     { "agent": "gemini",  "branch_prefix": "feat/gemini",  "cmd": "gemini" },
    "testing":  { "agent": "codex",   "branch_prefix": "test/codex",   "cmd": "codex" }
  },
  "github": {
    "project_id":    "PVT_kwDOAAUx684BYYIM",
    "agent_field":   "PVTSSF_lADOAAUx684BYYIMzhTecpE",
    "status_field":  "PVTSSF_lADOAAUx684BYYIMzhTeaz0",
    "agents": {
      "claude": "ecf901a8",
      "gemini": "50df70c2",
      "codex":  "32655d84"
    },
    "statuses": {
      "todo":        "f75ad846",
      "in_progress": "47fc9ee4",
      "in_review":   "ec458dde",
      "done":        "98236657"
    }
  }
}
```

### 5.3 Lite tier degradation

When `github` config is absent or `gh` CLI is not installed:
- `assign` writes to `agent-manifest.md` only, skips board updates
- `start` still creates worktrees and injects context — GitHub board is optional
- `handoff` writes the handoff note and prints manual board update instructions

The orchestration value (scoped context, worktrees, routing, handoff notes) is available in Lite tier. GitHub Projects sync is a Full-tier enhancement.

---

## 6. Context Scoping (Critical Improvement)

The current `context.md` is a full project snapshot — all active tasks, full memory, all roadmap items. For multi-agent use this is wasteful and noisy: when Codex is writing tests for issue #156, it doesn't need the frontend roadmap or the DPDP consent decisions.

`synlynk start --issue N` generates a **scoped context** instead:

```markdown
## Context for Issue #156 — India SMS OTP Go-Live

**Your task:** [issue body verbatim]
**Agent:** Claude | **Branch:** feat/claude/india-sms-otp

### Directly relevant tasks
- [ ] MSG-1: AWS SMS package ✅ (done — see handoff note)
- [ ] MSG-3: DNS records (this issue)
- [ ] LM-1: Private beta gate (blocked on this issue)

### Relevant decisions (from memory.md)
- AWS End User Messaging chosen over MSG91 (2026-04-27)
- DLT PE registration done; templates pending approval
- OTP_STUB_ENABLED decoupled from MSG91 key presence

### Handoff note (if applicable)
[contents of .synlynk/handoffs/156-to-codex.md]

### What to ignore
- Frontend roadmap, family plan features, US expansion — not relevant to this task
```

This is generated by a new `context_for_issue()` function that filters `memory.md` entries by keyword relevance to the issue title + labels.

---

## 7. Enforcing the Policy: What Each Agent Reads

### `CLAUDE.md` (in target project)
Updated to say:
> At session start, run `synlynk status`. If a task is active in `.synlynk/agent-state/claude.json`, resume it. Otherwise wait for `synlynk start --issue N`.

### `GEMINI.md` (in target project)
Same contract, referencing Gemini's domain (frontend/data).

### `synlynk init` (for new projects)
Writes CLAUDE.md, GEMINI.md, and `AI_INSTRUCTIONS.md` with the multi-agent session protocol baked in. Projects bootstrapped with `synlynk init --multi-agent` get the full routing config and agent-manifest.md scaffold.

---

## 8. Implementation Roadmap

### v0.3.0 (current scope — do not expand)
- `synlynk doctor`, shell completions, `synlynk cost add`, config validation
- **Prerequisite for multi-agent:** clean config schema + validation sets the stage for v0.4 additions

### v0.4.0 — Agent Routing Foundation
**Goal:** `synlynk assign` and `synlynk team status` work end-to-end

- [ ] `routing` block in config.json (schema_version → 2)
- [ ] `agent-manifest.md` schema + parser
- [ ] `synlynk assign --issue N` — GitHub Issues label read, board update, manifest write
- [ ] `synlynk team` dashboard (extends `synlynk status`)
- [ ] `synlynk init --multi-agent` flag

### v0.5.0 — Workspace Orchestration
**Goal:** `synlynk start --issue N` creates worktrees and injects scoped context

- [ ] Git worktree creation/management (`workspace.py` module)
- [ ] Scoped `context_for_issue()` — keyword-filtered memory + relevant tasks only
- [ ] `.synlynk/agent-state/<agent>.json` tracking
- [ ] `.synlynk/locks/` — simple file locks for conflict detection
- [ ] `synlynk start --issue N` end-to-end
- [ ] `github` config block — Projects board mutations

### v0.6.0 — Handoff Protocol
**Goal:** complete agent-to-agent handoffs with structured notes

- [ ] `synlynk handoff --issue N --to <agent>` — diff summarisation, handoff note generation
- [ ] Handoff notes injected into next agent's scoped context
- [ ] `synlynk pr --issue N` — PR creation with `Closes #N` template
- [ ] Cost attribution per agent per issue in `costs.md`

### v1.0.0 — Full Multi-Agent Team Edition
**Goal:** zero-friction orchestration; developer only sets direction

- [ ] `synlynk watch` enhanced to poll GitHub Issues for new assignments and notify
- [ ] Automatic worktree cleanup after PR merge
- [ ] Team-wide cost dashboard (per-agent totals, per-issue totals)
- [ ] `synlynk sync` — pull latest agent-manifest and handoffs from remote (for async team use)
- [ ] Webhook receiver for GitHub board events

---

## 9. What "Any Solo Dev on Any Project" Looks Like

A developer starting a new project with Synlynk multi-agent:

```bash
cd my-project
synlynk init --multi-agent
# Creates: project-docs/, CLAUDE.md, GEMINI.md, .synlynk/config.json with routing table
# Asks: "Which GitHub org/project? What domains does each agent own?"

# Day 1: add issues to GitHub, apply domain labels
# Synlynk auto-routes them via domain-route.yml (already in place for rxcc)

# Developer morning routine:
synlynk team
# Shows: 3 unstarted Claude tasks, 1 Gemini task, 0 Codex tasks

synlynk start --issue 12   # Claude handles it — domain:backend
# Claude works, commits, exits

synlynk handoff --issue 12 --to codex
synlynk start --issue 12 --agent codex
# Codex writes tests, pushes, exits

synlynk start --issue 15   # Gemini handles it — domain:frontend
# Gemini works concurrently (different worktree, no conflict)

# End of day:
synlynk team
# All issues In Review or Done; board is current; costs logged per agent
```

The developer's cognitive load is: **decide what matters, apply a domain label, run `synlynk start`.** The three-agent team handles the rest.

---

## 10. What Is Not Changing

- **Single-file architecture** — all new commands extend `bin/synlynk.py`; no new executables
- **Append-only logs** — `agent-manifest.md` and handoff notes are append-only; worktree state is additive
- **Lite/Full progression** — all v0.4/v0.5 features work without GitHub; board sync is enhancement-only
- **Shell alias contract** — `synlynk exec <cmd>` remains the launch primitive; `start` is a higher-level wrapper that calls `exec` internally
- **No new runtime dependencies** — `gh` CLI is used via subprocess (already available on any dev machine running GitHub workflows); no Python packages added
