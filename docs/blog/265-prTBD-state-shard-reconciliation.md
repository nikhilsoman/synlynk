---
title: "Reconciling Orphaned State Shards Before Any Deletion"
date: 2026-10-09
series: "Building the OS for Multi-Agent Development"
post: 265
pr: "2155"
status: shipped
author: "synlynk team"
version: "0.19.0"
tags: [posts]
type: pr
---
# gh:#1831 — Reconciling Orphaned State Shards Before Any Deletion

## The goal as of the last PR

PR #2085 (gh:#1926, blog post #254) shipped a migrations framework and buried 11,384 dead
`state.db` shards under `~/.synlynk/projects/<hash>/` — but it explicitly stopped short of
touching the data inside them. gh:#1831 warned, in its own body, "do not bulk-delete before
this": some of those shards hold orphaned story/capability/cost rows that never made it into the
canonical workspace ledger at `~/.synlynk/workspaces/<name>/state.db`. Burying the shard
directories made them stop growing; it didn't recover what was already stranded inside the
13267207-fingerprint shard (975 rows) or its siblings.

The Empirical Capability Assessment Policy (2026-10-04) also names this reconciliation as a
blocking dependency: aggregate `capability_ratings`/`cost_entries` measurement across harnesses
can't be trusted while relevant rows are scattered across thousands of per-job shards instead of
living in one canonical database.

## No strategic shift this PR

This PR delivers exactly what the design/plan scoped: a safe, dry-run-first reconciliation path
for `synlynk state inventory`, plus one `_project_root()` hardening fix that closes the same
CWD-fallback bug class as #1228 (a dispatch worktree silently minting its own shard instead of
resolving to its parent repo's canonical project hash). No scope change from the approved spec
(`docs/superpowers/specs/2026-10-09-state-shard-reconciliation-design.md`) or plan
(`docs/superpowers/plans/2026-10-09-state-shard-reconciliation-plan.md`).

## What this PR shipped

Seven tasks, executed via `superpowers:subagent-driven-development` (fresh implementer subagent
per task, spec-compliance review, then code-quality review, before moving on):

1. **`_project_root()` hardening** — raises instead of silently falling back to `os.getcwd()`
   when no project root can be resolved, with a `SYNLYNK_ALLOW_CWD_FALLBACK` escape hatch scoped
   to the two legacy test files that genuinely need it (not left as a global default).
2. **Inventory enrichment** — `synlynk state inventory` now reports `row_count`, `mtime_iso`, and
   `staleness_days` per shard, not just path and size.
3. **Project matching** — `_match_project()` resolves a legacy shard to its canonical workspace
   via exact fingerprint match first, falling back to a heuristic (path/name similarity) when no
   exact fingerprint exists.
4. **Reconcile planning** — `_reconcile_plan()` computes a union-merge plan between a legacy shard
   and the canonical DB: no-overlap rows union cleanly, full-overlap is a no-op, and genuine
   row-level conflicts are flagged rather than silently resolved.
5. **Apply with mandatory backup** — `apply_reconcile()` performs the merge atomically, always
   backing up the canonical DB first and rolling back on any failure mid-merge. `created_at` is
   preserved from the original row during merge, not overwritten.
6. **CLI wiring** — `--reconcile` / `--apply` / `--ignore-conflicts` / `--cutoff-days` flags on
   `synlynk state inventory`, defaulting to dry-run so a plan is always visible before anything
   is written.
7. **WAL-checkpoint backup fix** — the final whole-feature code-quality review caught that
   `apply_reconcile()`'s backup used `shutil.copy2()` directly on the canonical DB's main file,
   which can omit committed-but-not-yet-checkpointed rows living only in SQLite's `-wal` sidecar.
   The fix runs `PRAGMA wal_checkpoint(TRUNCATE)` on a throwaway connection immediately before the
   copy. The regression test needed a second idle connection held open across the call —
   SQLite auto-checkpoints on last-connection-close, so without it the writer's own close would
   mask the bug the test was meant to catch.

All 18 tests in `tests/test_state_inventory.py` pass (17 pre-existing + 1 new WAL-checkpoint
regression test), and the full suite ran clean earlier in this session at 4,052 passed / 0 failed
/ 3 skipped / 5 xfailed.

No brainstorm visuals were produced for this PR — the design was scoped directly from gh:#1831's
own problem statement and the existing `2026-10-06-state-db-consolidation-design.md`'s adjacent
(but distinct) single-workspace-DB architecture question.

## Progress toward the long-arc goal

This closes the "safe reconciliation path" piece of gh:#1831 that #1926/PR #2085 deliberately left
open, and removes one item (orphaned-row recovery) blocking the Empirical Capability Assessment
Policy's aggregate-measurement dependency. It does not yet perform any bulk deletion of the
now-buried shard directories — that remains a separate, later step once reconciliation has
actually been run against the real 11,384-shard population.

## The new goalpost

With `_project_root()` hardened and a dry-run-first `--reconcile`/`--apply` CLI in place, the next
step is running reconciliation against the real shard population (starting with the known
13267207 shard) and only then revisiting whether/how to delete the now-reconciled legacy
directories — plus continuing to track gh:#1993 (`synlynk capability report`) as the consumer of
the aggregate data this reconciliation unblocks.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_0167ERumamwnBGV98mN3gXMQ
