# Four-POV Evaluation — Token Usage & Cost Breakdown

**Date:** 2026-07-06
**Session:** Four-POV strategic evaluation + company roadmap (`docs/strategy/2026-07-06-four-pov-evaluation-and-company-roadmap.md`)
**Model:** Claude Fable 5 (`claude-fable-5`) — $10.00 input / $50.00 output per MTok; cache read ≈ $1.00/MTok; cache write (5-min TTL) ≈ $12.50/MTok
**Method:** Parsed the raw session JSONL transcript directly, deduplicated by `requestId`/`message.id` (naive per-line parsing over-counts due to streamed chunks — 18 raw entries collapsed to 7 unique requests for the eval turn).

## Token usage — the four-POV evaluation turn

7 API requests over ~5 minutes (02:24–02:29):

| # | Time | What it was | Fresh input | Cache write | Cache read | Output |
|---|------|-------------|--------:|--------:|--------:|--------:|
| 1 | 02:24:01 | Prompt + system/CLAUDE.md/memory load; intro + first recon batch | 9,690 | 15,995 | 10,540 | 929 |
| 2 | 02:24:11 | Recon results in (LOC counts, README, changelog); next commands | 2 | 13,255 | 26,535 | 385 |
| 3 | 02:24:19 | Locating the roadmap file | 2 | 893 | 39,790 | 146 |
| 4 | 02:24:24 | Roadmap found; issuing the read | 2 | 358 | 40,683 | 174 |
| 5 | 02:25:42 | Writing the strategy doc (after reading roadmap + harness proposal) | 2 | 10,970 | 41,041 | 9,772 |
| 6 | 02:28:08 | Devlog checkpoint append | 131 | 9,855 | 52,011 | 514 |
| 7 | 02:29:07 | Final evaluation message | 2 | 658 | 61,866 | 4,715 |
| | | **Totals** | **9,831** | **51,984** | **272,466** | **16,635** |

**Cost: ~$1.85** for the turn — input $0.10 + cache-write $0.65 + cache-read $0.27 + output $0.83.

Notes:
- ~350K tokens processed total, but 78% were cache reads at 1/10th price — all 7 requests landed inside the 5-minute cache TTL, so the prefix was never re-written mid-turn.
- Output was deliverable-dense: 87% of output tokens (14.5K of 16.6K) went to the two artifacts (strategy doc write + final message). The five recon requests cost only ~2.1K output combined.
- Peak context was ~62K tokens — the whole evaluation fit in one turn with no compaction risk.

## Follow-up: token breakdown/cost-estimate request (this later turn)

Answering the "how much did the context bridge help" question required a 10+ hour cold-cache re-read plus loading the `claude-api` skill for pricing lookup — a useful illustration of the cost of doing this accounting by hand rather than via telemetry.

## How much did synlynk's structured context help?

This session ran Claude Code directly, not through `synlynk exec` — so the literal context bridge (`.synlynk/context.md` injection) was never in the loop. What was in the loop was the documentation discipline synlynk enforces, plus Claude Code's own memory:

1. **`project-docs/roadmap.md`** was the single highest-leverage read — one ~4.5K-token file carried the entire version arc, every epic's status, and spec pointers, substituting for exploring the codebase and 48 blog posts.
2. **MEMORY.md** (auto-memory index, ~200 tokens, zero tool calls) pre-loaded the locked agent-role split, Vizor's strategic position, and project state before any command ran.
3. **CLAUDE.md + CHANGELOG release pitches** gave the architecture map and full v0.11 feature surface from a single `head -50`.

Clearest evidence of payoff: the evaluation covered a 32K-line project (19.7K source + 12.7K tests) without opening a single implementation file — every architectural claim came from maintained docs. Recon was 5 tool rounds, peaking at 62K context; an equivalent evaluation of an undocumented repo this size typically needs 15–25 exploration rounds and 120–180K+ context, often forcing compaction or a subagent.

Estimate (no measured counterfactual exists): structured docs cut input volume roughly 60–70% and request count ~3×, worth approximately $2–4 on this turn, and kept the whole turn inside one warm cache window.

Meta-note: producing this very cost breakdown required hand-scraping Claude Code's JSONL transcript, deduping streaming records, and manually looking up pricing — exactly the kind of accounting synlynk's telemetry is meant to automate. Had this session run under `synlynk exec`, it would have been one row in `costs.md`.
