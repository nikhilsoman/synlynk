# TPM Agent Design Spec

**Date:** 2026-06-23
**Status:** Approved for implementation
**Target release:** v0.8.2 (part of Agent Ecosystem Epic v0.8.1–v0.8.4)

---

## Agent Design Principles

These principles apply to the TPM agent and every agent built in this ecosystem:

**1. Opt-in at init / re-configurable.** `synlynk init` asks once whether to enable agents. `synlynk config --agents` toggles the setting at any time. A single `agents_enabled` flag in `.synlynk/config.json` gates all agent commands. No silent activation.

**2. Nothing breaks without agents.** The core synlynk workflow — `exec`, `checkpoint`, `story`, `team status`, `decide` — is fully functional with agents disabled. Agent commands (`tpm`, `release`) return a clear "agents not enabled — run `synlynk config --agents` to enable" message and exit 0. Agents are an accelerator layer, not a dependency of the base tool.

**3. Agents must earn their place.** After every wave, the TPM prints an ROI summary: tokens used, wall-clock time, and estimated manual equivalent. If an agent repeatedly underperforms (high block rate, high cost per task), `tpm status` surfaces this. The capability matrix self-corrects agent assignments over time. Autonomy is only beneficial if it demonstrably saves time and cost.

---

## Problem

Dispatching agents across a multi-task plan requires manual coordination: choosing which agent per task, grouping tasks into parallel waves, creating worktrees, monitoring completion, and managing merge order. This is repetitive, error-prone, and blocks the human from doing higher-value work. Additionally, when multiple stories are in flight simultaneously, there is no cross-story view and no ability to batch tasks from different stories into a shared wave.

## Goal

A config-driven TPM agent that:
- Is the lifecycle runner for per-story software development workflows
- Reads implementation plans and autonomously assembles wave groups from dependency graphs
- Assigns agents per task using a self-improving capability matrix
- Surfaces cross-story batching opportunities before dispatch
- Executes with per-task consent control (auto / notify / approve)
- Is fully configurable at the repo level without code changes

---

## Architecture

Three concerns with clean boundaries:

```
Lifecycle Engine     →   Wave Planner         →   Dispatcher
────────────────────     ────────────────────     ────────────────────────────
Tracks per-story         Reads plan file,          Dispatches agents per task,
stage in state.db.       builds dependency          monitors completion, manages
Detects new plans.       graph, groups tasks        merge order, advances lifecycle
Handles advance          into waves, assigns        stage when wave completes.
triggers (auto /         agents via capability
approve).                matrix.
```

**Lifecycle-as-first-class-entity:** Every story has a lifecycle instance in `state.db`. The TPM is the engine that moves stories through lifecycle stages. Advance triggers are per-stage: `auto` (on file appearance, exit code, or DB state) or `approve` (human calls `synlynk tpm advance`).

**Config-as-SOP:** `project-docs/tpm-agent.json` defines lifecycle types, dispatch rules, agent limits, and budget caps. Versioned with the repo, editable without touching code.

**Self-improving capability matrix:** After each task, TPM writes a row to `capability_ratings`. Future assignments read learned ratings first, fall back to `AGENT_CAPABILITY_BASELINES`.

---

## Command Surface

```
synlynk tpm suggest                  # scan for new plans, surface dispatch proposal (also cron)
synlynk tpm dispatch                 # execute current proposal
synlynk tpm dispatch --story <id>    # dispatch a single story
synlynk tpm status                   # board view: all stories + lifecycle stages
synlynk tpm advance  --story <id>    # manually advance story past an approve-gated stage
synlynk tpm pause    --story <id>    # halt in-flight dispatch for a story
synlynk tpm --install-cron           # register cron job via existing _install_cron_entry()
```

---

## Lifecycle Type Schema

Lifecycle types are defined in `project-docs/tpm-agent.json` under `lifecycle_types`. Two built-in types ship with `synlynk init`.

**Type: `software-development`**

| Stage | artifact_out | agent_roles | advance |
|---|---|---|---|
| brainstorm | session_transcript | architect | manual (approve) |
| spec | spec_doc | architect, reviewer | on_file: docs/superpowers/specs/*.md |
| plan | plan_doc | architect, tpm | on_file: docs/superpowers/plans/*.md |
| execution | branches, PRs | tpm, codex, claude, agy | on_db: tasks.status=all_done |
| review | merged_commit | tpm, reviewer | on_exit_0 (tests pass) |

**Type: `release`**

Defined by `project-docs/release-agent.json` (existing). TPM recognises it as a lifecycle type and can show it on the board alongside software-development stories.

---

## Config Schema

**Path:** `project-docs/tpm-agent.json`

```json
{
  "tpm_agent": {
    "cron": "0 9 * * 1-5",
    "default_consent": "approve",
    "aggregation_consent": "approve",
    "lifecycle_types": ["software-development", "release"],
    "dispatch_rules": [
      { "if": "task.complexity == 'exploratory'", "assign": "claude" },
      { "if": "task.complexity == 'targeted'",    "assign": "codex"  },
      { "if": "task.complexity == 'scaffold'",    "assign": "agy"    }
    ],
    "capability_overrides": {
      "claude": { "max_parallel": 2 },
      "codex":  { "max_parallel": 4 },
      "agy":    { "max_parallel": 3 }
    },
    "budget": {
      "per_wave_usd": 2.00,
      "per_story_usd": 8.00
    }
  }
}
```

### Field reference

| Field | Description |
|---|---|
| `cron` | Schedule for `tpm suggest` cron job |
| `default_consent` | Consent for each dispatch action: auto / notify / approve |
| `aggregation_consent` | Consent for cross-story batching suggestions |
| `dispatch_rules` | Ordered list of `if/assign` rules. First match wins. Falls back to capability matrix. |
| `capability_overrides` | Max parallel slots per agent |
| `budget.per_wave_usd` | Estimated cost threshold before TPM requires explicit approval |
| `budget.per_story_usd` | Total budget cap per story; TPM halts when exceeded |

---

## Database Schema

Two new tables in `~/.synlynk/projects/<project-id>/state.db`.

### `lifecycle_instances`

```sql
CREATE TABLE lifecycle_instances (
    story_id     TEXT NOT NULL REFERENCES stories(story_id),
    lifecycle_id TEXT NOT NULL DEFAULT 'software-development',
    stage        TEXT NOT NULL DEFAULT 'brainstorm',
    advanced_at  TEXT,
    artifact_ref TEXT,
    PRIMARY KEY (story_id)
);
```

### `tasks`

```sql
CREATE TABLE tasks (
    task_id      TEXT PRIMARY KEY,   -- e.g. "S4-T2"
    story_id     TEXT NOT NULL REFERENCES stories(story_id),
    plan_file    TEXT NOT NULL,
    title        TEXT NOT NULL,
    complexity   TEXT,               -- exploratory | targeted | scaffold
    agent        TEXT,               -- assigned agent
    wave         INTEGER NOT NULL DEFAULT 1,
    depends_on   TEXT NOT NULL DEFAULT '[]',  -- JSON array of task_ids
    status       TEXT NOT NULL DEFAULT 'pending',
    branch       TEXT,
    worktree_path TEXT,
    started_at   TEXT,
    completed_at TEXT,
    exit_code    INTEGER,
    tokens_used  INTEGER
);
```

Migration: `ALTER TABLE` additions to `_migrate_db()`, same pattern as existing migrations.

---

## TPM Flow

### 1. Detect

`cmd_tpm_suggest()` scans `docs/superpowers/plans/*.md` for files newer than the last-seen timestamp stored in `.synlynk/tpm-state.json`. Also checks `lifecycle_instances` for stories with `stage='plan'` that have no tasks yet (manual seeds — stories added directly to state.db without going through the Architect pipeline).

If nothing new: exits silently (cron mode) or prints "No new plans" (interactive).

### 2. Parse + Wave Assembly

For each new plan file:
- Extract `### Task N: <title>` blocks using regex
- Parse `depends_on:` field from task block if present; otherwise infer sequential dependency from ordering
- Build DAG; topological sort → assign wave numbers (1-indexed)
- Extract `complexity:` field from task block (exploratory / targeted / scaffold) if present; otherwise default to `targeted`
- Insert rows into `tasks` table with `status='pending'`

### 3. Agent Assignment

For each task, evaluate `dispatch_rules` top-to-bottom. First matching rule assigns the agent.

If no rule matches:
1. Query `capability_ratings` for average success rate per agent for this complexity type (last 20 entries)
2. Weight by inverse cost tier (prefer cheaper agents at equal competence)
3. Check `max_parallel` — don't assign if agent already has that many running tasks
4. Assign highest-weighted available agent

### 4. Aggregation Check

After assembling all wave plans, scan `lifecycle_instances` for other stories at `stage='execution'` with pending Wave 1 tasks. If 2+ stories qualify and their Wave 1 task sets have no cross-story `depends_on` entries, surface an aggregation suggestion.

Aggregation suggestion format (printed to terminal):
```
TPM: S1 and S3 are both at Execution with ready Wave 1 tasks.
     Combined: 6 agents, estimated ~$0.42.
     [A] Approve combined wave  [S] Run separately  [K] Skip
```

Consent level set by `aggregation_consent` in config. In cron mode with `approve` consent: writes pending notice to `sentinel.md`.

### 5. Present + Approve

Print wave plan table:

```
Story S4 — Lifecycle engine (Plan stage)
Wave 1 (parallel):  T1 → codex   T2 → codex   T3 → claude
Wave 2 (after W1):  T4 → codex
Estimated cost: ~$0.31   [y/N]
```

In `approve` consent mode: block on prompt. In `auto`: proceed immediately. In `notify`: proceed and log to sentinel.

If estimated cost exceeds `per_wave_usd`: always require explicit approval regardless of consent setting.

### 6. Dispatch

For each wave:
1. For each task in wave (parallel):
   - Create worktree: `git worktree add .worktrees/<story-id>-<task-id> -b <branch-name>`
   - Update `tasks.status = 'running'`, `tasks.started_at`
   - Call `_run_agent_sync(agent, prompt, timeout=300)` with task-specific prompt built from plan block
   - On completion: update `tasks.status`, `tasks.exit_code`, `tasks.tokens_used`, `tasks.completed_at`
   - Write to `capability_ratings`
2. Wait for all tasks in wave to complete
3. If any task has `exit_code != 0`: set `tasks.status = 'blocked'`, write to `sentinel.md`, pause story

### 7. ROI Summary

After every wave completes, print:

```
Wave 1 done — 3 tasks (T1 codex, T2 codex, T3 claude)
  Time:    8 min 22 sec
  Tokens:  ~43K (estimated $0.38)
  Manual equivalent: ~90 min (based on avg task duration in capability_ratings)
```

Manual equivalent is estimated as: `sum(avg_manual_duration_per_complexity_type * task_count)`. Defaults: exploratory=45min, targeted=20min, scaffold=10min. These defaults are configurable in `tpm-agent.json` under `manual_time_estimates`.

### 8. Lifecycle Stage Advance

When all tasks across all waves complete with exit code 0:
- Check `lifecycle_instances.stage` advance trigger
- If `auto` (on_db: tasks.status=all_done): update `lifecycle_instances.stage` to next stage, set `advanced_at`, set `artifact_ref` to last merged branch/SHA
- If `approve`: write pending advance notice to `sentinel.md`; human calls `synlynk tpm advance --story <id>` to proceed

---

## Capability Matrix

### Baselines (read from `AGENT_CAPABILITY_BASELINES` in `__init__.py`)

```python
AGENT_CAPABILITY_BASELINES = {
    "claude": {"cli": "claude", "non_interactive_flags": ["--print", "--yes"],
               "prompt_via_arg": True, "complexity_strength": ["exploratory"]},
    "codex":  {"cli": "codex",  "non_interactive_flags": ["--non-interactive"],
               "prompt_via_arg": True, "complexity_strength": ["targeted", "scaffold"]},
    "agy":    {"cli": "agy",    "non_interactive_flags": ["--yes"],
               "prompt_via_arg": False, "complexity_strength": ["scaffold"]},
}
```

### Learned ratings (from `capability_ratings` table)

After each task completion, TPM inserts:
```python
_sign_capability_rating(agent, story_id, task_id, complexity, exit_code, duration_s, tokens_used)
```

Assignment scoring query (simplified):
```sql
SELECT agent,
       AVG(CASE WHEN exit_code = 0 THEN 1.0 ELSE 0.0 END) as success_rate
FROM capability_ratings
WHERE complexity = ?
GROUP BY agent
ORDER BY success_rate DESC
LIMIT 1
```

---

## Failure Handling

| Failure type | TPM action |
|---|---|
| Task exit code != 0 | Set task `status='blocked'`, write sentinel notice, pause story wave |
| Cost exceeds `per_wave_usd` | Require explicit approval before proceeding |
| Cost exceeds `per_story_usd` | Halt story, write sentinel, require human override |
| Agent unavailable (CLI not found) | Skip assignment, surface in `tpm suggest` output, require manual assignment |
| Worktree creation fails | Retry once; on second failure, mark task blocked |

Human resolves blockers via:
- `synlynk tpm dispatch --story <id>` to re-attempt a blocked task (possibly with different agent)
- Direct edit to task in `tasks` table and re-run dispatch

---

## Cron Integration

`synlynk tpm --install-cron` registers via `_install_cron_entry()`. The cron job calls `synlynk tpm suggest`, which:

1. Runs detection
2. If nothing new and no in-flight stories with pending approval: exits silently
3. If new plan found: assembles wave plan, writes to `.synlynk/tpm-state.json`, appends suggestion to `sentinel.md`
4. If in-flight story with `approve`-gated wave: re-emits pending notice to `sentinel.md` (idempotent)

---

## Files Changed

| File | Change |
|---|---|
| `synlynk/__init__.py` | `_migrate_db()` additions; `_tpm_parse_plan()`, `_tpm_assign_agent()`, `_tpm_assemble_waves()`, `_tpm_check_aggregation()`, `_tpm_dispatch_wave()`, `_tpm_advance_lifecycle()`, `cmd_tpm_suggest()`, `cmd_tpm_dispatch()`, `cmd_tpm_status()`, `cmd_tpm_advance()`, `cmd_tpm_pause()`; argparse `tpm` subcommand with sub-actions |
| `tests/test_synlynk.py` | Tests for all TPM functions |
| `project-docs/tpm-agent.json` | Default TPM config (created by `synlynk init` when agents enabled) |
| `.synlynk/config.json` | Add `agents_enabled` boolean field; `synlynk init` sets it; `synlynk config --agents` toggles |

---

## What Is Not In Scope (v0.9.4)

- **Architect agent** — brainstorm/spec writing is still human + Claude session. TPM only consumes the plan artifact.
- **Automated PR creation** — TPM dispatches agents and monitors branches. Opening PRs is a future step.
- **Cross-project lifecycle** — single repo only.
- **Real-time streaming** — dispatch is fire-and-wait via `_run_agent_sync()`. Live output streaming is a future enhancement.
- **UI / TUI board** — `tpm status` is terminal text output only.
