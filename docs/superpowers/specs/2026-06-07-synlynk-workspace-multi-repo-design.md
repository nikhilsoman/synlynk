# synlynk: Workspace & Multi-Repo Design Spec

**Date:** 2026-06-07  
**Status:** Approved — ready for implementation planning  
**Author:** Nikhil Soman (brainstorm session with Claude)  
**Depends on:** `docs/superpowers/specs/2026-06-07-synlynk-state-db-agentic-pm-design.md`  
**Closes:** Gap 10 (Network Identity / multi-project keypair) from arc gap analysis  

---

## 1. Problem

synlynk's current design is project-scoped: one state.db per git repo, one identity keypair per repo, no shared state across repos. This breaks for multi-repo products in three ways:

1. **Context isolation** — an agent in `frontend/` has no visibility into backend API decisions, constraints, or in-progress work next door.
2. **Identity fragmentation** — one keypair per repo means one person has N identities across N repos, making attribution, audit, and Tokq registration incoherent.
3. **Cross-repo coordination** — a feature spanning frontend + backend requires two separate Epics with no structural link. The Architect's spec lives in one repo; the implementation stories are split with no shared parent.

---

## 2. Core Invariants

> A **workspace** is the unit of organization above a repo. One product = one workspace. A workspace spans N repos. A single repo is a workspace with one member — the solo case is structurally identical, just invisible to the user.

> **State never branches, and state never splits by repo.** All repos in a workspace share one `~/.synlynk/workspaces/<workspace_id>/state.db`. Repos are a dimension within that DB, not a boundary between DBs.

> **Identity is machine-scoped, not workspace- or repo-scoped.** One Ed25519 keypair per person per machine. Generated once. Shared across all workspaces on that machine.

---

## 3. Workspace Structure

### 3.1 File layout

```
~/.synlynk/
  identity.key                              ← Ed25519 private key, chmod 600
  identity.json                             ← { machine_uuid, public_key,
                                                fingerprint, created_at,
                                                git_user, git_email }
  workspaces/
    <workspace_name>/                       ← human-readable slug (e.g. "my-product")
      state.db                              ← ALL workspace state (SQLite WAL)
    another-product/
      state.db

<repo>/.synlynk/                           ← thin pointer only
  config.json                              ← { workspace_id, repo_id,
                                               workspace_name, project_name }
  context.md                               ← generated snapshot (overwritten each exec)
```

**The per-repo `.synlynk/` directory becomes a thin pointer** — only `config.json` (workspace address) and `context.md` (generated). No state, no telemetry, no keypair.

### 3.2 What lives in workspace state.db

**Workspace-level (shared across all repos):**
`arcs`, `phases`, `epics`, `memory`, `constraints`, `config`, `inbox`, `schedules`, `roles`, `entitlements`, `dispatch_log`, `external_refs`

**Repo-tagged (in same DB, filtered by `repo_id`):**
`stories`, `events`, `costs`, `agent_quotas`, `jobs`

**New tables:** `repos`, `sync_log` (see Section 6)

### 3.3 Key change from prior design

| Aspect | Before | After |
|---|---|---|
| Identity location | `.synlynk/identity.key` (per project) | `~/.synlynk/identity.key` (per machine) |
| State location | `~/.synlynk/projects/<project_id>/state.db` | `~/.synlynk/workspaces/<name>/state.db` |
| Cross-repo Epics | Not supported | First-class (stories have `repo_id` FK) |
| Solo dev experience | Unchanged (one project = one state.db) | Unchanged (one workspace, one repo member — invisible) |

---

## 4. Init + Join Flow

### 4.1 Path A — solo dev, first `synlynk init` on a machine

```
$ cd ~/dev/my-product/frontend && synlynk init

1. No ~/.synlynk/identity.key → generate Ed25519 keypair
   Writes ~/.synlynk/identity.key (chmod 600)
   Writes ~/.synlynk/identity.json { machine_uuid, public_key, git_user, git_email }

2. No workspace found → create workspace
   workspace_name = git remote slug OR parent dir name → "my-product"
   workspace_id   = uuid4()
   Creates ~/.synlynk/workspaces/my-product/state.db
   Seeds: repos, arcs, phases, epics, roles, entitlements tables with defaults

3. Register this repo
   INSERT INTO repos { id="frontend", name="frontend", path=cwd, git_remote }
   Writes .synlynk/config.json { workspace_id, workspace_name, repo_id: "frontend" }

4. Writes project-docs/ templates (conventions.md, roadmap.md, ...)

✓ Workspace "my-product" created · 1 repo · identity ready
  Hint: "To add another repo: cd ../backend && synlynk workspace join my-product"
```

Identity generation is skipped if `~/.synlynk/identity.key` already exists — the machine keypair is generated exactly once.

### 4.2 Path B — joining a second repo to an existing workspace

**Explicit join:**
```bash
cd ~/dev/my-product/backend
synlynk workspace join my-product
# Prompts: "Repo name for this directory? [backend]" → Enter
# INSERT INTO repos { id="backend", path=cwd, git_remote }
# Writes .synlynk/config.json { workspace_id, repo_id: "backend" }
# ✓ backend joined workspace "my-product" · workspace now has 2 repos
```

**Auto-detect on `synlynk init`:**  
If the GitHub remote matches an org/owner already present in a known local workspace, prompt:
```
Found related workspace "my-product" (frontend — same GitHub org)
Join it? [Y/n]
```

### 4.3 Path C — inheriting an existing multi-repo product

```bash
# Init in any repo first — order doesn't matter
cd ~/dev/existing-product/api && synlynk init
# → creates workspace "existing-product", registers "api"

# Join remaining repos
cd ../web   && synlynk workspace join existing-product
cd ../infra && synlynk workspace join existing-product

# ✓ Workspace "existing-product" · 3 repos: api · web · infra
# No parent-dir config file. No monorepo restructuring. Existing git history untouched.
```

### 4.4 Workspace management CLI

```bash
synlynk workspace list                          # all workspaces on this machine
synlynk workspace join <name-or-id>             # add current repo to existing workspace
synlynk workspace status                        # all repos, last activity, open epics
synlynk workspace rename <new-name>             # rename workspace slug
synlynk workspace trust <member> <fingerprint>  # confirm a new team member's key (one-time)
synlynk workspace conflicts                     # list state conflicts awaiting human resolution
```

---

## 5. Identity

### 5.1 Machine-level keypair

```
~/.synlynk/identity.key    — Ed25519 private key, chmod 600
~/.synlynk/identity.json   — {
  "machine_uuid":  "<uuid4>",
  "public_key":    "<ed25519-pubkey-hex>",
  "fingerprint":   "<sha256-hex>",
  "created_at":    "<iso8601>",
  "git_user":      "<git config user.name>",
  "git_email":     "<git config user.email>"
}
```

Generated once at first `synlynk init` on a machine. Never regenerated unless explicitly rotated. Shared across all workspaces on that machine.

**Replaces:** The per-project `.synlynk/identity.key` specified in the agent identity spec. All references to identity key path now point to `~/.synlynk/identity.key`.

### 5.2 Identity by scenario

**Solo dev, single machine:** One keypair, one workspace. All dispatch_log and event rows signed with the machine key. Trivial.

**Solo dev, two machines (laptop + desktop):** Two keypairs (m1, m2). Separate state.dbs. Events signed by their originating machine. Export carries the originating machine's sig — provably attributed. At Tokq Alpha: both machine identities register under one Tokq account and the cloud aggregates them.

**Simulated team (multiple git identities, one machine):** Identity = `machine_uuid + git_user at dispatch time`. Switching `git config user.name` to "gaurav-sim" produces events with `user="gaurav-sim"`, all signed by the same machine key. State.db records distinct human actors with full cost and activity attribution per simulated member. No extra keypairs or infrastructure needed.

**Real team (separate machines):** Each person generates their keypair on their own machine at first `synlynk init`. Their `identity.json` is included in sync exports. On first event import from a new member, synlynk prompts for fingerprint confirmation (one Slack message: "my fingerprint is ab:cd:ef"). Subsequent syncs auto-verify. Pre-Tokq trust is local and manual-bootstrapped. Tokq Alpha provides cryptographic verification at the cloud level.

### 5.3 Closes Gap 10

The "machine vs. project keypair" question (Gap 10 from arc gap analysis, previously parked at v0.9.0) is fully resolved by this design. Machine-level identity is the answer. No further design work needed.

---

## 6. Schema Additions

### 6.1 New tables

```sql
CREATE TABLE repos (
  id         TEXT PRIMARY KEY,    -- slug: "frontend", "backend", "infra"
  name       TEXT NOT NULL,
  path       TEXT NOT NULL,       -- absolute path on this machine
  git_remote TEXT,                -- for auto-detect and GitHub cross-linking
  joined_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE sync_log (
  id            INTEGER PRIMARY KEY,
  member        TEXT NOT NULL,     -- git_user of the remote member
  public_key    TEXT NOT NULL,     -- their Ed25519 public key (verified on first sync)
  last_event_id INTEGER,           -- last event ID received from them (idempotency)
  last_synced   TIMESTAMP,
  sync_channel  TEXT,              -- "git:<repo-url>" | "nats:<subject>"
  UNIQUE(member, sync_channel)
);
```

### 6.2 Additions to existing tables

```sql
-- stories: add repo scope
ALTER TABLE stories ADD COLUMN repo_id TEXT REFERENCES repos(id);

-- events: add repo scope (NULL = workspace-level event)
ALTER TABLE events ADD COLUMN repo_id TEXT REFERENCES repos(id);

-- costs: add repo attribution
ALTER TABLE costs ADD COLUMN repo_id TEXT REFERENCES repos(id);

-- agent_quotas: add repo scope (NULL = workspace-wide quota)
ALTER TABLE agent_quotas ADD COLUMN repo_id TEXT REFERENCES repos(id);
```

### 6.3 config.json update

```json
{
  "workspace_id":   "<uuid>",
  "workspace_name": "my-product",
  "repo_id":        "frontend",
  "project_name":   "My Product"
}
```

---

## 7. Context Generation

`generate_context()` opens `~/.synlynk/workspaces/<workspace_name>/state.db` (resolved from `config.json`) and generates two layers:

### 7.1 Workspace layer (always included, every agent)

- Active arc name + rationale
- Current phase name + capability assertion
- All active constraints (full text, ordered by created_at desc)
- Workspace-level memory entries (heading + body, all)
- Current epic details if the dispatched story has an `epic_id` (name, description, which repos are involved)

### 7.2 Repo slice (filtered to current repo)

- Stories WHERE `repo_id = this_repo` AND `status IN ('pending', 'in_progress')` — ordered by dependency
- Recent events WHERE `repo_id = this_repo` — last 20, for local context continuity
- Memory entries tagged with this repo_id (repo-specific decisions, patterns)

### 7.3 Architect phase override

When generating context for the **Architect role**, the repo slice expands to include all repos' stories within the current epic. The Architect needs the full cross-repo picture to write a coherent spec that spans frontend + backend + infra correctly.

### 7.4 Mapping to `scope` parameter

| `scope` value | What's included |
|---|---|
| `'workspace'` | Full workspace layer only (no repo slice) — for workspace-level planning |
| `'task'` | Workspace layer + repo slice + story text + done_criteria |
| `'architect'` | Workspace layer + all-repos epic slice + story text |
| `None` (default) | Full workspace layer + full repo slice. For projects without `workspace_id` in `config.json` (pre-migration), falls back to the current file-based `generate_context()` path — backward compatible until `synlynk migrate` runs. |

---

## 8. Team Sync — Event-Log Sync via Shared Channel

### 8.1 Why export/import is retired

Manual export/import (the initial design) fails at agentic velocity. A daemon can complete 6 stories in 90 minutes. A team member importing every few hours sees a backend that no longer matches what they were integrating against — including constraints they never received.

The correct sync unit is the **event**, not the database. Events are append-only, signed, and small (~200–500 bytes each). Syncing events is conflict-free by design: events are immutable once written.

### 8.2 Event sync architecture

**Local:** state.db with events table (append-only, already in schema). Each event carries `machine_uuid`, `git_user`, and Ed25519 `sig`.

**Sync channel (pre-Tokq):** A bare git repo shared by the team (private GitHub repo, self-hosted, or local network). One branch per team member:

```
<workspace-sync-repo>/
  nikhil/events.ndjson    ← Nikhil's new events since last push
  gaurav/events.ndjson    ← Gaurav's new events since last push
  kunal/events.ndjson     ← Kunal's new events since last push
```

**Daemon sync loop (v0.7.0+, runs every 5 minutes):**

```
1. Write new local events → sync/nikhil/events.ndjson → git push
2. git pull → read gaurav/ and kunal/ branches
3. For each new event (ordered by ts):
   - Verify Ed25519 signature against known public key
   - Check last_event_id in sync_log (idempotency — skip already-applied events)
   - Apply event to local state.db (story status, memory, constraints, costs)
   - UPDATE sync_log SET last_event_id, last_synced
```

**Result:** Max drift ≈ 5 minutes. A constraint added at 09:14 is visible to all team members by 09:19, and auto-injected into their next agent context generation.

### 8.3 Conflict model

Events are append-only and never modified — no event conflicts exist. The only potential conflict is in materialized state: two members marking the same story as `in_progress` simultaneously.

**Resolution rules (applied at import time, no human needed):**
- `done` wins over `in_progress` wins over `claimed` wins over `pending`
- If both have `in_progress`: later timestamp wins; loser's story reverts to `pending` with a `conflict_resolved` event emitted
- Memory and constraints: later timestamp wins (last-write-wins per heading/dimension)
- Costs: additive, no conflict possible

Conflicts that require human judgement (rare, e.g. both members manually edited done_criteria) are surfaced via `synlynk workspace conflicts` and require explicit resolution before the next sync push.

### 8.4 Trust bootstrap for new team member

First sync from a new member (e.g. Gaurav) requires fingerprint confirmation:
```
New member "gaurav" (m2) detected in sync channel.
Public key fingerprint: ab:cd:ef:12:34
Confirm via out-of-band (Slack/email) and then: synlynk workspace trust gaurav ab:cd:ef:12:34
```

Subsequent syncs auto-verify against the stored public key. The `sync_log` table stores the trusted key per member.

### 8.5 Sync channel setup

```bash
# Create sync channel (one-time, workspace owner does this)
synlynk workspace sync init --channel git:github.com/nikhilsoman/my-product-sync

# Team members configure the same channel
synlynk workspace sync connect --channel git:github.com/nikhilsoman/my-product-sync

# Manual sync (before daemon is running)
synlynk workspace sync pull
synlynk workspace sync push

# Status
synlynk workspace sync status    # last sync time, events pending, member lag
```

---

## 9. Path to Tokq Alpha

The event sync design is a direct stepping stone to NATS:

| Aspect | Pre-Tokq (v0.7.0+) | Tokq Alpha |
|---|---|---|
| Event format | Identical (signed NDJSON) | Identical |
| Transport | git push/pull to shared repo | NATS publish/subscribe |
| Latency | ~5 minutes | < 1 second |
| Auth | Ed25519 + local trust store | Tokq cloud-verified keypair |
| ZK encryption | Not applied to sync channel | Events encrypted before NATS publish |
| Config | `sync_channel: "git:<url>"` | `sync_channel: "nats:<subject>"` |

The daemon sync loop is the same code. Only the I/O backend changes. Migration cost at Tokq Alpha: a config line update and a `synlynk tokq connect` call.

---

## 10. Roadmap Impact

| Milestone | What changes |
|---|---|
| **v0.4.0** | `synlynk init` creates workspace + machine-level identity + `repos` table. `config.json` gets `workspace_id` + `repo_id`. Solo devs see no difference. |
| **v0.5.0** | Full state.db schema with `repos` table, `repo_id` FKs on stories/events/costs. `generate_context()` reads workspace state.db. `synlynk migrate` handles path change (`projects/` → `workspaces/`). |
| **v0.6.0** | `synlynk workspace join`, multi-identity attribution (`git_user` tracked on all events), `synlynk team status`, `sync_log` table seeded. |
| **v0.7.0** | Daemon gains event sync loop (5-min cadence). `synlynk workspace sync init/connect/pull/push/status`. Export/import retired. |
| **v0.9.0** | Team safety (concurrent write model, multi-user entitlements) remains as planned. |
| **Note** | Gap 10 (Network Identity) is fully closed by this spec — machine-level keypair generated at v0.4.0. No v0.9.0 design work needed for identity. |
| **Tokq Alpha** | `sync_channel` config updated from `git:` to `nats:`. ZK encryption applied to events before publish. Machine keypairs registered with Tokq account. |

**Export/import (`synlynk workspace export/import`) is retired** — replaced by event sync at v0.7.0. No implementation needed.

**Gap 10 (Network Identity) is closed** by this spec. Removed from the gap list. No v0.9.0 design work needed for identity.

---

## 11. Out of Scope

- **Cross-machine workspace without sync channel** — two machines sharing a workspace requires the sync channel (v0.7.0). Pre-v0.7.0, each machine has its own workspace state. This is intentional: the daemon is the sync engine, and it ships at v0.7.0.
- **Workspace merging** — merging two workspaces into one is not supported. Arcs and Epics are workspace-scoped and cannot be moved between workspaces.
- **Per-repo entitlements** — entitlements are role-scoped, not repo-scoped. A Builder role's write access to `src/` applies across all repos. Per-repo entitlement overrides are deferred post-v1.0.
- **Public workspaces** — workspaces are private by default. Public or shared-read workspaces (for open-source teams) are a Tokq Marketplace concern, not a local synlynk concern.
