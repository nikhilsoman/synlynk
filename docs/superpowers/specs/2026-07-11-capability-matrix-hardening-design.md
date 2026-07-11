# Capability Matrix Hardening — Epic Design

**Date:** 2026-07-11
**Author:** Claude (PM role)
**Tracks:** #137 (epic), #138 (tags), #139 (scoring), #140 (cost), #141 (quota + optimizer)
**Status:** Approved for dispatch, starting with #138

## Problem

The capability matrix that drives agent routing (`_best_agent_for_story()`) is built on
free-text fields with no validation, a scoring formula that only wires 3 of 5 designed
signals, a cost model that ignores which model actually ran, and a quota subsystem that
was designed (`docs/brainstorm/state-db-agentic-pm/design-token-budget.html`) but never
built. Four issues, one root cause: **nothing enforces the taxonomy the design docs
already specify, so live data has drifted away from it.**

- **#138** — `cmd_story_create` (`synlynk/db.py:832`) accepts `--engg`/`--org` as free
  text defaulting to `"unknown"`. Live `capability_scores` data confirms drift:
  `engg_domain` values include `cli`, `test`, `testing`, `backend` (2 of 6 are canonical);
  `org_domain` includes `developer_experience`, `marketing` (neither canonical); `phase`
  has two unreconciled taxonomies in production (`bootstrap/build/scale/research`) vs.
  design (`architect/build/verify`). `role` doesn't exist as a per-task field at all —
  `AGENT_CAPABILITY_BASELINES["roles"]` is a per-*agent* static declaration, conflated
  with what should be a per-task dimension.
- **#139** — `_write_capability_rating()` (`__init__.py:1394-1520`) only computes 3 of 5
  designed AUTO signals (`test_pass_rate`, `build_success`, `dispatch_rework`-penalty);
  `pr_review_cycles`, `verified_by_ci`, `duration_vs_estimate` are always NULL. No
  peer-agent VERIFIER signal is wired despite the 3-tier hierarchy being fully designed.
- **#140** — `extract_tokens()` (`__init__.py:6982-7059`) only scrapes input/output
  totals, no cache/tool breakdown. `update_costs()` (`__init__.py:7061+`) uses one flat
  hardcoded rate regardless of `model_version`.
- **#141** — `agent_quotas` table was designed (hourly/daily/weekly/monthly, headroom
  computed) but never created. Routing has no quota-headroom filter stage at all — the
  3-stage sequence (capability → quota → cost) designed in
  `design-token-budget.html` is currently 1-stage.

## GOVERNS resolves #138(d)

The "GOVERNS" blocker is resolved. It's the seven-stage SDLC model, already designed,
decided, and merge-ready on branch `chore/sdlc-goal-design` (2 commits, docs-only, not
yet merged into `main`):

- `docs/superpowers/specs/2026-07-11-business-goal-sdlc-model-design.md` — the spec
- `project-docs/decisions/2026-07-11-third-round-amending-our-locked-decision.md` — the
  4-agent panel decision that finalized Notify/Sustain semantics
- `docs/superpowers/plans/2026-07-11-governs-stage-rollout-plan.md` — the rollout plan
  that renames `CYCLES` in `hud.py` from the drifted 6-value vocabulary to the locked 7:

```
goal → open → visualize → execute → release → notify → sustain
```

**Dependency:** `chore/sdlc-goal-design` must merge before #138(d) can reference
`synlynk.hud.CYCLES` as the single source of truth for the `stage` enum. #138 should
reuse `CYCLES` directly rather than re-declaring a parallel taxonomy — `capability_ratings.stage`
takes the same 7 values, classified via the same `task_to_cycle` map `_recommend_handoff_agent`
already uses (Task 3 of the rollout plan) once it lands.

**`phase` is a separate, unrelated dimension — do not conflate with `stage`.** The
production `bootstrap/build/scale/research` values describe *project/product maturity*,
not *task execution stage*. Reconciling `phase` against the originally-designed
`architect/build/verify` is in scope for #138 as its own sub-fix, but the fix is to
rename the design-doc's stale `phase` values to match production usage (or vice versa
via a real migration) — not to merge `phase` into the new GOVERNS `stage` column. Keep
them as two distinct NOT-NULL columns.

## Sequencing (dependency order)

```
chore/sdlc-goal-design (merge first — unblocks #138d)
        │
        ▼
      #138 (tags) ──┬──> #139 (scoring)  ──┐
                     │                       ├──> #141 (quota + optimizer)
                     └──> #140 (cost)     ──┘
```

#139 and #140 can run in parallel once #138 merges. #141's base quota matrix depends on
neither #139 nor #140 functionally, but per the epic's own sequencing note, the
optimizer *design* pass should wait until the matrix is proven reliable — don't build a
scheduler on top of scores/costs that are still drifting.

## Scope decisions per sub-area

**#138 — tags**
- `org_domain`: keep the 9-value canonical enum from the 2026-06-14 design doc. Add a
  migration mapping table for drifted values found live: `developer_experience` → `platform`,
  `marketing` → `growth`. Any other unmapped drift value migrates to `unknown` with a
  logged warning, not silently.
- `engg_domain` → split into `discipline` (enforced 9-value enum, unchanged from design
  doc) × `stack_tags[]` (free normalized array, sourced from existing workspace language
  detection, not hand-typed).
- `role`: new enum `architect, dev, pm, tpm, qa, designer` — cross-reference the TPM/
  Release/Support-Engineer agent design specs so the enum covers persona types already
  speced elsewhere in the repo.
- `stage`: reuse `CYCLES` from `hud.py` post-merge (see above).
- All four become `NOT NULL` with enum validation at both `synlynk story create` and
  `_write_capability_rating()` write time.
- `gemini` / bare `unknown` agent identities: register in `AGENT_CAPABILITY_BASELINES`
  or reject at write time — do not let unregistered agents write rating rows.

**#139 — scoring**
- Wire the 2 remaining dead AUTO signals: `pr_review_cycles` (count review-request →
  approval round trips via the same git/PR data #127's `files_touched` fix already
  reads), `verified_by_ci` (read CI status if available, else leave NULL and re-weight
  rather than treat as 0).
- Add the VERIFIER tier: peer-agent rating via `synlynk-meta` block, weight 0.85 per the
  existing 3-tier design — this is also the mechanism for dogfooding Agy's review pass
  on #138/#140 PRs described below.
- Keep `dispatch_rework` (routing-significant) and `micro_rework` (informational) as
  two distinct signals per the original design — do not merge them.

**#140 — cost**
- Extend `extract_tokens()` to capture cache/tool breakdown where the CLI output format
  provides it (Claude and Codex both emit cache token counts today — confirm via a
  sample transcript before assuming Agy/Grok do too).
- Replace `update_costs()`'s flat rate with a per-`model_version` rate table. Source
  rates from the same models already named in `AGENT_CAPABILITY_BASELINES` plus a
  fallback default for unrecognized versions.
- Add `story_id`/`epic_id`/`phase_id` FK columns to `costs` per the
  `design-token-budget.html` schema — this is what makes "$per task" queryable instead
  of only "$ per session."

**#141 — quota matrix (base)**
- Build the designed-but-never-created `agent_quotas` table: `quota_type`
  (hourly/daily/weekly/monthly), `limit_tokens`, `used_tokens`, `headroom` (computed),
  `reset_at`. Handle token-vs-request unit variance explicitly — store a `unit` column
  (`tokens` | `requests`) per harness rather than assuming tokens everywhere.
- Wire the quota-headroom filter as stage 2 of the 3-stage routing sequence (capability
  score → quota headroom → cost), matching the design doc.

**#141 — optimizer (follow-up design, not this dispatch)**
- Once the base matrix is live and scores/costs/quotas are trustworthy, write a
  standalone design doc for the scheduling/sequencing optimizer (maximize total output
  across a workspace's variable per-harness quotas, not just gate on headroom). Claude
  owns this as an architect-role follow-up — no code in this pass.

## Assignment

| Work | Agent | Role-split lane |
|---|---|---|
| #138 schema/enum/migration | Codex | CLI plumbing, refactoring |
| #138 taxonomy supersets (domain/competency lists) + docs | Agy | Content |
| #139 signal wiring + weight formula | Codex | CLI plumbing, refactoring |
| #139/#140 PR review pass | Agy | Verifier role, peer-review dogfooding |
| #140 token/cost extraction + rate table | Codex | CLI plumbing |
| #141 base quota table + routing filter | Grok | Complex data structures |
| #141 optimizer design doc | Claude | Architect |

## Scope of this dispatch

This first dispatch covers **#138 only**, and only after `chore/sdlc-goal-design`
merges. Do not start #139/#140/#141 until #138 merges — they all read the tag columns
#138 defines.
