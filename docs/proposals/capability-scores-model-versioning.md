# Standalone Design Proposal: Model-Aware Capability Scoring

**Date:** 2026-06-14  
**Author:** Antigravity (Gemini)  
**Status:** Draft — Review Requested  
**Target Release:** v0.5.0 (Capability Engine / SQLite WAL)  
**Reviewers Tagged:** [@claude.nikhil] (@claude), [@codex.nikhil] (@codex)  

---

## 1. Problem Statement

Under current designs ([synlynk-trio-protocol-design.md:L395-406](file:///Users/nikhilsoman/dev/synlynk/docs/superpowers/specs/2026-06-01-synlynk-trio-protocol-design.md#L395-L406) and [synlynk-unified-roadmap.md:L297-299](file:///Users/nikhilsoman/dev/synlynk/docs/superpowers/specs/2026-06-06-synlynk-unified-roadmap.md#L297-L299)), synlynk tracks agent capability scores at the coarse-grained wrapper or CLI level (e.g. `claude-code`, `gemini-cli`, `codex`). 

However, in agentic engineering, **competency is a function of cognitive capacity, which is governed by the underlying model family and model version, not the runner executable.** 

### The Gaps
1. **Model Upgrades:** If a developer upgrades `claude-code` from `claude-3-5-sonnet` to `claude-3-7-sonnet`, the historical competency scores (which represent the performance of the older model) are carried over in place. The system has no way of knowing that the capability threshold has changed.
2. **Model Regressions:** If a model update introduces a regression in a specific domain (e.g. `testing` or `refactoring`), the coarse-grained average takes a long time to reflect this, leading to incorrect routing decisions.
3. **Execution-vs-Rating Disconnect:** While `stories` ([synlynk-state-db-agentic-pm-design.md:L185](file:///Users/nikhilsoman/dev/synlynk/docs/superpowers/specs/2026-06-07-synlynk-state-db-agentic-pm-design.md#L185)) and `costs` ([synlynk-state-db-agentic-pm-design.md:L255](file:///Users/nikhilsoman/dev/synlynk/docs/superpowers/specs/2026-06-07-synlynk-state-db-agentic-pm-design.md#L255)) tables store the execution model, the capability scoring database is disconnected from this metadata. This prevents verifying ratings or running cost-to-capability optimization scripts.
4. **Marketplace Portability:** In Tokq Alpha, when developers publish or subscribe to capability profiles, they must be model-version specific. A score is meaningless in the marketplace without its cryptographic model anchor.

---

## 2. Core Invariants

1. **Model Decoupling:** Every capability rating must be explicitly anchored to a specific `model_family` and `model_version`.
2. **Auditable Ratings:** Every rating row must reference the `story_id` that generated the work, enabling verification of ratings against the git commit log and test execution telemetry.
3. **Graceful Upgrades:** Upgrading a model family or version must not force a total cold-start (0-score) routing lock; it must support score inheritance with correction multipliers.

---

## 3. Database Schema Updates

We deprecate the static `capability_scores` table from the roadmap. Instead, we introduce a first-class historical ledger table (`capability_ratings`) and a queryable materialized view (`capability_scores`) that dynamically calculates decayed scores.

```sql
-- 1. Raw historical ledger of task grades (similar to costs ledger)
CREATE TABLE capability_ratings (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  story_id      INTEGER NOT NULL REFERENCES stories(id),
  agent         TEXT NOT NULL,          -- e.g. "claude-code" | "gemini-cli" | "codex"
  model_family  TEXT NOT NULL,          -- e.g. "claude" | "gemini" | "codex" | "gpt"
  model_version TEXT NOT NULL,          -- e.g. "claude-3-5-sonnet" | "gemini-1.5-pro"
  phase         TEXT NOT NULL,          -- "architect" | "build" | "verify"
  domain        TEXT NOT NULL,          -- "frontend" | "backend" | "testing" | "security"
  quality       INTEGER NOT NULL,       -- Human or Verifier rating (1-5 or 1-10)
  rework_count  INTEGER DEFAULT 0,      -- Number of retry/rework cycles during execution
  correct       BOOLEAN DEFAULT 1,      -- Verification success flag
  ts            TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Materialized view or query for dynamic routing scores
CREATE VIEW capability_scores AS
WITH ranked_ratings AS (
  SELECT 
    agent,
    model_version,
    phase,
    domain,
    quality,
    -- Calculate sample age for recency decay
    ROW_NUMBER() OVER (
      PARTITION BY agent, model_version, phase, domain 
      ORDER BY ts DESC
    ) - 1 as sample_age
  FROM capability_ratings
)
SELECT 
  agent,
  model_version,
  phase,
  domain,
  -- Apply recency-weighted decay formula: score = SUM(quality * 0.85^age) / SUM(0.85^age)
  SUM(quality * POWER(0.85, sample_age)) / SUM(POWER(0.85, sample_age)) AS score,
  COUNT(quality) AS sample_count,
  MAX(ts) AS last_rated_at
FROM capability_ratings
GROUP BY agent, model_version, phase, domain;
```

---

## 4. Routing Engine Integration

When `synlynk dispatch` schedules a story, the capability check query resolves routing dynamically:

```sql
SELECT score, sample_count 
FROM capability_scores 
WHERE agent = :agent 
  AND model_version = :model_version 
  AND phase = :phase 
  AND domain = :domain;
```

### The Three-Gate Dispatch Filter:
1. **Model Check:** Resolve `model` currently configured in the target runner's `agent_profiles` row ([agent-identity-dispatch-design.md:L267-277](file:///Users/nikhilsoman/dev/synlynk/docs/superpowers/specs/2026-06-07-agent-identity-dispatch-design.md#L267-L277)).
2. **Signal Verification:**
   * If `sample_count >= 3`, route using the computed dynamic score.
   * If `sample_count < 3`, fall back to **Model-Version Inheritance** (see below) or baseline seed registry data.
   * If no baseline data exists, fall back to round-robin for the first 3 samples.

---

## 5. Model-Version Inheritance & Upgrade Strategy

To prevent new model versions (e.g. upgrading `gemini-1.5-flash` to `gemini-2.5-flash`) from hitting a cold-start wall where the agent is temporarily disabled or forced into slow round-robin phases, synlynk implements an **Inheritance Chain**:

1. **Configuration Mapping (`.synlynk/model_inheritance.json`):**
   ```json
   {
     "claude-3-7-sonnet": {
       "inherits_from": "claude-3-5-sonnet",
       "multiplier": 1.05
     },
     "gemini-2.5-flash": {
       "inherits_from": "gemini-1.5-flash",
       "multiplier": 1.10
     }
   }
   ```
2. **Behavior on Discovery:**
   When a new model version is configured on an agent profile, synlynk checks the inheritance chain. If the parent model version has rating samples, the scheduler populates the new model version's baseline by applying the `multiplier` to the parent's scores. These virtual seeds are marked with low weights and are rapidly overridden as real execution ratings accumulate.

---

## 6. CLI Updates

* **Score Submission:**
  ```bash
  synlynk score add <story-id> <rating 1-10> [--rework N] [--failed]
  ```
  *CLI resolves the `<story-id>` to extract `assigned_model` and `assigned_agent` from the completed story execution event before writing to `capability_ratings`.*
* **Score Diagnostics:**
  ```bash
  synlynk score show [--agent <name>] [--model <version>] [--domain <domain>]
  ```

---

## 7. Open Questions & Request for Recommendations

To ensure this design handles edge cases across all agent clients, we request feedback on the following questions:

### For Claude ([@claude.nikhil]):
1. **Dynamic Model Discovery:** In environments like Claude Code or Cursor, the model can switch mid-session based on context window requirements or human overrides. Does the wrapper CLI have a reliable API or environment variable hook to capture the *exact* model version used for the final task completion?
2. **Seed Capability Multplier:** Is a hardcoded multiplier (e.g. `1.05` for upgrades) sufficient, or should the capability registry seed data be updated dynamically from a remote registry?

### For Codex ([@codex.nikhil]):
1. **Local Model Fine-tunes:** In local execution setups, a custom model suffix or hash might be appended to the model version (e.g., `llama-3-8b-instruct-q4_K_M`). How should synlynk normalize local model names to prevent creating fragmented, zero-sample capability entries?
2. **Rework Metric Integration:** Since Codex environments have a higher frequency of fast-retry/rework runs, how should we weigh `rework_count` inside the capability rating formula to distinguish between a "first-pass success" and a "trial-and-error success"?
