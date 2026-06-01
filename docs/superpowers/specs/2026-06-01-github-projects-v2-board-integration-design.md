# GitHub Projects V2 Board Integration
**Date:** 2026-06-01  
**Status:** Approved Design  
**Release target:** v0.4 (August 2026) — alongside Cross-Repo Standards Distribution  
**Author:** Claude Sonnet 4.6 (brainstorming session with Nikhil Soman)  

---

## Problem

Agents in a polyglot workgroup (Claude, Gemini, Codex) have no live visibility into what other agents are doing — especially across repos. The rxcc S-037 incident (Claude pushed to a branch Gemini was mid-commit on, causing 30 minutes of recovery) is the canonical failure: both agents had legitimate context but neither knew the other was active.

The rxcc CLAUDE.md currently addresses this with a hardcoded 15-line GraphQL snippet that agents must copy-paste each session to update the GitHub Projects V2 board. This is the pattern Synlynk should own.

---

## Scope

This feature adds GitHub Projects V2 as a **bidirectional coordination layer** within Synlynk:

- **Write path:** Five lifecycle commands that keep the board in sync as agents start work, open PRs, and finish.
- **Read path:** Board state injected into `.synlynk/context.md` on every session start, giving every agent a "Do Not Touch" WIP signal before they write a line of code.

This is **not** a dashboard, polling daemon, or webhook receiver — those belong in v0.6 (Full Board Gateway). This is the foundational read/write substrate that v0.6 builds on.

---

## Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Config split | Auth token global (`~/.synlynk/`), board schema per-repo (`.synlynk/`) | Token is machine-level; board IDs are repo-level and should be committed |
| Field resolution | Dynamic on every command | No stale cache to debug; ~200ms overhead is invisible next to a `git push` |
| Review enforcement | Soft suggestion with warning | Hard enforcement breaks solo human + 1 agent setups; rotation config is per-repo |
| Board failures | Non-blocking — degrade gracefully | Board hygiene must never block local workflow |
| v0.6 path | `synlynk board status` is a one-shot query now; v0.6 adds the polling daemon on top | Avoids daemon complexity until the bidirectional layer is proven |

---

## Configuration

### `~/.synlynk/config.json` (global, never committed)

```json
{
  "github": {
    "token": "ghp_...",
    "agent_identity": "claude"
  },
  "registered_repos": [
    "Dialify/rxcc",
    "Dialify/synlynk"
  ]
}
```

### `.synlynk/config.json` (per-repo, committed)

```json
{
  "board": {
    "project_id": "PVT_kwDO...",
    "fields": {
      "status_field_id": "PVTSSF_...",
      "agent_field_id": "PVTSSF_...",
      "status_options": { "Todo": "...", "In Progress": "...", "In Review": "...", "Done": "..." },
      "agent_options": { "claude": "...", "gemini": "...", "codex": "..." }
    },
    "review_rotation": {
      "claude": "gemini",
      "gemini": "codex",
      "codex": "claude"
    }
  }
}
```

Field option IDs are discovered dynamically at runtime via GraphQL introspection. The `fields` block in config is populated by `synlynk board connect` as a reference, but values are always re-queried before mutations.

---

## Commands

### `synlynk board connect <project-url>`

One-time setup per repo. Introspects the board schema and registers the repo.

1. Parse org/repo + project number from URL
2. GraphQL: fetch project metadata (id, fields, option IDs)
3. Detect Agent field + Status field by name convention (`"Agent"`, `"Status"`)
4. Write project_id + field schema to `.synlynk/config.json`
5. Register repo in `~/.synlynk/config.json → registered_repos`
6. Print confirmation table: fields found, agent options, status columns

Fails loudly if Agent or Status fields are not found — prints expected vs. actual field names.

---

### `synlynk start --issue <n>`

The primary entry point for any agent beginning work on a ticket.

1. Fetch issue metadata (title, labels, current board item ID)
2. **Read WIP from all registered repos** (read path — happens before any write)
3. Warn if issue's domain label routes to a different agent (soft)
4. If issue is not yet on the board, add it automatically
5. GraphQL: set Agent = self, Status = In Progress
6. Add label `agent:<name>` to the issue
7. Create git worktree at `.synlynk/worktrees/<branch>`
8. Write `.synlynk/wip.json` with issue number + item ID
9. Inject `## Live WIP` block into `.synlynk/context.md`

The read path runs before the write path so the agent sees any in-flight conflicts before claiming the ticket.

---

### `synlynk pr [--title <t>]`

Called when the agent is ready to open a pull request.

1. Read current issue from `.synlynk/wip.json`
2. GraphQL: set Status = In Review on board
3. Derive suggested peer reviewer from `review_rotation` config
4. Run `gh pr create` with `Closes #N` in body
5. Assign suggested reviewer; print warning if overridden by user
6. Post WIP comment on the issue: "PR opened by `<agent>`"

---

### `synlynk done`

Called after the PR is merged.

1. Verify PR is merged; warn with `--force` override if not
2. GraphQL: set Status = Done on board
3. Archive checked-off tasks to devlog (reuses existing `checkpoint` logic)
4. Delete git worktree + local branch
5. Clear `.synlynk/wip.json`
6. Remove this issue from `## Live WIP` in `context.md`

---

### `synlynk board status`

Read-only one-shot query. No daemon.

Queries all registered boards for In Progress + In Review items and renders a terminal table:

```
REPO          ISSUE  AGENT    BRANCH                        STATUS
rxcc          #42    gemini   feat/gemini/ui-timeline       In Progress
rxcc          #38    codex    test/codex/auth-suite         In Review
synlynk       #12    claude   fix/claude/context-slice      In Progress
```

This is the lightweight precursor to the v0.6 polling daemon. Same query, no background process.

---

## Read Path — Context Injection

On every `synlynk start` or `synlynk exec`, Synlynk queries all repos in `registered_repos`, collects In Progress and In Review items, and writes a `## Live WIP — other agents` block into `.synlynk/context.md`:

```markdown
## Live WIP — other agents
<!-- auto-injected by synlynk, do not edit -->

| Repo | Issue | Agent | Branch | Status |
|------|-------|-------|--------|--------|
| rxcc | #42 | gemini | feat/gemini/ui-timeline | In Progress |
| rxcc | #38 | codex | test/codex/auth-suite | In Review |

⚠ Do not push to these branches.
```

If a registered repo's board is unreachable, it is silently excluded from the WIP block. `synlynk doctor` surfaces stale registrations.

---

## Error Handling

| Failure | Behavior |
|---|---|
| No GitHub token | All board commands degrade gracefully — skip board sync, warn once per session |
| GitHub API 401/403 | Print token expiry hint; skip board sync; never block worktree creation |
| Issue not on board | `synlynk start` adds it automatically before setting In Progress |
| Agent/Status field not found | `synlynk board connect` fails loudly; `synlynk start` warns and skips board sync |
| Registered repo unreachable | Excluded from Live WIP silently; `synlynk doctor` surfaces it |
| `synlynk done` before PR merged | Warns; requires `--force` to override |

**Principle:** board sync failures never block local workflow.

---

## `.synlynk/wip.json`

New small file written by `synlynk start`, cleared by `synlynk done`. Tracks the active issue for the current worktree so subsequent commands don't require `--issue` every time.

```json
{
  "issue_number": 42,
  "board_item_id": "PVTI_...",
  "branch": "fix/claude/ocr-timeout",
  "agent": "claude",
  "started_at": "2026-06-01T10:30:00Z"
}
```

---

## Testing

- **Unit:** GraphQL query/mutation builders — mock HTTP client, not `gh` CLI
- **Unit:** Context injection — assert `## Live WIP` block renders correctly from seeded board state
- **Unit:** `wip.json` lifecycle — written on `start`, cleared on `done`
- **Integration:** `synlynk board connect` against a real test project (fixture in CI)
- **Integration:** `synlynk start` + `synlynk done` round-trip
- **Degradation:** All five commands pass with no GitHub token set

---

## Roadmap Placement

| Release | Scope |
|---|---|
| **v0.4 (this spec)** | `board connect`, `start`, `pr`, `done`, `board status` + context injection |
| **v0.6** | Polling daemon, real-time WIP signals, board → worktree automation (builds on this foundation) |

The v0.4 scoped context slicing (`synlynk context --task <id>`) in the existing roadmap remains unchanged — board integration is additive, not a replacement.
