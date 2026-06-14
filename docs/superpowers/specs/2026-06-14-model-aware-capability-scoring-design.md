# Model-Aware Capability Scoring Design

**Date:** 2026-06-14  
**Status:** Approved — ready for implementation planning  
**Extends:** `docs/proposals/capability-scores-model-versioning.md` (Gemini's initial proposal)  
**Tokq bearing:** This spec defines the schema and address space for Capability Profile Memory Units on Tokq.

---

## Goal

Extend synlynk's capability scoring system so that every quality rating is anchored to a specific model version executing within a precise domain coordinate. This makes scores attribution-safe, routing decisions model-aware, and Tokq Memory Units structurally rich enough to carry market value.

---

## Background

Gemini's proposal (`docs/proposals/capability-scores-model-versioning.md`) introduced `capability_ratings` and `capability_scores` with model version tracking and recency decay. Three gaps were identified:

1. **Model version extraction is unreliable** — no systematic strategy for capturing which model actually ran a story.
2. **Domain is one-dimensional** — engineering domain alone doesn't capture organizational context (product function) or industry vertical (business context), both of which are strong predictors of routing quality.
3. **Quality signal conflation** — the proposal didn't distinguish signal sources (automated vs. peer-agent vs. human), and `rework_count` collapsed two semantically different signals.

This spec resolves all three.

---

## Design

### 1. Model Version — 4-Tier Resolution Chain

Model version is resolved in priority order. The resolved value is stored as `model_version`. Both dispatch-time and completion-time values are stored separately to detect split-model executions.

| Tier | Source | Mechanism |
|------|--------|-----------|
| 1 (primary) | Structured output header | synlynk parses `# synlynk-meta` block from agent stdout at job completion; `model_version=<value>` field |
| 2 (probe) | Statusline at dispatch | `synlynk exec` captures agent's current model from statusline before spawning the job; stored as `model_at_dispatch` |
| 3 (config) | Explicit workspace config | `.synlynk/config.json` field `default_model` per agent; used when probe fails |
| 4 (recovery) | PR attestation | `synlynk pr check` hard-blocks merge when `model_version = 'unknown'`; author agent attests via `synlynk score attest <story-id> --model <version>` |

**Split-model stories:** When `model_at_dispatch ≠ model_at_completion` (user changed model mid-task), the row sets `split_model = true`. Routing excludes split-model rows from score aggregation (attribution is ambiguous). Tokq exposes them as "mixed-model execution" samples — lower confidence, lower marketplace value, still informative.

**`synlynk-meta` header format (agent output):**
```
# synlynk-meta
model_version=claude-opus-4-8
quality=8
correct=true
rework_needed=false
verifier_model=gemini-2.5-pro   # only present in verifier runs
```

**PR attestation CLI:**
```bash
synlynk pr check            # hard-blocks merge if model_version = 'unknown' on any open story
synlynk score attest <story-id> --model <version>   # agent or human retroactively attests
```

---

### 2. Domain Taxonomy — 3-Dimensional Coordinate

Every story and every Tokq Memory Unit carries a coordinate across three independent layers.

#### Layer 1 — Engineering Domain
Stack, environment, workflow, process associations.

Canonical values: `architecture`, `frontend`, `backend`, `data`, `ml`, `testing`, `security`, `devops`, `docs`

**Inference strategy:**
- Primary (B): Agent classifies the story description against the canonical list at dispatch time, stored in the story row.
- Fallback (C): File path heuristics at job completion (`src/api/` → `backend`, `src/components/` → `frontend`, etc.).

#### Layer 2 — Organizational Domain
Product function and business capability.

Canonical values: `personalization`, `monetization`, `adtech`, `workflow`, `analytics`, `growth`, `content`, `platform`, `identity`

**Cardinality rule:** Exactly **1 primary** `org_domain` (routing key — required for `capability_scores` partitioning) plus **N secondary** tags stored as `org_domain_tags` (JSON array — Tokq discoverability only, not used in routing queries).

**Inference strategy:** Agent classifies from story title + product context at dispatch; inherits from epic or phase tag if unclassified.

#### Layer 3 — Industry Vertical
Business context and market segment.

Canonical values: `ott`, `streaming`, `fintech`, `banking`, `securities`, `healthcare`, `ecommerce`, `edtech`, `gaming`

**Source:** Workspace-level config set at `synlynk init` (inferred from README scan). Inherited by all stories. Per-story override allowed via `--industry` flag on `synlynk story create`.

**Tokq address** — the coordinate becomes the marketplace key:
```
tokq://capability/{engg_domain}/{org_domain}/{industry}/{model_version}
```

Example: `tokq://capability/backend/monetization/ott/claude-opus-4-8`

Secondary tags expand discoverability without multiplying the address space.

---

### 3. Quality Signal Architecture — 3-Tier Hierarchy

Three tiers feed one ledger row. The tier providing the primary quality score is stored in `signal_source`. Auto signals are always captured as metadata regardless of which tier wins.

#### Tier A — AUTO (weight 0.60)
Zero human cost. Captured automatically at job completion.

| Column | Capture mechanism |
|--------|------------------|
| `test_pass_rate` | Scraped from CI log or test runner stdout in job log |
| `build_success` | Job exit code + build/lint output |
| `pr_review_cycles` | Count of PR review rounds before merge (ground truth for output quality) |
| `duration_vs_estimate` | Actual token/time cost ÷ `story.estimated_tokens` |
| `verified_by_ci` | CI pipeline outcome after PR merge |

Auto composite score normalised to 0–10, stored as `quality_auto`. Used as `quality` when no verifier or human rating exists. Rows with `signal_source = 'auto'` are flagged low-confidence in Tokq exports.

#### Tier B — VERIFIER (weight 0.85)
Peer agent rating. Dispatched as the Verifier role in a trio pipeline run.

The Verifier receives: Builder's diff, story's `done_criteria`, and the auto-signals. It emits a structured review ending with a `synlynk-meta` block:

```
# synlynk-meta
quality=8
correct=true
rework_needed=false
verifier_model=gemini-2.5-pro
```

`verifier_agent` and `verifier_model` are stored separately — the rating is a joint function of the Builder's model and the Verifier's model. A high score from a more capable verifier carries more weight in Tokq marketplace valuation.

#### Tier C — HUMAN (weight 1.0)
Override. Highest weight. Not required but always wins when present.

```bash
synlynk score add <story-id> 9 [--note "clean first-pass implementation"]
synlynk score add <story-id> 3 --rework --note "missed edge cases in auth flow"
```

Human rating sets `signal_source = 'human'` and overwrites verifier/auto as the effective score. The `note` field flows into the Tokq Memory Unit description.

#### Effective Score Resolution
```
if human rating present  → quality = human rating, signal_source = 'human'
elif verifier present    → quality = verifier rating, signal_source = 'verifier'
else                     → quality = quality_auto, signal_source = 'auto' (low-confidence flag)

# Auto signals always stored as metadata columns regardless of winner
```

#### Rework — Two Separate Signals
`rework_count` from Gemini's proposal is split into two distinct columns with different routing semantics:

| Column | Meaning | Routing role |
|--------|---------|-------------|
| `dispatch_rework` | Count of full re-dispatch cycles before story reached `done` | **First-class routing signal** — penalises score directly |
| `micro_rework` | Count of sub-task retries within a single dispatch session | **Informational only** — stored as metadata, never enters score formula |

Rationale: micro-rework is implementation noise (the agent self-correcting within a session); dispatch-rework is a definitive signal that the agent's first output was insufficiently correct for the story to be accepted.

---

### 4. Full Schema

#### `capability_ratings` (ledger)

```sql
CREATE TABLE capability_ratings (
  id                        INTEGER PRIMARY KEY AUTOINCREMENT,

  -- Identity
  story_id                  INTEGER NOT NULL REFERENCES stories(id),
  agent                     TEXT NOT NULL,           -- "claude" | "gemini" | "codex"

  -- Model (builder side)
  model_version             TEXT NOT NULL,           -- effective resolved value; "unknown" hard-blocked
  model_at_dispatch         TEXT,                    -- tier 2 probe at dispatch time
  model_at_completion       TEXT,                    -- tier 1 from synlynk-meta header
  split_model               BOOLEAN DEFAULT 0,       -- true when dispatch ≠ completion

  -- Domain coordinate
  engg_domain               TEXT NOT NULL,
  org_domain                TEXT NOT NULL,           -- primary routing key
  org_domain_tags           TEXT DEFAULT '[]',       -- JSON array; Tokq discoverability only
  industry                  TEXT NOT NULL,           -- workspace-inherited
  phase                     TEXT NOT NULL,           -- "architect" | "build" | "verify"

  -- Quality signal (primary)
  signal_source             TEXT NOT NULL,           -- "human" | "verifier" | "auto"
  quality                   REAL NOT NULL,           -- effective score 0–10
  quality_auto              REAL,                    -- auto composite; always computed

  -- Verifier metadata
  verifier_agent            TEXT,                    -- e.g. "gemini"
  verifier_model            TEXT,                    -- e.g. "gemini-2.5-pro"

  -- Auto signals (always captured)
  test_pass_rate            REAL,                    -- 0.0–1.0
  build_success             BOOLEAN,
  dispatch_rework           INTEGER DEFAULT 0,       -- full re-dispatch cycles; routing signal
  micro_rework              INTEGER DEFAULT 0,       -- sub-task retries; informational only
  pr_review_cycles          INTEGER DEFAULT 0,
  duration_vs_estimate      REAL,                    -- actual/estimated ratio
  verified_by_ci            BOOLEAN,

  -- Provenance
  correct                   BOOLEAN DEFAULT 1,
  note                      TEXT,
  ed25519_sig               TEXT,                    -- signs (story_id || model_version || quality || ts)

  ts                        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### `capability_scores` (derived view — routing surface)

Same as Gemini's proposal: recency-weighted decay `(0.85^age_in_weeks)` over the ledger, partitioned by `(agent, model_version, engg_domain, org_domain, industry, phase)`. Split-model rows (`split_model = 1`) excluded from aggregation.

```sql
CREATE VIEW capability_scores AS
SELECT
  agent,
  model_version,
  engg_domain,
  org_domain,
  industry,
  phase,
  SUM(quality * POW(0.85, CAST((julianday('now') - julianday(ts)) / 7 AS INTEGER))) /
    SUM(POW(0.85, CAST((julianday('now') - julianday(ts)) / 7 AS INTEGER)))
    AS weighted_score,
  COUNT(*) AS sample_count,
  MAX(ts) AS last_seen
FROM capability_ratings
WHERE split_model = 0
GROUP BY agent, model_version, engg_domain, org_domain, industry, phase;
```

---

### 5. Routing Engine

When `dispatch_agent()` selects an agent for a story, it queries `capability_scores` with the story's full coordinate:

```sql
SELECT agent, model_version, weighted_score, sample_count
FROM capability_scores
WHERE engg_domain = ?
  AND org_domain  = ?
  AND industry    = ?
  AND phase       = ?
ORDER BY weighted_score DESC
LIMIT 5;
```

**Cold-start (no matching rows):** Fall back to the broader coordinate — drop `industry`, then drop `org_domain`, progressively widening until a match is found. If no data exists at any level, use the model family registry for a prior estimate (see §6).

---

### 6. Model Inheritance — Replacing the Config File

Gemini's proposal suggested a hardcoded `model_inheritance.json` with capability multipliers. This is replaced with a dynamic approach:

Tokq publishes a public Memory Unit at `tokq://registry/model-families`. synlynk fetches this on `synlynk upgrade`. It contains:
- Model family lineage (e.g., `claude-opus-4-8` descends from `claude-opus-4-7`)
- Capability delta estimates per engineering domain, updated as community data accumulates

**Local fallback:** Until 3 real `capability_ratings` samples exist for a new model version at a given coordinate, the routing engine applies a neutral 1.0× multiplier (no bonus, no penalty) relative to the parent model's score.

---

### 7. Tokq Memory Unit — Capability Profile

A Capability Profile Memory Unit is a signed snapshot of the `capability_scores` view for one address coordinate.

**Address:** `tokq://capability/{engg_domain}/{org_domain}/{industry}/{model_version}`

**Contents:**

| Field | Description |
|-------|-------------|
| `score_distribution` | mean, stddev, p25, p75 of weighted_score |
| `sample_count` | number of contributing rows |
| `signal_source_mix` | % human / % verifier / % auto-only |
| `verifier_model_quality` | quality of the verifier agent used (if applicable) |
| `org_domain_tags` | secondary tags for discovery (not part of address) |
| `industry_aliases` | additional industry labels for cross-vertical discovery |
| `provenance` | creator Ed25519 pubkey, story_ids[], time range, model per sample |
| `auto_aggregates` | avg test_pass_rate, ci_pass_rate, avg dispatch_rework, avg pr_review_cycles |

**Marketplace value signals:** `sample_count`, `human_override_rate`, `ci_pass_rate`, `verifier_model`. Higher sample count from higher-trust signal sources commands higher subscription cost.

**Split-model samples** are exposed separately as "mixed-model execution" — lower confidence, lower value, flagged explicitly.

**Auto-only rows** (no verifier or human rating) are flagged `low_confidence: true` in the Tokq export. Subscribers can filter by this flag.

---

### 8. CLI Surface Additions

```bash
# Attest model version retroactively (required to clear PR block)
synlynk score attest <story-id> --model <version>

# Add human quality rating
synlynk score add <story-id> <0-10> [--note "..."] [--rework]

# View routing scores for a coordinate
synlynk score list --engg backend --org monetization --industry ott

# Export capability profile as Tokq Memory Unit (future)
synlynk tokq export --engg backend --org monetization --industry ott --model claude-opus-4-8
```

---

### 9. Init Wizard Changes

`synlynk init` gains two new prompts:

1. **Industry vertical** — "What industry is this product in? (ott/fintech/banking/healthcare/ecommerce/edtech/gaming/other)". Inferred from README scan; user confirms or overrides. Stored in `.synlynk/config.json` as `industry`.

2. **Default model** — "Which model does each agent default to? (used as tier-3 fallback for model_version)". One entry per discovered agent CLI.

---

## What This Does Not Cover

- Tokq marketplace gas/subscription mechanics — separate spec
- `tokq://registry/model-families` publishing workflow — owned by Tokq team
- Multi-workspace capability score federation — future
- Verifier dispatch scheduling in trio pipeline — covered in hybrid-workgroup spec

---

## Implementation Scope

This is a v0.5.0 feature. The implementation touches:

- `bin/synlynk.py` — `_reconcile_jobs()`, `update_costs()`, `dispatch_agent()`, new `score` and `pr` subcommands, init wizard prompts
- `project-docs/` schema — `stories` table gets `engg_domain`, `org_domain`, `org_domain_tags`, `industry`, `phase` columns; `capability_ratings` and `capability_scores` are new
- Tests — new test file `tests/test_capability_scoring.py`

No new dependencies. No config file format changes beyond additions to `.synlynk/config.json`.
