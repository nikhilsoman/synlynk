# Design: Three-Lens Review Follow-ups (#2062, #2063, #2064, #2065, #2076)

> Source: `docs/reviews/2026-10-05-three-lens-strategic-review.md` Cross-Lens
> Top 7, triaged into decision `dec-19555009`
> (`project-docs/decisions/2026-10-06-review-docs-reviews-2026-10-05-three-len.md`),
> which filed #2062-#2065. This brainstorm produced a fifth issue, #2076,
> split out of #2062 during design (see §D).

## Overview

Four independent, mostly small fixes. Each section below is scoped as its
own implementation unit (separate PR), reviewed cross-harness per existing
policy. They share no code dependencies on each other and can be dispatched
in parallel.

## Section A — #2063: Un-suspend empirical routing with sample-size fallback

**Problem.** `README.md` asserts live, proven routing ("routes tasks to the
best available harness using a live capability ledger") while
`.synlynk/policy.json`'s `capability_policy.mode` is `empirical` but
`suspended_since: 2026-10-04`, with `min_sample_size: 5` not met and
`grok`/`muse` `not_yet_calibrated`. The suspension was temporary — imposed
over one weekend because of failures caused by the GOVERNS-adherence
hardening work, which has since shipped (this session's
`docs/superpowers/plans/2026-10-06-governs-velocity-unblock-plan.md`, all 4
items merged). The suspension should now lift, with real fallback behavior
underneath it rather than a bare flag flip.

**Current state corrected in-session (supersedes an earlier, inaccurate
pass over this section):** three distinct capability-tracking mechanisms
exist, and none of them is what naive reuse would suggest:

- `synlynk/capability.py`'s `capability_score()`/`route_expected_value()`
  operate on `capability_ledger`, a Bayesian alpha/beta success-probability
  table keyed by `(model_id, harness, task_domain)`. Its own docstring says
  it's "deliberately" kept separate from `capability_ratings`. This is not
  the metric CLAUDE.md's Empirical Capability Assessment Policy names
  (median `pr_review_cycles`/`total_cost_usd`), so it is **not** reusable
  for this fix.
- `capability_scores` (a VIEW over `capability_ratings`, defined in
  `synlynk/db_schema.py:571-591`) already computes a recency-decayed
  `weighted_score` (quality-based, not `pr_review_cycles`/cost) and
  `sample_count`, grouped by `agent, model_version, discipline, engg_domain,
  org_domain, role, stage, industry, phase`. This is the view
  `_get_local_capability_score()` in `dispatch.py:91-113` reads, filtered to
  `agent='local'`, for the existing single-candidate local-vs-fallback
  threshold decision. It has no `cost_entries` join and no `task_type`
  column, and it isn't consulted today for cross-harness ranking.
- `capability_ratings` itself (`synlynk/db_schema.py:107-142`) has no
  `task_type`/`task_domain` column at all — the closest existing dimension
  is `discipline` (free text, default `'backend'`). It joins to
  `cost_entries` via `story_id` (confirmed via `_cross_harness_review_verdict()`
  in `synlynk/db.py:233+`), which is where `total_cost_usd` actually lives.

So un-suspending genuinely requires **new aggregation SQL**, not a
generalization of existing code — there is no existing function that
returns median `pr_review_cycles`/`total_cost_usd` per `(harness, task_type)`
with a sample-size gate.

**Correction to an earlier in-session claim:** this section previously
asserted #1926 (shard consolidation) is not a blocking dependency. That was
asserted without checking the live `.synlynk/policy.json`, which turns out
to already contain a `capability_policy.blocking_dependency` field stating
the opposite: "aggregate measurement unreliable while
capability_ratings/cost_entries are scattered across per-job workspace
shards, see gh:#1831" — matching CLAUDE.md's own Empirical Capability
Assessment Policy ("aggregate measurement requires state.db consolidation
(#1926, Track 3)... isn't reliably queryable in aggregate until that
lands"). Both documents agree with each other; my earlier claim was the
error. Resolution adopted here: scope Section A's routing query to the
**current workspace's own canonical `state.db`** only (per
`[[stray-local-state-db]]`, each workspace has one canonical db at
`~/.synlynk/workspaces/<name>/state.db` that its own dispatched jobs' cost
entries land in — this is not the cross-workspace shard-scatter problem
#1926/#1831 describe). Routing decisions are inherently per-repo anyway
(`task_allocation` lives in that repo's own `policy.json`), so a
single-workspace query is sufficient for this fix and does not need to wait
on #1926. Fleet-wide/cross-workspace aggregate reporting (the full `synlynk
capability report`, #1993) remains separately blocked on #1926 as
CLAUDE.md already states — this fix does not attempt that.

**Task-type mapping decision:** since `capability_ratings` has no
`task_type` column, the new query groups by `discipline` as the best
available existing proxy (matching `capability_scores`' own precedent of
grouping by `discipline` rather than inventing a parallel taxonomy). A row
is eligible for a given dispatch `task_type` when `discipline` matches it
case-insensitively; task types with no matching `discipline` rows simply
never clear the sample-size bar and fall back to the table, which is the
correct behavior (unmeasured means unmeasured).

**Fix:**

1. New function `synlynk/capability.py:ranked_harness_for_task(task_type,
   candidates, *, min_sample_size=5, conn=None) -> str | None` — queries
   `capability_ratings cr` JOIN `cost_entries ce ON ce.story_id=cr.story_id`
   (same join `_cross_harness_review_verdict()` already uses, confirmed in
   `synlynk/db.py:233+`), filtered to
   `cr.agent IN candidates AND lower(cr.discipline)=lower(task_type)`,
   grouped by `cr.agent`, computing `COUNT(*) AS sample_count`,
   `pr_review_cycles` median (SQLite has no built-in `MEDIAN()` — pull
   `cr.pr_review_cycles` values per group and compute in Python rather than
   SQL), and `AVG(ce.total_cost_usd) AS avg_cost_usd` (confirmed column name
   via `cost_entries`' definition at `synlynk/db.py:1485-1514`; note
   `cost_entries` has both an `agent` and a separate `harness` column — join
   and group on `ce.harness`/`cr.agent`, not `ce.agent`, since
   `capability_ratings.agent` holds harness identifiers like `'local'`,
   `'codex'`, `'grok'`, matching `cost_entries.harness`, not
   `cost_entries.agent`'s role-identity string). Returns the best candidate
   with `sample_count >= min_sample_size` that beats the incumbent (first
   element of `candidates`) on both metrics (lower median
   `pr_review_cycles`, lower `avg_cost_usd`), or `None` if no candidate
   qualifies.
2. In `dispatch.py:636`'s `compose_dispatch_preview()` (not
   `_resolve_dispatch_agent()`, which is local-specific) — this is where
   `policy.json`'s `overrides.dev_authority.task_allocation` table is read
   to compute the human-facing dispatch default. `policy.json`'s entries are
   already shaped for ranked substitution (e.g. `"implement": {"harness":
   "codex", "fallback": ["grok", "agy"]}`). Before returning
   `allocation[task_type]["harness"]`, call
   `ranked_harness_for_task(task_type, [harness] + fallback)`; if it returns
   a harness, prefer it; otherwise return the table's `harness` entry
   unchanged.
2. `.synlynk/policy.json`'s `capability_policy` block (confirmed live
   content in-session — it already has `mode`, `suspended_since`,
   `suspended_rationale`, `min_sample_size`, `metrics`, `metric_source`,
   `blocking_dependency`, `not_yet_calibrated`, `generator_status`, `note`):
   - Remove `suspended_since` and `suspended_rationale`.
   - Keep `min_sample_size: 5` and `not_yet_calibrated: ["grok", "muse"]`
     (still accurate — they fall back to the table until they individually
     clear 5 samples on a given task_type).
   - Rewrite `blocking_dependency` — it currently reads "aggregate
     measurement unreliable while capability_ratings/cost_entries are
     scattered across per-job workspace shards, see gh:#1831" and names
     gh:#1926, which is accurate for *cross-workspace* aggregation (matches
     CLAUDE.md's own Empirical Capability Assessment Policy) but was, before
     this section's self-correction above, wrongly read as blocking
     *this* fix. Reword to state explicitly that single-workspace routing
     (this fix) queries only the current repo's own canonical `state.db`
     and does not wait on #1926; #1926/#1993 remain required only for
     fleet-wide `synlynk capability report` aggregation.
   - Update `generator_status` and `metric_source` only if their wording no
     longer matches reality after (1) ships; otherwise leave unchanged.
3. `README.md:15` (checked live content in-session — line 5's banner text
   is generic enough to already be accurate and doesn't need changing;
   only line 15's "routes tasks to the best available harness using a live
   capability ledger" is the overclaim): replace with accurate present-tense
   language — empirical routing is live, per workspace, and promotes a
   harness once it clears the sample-size bar with better measured outcomes
   *in that workspace's own data*, falling back to a default allocation
   table below that threshold. This description is literally true once (1)
   and (2) ship, rather than aspirational.
4. `policy.json`'s existing `capability_policy.note` field already asks a
   future editor to update `task_allocation` + `docs/harness-capability-
   baseline.md` together when a harness is promoted. Extend that same
   sentence to also name `README.md`'s routing-claim sentences, so a future
   suspension (or re-suspension) remembers to update all three together —
   this is the concrete fix for the "contradicts each other" root cause,
   not just today's symptom.

**Verification:** unit test with a seeded `capability_ratings`/`cost_entries`
fixture giving one non-local harness 5+ samples with better metrics than the
incumbent `task_allocation` entry for a task_type — confirm dispatch routes
to it. A second fixture with <5 samples — confirm fallback to the table.
Regression test confirming the existing local-threshold routing path is
unchanged.

## Section B — #2064: Durable logging of dispatch routing fallback

**Problem.** `dispatch.py:_preflight_local_silent()` (line ~75) and
`_resolve_dispatch_agent()` (line ~130) already print a fallback decision to
stdout in real time (e.g. `"Routing to: codex (local oMLX unreachable)"`).
The real gap, confirmed by reading the current implementation, is that this
message is never persisted — it's invisible to anyone inspecting job history
after the fact, matching the same fingerprint class as #2048 (cold-start
tiebreak misattribution).

**Scope decision:** durable logging only, no behavior change. The issue
title's "fail closed" framing is not implemented here — only its visibility
half.

**Fix:**

1. At each of `_resolve_dispatch_agent()`'s two existing fallback print
   sites, also write an entry to `sentinel.md` using the same helper this
   session's plan item 4 added for the GOVERNS-linkage preflight warning
   (`docs/superpowers/plans/2026-10-06-governs-velocity-unblock-plan.md`
   §4) — reuse rather than duplicate.
2. Persist the same fact (requested harness vs. actual harness, and the
   precondition that triggered the fallback) into job metadata, so
   `synlynk jobs` and cost attribution can surface "dispatched as local, ran
   as codex" instead of reporting only the substituted harness with no
   trace.
3. No change to `_preflight_local_silent()`'s return value or
   `_resolve_dispatch_agent()`'s control flow.

**Verification:** dispatch with local unreachable; confirm `sentinel.md`
gains an entry and the job's metadata records both the originally-requested
and actual harness. Confirm existing stdout message is unchanged (no
duplicate print, no behavior regression).

## Section C — #2065: JSON Schema validation for config.json/policy.json via `synlynk doctor`

**Problem.** `.synlynk/config.json` (120+ lines: billing, workspace,
harness_billing, agent_slots, swarm_runners, sentinel) and
`.synlynk/policy.json` have no schema validation. The issue's own body
references "ad-hoc checks scattered in `synlynk/config.py`" — confirmed
in-session that this file does not exist; config-loading is actually
scattered across ~19 files (`cli.py`, `dispatch.py`, `doctor.py`, `status.py`,
`coldstart.py`, and others) that each read the JSON directly. The
underlying diagnosis (sprawl, no central validation) holds even though the
cited filename is wrong.

**Constraint.** `pyproject.toml` declares `dependencies = []` — stdlib-only,
repeatedly emphasized as a project-wide invariant. No `jsonschema` PyPI
package or any other third-party dependency.

**Fix (P1-1 scope only — P1-2's full decomposition into
`workspace.json`/`billing.json`/`policy.json` is a separate, larger
follow-up, not bundled here):**

1. New module `synlynk/config_schema.py`: a hand-rolled, minimal validator
   using only `json` and plain dict/type inspection — no external schema
   library. Define two schema dicts (field name → expected type,
   required/optional, allowed enum values where relevant) for
   `.synlynk/config.json` and `.synlynk/policy.json`. A
   `validate(data: dict, schema: dict) -> list[str]` function returns
   human-readable error strings (empty list = valid). The known, bounded key
   set in both files makes a full JSON Schema implementation (nested
   `$ref`, etc.) unnecessary.
2. Two new `doctor.py` checks following the existing `_hc_*() -> HealthCheck`
   pattern (same shape as the ~35 existing checks, e.g. `_hc_project_init()`,
   `_hc_identity_roles()`): `_hc_config_schema()` and `_hc_policy_schema()`,
   each loading its file and running it through `config_schema.validate()`,
   reporting a `HealthCheck` failure naming the specific bad key/type.

**Verification:** unit tests feeding `config_schema.validate()` a known-good
fixture (no errors) and fixtures with a wrong type, a missing required key,
and an invalid enum value (each producing the expected error string).
Integration test confirming `synlynk doctor` surfaces a failing
`_hc_config_schema()`/`_hc_policy_schema()` check when a malformed
`config.json`/`policy.json` is present.

## Section D — #2062: Adapter conformance test suite (scope narrowed during brainstorm)

**Problem.** No per-adapter conformance test exists for the three
properties that matter across harnesses: the `SYNLYNK_TASK_RECEIVED:
<sha256>` receipt marker, cost attribution landing in `cost_entries`, and
timeout handling. Quality drift (e.g. the Grok LIVE-13 permission-bypass
regression, since fixed) was only caught live.

**Scope change from the original issue text.** The issue's second half
("retire the incomplete strangler path") assumed `LegacyAdapter` was a
competing dispatch path for already-registered harnesses. Confirmed
in-session it is not: `LegacyAdapter`
(`synlynk/harness_adapters/legacy.py:13`) is reached only via the
`except KeyError` fallback in `dispatch.py:3741-3747`, when `get_adapter()`
doesn't recognize a harness name — i.e. a catch-all for unregistered names,
not a second path for the 5 known harnesses (`claude`, `codex`, `agy`,
`grok`, `local`, all registry-backed).

During brainstorm, replacing that catch-all with a hard error was considered
and rejected: a legitimate long tail of future harnesses exists that would
hit it — OpenRouter, a self-hosted LiteLLM proxy, or direct access to any
OpenAI-compatible endpoint, all reachable via a generic chat-completions HTTP
API with no CLI wrapper. (IDE-embedded assistants — Cursor, VS Code Copilot,
Pi — were considered and excluded: they're interactive/human-attended with
no non-interactive invocation surface, so they are not dispatch targets at
all.) Building that generic adapter is real scope, not something to rush
into this fix, so it was split out as **#2076** and deferred. `LegacyAdapter`
is therefore left untouched by this issue.

**Fix (narrowed to conformance tests only):**

1. Shared conformance test harness (new `synlynk/harness_adapters/tests/`
   module, or extending wherever adapter tests already live) that each of
   the 5 registered adapters (`claude.py`, `codex.py`, `agy.py`, `grok.py`,
   `local.py`) must pass, parametrized over all 5:
   - Receipt-marker SHA256 verification.
   - Cost-entry write-through to `cost_entries`.
   - Timeout/cancellation behavior.
2. No change to `LegacyAdapter` or the `dispatch.py:3741-3747` fallback.

**Verification:** the conformance suite itself is the verification —
running it against each of the 5 adapters and confirming all 5 pass is the
acceptance criterion. A deliberately broken adapter (missing receipt marker)
should fail the suite, confirming the test actually catches drift.

## Follow-up issue filed during this brainstorm

**#2076** — "Add GenericAPIAdapter for OpenRouter/LiteLLM-proxy/direct
OpenAI-compatible endpoints." Split out of #2062's original "retire the
strangler" framing. Not designed yet — needs its own brainstorm before any
implementation, per the Brainstorm-First Policy.

## Sequencing

All four sections (A-D) are independent and can be dispatched in parallel,
each as its own PR with cross-harness review per existing policy. Section A
is the most load-bearing (it's a behavior change to live dispatch routing)
and should get the most careful review; B, C, D are lower-risk/additive.
