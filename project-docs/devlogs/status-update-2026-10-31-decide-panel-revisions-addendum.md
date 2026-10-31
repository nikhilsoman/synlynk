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

## Blocked — found a data-integrity gap, not safe to push through blind

The remaining panel revisions were meant to land as `roadmap.md` phase updates (new publish-pipeline
fix task ahead of v0.27.0, #2087/#2088 disposition note, v0.26.7/Companion-v2/Muse-in-v0.27.3
deferral, v0.26.9/v0.26.10 marked non-gating, the statusline/Companion-v2 scope resolution for
v0.26.8, a pre-v0.27.4 `synlynk selftest --live` task). Per CLAUDE.md, `roadmap.md` is generated
from `state.db` and must not be hand-edited — the correct path is `synlynk roadmap add`/`update`.

**Found before attempting any write:** the canonical workspace db
(`~/.synlynk/workspaces/synlynk/state.db`, confirmed via `synlynk.get_state_db_path()` from this
worktree) has **no `roadmap_phases` rows for v0.26.7, v0.26.8, v0.26.9, v0.26.10, or any v0.27.x**
— the exact phases that are already committed, in full detail, in this worktree's `project-docs/
roadmap.md`. The db's `roadmap_phases` table tops out at `v0.26.0`/`v0.27.0`(generic, no sub-phase
detail)/`v0.28.0`, with a separate `v0.26.7` entry cluster whose actual titles (Gantt row
virtualization, live summary cards, agentic cell semantics, Sentinel HUD grouping — all tagged
`#497x`/`#267x`) don't match the "Jantt Timeline & Interactive GOVERNS Stage Mapping" content
`roadmap.md` shows for v0.26.7 today. Since `_generate_roadmap_md()` (confirmed in `synlynk/db.py`)
is the sole writer of `roadmap.md`, this means the committed file's v0.26.7–v0.27.5 content was
**not generated from this db** — it diverged from a different workspace/db snapshot at some point
before being committed, or this workspace's db has since been reset/partially migrated.

**Why I stopped rather than proceeding:** issuing `synlynk roadmap add --version v0.27.0 ...` etc.
against this db would not correct or match the existing committed text — it would create new,
disconnected phase rows that the next `_generate_roadmap_md()` regeneration could then silently
overwrite or duplicate against the current file content. That's a worse outcome than leaving the
file as-is for one more session. This looks like a fresh instance of the already-tracked
`stray-local-state-db` pattern (11,000+ scattered per-job shards, [[stray-local-state-db]] memory,
gh:#1831) rather than a one-off mistake — worth its own investigation, not a blind fix attempted
mid-task.

## Recommended next step (not yet actioned, needs a decision)

Before any further roadmap CLI writes in this repo:
1. Confirm which db actually backed the most recent `roadmap.md` commit (`d01afabb`, 2026-10-24,
   "attach platform-vision spec to v0.28.0 as phase") — check that commit's authoring
   worktree/session if recoverable, or diff `roadmap_arcs`/`roadmap_phases` across the handful of
   candidate workspace dbs under `~/.synlynk/workspaces/*/state.db`.
2. Once the right db is confirmed (or this workspace's db is reconciled to match the committed
   file), re-run the panel's roadmap revisions as real `synlynk roadmap add/update` calls:
   - Insert a publish-pipeline fix-and-verify phase ahead of v0.27.0 (PyPI + VS Code/OpenVSX dry-run
     tag, both green).
   - Mark v0.26.7 (Jantt), Companion v2, and Muse-in-v0.27.3 `[deferred]` past the Developer
     Preview; narrow v0.27.3's gate text to the four GA harnesses.
   - Tag v0.26.9/v0.26.10 as non-gating parallel tracks.
   - Resolve v0.26.8's `synlynk statusline` gap (fifth plan vs. shipped-elsewhere) and Companion v2
     scope ambiguity directly in its phase notes.
   - Add a `synlynk selftest --live` task ahead of v0.27.4.
3. Until then, treat this addendum (plus the panel's own decision record) as the documented
   intent — don't re-derive it from `roadmap.md`, which has not yet been updated to reflect it.

---

*Filed as a direct follow-up to "Yes, do all three" — item 3 partially complete (one story
unblocked, revisions fully specified and committed to this addendum) with the remainder blocked on
a newly-found db/roadmap.md divergence rather than silently pushed through.*
