# Roadmap/Cost/Decision Authority: state.db + GitHub, No Git-Tracked Markdown Mirrors

- **Status:** Draft — pending user review
- **Date:** 2026-10-29
- **Related:** gh:#2653 (parent investigation issue), PR #2654 (triggering incident)
- **Supersedes (for roadmap.md/memory.md scope):** the "Out of scope" deferral in
  `docs/archive/todo-devlog-decision-authority-spec/2026-08-29-design.md`

## 1. Problem

`project-docs/roadmap.md`, `todo.md`, and `costs.md` are git-tracked files regenerated from
`state.db` per-checkout whenever a mutating command runs in that worktree. This has produced at
least 17 distinct drift incidents since 2026-08-29 (see gh:#2653 comment for the full timeline),
accelerating from roughly one every 2.5 weeks to one every 1.7 days, surviving three separate
process-level remediation attempts. The underlying defect class — two sources of truth that
something has to remember to keep in sync — was already identified and fixed for `todo.md`
(full generation + doctor-level hand-edit-drift guard, shipped 2026-09-01) but was explicitly
deferred for `roadmap.md`/`memory.md` "unless a future issue surfaces the same defect class
there." It has.

A separate, earlier-suspected blocker — that worktrees/dispatched jobs maintain divergent local
`state.db` copies that only get reconciled via git-merging the committed markdown — does **not**
hold. `synlynk/__init__.py`'s `_resolve_db_path()`/`_get_db()` are fail-closed by design: every
writer resolves to one canonical `~/.synlynk/workspaces/<slug>/state.db` by default, raising
`RuntimeError` rather than silently diverging unless a caller explicitly opts into
`SYNLYNK_ALLOW_STATE_DB_FALLBACK=1` (which `dispatch.py` never sets). The historical shard
fragmentation this concern was based on (gh:#1831) is closed, with no active writes since
2026-09-15. The actual root cause of the triggering incident was ordinary git staleness — a
worktree's checkout predating commits merged elsewhere — not DB divergence.

## 2. Decision

1. Drop `roadmap.md`, `todo.md`, `costs.md` from git tracking. `state.db` is sole authority; a
   CLI command renders any of them on demand, locally or in CI.
2. Sync `roadmap_arcs` (releases) to GitHub Milestones and their stories to Issues via REST/
   GraphQL API only (Pattern A: core primitives — Milestones, Issues, labels — not Projects v2
   custom fields). No manual board/field setup.
3. Required (not follow-on) schema/write-path change: populate `cost_entries.epic_id` at write
   time so release-level cost rollups are a live query instead of two aspirational, always-NULL
   columns.
4. One-time normalization pass over the existing 66 `roadmap_arcs` rows before any GitHub sync
   touches them.
5. Extend the existing Multi-Task & Multi-Goal Series Tracking Protocol (parent-issue rollup
   comments) to cover devlog entries going forward — no new mechanism, no historical backfill.
6. Apply the same Pattern-A treatment to `decisions` (one Issue per row), fully backfilled.
7. `memory.md`/`memory_entries` are explicitly out of scope — prose, no structural FK backbone,
   no clear win from migration.

### Why Pattern A, not Pattern B (Projects v2 custom fields)

Pattern B would store cost (and other) values as GitHub Project custom fields — a second
storage location for data whose authoritative home is `cost_entries`. That recreates the exact
two-sources-of-truth problem this spec exists to eliminate, just on a new surface. Pattern A
only *renders* already-authoritative data (Milestone `description`, Issue body) — nothing new
is stored on the GitHub side except the sync bookkeeping described in §4.

## 3. Data Model Changes

### 3.1 `cost_entries.epic_id` resolution (required, not deferred)

Applied at every `cost_entries` insert (both `synlynk cost log` and dispatch-side capture):

1. If `story_id` is set and that story has a `roadmap_phases.story_id` match → resolve via that
   phase's `arc_version` → `roadmap_arcs.id`.
2. Else if the story's `goal_id` is tagged to a release (no such tagging exists today; this
   spec does not add one — see §3.3) → N/A, falls through.
3. Else leave `epic_id` NULL and set `estimate_basis = "epic_unresolved"` so unresolved rows are
   queryable/auditable rather than silently absent from rollups.

**Precondition this depends on:** `roadmap_phases.story_id` must actually be populated when a
story is attached to a release phase. Today only 29/82 `roadmap_phases` rows have it set. This
spec requires the `synlynk roadmap`/`synlynk story` phase-attach path to set
`roadmap_phases.story_id` going forward — without this, step 1 above resolves almost nothing
and the whole chain is cosmetic.

### 3.2 `roadmap_arcs` normalization (one-time migration, blocking prerequisite for §4)

Current state (66 rows) includes non-version identifiers and duplicate/malformed version
strings:

- `"v0.1–v0.3.0"` (en-dash range), `"1.0.0"` (likely a dupe of `v1.0.0`),
  `"epic-job-truth-2026-08"`, `"Future Expansions"` — none of these are valid Milestone-eligible
  release identifiers as-is.
- Status values beyond shipped/planned: `deferred`, `superseded` — GitHub Milestones only have
  open/closed.

Migration:
- New column `roadmap_arcs.is_milestone_eligible` (boolean, default `true`). Set `false` for
  rows that are not real release identifiers (`"Future Expansions"`,
  `"epic-job-truth-2026-08"`). Range-string rows (`"v0.1–v0.3.0"`) also get `false` — they
  predate per-version granularity and aren't worth splitting retroactively.
- Duplicate collapse: `"1.0.0"` merges into `v1.0.0`, preferring whichever row has more linked
  `roadmap_phases`/`cost_entries` rows; the losing row's `id` is retired, not deleted (FK
  references get repointed).
- Sync-time status mapping (no new column needed): `shipped`/`superseded` → Milestone closed;
  `planned`/`deferred` → open. `deferred` and `superseded` additionally get a
  `status:deferred`/`status:superseded` label on the Milestone so the open/closed binary doesn't
  erase the distinction.

### 3.3 `decisions` table

No schema change. `decision_id`, `status`, `goal_id`/`story_id`, `synthesis`/`decision_text`
already map cleanly to an Issue's identity/state/body.

### 3.4 New table: `github_sync_map`

```sql
CREATE TABLE github_sync_map (
    entity_type    TEXT NOT NULL,   -- 'roadmap_arc' | 'story' | 'decision'
    entity_id      TEXT NOT NULL,   -- roadmap_arcs.id / stories.story_id / decisions.decision_id
    github_number  INTEGER NOT NULL,
    github_node_id TEXT,
    content_hash   TEXT,            -- hash of the fields that determine sync content, for change detection
    last_synced_at TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (entity_type, entity_id)
);
```

This is a cache of a GitHub-side fact (which issue/milestone number corresponds to which local
row), not a second source of truth for roadmap/cost data — it exists purely so sync runs don't
re-derive GitHub IDs by API search every time.

## 4. GitHub Sync Mechanism

**Primitives (REST-first, Pattern A):**
- Release → Milestone. `title = "vX.Y.Z"`, `due_on = roadmap_arcs.target_date`,
  `description` = rendered phase list + cost rollup (regenerated every sync, not stored as a
  field).
- Story/phase → Issue, assigned to the release's Milestone. Body includes a machine-readable
  footer (`<!-- synlynk:story_id=story-xxxx -->`) so matching doesn't depend on title stability
  — titles alone are unreliable given §3.2's normalization history.
- `decisions` row → Issue, no milestone, label `decision`, state from `decisions.status`.

**Idempotency:**
1. One `GET /repos/{owner}/{repo}/milestones?state=all` per sync run, build an in-memory
   `title → milestone` map. Check-then-create, never create-then-check.
2. For each `roadmap_arcs` row with `is_milestone_eligible = true`: if present in the map and
   anything differs (`due_on`, state, description), `PATCH`; else `POST` create. Record/update
   `github_sync_map`.
3. For stories/decisions: look up `github_sync_map` first; only fall back to an API search
   (by footer content) if the local cache has no row, which should only happen on first sync or
   after local state loss.

**Cost rollup rendering:** computed fresh from `cost_entries` grouped by `epic_id`, written into
the Milestone `description` on every sync. Same shape as the current `costs.md` table
(total `actual_usd`, token counts, harness breakdown), rendered to a different target — never
stored as a GitHub field.

**Trigger points:**
- `synlynk release` checklist — replaces the currently-manual `[ ] gh release create` /
  `[ ] Roadmap row marked shipped` lines with automated Milestone create/close.
- `synlynk roadmap`/`synlynk story` mutating commands — sync the affected arc/story inline,
  same place `roadmap.md` regeneration happens today.
- Standalone `synlynk gh sync-roadmap [--dry-run] [--backfill]` for manual re-sync and the
  one-time backfill in §5.

## 5. Backfill Plan

Must run in this order, via `synlynk gh sync-roadmap --backfill --dry-run` first:

1. **Normalize `roadmap_arcs`** (§3.2) before any GitHub call. Dry-run prints proposed
   merges/flags; no auto-apply.
2. **Backfill `cost_entries.epic_id`** over all 3,456 existing rows using §3.1's resolution
   chain. Expected outcome, stated explicitly: only rows with `story_id` (3,177/3,456) are
   resolvable at all, and only those whose story is or can be retroactively linked to a
   `roadmap_phases` row resolve cleanly — likely a minority, since only 29/82 phases currently
   have `story_id` set. Everything else gets `estimate_basis = "epic_unresolved"` and shows as
   an explicit "unattributed" bucket in rollups — never silently dropped or guessed.
3. **Create Milestones** for all `is_milestone_eligible = true` arcs, version order. `shipped`/
   `superseded` arcs are created and immediately closed; `closed_at` backfilled from the nearest
   `git log` release-commit date where findable, else the backfill run's own timestamp with an
   explicit "approximate" note in the description.
4. **Create Issues for every story across every arc**, regardless of status — full backfill,
   no skip for old shipped-arc stories. For the 844 stories with `gh_issue` already populated,
   link the existing issue to its milestone rather than duplicating. For the rest, create new.
5. **Decisions → Issues**, full backfill (expected to be a small set — row count confirmed at
   implementation time).

**Verification gate before backfill is considered done:**
- Spot-check N=5 most-recent `shipped` milestones' `closed_at` against `git log` release-commit
  dates.
- Confirm the Milestone-rendered cost rollup for the v0.26.x arcs matches a direct
  `cost_entries` query for the same `epic_id`s — not just "the script exited 0."

## 6. Devlog & Decisions Sync

**Decisions:** full backfill per §5.5, ongoing sync on every `decisions` write via the same
`github_sync_map`-keyed idempotent create/update path as roadmap/stories.

**Devlog:** process change only, no backfill. Extends the existing Multi-Task & Multi-Goal
Series Tracking Protocol so every devlog entry — not just epic/series completions — posts as a
comment on the relevant goal's/story's parent tracking issue, resolved via
`devlog_entries.goal_id` (already populated). Historical devlog markdown stays where it is as
an archival record; this only changes where new entries go. This is an intentional asymmetry
with decisions: decisions are the kind of record someone links back to later, devlog entries
are not, so only decisions justify the backfill cost.

## 7. Out of Scope

- `memory.md` / `memory_entries` — prose, no structural FK backbone, no clear migration win.
- Any change to the actual release *process* beyond wiring Milestone create/close into already-
  manual `synlynk release` checklist steps.
- Perfect historical cost-rollup accuracy — best-effort only; imprecision for unresolvable rows
  is documented (§5.2), not hidden.

## 8. Testing

- Unit tests for the `epic_id` resolution chain (§3.1) against fixture `stories`/
  `roadmap_phases`/`roadmap_arcs` rows, including the unresolved-fallback path.
- Unit tests for `github_sync_map` idempotency: run sync twice against a mocked GitHub API,
  assert the second run makes zero create/update calls when nothing changed.
- Integration test against a real test-org repo for the full backfill sequence, gated manually
  (not CI-default) given live GitHub API quota.

## 9. Rollout Order

1. Schema migration + `epic_id` write-path fix (own PR, testable in isolation).
2. Sync mechanism + `github_sync_map` + Milestone/Issue create-update logic (own PR).
3. Backfill run (operator-triggered via `synlynk gh sync-roadmap --backfill`, not a PR).
4. Drop `roadmap.md`/`todo.md`/`costs.md` from git tracking — last, only after backfill passes
   the §5 verification gate.
