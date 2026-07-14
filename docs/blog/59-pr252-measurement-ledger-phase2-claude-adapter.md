---
title: "PR #252 — Measurement Ledger Phase 2: The Claude Structured-Output Adapter"
date: 2026-07-15
series: "Building the OS for Multi-Agent Development"
post: 59
pr: "#252"
merged: pending
---

## The Broader Goal at the End of the Previous PR

PR #244 shipped the first of four planned per-agent structured-output adapters — Codex — and validated the pattern end to end: `extract_tokens()` gains an `agent=` parameter, tries a per-agent `_extract_<agent>_structured()` function first, and falls through to the existing regex chain on any failure, silently and automatically. That PR's own closing note named the next goalpost explicitly: "the same pattern, three more times" — Claude, Gemini, Grok — each independently shippable, each requiring its own live-verified investigation of that CLI's actual structured-output shape rather than an assumption carried over from Codex's.

## Strategic Shifts in This PR

Two genuine design forks came up during brainstorming, both resolved by asking rather than assuming, per this project's established discipline of flagging non-obvious decisions explicitly.

**Cost capture scope.** Claude's `result` event carries a top-level `total_cost_usd` field — a dollar figure the CLI itself computes, and something no other agent's structured output reports. The tempting move is to capture it, since it's free and precise. It was deliberately declined: wiring in a per-agent dollar figure would break the uniform token-counts-only contract every adapter (and `_resolve_cost_tier()`) currently shares, for a benefit (Claude-only cost precision) that doesn't generalize to the other three agents still to come. Token-only, same shape as Codex.

**Log-rendering depth.** Claude's stream-json carries meaningfully richer event structure than Codex's — `assistant` events with mixed `text`/`tool_use` content blocks, `user` events carrying `tool_result` responses between turns, `rate_limit_event` noise. The question was whether `synlynk logs` needed full parity with Codex's readable-prose rendering, or just enough noise-suppression to keep the raw JSONL from being unreadable. Full parity was chosen — text blocks render as prose, `tool_use` blocks render as `$ ToolName(args)`, matching the bar Codex's `_render_codex_log_line()` already set.

## What This PR Shipped

The live investigation came first, same as the Codex pilot: running `claude -p --output-format stream-json --verbose` directly and capturing real output, not working from memory. Two things confirmed by that investigation shaped the design meaningfully:

`--verbose` turned out to be a hard requirement, not an optional nicety — the CLI refuses to start with `--print --output-format stream-json` unless `--verbose` is also present, confirmed by deliberately omitting it and reading the resulting error. And Claude's `usage` object has a shape genuinely different from Codex's: `cache_creation_input_tokens` and `input_tokens` are separate, additive pools (confirmed across a 1-turn and a 2-turn live test — the ratio between them can be three to four orders of magnitude), unlike Codex's `cached_input_tokens`, which is a subset of `input_tokens`. Folding `cache_creation_input_tokens` into `input_tokens` was the only option that didn't grossly undercount, given Phase 1's rate table has no separate cache-write tier.

Five commits landed on top of the design/plan docs:

- **`synlynk/costs.py`** — `_extract_claude_structured()` scans every line for the single `type: "result"` event (there's exactly one per invocation, carrying cumulative `usage`), returning `None` on any parse failure so the existing regex chain still applies unchanged. `extract_tokens()` gained a sibling `if agent == "claude":` branch immediately after the existing Codex one — no shared abstraction introduced; the spec's own precedent explicitly deferred a registry pattern until a fifth or sixth agent makes the flat `if` chain unwieldy.
- **`synlynk/dispatch.py`** — `--output-format stream-json --verbose` added to Claude's flag list in `dispatch_agent()`, as a sibling to the existing `if agent == "grok":`/`if agent == "codex":` blocks.
- **`synlynk/__init__.py`** — `_render_claude_log_line()` added, handling `assistant` events (rendering `text` and `tool_use` content blocks), and suppressing `system`/`rate_limit_event`/`result`/`user` events as noise. `cmd_logs()`'s two-way codex/passthrough dispatch became a three-way dispatch (codex renderer / claude renderer / raw passthrough) — unparseable lines still print as-is under every branch, so a pre-flag-change job or a crashed job's raw stderr stays visible.
- **`tests/test_cost_ledger.py`** — grew by 30 tests across all five tasks, directly mirroring the Codex adapter's own test suite shape (adapter unit tests, `extract_tokens` cross-agent tests, dispatch-flags test, renderer tests, `cmd_logs` integration tests).

**Process note, consistent with the discipline PR #244 established:** every implementation task was dispatched to Codex individually via `synlynk dispatch codex --task "..." --force-agent`, and every dispatch was independently verified before merging — reading the actual diff against the plan, then running the relevant test slice myself, rather than trusting the dispatched job's self-reported result. All five tasks matched the plan's specified code exactly on the first attempt; no defects were caught this time, which is itself a useful signal that a fully-specced plan with complete code in every step (per the writing-plans skill's no-placeholders rule) reduces the room for a dispatched agent to drift. A full-suite regression run (`pytest -q --ignore=worktrees`) closed the loop: 1100 passed, 2 skipped, with a separate `-k "codex or grok"` pass confirming zero collateral impact on the previously shipped adapter.

## Brainstorm Visuals Used

None — same as the Codex pilot, this stayed a text-and-code investigation. The two design forks (cost-capture scope, log-rendering depth) were conceptual/scope questions, not visual ones, and were resolved via direct multiple-choice questions rather than the visual companion.

## What This Achieved on the Path to Autonomy

This is the second of four planned per-agent adapters, and it stress-tests the pattern PR #244 established against a CLI with a meaningfully different output shape — mixed content-block events instead of Codex's flatter `item.completed` structure, and an additive rather than subset cache-token relationship. The pattern held without modification: one function, one dispatch branch, one renderer, zero changes required to `_resolve_cost_tier()` or any of Phase 1's provenance machinery. Gemini and Grok remain, and each still gets its own live investigation rather than a copy-paste of this shape — Claude's own `cache_creation_input_tokens` surprise is the reason that discipline stays non-negotiable.

## Strategic Note: The Goal at the End of This PR

Two of four structured-output adapters are now live (pending merge of this PR). Same as PR #244, this isn't a release blocker on its own — it's a fast-follow within the already-unblocked v0.12.0 theme, closing more of the gap between `estimated_tshirt` (coarse guess) and `estimated_token_rate` (precise, agent-native number) for the fleet's token accounting. The next goalpost is unchanged from where PR #244 left it, minus one: Gemini and Grok, each independently shippable, each requiring the same live-verification discipline this PR just re-validated was worth the effort.
