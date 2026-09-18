# Implementation Plan: State DB Identity and Idempotency Hardening

**Spec:** `docs/superpowers/specs/2026-09-18-state-db-idempotency-hardening-design.md`  
**Issue:** #1668  
**Goal:** `goal-d3333441`  
**Branch family:** `feat/codex/state-db-hardening-*`

## Execution rules

- Implement only after the spec/plan PR is reviewed.
- Every feature/fix uses its own worktree and branch.
- No legacy DB deletion in the first implementation slice.
- Each step must preserve fail-closed behavior and include focused tests before
  broader tests.

## Work packages

### 1. Inventory and resolver audit

Create a read-only inventory command/report that classifies every discovered
DB without opening it for mutation. Record path, SHA-256, SQLite integrity,
sidecars, metadata/product identity, and disposition. Audit all
`sqlite3.connect` and path-resolution call sites, including lineage,
capability sweep, backup, migration, and test helpers.

**Exit:** inventory is deterministic and no normal code path has an untracked
resolver or direct mutable SQLite open.

### 2. Registry and identity metadata

Add the fixed-location registry, explicit `SYNLYNK_REGISTRY_PATH` override,
product lock, registry lock, atomic update protocol, recovery/version record,
and metadata schema. Add the non-destructive bootstrapper for an already
verified canonical DB.

**Exit:** existing canonical state opens after bootstrap; wrong product,
wrong mode, duplicate mapping, corrupt registry, and copied-file identity all
fail closed.

### 3. Centralized typed open API

Implement `open_state_db(product_id, mode, read_only, explicit_path)` and route
all production callers through it. Preserve the merged unavailable-canonical
fail-closed behavior. Make degraded overrides read-only by default and require
explicit degraded-write opt-in plus telemetry.

**Exit:** normal commands can select only the registry canonical ledger;
tests/backups/restores require explicit modes and paths.

### 4. Crash-safe idempotent promotion

Implement the promotion state machine with locks, rollback journal/WAL
normalization, temporary destination, checksum/integrity validation, fsync,
atomic rename, parent-directory fsync, and recovery from every interrupted
phase. Use database/registry evidence as the source of truth for rerun no-op
decisions; external markers are advisory only.

**Exit:** repeated migration is a verified no-op, never an overwrite; all
crash-injection tests pass.

### 5. Quarantine and DR operations

Add dry-run-only classification first. After the second-machine DR drill and
human approval, add explicit quarantine movement with manifests and read-only
permissions. Add an explicit `admin dr-restore` workflow that validates a
snapshot, archives the broken canonical ledger, assigns a new lineage, and
updates the registry transactionally.

**Exit:** legacy copies are outside active discovery only after approval;
backups remain immutable and independently restorable.

### 6. Rollout and verification

Run the focused DB suite, full test matrix, nested-worktree/fleet matrix, and
doctor/status checks. Produce the inventory report, complete the second-machine
restore drill, publish the degraded-mode runbook, and attach evidence to #1668.

**Exit:** all gates pass and the hardening goal can advance; no deletion occurs
without a separate explicit approval.

## Test matrix

- Unit: registry locking, atomic replacement, metadata bootstrap, mode/path/
  inode validation, duplicate identity, degraded mode.
- Fault injection: crash before/after temp fsync, rename, parent fsync, and
  completion recording.
- Concurrency: two openers, two promoters, registry lock contention, and
  canonical-vs-restore races.
- Integration: CLI status/jobs/dispatch/backup/restore, nested worktrees,
  read-only home, and explicit test DBs.
- Recovery: checksum mismatch, corrupt registry, corrupt canonical, WAL/SHM
  sidecars, second-machine restore.

## PR sequencing

1. Spec/plan review PR.
2. Inventory + resolver audit PR.
3. Registry + metadata + centralized open PR.
4. Promotion/idempotency PR.
5. Quarantine/DR PR after restore gate.

Each PR links #1668 and the hardening goal, runs `synlynk pr check`, and is
reviewed by QA before merge.
