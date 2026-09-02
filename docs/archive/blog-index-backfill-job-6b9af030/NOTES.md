# Blog index backfill (found in worktrees/job-6b9af030)

Uncommitted diff discovered in `worktrees/job-6b9af030` while cleaning up post-merge
of PR #1352. Unrelated to that PR — appears to be leftover from an earlier,
unfinished job in the same worktree that was auditing `docs/blog/README.md` for
missing index rows.

**Finding:** ~24 files exist under `docs/blog/*.md` with no corresponding index row
in `docs/blog/README.md` (e.g. `52-pr156-157-fleet-scheduler-v1-and-v2-deferral.md`,
`91-prTBD-fleet-parity-security-cluster.md`, `144-pr1311-...`, etc.).

**Caveat:** the proposed numbers collide with numbers already in use in
`docs/blog/README.md` for unrelated posts (e.g. `[28]` is already
`28-pr70-v0.9.8-health-lifecycle.md` in main; the patch tries to add a second `[28]`
row for `28-pr72-fix-grok-dispatch-prompt-flag.md`). The numbering scheme is not
globally unique across the file, so this patch cannot be applied as-is — a real fix
needs to either renumber the new rows or confirm duplicate numbers are acceptable.

Preserved here (not applied, not discarded) per the archive-before-branch-removal
policy. Worth a real ticket if the blog index is meant to be exhaustive.
