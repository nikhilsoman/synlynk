# Dispatch lineage concurrency hardening

**Status:** Approved for implementation by Home Harness

## Decision

Lineage writes must serialize schema discovery/migration and the paired
supersession updates across threads and processes. The lineage helper must not
change the database journal mode on every call; the product database owns its
journal configuration.

## Safety

- Use a lock file adjacent to the selected state database plus an in-process
  reentrant lock.
- Keep the existing 30-second SQLite busy timeout.
- Preserve the boolean failure contract, but close connections on every path.
- Do not alter existing terminal-job or reservation semantics.

## Success condition

Concurrent supersession writes complete without `database is locked`, and each
old job has its `superseded_by` pointer while each new job has the correct
`lineage_root`.
