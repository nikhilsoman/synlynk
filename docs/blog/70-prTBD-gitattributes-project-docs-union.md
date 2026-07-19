---
title: "PR #383 — .gitattributes union merge for project-docs churn"
date: 2026-07-19
series: "Building the OS for Multi-Agent Development"
post: 70
pr: "#383"
merged: —
---

## The Broader Goal at the End of the Previous PR

After v0.12.0 (Measurement & Reliability) and the live-command-selftest arc (PR #328), concurrent multi-agent / multi-worktree work is the default operating mode. Shared markdown under `project-docs/` remains a write-through, git-tracked human surface even as `state.db` is the machine-readable substrate. That surface is also a merge-conflict magnet: todo checkboxes, cost ledger rows, and per-user devlogs get appended from many sessions at once.

## Strategic Shifts in This PR

None at the product architecture level. This is a pure hygiene fix for team-mode git friction — not a replacement for `state.db`, and not a change to how agents write docs. The goalpost stays the same: keep agents and humans on one shared project state without burning time on conflict markers in append-only files.

## What This PR Shipped

1. **Root `.gitattributes`** declaring Git's built-in union merge for:
   - `project-docs/todo.md`
   - `project-docs/costs.md`
   - `project-docs/devlogs/*.md`

2. **Verified driver setup:** a scratch-repo merge of concurrent appends confirmed that `merge=union` works with **zero** local git config. It is a built-in attribute value (see `gitattributes(5)`), not a custom driver that would need `git config merge.union.driver`. Control case without `.gitattributes` produced standard `<<<<<<<` conflict markers; with the attribute, both sides' lines were kept and the merge completed cleanly.

3. **CLAUDE.md Session Protocol note** so contributors and agents know pull is still preferred, union may leave nondeterministic line order, and no one-time config ceremony is required.

## Brainstorm Visuals Used

None — issue-driven plumbing.

## What This Achieved on the Path to Autonomy

Reduces a recurring class of human/agent merge pain (15 recent commits on these paths, historical conflict markers in `todo.md`) without inventing a custom merge driver or CI gate. Multi-agent team mode can keep writing append-only ledgers with fewer false-stop conflict resolutions.

## Strategic Note: The Goal at the End of This PR

Docs-drift merge noise is mitigated for the highest-churn append paths. Remaining gaps (roadmap/memory concurrent edits, intentional reorder/delete conflicts that union cannot resolve well, any future move of docs under `.synlynk/project-docs/`) stay out of scope until they show the same recurrence rate.
