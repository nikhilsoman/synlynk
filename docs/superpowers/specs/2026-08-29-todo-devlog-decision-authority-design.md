# Design: state.db authority for todo.md, devlogs, and decision records

**Status:** Approved by Nikhil 2026-08-29
**Resolves:** #1219 (state.db-vs-markdown authority decision), #936 root causes #1 and #2, folds in #1218 (checkpoint() todo_path migration-unaware bug)
**Related:** LIVE-11 (#1217), RCA at `docs/rca/2026-08-29-LIVE-11-checkpoint-todo-path-migration-unaware.md` (PR #1221)

## Problem

Two things this project's own docs already claim are true, and aren't:

1. `project-docs/todo.md` is stamped (in the DB-generated variant's header) "source of truth is state.db" — but the file every session actually reads/writes (`checkpoint()`'s hardcoded `project-docs/todo.md`) has never been connected to state.db. The real DB-driven generator (`_generate_todo_md()`) only fires on `create_story()`, and in this repo has only ever produced 2 placeholder rows.
2. `checkpoint()` never writes devlog entries to state.db at all (#936 root cause #1) — devlogs are flat-file only, with no index.
3. `cmd_decide()` resolves its write path without checking `_is_migrated()` (#936 root cause #2), so decision records can silently land in a gitignored, untracked path post-migration.

All three are instances of the same unresolved question: for a given project-docs file, is markdown or state.db actually authoritative, and does the code match whichever answer is claimed? This spec answers that question per file type and describes the mechanism to make the code match it.

## Decision: three-way split by file nature

| File type | Model | Rationale |
|---|---|---|
| `todo.md` | **Fully generated** — state.db authoritative | Structured checkbox list; title/status/domain map directly onto `stories` table columns. Matches the claim the file already makes. |
| `devlogs/<user>.md` | **Indexed, not replaced** — markdown authoritative, state.db indexes it | Free-text narrative. Forcing it into rows would destroy what makes a devlog useful. state.db gains a queryable index; the strategy doc's "index and protect the devlog, not replace it" framing is upheld. |
| `decisions/*.md` | **Indexed, not replaced** — markdown authoritative, state.db indexes it | Already CLI-authored prose via `synlynk decide --record`, not hand-edited freeform like todo.md. Same treatment as devlogs. |

No hybrid attempted for todo.md — it goes fully to state.db authority, matching the user's explicit (a)-leaning decision.

## Mechanism: todo.md

### Automatic, guarded backfill

On the first `checkpoint()` call after this change ships in a given repo:

1. Check a one-time completion marker (a `todo_backfill_completed_at` field in `.synlynk/config.json`, or an equivalent state.db metadata row if the repo predates `.synlynk/config.json`). If present, skip straight to normal generation (step 4 below).
2. If absent: read the existing `todo.md` (migration-aware path — `.synlynk/project-docs/todo.md` if `_is_migrated()`, else `project-docs/todo.md`).
3. Parse each checkbox line matching `- \[([ x-])\] (.+)`:
   - `[x]` → `status = "done"`
   - `[-]` → `status = "deferred"`
   - `[ ]` → `status = "open"` (maps to whatever the `stories` table's default/non-done/non-deferred status value is)
   - Extract any `#NNN` GitHub issue reference in the line text and store it in the story's title/metadata so the link survives (no new column required — embed as `<!-- gh:#NNN -->` trailer in the generated title field, consistent with the existing `<!-- id:story-... -->` convention `_generate_todo_md()` already uses).
   - Lines that don't match the checkbox pattern (section headers, free-form notes, sub-bullets without their own checkbox) are skipped, not inserted.
4. Insert one `stories` row per successfully parsed line via the same insert path `create_story()` uses, skipping any row whose parsed title exact-matches an existing `stories` row (prevents duplicate inserts if backfill is somehow re-triggered before the marker is set).
5. Set the completion marker.
6. Proceed to normal generation (below).

If a line fails to parse (unexpected format), log a warning naming the line and skip it — do not abort the whole `checkpoint()` call over one bad line.

### Regeneration on every mutation

`_generate_todo_md()` is called from:
- `create_story()` (existing behavior, unchanged)
- a new `update_story_status()` function (new — currently no such function exists; status changes have no call site today)
- `checkpoint()` itself, after it archives completed items into the devlog (see below) and updates their `stories` row status to `"done"`

`checkpoint()`'s current behavior of directly reading and rewriting `todo.md` is retired. Its new behavior:
1. Query `stories` table for rows with `status IN ("done", "deferred")` that haven't yet been archived (tracked via a new `archived_at` column on `stories`, nullable).
2. For each, append a line to the devlog (same archival behavior as today, just sourced from state.db instead of parsed from the markdown file) and set `archived_at`.
3. Call `_generate_todo_md()` to rewrite `todo.md` from the now-current `stories` table state.

This is where the #1218 path bug gets fixed as a side effect: `checkpoint()` no longer has its own `todo_path` variable at all — path resolution lives solely in `_generate_todo_md()`, which is already correctly migration-aware. #1218 should be closed as superseded by this spec rather than fixed separately.

### Hand-edit drift handling

Both `synlynk doctor` and `checkpoint()` (at the start of its run, before any writes) compute what `_generate_todo_md()` would currently produce and diff it (ignoring trailing whitespace) against the file on disk. If they differ:
- Print a warning: `todo.md has been hand-edited since the last checkpoint; state.db is authoritative, hand-edits will be overwritten. To make this change permanent, use 'synlynk story create/update' instead.`
- Proceed with normal regeneration (overwrite).

No blocking. No separate reconcile command. This is a deliberate choice: the warning is the enforcement mechanism, and it corrects the current false claim without adding friction to every session.

## Mechanism: devlogs

New state.db table `devlog_entries`:

```sql
CREATE TABLE devlog_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    author TEXT NOT NULL,
    canonical_id TEXT NOT NULL,
    story_ids TEXT,           -- comma-separated story_id references, nullable
    devlog_path TEXT NOT NULL,
    line_offset INTEGER,      -- line number in the markdown file where this entry starts
    created_at TEXT NOT NULL
);
```

`checkpoint()` gains a write to this table, one row per devlog entry it writes, at the same point it currently appends to the markdown file. The markdown append itself is unchanged — devlog content stays hand-written prose, authored the same way it is today. No generation, no drift-detection, no hand-edit guard for devlogs — the index is purely additive metadata, not a competing source of truth.

This resolves #936 root cause #1.

## Mechanism: decisions

1. `cmd_decide()` / `_write_decision_record()` (`synlynk/team.py`) gets the same `_is_migrated()` branch that `devlog_path` already uses correctly elsewhere — a direct, narrow fix, no new mechanism. This is the literal #936 root cause #2 bug.
2. New state.db table `decision_entries`:

```sql
CREATE TABLE decision_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    decision_id TEXT NOT NULL,
    title TEXT NOT NULL,
    story_ids TEXT,
    decision_path TEXT NOT NULL,
    created_at TEXT NOT NULL
);
```

`_write_decision_record()` inserts one row here alongside writing the markdown file. Same additive-index treatment as devlogs — markdown stays the authored artifact.

## Rollout

1. Schema migration adds `devlog_entries`, `decision_entries` tables, and the `archived_at` column on `stories`.
2. No separate backfill command — the todo.md backfill is folded into `checkpoint()`'s first post-upgrade run as described above. Devlogs/decisions need no backfill (indexes only track new entries going forward; historical entries aren't retroactively indexed, since there's no reliable way to parse "which devlog line corresponds to which story" for old free-text entries).
3. `#1218` closed as superseded by this spec (comment linking here) rather than implemented as a standalone fix.
4. `#1220` (doctor drift check) is implemented as part of this spec's hand-edit drift handling (the doctor-side half of the diff-and-warn logic described above), rather than as a separate follow-up.

## Testing

- `checkpoint()` exercised in both migrated and pre-migration states: confirms todo.md read/write happens at the correct path via `_generate_todo_md()`, with no direct path literal remaining in `checkpoint()`.
- Backfill: run `checkpoint()` against a repo with an existing hand-written `todo.md` containing `[ ]`, `[x]`, `[-]` lines and malformed lines; confirm correct `stories` rows are inserted, malformed lines are skipped with a warning, and the completion marker is set.
- Backfill idempotency: run `checkpoint()` a second time; confirm no duplicate `stories` rows are inserted and the parse step is skipped entirely (marker present).
- Regeneration: `synlynk story create` and a new `synlynk story update <id> --status done` both trigger `_generate_todo_md()` and are reflected in `todo.md` without a `checkpoint()` call.
- Hand-edit drift: manually edit `todo.md` to diverge from state.db, run `checkpoint()`, confirm the warning is printed and the file is overwritten to match state.db.
- Devlog index: `checkpoint()` archiving an entry produces both the markdown append and a matching `devlog_entries` row.
- Decision path fix: `cmd_decide()` in a migrated repo writes to `.synlynk/project-docs/decisions/`, not `project-docs/decisions/`; matching `decision_entries` row is inserted.

## Out of scope

- Retroactively indexing historical devlog/decision entries that predate this change.
- Any change to how `roadmap.md` or `memory.md` are generated (not touched by #936 or LIVE-11; out of scope unless a future issue surfaces the same defect class there).
- A `synlynk todo reconcile`-style manual command — the automatic warn-and-overwrite behavior is the whole mechanism; nothing further is planned unless real-world use shows it's insufficient.
