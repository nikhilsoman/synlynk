# Harness Capability Registry v2 + Full Agent→Harness Rename: #786

**Status:** approved, ready for planning
**Scope:** GitHub issue #786, expanded during kickoff brainstorm (2026-08-18) from a narrow terminology rename into two sequenced efforts: (A) the full agent→harness terminology rename across the codebase, and (B) a capability registry v2 that tracks live model rosters, evolving harness tools/skills/flags, and auto-calibrates newly-discovered models against a difficulty-graded per-role task pool.
**Roadmap link:** Not yet on `docs/strategy/2026-08-15-two-imperatives-roadmap.md` — this is a new, not-yet-tracked track. Add as a roadmap item once this spec is approved.

## Background

`docs/glossary-agent-vs-harness.md` established the canonical distinction: **Agent** = persistent role/charter identity (8 roles: pm, architect, tpm, dev, designer, qa, marketing, synlynk-bot), **Harness** = swappable execution backend (Claude, Agy, Grok, Codex, local). The CLI verb group was already renamed `synlynk agent` → `synlynk harness` in PR #993 (2026-08-15), but the underlying codebase still conflates the two concepts extensively — issue #786 tracks the full cleanup (~2,073 occurrences across 34 source files, 5 DB tables/columns, 18 CLI flags, 59 test files, 331 doc files).

During kickoff, Nikhil expanded scope beyond the rename to include: harness capability tracking must follow rapidly-superseding model versions; harness tools/skills/modes are also evolving and instructions/flags/configs need to target the right harness generation; Agent and Harness need independent first-class status in the data model; and a capability registry needs to maintain all of this automatically rather than through one-time manual audits.

Recon during this brainstorm found an existing partial mechanism, `synlynk/capability_sweep.py` (272 lines), that already implements cost-capped, independently-verified calibration sweeps — but only via manual invocation, against a fixed 3-skill/1-template task pool, with no auto-trigger on new-model-detection. This spec extends that mechanism rather than replacing it.

A genuine risk was found and resolved during design: PR #1003/#1030 (Agent-roles-charters Phase 1/2) already shipped real Agent-role columns (`daemon_jobs.agent_id`) that must NOT be swept into the harness rename — see the classification methodology below.

## Decisions (locked before this spec was written)

1. **Sequencing:** Plan A (classify & rename) lands before Plan B (registry v2) — building new registry tables on still-ambiguous `agent`/`harness` naming would create more conflation, not less.
2. **Rename methodology:** classify-then-rename, not mechanical find/replace. Every `agent`-named symbol is tagged against the three rules below before any rename executes.
3. **Model discovery:** hybrid — self-report via CLI probe first (`synlynk probe`), curated baseline (`HARNESS_CAPABILITY_BASELINES`) as fallback when self-report is unavailable or incomplete.
4. **Registry scope:** full set of available/selectable models per harness (not just the one currently pinned in config).
5. **Capability tracking granularity:** provider-native capabilities (tool use, vision, context window, etc.) rather than a synlynk-invented abstraction layer.
6. **Calibration:** auto-triggered sweep on new-model-detection (via `synlynk probe`'s diff against `harness_models`) AND a richer, difficulty-graded task pool per charter Agent role (replacing the current fixed 3-skill/1-template design) — extends `capability_sweep.py` rather than replacing it.
7. **Routing:** new models get an explicit "explore" bonus at Stage 0 of `_best_agent_for_story()` (ahead of the existing historical Stage 1) so they aren't starved by the cold-start `None` return, without disturbing proven Stage 1→2→3 scoring for already-calibrated models.
8. **Out of scope:** competitive landscape SWOT (Hermes Agent, Open Claw, Opencode, Openrouter, Pi Agent) is a separate, parallel-running track with no dependency on this spec.

## Plan A: Rename classification & migration

### Classification rules

| Rule | Meaning → renamed to | Applies when |
|---|---|---|
| 1 | Harness (execution backend) | Refers to which CLI runs a task: claude/codex/agy/grok/local, CLI contracts, quotas, dispatch flags, model pairing |
| 2 | Agent (role/charter) — **leave alone** | Refers to the 8 charter roles or charter identity introduced by PR #1003/#1030 |
| 3 | Container misnamed, internals already correct | Rename the container only; internal fields already disambiguate |

### Concrete classifications (confirmed by recon this session)

| Symbol | Rule | Action |
|---|---|---|
| `harness_baselines`, `harness_records`, `harness_verb_map`, `harness_command_palette`, `harness_version_history` | — | Already correct, no change. (Note: `harness_records`'s primary key column is still literally named `agent_name` — Rule 1, rename to `harness_name` for internal consistency even though the table itself is already correctly named.) |
| `AGENT_CAPABILITY_BASELINES` (`synlynk/_constants.py`) | 1 | Rename → `HARNESS_CAPABILITY_BASELINES` |
| `capability_sweep.py`'s `agent` variable/params throughout | 1 | Rename → `harness` |
| `agent_quotas` table + its `agent` column (`synlynk/db.py`) | 1 | Rename table → `harness_quotas`, column → `harness` (paired with `model` — this is CLI rate-limit data, not role data) |
| `agent_reservations` table (`synlynk/db.py`) | 3 | Rename table → `harness_reservations`; its existing `harness TEXT NOT NULL` column is untouched |
| `daemon_jobs.agent_id` (`synlynk/db.py`, `cli.py`, `dispatch.py`) | 2 | **Do not rename** — genuine charter identity from Agent-roles-charters Phase 1 |
| `stories.role` | 2 | Already correct, no change (good precedent for how Agent-role fields should be named) |
| CLI verb `synlynk agent` → `synlynk harness` | — | Already done, PR #993 |

### Audit process for the remaining ~2,000 occurrences

The remaining occurrences (34 source files, 59 test files, 331 doc files, 18 CLI flags) cannot be hand-classified in a design doc. Plan A's first implementation task is a **dispatched audit**: give the classification rules above plus a grep-generated worklist to Codex/Grok, have it tag every occurrence `RENAME` / `KEEP` / `AMBIGUOUS`, then Claude (PM/review role) reviews only the `AMBIGUOUS` bucket before the mechanical rename executes across the rest.

### DB migration

Table/column renames go through the existing `synlynk migrate` schema-version path, using `ALTER TABLE ... RENAME COLUMN` / `ALTER TABLE ... RENAME TO` (SQLite 3.25+, already the project's floor), gated the same way `_is_migrated()` gates other schema changes in `synlynk/db.py`.

### CLI flag deprecation

The 18 affected CLI flags are user-facing. Each renamed flag keeps its old name as a deprecated alias for one full named release (prints a deprecation warning, forwards to the new flag's behavior), removed in the following named release — never a hard break mid-cycle.

## Plan B: Capability registry v2

Builds on the Plan A-cleaned `harness_*` naming. Four new tables in `synlynk/db.py`:

### `harness_models` — live model roster per harness

```sql
CREATE TABLE IF NOT EXISTS harness_models (
    harness_name TEXT NOT NULL,
    model_id TEXT NOT NULL,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    status TEXT NOT NULL,          -- 'active' | 'superseded' | 'deprecated'
    superseded_by TEXT,            -- nullable, model_id
    discovery_source TEXT NOT NULL,-- 'self_report' | 'curated' | 'hybrid'
    PRIMARY KEY (harness_name, model_id)
);
```

Populated by `synlynk probe`: self-report first (parse the harness CLI's own model-listing output where available), `HARNESS_CAPABILITY_BASELINES` curated fallback otherwise — mirrors the existing hardcoded-fallback pattern already in `capability_sweep.py`'s `_discover_models()`.

### `harness_modes` — evolving tools/skills/flags per harness generation

```sql
CREATE TABLE IF NOT EXISTS harness_modes (
    harness_name TEXT NOT NULL,
    cli_version_range TEXT NOT NULL,
    mode_type TEXT NOT NULL,       -- 'flag' | 'skill' | 'config'
    mode_name TEXT NOT NULL,
    shape TEXT,                    -- JSON: expected args/schema
    PRIMARY KEY (harness_name, cli_version_range, mode_type, mode_name)
);
```

Extends the existing `harness_command_palette` pattern (which already tracks commands per version) with the flag/skill/config layer palette doesn't cover — directly answers Nikhil's point about targeting the right instructions/flags to the right harness generation.

### `capability_calibration_tasks` — difficulty-graded pool per charter Agent role

```sql
CREATE TABLE IF NOT EXISTS capability_calibration_tasks (
    task_id TEXT PRIMARY KEY,
    role TEXT NOT NULL,            -- pm|architect|tpm|dev|designer|qa|marketing|synlynk-bot
    skill TEXT NOT NULL,
    difficulty TEXT NOT NULL,      -- 'basic' | 'intermediate' | 'advanced'
    prompt_template TEXT NOT NULL,
    created_at TEXT NOT NULL
);
```

Replaces `capability_sweep.py`'s current fixed `_CALIBRATION_SKILLS = ["PROG", "TEST", "REQM"]` / single generic template with a real pool, seeded with at least one task per (role × difficulty) combination before the sweep is considered ready for that role.

### `capability_calibration_results` — links a sweep run to model + task

```sql
CREATE TABLE IF NOT EXISTS capability_calibration_results (
    result_id TEXT PRIMARY KEY,
    harness_name TEXT NOT NULL,
    model_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    score REAL NOT NULL,
    cost_usd REAL NOT NULL,
    verified_by TEXT NOT NULL,
    run_at TEXT NOT NULL,
    FOREIGN KEY (task_id) REFERENCES capability_calibration_tasks(task_id)
);
```

Feeds the existing `capability_ratings` table (does not replace it) — keeps `_best_agent_for_story()`'s Stage 1 historical scoring untouched.

### Auto-trigger

`synlynk probe` diffs the harness's reported/curated model list against `harness_models`. Any model_id not yet present gets a calibration sweep auto-queued through the existing `_run_sweep()` machinery: same `_pick_verifier_agent()` anti-self-attestation guard (never the harness/model being calibrated verifying itself), same `_DEFAULT_SWEEP_COST_CAP_USD` ceiling and `_estimate_sweep_cost()` pre-check, same `SystemExit(1)` abort-over-cap behavior — only the trigger changes, from manual invocation to discovery-driven.

### Routing integration

Add a Stage 0 to `_best_agent_for_story()` (`synlynk/jobs.py` ~line 1056), ahead of the existing Stage 1 capability score: if a `harness_models` row is `status='active'` with zero or only `phantom_sample_count`-only rows in `capability_ratings`, apply a small explicit "explore" bonus so new/superseding models get organically tried rather than being starved by the cold-start `None` return from `_capability_candidates_for_story()`. The bonus is bounded — it never overrides a well-calibrated cheaper option beyond the existing `_CAPABILITY_COST_TIE_GAP` tie-break window, so it nudges exploration without destabilizing proven routing.

## Testing

**Plan A:**
- Each renamed symbol gets a regression test asserting the old name is gone and the new name behaves identically.
- Migration tests: `ALTER TABLE RENAME` is idempotent, pre-existing rows survive with unchanged data.
- CLI flag deprecation tests: old flag name still works and prints a warning; new flag name works silently.
- `daemon_jobs.agent_id` retention: an explicit regression test asserting this column and its call sites (`cli.py:1156/1180`, `dispatch.py:173/839/2072/2620`) are unchanged by the rename — guards against the exact risk this design surfaced.

**Plan B:**
- `harness_models` diff-detection test: new model_id appears in probe output → sweep auto-queued, cost cap respected.
- `_pick_verifier_agent()` test: verifier is never the harness/model currently being calibrated.
- Stage 0 routing test: explore bonus applies only to thin/zero-data active models; never overrides a well-calibrated cheaper option beyond `_CAPABILITY_COST_TIE_GAP`.
- Calibration task pool completeness test: sweep refuses to run for a role until at least one task exists per difficulty tier for that role.

## Out of scope

- Competitive landscape SWOT (Hermes Agent, Open Claw, Opencode, Openrouter, Pi Agent) — separate, parallel-running track, no dependency on this spec's data model.
- One-time manual qualitative capability audit of current harness generations — this spec builds the *mechanism* (registry + auto-calibration) that produces that data organically; a standalone audit document is unnecessary once the sweep is live.
- Full 331-doc-file sweep as an itemized checklist in this spec — tracked inside Plan A's dispatched audit task instead; doc references are text, not load-bearing code, so a stale doc reference is a doc bug, not a correctness risk.
- Multi-repo/workspace-level harness registries (`#914`, already flagged in the roadmap as its own not-yet-scoped future brainstorm) — this spec is single-repo/single-workspace only.
