# Sentinel lifecycle hygiene implementation plan (#1488)

## Goal

Make Sentinel persistence, active-alert views, expiry, and deduplication use one
consistent policy while preserving the existing markdown history and legacy
compatibility.

## Sequence

1. Add shared parsing, identity, active/expiry, and filtered iteration helpers.
2. Make alert writes idempotent within a configurable window and atomic where
   supported, without deleting historical records.
3. Route all active consumers through the shared policy and normalize WARN/
   WARNING comparisons.
4. Ensure every producer passes the workspace-local sentinel path.
5. Add focused regression coverage for compatibility, deduplication, expiry,
   consumer agreement, path isolation, selftest isolation, and write failures.
6. Run focused Sentinel/selftest/platform tests, then the full suite and live
   smoke validation in a disposable clean worktree.

## Rollback

The change is code-only and leaves existing markdown history intact. A code
rollback restores prior readers; no data migration or automatic pruning is
performed.

## Acceptance

- Fresh critical alerts block and stale timestamped critical alerts do not.
- Untimestamped legacy critical alerts remain fail-safe and blocking.
- Repeated identical events do not grow the alert log inside the dedup window.
- Distinct incidents remain observable and all active consumers agree.
- Daemon and scratch selftest writes use the intended workspace-local path.
