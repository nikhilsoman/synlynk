# Generated State Export Paths Implementation Plan

Approved design: [Generated State Export Paths](../specs/2026-10-16-generated-state-export-paths-design.md), decision `dec-02b76895`.

1. Resolve a product-scoped export directory beside the canonical state DB;
   route the three database generators, readers, and status refresh through it.
2. Exclude checkout and canonical export paths from job autocommits, and make
   `pr check` fail on PR diffs touching the three legacy checkout paths.
3. Remove the tracked markdown exports and only their union attributes.
4. Update generation, worktree isolation, autocommit, and PR gate tests.
5. Run `pytest -q` on changed test files and open one PR without merging.
