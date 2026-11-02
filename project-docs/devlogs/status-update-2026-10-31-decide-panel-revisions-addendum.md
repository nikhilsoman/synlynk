# Addendum: Translating the Decide Panel's Revisions into Plan State — 2026-10-31

**Prepared by:** Claude (PM/review role), follow-up to `status-update-2026-10-31-dev-preview-readiness.md`
and the panel decision record `project-docs/decisions/2026-10-31-release-readiness-plan-review-review-and.md`
(verdict: **APPROVE-WITH-REVISIONS**).

This records exactly what changed (or was attempted) as a direct result of the panel's revisions,
and what's still pending with an explicit blocker.

---

## Done this session

1. **`story-issue-1973`** (baseline metrics capture before any onboarding/dispatch UX change) marked
   **ready** via `synlynk story ready story-issue-1973` — unblocks it to run in parallel with v0.26.8
   rather than staying sequenced behind it, per panel revision #7. This directly feeds v0.27.1's
   "under 15 minutes" gate, which otherwise has no baseline to measure against.

2. **Stale `#2139`-closed claim corrected** in project memory (`project-synlynk.md`, see memory
   `gh2139-still-open-correction`). Issue is confirmed still OPEN; tracking moved to `#2137`/
   `story-25872226`/`goal-bde24050`.

## Blocked, then resolved — not a data-integrity bug, a landed architecture change this branch predated

The remaining panel revisions were meant to land as `roadmap.md` phase updates (new publish-pipeline
fix task ahead of v0.27.0, #2087/#2088 disposition note, v0.26.7/Companion-v2/Muse-in-v0.27.3
deferral, v0.26.9/v0.26.10 marked non-gating, the statusline/Companion-v2 scope resolution for
v0.26.8, a pre-v0.27.4 `synlynk selftest --live` task). This session initially found the canonical
workspace db (`~/.synlynk/workspaces/synlynk/state.db`) had no `roadmap_phases` rows for
v0.26.7–v0.27.5, even though this worktree's committed `project-docs/roadmap.md` has full detailed
content for all of them, and treated that as a possible data-integrity gap worth stopping for.

**Root-caused 2026-10-31 (same session, user said "chase that down now"):** it is not a bug. gh:#2653
landed on `main` today (spec/plan `313a74bc`, implementation `934e4922`/PR #2655, cutover commit
`00520644`/PR #4964, merged 01:18) and **retires `roadmap.md`/`todo.md`/`costs.md` as git-tracked
files entirely** — `state.db` is now the sole authority, with GitHub Milestones/Issues (via
`synlynk gh sync-roadmap`) as the shareable projection; these files are local, generated-on-demand
output only, added to `.gitignore`. This worktree's branch
(`docs/claude/synlynk-com-platform-vision`) was cut before that merged and is now 11 commits behind
`origin/main` on this exact file — the v0.26.7–v0.27.5 content in this worktree's `roadmap.md` is
just a stale pre-cutover snapshot, not evidence of a corrupted or wrong db. The canonical db I
queried was the right one all along; it was never supposed to contain those phases once GitHub
Milestones/Issues became the real target.

## Corrected next step

1. Apply the panel's remaining roadmap revisions as GitHub Milestone/Issue updates via
   `synlynk gh sync-roadmap`-compatible writes, not `synlynk roadmap add/update` CLI calls against
   a local `roadmap.md` — that file is no longer the live artifact.
2. Before any further `project-docs/` work in this worktree, merge/rebase `origin/main` to pick up
   gh:#2653 so this branch isn't operating against files that no longer exist upstream.
3. The stale `#2139`-closed text in this worktree's `roadmap.md` (flagged in `gh2139-still-open-
   correction` memory) is moot now that the file is untracked — the memory correction already made
   is the source of truth; no CLI fix against `roadmap.md` is needed or possible anymore.

---

*Filed as a direct follow-up to "Yes, do all three" — item 3's roadmap-phase revisions remain
not-yet-applied, now correctly scoped to GitHub Milestones/Issues post-gh:#2653 rather than blocked
on a (non-existent) db divergence.*
