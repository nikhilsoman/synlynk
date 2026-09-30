---
title: "Fixing #1865 — The Wizard's Dry-Run Flag Never Reached the Wizard"
date: 2026-09-30
series: "Building the OS for Multi-Agent Development"
post: 235
pr: "1876"
issue: "1865"
status: published
author: "synlynk team"
version: "0.23.0-dev"
tags: [posts, bugfix, wizard]
type: story
---

## The Broader Goal at the End of the Previous PR

The previous post (234, PR #1875) closed out #1862 — the wizard's `_wiz_clear()` no longer
spawns a pipe-inheriting shell child. That left #1865 as the second confirmed, independent
defect from the same review-remediation wave: a real bug, unrelated to #1862 beyond sharing a
test file.

## Strategic Shifts in This PR

None in scope, but this PR is the one that surfaced a genuine *process* problem worth naming:
#1875 and this PR both independently touched `tests/test_wizard.py`'s subprocess env-setup
block (both needed to propagate `PYTHONPATH`), and #1875 merged first. That turned an ordinary
squash-merge into a real content conflict on this branch — covered in the Process section
below, since it's as much a part of what shipped as the code fix itself.

## What #1865 Was

`synlynk init --wizard` accepts a `--dry-run` flag at the CLI layer, but `synlynk/cli.py`'s
dispatch to the wizard entry point silently dropped it:

```python
elif getattr(args, "wizard", False):
    wizard_init()
```

`wizard_init()` was called with no arguments, so `--dry-run` never reached it — a wizard run
invoked with `--dry-run` behaved identically to one without it, including writing real state
to whatever `state.db` path was in scope for that process. In a captured subprocess test that
shares environment with other concurrent test runs, that's a real state-isolation gap, not
just a missing flag.

## What This PR Shipped

One line:

```python
elif getattr(args, "wizard", False):
    wizard_init(dry_run=getattr(args, "dry_run", False))
```

`--dry-run` now actually reaches `wizard_init()`. The regression test was extended well beyond
"does it return 0" to prove the isolation claim directly: it runs the wizard subprocess with
`SYNLYNK_STATE_DB_PATH` pointed at a private `isolated-state.db` inside the test's `tmp_path`,
then asserts that (a) some `isolated-state.db*` artifact exists (the wizard did write state
somewhere), (b) every such artifact is confined to the expected `state_db` path plus its WAL/
SHM sidecar files — nothing wrote outside the isolated path — and (c) no `.synlynk/state.db`
appeared under `tmp_path`, which would mean the dry-run leaked into the default on-disk
location instead of staying isolated.

## Process: A Real Merge Conflict, Not a False Negative

Two review cycles followed the same pattern as #1875's: first review `CHANGES_REQUESTED` (same
`PYTHONPATH`-not-CI-runnable finding, fixed the same way), second review `APPROVED`. But by the
time the second approval landed, PR #1875 had already merged — and both PRs had independently
added near-identical `PYTHONPATH`-propagation blocks to the same lines of
`test_synlynk_init_wizard_dry_run_subprocess`. `gh pr merge` failed with a genuine
`mergeable: CONFLICTING` / `mergeStateStatus: DIRTY`, not one of this project's known
job-status false negatives.

Resolution: fetch `origin/main`, merge into the PR branch, and manually keep the superset of
both sides — #1875's `PYTHONPATH` fix *and* this PR's `SYNLYNK_STATE_DB_PATH` isolation
assertions, rather than picking one side and losing the other's test coverage. Verified with a
local run (22/22 passing in `test_wizard.py`) before pushing the merge commit. That push
invalidated the prior `APPROVED` review (GitHub ties approval to a commit SHA, and a new commit
— even a pure conflict-resolution one — makes the existing approval stale), so a fresh
non-authoring review ran specifically against the new head and came back `APPROVED` on the
exact commit before merging.

## What's Next

Both #1862 and #1865 are now closed with merged, reviewed fixes. #1864 — the third issue from
the same wave, a suspected pytest full-suite hang — got its own deeper investigation pass in
parallel with this PR's conflict resolution: a genuine attempt to reproduce and bisect it,
rather than another static source audit. It did not reproduce. Worth watching for recurrence,
not closing outright — write-up is its own comment on the issue rather than a blog post, since
there's no shipped fix to describe yet.

Refs #1865.
