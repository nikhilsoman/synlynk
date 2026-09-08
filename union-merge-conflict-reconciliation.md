# Union-Merge Conflict Reconciliation — Advanced / General

**Scenario:** A general union-merge-style append-only markdown ledger contains both sides of a conflict, with narrative entries, related PR rows, and cost rows interleaved. The line-level union preserved the content but left the markdown structure ambiguous, so this reconciliation restores the semantic sections without dropping either append.

## Reconciled ledger

The conflict markers are removed from the committed document. Unique content is retained in arrival order for narrative entries, while the interleaved PR and cost records are normalized into one table per record type.

### Shared preamble

- Fleet operating normally.

## 2026-09-08 — Job A (velocity pilot)

- Opened bounded autonomy pilot behind quota gates.
- Metrics: jobs/week, median time-to-merge.

## 2026-09-08 — Job B (trust floor)

- Hardened reconciler exception boundaries.
- Metrics: false zombie rate, log retention.

### Related PRs (merged table)

| PR | Topic |
| --- | --- |
| PR #1488 | sentinel lifecycle policy |
| PR #1490 | selftest probe cold source |
| PR #1491 | sentinel lifecycle |
| PR #1498 | zombie termination reliability |

### Cost rows (merged ledger)

| Date | Job | Harness | Kind | Est. USD |
| --- | --- | --- | --- | --- |
| 2026-09-08 | job-aaa | grok | calibration | ~0.02 |
| 2026-09-08 | job-bbb | agy | calibration | ~0.03 |

### Trailer

- Pull before editing remains preferred.

## Reconciliation rules

1. Preserve both unique narrative sections in arrival order; neither append is discarded.
2. Collapse duplicate table headers and separators into one canonical header.
3. Sort PR body rows by PR number so the merged table is scannable.
4. Merge cost rows under one ledger section with stable columns.
5. Preserve shared preamble and trailer content unchanged.

The result keeps all unique content from both sides while restoring valid markdown structure. No content is invented, and the conflict syntax is not part of the committed ledger.

## Completed feature status

- Root cause closed: premature zombie reaping no longer marks healthy exited workers as `killed_zombie` or deletes their evidence before exit and work ground truth is read.
- Logs survive reaps: worker logs live under durable daemon state, so reaping preserves forensic artifacts instead of destroying in-worktree logs.
- Reconciler hardened: per-job exception isolation, timezone-aware GitHub timestamp comparisons, and absolute GitHub App PEM resolution keep fleet truth intact under concurrent dispatch.
