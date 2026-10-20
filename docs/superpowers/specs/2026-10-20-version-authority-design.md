# Version Authority and Release Metadata Integrity Design

Date: 2026-10-20  
Status: Proposed  
Issue: #1914  
Roadmap: `docs/superpowers/specs/2026-10-20-roadmap-reconciliation-design.md` Section 4, v0.25.4

## Purpose

Eliminate version drift before the roadmap reconciliation creates or updates
any named release state. This design establishes one editable authority for the
Synlynk version and makes all public version surfaces verifiable projections.

## Authority Model

- The repository-root `VERSION` file is the sole editable source for the
  current development or release version.
- Package metadata, the runtime `synlynk --version` result, README badge and
  hero, CHANGELOG release header, release tags, and release documentation are
  derived views. They must not independently establish a version.
- `synlynk --version` reads the repository `VERSION` when running from a
  checkout. An installed distribution may use package metadata only as a
  fallback, and must identify that fallback to the operator.
- `synlynk release` must refuse to create, verify, or announce a release when
  `VERSION` is missing or any required derived surface is inconsistent.

## Required Behavior

### Validation

`synlynk release --check-docs` validates, without mutating state:

1. `VERSION`, package metadata, README badge/hero, and the current CHANGELOG
   header agree where each surface is applicable.
2. A proposed release version has one non-empty CHANGELOG entry.
3. A release tag matches the corresponding CHANGELOG entry on its target
   commit.
4. A release workflow cannot pass while any of those checks fails.

`synlynk doctor --version` reports each observed source and its authority. A
missing `VERSION` is an error for release operations; ordinary version display
may fall back to installed package metadata with a warning.

### Historical Releases and Gaps

- Published releases remain immutable.
- Missing public version numbers, including v0.23.0 and v0.24.0, are retained
  as documented historical gaps; they are never retroactively fabricated.
- The CHANGELOG records the gap rationale and links this design plus the
  roadmap reconciliation design. A read-only command or equivalent report
  exposes the same rationale.

### Release Workflow

- The release-docs CI job runs for release candidates, release branches, and
  tag-triggered release workflows.
- It invokes the same validation path used by `synlynk release --check-docs`;
  CI must not duplicate the comparison logic.
- A failure identifies the disagreeing surface and the required repair. It
  does not silently select a different authority.

## Migration

1. Inventory current values and document historical gaps before edits.
2. Make `VERSION` and package metadata agree with the current development
   version; regenerate or update derived documentation only through the
   defined validation path.
3. Add deterministic tests for matching and mismatched metadata, missing
   `VERSION`, absent CHANGELOG entries, and a tag/CHANGELOG mismatch.
4. Enable the CI gate before any `v0.25.2`--`v0.29.0` roadmap arc is created
   or edited in canonical state.

## Non-Goals

- This does not tag, publish, or announce a release.
- This does not rewrite published changelog history.
- This does not choose a Developer Preview date.
- This does not alter canonical roadmap state; that remains blocked until
  this design is implemented and verified.

## Acceptance Criteria

1. `VERSION` is the only editable authority and all required derived surfaces
   agree with it on `main`.
2. `synlynk release --check-docs` fails non-zero for a missing authority,
   mismatched surface, or absent/non-empty proposed CHANGELOG entry.
3. `synlynk doctor --version` provides a clear, read-only mismatch report and
   identifies package-metadata fallback.
4. CI blocks release-related changes on the same validation logic.
5. v0.23.0 and v0.24.0 remain documented gaps with an explicit rationale.
6. The full test matrix passes before any named canonical roadmap release is
   mutated.

## Approval Gate

Implementation begins only after Nikhil Soman approves this proposed design.
