# Roadmap Studio — Visual Front-End for the TPM-Sweep Proposal Protocol

**Date:** 2026-11-15
**Status:** Approved by decide panel (claude/agy/codex, 2026-11-15, grok unavailable —
`2026-11-15-approve-roadmap-studio-design-pr-5286-do`) conditional on three clarifications, folded
into this revision — pending Nikhil's sign-off

## Context

Nikhil's stated problem: it's hard to track the roadmap by theme/constituents, and prioritization
changes constantly based on how early adopters respond — he wants a visual way to reorder, park,
and group roadmap items rather than reading markdown tables and typing GitHub comments.

Two existing architecture decisions bound this spec and were confirmed directly with Nikhil before
writing it:

1. **Approach C** (`2026-11-13-fully-derived-roadmap-approach-c-design.md`, approved 2026-11-13)
   made the roadmap fully derived: `roadmap_arcs`/`roadmap_phases` are SQL views computed from
   `goals.arc_version`/`phase_title`/`roadmap_priority`, with `decide --record` as the single
   writer. Manual `roadmap add`/`update` was deliberately removed. This spec does not touch that
   schema, those columns, or those views.
2. **gh:#2653** (`2026-10-29-roadmap-state-db-github-authority-design.md`) deliberately made
   GitHub Milestones/Issues a **read-only rendered mirror** of `state.db` (Pattern A), explicitly
   rejecting GitHub Projects v2 custom fields as "recreating the two-sources-of-truth problem."
   This spec does not add a GitHub write-back path.

Separately, `synlynk/tpm_sweep.py` already implements a working proposal/approval mechanism:
`package_next_release_proposal()` packages up to 5 unblocked backlog stories into a single-release
candidate, `format_release_proposal_markdown()` renders it as a GitHub issue body, and
`process_proposal_comments()` parses `/approve`, `/revise <text>`, `/drop <story-id>`,
`/prioritize <story-id>`, and `/hold` comments on that issue into writes against `stories` and
`approval_tickets`. Nikhil confirmed he's happy with this structure as-is and specifically asked
for the *existing* `/revise`-style interaction to become visual, on its own dedicated page —
not for a new roadmap data model.

## Decision

Build **Roadmap Studio**, a new Vizor page that visualizes open/held `release_proposal`
`approval_tickets` as draggable cards and a backlog pool, and turns the five comment-grammar
commands into clicks/drags. It is a UI layer over the existing mechanism, not a new source of
truth. `state.db` and the comment-grammar protocol remain authoritative; this page calls the same
underlying writes `process_proposal_comments()` already makes, directly (bypassing GitHub comment
parsing, since the Vizor page is itself the human input channel — no comment text to parse).

### Why not GitHub Projects v2 (confirmed with Nikhil)

GitHub Milestones/Issues sync is read-only by design (Pattern A, above). Nikhil considered and
rejected driving reordering from GitHub Projects v2's native drag/drop with an import-back path —
it would reopen the exact two-way-sync problem Pattern A exists to avoid, just on ordering/grouping
data instead of cost/status data.

### Why not a new staging/draft schema

An earlier version of this design considered a separate staging table (draft arc/phase/priority
fields, decoupled from ratification) to support fully free-form milestone packaging. Nikhil scoped
this down: the existing TPM-sweep-generated proposal *is* the draft layer already — it's an
`approval_tickets` row that isn't "real" until `/approve`. No second table is needed; Roadmap
Studio visualizes what already exists and writes through the same columns.

## Scope

**In scope:**
- A new Vizor page rendering all `approval_tickets` rows with `action='release_proposal'` and
  `status IN ('open', 'held')` as milestone columns, each showing its resolved `constituent_story_ids`
  as cards (title, role, harness, estimated cost, status — the same fields
  `format_release_proposal_markdown()` already renders as a table).
- A backlog pane: stories with `readiness IN ('advisory', 'draft', 'ready')` not already claimed by
  an open ticket's `constituent_story_ids` — the same candidate pool
  `package_next_release_proposal()` draws from.
- Five interactions, each mapped onto the exact write `process_proposal_comments()` makes for the
  equivalent comment, called directly rather than via comment parsing:
  - **Approve** (button on a milestone column) → `stories.readiness='ready'` for all constituents,
    ticket `status='resolved'`.
  - **Hold** (button) → ticket `status='held'`.
  - **Revise** (text box) → calls `process_proposal_comments()`'s existing revise path, which today
    returns the instruction in an in-memory `revision_instructions` list only — confirmed via
    `grep -n revision_instructions synlynk/tpm_sweep.py` (lines 882, 913, 949): it is never written
    to any table or column, so today's `/revise` instruction is not actually persisted anywhere for
    later TPM reading. Roadmap Studio's Revise box matches this exact (non-persistent) behavior for
    parity with the GitHub-comment path — no new auto-replanning behavior, and no new persistence
    added in this spec either. If persisting revise instructions turns out to matter in practice,
    that is a follow-up story against `tpm_sweep.py` itself, not a Roadmap Studio design change.
  - **Drop** (drag a card out of a milestone column into backlog, or a "drop" affordance on the
    card) → `stories.readiness='deferred'`.
  - **Prioritize** (drag-to-reorder within a milestone column) → see "New column" below.
- One small additive column: `stories.proposal_order INTEGER` (nullable), written only by this
  page's drag-to-reorder interaction. It is a display-ordering hint local to a proposal, not a
  roadmap-authority field — it does not feed `goals.roadmap_priority` or the Approach C views.
  Rationale: today's `/prioritize` only sets a binary flag (`stories.priority=1`, "move to the
  critical path"); it has no concept of relative position. Drag-to-reorder needs an ordinal to be
  meaningful, so this column is added specifically for that, leaving `/prioritize`'s existing
  binary semantics on the GitHub-comment path untouched.
- **Pin:** dragging a backlog story into a milestone column appends its `story_id` into that
  ticket's existing `constituent_story_ids` JSON column directly — the same column
  `dispatch_tpm_advisory_proposal()` already writes at proposal-creation time. This makes the story
  stick to that specific proposal even if a later TPM sweep or `/revise` cycle would not otherwise
  have selected it. No new column; reusing what's already there.
- **Pin vs. the 5-story cap:** `package_next_release_proposal()` only validates the 5-story cap at
  proposal-creation time — nothing re-checks it when `constituent_story_ids` is mutated afterward.
  Pin is therefore capable of pushing a ticket past 5 constituents. Decided behavior: pin is allowed
  to exceed the cap (it's a deliberate manual override of a TPM-generated suggestion, which is the
  entire point of the feature), but the UI surfaces a non-blocking warning badge on the column
  ("6 of 5 suggested") rather than enforcing the cap silently or blocking the action. No change to
  `package_next_release_proposal()` itself — the cap still applies exactly as before to what the TPM
  sweep proposes on its own.
- **`proposal_order` scoping invariant:** a reorder write only ever targets story IDs that are
  members of the acting ticket's own `constituent_story_ids` — the reorder handler rejects (not
  silently ignores) any `story_id` in `ordered_story_ids` not present in that ticket's own
  constituent list. This guards against a story being reordered under a ticket it doesn't actually
  belong to, even though nothing in today's packaging logic produces a story belonging to more than
  one active ticket simultaneously (codex's note from the decide panel, kept as a one-line
  invariant rather than new logic, since the precondition can't currently occur).

**Out of scope (explicitly deferred, not silently dropped):**
- Free-form creation of new milestones beyond the existing one-candidate-per-release-version /
  `max_active_proposals` cap (default 3). Roadmap Studio visualizes and rearranges *within* that
  existing structure. A "spin up an arbitrary Nth milestone by hand, independent of the TPM sweep
  cadence" capability is new scope, not a visual wrapper, and was not asked for in this round.
- Any change to `goals.arc_version`/`phase_title`/`roadmap_priority`, the `roadmap_arcs`/`roadmap_phases`
  views, or `decide --record`'s `--arc`/`--phase`/`--priority` flags (Approach C, untouched).
- Any GitHub write-back (Pattern A, untouched).
- Auto-replanning on `/revise` — still a human/TPM-read instruction, not executed by this spec.

## Design

### Page location and shell

New Vizor view, `roadmap_studio.html`, generated by `generate_roadmap_studio_html()` in
`synlynk/viz.py` (same generator → `_write_cache()` pattern as every other view). Added to the
**STATUS** nav category alongside Board and Gantt (`synlynk/viz/home.py` sidebar), since it is a
status/action surface, not a read-only projection.

### Data query

```sql
-- Open/held proposals
SELECT id, story_id AS release_version, issue_url, status, constituent_story_ids
FROM approval_tickets
WHERE action = 'release_proposal' AND status IN ('open', 'held');

-- Resolved constituent stories per ticket (constituent_story_ids is a JSON array)
SELECT story_id, title, role, estimated_tokens, gh_issue, readiness, status,
       priority, proposal_order
FROM stories
WHERE story_id IN (<constituent_story_ids for this ticket>)
ORDER BY proposal_order ASC NULLS LAST, rowid ASC;

-- Backlog pool (same predicate as package_next_release_proposal())
SELECT story_id, title, role, estimated_tokens, gh_issue
FROM stories
WHERE (readiness = 'advisory'
       OR (readiness IN ('ready', 'draft') AND status NOT IN ('done', 'archived')))
  AND story_id NOT IN (<union of all open/held tickets' constituent_story_ids>);
```

### Write path

One new local write surface on the always-on Vizor daemon, following the existing
`authorize_local_request` single-call-site pattern used for Board's `/api/board/stage` and
`/api/board/status` (`2026-10-31` write-path spec):

- `POST /w/<slug>/api/roadmap_studio/approve` `{ticket_id}`
- `POST /w/<slug>/api/roadmap_studio/hold` `{ticket_id}`
- `POST /w/<slug>/api/roadmap_studio/revise` `{ticket_id, instructions}`
- `POST /w/<slug>/api/roadmap_studio/drop` `{story_id}`
- `POST /w/<slug>/api/roadmap_studio/reorder` `{ticket_id, ordered_story_ids}` — writes
  `proposal_order` sequentially for the given story IDs.
- `POST /w/<slug>/api/roadmap_studio/pin` `{ticket_id, story_id}` — appends `story_id` into that
  ticket's `constituent_story_ids` JSON if not already present.

Each handler calls the same underlying SQL `process_proposal_comments()` already executes for its
matching comment command (extracted into small shared helper functions where
`process_proposal_comments()` currently inlines the SQL, so both the comment-grammar path and the
Vizor path call one implementation — avoiding two copies of the same write logic drifting apart).

**Ticket-scoping difference from the comment path:** today, `process_proposal_comments()` scans
and acts across *all* open proposals when parsing a GitHub issue's comments (the issue itself is
the scope, and only one proposal issue is normally open at a time in practice, but the function
doesn't enforce that). The extracted shared helpers take an explicit `ticket_id` and act only
against that one ticket's rows — Roadmap Studio always passes the `ticket_id` of the column the
user is interacting with, since multiple milestone columns are visible and addressable
simultaneously in the UI, unlike the single-issue-comment path. The GitHub-comment path keeps its
current all-open-proposals behavior unchanged; only the new Vizor-side callers are ticket-scoped.

### Front-end interaction

This is the first Vizor view with real JavaScript (confirmed acceptable with Nikhil — Vizor's
zero-JS architecture is a convention, not a hard constraint, and drag/drop has no native-HTML
equivalent). Scope the JS tightly: one small module (`roadmap_studio.js`) handling card drag
events and the five fetch calls above, with no build step and no framework — consistent with
Vizor's existing "no build step" character even though it is no longer zero-JS.

- Milestone columns render as a horizontal board (ticket per column), cards vertically
  draggable within a column (→ reorder) and between a column and the backlog pane (→ drop/pin).
- Each column header carries Approve / Hold buttons and a collapsible Revise text box.
- Backlog pane is a single scrollable list, drag-source for pin, drag-target for drop.
- On any successful write, the page re-fetches and re-renders from `state.db` rather than trusting
  optimistic local state — keeps the page a thin view over authoritative data rather than its own
  cache.

### Testing

- Unit tests for the new shared helper functions (approve/hold/revise/drop/reorder/pin), asserting
  identical `stories`/`approval_tickets` row changes whether invoked via the extracted helper
  (Vizor path) or via `process_proposal_comments()`'s existing comment parsing (GitHub path) — this
  is the regression that would indicate the two paths drifted.
- `viz.py` rendering test for `generate_roadmap_studio_html()`, same pattern as other view tests.
- Manual verification via `synlynk viz` for drag/drop behavior (not meaningfully unit-testable).

## Rollout

Additive only: one new nullable column (`stories.proposal_order`), one new view, one new set of
daemon routes. No migration of existing data, no change to any other view's behavior. Can ship in
a single PR.
