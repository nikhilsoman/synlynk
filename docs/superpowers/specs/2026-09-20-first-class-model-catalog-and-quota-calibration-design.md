# Design Spec: First-Class Model Catalog & Rolling Quota Calibration Engine

**Date:** 2026-09-20  
**Status:** Draft / In Review  
**Decision Records:**  
- [`project-docs/decisions/2026-09-20-2026-sota-model-matrix-modernization-fir.md`](file:///Users/nikhilsoman/dev/synlynk/project-docs/decisions/2026-09-20-2026-sota-model-matrix-modernization-fir.md) (`dec-b8fbb0ad`)  
**Authors:** [@nikhilsoman], [@agy], [@claude], [@codex]  

---

## 1. Executive Summary & Problem Statement

Synlynk orchestrates heterogeneous compute harnesses (`claude`, `agy`, `codex`, `grok`, `local`). However, two architectural gaps create operational friction:

1. **Model Catalog Fragmentation:** Model definitions, pricing rates, context limits, and tier mappings are scattered across `update_costs()`, `dispatch.py`, and `models.py`, lagging behind 2026 SOTA releases.
2. **Multi-Track Quota Blindness:** Modern subscriptions (such as Google AI Pro in Antigravity) bundle multiple distinct model families (Gemini, Claude, and GPT OSS tracks) with separate quotas. Furthermore, static limit estimates drift from actual provider enforcement. Without periodic calibration against live `/usage` percentages across rolling 5-Hour (5H) and 1-Week (1W) consumption windows, dispatches risk abrupt mid-task rate limit failures.

This specification establishes:
- A declarative, stdlib-only JSON **First-Class Model Catalog** ([`.synlynk/models.json`](file:///Users/nikhilsoman/dev/synlynk/.synlynk/models.json)).
- An automated **Rolling Quota Calibration Engine** that periodically parses CLI `/usage` reports, cross-references local token telemetry against reported consumption percentages, computes exact 5H/1W capacity ceilings, and projects live quota runways.

---

## 2. Architecture & Subsystem Topology

```
┌────────────────────────────────────────┐
│        SYNLYNK QUOTA & CATALOG         │
└───────────────────┬────────────────────┘
                    │
         ┌──────────┴──────────┐
         ▼                     ▼
┌─────────────────┐   ┌─────────────────┐
│ Declarative     │   │ Rolling Quota   │
│ Model Catalog   │   │ Calibration     │
│ (.synlynk/      │   │ (/usage Probe & │
│  models.json)   │   │  5H/1W Windows) │
└────────┬────────┘   └────────┬────────┘
         │                     │
         ▼                     ▼
┌───────────────────────────────────────┐
│       TRIPARTITE DISPATCH ENGINE      │
│  • Fast / Pro / Reasoning Tiers       │
│  • Pinned Requested & Resolved IDs    │
│  • Predictive Pre-Exhaustion Routing  │
└───────────────────┬───────────────────┘
                    │
         ┌──────────┴──────────┐
         ▼                     ▼
┌─────────────────┐   ┌─────────────────┐
│ Antigravity Pro │   │ Claude / Codex  │
│ Multi-Track:    │   │ Direct Quota    │
│ • Gemini Track  │   │ Pools (5H/1W)   │
│ • Claude Track  │   │                 │
│ • GPT OSS Track │   │                 │
└─────────────────┘   └─────────────────┘
```

---

## 3. First-Class Model Catalog ([`.synlynk/models.json`](file:///Users/nikhilsoman/dev/synlynk/.synlynk/models.json))

The catalog is stored as a version-controlled, stdlib-only JSON file under `.synlynk/models.json`, with shipped system defaults and user overrides.

```json
{
  "schema_version": 1,
  "as_of": "2026-09-20",
  "tiers": {
    "fast": {
      "claude": "claude-haiku-4.5",
      "agy": "gemini-3.7-flash",
      "codex": "gpt-5-mini",
      "grok": "grok-3-mini",
      "local": "qwen2.5-coder-7b"
    },
    "pro": {
      "claude": "claude-sonnet-5",
      "agy": "gemini-3.0-pro",
      "codex": "gpt-5",
      "grok": "grok-3",
      "local": "qwen2.5-coder-32b"
    },
    "reasoning": {
      "claude": "claude-opus-5",
      "agy": "gemini-3.5-pro",
      "codex": "o3",
      "grok": "grok-3.5",
      "local": "deepseek-r1"
    }
  },
  "models": [
    {
      "model_id": "claude-sonnet-5",
      "family": "claude-5",
      "harness": "claude",
      "context_window": 200000,
      "max_output": 16384,
      "rates": {"input_per_1k": 0.003, "output_per_1k": 0.015, "cache_read_per_1k": 0.0003}
    },
    {
      "model_id": "gemini-3.7-flash",
      "family": "gemini-3",
      "harness": "agy",
      "context_window": 1000000,
      "max_output": 8192,
      "rates": {"input_per_1k": 0.0001, "output_per_1k": 0.0004}
    }
  ]
}
```

---

## 4. Multi-Track Quota Management & Antigravity Bundles

In Google AI Pro / Antigravity, subscriptions bundle multiple separate model families:
1. **Gemini Track (`gemini-*`):** Primary multimodal/large-context quota.
2. **Claude Track (`claude-*` via Agy):** Dedicated Claude allocation within the Pro plan.
3. **GPT OSS Track (`gpt-oss-*` / `gpt-5-mini-proxy`):** Independent inference allowance.

### Schema Update (`harness_quotas` Table)
In `state.db`, the unique key is updated to track model family tracks independently:

```sql
CREATE TABLE IF NOT EXISTS harness_quotas (
    harness      TEXT NOT NULL,
    track        TEXT NOT NULL DEFAULT 'default', -- e.g. 'gemini', 'claude_proxy', 'gpt_oss'
    model        TEXT NOT NULL,
    quota_type   TEXT NOT NULL, -- '5h', 'weekly', 'monthly'
    unit         TEXT NOT NULL, -- 'tokens', 'percent', 'requests'
    limit_tokens INTEGER,
    used_tokens  INTEGER,
    used_pct     REAL,          -- Live reported percentage from /usage
    reset_at     TEXT,          -- Provider reset timestamp
    updated_at   TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(harness, track, quota_type, unit)
);
```

---

## 5. Periodic `/usage` Calibration Engine

```
┌──────────────────────────────────────┐
│  Periodic Calibration Tick (Daemon)  │
│  Runs CLI Usage Probes Every 15 min  │
└──────────────────┬───────────────────┘
                   │
                   ▼
┌──────────────────────────────────────┐
│  Parse Provider /usage Reports:      │
│  • 5H Window: "42% used (resets 2h)" │
│  • 1W Window: "68% used (resets 3d)" │
└──────────────────┬───────────────────┘
                   │
                   ▼
┌──────────────────────────────────────┐
│  Cross-Reference Local Telemetry:    │
│  Δ Tokens = 84,000                   │
│  Δ Reported % = 42%                  │
│  ⟹ Deduced 5H Total Limit = 200,000 │
└──────────────────┬───────────────────┘
                   │
                   ▼
┌──────────────────────────────────────┐
│  Update harness_quotas & Project     │
│  Live Burn Rate & Quota Runway       │
└──────────────────────────────────────┘
```

### Mathematical Calibration Formula
When a provider CLI reports $P_1\%$ at $T_1$ and $P_2\%$ at $T_2$, with local executed token consumption $\Delta \text{Tokens}$:

$$\text{Calculated Ceiling} = \frac{\Delta \text{Tokens}}{(P_2 - P_1) / 100}$$

$$\text{Projected Runway (hours)} = \frac{\text{Remaining Tokens}}{\text{Rolling Token Burn Rate (tokens/hour)}}$$

---

## 6. Dynamic Empirical Allocation Modeling & Off-Peak Capacity Surges

Providers do not enforce static, fixed ceilings. Instead, they dynamically scale user token quotas across 5-Hour and 1-Week windows based on **time-of-day traffic, regional grid load, and server cluster congestion**:

```
┌────────────────────────────────────────┐
│     DYNAMIC 5H CAPACITY FLUCTUATION    │
├───────────────────┬────────────────────┤
│ Time Window (UTC) │ Allocation Factor  │
├───────────────────┼────────────────────┤
│ 00:00 - 08:00     │ 1.50x (Off-Peak)   │
│ 08:00 - 13:00     │ 1.00x (Standard)   │
│ 13:00 - 19:00     │ 0.65x (Peak Surge) │
│ 19:00 - 24:00     │ 1.10x (Evening)    │
└───────────────────┴────────────────────┘
```

### Empirical Statistical Engine
By continuously correlating executed tokens $\Delta \text{Tokens}$ against reported percentage deltas $\Delta P\%$ from `/usage`, Synlynk fits a time-series model $\text{Ceiling}(harness, tier, t)$:
1. **Surge / Throttled Blocks:** Detects when effective 5H capacity drops (e.g. 13:00–19:00 UTC during US/EU peak hours), alerting agents to throttle non-urgent background swarms.
2. **Expanded Off-Peak Windows:** Detects when providers grant bonus headroom during off-peak hours (e.g. night/weekend blocks), recommending these windows for heavy batch migrations, refactoring sweeps, and multi-node soak runs.

---

## 7. Public Fleet Utilization Advisory Service (`synlynk.com/advisory`)

To benefit the broader developer ecosystem and inform autonomous schedulers fleet-wide, Synlynk establishes an **Anonymized Quota & Utilization Advisory Service**:

```
┌────────────────────────────────────────┐
│         SYNLYNK FLEET RUNTIMES         │
│  (Anonymized Quota Telemetry Opt-in)   │
└───────────────────┬────────────────────┘
                    │
                    ▼
┌────────────────────────────────────────┐
│     SYNLYNK.COM ADVISORY SERVICE       │
│  • Aggregated 5H & 1W Heatmaps         │
│  • Regional Throttle / Surge Status    │
│  • Real-Time Effective Token Ceilings  │
└───────────────────┬────────────────────┘
                    │
                    ▼
┌────────────────────────────────────────┐
│  • Web Dashboard: synlynk.com/advisory │
│  • CLI Feed: synlynk quota advisory    │
│  • Swarm Scheduler Optimal Dispatch   │
└────────────────────────────────────────┘
```

1. **Anonymized Telemetry Feed:** Participating Synlynk nodes publish non-sensitive telemetry snapshots: `(harness, track, window, time_block, effective_ceiling_estimate)`. No code, prompts, or user IDs are transmitted.
2. **Live Monthly & Regional Advisory:**
   - Visualizes live and historical capacity curves for Claude, Antigravity (Google AI Pro), Codex, and Grok.
   - Highlights regional 5H blocks known to provide 1.5x–2.0x expanded allocations.
3. **Autonomous Swarm Scheduling Optimization:**
   - `synlynk swarm dispatch --window optimal` automatically holds heavy batch workloads until an expanded off-peak 5H block opens.

---

## 8. CLI User Experience (`synlynk quota`)

```bash
# View live calibrated quota headroom and runways
synlynk quota

# View public / fleet utilization advisory and off-peak surge forecast
synlynk quota advisory

# Trigger manual calibration probe across all harnesses
synlynk quota calibrate

# Output structured JSON for agentic planners
synlynk quota --json
```

### Sample Output (`synlynk quota advisory`):
```text
FLEET UTILIZATION ADVISORY  2026-09-20 12:40 UTC
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Harness/Track       Current State     Effective 5H Ceiling   Next Expanded Window
claude (Sonnet 5)   🔴 Peak Surge      130,000 tokens (-35%)  20:00 UTC (+50% bonus)
agy (Gemini Track)  🟢 Standard        1,000,000 tokens       Continuous High Headroom
agy (Claude Track)  🟡 Moderate        160,000 tokens (-20%)  21:00 UTC
codex (GPT-5)       🔴 Peak Surge      120,000 tokens (-40%)  19:30 UTC

💡 Recommendation: Defer heavy batch swarm jobs until 20:00 UTC for 1.8x token runway.
```

---

## 9. Verification & Acceptance Criteria

1. `synlynk/models.py` loads declarative `.synlynk/models.json` with fallback to builtin definitions.
2. `synlynk/quota.py` implements `/usage` percentage parsing for 5H and 1-Week rolling windows.
3. Antigravity multi-track quotas (`gemini`, `claude_proxy`, `gpt_oss`) are stored and reported independently.
4. `synlynk quota calibrate` executes without blocking dispatches and populates `harness_quotas.used_pct`.
5. `synlynk quota advisory` surfaces current capacity states and off-peak window recommendations.
6. 100% test coverage in `tests/test_models.py` and `tests/test_quota_calibration.py`.

