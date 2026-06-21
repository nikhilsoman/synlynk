# Invisible State — Design Spec

**Date:** 2026-06-21  
**Status:** Draft — pending user review  
**Target version:** v1.0.0 (dog-food migration on synlynk itself ships as part of v0.9.1 prep)  
**Brainstorm session:** `.superpowers/brainstorm/66881-1782039767/`

---

## Goal

Eliminate `project-docs/` from git entirely. All synlynk-managed state moves to `~/.synlynk/projects/<hash>/` on the local machine — invisible to the human, conflict-free, and relay-syncable. The human talks to their preferred agent; other agents are invisible workers. No markdown files to manage, no merge conflicts, ever.

---

## Core Principle: Local-First, Sync is Additive

Every tier of the system works standalone. Upper tiers add reach, not dependency.

```
Tier 0  Solo / offline / air-gapped      ← always works, zero network
  ↕ optional
Tier 1  Team via relay (v0.9.3)          ← graceful degradation to Tier 0 on failure
  ↕ optional (or Tier 1b: git transport)
Tier 2  Workspace / multi-repo (v0.10)   ← cross-repo epics
  ↕ optional
Tier 3  Community / Tokq (v1.1–v1.3)    ← cross-workgroup reputation
```

Relay failure → Tier 0, fully operational. Security blocks relay → Tier 1b git transport or stay on Tier 0. Community server down → all lower tiers unaffected. The human never sees any of this — they just talk to their agent.

---

## What Changes

### Removed from git (forever)

```
project-docs/todo.md
project-docs/roadmap.md
project-docs/memory.md
project-docs/costs.md
project-docs/devlogs/<user>.md
project-docs/source-map.md
project-docs/.synlynk_config.json
```

The `project-docs/` directory is removed from the repository entirely — not `.gitignore`d, removed. `git rm -r project-docs/` is part of the `synlynk migrate` commit.

### What stays in git (unchanged)

```
CLAUDE.md / AGENTS.md / GEMINI.md   ← session protocol for each agent
.synlynk/config.json                ← budget limits (non-sensitive, project-specific)
synlynk/__init__.py                 ← your actual source code
```

`CLAUDE.md` / `AGENTS.md` / `GEMINI.md` retain their session protocol role — they tell each agent how to behave, what CLI commands to run at session start, and how to interact with synlynk. They no longer instruct agents to "update project-docs/" for anything.

### New local state location

All state lives at `~/.synlynk/projects/<hash>/` where `<hash>` is the existing 8-char md5 of the git root (already used for `state.db`). Nothing in this directory is ever committed to git.

```
~/.synlynk/projects/<hash>/
  state.db          ← SQLite, source of truth for structured state
  context.md        ← generated before each exec/dispatch, agent reads this
  todo.md           ← generated view of active stories (human-readable)
  roadmap.md        ← generated view of story phases + release arc
  memory.md         ← authored: human/agent writes decisions here; read on each cycle
  devlog.md         ← authored: agent appends session entries; human reads
  costs.md          ← generated from telemetry.json
  source-map.md     ← generated from source_symbols table
```

**Generated views** (`todo.md`, `roadmap.md`, `costs.md`, `source-map.md`, `context.md`) are overwritten by synlynk on each relevant cycle. Do not hand-edit these — edits will be overwritten.

**Authored files** (`memory.md`, `devlog.md`) are written by humans and agents, read by `generate_context()` on each cycle. Edits persist. On next context generation, synlynk reads `memory.md`, computes a content hash per line, and inserts any lines not already present in the `notes` table (dedup by hash). This means a human can open `~/.synlynk/projects/<hash>/memory.md`, add a line, and it will appear in state.db and every future context without any explicit command.

---

## New SQLite Tables

Two new tables added to `state.db`. All existing tables (`stories`, `capability_ratings`, `source_symbols`, `autopilot_runs`) are unchanged.

### `notes` — replaces memory.md

```sql
CREATE TABLE IF NOT EXISTS notes (
    id          TEXT PRIMARY KEY,          -- uuid4
    content     TEXT NOT NULL,             -- the decision or note, markdown
    author      TEXT NOT NULL,             -- git user.name or gh login
    tags        TEXT DEFAULT '[]',         -- JSON array of topic tags
    ts          TEXT NOT NULL,             -- ISO 8601
    ed25519_sig TEXT                       -- signed at write time
);
```

`synlynk memory add "we are using Postgres not MySQL"` inserts a row. `generate_context()` reads all notes sorted by `ts DESC`, renders them into `memory.md` and injects into context. The agent can also insert notes inline during a session via the existing tool-call pattern.

### `devlog_entries` — replaces devlogs/<user>.md

```sql
CREATE TABLE IF NOT EXISTS devlog_entries (
    id           TEXT PRIMARY KEY,         -- uuid4
    author       TEXT NOT NULL,            -- git user.name
    session_date TEXT NOT NULL,            -- YYYY-MM-DD
    content      TEXT NOT NULL,            -- markdown narrative block
    ts           TEXT NOT NULL             -- ISO 8601, entry written time
);
```

Append-only. `checkpoint()` inserts a new row. `generate_context()` renders the last 3 entries per author into `devlog.md` and injects a team digest into context (team mode: last 1 entry per teammate). Never updated in place — always a new row.

---

## generate_context() — New Flow

The existing `generate_context(scope)` function is updated to read from state.db instead of markdown files. The `context.md` output format is unchanged so all agents continue to work without instruction file updates.

**Full scope (existing behaviour, new source):**
1. Read `stories` table (active tasks only, `status != 'done'`) → renders `## Active Tasks` block
2. Read `notes` table (all, `ts DESC`) → renders `## Memory & Decisions` block  
3. Read `devlog_entries` (last 3 sessions, current author) → renders `## Recent Sessions` block
4. Read `source_symbols` (scan cache) → renders `## Source Architecture` block
5. Read `telemetry.json` → renders `## Budget Pulse` block
6. Write assembled context to `~/.synlynk/projects/<hash>/context.md`

**Task scope (existing, unchanged):**
`generate_context(scope="task:<story_id>")` → `_generate_task_context()` path, unaffected.

**Generated views refreshed alongside context:**
- `todo.md` — regenerated from `stories` (active + deferred)
- `memory.md` — regenerated from `notes` table (human may re-edit; next cycle re-reads)
- `devlog.md` — regenerated from `devlog_entries` (last 10 sessions)
- `roadmap.md` — regenerated from `stories` grouped by phase + hardcoded release arc
- `costs.md` — regenerated from `telemetry.json`

---

## Human Interface

Three modes, all coexist:

### 1. Conversational (primary)
The human talks to their preferred agent (Claude Code, AGY, Codex) as they do today. The agent reads `context.md` at session start and has full project state. The human asks:

- "what's next?" → agent answers from state.db via context.md
- "remember we're using Postgres" → agent calls `synlynk memory add "..."` or the new `cmd_memory_add()` inline
- "show me what my teammates have been working on" → agent reads devlog context section
- "dispatch this to codex" → `synlynk dispatch codex --task "..."` (unchanged)

### 2. CLI (power users and scripting)

New commands added:

| Command | Description |
|---|---|
| `synlynk memory add "<text>"` | Inserts a note into `notes` table, signed with Ed25519 |
| `synlynk memory list [--tag <tag>]` | Lists recent notes |
| `synlynk todo` | Prints active stories as a formatted task list |
| `synlynk roadmap` | Prints the generated roadmap to terminal |
| `synlynk devlog [--sessions N]` | Prints last N devlog entries |
| `synlynk migrate` | One-time migration from project-docs/ to state.db |
| `synlynk export [--format md\|json]` | Exports full project state snapshot on demand |

Existing commands (`synlynk status`, `synlynk story`, `synlynk score`, `synlynk scan`, `synlynk dispatch`, `synlynk jobs`) are unchanged.

### 3. HUD (ambient terminal presence)

A thin status bar rendered below terminal output. Activates via `synlynk daemon` (v0.9.2) or injected as a post-exec hook. Two states:

**Ambient (always visible, minimal):**
```
● auth-oauth-flow  ·  $3.40  ·  relay 2↑  ·  no alerts
```

**Expanded (on event, auto-collapses after 4s):**
```
✓ job-a1b2 done  ·  codex wrote 12 tests · all passing    auto-collapses in 4s
● auth-oauth-flow  ·  $3.40  ·  relay 2↑  ·  no alerts
```

**Events that trigger expansion:**
- Background job completes (success or failure)
- Budget crosses 80% threshold
- Sentinel alert fires (FLATLINE, INSTRUCTION_DRIFT, etc.)
- Relay peer connects or disconnects
- Teammate story synced via relay

HUD is read-only output. Full TUI (`synlynk tui`) ships at v0.9.2 as an interactive layer on top.

---

## Tier 0: Solo / Offline

Baseline that always works. No network, no relay, no team.

- `state.db` is the only source of truth
- Generated views refresh on each `synlynk exec` or `synlynk generate`
- Human edits `memory.md` locally; absorbed on next context cycle
- Devlog appended by `checkpoint()`; stays local
- `synlynk export` produces a markdown or JSON snapshot at any time

---

## Tier 1: Team via Relay (v0.9.3)

Relay syncs state.db deltas between teammates over WSS/443. Each machine is authoritative for its own writes. Relay is a broadcast bus, not a source of truth.

**Tables synced as deltas:**
- `stories` — last-write-wins per `story_id`
- `notes` — last-write-wins per `id`
- `devlog_entries` — append-only, never conflicts
- `capability_ratings` — append-only, never conflicts

**Tables NOT synced (local only):**
- `source_symbols` — too large, machine-specific
- `autopilot_runs` — local agent history
- Telemetry — local cost tracking

**Relay failure behaviour:** Each machine continues fully on Tier 0. State.db accumulates local writes. On reconnect, relay runs a delta merge: new rows appended, last-write-wins applied to `stories` and `notes`. No data loss.

**Security-blocks-relay fallback (Tier 1b):** `synlynk export --delta` produces a compact JSON bundle of unsynced rows. Bundle can be committed to a `synlynk-state` sidecar branch or shared via any file transfer. `synlynk import --delta <file>` applies it. Same conflict-free merge model as relay, async.

**LAN mode:** Relay runs on local network via mDNS discovery + direct WSS. No internet required. Configured via `--relay-mode lan` in `.synlynk/config.json`.

---

## Tier 2: Workspace / Multi-repo (v0.10.0)

Relay scope expands to federate `stories` and `capability_ratings` across repos in a workspace. Each repo retains its own `state.db`. A workspace-level `state.db` at `~/.synlynk/workspaces/<workspace-hash>/state.db` holds cross-repo epics and aggregated scores.

Details deferred to workspace spec.

---

## Tier 3: Community / Tokq (v1.1–v1.3)

Ed25519-signed `capability_ratings` (signing already wired in v0.9.0) propagate to the community server. Cross-workgroup agent reputation emerges from aggregated, tamper-evident ratings. The `notes` table entries are optionally published (with author consent) to community knowledge pools. Tokq bridge at v1.3 makes ratings and notes portable across organisations via the open ledger protocol.

Details deferred to community and Tokq specs.

---

## Migration: `synlynk migrate`

Run once per project. Designed to be dog-fooded on synlynk itself first.

**Steps (in order, atomic — rolls back on any failure):**

1. Verify `project-docs/` exists and is git-tracked; abort if already migrated
2. Parse `project-docs/todo.md` — extract tasks with `<!-- id:N -->` comments → `INSERT INTO stories` (preserving story_ids where possible)
3. Parse `project-docs/memory.md` — split by `##` sections or line boundaries → `INSERT INTO notes` (author from git log of last edit, ts from file mtime)
4. Parse `project-docs/devlogs/*.md` — each `## YYYY-MM-DD` section → `INSERT INTO devlog_entries` (author from filename)
5. Parse `project-docs/costs.md` → validate telemetry.json coverage (costs.md entries already captured in telemetry; this is a consistency check only)
6. Generate initial views at `~/.synlynk/projects/<hash>/`
7. `git rm -r project-docs/`
8. Update `.gitignore` to add a comment (directory is removed, not ignored)
9. Update `CLAUDE.md` / `AGENTS.md` / `GEMINI.md` — remove all `project-docs/` references, update session protocol to new CLI commands
10. Stage and commit: `chore: migrate project-docs to synlynk state.db [synlynk migrate]`

**Dry-run mode:** `synlynk migrate --dry-run` prints what would be imported without writing to DB or running git commands.

**Rollback:** If any step after step 6 fails, the DB writes are rolled back (SQLite transaction), git changes are unstaged. The `project-docs/` directory is left intact.

---

## CLAUDE.md / AGENTS.md Updates

Session protocol in each instruction file changes from:

```markdown
- Update task status in project-docs/todo.md
- Append decisions to project-docs/memory.md
- Log costs in project-docs/costs.md
- Append devlog entry to project-docs/devlogs/<username>.md
- Always git pull before editing any project-docs/ file
```

To:

```markdown
- Record decisions: `synlynk memory add "<decision>"` 
- Mark tasks done: `synlynk story done <story-id>` or via conversation
- Costs tracked automatically by synlynk — no manual logging needed
- Devlog appended automatically by `synlynk checkpoint`
- No project-docs/ directory — all state is in ~/.synlynk/ and managed by synlynk
```

---

## What This Unlocks on the Roadmap

| Milestone | How invisible state enables it |
|---|---|
| v0.9.1 Team Onboarding | `synlynk join` imports relay state into local state.db — no file conflict on join |
| v0.9.2 Async Daemon | Daemon writes to state.db directly; no file locking issues across processes |
| v0.9.3 Relay | Relay syncs DB rows, not markdown files — clean delta model |
| v0.9.2+ HUD | Daemon emits events; HUD reads live from state.db |
| v1.0.0 Public Launch | New users get zero-friction init — no project-docs/ to explain or manage |
| v1.3 Tokq | Signed notes + ratings in state.db are the trust anchor for the open ledger |

---

## Implementation Order

1. **Add `notes` and `devlog_entries` tables** — schema migration in `_init_db()`
2. **`cmd_memory_add()` + `cmd_memory_list()`** — CLI entry points
3. **Update `generate_context()`** — read from state.db instead of markdown files; write generated views to `~/.synlynk/projects/<hash>/`
4. **Update `checkpoint()`** — append to `devlog_entries` table instead of file
5. **Update `update_costs()`** — no longer writes to `project-docs/costs.md`
6. **`synlynk migrate`** — full migration command with dry-run + rollback
7. **Update CLAUDE.md / AGENTS.md / GEMINI.md templates** in `_build_templates()`
8. **Dog-food: run `synlynk migrate` on synlynk itself** — open as standalone PR
9. **HUD foundation** — thin ambient bar, event expansion (ship with v0.9.2 daemon)

Steps 1–8 are the v0.9.1 target. Step 9 is v0.9.2.
