# synlynk capability report — Design Spec

**Issue:** gh:#1993 — "synlynk capability report: generate task_allocation from capability_ratings/cost_entries"
**Status:** Approved by Nikhil 2026-10-10
**Blocking dependency:** gh:#1926 (state.db consolidation) — CLOSED 2026-10-08.

## Problem

`.synlynk/policy.json`'s `task_allocation` block (which harness runs which task type) is
100% hand-authored. `capability_ratings` and `cost_entries` already record the data needed
to validate or override those defaults empirically (`pr_review_cycles`, `total_cost_usd`),
and `synlynk capability sweep` already runs calibration tasks that populate
`capability_ratings` — but nothing reads this data back into a proposed `task_allocation`
diff for human/PM review.

## Resolved scope questions

**1. `task_type` vs. `discipline` mismatch.** `capability_ratings` and `cost_entries` have
no `task_type` column. The only persisted dimension is `discipline` (backend / testing /
architecture), which `synlynk capability sweep` already writes
(`_SKILL_TO_DISCIPLINE = {"PROG": "backend", "TEST": "testing", "REQM": "architecture"}`
in `synlynk/capability_sweep.py`), and which `synlynk/dispatch.py`'s
`_get_local_capability_score()` already treats as the stand-in for `task_type` when routing
local-model dispatches. `task_type` itself exists only ephemerally, as a CLI argument
(`--task-type`) and inferred value (`_infer_task_type()`) used at dispatch-routing time in
`synlynk/dispatch.py` and `synlynk/cli.py` — it is never persisted to either table.

**Decision:** reuse the existing discipline vocabulary. Add an explicit
`_TASK_TYPE_TO_DISCIPLINE` crosswalk dict in `synlynk/capability.py` rather than adding a
new schema column or deferring the report until historical data is re-tagged.

**2. Single-workspace vs. fleet-wide scope.** `.synlynk/policy.json`'s own
`capability_policy.blocking_dependency` note draws a distinction the issue body doesn't:
single-workspace `task_allocation` generation (this repo's own policy.json) only needs this
workspace's canonical `state.db` and does not require #1926. Fleet-wide aggregation across
multiple synlynk workspaces remains blocked on #1926 **and** gh:#1831 (shard consolidation),
which is still open.

**Decision:** scope this feature to single-workspace only. Fleet-wide aggregation is a
separate future issue, filed once gh:#1831 closes.

**3. Output destination.** The issue requires the report to propose a diff "for
human/PM review — not an auto-write."

**Decision:** stdout diff (default, changed entries only) + optional `--out <path>.json`
for a full structured dump. Nothing writes to `.synlynk/policy.json` itself.

## Architecture

Add `capability_report()` to `synlynk/capability.py`, alongside the existing
`ranked_harness_for_task()` (which already implements the median-cycles / sample-gate
logic this feature needs, just for one task_type/candidate-list at a time). Add a new
`synlynk capability report` CLI subcommand in `synlynk/cli.py`, as a sibling to the
existing `capability sweep` subcommand.

### Discipline crosswalk

```python
_TASK_TYPE_TO_DISCIPLINE = {
    "implement": "backend", "refactor": "backend", "cli-plumbing": "backend",
    "infra": "backend", "canvas": "backend", "js": "backend",
    "test": "testing",
    "css": "backend", "templates": "backend", "content": "backend", "subpages": "backend",
    "review": "architecture", "architecture-review": "architecture",
    "pm": "architecture", "brainstorm": "architecture", "deploy": "architecture",
    "gh_write": "backend",
}
```

Matches the discipline vocabulary already in use by `capability_sweep.py` and
`dispatch.py`'s local-score lookup — no new vocabulary introduced.

### Metric computation — per-merged-PR cost correction

`.synlynk/policy.json`'s `capability_policy.metric_source` documents
`total_cost_usd` as "median per merged PR." `ranked_harness_for_task()`'s existing query
instead averages `cost_entries.total_cost_usd` per *row*, which is overweighted for a
story/harness with several small retry-related cost_entries rows versus one that got it
right in a single pass. `capability_report()` uses a separate query that groups
`cost_entries` by `pr_number` first (`SUM(total_cost_usd) GROUP BY pr_number, harness`),
then takes the median across those per-PR sums. This is a new query local to
`capability_report()` — `ranked_harness_for_task()` itself is left unchanged, to avoid
touching its existing callers/tests.

### Algorithm

For each `task_type` in `.synlynk/policy.json`'s `task_allocation`:
1. Map `task_type` → `discipline` via the crosswalk. If no mapping exists, skip with a
   `WARN` line (never fail the whole report).
2. Query every harness with `capability_ratings` rows for that `discipline`
   (`JOIN cost_entries ON story_id`, same join shape as `ranked_harness_for_task()`).
3. Compute, per harness: `sample_count`, median `pr_review_cycles`,
   median per-PR `total_cost_usd` (see above).
4. Discard any harness with `sample_count < capability_policy.min_sample_size` (default 5).
5. Compare every remaining harness against the current incumbent
   (`task_allocation[task_type].harness`). A harness is proposed only when it beats the
   incumbent on **both** median cycles and median cost — matching
   `ranked_harness_for_task()`'s existing promotion rule.
6. If a harness qualifies, emit a diff entry: `{task_type, incumbent, proposed, incumbent_stats, candidate_stats, reason}`.
7. Entries are only included in the report when `proposed != incumbent` (default stdout
   view); `--verbose` additionally shows task_types that were evaluated but produced no
   change (including an explicit "insufficient samples" reason).

### CLI output

Default stdout: a table of only the task_types with a proposed change. Example:

```
Capability Report — generated 2026-10-10 from this workspace's state.db

task_type   incumbent  proposed  samples  median_cycles  avg_cost/PR  reason
implement   codex      grok      6        1.0            $4.20       grok: 1.0 cycles/$4.20 vs codex: 2.5 cycles/$9.10 (n=6)
```

`--verbose` additionally lists unchanged/insufficient-sample task_types.
`--out <path>.json` writes the full structured result (every task_type evaluated, raw
stats included) for attaching to a PR description. No flag writes to
`.synlynk/policy.json` — a human applies the diff manually, per the issue's "not an
auto-write" requirement, and separately updates `capability_policy.generator_status`.

### Error handling

- Missing/malformed `task_allocation` in `.synlynk/policy.json` → hard error, clear message.
- `task_type` with no crosswalk entry → `WARN`, skip that entry, continue the report.
- Harness below `min_sample_size` → included only under `--verbose`, as "insufficient
  samples"; never promoted regardless of how good its metrics look.

### Testing

Unit tests in `tests/test_capability.py` (reusing the existing in-memory sqlite fixture
pattern used for `ranked_harness_for_task()`'s tests):
1. Crosswalk resolves without `KeyError` for every current `task_allocation` key in
   `.synlynk/policy.json`.
2. Per-PR cost aggregation correctly sums multiple `cost_entries` rows sharing one
   `pr_number` before taking the median (regression test for the per-row averaging bug
   this design fixes relative to `ranked_harness_for_task()`).
3. A harness below `min_sample_size` never appears as `proposed`.
4. A task_type with zero qualifying harnesses produces no diff entry.
5. CLI-level test: `--out` writes valid JSON; default stdout excludes unchanged entries.

## Out of scope

- Fleet-wide / cross-workspace aggregation (blocked on gh:#1831).
- Auto-writing `.synlynk/policy.json` or `docs/harness-capability-baseline.md`.
- Changing `ranked_harness_for_task()`'s existing per-row cost averaging (left as-is for
  its current callers; only the new report uses per-PR aggregation).
- Adding a persisted `task_type` column to any table — this is an explicit decision to
  reuse `discipline`, not a deferred TODO.
