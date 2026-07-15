---
title: "Measurement Ledger Phase 2: The Agy (Gemini) Structured-Output Adapter"
date: 2026-07-15
series: "Building the OS for Multi-Agent Development"
post: 60
pr: "TBD"
merged: pending
---

## The Broader Goal at the End of the Previous PR

PR #252 shipped the second of four planned per-agent structured-output adapters — Claude — and re-validated the pattern PR #244 (Codex) established: `extract_tokens()` tries a per-agent `_extract_<agent>_structured()` function first, falls through to the existing regex chain on any failure, and requires zero changes to `_resolve_cost_tier()` or any of Phase 1's provenance machinery. That PR's closing note named the next goalpost explicitly: Gemini and Grok remain, each independently shippable, each requiring its own live-verified investigation of that CLI's actual structured-output shape rather than a copy-paste of Codex's or Claude's.

## Strategic Shifts in This PR

One genuine strategic shift, decided before any design work started: this PR's four implementation tasks were the first in the Measurement Ledger series to be distributed across all three real CLI agents — Codex, Agy, and Grok — via `synlynk dispatch <agent> --task "..." --force-agent`, rather than defaulting every task to Codex as both the Codex and Claude adapters had. The rotation was Task 1 → Codex, Task 2 → Agy, Task 3 → Grok, Task 4 (verification-only) → Claude itself, per this project's PM/reviewer-only role split. Tasks 1 and 2 were deliberately serialized rather than dispatched in parallel, since both touch the shared file `tests/test_cost_ledger.py` — parallel dispatch risked the second job's context not reflecting the first job's not-yet-cherry-picked test additions.

Four smaller design forks came up during brainstorming, all resolved by asking rather than assuming:

**`thinking_tokens` handling.** Agy's `usage` object separates `input_tokens`, `output_tokens`, and `thinking_tokens`, with `total_tokens` covering only the first two. Folding `thinking_tokens` into `output_tokens` was chosen — mirroring how Codex's `reasoning_output_tokens` is treated as billable output — rather than discarding it or inventing a new provenance field.

**Extraction-failure semantics.** Agy's single JSON response carries a top-level `status` field. `status != "SUCCESS"` was defined as an extraction failure (returns `None`, falls through to the regex chain) rather than inventing a distinct failure schema — consistent with every other adapter's "fail closed, fall through" contract.

**No renderer.** Unlike Codex's `item.completed` event stream or Claude's mixed-content-block `assistant` events, Agy's `--output-format json` emits exactly one JSON object per invocation — there's no multi-event noise for `synlynk logs` to suppress. A `_render_agy_log_line()` was deliberately not added; raw passthrough is sufficient.

**Flag block placement.** `dispatch.py`'s new `if agent == "agy":` block was kept as an independent sibling to the coincidentally-identical `if agent == "grok":` block (both add `["--output-format", "json"]`), rather than merging them — matching the established flat-chain convention that has already absorbed Codex's and Claude's differently-shaped flag additions without needing an abstraction.

## What This PR Shipped

The live investigation came first, same discipline as the Codex and Claude pilots: running `agy -p --output-format json` directly and capturing real output. The key finding that shaped the whole design: Agy's structured output is not an event stream like Codex's or Claude's — it's exactly one JSON object per invocation, schema `{conversation_id, status, response, duration_seconds, num_turns, usage: {input_tokens, output_tokens, thinking_tokens, total_tokens}}`. That single fact eliminated an entire category of design questions the other two adapters had to answer (which event carries the final usage, how to detect the terminal event, how much of the stream to suppress) and is also why no renderer was needed.

A red herring surfaced during the "what already exists" investigation phase: epic #210's issue body cites `synlynk/local_agent.py` as a template pattern for structured JSON output. Reading it in full showed this is unrelated — it's `.agents/local.json` config loading, a health-check GET against an OpenAI-compatible endpoint, and aider CLI flag building for the `local` agent (aider running against a local model server), with no token-extraction logic anywhere. This was confirmed rather than assumed, and the epic reference was set aside as stale.

Three commits landed on top of the design/plan docs:

- **`synlynk/costs.py`** — `_extract_agy_structured()` parses the single trailing JSON object (scanning from the last non-empty line, matching the "exactly one object" shape confirmed live), returning `None` on any malformed JSON, non-`SUCCESS` status, or missing/malformed `usage` — the same fail-closed contract as Codex's and Claude's extractors. `extract_tokens()` gained a sibling `if agent == "agy":` branch immediately after the existing `claude` one.
- **`synlynk/dispatch.py`** — `--output-format json` added to Agy's flag list in `dispatch_agent()`, as a sibling to the existing `grok`/`claude`/`codex` blocks. `synlynk/_constants.py` was deliberately left untouched — TC-2 preflight checks every flag in an agent's `valid_flags` against that agent's literal `--help` text, and `--output-format` is confirmed undocumented for `agy`, so adding it there would fail preflight. Same pattern as Codex's and Claude's own structured-output flags.
- **`tests/test_cost_ledger.py`** — grew by 15 tests across the three code tasks (11 for the extractor, 3 for the `extract_tokens()` wiring, 1 for the dispatch-flags block), directly mirroring the shape of the Codex and Claude adapters' own test suites.

**Process note — the cross-agent dispatch rotation, in detail.** Task 1 went to Codex (`_extract_agy_structured()` + 11 tests), Task 2 to Agy itself (wiring into `extract_tokens()` + 3 tests — Agy implementing its own token-counting adapter), Task 3 to Grok (the dispatch flag block + 1 test). Every dispatch was independently verified before cherry-picking onto the design branch: reading the actual diff against the plan's exact code, confirming `_constants.py` stayed untouched, and running the plan's specified test command myself in the job's worktree — never trusting a job's self-reported pass/fail, and never trusting `synlynk jobs`' status column alone (still `unknown` for completed jobs per the known #202 display bug; verified via the job's log tail and `git log` in its worktree instead). All three dispatched tasks matched the plan's specified code exactly on the first attempt. Task 3's job also left two uncommitted, plan-unrelated working-tree modifications — a `GEMINI.md` harness-version stamp bump and a `project-docs/todo.md` overwrite that replaced roughly fifty real story rows with two placeholder stub rows, apparently triggered by a template-context regeneration during the dispatch run. Neither was part of any task; both were confirmed as incidental and discarded before the branch diff was finalized. A full-suite regression (`pytest -q --ignore=worktrees`) closed the loop: 1115 passed, 2 skipped, with the branch diff against `origin/main` confirmed to touch exactly the spec, the plan, and the three expected code files — nothing else.

## Brainstorm Visuals Used

None — same as both prior adapters in this series, this stayed a text-and-code investigation. All four design forks were conceptual/scope questions, resolved via direct multiple-choice questions rather than the visual companion.

## What This Achieved on the Path to Autonomy

This is the third of four planned per-agent adapters, and the first to validate two things simultaneously: that the pattern generalizes to a genuinely simpler output shape (one JSON object, no event stream, no renderer needed), and that the *execution* of an adapter's plan can itself be distributed across the multi-agent fleet rather than routed through a single implementation agent by default — Agy wired its own token-counting logic into `extract_tokens()`, and Grok wired its own dispatch flag. Both were independently verified against the plan with the same rigor as every Codex-dispatched task in the prior two adapters, and both matched exactly. The rotation didn't just distribute load — it exercised the dispatch-then-verify discipline against a wider set of agents' actual code-generation behavior, and surfaced one incidental side-effect bug (the `todo.md` template-regeneration wipe) worth a closer look outside this PR's scope.

## Strategic Note: The Goal at the End of This PR

Three of four structured-output adapters are now live (pending merge of this PR). Same as PR #244 and PR #252, this isn't a release blocker on its own — it's a fast-follow within the already-unblocked v0.12.0 theme, closing more of the gap between `estimated_tshirt` and `estimated_token_rate` for the fleet's token accounting. The next goalpost is unchanged from where PR #252 left it, minus one: Grok's own adapter is the fourth and final deliverable of epic #210's structured-output layer — independently shippable, and per this PR's newly-validated pattern, a candidate for the same cross-agent dispatch rotation rather than a single-agent default.
