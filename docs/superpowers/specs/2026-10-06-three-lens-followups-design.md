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

**Current state confirmed in-session:** `synlynk/capability.py` already has
`capability_score()`, `route_expected_value()`, and a schema/`_ensure_table()`
for scoring — built for the existing local-harness routing threshold
(`_get_local_capability_score()` in `dispatch.py`). `capability_ratings` and
`cost_entries` live in the canonical `state.db` (not the scattered per-job
shards tracked by #1926/#1831), and are already queryable via `capability.py`
today. This means un-suspending does **not** require #1926 (shard
consolidation) or #1993 (the `synlynk capability report` CLI surface) — both
remain separately useful but are not blocking dependencies for this fix.

**Fix:**

1. Generalize the existing local-threshold scoring pattern to non-local
   routing. Confirmed in-session: `policy.json`'s `overrides.dev_authority
   .task_allocation` is keyed by `task_type`, each entry holding a `harness`
   (the current default) and a `fallback` list (e.g. `"implement": {"harness":
   "codex", "fallback": ["grok", "agy"]}`) — already shaped for a ranked
   substitution list, just not populated from measurement yet. The real
   consult site is `dispatch.py:636`'s `compose_dispatch_preview()` (not
   `_resolve_dispatch_agent()`, which is local-specific) — this is where the
   allocation table is read to compute the human-facing dispatch default.
   Before returning `allocation[task_type]["harness"]`, query `capability.py`
   for each of `[harness] + fallback`'s `(harness, task_type)` sample count
   and median `pr_review_cycles`/`total_cost_usd`. If any candidate has
   `>= min_sample_size` (5) samples and beats the current `harness` entry on
   both metrics, prefer it. Otherwise return the table's `harness` entry
   unchanged — identical fallback shape to the existing local-threshold
   logic, generalized across all task types instead of gating only the
   local/non-local decision.
2. `.synlynk/policy.json`: remove `suspended_since` and `suspended_rationale`
   from `capability_policy`. Keep `min_sample_size: 5`,
   `not_yet_calibrated: ["grok", "muse"]` (still accurate — they fall back to
   the table until they individually clear 5 samples on a given task_type).
3. `README.md`: replace the two asserting sentences (lines 5 and 15) with
   accurate present-tense language — empirical routing is live and promotes
   a harness once it clears the sample-size bar with better measured
   outcomes, falling back to a default allocation table below that
   threshold. This description is literally true once (1) and (2) ship,
   rather than aspirational.
4. Add a short note in `policy.json` next to `capability_policy` pointing
   back to `README.md`'s routing-claim sentences, so a future suspension (or
   re-suspension) remembers to update both files together — this is the
   concrete fix for the "contradicts each other" root cause, not just
   today's symptom.

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
