---
title: "PR #236 — Measurement Ledger Hardening Phase 1: No Number Lies About Where It Came From"
date: 2026-07-14
series: "Building the OS for Multi-Agent Development"
post: 56
pr: "#236"
issue: "#210 (Phase 1 of 2)"
merged: —
---

## The Broader Goal at the End of the Previous PR

Fable's external review (`docs/strategy/2026-07-12-fable-deep-review-and-strategic-roadmap.md`) drew a hard line for synlynk's pre-GA arc: **"every number synlynk displays is either structurally sourced or visibly labeled as an estimate. No GA, no users, no revenue talk before this."** The review, done alongside the local-agent MLX driver design, turned up two compounding problems in the cost ledger: extraction fragility (a regex-scraping pipeline that silently degrades to an 80/20 heuristic guess on format drift, with nothing distinguishing a measured number from a guessed one) and coverage gaps (several real execution surfaces — the `jobs.py` daemon reconcile path, `synlynk launch`, native PM sessions, the `support_engineer.py` autonomous agent — writing incomplete cost rows or none at all). A related, narrower fix (#189: per-model rate table bypasses in three specific call sites) had already landed independently. This PR picks up the larger structural problem #189 was a symptom of.

## Strategic Shifts in This PR (if any)

No goalpost move, but a deliberate scope split. The design brainstorm considered doing extraction hardening (replacing regex/heuristic token scraping with per-agent structured-output adapters) in the same pass as the coverage/provenance work. It was split into two phases instead: **Phase 1** (this PR) fixes the ledger's schema, write discipline, and coverage — every row now says explicitly how confident its number is. **Phase 2** (deferred, tracked under the same #210 epic) replaces the extraction mechanism itself. The reasoning: Phase 1 is schema-and-plumbing work with a clean, testable invariant ("no row is ever silently `actual`"); Phase 2 is per-agent integration work with a much larger surface (every CLI vendor's output format) and no shared abstraction yet. Bundling them would have made both harder to review and land.

## What This PR Shipped

**Provenance-tagged schema.** `cost_entries` gained two columns: `cost_source TEXT NOT NULL` (`actual` | `estimated_token_rate` | `estimated_tshirt` | `estimated_manual` | `legacy_unknown`, no default — every `INSERT` must pass it explicitly) and `estimate_basis TEXT` (which fallback tier produced an estimate, or `NULL` for `actual`/`legacy_unknown` rows). The migration rebuilds the table (rename → recreate → backfill-as-`legacy_unknown` → drop), since SQLite can't add a `NOT NULL` column without a default to an existing table with rows in it.

**One writer, enforced by a test, not just a comment.** Before this PR, four different call sites (`dispatch.py`, `jobs.py` ×2, `support_engineer.py`) each ran their own `INSERT`/`UPDATE` against `cost_entries`, drifting independently. `_insert_cost_row()` in `synlynk/db.py` is now the sole sanctioned path — validates `cost_source` against an allow-list, upserts by `job_id` when present (so a reconciled job's estimate gets replaced by its actual rather than duplicated). A new test walks the entire `synlynk/` source tree looking for `INSERT INTO cost_entries` / `UPDATE cost_entries` outside `db.py` and fails the suite if it finds one — the invariant is enforced mechanically, not just documented.

**Extraction confidence tagging.** `extract_tokens()` now returns a `.basis` attribute alongside token counts: `regex_pair` (real per-field extraction), `total_split` (the 80/20 heuristic guess on a bare total), or `none`. This is the signal `_resolve_cost_tier()` uses to decide whether a row can be `estimated_token_rate` (real count, priced) or must fall back to `estimated_tshirt` (guessed).

**Three-tier t-shirt fallback.** For surfaces with no real token count at all, `_estimate_tshirt_tokens()` tries: (1) the story's own `estimated_tokens` column, split evenly in/out; (2) a historical average from `cost_entries`, same discipline+phase, requiring ≥3 samples; (3) a fixed conservative default (5000 in / 2000 out). Deliberately sourced from `cost_entries` rather than `stories.actual_tokens` — the fallback gets smarter as real usage data accumulates, rather than depending on a separately-maintained estimate column.

**Coverage closure.** Every surface the design spec's audit flagged now writes through the chokepoint unconditionally: `dispatch_agent()`'s exec wrapper no longer gates the cost write on `in_tokens > 0` (a failed/zero-token job now gets a `[failed job]`-labeled placeholder row instead of writing nothing); `jobs.py`'s reconcile and daemon-reconcile paths call `update_costs()` with the job's real `job_id` for idempotent upsert; `cmd_launch()` routes through the fallback chain instead of writing untagged 0/0 rows; `support_engineer.py`'s `_run_investigation()` — previously zero `update_costs()` calls anywhere in the file — now logs every investigation run. `synlynk cost log` was added as a new command so native/unwrapped PM and brainstorming sessions (previously invisible to the ledger entirely) can be logged manually as `estimated_manual`. `synlynk release`, `synlynk probe`, and `synlynk doctor` were separately audited and confirmed to be correctly out of scope — non-billable operations, not gaps.

**Reporting stayed honest.** `costs.md` entries for anything other than `actual`/`legacy_unknown` now carry an `[est] ` prefix; the parser (both `costs.md` ingestion and `check_budgets()`'s live query) tolerates that prefix (and `[legacy] `, `~`) without breaking numeric parsing. `check_budgets()` gained a dedicated sub-line for failed-job placeholder estimates so they're visible but don't silently blend into the headline spend total.

**A bug the plan didn't anticipate, caught by review, not by a test.** During the final whole-branch review — reading the assembled diff end-to-end rather than task-by-task — the `[failed job]` marker `dispatch.py` appends for zero-token failures turned out to be silently truncated away by `update_costs()`'s pre-existing 20-character `short_cmd` slice, which runs *after* the marker is appended. Real commands are almost always longer than 20 characters before the marker is even added, so the truncation cut the string off before the tail-appended marker survived. `check_budgets()`'s failed-job sub-line (which greps `notes` for the literal text `"failed job"`) was therefore dead code in production — while its own unit test passed cleanly, because that test inserted a DB row with the marker already present, never exercising the interaction with truncation. Fixed by prepending the marker instead of appending it, with a new regression test that calls the real `update_costs()` path with a >20-character command to prove the marker now survives. This is exactly the class of bug two-stage per-task review (spec compliance, then code quality) doesn't catch on its own — it only shows up when you trace a value through two functions written in different tasks.

**Process note.** All 20 units of work (the 19 plan tasks plus this review-caught fix) were implemented by dispatched CLI agents (`synlynk dispatch <agent> --task "..." --force-agent`), per this project's locked PM/reviewer-only governance — Claude wrote zero implementation code, only dispatch prompts, spec/quality review, and the final whole-branch pass. One dispatch (the CLAUDE.md docs section) was rejected on first attempt for mangling markdown formatting and redone from a clean prompt before it ever touched the integration branch.

## Brainstorm Visuals Used

None — this was a text-driven design brainstorm (schema, provenance taxonomy, coverage audit), not a visual/UI decision. No `docs/brainstorm/` artifacts informed this PR.

## What This Achieved on the Path to Autonomy

Every dispatched job's cost is now traceable end-to-end with an explicit confidence label, which is the prerequisite for two things further out on the roadmap: (1) budget/quota gating that can actually trust its own numbers instead of silently under- or over-counting, and (2) eventually surfacing per-agent cost-efficiency in the capability/scoring system without contaminating it with unlabeled guesses. The sole-writer chokepoint also means future coverage gaps (a new agent surface, a new dispatch path) fail loudly at review time via the audit test, rather than silently drifting the way the original four independent write sites did.

## Strategic Note: The Goal at the End of This PR

The ledger's schema and coverage are hardened; every number it stores says explicitly how it was derived. Phase 2 — replacing regex/heuristic extraction with per-agent structured-output adapters, closing the rest of #210 — remains open as a separate follow-up plan, deliberately not bundled here. The design spec and implementation plan for this Phase 1 work live on a separate `chore/measurement-ledger-hardening-design` branch and will land as their own docs-only PR, per this project's standing policy of never bundling doc changes with code changes.
