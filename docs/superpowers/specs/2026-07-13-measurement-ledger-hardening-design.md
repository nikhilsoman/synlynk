# Measurement Ledger Hardening — Design Spec

**Date:** 2026-07-13
**Author:** Claude (PM), brainstormed with Nikhil
**Status:** Approved for planning
**Supersedes/closes:** GitHub issue #210 (Structured Integration Layer — Fable H0 gate)
**Related:** `docs/strategy/2026-07-12-fable-deep-review-and-strategic-roadmap.md` §3.3, §6.3 Horizon 0 item 1

---

## 1. Problem Statement

synlynk's cost ledger has two compounding trust problems, both confirmed in code as of 2026-07-13:

1. **Extraction fragility.** `extract_tokens()` (`synlynk/costs.py:35-75`) tries 5 regex families against captured CLI stdout, then falls back to an 80/20 input/output split heuristic on a bare "Total tokens: N" line. A vendor CLI format change doesn't error — it silently degrades to the heuristic. There is no signal anywhere distinguishing a number synlynk actually measured from one it guessed.

2. **Coverage gaps.** Cost is only captured for two of five real execution surfaces:
   - ✅ `synlynk exec <agent>` (interactive, wrapped) — `synlynk/__init__.py:2057`
   - ✅ `dispatch_agent()` (dispatched jobs, incl. daemon/scheduler queue since #190) — `synlynk/dispatch.py:1027`
   - ❌ Native/unwrapped Claude Code sessions (PM, brainstorming, roadmap work) — **zero entries in `.synlynk/telemetry.json` for this class of work, confirmed by inspection during this design's brainstorm.** synlynk's own PM work is invisible to its own cost ledger.
   - ❌ `synlynk/support_engineer.py` (the Maintain-stage autonomous agent) — zero `update_costs()` calls anywhere in the file, confirmed via grep.
   - N/A `synlynk release` and future autopilot fleet agents (v1.1+, not yet built) — need a documented constraint so they don't repeat this gap.

The user's stated goal: **never miss capturing cost of any implementation — even as an estimate — for any type of task at any SDLC stage**, with actuals used wherever a PAYG/API account makes them available, and every non-actual number explicitly labeled as an estimate, never blended in silently.

This directly resolves the Fable review's Horizon 0 gate: *"every number synlynk displays is either structurally sourced or visibly labeled as an estimate. No GA, no users, no revenue talk before this."*

---

## 2. Core Invariant

**Every cost row carries an explicit provenance tag. No row is ever silently `actual` unless it demonstrably is one.** Coverage extends to every SDLC stage (Dream, Plan, Work, Ship, Maintain, Engage), not just dispatched agent jobs.

---

## 3. Provenance Taxonomy

New column on the cost ledger table:

```sql
cost_source TEXT NOT NULL DEFAULT 'actual'
  -- 'actual' | 'estimated_token_rate' | 'estimated_tshirt' | 'estimated_manual'
```

| Tier | Meaning | When it fires |
|---|---|---|
| `actual` | Real metered billing | PAYG/API-key accounts; `local` agent (verified true $0 via existing agent-level rate override in `_model_rate_for_version`) |
| `estimated_token_rate` | Subscription account, real token count known | CLI reported genuine token counts (via structured output or regex extraction), but the account is flat-rate — no real per-call bill exists. Priced at published API list rate as a dollar-equivalent, explicitly labeled as such. |
| `estimated_tshirt` | Subscription account, no token count available | Fallback chain (§5) estimates tokens from story metadata or history. |
| `estimated_manual` | Self-reported, no CLI token data at all | Native/unwrapped sessions (PM, brainstorming, design docs) logged via `synlynk cost log`. Lowest-confidence tier, always explicit. |

Given the user's confirmed context (most agents run on subscription plans today, not PAYG), `estimated_token_rate` is expected to be the **majority case**, not an edge case — this is not a rarely-hit fallback path, it is the primary pricing mechanism for most dispatched work.

---

## 4. Extraction Layer (Phase 2 — per-agent, sequenced after ledger/schema lands)

Per-agent structured output adapters replace the 80/20 regex-split heuristic as the primary token-extraction path:
- `claude -p --output-format stream-json`
- Codex headless JSON
- Gemini structured mode
- Grok (format TBD, investigate during planning)

The regex heuristic becomes an explicit last-resort fallback feeding `estimated_tshirt` (not `estimated_token_rate` — if we had to guess the split, we don't have a real token count). One PR per agent, each independently shippable and testable.

**Why this matters more than originally scoped:** since most agents are subscription-based, `estimated_token_rate`'s accuracy is entirely dependent on extraction accuracy. Getting real token counts (regardless of billing model) is the single highest-leverage fix in this whole plan — it's what lets the majority of cost rows be `estimated_token_rate` (precise, just relabeled) instead of `estimated_tshirt` (coarse guess).

---

## 5. T-Shirt / Manual Fallback Chains

### 5.1 `estimated_tshirt` (dispatched work, no token count at all)

Fallback chain, first match wins:
1. Story's `estimated_tokens` field (existing, optional, manually set via `--tokens` at story creation) × rate.
2. Historical average `actual_tokens` for stories with the same `discipline` + `phase`, if ≥3 prior samples exist for that combination.
3. Fixed conservative default (documented in code/config, not silently hidden) — no row is ever left unpriced or `$0` by omission.

The row records **which tier of this chain fired**, not just the top-level `cost_source` — this makes the fallback chain itself auditable later (e.g., "is tier 2's historical-average actually converging on something sane?").

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
  "models": {
    "claude-opus-4-8": {"input": 0.015, "output": 0.075, "cache_read": 0.0000015},
    "claude-sonnet-4-6": {"input": 0.003, "output": 0.015, "cache_read": 0.0000003},
    "gpt-5-codex": {"input": 0.003, "output": 0.015, "cache_read": 0.0000003},
    "gpt-5.4-mini": {"input": 0.003, "output": 0.015, "cache_read": 0.0000003},
    "gemini-2.5-pro": {"input": 0.00125, "output": 0.01, "cache_read": 0.000125},
    "grok-build": {"input": 0.003, "output": 0.015, "cache_read": 0.0000003},
    "grok-composer-2.5-fast": {"input": 0.003, "output": 0.015, "cache_read": 0.0000003}
  },
  "default": {"input": 0.003, "output": 0.015, "cache_read": 0.0000003}
}
```

- `local` agent keeps its existing code-level `agent == "local"` → `$0.0` override (unaffected by this file — it's agent-level, not model-level, per the fix already shipped in #189).
- `synlynk status` warns when `rates_updated_at` is more than 90 days stale.
- An unrecognized `model_version` still falls back to `default`, but the row is now honestly tagged `estimated_tshirt` or `estimated_token_rate` (whichever applies) instead of silently passing as a confident number — this closes the "unknown model billed as if certain" problem as a side effect of the provenance column existing.

---

## 7. Coverage Closure — Every SDLC Stage

| SDLC stage | Execution surface | Provenance tier(s) | Fix required |
|---|---|---|---|
| Dream / Plan | Native Claude PM/brainstorm session | `estimated_manual` | New `synlynk cost log` command (§5.2) |
| Work | `synlynk exec` (interactive) | `actual` / `estimated_token_rate` | None — already wired, benefits from Phase 2 extraction upgrade |
| Work / Ship | `dispatch_agent()` (interactive + daemon/scheduler queue) | `actual` / `estimated_token_rate` / `estimated_tshirt` | None structurally — benefits from Phase 2 extraction upgrade |
| Ship | `synlynk release` | `estimated_manual` (native invocation) | Confirm during planning; likely same `cost log` path |
| Maintain | `synlynk/support_engineer.py` | `actual` / `estimated_token_rate` | **Wire `update_costs()` into its subprocess call site — currently zero calls, confirmed gap.** Same pattern as `dispatch.py:1027`. |
| Engage | Future autopilot fleet (TPM/Release/Docs Keeper/Security, v1.1+) | inherits from execution surface | Not built yet. **Documented constraint**: any future agent must dispatch through `dispatch_agent()` or explicitly call `update_costs()`/`synlynk cost log` — no new agent may ship without a cost-capture path. |

---

## 8. Reporting

- `project-docs/costs.md` and `synlynk status` show **one headline total** (sum of all four tiers — still the most useful top-line number), with a **per-tier subtotal breakdown** immediately visible alongside it.
- Any non-`actual` row is visually flagged in itemized views (e.g. `~` prefix or `[est]` tag).
- `check_budgets()` sums **all four tiers** — estimated dollars count toward budget-limit alerts. Rationale (user-confirmed): better to over-alert on a rough number than silently exclude subscription/manual spend from budget tracking.

---

## 9. New CLAUDE.md Protocol — "Cost Capture Protocol"

Added to `/Users/nikhilsoman/dev/synlynk/CLAUDE.md`, same pattern and weight as the existing Blog Post Protocol and Workspace Map Update Protocol:

> **For every PR, before merging:** confirm all dispatched/wrapped work in this PR is auto-captured (nothing to do — it already is via `dispatch_agent()`/`synlynk exec`), and any native/PM-session work (brainstorming, design docs, manual fixes) not tied to a dispatched job has a corresponding `synlynk cost log` entry. If genuinely zero cost was incurred outside dispatched work, note that explicitly in the PR rather than skipping the check silently.

Enforced by discipline (Claude/PM checks it as part of PR housekeeping), not CI — matches how the Blog Post Protocol already operates. Not a blocking CI gate.

---

## 10. Testing Approach

- Unit tests per fallback tier in §5.1 (mock a story with/without `estimated_tokens`, with/without ≥3 historical siblings of matching discipline+phase).
- Regression test asserting `cost_source` is never left at its schema default (`'actual'`) silently — every code path that writes a cost row must set it explicitly; a test should audit all call sites of the cost-write function and confirm each passes an explicit tier.
- Unit tests for `synlynk cost log` — writes correct row, correct default phase bucketing when `--story-id` omitted.
- One integration test per agent's Phase 2 structured adapter, confirming real output shape parses into `actual`/`estimated_token_rate` correctly (using recorded fixture output per agent, consistent with existing `tests/conftest.py` patterns).
- Test confirming `support_engineer.py`'s subprocess calls now produce a cost row.
- Test confirming an unrecognized `model_version` still produces a non-`actual`-tagged row (not silently priced as if confident).

---

## 11. Out of Scope

- Building the future autopilot fleet agents themselves (v1.1+) — only the documented constraint that they must integrate with this ledger.
- CI-enforced (blocking) cost-capture gate — deferred; discipline-based enforcement via the CLAUDE.md protocol is sufficient for now, matching existing precedent (Blog Post Protocol).
- Capability matrix hardening (role/stage routing, decay bug #212, model-version inheritance) — separate design brainstorm, tracked independently.
- Local-agent scheduler preflight (#211) — separate issue, not part of this plan.

---

## 12. Self-Review Notes

- **Placeholder scan:** none found — all sections have concrete mechanisms, no TBDs except Grok's structured-output format (explicitly flagged as "investigate during planning," not a silent gap).
- **Internal consistency:** the four-tier taxonomy is used consistently across schema, fallback chains, reporting, and testing sections.
- **Scope check:** focused on measurement/cost ledger only; capability matrix and local-agent issues are explicitly cross-referenced but excluded (§11).
- **Ambiguity check:** "estimated_token_rate" vs "estimated_tshirt" boundary is unambiguous (token count known vs not known); `synlynk release`'s exact cost-logging mechanism is the one item flagged for confirmation during planning, not left ambiguous in intent.
