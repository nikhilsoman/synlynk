# State DB Identity, Idempotency, and Recovery Hardening

**Date:** 2026-09-18  
**Issue:** #1668  
**Related incident:** #1655  
**Goal:** `goal-d3333441` — Control-plane trust and closure  
**Status:** Approved for planning; implementation requires the rollout gates in this document.

## Problem

Synlynk has accumulated several physically valid SQLite files: the current
product-scoped ledger, legacy hash-based project ledgers, repo-local fallback
copies, test/selftest ledgers, recovery artifacts, and DR snapshots. These
files have different meanings, but historical path resolution treated some of
them as interchangeable. Sev1 #1655 showed that this is a split-brain
control-plane failure: a command can succeed against the wrong ledger.

The existing fail-closed change stops the normal unavailable-canonical fallback.
This design makes the remaining identity, migration, and recovery rules
explicit and idempotent.

## Decision

There is exactly one active canonical ledger for a product. All other database
files are explicitly typed as `ephemeral-test`, `restore`, `backup`, or
`quarantine` and are never eligible for normal product resolution.

Canonical identity is an explicitly assigned, immutable `product_id`; it is
never derived from a repository path, worktree path, slug, or hash. A fixed
authoritative registry maps `product_id` to its canonical path and current
lineage generation. The registry is not discovered from CWD.

All runtime opens go through one centralized `open_state_db()` API. Direct
module-level path resolvers and unguarded `sqlite3.connect` calls are removed
or routed through this API.

## Ledger identity and canonical proof

Every managed DB contains a metadata record with:

- immutable `product_id`;
- `mode`: canonical, ephemeral-test, restore, backup, or quarantine;
- schema version;
- lineage generation;
- creation/source checksum and migration state.

Metadata alone is not proof of canonical status because copying a SQLite file
also copies its metadata. A write-capable canonical open is valid only when:

1. DB metadata matches the requested `product_id` and mode;
2. the real path matches the registry's canonical path;
3. registered filesystem identity (device/inode, where supported) matches;
4. integrity and schema checks pass; and
5. no competing registry entry maps the product to another active path.

Path or inode changes are treated as an explicit restore/migration event, never
as an automatic promotion.

## Registry

The registry lives at a fixed product-manager location outside any worktree,
with `SYNLYNK_REGISTRY_PATH` available only as an explicit test/sandbox
override. Registry updates use a cross-process advisory lock, write a
validated temporary file, fsync the file, atomically replace the registry,
and fsync its parent directory. Corrupt, missing, duplicate, or ambiguous
registry state fails closed.

The registry must retain a signed or versioned recovery representation so the
registry itself is not an unprotected single point of failure. Registry reads
may be read-only in a restricted `$HOME`; registry writes must report the
exact permission failure and must not fall back to CWD-relative state.

## Explicit modes

Normal commands resolve only `canonical`. Other modes require an explicit
operator/test selection:

- `canonical`: normal product mutations and reads;
- `ephemeral-test`: test/selftest-only, isolated by fixture or explicit path;
- `restore`: a validated candidate being promoted by the restore workflow;
- `backup`: immutable snapshot input/output, never a normal mutation target;
- `quarantine`: read-only retained evidence, never auto-selected.

`SYNLYNK_STATE_DB_PATH` remains an explicit path override, but degraded access
defaults to read-only. Mutations through a degraded path require
`SYNLYNK_ALLOW_DEGRADED_WRITES=1` and emit structured warning
`STATE_DB_DEGRADED_OVERRIDE_ACTIVE`.

## Bootstrap and migration

Slice 1 includes a non-destructive metadata bootstrapper because existing
canonical ledgers predate the metadata schema. Bootstrap may stamp only the
verified registry-selected canonical ledger after integrity and identity checks;
it may not copy, replace, or infer a canonical ledger from availability.

Migration/promotion is a recoverable state machine, not a claim of one atomic
filesystem/database transaction:

1. acquire product and registry locks;
2. inspect source, compute checksum, and validate SQLite integrity;
3. create a temporary destination in the target filesystem;
4. normalize journal mode to rollback/DELETE, checkpoint and close WAL
   connections, then write and fsync the destination;
5. validate destination checksum, schema, metadata, and product identity;
6. atomically rename the destination into the registered path and fsync the
   parent directory;
7. record the completed phase and source/destination checksums in durable
   metadata/registry state.

If interrupted, rerun is safe: a valid destination with matching identity,
schema, and checksum is treated as already promoted even if the final marker
was not written. A mismatched destination is preserved for inspection and
halts; it is never overwritten automatically. No operation overwrites the
canonical DB in place.

## Legacy inventory and quarantine

Before migration or deletion, an inventory reports path, class, product
identity if present, SHA-256, size, SQLite integrity, WAL/SHM presence,
lineage, and recommended disposition. The first implementation slice only
reports and read-only validates.

Quarantine moves stale hash-based, repo-local, and recovery ledgers out of
active discovery paths to:

`~/.synlynk/quarantine/<product_id>/<timestamp>-<sha256>/state.db`

with read-only permissions and a manifest. Deletion requires retention expiry,
successful canonical verification, a current DR snapshot, and explicit human
confirmation. DR snapshots remain immutable and independently restorable;
they never participate in canonical resolution.

## Required tests and rollout gates

Tests must cover:

- existing-ledger metadata bootstrap without data mutation;
- registry path/product/mode enforcement and duplicate-product rejection;
- copied canonical DB rejection by path/inode/registry checks;
- registry corruption, lock contention, and read-only `$HOME` behavior;
- migration interruption at every phase and repeat-run no-op behavior;
- WAL checkpoint/sidecar cleanup and parent-directory durability;
- concurrent promotion/open races and split-brain prevention;
- explicit restore and degraded read-only/write opt-in behavior;
- proof that test, backup, restore, and quarantine DBs cannot auto-select;
- codebase-wide audit for direct SQLite opens bypassing `open_state_db()`.

Rollout is gated by a human-reviewed dry-run inventory, a successful backup
restore drill on a second machine, and a documented degraded-mode runbook.
No legacy artifact is deleted as part of the first implementation PR.

## Scope boundary

The first implementation slice is registry + centralized resolver + metadata
bootstrap + identity/mode enforcement + inventory dry-run. Full migration,
quarantine movement, deletion, and second-machine restore automation follow
only after this slice passes its gates.
