# LIVE-1: Canonical state DB ambiguity and fallback risk

Date: 2026-09-18
Severity: Sev1
Issue: #1655

## Impact

The product's canonical `state.db` became unreadable during recovery and
inspection. In the affected environment, the canonical workspace path was not
accessible, while a worktree-local `.synlynk/state.db` was malformed. The
previous runtime behavior could silently select that local database after a
canonical open failure. This creates a split-brain control plane: commands may
appear to work while reading or mutating a different ledger from the product's
source of truth.

This is an existential correctness and recovery risk, even when no records are
lost. A successful command against the wrong ledger is more dangerous than an
explicit outage because it can produce false status, incorrect scheduling,
duplicate work, or divergent state.

## Findings

1. The canonical product DB is the original artifact preserved with SHA-256
   `6953985554ddda42ee977d0c5cd14495f95cd519e927bbfc784fe67b25cb1a8b`.
2. Recovery promoted a validated canonical ledger with SHA-256
   `ca9fb2bce8788e95830f1aafeb5c283908ef05dab6391760c3ec9ef0b0a4cada`.
3. The current restricted environment cannot access the canonical path and
   therefore cannot independently re-open that promoted artifact.
4. Read-only access already failed closed, but normal access caught canonical
   `OSError`/SQLite open errors and selected a local fallback automatically.
5. Inspection had previously created SQLite WAL/SHM sidecars; the immutable
   inspection hardening in PR #1658 removed that mutation path. Sidecars were
   not the justification for selecting another database.

## Root cause

The state resolver treated an environment/path access failure as a reason to
choose a different database. That behavior was originally intended to make
isolated dispatch sandboxes usable, but it did not encode the critical
distinction between an explicitly selected test ledger and an unavailable
canonical product ledger. The fallback path was therefore operationally
convenient but semantically unsafe.

## Corrective action

The resolver now fails closed when the canonical DB cannot be opened. It never
silently chooses `./.synlynk/state.db` or a temporary ledger. An operator must
either set `SYNLYNK_STATE_DB_PATH` to an explicitly verified database or set
`SYNLYNK_ALLOW_STATE_DB_FALLBACK=1` for an intentional isolated sandbox. Even
with that opt-in, a malformed fallback raises a database error instead of
being recreated or silently replaced.

Regression tests cover inaccessible canonical storage, explicit sandbox
fallback, and malformed fallback handling.

## Recovery status and residual risk

The recovery ledger was validated and promoted before this fix. Existing
context remains recoverable from the preserved original, recovery ledger,
Git history, issue/PR records, and project documents; the deferred second
machine restore remains the outstanding DR validation step. This change closes
the runtime split-brain path but does not substitute for that independent
restore test or for encrypted off-machine backup custody.
