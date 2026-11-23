# RCA: [LIVE-35] Native-session cost capture is missing from the ledger

**Date:** 2026-11-23
**Severity:** Sev1 (correctness of the cost and capability record)
**Status:** Root cause confirmed. No fix shipped. Action items below are unticketed pending sign-off.
**Tracking issue:** gh:#5457 (OPEN)
**Related:** gh:#510 (flat-rate divergence), gh:#5419 (intake epic whose PRs exposed the gap)

## Summary

The PM session could not log real token counts for PRs #5420, #5425, #5433, #5447 and #5453, so their `synlynk cost log` entries stayed missing. The founder remembered session-JSONL cost logging, billing-type identification, relative cost tracking and quota-tracked dispatch as built. An exhaustive search found that quota-tracked dispatch, config-driven billing type and relative cost exist. It found no synlynk code that reads Claude Code's own session transcripts. It found one out-of-repo script that does, and that script overcounts by about 2x.

## What was searched

Tracked code, tests, docs, specs, plans, blog and decisions. Git history on all refs, by pickaxe and by commit message. Stashes and unmerged branches. `~/.claude` (hooks, scripts, costs, settings), `~/dotfiles`, `~/.synlynk`, and sibling repos under `~/dev`. Not searched: other machines, or clones on a different host.

## Findings

### Built and working

| Capability | Location |
|---|---|
| Quota-tracked dispatch | `synlynk/quota.py`, `quota_capture.py`, migrations m0020 and m0031; specs 2026-08-08, 2026-10-10, 2026-10-31 |
| Billing type and relative cost | `.synlynk/billing.json` `harness_billing.<h>.payment_mode`; amortization and true-up (spec 2026-09-02, PR #1337); payment-mode and relative-cost columns in `cost_entries` |
| Token capture for dispatched jobs | `costs.py` stream-json adapters for Claude, Codex, Grok and Agy |
| Codex and Grok session-log scraping | `quota_capture.py`, quota percentages only, not token counts |
| Claude quota | `claude -p "/usage"` text parse |

### Missing

1. No synlynk code parses `~/.claude/projects/**/*.jsonl`. `git grep` over `synlynk/ bin/ scripts/ tests/ .github/` and all-refs pickaxes on `.claude/projects`, `transcript_path` and `cache_read_input_tokens` find only the dispatch adapters.
2. The repo's own SOP (`docs/sop/worktree-and-cost-hygiene.md`) states there is no automatic capture for native CLI sessions, and that the protocol is enforced by discipline, not CI.
3. Billing type is configured by hand. Nothing inspects whether the logged-in account is a subscription or an API key. `billing.json` declares every harness `subscription`.
4. Native-session `cost_entries` rows are `estimated_manual` with round numbers (for example 120000/15000 and 50000/8000) and the note "no per-turn telemetry for native session". The earliest seen is 2026-10-21.

### The existing parser

`~/.claude/costs/calc_costs.py` (dated 2026-04-17) parses session JSONL. It lives outside the repo, is not in dotfiles, and nothing references it. Measured on session 124f8b4d:

| Field | Script-style sum | De-duplicated by `message.id` | Overcount |
|---|---|---|---|
| input | 1,910 | 1,026 | 1.86x |
| output | 546,199 | 243,094 | 2.25x |
| cache_creation | 4,655,239 | 2,218,297 | 2.10x |
| cache_read | 104,204,341 | 54,415,618 | 1.91x |

It does not de-duplicate streamed messages, hardcodes Sonnet 4.6 prices, ignores subscription versus API billing, and uses Linux path slugs. It reports $555.50 for this project.

## Root cause

A design and ownership gap. Native Claude Code sessions sit outside the dispatch wrapper, which sees stream-json, and outside the quota scrapers, which read percentages. Three partial mechanisms exist in three places (a personal script, a statusline, a manual CLI), and none feeds the ledger. The "discipline, not CI" decision left no failing signal when an entry is skipped. `cost log` requires typed token counts that the PM session cannot know, so the practical outcomes were a guess or no entry.

This RCA does not demonstrate a code regression. No removed implementation was found. If one existed on another machine, the root cause section should be revised.

## Impact

- Native PM, review and brainstorm cost is missing or guessed in `cost_entries`.
- Empirical routing under the Empirical Capability Assessment Policy runs on dispatch data only, which understates the harness doing the most native work.
- Subscription true-up and quota burn estimates exclude native usage.
- The only tool producing numbers (`calc_costs.py`) overstates them by about 2x.

## Timeline

- **2026-04-17.** `calc_costs.py` written outside the repo.
- **2026-10-21 and earlier.** Native rows logged as `estimated_manual` guesses.
- **2026-11-20 to 2026-11-23.** Intake epic #5419 PRs merge without cost rows.
- **2026-11-23.** Filed as a ticket, then escalated to Sev1 on the founder's report that the feature had been built. Exhaustive search completed the same day.

## Action items

1. `synlynk cost capture-session` (or `cost log --from-transcript`): de-duplicate by `message.id`, sum per model, attribute sidechains, read counts only and never content.
2. A `Stop` or `SessionEnd` hook that calls it, installed and verified by `synlynk init` and `doctor`, as an idempotent upsert keyed by session id.
3. Account-type detection (OAuth subscription versus API key) feeding `payment_mode`, with config as override.
4. A per-model price table replacing the hardcoded Sonnet 4.6 rates in the statusline and scripts.
5. A `synlynk pr check` observe-mode warning when a native PR has no cost row.
6. A backfill that recomputes historical `estimated_manual` rows from surviving transcripts, tagged `transcript_derived`, and relabels the rest.
7. Fix or retire `calc_costs.py` now.

Open design question: one session spans several PRs, so attribution needs a rule (split by message timestamps between PR events, or log at session level with an explicit PR list).

## Prevention

- Treat any protocol "enforced by discipline" that depends on data the actor cannot see as a defect, not a convention.
- Add a doctor check that fails when native sessions exist in the transcript directory with no matching ledger rows.
- Add a format-drift test for the transcript parser, since the transcript format belongs to Claude Code.
