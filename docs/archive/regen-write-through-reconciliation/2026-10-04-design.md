# Design: regen write-through reconciliation (fixes #1995, #1999, #1917, #1915)

**Status:** draft, pending Nikhil sign-off. Per Brainstorm-First Policy, no implementation may be
dispatched until this is committed and approved.

**Investigation source:** issue #2023 (root-cause-only, Wave 2, job-7f4334af), full findings in
that issue's comment thread. This spec turns those findings into a scoped fix.

## Problem

Every `state.db`-backed Markdown generator (`_write_generated_project_doc()` /
`_rotate_project_doc()`, used by `costs.md`, `memory.md`, and others) treats the caller's **local**
`state.db` as the sole render input and overwrites the tracked file wholesale. Because each
dispatch job runs in its own worktree with its own local `state.db` shard
([[stray-local-state-db]], #1831), a row that exists in the tracked file (committed by another
job, another machine, or git history) but is absent from *this* job's local DB gets silently
dropped on the next regen. Confirmed for:

- **#1915** — `costs.md` loses main-only/history-only rows directly.
- **#1995** — same mechanism, triggered incidentally by dispatch's host-side cost capture even when
  the dispatched task never touched costs.
- **#1917** — same mechanism for `memory.md`.
- **#1999** — a related but distinct bug in `_rotate_project_doc()`: it recomputes
  `archived_rows = all_rows[:-keep_n]` from scratch on every regen and appends the whole slice to
  the archive file in `"a"` mode, so repeated regens duplicate already-archived rows (45x+
  duplication / 160MB archive growth observed).

## Proposed fix

### Part A — reconcile before overwrite (fixes #1995, #1917, #1915)

`_write_generated_project_doc()` gains a reconciliation step before rendering:

1. Read the current on-disk target file (if it exists and is git-tracked).
2. Parse its row-identifying key (row id / timestamp+agent for costs, entry id for memory) back
   into a row set.
3. Union that row set with the local `state.db` row set — local DB rows win on conflict (same key,
   different content), since the local write is the newer intent; rows present only on disk are
   preserved, not dropped.
4. Render the unioned set and write.

This mirrors the existing `merge=union` `.gitattributes` strategy already used for
`project-docs/todo.md`/`costs.md`/`devlogs/*.md` at the git level (CLAUDE.md, issue #379) — this
spec adds the equivalent reconciliation at the *application* level, which git-level union merge
cannot provide: the drop currently happens via a plain overwrite, not a conflicting merge, so there
is no git conflict for `merge=union` to resolve.

### Part B — idempotent archival (fixes #1999)

Replace `_rotate_project_doc()`'s from-scratch `all_rows[:-keep_n]` recomputation with a persisted
high-water-mark (last-archived row id/timestamp, stored alongside the archive file or in a small
sidecar). Each regen only appends rows strictly newer than the high-water-mark, then advances it.

## Scope / non-goals

- Does not change `cost_entries`/`memory_entries` schemas.
- Does not address the broader `state.db` consolidation (#1926, Track 3) — this fix is
  independently valuable and should land regardless of that consolidation's timeline, but the
  consolidation would reduce how often the reconciliation path is actually exercised (fewer
  divergent local shards).
- Conflict resolution policy (local-wins-on-key-collision) is a judgment call flagged here for
  explicit sign-off — an alternative (file-wins, or hard-fail on collision) is possible if preferred.

## Rollout

1. Implement Part A + B behind the existing generator functions (no new CLI surface).
2. Add regression tests: (a) regen with a local DB missing a row the file has → row survives;
   (b) regen twice in a row → archive has no duplicate rows.
3. One PR covering both parts, since they share the root cause and the same touched functions.
