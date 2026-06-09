# synlynk: State DB & Agentic Project Management — Design Spec

**Date:** 2026-06-07
**Status:** Approved — ready for implementation planning
**Author:** Nikhil Soman (brainstorm session with Claude)
**Linked roadmap:** `docs/superpowers/specs/2026-06-06-synlynk-unified-roadmap.md`
**Supersedes:** `project-docs/` flat-file model (v0.3.0)

---

## 1. Problem

`project-docs/` is tracked in git. Every agent worktree gets a snapshot of these files at branch-cut time. As the main branch evolves, worktree snapshots drift silently. Merge resolution picks one stale state over another — no version is correct. Enforcing "never commit docs on feature branches" has not held as a discipline.

The root cause: **project state has been modelled as code**. State should not branch.

---

## 2. Core Invariant

> No matter which worktree an agent runs in, it always reads and writes the same `state.db`.
> Branching is for code. State never branches.

---

## 3. Storage Layout

### 3.1 What moves

`project-docs/` contents move to `~/.synlynk/projects/<project_id>/state.db` (SQLite WAL). The directory is gitignored and removed from tracking. Files remain on disk after migration.

Resolution from any worktree:
```
CWD → walk up to find .synlynk/config.json → read project_id
→ open ~/.synlynk/projects/<project_id>/state.db
→ generate .synlynk/context.md → spawn agent
```

### 3.2 What stays in git

AI instruction templates (`CLAUDE.md`, `GEMINI.md`, `AGENTS.md`, `AI_INSTRUCTIONS.md`, `.cursorrules`) remain git-tracked. These are configuration that agents need on clone, not session state.

### 3.3 What stays as files

`.synlynk/sentinel.md` — ephemeral alerting state written by `check_flatline()` and `check_budgets()`. No historical value. Not migrated to state.db.

`.synlynk/context.md` — generated snapshot written before each exec. Ephemeral by design.

---

## 4. Context Bridge

`generate_context()` is rewritten to query `state.db` instead of reading files. Output format and injection mechanism are unchanged — agents still receive `.synlynk/context.md`. The change is invisible to agents; they see the same context, always current, never a stale worktree snapshot.

### 4.1 Queries that assemble context.md

```sql
SELECT heading, body FROM memory ORDER BY updated_at DESC
SELECT * FROM phases WHERE status IN ('next','in_progress') ORDER BY priority_order
SELECT * FROM stories WHERE status = 'pending' ORDER BY epic_id
SELECT date, session_title, content FROM events
  WHERE user = :username AND type IN ('note','decision','completed')
  AND ts >= date('now','-7 days') ORDER BY ts DESC
-- teammates (team mode):
SELECT date, session_title, content FROM events
  WHERE user != :username AND ts >= date('now','-1 day') ORDER BY ts DESC LIMIT 1 per user
```

### 4.2 New CLI surface

| Command | Purpose |
|---|---|
| `synlynk context dump` | Human-readable markdown to stdout |
| `synlynk context show <table>` | Filtered by table (tasks, roadmap, etc.) |
| `synlynk log "message"` | Append a note event |
| `synlynk story done <id>` | Mark story complete, emit completed event |
| `synlynk memory set <heading> <body>` | Upsert memory section |

### 4.3 Scheduled maintenance (replaces "nightly consolidation")

The DB is always live — no batch import from files is needed. Scheduled ops are maintenance only:

- **Vacuum** — SQLite WAL compaction, nightly
- **Devlog archive** — events older than 30 days where type IN ('note','started','completed') → `events_archive` table
- **Costs rollup** — weekly aggregate rows appended to costs

---

## 5. Agentic Project Management Hierarchy

Human PM anchors on time and capacity. Neither applies to agents. The replacement anchors:

| Human PM | Agentic PM |
|---|---|
| Sprint / calendar date | Capability gate (phase complete when assertions pass) |
| Story points / capacity | Token estimate / quota headroom |
| Velocity (points/sprint) | Throughput (tokens/quota-period) |
| Blocking = waiting on human | Blocking = unmet dependency or quota exhausted |
| Done = sprint ended + accepted | Done = done_criteria verified |

### 5.1 Hierarchy

```
Project
  └── Arc       — strategic direction (pivot/convergence/archive)
        └── Phase     — structural backbone (capability gate, rarely changes)
              └── Epic      — one implementation plan (writing-plans output)
                    └── Story     — one agent task unit (assigned, verifiable)
                          └── Event     — state transition (append-only log)

Memory          — curated durable decisions (maintained separately)
Costs           — session cost ledger (not injected into context)
```

### 5.2 Three evolution archetypes

| Archetype | Example | Mechanism |
|---|---|---|
| Pivot-heavy | synlynk / Tokq | Arc archived + new Arc started + external_signal event |
| Scale-complex | rxcc | Phase priority_order resequenced + reprioritize event |
| Dormant/resumable | cc-videoreframing | checkpoint event → synlynk resume generates re-entry brief |

---

## 6. Complete Schema

### arcs
```sql
CREATE TABLE arcs (
  id              INTEGER PRIMARY KEY,
  name            TEXT NOT NULL,
  status          TEXT NOT NULL DEFAULT 'active', -- active|archived|merged
  rationale       TEXT,
  external_trigger TEXT,
  merged_into     INTEGER REFERENCES arcs(id),
  created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  archived_at     TIMESTAMP
);
```

### phases
Replaces `roadmap.md`. Structural project backbone.
```sql
CREATE TABLE phases (
  id                   INTEGER PRIMARY KEY,
  arc_id               INTEGER REFERENCES arcs(id),
  name                 TEXT NOT NULL,       -- "SQLite Kernel"
  os_layer             TEXT,               -- "Scheduler — data-driven routing"
  infrastructure       TEXT,               -- "SQLite WAL"
  capability_assertion TEXT,               -- "after this, synlynk exec reads from state.db"
  status               TEXT DEFAULT 'planned', -- shipped|next|planned
  priority_order       INTEGER,
  target_alias         TEXT,               -- "v0.5.0 · Aug 2026" — human label only
  UNIQUE(name)
);
```

### epics
One implementation plan = one epic. `source='superpowers-plan'` when generated by writing-plans.
```sql
CREATE TABLE epics (
  id         INTEGER PRIMARY KEY,
  phase_id   INTEGER REFERENCES phases(id),
  name       TEXT NOT NULL,
  source     TEXT DEFAULT 'manual',  -- 'superpowers-plan'|'manual'
  owner      TEXT,
  status     TEXT DEFAULT 'pending', -- pending|active|done
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### stories
Replaces `todo.md`. One agent task unit — assigned, verifiable, dependency-aware.
```sql
CREATE TABLE stories (
  id               INTEGER PRIMARY KEY,
  epic_id          INTEGER REFERENCES epics(id),
  text             TEXT NOT NULL,
  done_criteria    TEXT,              -- explicit verification statement; evaluated by agent/human until autonomous dispatch brainstorm
  depends_on       TEXT,             -- JSON array of story IDs
  status           TEXT DEFAULT 'pending', -- pending|in_progress|done|blocked
  block_reason     TEXT,             -- 'dependency'|'quota'|'human-approval'
  owner            TEXT,
  assigned_agent   TEXT,
  assigned_model   TEXT,
  routing_reason   TEXT,             -- "capability:ok·quota:61K·cost:$0.04"
  estimated_tokens INTEGER,          -- set by Architect agent at epic creation; updated by routing logic
  actual_tokens    INTEGER,          -- measured after completion via extract_tokens()
  created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### events
Replaces `devlogs/`. Append-only universal log. Never updated or deleted.
```sql
CREATE TABLE events (
  id        INTEGER PRIMARY KEY AUTOINCREMENT,
  type      TEXT NOT NULL,
  -- types: started|completed|blocked|decision|note|external_signal|
  --        pivot|reprioritize|checkpoint|resume
  story_id  INTEGER REFERENCES stories(id),
  epic_id   INTEGER REFERENCES epics(id),
  phase_id  INTEGER REFERENCES phases(id),
  arc_id    INTEGER REFERENCES arcs(id),
  user      TEXT,                    -- git username (human) or agent name
  content   TEXT,                   -- narrative or JSON payload
  ts        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

Derived views:
- **devlog** = `SELECT * FROM events WHERE user='nikhil' AND ts >= date('now','-7d') ORDER BY ts DESC`
- **pivot history** = `SELECT * FROM events WHERE type='pivot' ORDER BY ts DESC`
- **decision log** = `SELECT * FROM events WHERE type='decision'`

### memory
Unchanged. Curated durable decisions at section granularity. Schema corrected from draft:
```sql
CREATE TABLE memory (
  id         INTEGER PRIMARY KEY,
  heading    TEXT UNIQUE NOT NULL,  -- "Positioning (decided 2026-06-06)"
  body       TEXT NOT NULL,         -- full markdown section (multiple bullets)
  agent      TEXT,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

`decision` events may partially duplicate memory. This overlap is expected and acceptable — events are the historical log; memory is the curated live state.

### agent_quotas
Token quota tracking per agent. Updated by `extract_tokens()` after each exec.
```sql
CREATE TABLE agent_quotas (
  id           INTEGER PRIMARY KEY,
  agent        TEXT NOT NULL,       -- "claude"|"gemini"|"codex"
  model        TEXT NOT NULL,
  quota_type   TEXT NOT NULL,       -- "hourly"|"daily"|"weekly"|"monthly"
  limit_tokens INTEGER NOT NULL,
  used_tokens  INTEGER DEFAULT 0,
  reset_at     TIMESTAMP,
  updated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(agent, quota_type)
);
```

Throughput ceiling query: `SELECT SUM(limit_tokens - used_tokens) FROM agent_quotas WHERE quota_type='hourly'`

### costs
Existing schema with project FK columns added for attribution:
```sql
CREATE TABLE costs (
  id           INTEGER PRIMARY KEY,
  session_date DATE,
  user         TEXT,
  model        TEXT,
  tokens_in    INTEGER,
  tokens_out   INTEGER,
  cost_usd     REAL,
  story_id     INTEGER REFERENCES stories(id),  -- NEW — nullable
  epic_id      INTEGER REFERENCES epics(id),    -- NEW — nullable
  phase_id     INTEGER REFERENCES phases(id),   -- NEW — nullable
  ts           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

Phase cost rollup: `SELECT SUM(cost_usd) FROM costs WHERE phase_id = :id`

### config
Absorbs both `.synlynk/config.json` and `project-docs/.synlynk_config.json`:
```sql
CREATE TABLE config (
  key   TEXT PRIMARY KEY,
  value TEXT
  -- keys: mode, version, project_name, project_id, init_ts, limit_usd, limit_requests
);
```

### external_refs
Platform sync — one row per entity per platform:
```sql
CREATE TABLE external_refs (
  id           INTEGER PRIMARY KEY,
  entity_type  TEXT NOT NULL,   -- "arc"|"phase"|"epic"|"story"
  entity_id    INTEGER NOT NULL,
  platform     TEXT NOT NULL,   -- "github"|"jira"|"linear"|"asana"
  external_id  TEXT NOT NULL,
  external_url TEXT,
  last_synced  TIMESTAMP,
  UNIQUE(entity_type, entity_id, platform)
);
```

Platform mapping:

| synlynk | GitHub Projects | Jira | Linear |
|---|---|---|---|
| Arc | Project board | Epic (top-level) | Project |
| Phase | Milestone | Version | Cycle |
| Epic | Epic label | Story | Project |
| Story | Issue | Sub-task | Issue |

`state.db` is canonical. Platforms are views. `synlynk sync --github` pushes. Incoming webhooks record status changes as `completed`/`blocked` events.

---

## 7. Agent Routing — capability → quota → cost

`synlynk run` routes each story through a three-gate decision:

```
1. CAPABILITY  — score per (agent, domain) from capability_scores table
                 → filter agents below threshold for this story's domain

2. QUOTA       — story.estimated_tokens vs agent_quotas.headroom
                 → filter agents with insufficient headroom
                 → record block_reason='quota' + reset_at if all agents exhausted

3. COST        — compare cost across remaining candidates
                 → if capability gap <= 0.15, pick cheaper model
                 → record routing_reason on story
```

Routing decision is emitted as a `started` event with full rationale. Over time this builds an empirical record of routing decisions vs. outcomes (estimate accuracy, capability score validity).

---

## 8. Migration — `synlynk migrate`

One-time command. Safe and reversible.

1. Create `~/.synlynk/projects/<project_id>/state.db`
2. Apply schema (all tables above)
3. Parse `project-docs/memory.md` → INSERT INTO memory (sections as heading/body)
4. Parse `project-docs/roadmap.md` → INSERT INTO phases
5. Parse `project-docs/todo.md` → for each milestone heading (## v0.4.0, ## v0.5.0...) INSERT a stub epic row linked to the matching phase; INSERT stories under that epic
6. Parse `project-docs/costs.md` → INSERT INTO costs
7. Parse `project-docs/devlogs/*.md` → INSERT INTO events (type='note', user=filename)
8. Seed one Arc row: `{name: project_name, status: 'active'}`
9. Add `project-docs/` to `.gitignore`
10. Run `git rm --cached project-docs/` — untracks without deleting
11. Print summary. Prompt user to commit `.gitignore` change.

Files remain on disk after migration. Old `project-docs/` content is not deleted.

---

## 9. What Does Not Change

- Agent experience: `.synlynk/context.md` injected before each exec — identical format
- `check_flatline()` and `check_budgets()` — logic unchanged, read from state.db instead of files
- `extract_tokens()` — unchanged, feeds `agent_quotas.used_tokens` and `costs`
- `sentinel.md` — stays in `.synlynk/` as ephemeral alert file
- AI templates in git — `CLAUDE.md`, `GEMINI.md`, `AGENTS.md` unchanged

---

## 10. Out of Scope — Next Brainstorm

**Agent identity, addressability, scheduling, entitlements.** The schema hooks are in place (`assigned_agent`, `done_criteria`, `agent_quotas`, dependency graph in `depends_on`). A daemon watching state.db for pending stories with satisfied dependencies is the natural next step, but requires its own design session covering: durable agent identity (Ed25519, Tokq alignment), autonomous dispatch without human initiation, privilege boundaries, and the entitlement model for story auto-approval.

---

## 11. Roadmap Alignment

| Version | How this spec lands |
|---|---|
| v0.5.0 | `synlynk migrate` ships — moves project-docs to state.db, full Arc/Phase/Epic/Story/Event schema |
| v0.5.0 | Capability engine + agent_quotas + routing logic fully operational |
| v0.7.0 | Daemon watches state.db for pending stories → autonomous dispatch (next brainstorm) |
| v0.8.0 | `context --for <agent>` reads from state.db via HTTP Context Server |
| v1.0.0 | external_refs sync + state.db → Tokq memory unit mapping defined |
