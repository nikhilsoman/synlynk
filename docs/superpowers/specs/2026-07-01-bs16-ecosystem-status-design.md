# BS-16: Ecosystem Status + Capacity
## Design Spec

**Date:** 2026-07-01
**Session:** BS-16 (Nikhil + Claude)
**Status:** Approved — ready for implementation plan
**Epic:** BS-16 (new)
**Target:** v0.10.0 (status command + agent cards + cycle matrix); HUD visual = post-v0.10.0

---

## Problem Statement

synlynk wraps independently-evolving AI CLIs from different vendors. At any point in time, some agents are fully functional, some are degraded, some have variable limits based on plan, region, and traffic. There is currently no single surface that tells the user:

- Which agents are attached and reachable right now?
- What can each agent do in synlynk's 6-cycle model?
- What are the actual token budgets available per agent (read / write / tool calls) — and does the current task fit?
- How efficiently is synlynk using the fleet (headless vs. interactive)?

The goal is not a pass/fail quality gate. It is a **capability availability report** — showing the true state of the ecosystem at a point in time, acknowledging that ephemeral degradation is expected for a polyglot aggregator. As long as no agent actively blocks synlynk, some subset of the fleet always delivers value.

---

## Philosophy

synlynk is a coordination layer over agents it does not control. The status system reflects this:

- **No thresholds or minimum bars.** There is no "below this score, the agent is unsupported." All attached agents contribute capability; partially functional agents are shown accurately, not hidden.
- **Separation of status from quality gates.** `synlynk probe` refreshes the status snapshot. `synlynk doctor` enforces compliance. `synlynk status` only reads — it never blocks.
- **Headless efficiency is a first-class metric.** Each headless dispatch starts with a clean context. No conversation history accumulates. This is the primary reason synlynk users get more done per token than interactive users. The status surface makes this visible and quantified.

---

## Two Roles Per Agent

Each agent in the fleet operates in two distinct contexts, scored independently:

| Role | Description | Measured by |
|---|---|---|
| **Agent** (dispatch target) | Controlled externally by synlynk. Receives tasks, produces output. | Attach rate, instruction adherence, completion reliability, output velocity |
| **Harness** (user's home) | The environment synlynk runs inside. Provides the entry point for dispatch. | Context injection reach, dispatch subprocess access, verb surface reachable from here |

Claude is the reference harness — all agent scores are expressed relative to Claude's behaviour as the implementation baseline.

---

## 6-Cycle Capability Model

synlynk's capability surface maps to 6 development cycles. Each agent is scored per cycle:

| Cycle | synlynk verbs | Commands / flags |
|---|---|---|
| 💡 Dream | `decide`, brainstorm dispatch | `synlynk decide`, dispatch to agent with spec task |
| 📋 Plan | `story`, `epic`, roadmap | `synlynk story create/update`, `synlynk epic` |
| ⚙️ Work | `dispatch.*`, `jobs` | `dispatch.task`, `dispatch.headless`, `dispatch.resume`, `dispatch.approve`, `dispatch.model`, `dispatch.context`, `synlynk jobs` |
| 🚀 Ship | `release`, changelog | `synlynk release`, VERSION bump, CHANGELOG, blog stub |
| 🔧 Maintain | `probe`, `doctor`, `repair`, `exit`, `sync`, `status` | `synlynk probe`, `synlynk doctor` TC-1–4, `synlynk repair`, `synlynk sync` |
| 🤝 Engage | `join`, `relay`, `workspace`, `upgrade` | `synlynk join`, `synlynk relay`, `synlynk upgrade` |

Each cycle × agent cell scores as: `full` / `partial` / `none`, derived from `harness_verb_map` rows.

**Current cycle capability baseline (from verb_map):**

| Cycle | claude | agy | codex | grok |
|---|---|---|---|---|
| Dream | full | partial (loop risk) | none | none |
| Plan | full | none | none | none |
| Work | full | partial (headless ~) | full (resume ✗) | partial (network dep) |
| Ship | full | none | none | none |
| Maintain | full | partial (probe ✓, doctor ~) | partial (probe ✓) | partial (probe ✓) |
| Engage | full | none | partial (upgrade only) | partial (upgrade only) |

This table is seeded from `harness_verb_map` at `synlynk probe` time and refreshed when verb_map or probe results change.

---

## Data Architecture

### New table: `harness_status`

```sql
CREATE TABLE IF NOT EXISTS harness_status (
    agent_name             TEXT PRIMARY KEY,
    attach_rate_24h        REAL DEFAULT 0.0,   -- telemetry: successful/attempts last 24h
    attach_point_in_time   INTEGER DEFAULT 0,  -- probe: 1=up, 0=down
    adherence_score        REAL DEFAULT NULL,  -- telemetry proxy (NULL until data accumulates)
    completion_rate_24h    REAL DEFAULT NULL,  -- telemetry: clean_exit/total last 24h
    rescue_count_24h       INTEGER DEFAULT 0,  -- telemetry: jobs picked up by another agent
    output_velocity_p50    REAL DEFAULT NULL,  -- telemetry: bytes/min median
    installed_version      TEXT DEFAULT '',
    latest_version         TEXT DEFAULT NULL,  -- best-effort; NULL if unreachable
    plan_tier              TEXT DEFAULT 'unknown',  -- free/pro/max/enterprise/unknown
    plan_type              TEXT DEFAULT 'd2c',      -- d2c/bulk/api
    ctx_window_tokens      INTEGER DEFAULT NULL,
    read_budget_tokens     INTEGER DEFAULT NULL,    -- input available for prompt+context
    write_budget_tokens    INTEGER DEFAULT NULL,    -- output generation limit
    tool_budget_count      INTEGER DEFAULT NULL,    -- estimated tool calls per dispatch
    tc1_status             TEXT DEFAULT 'unknown',  -- pass/fail/unknown
    tc2_status             TEXT DEFAULT 'unknown',
    tc3_status             TEXT DEFAULT 'unknown',
    tc4_status             TEXT DEFAULT 'unknown',
    harness_compat_score   REAL DEFAULT NULL,       -- verb_map baseline + telemetry blend
    last_probe_at          TEXT DEFAULT NULL,
    last_telemetry_at      TEXT DEFAULT NULL
);
```

### New table: `cycle_capability`

```sql
CREATE TABLE IF NOT EXISTS cycle_capability (
    agent_name   TEXT NOT NULL,
    cycle        TEXT NOT NULL,   -- dream/plan/work/ship/maintain/engage
    support      TEXT NOT NULL,   -- full/partial/none
    notes        TEXT,
    verb_count   INTEGER DEFAULT 0,  -- total verbs in this cycle for this agent
    full_count   INTEGER DEFAULT 0,  -- verbs with support=full
    partial_count INTEGER DEFAULT 0,
    updated_at   TEXT NOT NULL,
    PRIMARY KEY (agent_name, cycle)
);
```

Populated by `_compute_cycle_capability(agent_name, db_conn)` — aggregates `harness_verb_map` rows grouped by cycle mapping.

### Telemetry enrichment fields (new in `telemetry.json` rows)

Each dispatch telemetry entry gains:
- `first_output_at` — timestamp of first stdout byte (proxy for re-scan delay)
- `tool_call_count` — number of tool invocations recorded (from log parse)
- `rescue_agent` — agent name if this job was continued by another agent (NULL otherwise)
- `output_velocity_bpm` — bytes per minute, computed at job close

### `rescue_count` tracking

When a job's `status` transitions to `done` or `failed` by an agent different from the original `agent` field in `jobs.json`, the completing agent is recorded in `telemetry[n].rescue_agent`. `harness_status.rescue_count_24h` aggregates these.

---

## Capacity Model

### Three independent token budgets

Each agent has three separately-limited token pools that affect dispatch:

| Budget | Description | Failure mode when exceeded |
|---|---|---|
| **Read (input)** | Tokens consumed by: context.md + prompt + tool definitions + system overhead | Model truncates context silently; task operates on incomplete information |
| **Write (output)** | Tokens the model can generate per response | Partial completion — code or output silently truncated mid-task |
| **Tool calls** | Tool definitions + tool results consume input budget; some platforms cap call count | Agent exhausts tool budget mid-investigation; stops calling tools, produces incomplete analysis |

These budgets are distinct from context window size. `ctx_window_tokens` is a label (text) in the status display. The three budget fields are what dispatch gates on.

### Capacity tiers

**Tier 1 — Static curated (v1, in scope):**
Budgets seeded from `AGENT_CAPABILITY_BASELINES` per agent. Updated when probe detects a version change. Displayed as the authoritative capacity until Tier 2 config is present.

**Tier 2 — Plan-aware (v2, post v0.10.0):**
User declares `plan_tier` and `plan_type` in `.agents/<agent>.json`. Synlynk looks up the correct limits from a curated `PLAN_CAPACITY_TABLE` keyed by `(agent_name, plan_tier, plan_type)`. Example: `agy` + `pro` + `d2c` → write budget 32K; `agy` + `free` + `d2c` → write budget 8K.

**Tier 3 — Dynamic (deferred, post-GA):**
After each dispatch, parse `X-RateLimit-*` and equivalent response headers. If observed `limit` exceeds the curated baseline, a `SURGE_WINDOW` notification fires. In eco dispatch mode, queued tasks drain into the surge window.

### Curated capacity baseline (Tier 1)

| Agent | ctx window | read budget | write budget | tool budget |
|---|---|---|---|---|
| claude (max) | 200K | 750K† | 32K | ~200 |
| agy (pro) | 1,000K | 900K | 32K | ~500 |
| agy (free) | 1,000K | 900K | 8K | ~500 |
| codex (plus) | 128K | 110K | 16K | ~128 |
| grok (unknown) | 131K | 115K | 16K | ~100 |

† Claude's read budget is the input token limit minus tool definition overhead.

---

## Token Budget Estimation (`estimate_dispatch_tokens`)

Called at pre-dispatch time from `_preflight_dispatch()`. Returns `{input, output, tools}` estimates.

```python
def estimate_dispatch_tokens(prompt: str, context_md: str, agent_name: str) -> dict:
    TOOL_DEF_OVERHEAD = {
        "claude": 2200, "agy": 1800, "codex": 1600, "grok": 1400
    }
    TASK_TYPE_OUTPUT = {
        "implement": 8000, "review": 2000, "plan": 3000,
        "debug": 1500, "test": 2500, "docs": 2000, "default": 4000
    }
    SYSTEM_OVERHEAD = 2000

    input_est = (
        len(context_md.split()) * 1.3      # rough token estimate
        + len(prompt.split()) * 1.3
        + TOOL_DEF_OVERHEAD.get(agent_name, 2000)
        + SYSTEM_OVERHEAD
    )
    task_type = _classify_task_type(prompt)  # keyword heuristic
    output_est = TASK_TYPE_OUTPUT.get(task_type, 4000)

    # tool estimate from 30-day telemetry baseline for this agent
    avg_tool_calls = _get_avg_tool_calls(agent_name)  # from harness_status
    avg_tokens_per_call = 800  # conservative default
    tool_est = avg_tool_calls * avg_tokens_per_call

    return {"input": int(input_est), "output": output_est, "tools": int(tool_est)}
```

Estimates use conservative heuristics. They do not need to be precise — they exist to block obviously wrong routing (e.g., a 600K context task dispatched to Codex-128K) and to warn on output pressure before a task starts.

---

## Updated `_preflight_dispatch()` — Four Gates

The existing two gates (flag validation, network reachability) gain two new gates:

```
Gate 1 (existing): Flag validation — invalid_flags check
Gate 2 (existing): Network reachability — TCP connect to required_endpoints
Gate 3 (new):      Capacity — input budget
Gate 4 (new):      Capacity — output budget
Gate 5 (new, warn only): Tool pressure
```

```python
# Gate 3 — input budget
if est["input"] > cap["read_budget_tokens"]:
    return {"passed": False, "sentinel": "CAPACITY_EXCEEDED_INPUT",
            "reason": f"task needs ~{est['input']} input tokens; {agent} budget is {cap['read_budget_tokens']}. "
                      f"Suggest: split context, use agy (1M), or switch to eco mode."}

# Gate 4 — output budget
if est["output"] > cap["write_budget_tokens"]:
    return {"passed": False, "sentinel": "CAPACITY_EXCEEDED_OUTPUT",
            "reason": f"task needs ~{est['output']} output tokens; {agent} write budget is {cap['write_budget_tokens']}. "
                      f"Suggest: split task, or route to claude/agy (32K write)."}

# Gate 5 — tool pressure (non-blocking warning)
if est["tools"] > cap["tool_budget_count"] * 0.7:
    _write_sentinel(sentinel_path, "WARNING TOOL_PRESSURE",
                    f"{agent} tool budget ~{cap['tool_budget_count']}; estimated usage {est['tools']}")
    # dispatch continues
```

New sentinels added to `SENTINEL_PATTERNS`:
- `CAPACITY_EXCEEDED_INPUT` — blocks dispatch, suggests rerouting
- `CAPACITY_EXCEEDED_OUTPUT` — blocks dispatch, suggests task split
- `TOOL_PRESSURE` — warning only, dispatch continues

---

## Headless Efficiency Metric

**Definition:** ratio of tokens doing useful work vs. the equivalent interactive session baseline.

```
headless_efficiency = 1 / (1 - history_fraction)
```

Where `history_fraction` is the estimated proportion of tokens in a typical interactive session consumed by conversation history rather than the current task. Empirical baseline: 0.76 for a 10-turn Claude session (76% of context is prior turns).

In practice, computed per session as:

```python
tokens_saved = sum(
    est_history_tokens(job)       # counterfactual: tokens this job would have consumed in interactive
    - actual_context_tokens(job)  # actual: context.md size at dispatch time
    for job in session_jobs
)
efficiency_ratio = total_task_tokens / (total_task_tokens - tokens_saved)
```

Displayed in the efficiency banner as `Nx` where N = ratio rounded to 1 decimal.

**Why this is prominent:** This is synlynk's core value proposition made visible. Users who understand the efficiency ratio do not switch back to interactive mode for multi-agent work. It belongs at the top of the status display, not in a metrics footnote.

---

## Dispatch Modes

Stored in `.synlynk/config.json` as `dispatch_mode: "daily-grind" | "perf" | "eco"`. Shown in status header. Changed via `synlynk config set dispatch_mode eco`.

| Mode | Routing behaviour | Best for |
|---|---|---|
| **daily-grind** (default) | Dispatch to per-story configured agent. Preflight gates on capacity fit. If task won't fit, escalate to largest-window agent. | Routine predictable work |
| **perf** | Route to highest compat-score + capacity-fit agent. Parallel dispatch where tasks are independent. Fire immediately. | Sprint crunch, blocking work |
| **eco** | Queue tasks until a capacity expansion window is detected (Tier 3) or off-peak hours (Tier 2 schedule). Prefer large-window agents for bulk tasks. | Large tasks, non-urgent, cost-sensitive |

In Tier 1, eco mode behaves identically to daily-grind (no surge detection available). The config field is written now so users can set it; surge-aware behaviour activates when Tier 3 is implemented.

---

## `synlynk status` — Terminal Output Format

```
SYNLYNK ECOSYSTEM STATUS  2026-07-01 14:23
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

HEADLESS EFFICIENCY  4.2×   847K tokens saved · 23 dispatches · $0.34 saved

FLEET   3/4 attached   mode: daily-grind   last probe: 4m ago   active jobs: 2

AGENT SCORE           ATTACH  ADHERENCE  COMPLETE  VERSION
  claude [ref]         100%   —           99%      v1.2.3  ✓
  codex                 94%   87%         92%      v1.1.0  ✓
  grok                  78%   71%         81%      v2.0.1  ⚠ v2.1.0 avail
  agy                   61%   43%         67%      v3.2.0  ✓

CAPACITY              R(read)   W(write)  T(tools)  CTX     PLAN
  agy                 900K      8K        ~500      1,000K  pro
  claude              750K      32K       ~200      200K    max
  codex               110K      16K       ~128      128K    plus
  grok                115K      16K       ~100      131K    ?

  Tasks >32K output  → claude or agy (pro)
  Tasks >750K input  → agy only

CYCLE CAPABILITY      Dream  Plan   Work   Ship   Maint  Engage
  claude [ref]        ●●●    ●●●    ●●●    ●●●    ●●●    ●●●
  codex               ○○○    ○○○    ●●◐    ○○○    ●●◐    ◐○○
  grok                ○○○    ○○○    ●◐○    ○○○    ●◐○    ◐○○
  agy                 ◐○○    ○○○    ◐○○    ○○○    ●◐○    ○○○

  ● full  ◐ partial  ○ none   (3 dots = 3 key verbs per cycle)

SENTINELS   none active
```

Terminal uses Unicode: `●` (U+25CF) for full, `◐` (U+25D0) for partial, `○` (U+25CB) for none. No ANSI colour required for the cycle capability row — the symbols carry the information.

---

## Web HUD Visual Design

The web HUD (`synlynk watch` / `synlynk viz` web board) renders the same data with full visual treatment. Design approved in brainstorm session 2026-07-01. HTML files in `.superpowers/brainstorm/2822-1782873607/content/hud-v3.html`.

### Layout (top to bottom)

1. **Header bar** — workspace name, timestamp, dispatch mode badge with pulsing dot
2. **Headless efficiency banner** — `Nx` hero number, tokens saved, dispatch count, cost saved, one-line explanation
3. **Agent card row** — horizontal scroll, strict equal-width cards (180px), `+` placeholder for local agents
4. **Capability section** — two panels side by side:
   - **Cycle × Agent matrix** (primary): rows=cycles, columns=agents, each cell has 3 dots (key verbs) coloured full/partial/none + short note
   - **Cycle radar strip** (secondary): one hexagon per agent, 6 axes = 6 cycles, shape gives gestalt comparison
5. **Bottom row** — sentinels panel + capacity opportunity panel (eco/surge alerts)

### Agent card anatomy (180×fixed)

```
┌─────────────────────────────┐
│ [icon] agent-name  [status] │  ← icon 26×26, status dot
│        model · plan · ver   │
│                             │
│ ctx: 200K                   │  ← text label, no bar
│                             │
│ attach  100% [sparkline──]  │  ← 24h rolling attach rate
│                             │
│ R ████████████░░  750K      │  ← read budget bar
│ W ████████████████ 32K      │  ← write budget bar (scaled to fleet max write)
│ T ████████░░░░░░░  ~200     │  ← tool budget bar
│                             │
│ [99% complete] [ref adhere] │  ← score chips
└─────────────────────────────┘
```

Budget bars are scaled to fleet maximum per dimension: largest write budget = 100% width. This makes agy's 8K (free) write bar visually short relative to its 900K read bar — the imbalance reads as the imbalance it is.

### Cycle × Agent matrix cell

Each cell contains: 3 dot indicators (coloured) + one-line note below. Three dots represent the 3 most important verbs in that cycle for that agent. Colour: `#10b981` full, `#f59e0b` partial, `#1e293b` none.

### Cycle radar

SVG hexagons, one per agent. Axis order clockwise from top: Dream, Plan, Work, Ship, Maintain, Engage. Score per axis = `full_count / verb_count` for that cycle. Claude fills the hexagon. All other agents have asymmetric shapes — their shape is their fingerprint.

---

## `synlynk probe` Enhancements

The existing `_probe_agent()` function gains:

1. **Cycle capability computation** — after TC runs, call `_compute_cycle_capability(agent_name, db_conn)` to aggregate `harness_verb_map` into `cycle_capability` table rows
2. **Capacity record write** — upsert `harness_status` with Tier 1 capacity values from `AGENT_CAPABILITY_BASELINES`
3. **Latest version fetch** — best-effort, 3s timeout, per-agent registry:
   - claude: `npm info @anthropic-ai/claude-code version`
   - agy: `pip index versions google-labs-agy 2>/dev/null | head -1` (or equivalent)
   - codex: `npm info @openai/codex version`
   - grok: skip (no public registry known)
   - On timeout or error: `latest_version = None`, no sentinel

---

## Instruction Adherence — Proxy Signals

Direct measurement of whether an agent reads and acts on its harness fence requires instrumented agent output (AB-series, deferred). The proxy signals available from telemetry:

| Signal | What it captures | How computed |
|---|---|---|
| `avg_tool_calls` | Agent re-reading context already available | Mean `tool_call_count` per job, per agent, 30-day window |
| `time_to_first_output` | Re-scan delay vs. context-read start | `first_output_at - dispatched_at`, per job |
| `rescue_count` | Partial completions handed to another agent | Count of jobs where `rescue_agent IS NOT NULL` per agent per 24h |

`adherence_score` in `harness_status` is computed as a blend:

```python
adherence_score = (
    (1 - normalise(avg_tool_calls, baseline=AGENT_CAPABILITY_BASELINES[agent]["expected_tool_calls"])) * 0.5
    + (1 - normalise(avg_first_output_delay, baseline=10.0)) * 0.3   # 10s = neutral
    + (1 - normalise(rescue_rate, baseline=0.0)) * 0.2
)
```

Claude's adherence is `None` (reference, not scored against itself). All scores are relative. A cold agent (< 5 jobs in window) shows `adherence_score = None` rather than an uninformed number.

---

## Scope

### In scope (BS-16 v1 — targets v0.10.0)

- `harness_status` and `cycle_capability` tables in `_migrate_db()`
- `_compute_cycle_capability()` — aggregate verb_map into cycle scores
- `estimate_dispatch_tokens()` — task-level budget estimation
- `_preflight_dispatch()` — three new gates (CAPACITY_EXCEEDED_INPUT, CAPACITY_EXCEEDED_OUTPUT, TOOL_PRESSURE)
- Telemetry: `first_output_at`, `tool_call_count`, `rescue_agent`, `output_velocity_bpm` fields
- `synlynk probe` enhancements: cycle capability write, capacity record write, best-effort latest version
- `synlynk status` terminal output: efficiency banner, agent score, capacity table, cycle capability matrix
- Dispatch mode config (`dispatch_mode` in `.synlynk/config.json`), `synlynk config set dispatch_mode`
- Headless efficiency metric computation and display
- Tests: `tests/test_ecosystem_status.py` — ~20 tests covering all new functions

### In scope (BS-16 v2 — post v0.10.0)

- Plan-tier and plan-type config in `.agents/<agent>.json` + `PLAN_CAPACITY_TABLE`
- Plan-aware capacity limits per agent
- `synlynk status --json` output for HUD consumption
- Web HUD agent cards + cycle matrix + radar (BS-13 integration)

### Deferred (Tier 3 — post-GA)

- Surge window detection from response headers
- Eco mode queue scheduling into detected windows
- `SURGE_WINDOW` notification sentinel
- Regional routing / latency-based capacity inference
- IDE parity (Cursor, Windsurf, Copilot)
- Direct instruction adherence measurement (AB-series)

---

## Test Plan

New file: `tests/test_ecosystem_status.py`

Key tests:
- `test_compute_cycle_capability_full_agent` — claude maps all 6 cycles to full/partial correctly
- `test_compute_cycle_capability_agy` — agy: work=partial, plan=none, maintain=partial
- `test_estimate_dispatch_tokens_small_prompt` — small prompt + small context → input < 10K
- `test_estimate_dispatch_tokens_large_context` — 500K context → input estimate > 500K
- `test_preflight_blocks_input_overflow` — task estimated at 900K → CAPACITY_EXCEEDED_INPUT for codex (128K)
- `test_preflight_blocks_output_overflow` — implement task → CAPACITY_EXCEEDED_OUTPUT for agy-free (8K write)
- `test_preflight_warns_tool_pressure` — heavy tool task → TOOL_PRESSURE warning, dispatch not blocked
- `test_preflight_passes_for_fitting_task` — small task → all gates pass
- `test_harness_status_upsert_from_probe` — probe run → harness_status row written with correct capacity
- `test_telemetry_records_rescue_agent` — job completed by different agent → rescue_agent field set
- `test_adherence_score_cold_agent` — < 5 jobs in window → adherence_score is None
- `test_headless_efficiency_ratio` — 23 dispatches with known context sizes → correct ratio
- `test_status_output_contains_efficiency_banner` — `synlynk status` stdout includes efficiency ratio
- `test_dispatch_mode_defaults_to_daily_grind` — new project → config.dispatch_mode = daily-grind
- `test_config_set_dispatch_mode` — `synlynk config set dispatch_mode eco` → persisted in config.json

Existing `tests/test_capability_scoring.py` continues to be ignored (`--ignore=tests/test_capability_scoring.py`).
