---
title: "PR #542 — State Engine PR1: DB-Canonical Roadmap, Memory, and Costs"
date: 2026-07-26
series: "Building the OS for Multi-Agent Development"
post: 80
pr: "#542"
merged: 2026-07-26
---

## The Broader Goal at the End of the Previous PR

`todo.md` had already been DB-canonical for a while — stories live in a `stories` table, `todo.md` is regenerated from it, and that pattern was stable. `roadmap.md`, `memory.md`, and `costs.md` were still flat markdown, hand-edited or append-only, and drifting: repeated `costs.md` corruption incidents (#481, #482, #485) traced back to exactly the class of problem `todo.md` had already solved — multiple writers touching a plain-text file with no single source of truth. The `2026-07-20-state-engine-tiered-design.md` spec had already been approved, laying out a three-PR sequence (PR1/PR2/PR3) to extend the `todo.md` pattern to the rest of `project-docs/`.

## Strategic Shifts in This PR

None — this PR executes Tier 1 PR1 as specced, no scope changes. The one deliberate addition beyond the spec's letter: §8.1 called for running `synlynk migrate` against synlynk's own repo as the final landing step, and Task 7 of the implementation plan treated that as a *real* dry run, not a formality — it surfaced two live bugs in the process (a stash-exclude-pathspec/`.gitignore` interaction bug, and a `cmd_roadmap_add` `NameError`), both fixed before merge, plus one deliberately deferred `.gitignore` substring false-positive (tracked separately as #546).

## What This PR Shipped

- `_generate_roadmap_md()` + `cmd_roadmap_add()`-style CLI verbs writing through to `roadmap_arcs`/`roadmap_phases`, mirroring `todo.md`'s existing pattern.
- `_generate_costs_md()`, with `cmd_cost_log()` now writing through on every log call instead of relying on append-only markdown.
- `check_budgets()` switched to query `cost_entries` directly; `parse_costs_md()` regex parsing demoted to a fallback path only.
- Rotation/archive: `project-docs/archive/<file>-<period>.md` + `INDEX.md`, replacing unbounded file growth.
- A mutation guard: a header banner on generated files plus a hand-edit detection check that warns loudly and continues (rather than blocking) when a genuine uncommitted hand-edit is found — deliberately warn-and-continue per §8.2, not a hard gate.
- A specific test proving the guard's git-pull-then-resync case does *not* false-positive: a fresh pull that changes the file without a local DB mutation must not trigger a warning.
- The migrate-on-self step itself: `synlynk migrate` run against this repo, `.synlynk_migrated` sentinel committed, `project-docs/roadmap.md`/`memory.md`/`costs.md`/`todo.md` removed from git tracking in favor of DB-backed regeneration.

Two real bugs surfaced by actually running the migrate (not just unit-testing the migrate code) rather than three fabricated ones — the whole point of Task 7 being a live dry run instead of a mocked one.

## Brainstorm Visuals Used

None — this PR executed an already-approved spec; no new design decisions needed a visual companion.

## What This Achieved on the Path to Autonomy

Every file an agent might read for context (`roadmap.md`, `memory.md`, `costs.md`) is now regenerated from a single database, the same discipline `todo.md` already had. That closes the specific failure mode that caused #481/#482/#485: two agents (or an agent and a human) editing the same markdown file concurrently, each unaware of the other's write. A DB-backed write-through with a mutation guard means concurrent agent writes converge instead of clobbering each other silently.

## Strategic Note: The Goal at the End of This PR

PR1 is done; PR2 (DB-canonicalize `vizor-workspace-map.json` + fix `viz.py`'s stale reads of `roadmap_arcs`/`roadmap_phases`, owned by Grok) and PR3 (scoped `dispatch_agent()` context + symbol/story graph tables, owned by Codex+Grok) are next in the Tier 1 sequence. But this PR's own merge produced an unplanned complication: the non-authoring reviewer's conflict resolution (triggered by other PRs landing during review) deleted more of `project-docs/` than PR1 actually intended — see PR #549 and its RCA, the direct follow-up to this post.
