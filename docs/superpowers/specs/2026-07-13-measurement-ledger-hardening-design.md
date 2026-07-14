# Measurement Ledger Hardening — Design Spec

**Date:** 2026-07-13
**Author:** Claude (PM), brainstormed with Nikhil
**Status:** Approved for planning — revised 2026-07-13 after independent Agy/Codex/Grok design review (see §13)
**Supersedes/closes:** GitHub issue #210 (Structured Integration Layer — Fable H0 gate)
**Related:** `docs/strategy/2026-07-12-fable-deep-review-and-strategic-roadmap.md` §3.3, §6.3 Horizon 0 item 1

---

## 1. Problem Statement

synlynk's cost ledger has two compounding trust problems, both confirmed in code as of 2026-07-13:

1. **Extraction fragility.** `extract_tokens()` (`synlynk/costs.py:35-75`) tries 5 regex families against captured CLI stdout, then falls back to an 80/20 input/output split heuristic on a bare "Total tokens: N" line. A vendor CLI format change doesn't error — it silently degrades to the heuristic. There is no signal anywhere distinguishing a number synlynk actually measured from one it guessed.

2. **Coverage gaps.** Cost is captured incompletely or not at all across several real execution surfaces — see the full accounting in §7, which was expanded during external review (§13) to include surfaces (the `jobs.py` reconcile path, `synlynk launch`) not identified in the original brainstorm:
   - ⚠️ `synlynk exec <agent>` (interactive, wrapped) — `synlynk/__init__.py:2057` — wired, but silently skips writing when no token count is available.
   - ⚠️ `dispatch_agent()` foreground path — `synlynk/dispatch.py:1027` — wired, but gated on `in_tokens > 0`, so failed/zero-token jobs write nothing.
   - ❌ `synlynk/jobs.py` daemon/reconcile completion path — never calls the cost-write path at all (found during external review, §13).
   - ❌ Native/unwrapped Claude Code sessions (PM, brainstorming, roadmap work) — **zero entries in `.synlynk/telemetry.json` for this class of work, confirmed by inspection during this design's brainstorm.** synlynk's own PM work is invisible to its own cost ledger.
   - ❌ `synlynk/support_engineer.py` (the Maintain-stage autonomous agent) — zero `update_costs()` calls anywhere in the file, confirmed via grep.
   - ⚠️ `synlynk launch` — already writes untagged 0/0-token rows today (found during external review, §13).
   - N/A `synlynk release` and future autopilot fleet agents (v1.1+, not yet built) — need a documented constraint so they don't repeat this gap.

The user's stated goal: **never miss capturing cost of any implementation — even as an estimate — for any type of task at any SDLC stage**, with actuals used wherever a PAYG/API account makes them available, and every non-actual number explicitly labeled as an estimate, never blended in silently.

This directly resolves the Fable review's Horizon 0 gate: *"every number synlynk displays is either structurally sourced or visibly labeled as an estimate. No GA, no users, no revenue talk before this."*

---

## 2. Core Invariant

**Every cost row carries an explicit provenance tag. No row is ever silently `actual` unless it demonstrably is one.** Coverage extends to every SDLC stage (Dream, Plan, Work, Ship, Maintain, Engage), not just dispatched agent jobs.

---

## 3. Provenance Taxonomy

Two new columns on the cost ledger table (`cost_entries`):

```sql
cost_source TEXT NOT NULL
  -- 'actual' | 'estimated_token_rate' | 'estimated_tshirt' | 'estimated_manual' | 'legacy_unknown'
  -- NO DEFAULT. Every INSERT must pass this explicitly — see "No silent actual" below.

estimate_basis TEXT
  -- NULL for 'actual' rows. For 'estimated_tshirt' rows: 'story_estimate' | 'historical_avg' | 'fixed_default'.
  -- For 'estimated_token_rate' rows: 'structured_output' | 'regex_pair'.
  -- For 'estimated_manual' rows: 'cli_manual_entry'.
```

| Tier | Meaning | When it fires |
|---|---|---|
| `actual` | Real metered billing | Set only when `billing_mode` (see below) resolves to `payg` for the agent/account in play, or the agent is `local` (verified true $0 via existing agent-level rate override in `_model_rate_for_version`). Never inferred from "we happened to get real token counts." |
| `estimated_token_rate` | Subscription account, real token count known | CLI reported genuine token counts (via structured output or regex extraction), and `billing_mode` resolves to `subscription`. Priced at published API list rate as a dollar-equivalent, explicitly labeled as such. |
| `estimated_tshirt` | No real token count available | Fallback chain (§5) estimates tokens from story metadata or history. Also the destination for the regex 80/20 total-split heuristic (see §4) — a guessed split is not a real token count, regardless of billing mode. |
| `estimated_manual` | Self-reported, no CLI token data at all | Native/unwrapped sessions (PM, brainstorming, design docs) logged via `synlynk cost log`. Lowest-confidence tier, always explicit. |
| `legacy_unknown` | Pre-migration historical row | Backfill tag only (see §3.2) — never written by new code. |

Given the user's confirmed context (most agents run on subscription plans today, not PAYG), `estimated_token_rate` is expected to be the **majority case among dispatched work with usable token counts**, not an edge case. Note per Codex's review: this majority only materializes once Phase 2's structured adapters reduce reliance on the regex heuristic — until then, a meaningful share of rows will still land in `estimated_tshirt` even on subscription accounts, because a guessed split isn't a real count. Phase 1 ships the honest labels; Phase 2 shifts the mix toward `estimated_token_rate`.

### 3.1 No silent `actual` — enforcement, not just convention

All three review agents (Agy, Codex, Grok) independently flagged that a `DEFAULT 'actual'` on `cost_source` directly contradicts §2's Core Invariant: any write path that omits the column would silently pass as metered billing. Fixed as follows:

- `cost_source` has **no column default**. SQLite will reject any INSERT that omits it (`NOT NULL` with no default raises on omission), converting a silent mislabeling bug into a loud INSERT failure at write time — this is the primary enforcement mechanism, not the regression test in §10 (which is a secondary safety net, not the only one).
- A single internal write helper (`_insert_cost_row(..., cost_source, estimate_basis=None)`) becomes the **only** code path allowed to insert into `cost_entries`. All existing call sites (`update_costs()` in `costs.py`, the `dispatch.py` and `__init__.py`/`cmd_launch` write sites, the new `support_engineer.py` and `synlynk cost log` sites) are migrated to call it. This closes the "broader API discipline problem" Codex's review named directly — provenance is enforced at the one write chokepoint, not by convention at N call sites.

### 3.2 Billing mode — the actual `actual`-vs-`estimated_token_rate` trigger

Grok and Agy both identified the same gap from different angles: nothing in current code or config records whether an agent/account is PAYG or subscription, so the spec had no real mechanism for choosing between `actual` and `estimated_token_rate` — it was aspirational labeling, not a resolvable rule.

New config, `.synlynk/model_rates.json` gains a `billing_mode` map (see revised §6):

```json
"billing_mode": {
  "default": "subscription",
  "local": "actual"
}
```

Resolution rule at write time: look up the dispatching agent's key in `billing_mode`; fall back to `"default"`. `local` is hardcoded to `"actual"` in code (matching its existing `$0.0` rate override) regardless of what the config says, so a misconfigured file can't accidentally mis-tag the one agent we're certain about. No PAYG account exists in the fleet today, so `billing_mode.default` starts at `"subscription"` — the moment a PAYG/API-key account is added for any agent, that agent's key gets `"actual"` and its rows switch tiers automatically, with no schema change required.

### 3.3 Historical backfill

Codex and Grok both flagged that a migration must not default pre-existing `cost_entries` rows to `actual` — that would relabel two years of subscription-era spend as metered billing overnight, the opposite of what this spec exists to fix. The migration (§6.1) backfills all pre-migration rows to `cost_source = 'legacy_unknown'`, `estimate_basis = NULL`. Reporting (§8) treats `legacy_unknown` the same as an estimated tier for budget-summing purposes, and itemized views label it distinctly (`[legacy]`) so historical rows are never mistaken for freshly-verified actuals.

---

## 4. Extraction Layer (Phase 2 — per-agent, sequenced after ledger/schema lands)

Per-agent structured output adapters replace the 80/20 regex-split heuristic as the primary token-extraction path:
- `claude -p --output-format stream-json`
- Codex headless JSON
- Gemini structured mode
- Grok (format TBD, investigate during planning)

The regex heuristic becomes an explicit last-resort fallback feeding `estimated_tshirt` with `estimate_basis = 'total_split'` (not `estimated_token_rate` — if we had to guess the split, we don't have a real token count). One PR per agent, each independently shippable and testable.

**Why this matters more than originally scoped:** since most agents are subscription-based, `estimated_token_rate`'s accuracy is entirely dependent on extraction accuracy. Getting real token counts (regardless of billing model) is the single highest-leverage fix in this whole plan — it's what lets the majority of cost rows be `estimated_token_rate` (precise, just relabeled) instead of `estimated_tshirt` (coarse guess).

### 4.1 Extraction confidence must land in Phase 1, not wait for Phase 2

Codex and Grok both flagged the same dependency: `extract_tokens()` today returns a bare `(in_tokens, out_tokens)` tuple with no signal for *how* it got those numbers — regex pair match vs the 80/20 total-split heuristic. Phase 1 cannot correctly choose between `estimated_token_rate` and `estimated_tshirt` without knowing which extraction path fired. This is **not** deferred to Phase 2: `extract_tokens()` gets a minimal signature change in Phase 1 — it returns a third value, `basis: 'regex_pair' | 'total_split' | 'none'` — before any of the per-agent structured adapters are built. Phase 2 then adds a fourth value, `'structured_output'`, per agent as each adapter ships. This is a small, mechanical change to an existing function, not a scope increase — it's what makes Phase 1's tier boundary actually implementable.

---

## 5. T-Shirt / Manual Fallback Chains

### 5.1 `estimated_tshirt` (dispatched work, no usable token count)

Fallback chain, first match wins, each tier recorded in `estimate_basis`:
1. `estimate_basis = 'story_estimate'` — story's `estimated_tokens` field (existing, optional, manually set via `--tokens` at story creation) × rate.
2. `estimate_basis = 'historical_avg'` — average tokens for prior stories with the same `discipline` + `phase`, if ≥3 qualifying samples exist for that combination. **Sourced from `cost_entries` (`tokens_in` + `tokens_out` on rows tagged `actual` or `estimated_token_rate` only), not `stories.actual_tokens`.** Agy's review caught that `stories.actual_tokens` is never written to a real value — it's computed dynamically from `telemetry.json` at display time (`team.py:337`) and would return NULL for every query, silently collapsing tier 2 to always-tier-3. Filtering the `cost_entries` source to `actual`/`estimated_token_rate` rows (not raw `estimated_tshirt` guesses) also addresses Grok's point that unfiltered historical averaging would recycle bad estimates into future estimates.
3. `estimate_basis = 'fixed_default'` — fixed conservative default (documented in code/config, not silently hidden) — no row is ever left unpriced or `$0` by omission.

Recording which tier fired in `estimate_basis` (§3) makes the fallback chain itself auditable later (e.g., "is tier 2's historical-average actually converging on something sane?").

### 5.1.1 Always write a row, even on zero tokens or job failure

Grok's review found that today's write gate (`dispatch.py` ~line 1013, `if in_tokens > 0`) means a failed or zero-token extraction produces **no ledger row at all** — the exact opposite of this spec's stated goal ("never miss capturing cost... even as an estimate"). This is folded into Phase 1, not treated as a pre-existing issue out of scope:
- Every terminal job state (success, failure, or zero-token completion) writes exactly one `cost_entries` row via the `_insert_cost_row()` chokepoint (§3.1). A zero/failed extraction writes an `estimated_tshirt` row through the same fallback chain above, not a skipped write.
- `synlynk/jobs.py`'s daemon/reconcile completion path — which today never calls the cost-write path at all (only `dispatch.py`'s foreground path does) — is wired to the same chokepoint, closing a real coverage gap Grok identified independent of this spec's original scope.
- To prevent double-counting if both the foreground `dispatch.py` path and the reconcile path could observe the same job, `cost_entries` gains a `job_id` column (nullable, unique index where non-null) and the write helper is idempotent on `job_id` — a second write attempt for the same job updates rather than inserts a duplicate row.

### 5.2 `estimated_manual` (native/unwrapped sessions)

New command:
```bash
synlynk cost log --agent claude --tokens-in <N> --tokens-out <N> [--story-id <id>] [--note "..."]
```
Writes directly into the same ledger table `update_costs()` writes to, tagged `estimated_manual`. `--story-id` is optional — brainstorming/roadmap work often has no story yet; when absent, the row is bucketed under `phase='dream'` or `phase='plan'` for reporting purposes.

**This command replaces the parallel, untracked `<project>_costs.md` file** currently mandated by the user's global CLAUDE.md end-of-session protocol. One ledger going forward, not two — the existing manual cost-estimation habit (already required at session end per global CLAUDE.md) gets redirected into this command instead of a separate file.

---

## 6. Rate File

`.synlynk/model_rates.json` replaces the hardcoded `_MODEL_RATE_TABLE` in `synlynk/costs.py`:

```json
{
  "rates_updated_at": "2026-07-13",
  "unit": "usd_per_1k_tokens",
  "models": {
    "claude-opus-4-8": {"input": 0.015, "output": 0.075, "cache_read": 0.0000015},
    "claude-sonnet-4-6": {"input": 0.003, "output": 0.015, "cache_read": 0.0000003},
    "gpt-5-codex": {"input": 0.003, "output": 0.015, "cache_read": 0.0000003},
    "gpt-5.4-mini": {"input": 0.003, "output": 0.015, "cache_read": 0.0000003},
    "gemini-2.5-pro": {"input": 0.00125, "output": 0.01, "cache_read": 0.000125},
    "grok-build": {"input": 0.003, "output": 0.015, "cache_read": 0.0000003},
    "grok-composer-2.5-fast": {"input": 0.003, "output": 0.015, "cache_read": 0.0000003}
  },
  "default": {"input": 0.003, "output": 0.015, "cache_read": 0.0000003},
  "billing_mode": {
    "default": "subscription",
    "local": "actual"
  }
}
```

- Grok's review flagged that the rate numbers as originally written were ambiguous — they happen to match `update_costs()`'s existing per-1K-token math, but nothing said so, inviting a future per-MTok paste error straight from a vendor pricing page. The explicit `"unit": "usd_per_1k_tokens"` key documents this; the loader validates the field is present and matches the expected literal, refusing to load (falling back to `default` rates with a loud warning) if it's missing or wrong.
- `billing_mode` resolves `actual` vs `estimated_token_rate` per §3.2. `local` is additionally hardcoded to `"actual"` in code — the config value for `local` is read but ignored if it ever diverges, so a bad edit to this file can't mis-tag the one agent we're certain about.
- `local` agent keeps its existing code-level `agent == "local"` → `$0.0` rate override (unaffected by this file — it's agent-level, not model-level, per the fix already shipped in #189).
- `synlynk status` warns when `rates_updated_at` is more than 90 days stale.
- An unrecognized `model_version` still falls back to `default`, but the row is now honestly tagged `estimated_tshirt` or `estimated_token_rate` (whichever applies) instead of silently passing as a confident number — this closes the "unknown model billed as if certain" problem as a side effect of the provenance column existing.

**Pre-existing bug folded in:** `cost_entries.agent` currently stores the dispatching *username*, not the agent name (Grok's review). Per-agent/per-tier reporting (§8) is meaningless until this is corrected — the write helper (§3.1) takes an explicit `agent` parameter sourced from the dispatch/exec context, not `git config user.name`, closing this alongside the schema work since both touch the same write path.

---

## 7. Coverage Closure — Every SDLC Stage

| SDLC stage | Execution surface | Provenance tier(s) | Fix required |
|---|---|---|---|
| Dream / Plan | Native Claude PM/brainstorm session | `estimated_manual` | New `synlynk cost log` command (§5.2) |
| Work | `synlynk exec` (interactive) | `actual` / `estimated_token_rate` / `estimated_tshirt` | Already wired to the write chokepoint, but currently **skips writing entirely** when no token count is available (TTY session, no output captured). Fixed to fall through to the §5.1 estimate chain instead of skipping, same as dispatch (§5.1.1). Benefits from Phase 2 extraction upgrade. |
| Work / Ship | `dispatch_agent()` foreground path | `actual` / `estimated_token_rate` / `estimated_tshirt` | Zero-token write gate removed per §5.1.1. Benefits from Phase 2 extraction upgrade. |
| Work / Ship | `synlynk/jobs.py` daemon/reconcile completion path | `actual` / `estimated_token_rate` / `estimated_tshirt` | **Currently never calls the cost-write path at all** (Grok's review) — only the foreground `dispatch.py` path does. Wired to the same `_insert_cost_row()` chokepoint, deduplicated against the foreground path via `job_id` (§5.1.1). This closes a real coverage gap independent of this spec's original scope. |
| Ship | `synlynk launch` (`__init__.py:2057`) | `estimated_tshirt` (currently writes 0/0-token rows) | Grok's review found this path already writes ledger rows today, at 0/0 tokens, untagged — not previously in this table. Routed through the §5.1 fallback chain instead of writing a bare zero. |
| Ship | `synlynk release` | `estimated_manual` (native invocation) | **Closed, not provisional** — Codex's review flagged the original wording ("confirm during planning") as leaving this cell open. Decision: `synlynk release` is a native/PM-style invocation like brainstorming, so it uses the same `synlynk cost log` path as §5.2, not a new mechanism. |
| Maintain | `synlynk/support_engineer.py` | `actual` / `estimated_token_rate` | **Wire the write chokepoint (§3.1) into its subprocess call site — currently zero calls, confirmed gap.** Grok's review notes this is a direct CLI shell invoke, not a `dispatch_agent()` call — "same pattern as `dispatch.py:1027`" is approximate, not identical; the write call is added after log capture in its own subprocess-wrapping function. One row per investigation; the fixer path reuses the investigation log and does not get a second cost row unless it makes its own separate model call. |
| Engage | Future autopilot fleet (TPM/Release/Docs Keeper/Security, v1.1+) | inherits from execution surface | Not built yet. **Documented constraint**: any future agent must dispatch through `dispatch_agent()` or explicitly call `_insert_cost_row()`/`synlynk cost log` — no new agent may ship without a cost-capture path. |
| — | IDE-embedded AI assistants (Cursor, Copilot, Windsurf, etc.) | out of scope | Agy's review flagged these as a real execution surface with no automatic capture mechanism (they run inside editor extensions, not wrapped CLI calls). Explicitly out of scope for this spec (§11) — not silently omitted. |
| — | `synlynk probe` / `synlynk doctor` | N/A — no cost incurred | Agy's review flagged these diagnostic commands as an omitted execution surface. Confirmed by reading every `subprocess` call site in `probe.py`/`doctor.py` (2026-07-13): all invoke wrapped-CLI `--help`/`--version`/`/status`/`-v` flags for capability/version metadata only, never a prompted generation. `doctor.py` has no subprocess calls of its own — it reuses `probe.py`'s TC-1..TC-4 helpers. Explicitly out of scope: not a gap, because no token cost is ever incurred here. |

---

## 8. Reporting

- `project-docs/costs.md` and `synlynk status` show **one headline total** (sum across all tiers, including `legacy_unknown` — still the most useful top-line number), with a **per-tier subtotal breakdown** immediately visible alongside it.
- Any non-`actual` row is visually flagged in itemized views: `[est]` for the three estimate tiers, `[legacy]` for backfilled pre-migration rows.
- Agy's review found that the existing markdown parsers (`parse_costs_md` in `costs.py`, `_parse_costs_md` in `db.py`) do a bare `float(parts[5].lstrip("$"))`/strip-`~`-only extraction on the cost column — any other prefix raises `ValueError` and silently drops the row. Both parsers are updated in the same PR that changes the write-through format, with a test asserting `[est]`/`[legacy]`-prefixed rows still parse to the correct float. This is called out explicitly rather than left as an incidental side effect of the display change.
- `check_budgets()` sums **all tiers, including `legacy_unknown`** — estimated and legacy dollars count toward budget-limit alerts. Rationale (user-confirmed): better to over-alert on a rough number than silently exclude subscription/manual spend from budget tracking.
- Once §5.1.1's always-write-a-row change lands, a `estimated_tshirt` fixed-default row is written even for a job that failed outright. Grok's review flagged this as a potential budget-noise risk — a burst of failed jobs could inflate the estimated total with fixed-default placeholder dollars. Mitigation: `check_budgets()` reports failed-job estimated rows as a separate, clearly-labeled sub-line ("N failed-job placeholder estimates, $X") rather than blending them into the same subtotal as completed-work estimates — visible for debugging, not silently hidden, but not conflated with real spend either.

---

## 9. New CLAUDE.md Protocol — "Cost Capture Protocol"

Added to `/Users/nikhilsoman/dev/synlynk/CLAUDE.md`, same pattern and weight as the existing Blog Post Protocol and Workspace Map Update Protocol:

> **For every PR, before merging:** confirm all dispatched/wrapped work in this PR is auto-captured (nothing to do — it already is via `dispatch_agent()`/`synlynk exec`), and any native/PM-session work (brainstorming, design docs, manual fixes) not tied to a dispatched job has a corresponding `synlynk cost log` entry. If genuinely zero cost was incurred outside dispatched work, note that explicitly in the PR rather than skipping the check silently.

Enforced by discipline (Claude/PM checks it as part of PR housekeeping), not CI — matches how the Blog Post Protocol already operates. Not a blocking CI gate.

---

## 10. Testing Approach

- **DB-level enforcement test (primary safety net, per §3.1):** a raw INSERT into `cost_entries` omitting `cost_source` must raise, not silently succeed with a default value. This is the load-bearing test — the call-site audit below is a secondary net, not the only one.
- Unit tests per fallback tier in §5.1, each asserting both `cost_source` **and** the correct `estimate_basis` value: `story_estimate` (story has `estimated_tokens`), `historical_avg` (≥3 qualifying `cost_entries` siblings of matching discipline+phase, sourced from `actual`/`estimated_token_rate` rows only — not raw `stories.actual_tokens`), `fixed_default` (no story estimate, <3 historical siblings).
- Call-site audit test: every existing call site of the cost-write chokepoint (`update_costs()`, `dispatch.py`, `cmd_launch`, plus the new `support_engineer.py` and `jobs.py` reconcile sites) passes an explicit `cost_source`.
- Migration/backfill test: pre-migration rows are tagged `legacy_unknown` with `estimate_basis = NULL`, never `actual`.
- Idempotency test: writing a cost row twice for the same `job_id` (simulating both the foreground dispatch path and the reconcile path observing the same job) updates in place rather than double-inserting (§5.1.1).
- Always-write test: a job that fails or extracts zero tokens still produces exactly one `estimated_tshirt` row, not zero rows (§5.1.1) — covering both the `dispatch.py` foreground path and the `jobs.py` reconcile path.
- Test confirming `synlynk launch`'s previously-silent 0/0-token write now routes through the §5.1 fallback chain instead of writing an untagged zero (§7).
- `synlynk release`'s `cost log`-path write is tested the same way as §5.2's manual-entry tests below, since it uses the same mechanism (§7).
- Unit tests for `synlynk cost log` — writes correct row with an explicit `estimate_basis = 'cli_manual_entry'`; correct default phase bucketing (`dream`/`plan`) when `--story-id` omitted; with `--story-id`; with missing/malformed token or note input (should error, not write a bad row).
- One integration test per agent's Phase 2 structured adapter, confirming real output shape parses into `actual`/`estimated_token_rate` correctly (using recorded fixture output per agent, consistent with existing `tests/conftest.py` patterns).
- Test confirming `support_engineer.py`'s subprocess calls now produce exactly one cost row per investigation (not a duplicate for the fixer path when it reuses the investigation log, per §7).
- Test confirming an unrecognized `model_version` still produces a non-`actual`-tagged row (not silently priced as if confident), **and** that row is still summed correctly into `check_budgets()` (§8) — reporting correctness is part of this contract, not assumed.
- Parser compatibility test: `parse_costs_md` / `_parse_costs_md` correctly parse `[est]`- and `[legacy]`-prefixed cost cells without raising or silently dropping the row (§8).
- Rate-file test: a `model_rates.json` missing or mismatching the `"unit"` key fails to load and falls back to `default` rates with a logged warning, rather than silently misapplying per-MTok numbers as per-1K (§6).

---

## 11. Out of Scope

- Building the future autopilot fleet agents themselves (v1.1+) — only the documented constraint that they must integrate with this ledger.
- CI-enforced (blocking) cost-capture gate — deferred; discipline-based enforcement via the CLAUDE.md protocol is sufficient for now, matching existing precedent (Blog Post Protocol).
- Capability matrix hardening (role/stage routing, decay bug #212, model-version inheritance) — separate design brainstorm, tracked independently.
- Local-agent scheduler preflight (#211) — separate issue, not part of this plan.
- IDE-embedded AI assistants (Cursor, Copilot, Windsurf, etc.) — real execution surface, no automatic capture mechanism exists (editor-extension-hosted, not a wrapped CLI call). Flagged by Agy's review (§13); explicitly excluded here rather than silently omitted. Revisit if/when this becomes a material share of team spend.

---

## 12. Self-Review Notes

- **Placeholder scan:** none found — all sections have concrete mechanisms, no TBDs except Grok's structured-output format (explicitly flagged as "investigate during planning," not a silent gap).
- **Internal consistency:** the five-tier taxonomy (`actual` / `estimated_token_rate` / `estimated_tshirt` / `estimated_manual` / `legacy_unknown`) is used consistently across schema, fallback chains, reporting, and testing sections; `estimate_basis` sub-tiers are defined once (§3) and referenced consistently thereafter (§5.1, §10).
- **Scope check:** focused on measurement/cost ledger only; capability matrix and local-agent issues are explicitly cross-referenced but excluded (§11). The coverage-gap fixes folded in from external review (zero-token write gate, `jobs.py` reconcile wiring, `synlynk launch`) are in-scope because they're the same write chokepoint this spec already owns, not separate initiatives.
- **Ambiguity check:** "estimated_token_rate" vs "estimated_tshirt" boundary is unambiguous (real token count vs guessed/absent); `synlynk release`'s cost-logging mechanism is now closed (§7) rather than left open; `billing_mode` resolution order (agent key → `default`, with `local` hardcoded) is stated explicitly (§3.2) to avoid two readers reaching different conclusions about precedence.

---

## 13. External Review — Agy / Codex / Grok (2026-07-13)

Before moving to `writing-plans`, this spec was dispatched to all three implementation agents (Agy, Codex, Grok) for independent design review — same input, same questions, no cross-visibility between them. All three converged on the same core findings without prompting, which is treated as a strong signal the findings are real rather than agent-specific noise:

1. `DEFAULT 'actual'` on `cost_source` contradicted the spec's own §2 invariant (all three, independently).
2. A single `cost_source` column can't fulfill the "which fallback tier fired" audit promise in §5.1 — needed a second field (all three, independently).
3. Historical backfill must not default existing rows to `actual` (Codex, Grok).

Each agent also surfaced findings unique to its read of the live codebase:
- **Agy:** `stories.actual_tokens` referenced in the original §5.1 is never populated (computed dynamically, not stored) — the fallback chain as originally written would have silently never worked. Also flagged IDE-assistant coverage and markdown-parser brittleness against non-`$`-prefixed cost cells.
- **Codex:** `synlynk release`'s coverage cell was left provisional ("confirm during planning") rather than closed; flagged that Phase 1 doesn't structurally depend on Phase 2 but the spec's "majority case" claim for `estimated_token_rate` does.
- **Grok:** found the deepest set of pre-existing bugs — `cost_entries.agent` stores username not agent name; `jobs.py`'s reconcile path never writes to the ledger at all; the `if in_tokens > 0` write gate silently drops rows on failed/zero-token jobs; `synlynk launch` already writes untagged 0/0 rows today; rate-file units were ambiguous; no `billing_mode` concept existed to actually resolve `actual` vs `estimated_token_rate`.

All findings above were folded into §3, §4, §5, §6, §7, §8, §10, and §11 in this revision. Full transcripts: `synlynk logs --job job-58eb0de6` (Agy), `job-f3f92eba` (Codex), `job-54747874` (Grok).
