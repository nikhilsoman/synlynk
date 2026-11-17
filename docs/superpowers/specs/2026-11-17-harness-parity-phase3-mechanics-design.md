# Harness Parity Phase 3: Implementation Mechanics Design

## Status

Design only. Implements the mechanics authorized by the Phase 2 decision in
`project-docs/decisions/2026-11-17-harness-parity-governance-gate-calibrati.md`
(panel: claude, agy, codex, muse). That decision closed Investigation 1 (live
harness trial) and Investigation 2 (instruction-uniformity audit) as evidence,
and authorized this Phase 3 spec to work out concrete file-level mechanics for
the nine hard requirements it lists. No code or config has shipped yet; this
document is the spec gating the next implementation plan
(`docs/superpowers/plans/`), per this repo's Design → Plan → Build sequence.

## Goals (traceable to the nine hard requirements)

1. Any available harness is ready for work at all times (req. 1).
2. All task types are assignable to all harnesses as a matter of policy — no
   structurally privileged or structurally excluded harness (req. 2, 7).
3. Actual allocation of a given task is determined entirely by measured
   capability/cost track record for that task type (req. 3).
4. Every harness runs with its own native, validated configuration — flags,
   models, auth, MCP tools — confirmed by a real run, never assumed (req. 4).
5. A CLI version change for a harness triggers rediscovery of its model list
   and flag/command accessibility before it is trusted again (req. 5).
6. Every harness capable of MCP calls has that capability verified, not
   assumed (req. 6).
7. A single command onboards a new harness end-to-end (req. 8).
8. The only legitimate reason a harness is unavailable is its own quota
   exhaustion — never an synlynk-side policy/config block (req. 9). This spec
   names and closes the two concrete violations Investigation 1 found: the
   Muse budget-ledger disconnect and the "local" silent reroute.

## Non-Goals

- Building a real local-model execution backend (Ornith+Aider+oMLX). Out of
  scope for this spec; `local` remains an explicit-opt-in reroute target
  until that backend exists (see Section 6).
- Building the full `synlynk capability report` generator (gh:#1993). Routing
  in this spec queries `capability_ratings`/`cost_entries` live at dispatch
  time instead (Approach 1, chosen over a precomputed/regenerated artifact —
  see "Routing Approach" below). gh:#1993 remains a separate, larger piece of
  future work if a precomputed artifact is later wanted for performance.
- Changing `merge_authority` (`can_merge`, `cross_harness_review_required`,
  `require_non_authoring_review`). Those are role/identity invariants, not
  task-type eligibility, and are unaffected by this spec.
- Grok-specific quota remediation. Grok's standing quota exclusion is an
  external fact (its own quota exhaustion), not a defect this spec fixes.

## Amendments (Phase 3 spec review, 2026-11-17)

A separate `synlynk decide --panel claude,agy,codex,muse` review of this spec
against external best practices, SOTA multi-model platforms, architecture
patterns, and build-vs-wrap alternatives (recorded in
`project-docs/decisions/2026-11-17-comprehensive-architecture-review-of-the.md`)
endorsed the spec's core shape unanimously and recommended seven amendments,
folded into the sections below:

1. A composite DB index backing the live routing query (Section 2).
2. A `manifest_schema_version` field on the per-harness manifest (Section 3).
3. Deterministic tie-breaking for the routing ranking step (Section 2).
4. Billing-field validation at probe/onboard time, not blind trust (Section 3).
5. A narrow `Router` interface boundary around routing logic (Section 2).
6. Named, tunable scoring constants instead of inline magic numbers (Section 2).
7. A tracked follow-up ticket for instruction-file-duplication centralization,
   out of Phase 3 scope (Section 1).

The same review rejected or deferred, as premature at synlynk's current
scale, standardizing on a single external gateway (OpenRouter/LiteLLM) in
place of per-harness adapters, and building a native synlynk harness —
neither changes this spec.

## Section 1 — Eligibility vs. Routing Split

**Eligibility** (policy, static, symmetric) is separated from **routing**
(runtime, evidence-driven, dynamic). Collapsing these into one mechanism is
exactly the failure mode the old fixed-lane table had: it conflated "may this
harness ever do this task type" with "should this harness do this specific
task," so a harness with no measured track record was *structurally* excluded
rather than merely *unweighted*.

### Policy changes

- `.synlynk/capability-roles.json` is retired. Its `roles` map (`claude`:
  `["pm", "review", "deploy", "brainstorm"]`, etc.) is replaced by nothing —
  eligibility is no longer expressed as a per-harness task-type allowlist.
- `.synlynk/policy.json`'s `overrides.dev_authority.task_allocation` block
  (the `implement`/`css`/`canvas`/etc. → fixed-harness-with-fallback-list
  table) is deleted in its entirety.
- `.synlynk/policy.json`'s `overrides.role_task_type_compat` block (`dev`,
  `qa`, `architect`, `pm` → allowed task types) is **retained unchanged**.
  This is a role→task-type compatibility gate (what a *role identity* like
  `qa` or `architect` is authorized to do), which is orthogonal to
  harness→task-type eligibility. It is not part of the retired fixed-lane
  table and this spec does not touch it.
- New `.synlynk/policy.json` top-level block:
  ```json
  "eligibility": {
      "mode": "universal",
      "excluded_harnesses": [],
      "note": "Every registered harness is eligible for every task_type by default (req. 2, 7). The only runtime exclusions are: missing dispatch adapter (get_adapter KeyError), a stale/unvalidated manifest (Section 4), exhausted quota/budget (Section 5), or Grok's existing sandbox-write capability_probe check. None of those are expressed here — they are runtime checks, not a policy list. This block exists so 'is harness X eligible for task type Y' always has one answer: yes, unless a runtime check below says otherwise."
  }
  ```
  `excluded_harnesses` stays empty under normal operation; it exists only as
  an explicit, auditable emergency kill-switch (e.g. a harness pulled for a
  security incident), never for routine capability shaping.

### Instruction-file changes (same PR)

- `CLAUDE.md`, `AGENTS.md`, `GEMINI.md`: delete the `## Your Role` role-lock
  section (and its "SUSPENDED" framing) and the `## Capability-Based Task
  Allocation` table entirely. Replace with one sentence: "Harness eligibility
  is universal (`.synlynk/policy.json`'s `eligibility` block); actual task
  routing is capability/cost-scored at dispatch time — see
  `docs/superpowers/specs/2026-11-17-harness-parity-phase3-mechanics-design.md`."
- `AI_INSTRUCTIONS.md` is already universal with no identity-local pin
  (confirmed, Investigation 2) — no change needed there.
- `.cursorrules` is absent from the checkout despite `init()`'s claim to
  write one (Investigation 2 finding) — out of scope for this spec; file a
  tech-debt ticket instead of fixing it here, since it's unrelated to harness
  parity mechanics.
- **Amendment 7 (decide-panel review):** `CLAUDE.md`/`AGENTS.md`/`GEMINI.md`
  each carrying their own near-duplicate copy of the eligibility sentence
  above is itself a tracked cost as harness count grows (noted independently
  by all four panelists under the sustainability agenda item). File a
  tech-debt ticket for a future centralization pass (e.g. one canonical
  `docs/harness-eligibility.md` that the per-harness instruction files
  `#include`/link to, rather than restating) — out of Phase 3 scope, since
  Phase 3's instruction-file edit here is a one-time deletion, not a new
  duplication pattern.

## Section 2 — Live Capability-Based Routing

### Routing approach (decided)

Three approaches were considered:

1. **Live query at dispatch time** (chosen). Dispatch computes routing scores
   on the spot from `capability_ratings`/`cost_entries`. Always fresh, no
   staleness window, no new generator to build.
2. **Precomputed artifact, periodically regenerated** into
   `policy.json`'s `task_allocation` via a new `synlynk capability report
   --regen` command. Matches policy.json's existing "generated output, not
   hand-edited" framing but requires building gh:#1993's generator now and
   accepts staleness between regenerations.
3. **Hybrid**: live query with a short in-process TTL cache.

Approach 1 is chosen: it is the simplest, has no staleness risk, and this
repo's dispatch volume does not justify caching's added complexity. gh:#1993
remains available as future work if query cost ever becomes a real problem.

### Implementation

New module `synlynk/routing.py`, structured as a narrow `Router` interface
rather than a bare function (**Amendment 5**) so a second scoring strategy
(e.g. a future gh:#1993 precomputed-artifact mode) can be swapped in later
without touching `dispatch.py`'s call site:

```python
class Router(Protocol):
    def score_harnesses(self, task_type: str, db, eligible: list[str]) -> list[tuple[str, float, int]]:
        """Return (harness, score, sample_count) sorted best-first, ties broken
        deterministically (see tie-breaking rule below).

        score is None-safe: a harness below min_sample_size is excluded from
        the ranking entirely (not scored at 0), so it never loses to an
        under-sampled competitor by a fabricated low score.
        """

class LiveQueryRouter:
    """Default Router: Approach 1, live query at dispatch time."""
    def score_harnesses(self, task_type, db, eligible): ...

# dispatch.py constructs one instance at module load and calls it; it does
# not call score_harnesses() as a bare function.
_default_router: Router = LiveQueryRouter()
```

- Queries `capability_ratings` for median `pr_review_cycles` per
  `(harness, task_type)` and `cost_entries` for median `total_cost_usd` per
  merged PR per `(harness, task_type)`, restricted to the last 90 days (same
  window the existing `AVG(quality)` measurement in policy.json's comment
  used — 14-day was too narrow for low-volume task types, 90-day balances
  recency against sample size).
- **Amendment 1 (query cost under growth):** the decide panel's Codex
  panelist flagged this as a blocking-grade risk, not a monitor-only one.
  Add a composite index on `state.db` backing both queries:
  ```sql
  CREATE INDEX IF NOT EXISTS idx_capability_ratings_harness_task
      ON capability_ratings (harness, task_type, created_at);
  CREATE INDEX IF NOT EXISTS idx_cost_entries_harness_task
      ON cost_entries (harness, task_type, created_at);
  ```
  Add both as a new migration (`synlynk/migrations/`, following the existing
  `mNNNN_*.py` numbering) in the same PR as `routing.py`. The implementation
  plan's testing section must include an `EXPLAIN QUERY PLAN` assertion that
  the routing query uses these indexes, not a table scan, so a regression
  here is caught in CI rather than discovered as dispatch latency later.
- A harness qualifies for ranking only once it has `>= min_sample_size`
  (read from `.synlynk/policy.json`'s existing `capability_policy.min_sample_size`,
  currently 5) completed+merged jobs for that exact `task_type`.
- Score = normalized rank combining lower `pr_review_cycles` (quality proxy)
  and lower `total_cost_usd` (cost proxy), equally weighted. Exact formula:
  `score = -(pr_review_cycles_median) - (total_cost_usd_median / SCORE_COST_DIVISOR)` —
  higher (less negative) is better. **Amendment 6:** `SCORE_COST_DIVISOR` is
  a named module-level constant in `routing.py` (default `10.0`, chosen for
  this repo's typical $2-$15 per-merged-PR cost range and typical 1-3
  review-cycle range), not an inline magic number. Per Codex's review
  comment, it is a `dict[task_type, float]` keyed by `task_type` with a
  `"_default": 10.0` fallback, so a task type whose cost/cycle ratio differs
  materially (e.g. `infra` jobs tend to run longer and cost more per cycle
  than `content` jobs) can be tuned independently without a code change to
  the formula itself — only a constant-table edit.
- **Amendment 3 (deterministic tie-breaking):** when two harnesses' scores
  are equal (common at low sample sizes, where medians collide), break ties
  by, in order: (1) higher `sample_count` (more evidence wins), (2) if still
  tied, alphabetical harness name. This is deterministic and auditable —
  never a random or insertion-order tiebreak — so a routing decision can be
  reproduced from `capability_ratings`/`cost_entries` state alone during a
  later audit.
- If zero eligible harnesses clear `min_sample_size` for the task_type,
  `score_harnesses` returns an empty ranked list and the caller falls back to
  round-robin: a `last_routed` cursor per task_type stored in a new
  `harness_status.last_routed_task_types` JSON column, advanced on every
  unscored dispatch so no single harness starves the others of a chance to
  accumulate samples (req. 1).
- `_resolve_dispatch_agent`'s `auto` path (dispatch.py, the `requested_agent
  == "auto"` branch) calls `_default_router.score_harnesses(task_type, db,
  eligible_harnesses)` instead of any fixed table lookup. `eligible_harnesses`
  is every harness with a registered adapter (`get_adapter` succeeds) minus
  any in `policy.json`'s `eligibility.excluded_harnesses` — this is the only
  place eligibility and routing meet, and it is a filter-then-rank, never a
  lookup-table substitution.

## Section 3 — Harness Manifest + Onboarding/Probe Commands

### Manifest schema

`.synlynk/harnesses/{harness}.json`, one file per harness:

```json
{
  "manifest_schema_version": 1,
  "harness": "codex",
  "cli_version": "1.4.2",
  "cli_version_hash": "sha256:9f8a...",
  "models": ["gpt-5.1-codex-luna", "gpt-5.1-codex-terra", "gpt-5.1-codex-sol"],
  "native_flags": {
    "approval_mode": "--approval never",
    "model_select": "--model",
    "output_format": "--output-format"
  },
  "auth_model": "oauth-device",
  "mcp_tools": ["filesystem", "github"],
  "last_validated_at": "2026-11-17T12:00:00Z",
  "last_validation": {
    "job_id": "job-7f3a9c1e",
    "passed": true,
    "notes": ""
  }
}
```

Field notes:
- **Amendment 2:** `manifest_schema_version` (integer, starts at `1`) is
  required on every manifest. `discover_and_validate` refuses to write a
  manifest without it, and any manifest reader (Section 4's preflight check,
  `synlynk harness onboard`/`probe`) that encounters a missing or
  higher-than-known `manifest_schema_version` treats the manifest as
  unvalidated (same as a version-hash mismatch, Section 4) rather than
  guessing at an unknown shape. This is what lets the manifest schema itself
  evolve later without silently misreading old files.
- `cli_version_hash` is `sha256` of the adapter's raw `--version` stdout —
  used for the cheap equality check in Section 4, not for display (display
  uses `cli_version`).
- `native_flags` is a flat map of logical-flag-name → actual CLI syntax,
  populated from each harness's own `HARNESS_CAPABILITY_BASELINES` entry in
  `synlynk/_constants.py` plus whatever the onboarding smoke run confirms
  actually works — never hand-authored to "look the same" across harnesses.
- `mcp_tools` lists only tools the smoke run actually exercised
  successfully this validation cycle, not a harness's theoretical MCP
  surface.
- `last_validation.passed: false` means the manifest exists but the harness
  is NOT eligible to be routed to until revalidated — this is the one case
  where a manifest's own state (not policy) legitimately blocks a harness,
  and it satisfies req. 9 because the harness's own validation failure is
  the reason, not an synlynk policy choice.

### Commands

- `synlynk harness onboard --harness <name>`: for a harness with no existing
  manifest. Steps: (1) call the adapter's version/help introspection, (2)
  write a draft manifest, (3) dispatch one real smoke-run task that exercises
  a native flag and at least one MCP tool call, (4) **(Amendment 4) validate
  `.synlynk/billing.json`'s `harness_billing[name]` entry exists and, for a
  non-subscription `payment_mode`, that `cost_per_1k_tokens` is present and
  a positive number** — a missing/invalid billing entry is a hard onboarding
  failure (`HARNESS_BILLING_CONFIG_INVALID`), not a silent skip, since
  Section 5's budget fallback depends on this value being trustworthy, not
  merely present, (5) on success, finalize the manifest with
  `last_validation.passed: true`; on failure, write the manifest with
  `passed: false` and print exactly what failed and why.
- `synlynk harness probe --discover --harness <name>`: same steps 1-5 for a
  harness that already has a manifest — used both by Section 4's
  version-mismatch trigger and for a manual re-check. Billing-field
  validation (step 4) re-runs every time, not only at first onboarding, so a
  `billing.json` edit that breaks a harness's rate is caught at the next
  rediscovery rather than silently trusted until a budget bug surfaces.
- Both commands share one internal function,
  `synlynk/harness_manifest.py:discover_and_validate(harness)` (inclusive of
  the Amendment 4 billing check and the Amendment 2 schema-version stamp),
  so onboarding and rediscovery can never drift into two different
  validation standards.

## Section 4 — CLI-Version-Triggered Rediscovery

- In `_resolve_dispatch_agent`'s preflight, before the existing baseline/auth
  checks, read the manifest for the resolved harness. Call the adapter's
  `--version`, hash it, and compare to `manifest["cli_version_hash"]`.
- **Match:** proceed normally.
- **Mismatch:** print `"Harness '{name}' CLI version changed ({old} ->
  {new}); revalidating before dispatch (req. 5)."`, synchronously run
  `discover_and_validate(name)` once, then retry the preflight once with the
  refreshed manifest. If the revalidation itself fails, the dispatch fails
  closed with `HARNESS_MANIFEST_REVALIDATION_FAILED` — this is a legitimate
  req.-9-compliant block (the harness's own CLI changed and didn't pass
  revalidation), not a policy block.
- **No manifest at all:** treat identically to a version mismatch — triggers
  onboarding inline rather than failing with a confusing "no manifest" error.
  This means a harness newly added to `HARNESS_CAPABILITY_BASELINES` without
  running `synlynk harness onboard` first gets onboarded automatically on its
  first real dispatch attempt, satisfying req. 8's "easy" bar without a
  required manual step blocking first use.
- This check is **event-triggered by dispatch**, never a polled background
  job — matches the Phase 2 decision's explicit framing.

## Section 5 — Muse Budget-Ledger Fix

### Root cause (confirmed, Investigation 1)

`synlynk/dispatch.py` (~4232-4262) reads `read_budget_tokens`,
`write_budget_tokens`, `tool_budget_count` from the `harness_status` table,
falling back to `synlynk/status.py`'s `TIER1_CAPACITY` dict if no row exists.
Muse has `TIER1_CAPACITY["muse"]` entries that are all `None`, and no
`harness_status` row, so `read_budget` resolves to `None` → the `0` comparison
in `est["input"] >= (read_budget or 0)` always trips, regardless of any
`credit_grants` balance. `credit_grants` is never consulted.

### Fix

```python
if cap_row and any(v is not None for v in cap_row):
    read_budget, write_budget, tool_budget = cap_row
else:
    tier1 = TIER1_CAPACITY.get(harness_name, {})
    read_budget = tier1.get("read_budget_tokens")
    write_budget = tier1.get("write_budget_tokens")
    tool_budget = tier1.get("tool_budget_count")
    if read_budget is None or write_budget is None:
        credit_row = db_conn.execute(
            "SELECT SUM(remaining_usd) FROM credit_grants "
            "WHERE agent=? AND (expires_at IS NULL OR expires_at > datetime('now'))",
            (harness_name,),
        ).fetchone()
        remaining_usd = (credit_row[0] or 0.0) if credit_row else 0.0
        if remaining_usd > 0:
            rate = _billing_rate_per_1k_tokens(harness_name)  # new helper, Section 5 below
            budget_tokens = int((remaining_usd / rate) * 1000)
            read_budget = read_budget if read_budget is not None else budget_tokens
            write_budget = write_budget if write_budget is not None else budget_tokens
            tool_budget = tool_budget if tool_budget is not None else 200  # TIER1 default floor
        else:
            read_budget = read_budget or 0
            write_budget = write_budget or 0
            tool_budget = tool_budget or 0
```

- New helper `_billing_rate_per_1k_tokens(harness_name)` in `dispatch.py`
  reads `.synlynk/billing.json`'s `harness_billing[harness_name]`. Add a
  `cost_per_1k_tokens` field to that file for any non-subscription harness:
  ```json
  "muse": {
      "payment_mode": "pay_as_you_go",
      "cost_per_1k_tokens": 0.02,
      "allow_extra_usage": true
  }
  ```
  (Value is a placeholder for the implementer to confirm against Muse's
  actual published rate at implementation time — this spec fixes the
  mechanism, not the number.)
- Net effect: a harness with a real `credit_grants` balance and no
  subscription-style `harness_status`/`TIER1_CAPACITY` row is no longer
  budget-blocked. A harness with neither a grant nor a subscription entry is
  still correctly blocked at `0` — this is genuine quota exhaustion (req. 9
  compliant), not a policy block.

## Section 6 — Local-Harness Reroute Fix

### Decision (per your answer)

Keep reroute-on-unavailable behavior for `local`, but require explicit opt-in
and guarantee the persisted record is never mislabeled `"local"`.

### Changes

- `_resolve_dispatch_agent` and the CLI's `dispatch` command gain a new
  `--allow-reroute` flag (default `False`). When the caller requests `local`
  (`requested_agent == "local"` or the `auto`/pilot path would otherwise
  silently substitute a fallback) and `--allow-reroute` is not set, dispatch
  **fails closed**:
  ```
  Dispatch refused: 'local' routing would substitute '<fallback>' (<reason>).
  Pass --allow-reroute to accept this substitution, or configure a working
  local harness adapter. See docs/superpowers/specs/2026-11-17-harness-parity-phase3-mechanics-design.md#section-6.
  ```
- With `--allow-reroute` set, existing behavior continues to call
  `_log_routing_fallback(message, requested="local", actual=fallback)` and
  `take_routing_fallback(agent)` (both already implemented, confirmed at
  `dispatch.py:276-301` and `:4728`) — no new plumbing needed for *capturing*
  the fallback, only for **using** it correctly downstream:
  - The job record's persisted `agent`/`harness` column is set to
    `actual_harness` from the routing-fallback record, never
    `requested_harness`, whenever a routing fallback exists for that job.
  - `cost_entries` and `capability_ratings` inserts for that job use the same
    `actual_harness` value.
  - `synlynk jobs`/`synlynk status` display format changes from a bare
    harness name to `"<actual> (rerouted from <requested>)"` whenever a
    job's `fallback_reason` field is non-null, so a human skimming job
    output can never mistake a rerouted job for a genuine `local` result.
- This directly closes the Investigation 1 finding: job-3ee659a3's PR #5336
  would, under this fix, either have been refused (no `--allow-reroute`) or
  recorded and displayed as `"agy (rerouted from local)"`, never silently as
  `"local"`.

## Section 7 — MCP Parity & Quota-Only-Unavailability (structural checks)

- Section 3's `discover_and_validate` smoke run must include at least one
  real MCP tool invocation for every harness whose adapter declares MCP
  support. A harness that declares MCP support but fails the MCP smoke-run
  step gets `last_validation.passed: false` with the specific failing tool
  named — req. 6 becomes a build-time gate, not a documentation claim.
- Implementation-time audit (not new code): before this PR merges, grep
  `synlynk/dispatch.py` and `synlynk/capability_probe.py` for every place a
  harness is rejected or rerouted, and confirm each site maps to one of:
  (a) missing adapter, (b) stale/failed manifest validation (Section 4), (c)
  budget/quota exhaustion per the corrected accounting (Section 5), or (d) an
  explicit `--allow-reroute`-gated substitution (Section 6). Any site that
  doesn't map to one of these four is a leftover policy-imposed block and
  must be fixed in this same PR, not deferred — this is what makes req. 9
  "only reason... never an active block imposed by synlynk policy" actually
  true rather than aspirational.

## Sequencing

Single coherent PR/plan (per the brainstorm brief's explicit instruction to
keep this as one spec unless genuinely too large). Suggested task order for
the implementation plan, each independently testable:

1. Section 1 (policy/instruction-file eligibility change) — no behavior
   change yet, just removes the fixed-lane table and role-lock text.
2. Section 2 (new migration for the two composite indexes, then `routing.py`
   as a `Router`/`LiveQueryRouter` pair + `auto` path wiring) — routing now
   live-scored, with the indexes landing first so the query-plan test has
   something to assert against.
3. Section 3 (manifest schema + onboard/probe commands) — new capability,
   additive.
4. Section 4 (version-triggered rediscovery) — depends on Section 3's
   manifest existing.
5. Section 5 (Muse budget-ledger fix) — independent bug fix, can run in
   parallel with 2-4.
6. Section 6 (local-reroute fix) — independent bug fix, can run in parallel
   with 2-5.
7. Section 7 (structural audit) — last, since it depends on everything above
   actually existing to audit against.

## Testing

- `routing.py`: unit tests for `LiveQueryRouter.score_harnesses` — below-floor
  exclusion, the deterministic tie-breaking order (sample_count then
  alphabetical, Amendment 3), empty-ranking round-robin fallback, and a
  `per-task_type SCORE_COST_DIVISOR` override actually changing the ranking
  (Amendment 6). A query-plan test asserting the routing query hits the new
  `idx_capability_ratings_harness_task`/`idx_cost_entries_harness_task`
  indexes via `EXPLAIN QUERY PLAN`, not a table scan (Amendment 1).
- `harness_manifest.py`: unit test for `discover_and_validate` against a
  fake/mocked adapter (pass and fail cases); no live harness CLI calls in
  the test suite. Additional cases: a manifest missing `manifest_schema_version`
  or carrying an unknown version is treated as unvalidated (Amendment 2); a
  missing or non-positive `cost_per_1k_tokens` for a non-subscription harness
  fails onboarding/probe with `HARNESS_BILLING_CONFIG_INVALID` (Amendment 4).
- Dispatch preflight: test that a version-hash mismatch triggers exactly one
  revalidation attempt, not an infinite loop, and fails closed if
  revalidation itself fails.
- Budget-ledger fix: unit test with a `credit_grants` row and no
  `harness_status`/`TIER1_CAPACITY` entry, asserting the dispatch is no
  longer blocked at the old `0`-budget error.
- Local-reroute fix: test that `dispatch local` without `--allow-reroute`
  raises/refuses; test that with the flag, the persisted job record's
  harness field equals `actual_harness`, not `"local"`.
- Manual verification: re-run Investigation 1's exact one-line-fix task
  against `local` (with and without `--allow-reroute`) and against Muse
  (after a real `credit_grants` grant) to confirm both named defects are
  closed end-to-end, not just unit-tested.
