# Context-mode telemetry + Architect as context provider

**Status:** telemetry portion shipping; Architect provider is design-forward  
**Date:** 2026-08-09  
**Related:** right-sizing context is a core synlynk value prop

## Problem

Dispatch supports `--context-mode {none,task,full}` (default `task`), but we never persisted mode or payload size. Platform ops could not answer: *what % of jobs get task vs full context?* Without that, we cannot refine sizing policy or prove the product benefit.

## What ships now (instrumentation)

| Field | Where | Meaning |
|-------|--------|---------|
| `context_mode` | `daemon_jobs`, `cost_entries` (inherited), `jobs.json` job dict, telemetry event | `none` \| `task` \| `full` |
| `context_bytes` | `daemon_jobs`, job dict, telemetry | UTF-8 bytes of injected context **after** profile truncation |

`ops report` L1/L2 surfaces:

- `by_context_mode` counts + `%`
- `context_bytes` summary (n, min, p50, p90, max, mean)
- cost `by_context_mode` (usd / tokens / n)

Legacy rows without columns report as `unknown` until new dispatches fill the ledger.

## What we need after ~1 week of telemetry

1. **Baseline report:** % task/full/none by agent, by status (done vs failed), by cost.
2. **Mis-size hypotheses:** e.g. full on mechanical tasks; task on architecture work that thrash-reads.
3. **Instruction experiments:** change workspace agent prompts / default mode matrix and measure shift in success + cost.

## Future: Architect Workspace Agent as configurable context provider

**Agree** — Architect is the right long-term owner of *what* goes into context, not only *which bucket* (`task`/`full`).

Today:

```
dispatch → generate_context(scope=task|full) → static project-docs + DB snapshot
```

Target:

```
dispatch → context_provider (configurable) → Architect flow (or static fallback)
                ↓
         context_mode + context_bytes + provider_id + recipe_version
```

### Config surface (proposal)

```jsonc
// .synlynk/config.json (sketch)
{
  "context_provider": {
    "engine": "static" | "architect",   // static = today's generate_context
    "architect": {
      "agent": "architect",             // or role name
      "recipe": "default" | "path/to/recipe.json",
      "max_bytes": 80000,
      "timeout_s": 30,
      "fallback": "static"              // on provider failure
    },
    "mode_policy": {
      // optional auto-mode later
      "default": "task",
      "rules": [
        {"when": "task_matches:architecture|design", "mode": "full"},
        {"when": "template:lifecycle-setup", "mode": "task"}
      ]
    }
  }
}
```

### Pass-through “agent flow” requirements

| Need | Why |
|------|-----|
| **Provider interface** | `build_context(job) -> ContextBundle{text, mode, bytes, provenance}` |
| **Recipe / skill pack** | Architect instructions: what to include (roadmap slice, deps graph, open decisions) per job class |
| **Deterministic cache** | Same task+repo fingerprint → same context unless recipe version bumps |
| **Budget guards** | max_bytes, max tokens, timeout; always fall back to static |
| **Telemetry** | store `context_provider`, `recipe_version`, `mode`, `bytes` (this PR is the mode/bytes spine) |
| **Eval harness** | A/B: static task vs Architect-built context on fixed task set; score completion + rework + cost |

### Why Architect (not Support / generic Claude)

- **Role fit:** Architect already sits on “what is the system / what matters for this change.”
- **Stable charter:** Support is reactive (LIVE/sentinel); Architect is structural.
- **Composable:** can later call sub-tools (map, goals, open PRs) without bloating every dispatch path.

### Non-goals (near term)

- Replacing `--context-mode` flags (keep operator override)
- Online RAG over whole git history without budgets
- Requiring network for every dispatch

## Acceptance for telemetry PR

- [x] New dispatches persist `context_mode` + `context_bytes`
- [x] Cost rows inherit mode from job when possible
- [x] `ops report` shows mode mix + byte summary
- [x] Tests for persist, cost inherit, report format

## Next tickets (suggested)

1. This PR — instrumentation  
2. Issue: Architect context provider interface + static fallback  
3. After 7d data — mode policy v0 (rules + defaults) informed by ops rollup  
