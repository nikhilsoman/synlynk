# BS-12: Agent Autonomy Bridge
## Design Spec

**Date:** 2026-07-05
**Session:** BS-12 (Nikhil + Claude)
**Status:** Approved — ready for implementation plan
**Epic:** BS-12
**Target:** v0.11.0

---

## Problem Statement

synlynk dispatches agents but cannot yet control what they're allowed to do, adjust their runtime configuration per-project, recover gracefully when they fail, guide users through fixing health check failures, or guarantee that agents have internalized the workflow discipline SOPs needed to operate autonomously.

Five gaps, all in the same trust boundary: synlynk tells agents what to do, but not how they're allowed to do it, what to do when they can't, or how to behave in the absence of explicit instruction.

---

## Scope

### A — Permission Grants

Role entries in `.synlynk/config.json` carry a default permission set. Each role maps to a named capability tier:

| Role | Default permissions |
|:---|:---|
| `pm`, `review`, `deploy` | `read:*` |
| `implement`, `test`, `refactor` | `read:*, write:src/, run:tests` |
| `css`, `templates`, `content` | `read:*, write:src/, write:docs/` |
| `canvas`, `js`, `infra` | `read:*, write:src/, run:shell` |

Stored under a new `permissions` key in `.agents/<agent>.json`. Individual dispatches override with `--grant <perm>` / `--revoke <perm>`. `dispatch_agent()` resolves the final set at call time: role default → `.agents` override → per-call flags.

The resolved permission set is translated into per-agent dispatch flags:
- Claude: `--allowedTools` list
- Codex: `--ask-for-approval` (untrusted / on-request / never)
- Agy: included in task context header as a `## Permissions` section (no CLI flag available)

### B — Harness Config

`AGENT_CAPABILITY_BASELINES` in `__init__.py` is currently hardcoded. BS-12 makes it overridable per-project without touching the source file.

New subcommand: `synlynk configure agent <name> [--flag <key>=<val>] [--env <KEY>=<VAL>] [--network-dep <host:port>]`

Writes to `.agents/<agent>.json` under a new `harness_overrides` key. `dispatch_agent()` merges at call time: baseline → `.agents/harness_overrides` → per-call `--grant`/`--revoke`. `synlynk doctor` TC-2 reads the merged config rather than the hardcoded baseline.

### C — Handoff Protocol

When a running job accumulates a `STALL_NO_OUTPUT`, `FLATLINE`, or `QUOTA_EXHAUSTED` sentinel, synlynk writes a `HANDOFF_PENDING` sentinel and surfaces the job in `synlynk jobs --stalled`.

The stalled job view shows:
- Job ID, agent, failure sentinel, elapsed time
- Recommended next agent (derived from capability matrix: highest cycle-coverage for the job's task type, excluding the failed agent)

User confirms transfer: `synlynk jobs handoff <job_id> [--to <agent>]`

On handoff:
1. Job context file (`.synlynk/contexts/<job_id>.md`) gets a `## Handoff Note` appended with failure reason + previous agent
2. `jobs.handoff_count` incremented, `jobs.previous_agents` (JSON array) updated
3. New dispatch launched with same context file + updated agent
4. `HANDOFF_PENDING` sentinel cleared

**Schema additions:**
```sql
ALTER TABLE jobs ADD COLUMN handoff_count INTEGER DEFAULT 0;
ALTER TABLE jobs ADD COLUMN previous_agents TEXT;  -- JSON array
```

### D — Doctor Guided Fix Wizard + Escalate

After `synlynk doctor` runs each TC check, failures enter an interactive fix loop rather than just printing and exiting.

**Structured paths (known failures):**

| TC | Failure | Fix menu option |
|:---|:---|:---|
| TC-1 | Requires PTY | Show PTY workaround for this agent + offer to write config note |
| TC-2 | Bad flags | Offer to apply recommended flags to `.agents/<agent>.json` |
| TC-3 | Network unreachable | Show endpoint list, offer to skip agent or configure proxy |
| TC-4 | Missing verbs | Offer to run `synlynk configure agent <name>` to add them |
| TC-5 | Missing SOP sections | Offer to run `synlynk sync --repair-sops` |

**Escalation path ("I'm stuck"):**
Always available as the last menu option. Assembles a failure context string from TC results + agent config + last 5 telemetry rows, then calls `dispatch_agent("claude", task=<context>)` with the failure pre-loaded. The user stays in their terminal; the Claude session handles the diagnosis conversationally.

The wizard uses the existing `termios`-based TUI pattern from `cmd_wizard`. No new TUI primitives needed.

### E — Agent SOP Codification

Six new SOP string constants added to `__init__.py` and written into all four directive files (CLAUDE.md, GEMINI.md, GROK.md, AGENTS.md) at `synlynk init` and `synlynk sync` time.

**New SOP blocks:**

| Constant | Section header | Content |
|:---|:---|:---|
| `_pr_review_sop` | `## PR Review Discipline` | Non-authoring agent reviews and merges. Authoring agent never self-merges. |
| `_brainstorm_sop` | `## Brainstorm-First Policy` | Every feature and epic requires a brainstorm session before implementation. No code before design approval. |
| `_design_sequence_sop` | `## Design → Plan → Build Sequence` | Design spec → implementation plan → capability-allocated tasks. No skipping steps. |
| `_capability_allocation_sop` | `## Capability-Based Task Allocation` | Tasks routed by agent role and cycle-capability matrix. Never self-assign outside your role. |
| `_cost_visibility_sop` | `## Cost Visibility` | Log cost estimate before each dispatch. Flag if estimated cost exceeds session budget. |
| `_repo_hygiene_sop` | `## Repo Hygiene` | No direct commits to main. Branch naming convention. Commit trailers required. Worktree per feature. |

**TC-5 in `cmd_doctor`:** After TC-4, scan each directive file for the presence of all six section headers. Warn (not fail) if any are missing. Reports which sections are absent per file.

**`synlynk sync --repair-sops`:** Calls `_upsert_harness_fence` for each missing SOP section. Preserves existing user content; only injects absent sections.

---

## Data Model Summary

**`.agents/<agent>.json` — new keys:**
```json
{
  "harness_overrides": {
    "dispatch_flags": {},
    "env": {},
    "network_deps": []
  },
  "permissions": {
    "defaults": ["read:*", "write:src/", "run:tests"],
    "grants": [],
    "revokes": []
  }
}
```

**`jobs` table — new columns:**
```sql
handoff_count    INTEGER DEFAULT 0
previous_agents  TEXT              -- JSON array of agent names
```

**New sentinel value:** `HANDOFF_PENDING`

---

## New CLI Surface

| Command | Description |
|:---|:---|
| `synlynk configure agent <name> [--flag k=v] [--env K=V] [--network-dep host:port]` | Write per-project harness overrides |
| `synlynk dispatch <agent> --grant <perm> --revoke <perm>` | Per-task permission override |
| `synlynk jobs --stalled` | List jobs with HANDOFF_PENDING sentinel |
| `synlynk jobs handoff <job_id> [--to <agent>]` | Confirm agent handoff |
| `synlynk sync --repair-sops` | Re-inject missing SOP sections into directive files |

Doctor gains: TC-5 (SOP presence check), interactive fix wizard after each TC failure.

---

## Delivery Phases

| Phase | Scope | Owner | Unblocked? |
|:---|:---|:---|:---|
| P1-code | E: TC-5 + `sync --repair-sops` plumbing | Codex | ✅ |
| P1-content | E: 6 SOP block strings | Agy | ✅ |
| P2 | B: `configure agent` CLI + dispatch merge | Codex | after P1 |
| P3 | A: role permission defaults + `--grant`/`--revoke` | Codex | after P2 |
| P4 | C: `HANDOFF_PENDING` + `jobs --stalled` + `jobs handoff` | Codex | after P3 |
| P5a | D: doctor guided wizard Python TUI | Codex | after P4 |
| P5b | D: wizard menu text + escalation prompt template | Agy | after P4 |
| BS-22 | Vizor Efficiency enrichment (independent) | Agy | ✅ |

P1-code and P1-content run in parallel. P5a and P5b run in parallel; Codex uses Agy's strings as constants.

---

## Key Design Constraints

- All logic stays in `synlynk/__init__.py` until `chore/modularise-init` ships. No new top-level modules for BS-12.
- The permission translation layer (role → CLI flags) lives in a single `_resolve_dispatch_permissions(agent, grants, revokes)` function — one place to update when agent CLIs change.
- TC-5 is a **warn**, not a **fail** — missing SOPs don't block dispatch. This matches the non-blocking philosophy of the existing status system.
- Handoff only triggers on explicit sentinel patterns — never on exit code alone.
- `synlynk sync --repair-sops` is idempotent. Running it twice produces no change on the second run.
