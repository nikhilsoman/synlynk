# Story ID Auto-Provisioning for Ad-Hoc Dispatches — Design

**Date:** 2026-07-19
**Status:** Proposed

## Problem

`capability_ratings.story_id` is a `NOT NULL` foreign key into `stories`. Every ad-hoc
`synlynk dispatch` invocation driven by a bare GitHub issue (not a planned `todo.md`/roadmap
story) currently omits `story_id` — confirmed via direct `sqlite3` query against this project's
`state.db`: zero `capability_ratings` rows exist for any job dispatched this session (#404, #395's
fix, both PR review jobs), despite all of them completing real, verifiable work. `capability_scores`
(the time-decayed aggregate view keyed on `agent, model_version, engg_domain, org_domain, industry,
phase`) is therefore silently blind to this entire class of dispatch — likely dozens of jobs across
the project's history.

The gap is structural, not accidental: nothing in `dispatch_agent()` requires or infers a
`story_id`, and relying on the dispatcher (Claude, as PM) to remember to pass one by hand is the
exact discipline failure that produced the gap in the first place.

## Goals

1. Every future ad-hoc, issue-driven dispatch gets a `story_id` automatically, with no extra step
   required from the dispatcher.
2. Repeated dispatches against the same issue (implementer, then reviewer, then rework) roll up
   onto one story, so per-issue aggregates (rework counts, the PR review-cycle multiplier) stay
   coherent.
3. Recover capability signal from jobs that already ran without a `story_id`, where the job's log
   and worktree still exist to derive real quality signal from.
4. Classification quality (engg_domain/org_domain/role/stage) is a config-selectable strategy, not
   hardcoded, so it can be upgraded later without changing the dispatch call sites.

## Non-Goals

- Building the LLM-classification or PM-manual-classification strategies now — only `heuristic` is
  implemented in this pass. The config surface exists so they can be added later without a
  breaking change.
- Retrofitting jobs whose logs/worktrees have already been deleted (e.g. `job-251378ce`, removed
  earlier this project for an unrelated reason) — these are unresolvable and get skipped with a
  warning, not silently dropped nor fabricated.
- Changing how *planned* work (stories created via `todo.md`/roadmap flow) is dispatched — this
  design only affects the ad-hoc/GitHub-issue path.

## Architecture

### 1. `synlynk/story_provisioning.py` (new module)

`resolve_or_create_story_id(task_text: str, issue: Optional[int] = None) -> str`

Called from `dispatch_agent()` whenever the caller does not pass an explicit `story_id`:

1. **Issue detection**, in priority order:
   - Explicit `--issue N` flag (new, optional, on `synlynk dispatch`)
   - Regex `#(\d+)` scanned across `task_text`
   - Neither found → ad-hoc fallback (step 2c below)
2. **Deterministic story_id derivation:**
   - Issue found → `story-issue-<N>` (e.g. `story-issue-395`). Deterministic so a second dispatch
     against the same issue resolves to the same `story_id` instead of minting a new one.
   - No issue found → `story-adhoc-<YYYYMMDD-HHMMSS>` (fresh per dispatch — there's no natural key
     to reuse for a non-issue-linked ad-hoc task).
3. **Story existence check + creation:** query `stories` for the derived `story_id`; if absent,
   classify (see below) and call the existing `cmd_story_create()` with the derived id, an
   issue-derived title, and the classified enum fields. If present, reuse it as-is (no
   re-classification on repeat dispatch — the first classification stands for the life of the
   issue).

`dispatch_agent()` change: where `story_id` is currently read straight from CLI args, fall back to
`resolve_or_create_story_id(task, issue=args.issue)` when it's empty/absent. This is the only
change to the dispatch path itself — the module above owns all new logic.

### 2. Classifier strategy (config-selectable)

New `.synlynk/config.json` block:

```json
"story_classification": {
  "method": "heuristic"
}
```

`method` accepts `"heuristic"` (implemented now), `"llm"`, `"pm_manual"` (both raise
`NotImplementedError("story classification method '<name>' is not yet implemented")` if selected —
explicit failure, not a silent fallback, so a misconfiguration is caught immediately rather than
quietly degrading to defaults).

**Heuristic classifier** (`synlynk/story_provisioning.py::_classify_heuristic`):
- Fetches `gh issue view <N> --json labels,title,body` when an issue number is available.
- Matches labels/keywords against the same fixed enums `cmd_story_create()` already validates
  (e.g. label `backend` → `engg_domain=backend`; label `frontend` → `engg_domain=frontend`).
- Falls back to `engg_domain="unknown"`, `org_domain="platform"`, `role="dev"`, `stage="build"`
  when nothing matches — mirroring the existing "remap to unknown, warn" pattern already used in
  `_migrate_db()`'s org_domain remapping.
- No issue number available (ad-hoc fallback case) → skips the `gh` call entirely and uses the
  same defaults immediately.

### 3. Backfill command

`synlynk backfill-capability-ratings` (new subcommand, one-off/idempotent — safe to re-run):

1. Reads `.synlynk/jobs.json` (last 100 entries) plus any `.synlynk/logs/*.summary` files still on
   disk, for jobs with `story_id == ""`.
2. Applies the same issue-detection regex to each job's `task` field.
3. Resolves/creates a story via the identical path `dispatch_agent()` now uses (so backfilled and
   future stories are indistinguishable in shape).
4. Re-invokes `_write_capability_rating(job, log_text)` using the job's already-captured log —
   this is exactly what would have run at job completion, just delayed.
5. Skips (with a printed warning identifying the job id) any job whose log file or worktree no
   longer exists — never fabricates a rating from absent data.
6. Prints a summary: `N backfilled, M skipped (reason)`.

## Data Flow

```
synlynk dispatch codex --task "Fix #395: worktree base bug"
  → dispatch_agent(): story_id arg empty
  → resolve_or_create_story_id("Fix #395: worktree base bug")
      → regex finds #395
      → story_id = "story-issue-395"
      → stories table: no row for story-issue-395
      → _classify_heuristic(issue=395)
          → gh issue view 395 --json labels,title,body
          → labels=["bug"], title="files_touched shows bogus..."
          → engg_domain=backend (matched), org_domain=platform (default)
      → cmd_story_create(story_id="story-issue-395", ...)
  → job dispatched with story_id="story-issue-395"
  → (later) _write_capability_rating(job, log) succeeds — story_id satisfies FK
```

## Testing

- Unit tests for `resolve_or_create_story_id()`: issue found via flag, issue found via regex, no
  issue (ad-hoc fallback), repeat dispatch against existing story_id reuses it without
  re-classifying.
- Unit tests for `_classify_heuristic()`: label match, keyword-only match (no labels), no match
  (defaults), `gh` call failure (network/auth) handled without crashing the dispatch.
- Unit test for the `NotImplementedError` path when `method` is `"llm"` or `"pm_manual"`.
- Integration test for `backfill-capability-ratings`: seeded `jobs.json` with a mix of
  resolvable and log-missing entries, asserts correct backfilled/skipped counts and that
  `capability_ratings` rows appear only for the resolvable ones.

## Open Question Resolved During Brainstorm

All decisions below were confirmed with the user directly (2026-07-19):

- Auto-create story at dispatch time, not a separate manual step (closes the gap unconditionally).
- Backfill all resolvable past jobs, not just this session's or none.
- Classification starts with a heuristic strategy; config leaves room to add `llm`/`pm_manual`
  later without changing call sites.
- One story per issue, shared across repeat dispatches (implementer + reviewer + rework all
  roll up together).
- Issue number detected via regex on task text, with an explicit `--issue` flag as an override/
  fallback, and a generic ad-hoc story as the last resort so nothing dispatched ever goes unrated.
