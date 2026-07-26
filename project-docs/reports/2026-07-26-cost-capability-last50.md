# Cost / Capability Report — Last 50 Job Cost Entries

Generated 2026-07-26 from `~/.synlynk/projects/13267207/state.db`.

## Coverage summary

| Metric | Value |
|---|---|
| Cost entries examined | 50 (most recent by `recorded_at`) |
| Total cost | $26.29 |
| Entries with a `story_id` (discipline-taggable) | 8 / 50 |
| Entries `cost_source = legacy_unknown` (pre-taxonomy, no story link) | 41 / 50 |
| Cost concentrated in the 8 tagged entries | $25.21 (96% of total) |

**Finding:** discipline/SFIA tagging is only possible for 8 of the last 50 rows. The other 41 are `legacy_unknown` — logged before story/discipline tracking existed, not a join bug. They're mostly near-zero-cost stub rows, so the dollar coverage (96%) is much better than the row coverage (16%).

## Discipline breakdown (tagged rows only, n=8)

| Discipline (raw `stories.discipline`) | Count | Notes |
|---|---|---|
| `backend` | 4 | legacy string, not yet SFIA-coded |
| `security` | 4 | legacy string, not yet SFIA-coded |

None of the 8 tagged rows have run through the SFIA crosswalk (`taxonomy_standards.py`) yet — `stories.discipline` is a mixed column: some rows already hold true SFIA codes (`PROG`, `DEPL`, `SCTY`, `DTAN`), others still hold pre-crosswalk legacy strings (`backend`, `testing`, `cli`, `docs`, etc.). `stories.legacy_unmapped` flags which: 86 of 184 story rows repo-wide are still `legacy_unmapped=1`. The `_taxonomy_crosswalk_state` table shows `completed=1`, i.e. the one-time backfill ran, but it evidently didn't rewrite every existing row — worth a follow-up issue if full SFIA normalization matters for reporting.

## By agent (n=50)

| Agent | Entries |
|---|---|
| codex | 28 |
| grok | 10 |
| agy | 7 |
| nikhil (manual `cost log`) | 4 |
| claude | 1 |

## Token/cost columns available vs. not

`cost_entries` has `input_tokens`, `output_tokens`, `cache_read_tokens`, `total_cost_usd` per row — reliable, DB-native.

**No thinking-token or tool-use-count column exists anywhere in the schema.** Confirmed by re-checking log formats:
- Codex `.log` files end with a bare `tokens used\n<total>` line — a single combined total, no input/output/thinking split.
- Only 136 of 263 `.synlynk/logs/*.summary` files have a matching `.log` (raw transcript); the rest have only the `.summary` (cost/exit-code rollup, no transcript).
- The 4 jobs whose worktrees I removed this session (`job-b5df15ce`, `job-e6a66ce6`, `job-0d3b2b0f`, `job-da38baad`) each have only a `.summary` in the top-level `.synlynk/logs/` — no `.log` — so thinking/tool-use detail for those 4 is **not recoverable**, matching Thursday's report's treatment of its 16 pre-telemetry jobs as "not captured."

**Conclusion:** for any future report needing a thinking/tool-use breakdown, budget for per-log scraping (as Thursday's did) rather than a DB query — the data isn't persisted in a structured column, and roughly half of jobs don't even have a raw log to scrape from.

## Recommendation

If discipline/SFIA breakdowns are going to be a recurring report, the crosswalk backfill needs a second pass — `_taxonomy_crosswalk_state.completed=1` is misleading since 86 story rows are still `legacy_unmapped`. Worth its own issue rather than silently re-running ad hoc per report.
