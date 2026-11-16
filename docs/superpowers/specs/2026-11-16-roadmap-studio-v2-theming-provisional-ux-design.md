# Roadmap Studio v2: Theming, Provisional-State Language, and Verb-Parity Buttons

## Context

Roadmap Studio (v1, PRs #5293-#5296, design spec `2026-11-15-roadmap-studio-visual-proposal-ui-design.md`) shipped a drag/drop board over `approval_tickets` release-proposal rows. Nikhil reviewed the live page (2026-11-16) and flagged three gaps:

1. The Approve/Hold buttons are illegible in dark mode — both render as the same flat panel color as the card background, with no visual distinction between a commit action (Approve) and a pause action (Hold).
2. The board shows only whatever tickets happen to be `open`/`held` today (currently just one, v0.36.1) with no visible "theme" — even though `tpm_sweep.py` already computes a theme string per milestone, it's only ever baked into the GitHub issue title text, never persisted anywhere Roadmap Studio's read path can reach.
3. Nothing on the page signals that what's shown is provisional. A ticket's raw `status` word (`open`, `held`) reads as neutral/informational, not as "this release does not happen until you type `/approve`."

Separately, Nikhil asked why `/revise` and `/drop` (and, once raised, `/pin`) don't get the same button treatment as Approve/Hold, since all five actions already exist as working POST routes — only Approve/Hold have explicit buttons today; Revise is Enter-key-only, Drop is drag-only, Pin is drag-only.

## Scope decisions (resolved during brainstorming)

- **Milestone data source:** show only *real* tickets — i.e. rows that already exist in `approval_tickets` with `status IN ('open','held')`. The TPM sweep already caps concurrent open proposals at `max_active_proposals=3` (`synlynk/tpm_sweep.py`); Studio shows however many of those 0-3 rows exist, nothing speculative. The older `roadmap_arcs`/`goals` view (status=`planned`) is out of scope — it's stale (last live rows are v0.26.x) and has no theme/constituent-story shape compatible with this page. No change to `max_active_proposals` itself.
- **Pin gets a button**, not just drag: a "Pin to ▾" picker on each backlog card, since once more than one ticket is visible at once, drag-only pin has no way to disambiguate target without dragging precisely onto one specific column.
- **Reorder stays drag-only.** It's an in-place position change within a single column; there's no sensible discrete button form for it, and it wasn't raised as a gap.

## Data model change

Add a `theme TEXT` column to `approval_tickets` via a new migration, following the existing pattern in `synlynk/migrations/m0032_approval_tickets_constituent_stories.py`:

**New file:** `synlynk/migrations/m0034_approval_tickets_theme.py`

```python
"""Migration 34: persist the per-release theme string on approval_tickets.

Roadmap Studio needs to display each proposal's theme, but today the theme
computed in tpm_sweep.package_next_release_proposal() is only ever baked
into the GitHub issue title text (`[Proposal] {ver}: {theme}`) — never
written to any column Studio's read path (studio_data()) can reach.
"""
import sqlite3

from synlynk.migrations import Migration


def _up(conn: sqlite3.Connection) -> None:
    table_exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='approval_tickets'"
    ).fetchone()
    if not table_exists:
        return
    cols = {row[1] for row in conn.execute("PRAGMA table_info(approval_tickets)")}
    if "theme" not in cols:
        conn.execute("ALTER TABLE approval_tickets ADD COLUMN theme TEXT")
    # One-time backfill: the only pre-existing open release_proposal ticket
    # (v0.36.1) had its theme computed by the same roadmap_metadata lookup
    # tpm_sweep.py uses today but never persisted. Known value, set directly.
    conn.execute(
        "UPDATE approval_tickets SET theme=? "
        "WHERE action='release_proposal' AND story_id='v0.36.1' AND theme IS NULL",
        ("Milestone v0.36.1",),
    )


MIGRATION = Migration(version=34, name="add_approval_tickets_theme", up=_up)
```

(The backfill value `"Milestone v0.36.1"` matches `tpm_sweep.py`'s own fallback shape for versions not in the hardcoded `roadmap_metadata` dict — v0.36.1 isn't one of the hardcoded keys, so this is what it would have computed.)

**Write path** — `synlynk/tpm_sweep.py`'s `dispatch_tpm_advisory_proposal()` (around line 787) already computes `proposal["theme"]` and currently discards it after using it for the issue title. Add it to the existing `INSERT`:

```python
# Before (synlynk/tpm_sweep.py:787, abbreviated):
conn.execute(
    "INSERT INTO approval_tickets (story_id, action, issue_url, status, constituent_story_ids) "
    "VALUES (?, 'release_proposal', ?, 'open', ?)",
    (rel_ver, issue_url, json.dumps(constituent_story_ids)),
)

# After:
conn.execute(
    "INSERT INTO approval_tickets (story_id, action, issue_url, status, constituent_story_ids, theme) "
    "VALUES (?, 'release_proposal', ?, 'open', ?, ?)",
    (rel_ver, issue_url, json.dumps(constituent_story_ids), proposal["theme"]),
)
```

**Read path** — `synlynk/roadmap_studio.py`'s `studio_data()` (lines 58-62) adds `theme` to its `SELECT` and to the returned dict (lines 80-88):

```python
ticket_rows = active_conn.execute(
    "SELECT id, story_id AS release_version, issue_url, status, constituent_story_ids, theme "
    "FROM approval_tickets WHERE action=? AND status IN ('open','held')",
    (RELEASE_PROPOSAL_ACTION,),
).fetchall()
...
tickets.append(
    {
        "id": row_dict["id"],
        "release_version": row_dict["release_version"],
        "issue_url": row_dict["issue_url"],
        "status": row_dict["status"],
        "theme": row_dict.get("theme"),
        "stories": stories,
    }
)
```

## UI changes

All changes are in `synlynk/viz/roadmap_studio.py` (the single file holding both the HTML/CSS shell and the client-side JS — no new files needed, consistent with the existing single-file-per-Vizor-page pattern).

### Provisional-state language

- Page subtitle gains a persistent banner line directly under the existing `<p class="subtitle">`: *"Nothing below is final. A release only ships once you Approve it."*
- Column header text changes from the raw status word to explicit proposal language:
  - `open` → `"PROPOSAL — awaiting /approve"`
  - `held` → `"ON HOLD — still a proposal"`
- Each column (`.column`) gets a 3px amber-tinted left border (`--provisional: #d97706` light / `#fbbf24` dark) for the duration it's visible in this view. No stale-amber risk: once a ticket leaves `open`/`held` (i.e. gets approved), `studio_data()`'s query already excludes it from the result set entirely, so an approved ticket simply disappears from the board rather than ever rendering with this border.
- Theme renders under the release version in the column header: `"{release_version} · {theme}"` as a sub-line, falling back to nothing (not a placeholder string) when `theme` is `None`.

### Button/verb redesign

New CSS variables (added to the existing `:root` / dark-mode block):

```css
:root{...--hold-bg:#fef3c7;--hold-border:#d97706;--hold-ink:#92400e;--drop-bg:#fee2e2;--drop-border:#dc2626;--drop-ink:#991b1b}
@media (prefers-color-scheme: dark){:root{...--hold-bg:#3a2e0f;--hold-border:#d97706;--hold-ink:#fbbf24;--drop-bg:#3a1414;--drop-border:#dc2626;--drop-ink:#f87171}}
```

- **`.btn-approve`** — filled, `background:var(--accent)`, white/dark ink depending on mode, `font-weight:700`. Replaces the current shared `.btn` class for this one action.
- **`.btn-hold`** — outlined, `border:1px solid var(--hold-border)`, `background:var(--hold-bg)`, `color:var(--hold-ink)`.
- **`.btn-drop`** — small, same outlined treatment as hold but in `--drop-*` colors, sized to sit inline on a story card (`font-size:10px;padding:2px 6px`).
- **`.btn-revise`** — same neutral outlined style as the existing `.btn`, placed directly after the revise text input instead of relying on `Enter` alone (the input's `onkeydown` Enter handler stays, for users who prefer it).
- **Pin picker** — a small `<select>` (not a custom dropdown — no new JS library, keeps this page dependency-free per the v1 spec's "no build step" constraint) listing every currently-open ticket's `release_version`, with a "Pin" button next to it. Appears only on backlog cards (`cardHtml(story, ticketId)` already distinguishes backlog cards via `ticketId == null`).

### Card-level Drop button

`cardHtml()` gains a second rendering branch: cards rendered inside a ticket column (`ticketId != null`) get a `.btn-drop` button; backlog cards (`ticketId == null`) get the Pin picker instead. One function, branching on the existing `ticketId` parameter — no new function needed.

```js
function cardHtml(story,ticketId){
  const action = ticketId!=null
    ? `<button class="btn btn-drop" onclick="dropStory('${esc(story.story_id)}')">Drop</button>`
    : openTickets.length
      ? `<select class="pin-select" id="pin-${esc(story.story_id)}">${openTickets.map(t=>`<option value="${t.id}">${esc(t.release_version)}</option>`).join('')}</select>
         <button class="btn btn-pin" onclick="pinStory(Number(document.getElementById('pin-${esc(story.story_id)}').value),'${esc(story.story_id)}')">Pin</button>`
      : '';
  return `<article class="card" draggable="true" data-story-id="${esc(story.story_id)}" data-ticket-id="${ticketId??''}">
    <h3>${esc(story.title||story.story_id)}</h3>
    <div class="meta">${esc(story.story_id)} &middot; ${esc(story.role||'')}</div>
    <div class="card-actions">${action}</div>
  </article>`;
}
```

(`openTickets` is derived once per `draw()` call from `studioData.tickets`, so the picker always reflects the current board.)

### Multi-milestone layout

No structural change: `.board{display:flex;gap:14px;...;overflow-x:auto}` (existing, `synlynk/viz/roadmap_studio.py:26`) already lays out N columns side-by-side with horizontal scroll once they overflow. With today's data (one open ticket) this is unverifiable beyond code inspection; the plan's test tasks include a fixture seeding 3 tickets to manually confirm the layout holds before merge.

## Out of scope

- Changing `max_active_proposals` (TPM sweep's own concurrent-proposal cap) — that's a scheduling/policy decision, not a UI concern.
- Surfacing the stale `roadmap_arcs`/`goals` "planned" data — no coherent theme/constituent shape exists there today; would need its own design pass.
- Any new JS test harness for this page — none exists today (confirmed during the v1 series); this spec keeps the same manual-browser-verification acceptance method as v1, plus Python-level tests for the DB/route layer.

## Testing

1. `tests/test_migrations_framework.py`-style unit test for `m0034`: `_up()` is idempotent (column present after running twice), and the v0.36.1 backfill sets the expected value on a fixture row.
2. `synlynk/roadmap_studio.py` test: `studio_data()` returns `theme` in each ticket dict, `None` when the column is unset on a fixture row.
3. `synlynk/viz` route test (extending `tests/test_viz_roadmap_studio_routes.py`): GET `/api/roadmap_studio` payload includes `theme` per ticket.
4. Manual browser verification (per v1's precedent, no JS harness exists): seed 2-3 fixture tickets locally, confirm — columns render side-by-side with themes shown, provisional banner and amber border appear, Approve/Hold/Drop/Revise/Pin all visually distinct and functional, Pin picker correctly targets the selected ticket.
