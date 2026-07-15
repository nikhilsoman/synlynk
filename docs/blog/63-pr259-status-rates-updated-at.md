---
title: "Closing v0.12.0: Surfacing rates_updated_at in synlynk status"
date: 2026-07-15
series: "Building the OS for Multi-Agent Development"
post: 63
pr: "#259"
merged: pending
---

## The Broader Goal at the End of the Previous PR

PR #264 closed epic #210 in full — every dollar figure the Vizor Effort & Cost tab renders is now either structurally sourced or visibly flagged as an estimate. That PR's closing note named the one thing still standing between the current state and marking the v0.12.0 Measurement Ledger Hardening theme shipped: issue #259, `synlynk status` surfacing `rates_updated_at`. Fable's 2026-07-12 strategic review had asked for the `_MODEL_RATE_TABLE` move out of code and into an updatable data file "with a `rates_updated_at` shown in `status`." The data-file move itself shipped back in Measurement Ledger Phase 1 (`.synlynk/model_rates.json`, PR #236) — `synlynk/costs.py`'s `_load_model_rates()` has returned a `rates_updated_at` key ever since. Nothing downstream ever read it. `synlynk status` — the command most people actually run — had no way to tell a caller whether the rate table behind every cost number on screen was current or a hardcoded fallback from before any rate file existed.

## Strategic Shifts in This PR

None to scope. Two design decisions were resolved during brainstorming, both taken as the recommended option without pushback: the new `RATES` line sits immediately next to the existing `BUDGET` line rather than getting its own section header, since both lines answer "how trustworthy are the numbers on this screen" and belong together; and a missing/`None` `rates_updated_at` renders as an explicit `⚠` warning (`"RATES   never updated ⚠ (hardcoded defaults)"`) rather than a silent "unknown" — matching epic #210's own precedent that unmeasured or estimated data must be visibly flagged, never blended in unmarked.

## What This PR Shipped

A single-file change to `synlynk/status.py`, small enough to dispatch as one task rather than the data/rendering split #258 needed:

- **New helper** — `_format_rates_line(rates_updated_at: Optional[str]) -> str` returns `"RATES   updated {date}"` when a date is present, else the warning string above.
- **`_format_status_terminal()` signature** gained one new keyword parameter, `rates_updated_at: Optional[str] = None` — a default rather than a required positional arg, specifically so the two pre-existing direct-call tests that don't pass it (`test_format_status_terminal_structure`, `test_format_status_json_valid`) kept working unmodified.
- **Terminal output** inserts the `RATES` line right after `BUDGET` in the existing `lines` list.
- **JSON output** gains a `rates_updated_at` top-level key in the `payload` dict, serializing as the date string or `null` — `json.dumps` handles `None` natively, no special-casing needed.
- **`cmd_status()`** now calls `synlynk.costs._load_model_rates().get("rates_updated_at")` and threads the result through to `_format_status_terminal()`.

**Task 1 (dispatched to Codex, job-48d58abb)** implemented the change exactly as specified in the plan — verified via `git diff` against the plan's parent commit to confirm zero deviation, not just a self-report. Five new tests landed in `tests/test_ecosystem_status.py`: two on `_format_status_terminal()` directly (date-present and warning-path), one on the JSON payload, and two on `cmd_status()` end-to-end (rate file present with a date, and no rate file at all asserting `null`). All 5 passed on independent re-run; the full `test_ecosystem_status.py` + `test_status.py` + `test_cost_ledger.py` set (147 tests) stayed green.

**Task 2 (Claude, verification-only, not dispatched)** ran the full project suite rather than just the touched files — 1140 passed, 2 skipped, matching the pre-#259 baseline (1135) plus exactly the 5 new tests. This full-suite discipline is a direct lesson from PR #264's CI failure, where a regression in a completely different test file's own fixture (`test_vizor_efficiency.py`'s separate `make_test_db()`) only surfaced because CI ran everything — a narrowly-scoped local check would have missed it. A manual smoke test confirmed both terminal and JSON output render correctly against a real (non-mocked) `_load_model_rates()` call on a workspace with no rate file, and a grep audit confirmed `_format_status_terminal()` has exactly one production call site (`cmd_status()`), so no other caller needed updating.

## Brainstorm Visuals Used

None — this was a small, text-only design resolved through two direct multiple-choice questions (line placement, null-handling), no mockups warranted.

## What This Achieved on the Path to Autonomy

This closes the v0.12.0 Measurement Ledger Hardening theme's last remaining item. Combined with #258/PR #264, epic #210 is now fully shipped: cost data is structurally sourced end to end, from the token-extraction adapters (Codex/Claude/Agy/Grok structured-output basis) through the ledger schema (`cost_source`/`estimate_basis` provenance columns) through both display surfaces that show cost data to a human — the Vizor web HUD and the terminal `synlynk status` command. Every number a person looks at now either says where it came from or flags that it's an estimate.

It's also the sixth PR in a row where all production code was dispatched (Codex/Agy/Claude/Grok rotating), with Claude's role held to design, plan-writing, independent diff verification, full-suite test re-execution, and cherry-picking — the PM/reviewer discipline holding even on the smallest scoped task in this run.

## Strategic Note: The Goal at the End of This PR

With #258 and #259 both shipped, `project-docs/roadmap.md`'s v0.12.0 Measurement Ledger Hardening arc gets marked shipped next. #260 (Savings Ledger), #261 (dispatch-path unification), #262 (surface consolidation), and #263 (stage constants staleness, filed during #258's side investigation) remain filed and scoped for a later point release, none blocking. #202 (`synlynk jobs` stale status display) also remains open, tracked separately.
