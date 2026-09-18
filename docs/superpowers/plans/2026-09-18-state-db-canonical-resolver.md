# State DB Canonical Resolver Implementation Plan

## 1. Registry primitives

- Add a fixed registry under `~/.synlynk/workspaces/registry.json`.
- Store explicit product ID, canonical path, and registry format version.
- Write through a temporary file, flush and replace atomically.
- Reject duplicate product IDs, path changes, malformed JSON, and non-canonical
  registry entries.

## 2. Connection integration

- Add a typed open mode with `canonical` as the normal default.
- Resolve normal opens through the registry while preserving explicit test and
  restore paths.
- Add a `state_metadata` table and validate product ID/mode on every writable
  canonical open.
- Keep fallback disabled and fail closed on every resolution error.

## 3. Verification

- Add tests for registry creation/repeat no-op, corruption, duplicate product,
  metadata mismatch, mode mismatch, and explicit test/restore access.
- Run focused state DB tests, then the full relevant test module set.
- Record the result in the issue and PR; do not quarantine or delete legacy
  artifacts in this slice.
