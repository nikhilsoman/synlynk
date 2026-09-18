# State DB Canonical Resolver Design

## Context

Synlynk currently has a product-scoped state database, legacy hash-based
ledgers, repo-local copies, test databases, and DR snapshots. Automatic
interchangeability between those artifacts can create split-brain control
plane state. The approved decision in
`project-docs/decisions/2026-09-18-state-db-simplification-and-idempotent-h.md`
requires the first implementation slice to make canonical selection explicit
and fail closed.

## Scope

This slice will:

- add one fixed, non-worktree-relative product registry;
- resolve the canonical database through that registry;
- add self-identifying database metadata (`product_id`, `mode`, and schema);
- expose explicit database modes: `canonical`, `ephemeral-test`, `restore`, and
  `backup`;
- reject registry corruption, product mismatch, and non-canonical modes for
  normal writable opens;
- preserve legacy files without migrating, deleting, or auto-promoting them;
- retain the explicit `SYNLYNK_STATE_DB_PATH` override for isolated tests and
  deliberate operator recovery.

## Invariants

1. A normal writable open resolves exactly one registered canonical path.
2. Missing or malformed registry data fails closed; no fallback is selected.
3. A database copied from another product or mode cannot become canonical by
   being placed at the canonical path.
4. Registry writes are atomic and idempotent; repeating registration produces
   no semantic change.
5. Existing databases are annotated only after integrity and identity checks;
   no destructive migration occurs in this slice.
6. Test and DR paths require explicit mode or path selection and are never
   candidates for normal canonical resolution.

## Rollout gate

The change is accepted only after focused resolver, metadata, corruption,
mode-mismatch, and idempotent-registration tests pass. Legacy inventory,
quarantine, promotion, and deletion require a later reviewed slice.
