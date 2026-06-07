# synlynk: Agent Identity, Addressability, Dispatch & Entitlements — Design Spec

**Date:** 2026-06-07
**Status:** Approved — ready for implementation planning
**Author:** Nikhil Soman (brainstorm session with Claude)
**Depends on:** `docs/superpowers/specs/2026-06-07-synlynk-state-db-agentic-pm-design.md`
**Linked roadmap:** `docs/superpowers/specs/2026-06-06-synlynk-unified-roadmap.md`

---

## 1. Problem

Today every agent task requires a human to type a command to begin. Stories in state.db can be ready — dependencies satisfied, agent assigned, quota available — and they sit idle until someone opens a terminal. This is the last human bottleneck in an otherwise agentic build process.

---

## 2. Core Invariant

> A story that is ready, entitled, and has a capable agent available should dispatch automatically.
> Human intervention is reserved for approval gates, not routine task initiation.

---

## 3. Identity Model

Agent identity is two-layered. The layers answer different questions and never mix.

### 3.1 Local Identity — cryptographic anchor

Generated once at `synlynk init` (pulling forward from v0.9.0):

```
.synlynk/identity.json   — { agent_uuid, public_key (hex), fingerprint, created_at, git_user, git_email }
.synlynk/identity.key    — Ed25519 private key, chmod 600
```

Implementation: `ssh-keygen -t ed25519 -f .synlynk/identity.key -N ""` via subprocess. stdlib-safe.

Every dispatch event and completion event is signed with this key. Signature stored as `sig TEXT` on the event row. The audit trail is non-repudiable. At Tokq Alpha, the same signature verifies against the registered public key in the cloud.

### 3.2 Role — primary entitlement unit

Roles define **what work can be claimed and what it can touch**. Default roles:

| Role | Purpose |
|---|---|
| Architect | Designs, writes specs and plans. No src/ writes. |
| Builder | Implements. Writes src/, creates branches and PRs. |
| Verifier | Tests, audits. Reads all, writes reports, runs tests. |

Custom roles via `synlynk role add <name>`. A story's required role is set at epic creation (writing-plans output) and does not change.

### 3.3 Agent Profile — fitness function

Determines **who fills a role best right now**. One profile per CLI × environment:

| Field | Description |
|---|---|
| `agent` | `claude-code` · `claude-desktop` · `gemini-cli` · `codex` |
| `environment` | `cli` · `desktop` · `ci` |
| `model` | model identifier |
| `capabilities` | JSON array of native capability flags |
| `use_native_scheduling` | whether to delegate schedule triggers to agent |

Roles are stable. Agent profiles are dynamic — competency scores update after every execution, quota headroom changes hourly, capabilities update on probe.

### 3.4 Capability flags

Known flags seeded at `synlynk init`, updated by `synlynk profile probe <agent>`:

| Flag | Meaning |
|---|---|
| `bash` | Can execute shell commands |
| `git` | Has git integration |
| `gh` | Has GitHub CLI access |
| `edit` | Structured file edit tools available |
| `mcp` | Can connect to MCP servers |
| `hooks` | Supports pre/post tool hooks |
| `scheduling` | Has native scheduling (e.g. Claude Code `/schedule`) |
| `background` | Can run tasks persistently in background |
| `computer_use` | GUI automation (Claude Desktop) |
| `browser` | Browser automation |

---

## 4. Addressability

Addressability is separate from identity: identity is *who* the agent is, address is *where* work is sent to reach it. Two distinct channels serve different purposes.

### 4.1 Dispatch address — machine to agent

**Now (v0.5–v0.7): `inbox` table in state.db**

Each role has an inbox. The daemon writes `dispatch_request` rows; agent workers claim them.
Logical address: `synlynk://<project_id>/roles/<role>/inbox` → resolved to state.db row locally.

**v1.0+: NATS subject**

`synlynk.<project_id>.<role>` — same logical address, different transport. Cross-machine, cross-network. Tokq-aligned.

The inbox table row maps 1:1 to a future NATS message — the address scheme is forward-compatible.

### 4.2 Human-agent bridge — approvals and notifications

Email is the right channel for the human loop. Low-frequency, asynchronous, auditable, works across machines without any infrastructure.

Three events that reach the human via email:

| Event | Email content |
|---|---|
| `approval_requested` | Story details, estimated cost, affected paths. Reply: YES / HOLD / REASSIGN |
| `completed` | Story done, done_criteria met, next story queued |
| `escalation` | Story blocked for > N minutes, human review needed |

**v0.7.0:** Email notifications are send-only (SMTP). Human approves via `synlynk story approve <id>` CLI command as the initial mechanism — no email reply parsing needed. Email reply parsing (Gmail API webhook) is deferred to v0.8.0. The approval event and audit record are identical regardless of approval channel.

Email address configured at `synlynk init` from git user email. Override via `synlynk config set notification_email <addr>`.

---

## 5. Dispatch Architecture

### 5.1 Primary — persistent daemon (Mode A)

Watchman-style daemon (already designed in Trio Protocol spec). Unix domain socket, ~5MB resident. Watches state.db for stories with satisfied `depends_on`. Evaluates entitlements, selects best-fit agent profile, writes to `inbox`. Launched via `synlynk daemon start`.

### 5.2 Fallback — one-shot dispatch (Mode C)

`synlynk dispatch` — stateless, no persistent process. Evaluates state.db, fires N execs in parallel for N ready stories, waits for completion, exits. Universal fallback for any environment that blocks persistent processes (CI, sandboxed containers, cloud runners).

Called from any trigger: cron, git hook, CI step, manual.

### 5.3 Self-chaining — agent completion triggers next (Mode B)

When an agent completes a story (`status='done'`), synlynk re-evaluates what is now unblocked. If the daemon is running, it picks up immediately. If not, the completing agent calls `synlynk dispatch` before exiting. Self-chaining requires no separate mechanism — it emerges from the completion → re-evaluate loop.

### 5.4 Agent-native scheduling (Mode D)

When `agent_profiles.use_native_scheduling = true` AND the agent has the `scheduling` capability flag, synlynk delegates schedule triggers to the agent's native mechanism (e.g. Claude Code's `/schedule`). The inbox row includes the schedule expression; the agent manages its own firing. Completion signals back through the standard `status='done'` + event path.

### 5.5 Cron fallback for capability-limited agents (Mode C extended)

For agents with no scheduling capability, `synlynk dispatch` is the universal trigger:

```
*/5 * * * *   synlynk dispatch
```

One cron entry, not one per agent. synlynk evaluates all ready stories and fires N parallel execs. Per-role frequency tuning via multiple schedule entries with different `filter` values:

```
synlynk schedule add "builder-check"   --cron "*/5 * * * *"  --filter role=Builder
synlynk schedule add "architect-check" --cron "0 * * * *"    --filter role=Architect
```

### 5.6 Trigger source summary

| Mode | Trigger | Agent awareness needed | When to use |
|---|---|---|---|
| A | Daemon (persistent) | None | Dev machine, always-on server |
| B | Self-chain on completion | None | Always on alongside A or C |
| C | `synlynk dispatch` via cron/hook/CI | None | Universal fallback |
| D | Agent-native (`/schedule`) | `scheduling` capability | When available, preferred for fine-grained timing |

### 5.7 Full dispatch flow

```
TRIGGER (any of A/B/C/D)
  ↓
synlynk dispatch evaluates:
  SELECT stories WHERE status='pending' AND depends_on all done
  FOR each candidate:
    1. resolve role → check entitlements
    2. decision: auto | approval | hold | reject
    3a. auto:
        score agent_profiles (competency × capability × quota × cost)
        INSERT INTO inbox {role_id, story_id}
        INSERT INTO dispatch_log {decision='auto', routing_reason, sig=Ed25519}
    3b. approval:
        emit event type='approval_requested'
        send email → await reply → on YES → goto 3a
        INSERT INTO dispatch_log {decision='approval', approver, approved_at}
    3c. hold / reject:
        emit event type='blocked', block_reason='entitlement'|'quota'|'dependency'

agent worker (daemon-launched OR synlynk worker --role Builder):
  WATCH inbox WHERE role_id=my_role AND status='pending'
  claim row → run synlynk exec <agent> with story-scoped context
  on done → UPDATE stories status='done', actual_tokens=N
           → emit event type='completed', sig=Ed25519
           → synlynk dispatch re-evaluates (Mode B)
```

Each exec receives a **story-scoped context package** — the `scope='task'` path in `generate_context()` (currently stubbed). Only the story text, done_criteria, and a relevant memory/roadmap slice are injected. Not the full project context.

---

## 6. Entitlements

### 6.1 Two layers

**Authorization** — gate before dispatch. Checked by the daemon/coordinator before writing to inbox.

**Sandboxing** — constraints while running. Enforced by the synlynk exec wrapper.

### 6.2 Authorization dimensions

| Dimension | Description |
|---|---|
| `cost_ceiling` | Auto-dispatch if estimated cost below threshold; else approval |
| `path:<glob>` | Write access to path pattern (e.g. `path:src/`, `path:infra/`) |
| `git:<op>` | Git operation (branch, commit, push, pr, merge) |
| `novelty` | First execution in a domain requires approval |
| `competency_floor` | Agent score below threshold → hold for approval |

### 6.3 Sandboxing dimensions

| Dimension | Description |
|---|---|
| `token_ceiling` | Max tokens per story execution before escalation |
| `time_ceiling` | Max wall-clock duration before human check-in required |
| `network` | External API calls allowed / blocked |

### 6.4 Default role entitlement matrix

| Entitlement | Architect | Builder | Verifier |
|---|---|---|---|
| Write `src/` | ✗ | ✓ auto | ✗ |
| Write `docs/` · `specs/` | ✓ auto | ✓ auto | ✓ auto |
| Write `infra/` · `.github/` | ⚠ approval | ⚠ approval | ✗ |
| Create branch · commit · push | ✗ | ✓ auto | ✗ |
| Create PR | ✗ | ✓ auto | ✓ auto |
| Merge to main | ✗ | ⚠ approval | ⚠ approval |
| Run tests · shell commands | ✗ | ✓ auto | ✓ auto |
| Auto-dispatch if cost < $0.50 | ✓ | ✓ | ✓ |
| Token ceiling per story | 50K | 200K | 100K |

✓ auto = dispatches without approval · ⚠ approval = email sent, waits for reply · ✗ blocked

Merge to main is the one absolute — always approval-required, no threshold overrides it.

### 6.5 Entitlement management

```bash
synlynk entitle Builder write:src/ allow         # set dimension
synlynk entitle Builder cost_ceiling 1.00        # raise threshold
synlynk entitle Builder git:merge approval       # already default
synlynk entitle show Builder                     # display full matrix
```

Per-story override: a story can declare `required_approval: true` in its text or via `synlynk story require-approval <id>` regardless of role thresholds.

All entitlement checks and outcomes written to `events` table and `dispatch_log` — full audit trail.

---

## 7. Schema Additions to state.db

```sql
CREATE TABLE roles (
  id          INTEGER PRIMARY KEY,
  name        TEXT UNIQUE NOT NULL,  -- "Architect"|"Builder"|"Verifier"
  description TEXT,
  created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE agent_profiles (
  id                    INTEGER PRIMARY KEY,
  agent                 TEXT NOT NULL,        -- "claude-code"|"gemini-cli"|"codex"
  environment           TEXT NOT NULL,        -- "cli"|"desktop"|"ci"
  model                 TEXT,
  capabilities          TEXT DEFAULT '[]',    -- JSON array of capability flags
  use_native_scheduling BOOLEAN DEFAULT 0,
  active                BOOLEAN DEFAULT 1,
  updated_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(agent, environment)
);

CREATE TABLE entitlements (
  id        INTEGER PRIMARY KEY,
  role_id   INTEGER NOT NULL REFERENCES roles(id),
  dimension TEXT NOT NULL,   -- "write:src/"|"git:merge"|"cost_ceiling"|"token_ceiling"
  value     TEXT NOT NULL,   -- "allow"|"block"|"approval"
  threshold REAL,            -- for cost_ceiling / token_ceiling / competency_floor
  UNIQUE(role_id, dimension)
);

CREATE TABLE inbox (
  id          INTEGER PRIMARY KEY,
  role_id     INTEGER NOT NULL REFERENCES roles(id),
  story_id    INTEGER NOT NULL REFERENCES stories(id),
  status      TEXT NOT NULL DEFAULT 'pending',  -- pending|claimed|done
  claimed_by  INTEGER REFERENCES agent_profiles(id),
  created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  claimed_at  TIMESTAMP
);

CREATE TABLE schedules (
  id        INTEGER PRIMARY KEY,
  name      TEXT UNIQUE NOT NULL,
  cron_expr TEXT NOT NULL,           -- "*/5 * * * *"
  filter    TEXT,                    -- "role=Builder" | epic_id | story tag
  enabled   BOOLEAN DEFAULT 1,
  last_run  TIMESTAMP,
  next_run  TIMESTAMP
);

CREATE TABLE dispatch_log (
  id               INTEGER PRIMARY KEY,
  story_id         INTEGER REFERENCES stories(id),
  role_id          INTEGER REFERENCES roles(id),
  agent_profile_id INTEGER REFERENCES agent_profiles(id),
  decision         TEXT NOT NULL,    -- "auto"|"approval"|"hold"|"reject"
  routing_reason   TEXT,
  approver         TEXT,             -- git username if human-approved
  approved_at      TIMESTAMP,
  dispatched_at    TIMESTAMP,
  sig              TEXT              -- Ed25519 signature of dispatch record
);
```

**Additions to existing tables:**

`stories` gains: `role_id INTEGER REFERENCES roles(id)` — the role required for this story.

`events` gains: `sig TEXT` — Ed25519 signature on `completed`, `approval_granted`, `pivot`, `decision` event types.

---

## 8. New CLI Surface

```bash
# Identity
synlynk identity init              # generate Ed25519 keypair (auto on synlynk init)
synlynk identity show              # display public key + fingerprint
synlynk identity rotate            # new keypair, re-sign pending dispatch_log

# Profiles
synlynk profile probe <agent>      # discover + write capability flags
synlynk profile show               # display all agent profiles + capabilities
synlynk profile set <agent> <k=v>  # override a profile field

# Roles & entitlements
synlynk role add <name>            # create custom role
synlynk entitle <role> <dim> <val> # set entitlement dimension
synlynk entitle show <role>        # display full entitlement matrix

# Dispatch
synlynk daemon start               # launch persistent dispatcher
synlynk daemon stop / status
synlynk dispatch                   # one-shot dispatch — evaluates state.db, fires ready stories, exits
synlynk story approve <id>         # human approval via CLI (email reply parsing deferred to v0.8.0)
synlynk worker --role <role>       # agent worker loop (claim + exec + signal)

# Scheduling
synlynk schedule add <name> --cron <expr> [--filter <f>]
synlynk schedule list / remove / run <name>
```

---

## 9. Roadmap Alignment

| Version | What lands |
|---|---|
| v0.5.0 | `synlynk identity init` (Ed25519), `roles` + `agent_profiles` + `entitlements` tables seeded at init, `synlynk profile probe` |
| v0.6.0 | `inbox` table + `synlynk worker`, `dispatch_log`, authorization entitlement enforcement, `synlynk dispatch` |
| v0.7.0 | Persistent daemon (`synlynk daemon`), self-chaining (Mode B), email bridge for approvals, sandboxing enforcement |
| v0.8.0 | `synlynk schedule` (Mode C + D), agent-native scheduling delegation, story-scoped context (`scope='task'`) |
| v1.0.0 | Ed25519 signatures on all dispatch events, NATS subject replaces inbox as cross-machine dispatch address |
| Tokq Alpha | Signature verification against Tokq cloud-registered public key |

---

## 10. Out of Scope

- **Sandboxing enforcement mechanism** — the entitlement model defines what is sandboxed; enforcement (filesystem ACLs, seccomp, container boundaries) is platform-specific and deferred to v0.7.0 implementation.
- **Multi-project agent identity** — currently one keypair per project (`.synlynk/identity.key`). Machine-level identity spanning multiple projects is deferred to the Tokq identity layer (v1.0).
- **Agent-to-agent communication** — agents communicate through state.db (shared store), not directly. Direct agent messaging is a Tokq/NATS concern.
