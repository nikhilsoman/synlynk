# Roadmap Studio v2: Theming, Provisional-State Language, and Verb-Parity Buttons — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist each release proposal's theme string, and redesign Roadmap Studio's board to make legible, verb-complete (Approve/Hold/Revise/Drop/Pin) actions and the provisional nature of every shown milestone explicit.

**Architecture:** One new migration (`m0034`) adds `approval_tickets.theme`; `tpm_sweep.py`'s existing insert persists it; `roadmap_studio.py`'s `studio_data()` read path returns it; `viz/roadmap_studio.py`'s single-file HTML/CSS/JS shell gets new CSS classes, reworded copy, and two new per-card controls (Drop, Pin picker). No new files, no new routes — this extends four existing modules.

**Tech Stack:** Python 3, sqlite3, pytest, vanilla JS/CSS (no build step, per Vizor's existing convention).

---

### Task 1: `theme` column migration

**Files:**
- Create: `synlynk/migrations/m0034_approval_tickets_theme.py`
- Modify: `synlynk/migrations/runner.py` (import + register in `MIGRATIONS`)
- Test: `tests/test_migrations_framework.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_migrations_framework.py` (mirrors the existing `test_migration_0032_...`/`test_m0032_is_idempotent` pair immediately above, at the end of the file):

```python
def test_migration_0034_adds_approval_tickets_theme(tmp_path, monkeypatch):
    import sqlite3
    from synlynk.migrations import runner
    from synlynk.migrations.m0034_approval_tickets_theme import MIGRATION

    conn = sqlite3.connect(tmp_path / "state.db")
    conn.execute(
        """CREATE TABLE approval_tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            story_id TEXT,
            action TEXT,
            issue_url TEXT,
            status TEXT
        )"""
    )
    conn.execute("PRAGMA user_version = 33")
    conn.commit()

    monkeypatch.setattr(runner, "MIGRATIONS", [MIGRATION])
    runner.run_pending_migrations(conn)

    cols = {row[1] for row in conn.execute("PRAGMA table_info(approval_tickets)")}
    assert "theme" in cols
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 34

    # Re-running against an already-migrated db is a no-op, not a crash.
    runner.run_pending_migrations(conn)
    cols_after = {row[1] for row in conn.execute("PRAGMA table_info(approval_tickets)")}
    assert cols_after == cols
    conn.close()


def test_m0034_is_idempotent(tmp_path):
    import sqlite3
    from synlynk.migrations.m0034_approval_tickets_theme import MIGRATION

    conn = sqlite3.connect(tmp_path / "state.db")
    conn.execute(
        """CREATE TABLE approval_tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            story_id TEXT,
            action TEXT,
            issue_url TEXT,
            status TEXT
        )"""
    )
    MIGRATION.up(conn)
    MIGRATION.up(conn)
    conn.commit()

    cols = {row[1] for row in conn.execute("PRAGMA table_info(approval_tickets)")}
    assert "theme" in cols
    conn.close()


def test_m0034_backfills_known_v0_36_1_theme(tmp_path):
    import sqlite3
    from synlynk.migrations.m0034_approval_tickets_theme import MIGRATION

    conn = sqlite3.connect(tmp_path / "state.db")
    conn.execute(
        """CREATE TABLE approval_tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            story_id TEXT,
            action TEXT,
            issue_url TEXT,
            status TEXT
        )"""
    )
    conn.execute(
        "INSERT INTO approval_tickets (story_id, action, issue_url, status) "
        "VALUES ('v0.36.1', 'release_proposal', 'https://github.com/test/5285', 'open')"
    )
    conn.commit()

    MIGRATION.up(conn)
    conn.commit()

    theme = conn.execute(
        "SELECT theme FROM approval_tickets WHERE story_id='v0.36.1'"
    ).fetchone()[0]
    assert theme == "Milestone v0.36.1"
    conn.close()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_migrations_framework.py -k "m0034" -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.migrations.m0034_approval_tickets_theme'`

- [ ] **Step 3: Create the migration**

Create `synlynk/migrations/m0034_approval_tickets_theme.py`:

```python
"""Migration 34: persist the per-release theme string on approval_tickets.

Roadmap Studio needs to display each proposal's theme, but today the theme
computed in tpm_sweep.package_next_release_proposal() is only ever baked
into the GitHub issue title text (`[Proposal] {ver}: {theme}`) — never
written to any column Studio's read path (studio_data()) can reach.

See docs/superpowers/specs/2026-11-16-roadmap-studio-v2-theming-provisional-ux-design.md.
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
    # tpm_sweep.py uses today but never persisted. v0.36.1 isn't one of the
    # hardcoded roadmap_metadata keys, so this matches what it would have
    # fallen back to computing.
    conn.execute(
        "UPDATE approval_tickets SET theme=? "
        "WHERE action='release_proposal' AND story_id='v0.36.1' AND theme IS NULL",
        ("Milestone v0.36.1",),
    )


MIGRATION = Migration(version=34, name="add_approval_tickets_theme", up=_up)
```

- [ ] **Step 4: Register the migration in the runner**

In `synlynk/migrations/runner.py`, add the import after the existing `M0033` import (line 27):

```python
from synlynk.migrations.m0034_approval_tickets_theme import MIGRATION as M0034
```

And add `M0034` to the `MIGRATIONS` list (currently ends `M0032, M0033,` around line 35):

```python
    M0032, M0033, M0034,
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `pytest tests/test_migrations_framework.py -k "m0034" -v`
Expected: PASS (3 passed)

- [ ] **Step 6: Run the full migrations test file to confirm no regression**

Run: `pytest tests/test_migrations_framework.py tests/test_db_migration.py -v`
Expected: PASS, no failures

- [ ] **Step 7: Commit**

```bash
git add synlynk/migrations/m0034_approval_tickets_theme.py synlynk/migrations/runner.py tests/test_migrations_framework.py
git commit -m "feat: add approval_tickets.theme migration (m0034)"
```

---

### Task 2: Persist theme on the write path (`tpm_sweep.py`)

**Files:**
- Modify: `synlynk/tpm_sweep.py:815-837` (the `INSERT INTO approval_tickets` block inside `dispatch_tpm_advisory_proposal`)
- Test: `tests/test_tpm_l1_advisory.py`

The existing insert already branches on whether `constituent_story_ids` exists as a column (via a `PRAGMA table_info` check), because several test fixtures intentionally create a minimal `approval_tickets` table without it. `theme` needs the same defensive treatment — not a required column for this function to keep working against those older/minimal fixtures.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_tpm_l1_advisory.py`, near the other `dispatch_tpm_advisory_proposal` tests (after `test_dispatch_tpm_advisory_proposal_uses_tpm_role`, which already shows the `conn.execute("CREATE TABLE IF NOT EXISTS approval_tickets (...)")` + monkeypatched `gh_role` pattern to copy):

```python
def test_dispatch_tpm_advisory_proposal_persists_theme(monkeypatch, tmp_path):
    import sqlite3
    import synlynk.tpm_sweep as tpm_mod

    conn = sqlite3.connect(tmp_path / "state.db")
    conn.execute(
        "CREATE TABLE approval_tickets (id INTEGER PRIMARY KEY, story_id TEXT, "
        "action TEXT, issue_url TEXT, status TEXT, constituent_story_ids TEXT, theme TEXT)"
    )
    conn.commit()

    monkeypatch.setattr(
        tpm_mod,
        "package_next_release_proposal",
        lambda conn=None, repo_root=".": {
            "release_version": "v9.9.9",
            "theme": "Test Theme",
            "bookend_mtd": "", "bookend_wtd": "", "bookend_today": "", "bookend_horizon": "",
            "stories": [], "role_breakdown": {},
        },
    )

    class _FakeResult:
        returncode = 0
        stdout = "https://github.com/test/9999\n"
        stderr = ""

    monkeypatch.setattr(
        "synlynk.gh_role.run_gh_as_role", lambda *a, **kw: _FakeResult()
    )

    url = tpm_mod.dispatch_tpm_advisory_proposal(conn=conn, max_active_proposals=5, assignee="nikhilsoman")

    assert url == "https://github.com/test/9999"
    theme = conn.execute(
        "SELECT theme FROM approval_tickets WHERE story_id='v9.9.9'"
    ).fetchone()[0]
    assert theme == "Test Theme"
    conn.close()


def test_dispatch_tpm_advisory_proposal_skips_theme_when_column_absent(monkeypatch, tmp_path):
    """The existing constituent_story_ids-absent fixtures in this file prove the insert must
    still succeed against a minimal approval_tickets table with neither optional column."""
    import sqlite3
    import synlynk.tpm_sweep as tpm_mod

    conn = sqlite3.connect(tmp_path / "state.db")
    conn.execute(
        "CREATE TABLE approval_tickets (id INTEGER PRIMARY KEY, story_id TEXT, "
        "action TEXT, issue_url TEXT, status TEXT)"
    )
    conn.commit()

    monkeypatch.setattr(
        tpm_mod,
        "package_next_release_proposal",
        lambda conn=None, repo_root=".": {
            "release_version": "v9.9.8",
            "theme": "Test Theme",
            "bookend_mtd": "", "bookend_wtd": "", "bookend_today": "", "bookend_horizon": "",
            "stories": [], "role_breakdown": {},
        },
    )

    class _FakeResult:
        returncode = 0
        stdout = "https://github.com/test/9998\n"
        stderr = ""

    monkeypatch.setattr(
        "synlynk.gh_role.run_gh_as_role", lambda *a, **kw: _FakeResult()
    )

    url = tpm_mod.dispatch_tpm_advisory_proposal(conn=conn, max_active_proposals=5, assignee="nikhilsoman")

    assert url == "https://github.com/test/9998"
    row = conn.execute(
        "SELECT story_id, status FROM approval_tickets WHERE story_id='v9.9.8'"
    ).fetchone()
    assert row == ("v9.9.8", "open")
    conn.close()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_tpm_l1_advisory.py -k "persists_theme or skips_theme" -v`
Expected: FAIL — `test_dispatch_tpm_advisory_proposal_persists_theme` fails with `sqlite3.OperationalError: no such column: theme` (or an assertion on a `None` theme) since the insert doesn't write it yet.

- [ ] **Step 3: Update the insert to persist theme defensively**

In `synlynk/tpm_sweep.py`, replace lines 818-831 (the `try:` block building the `INSERT INTO approval_tickets` statement) with:

```python
        try:
            cols = {row[1] for row in conn.execute("PRAGMA table_info(approval_tickets)")}
            extra_cols: list[str] = []
            extra_vals: list[Any] = []
            if "constituent_story_ids" in cols:
                extra_cols.append("constituent_story_ids")
                extra_vals.append(constituent_ids_json)
            if "theme" in cols:
                extra_cols.append("theme")
                extra_vals.append(proposal["theme"])
            col_list = "story_id, action, issue_url, status" + "".join(f", {c}" for c in extra_cols)
            placeholders = "?, 'release_proposal', ?, 'open'" + ", ?" * len(extra_cols)
            conn.execute(
                f"INSERT INTO approval_tickets ({col_list}) VALUES ({placeholders})",
                (rel_ver, issue_url, *extra_vals),
            )
            conn.commit()
```

Check the top of `synlynk/tpm_sweep.py` for an existing `from typing import ...` import line — if `Any` isn't already imported, add it to that line (needed for the `list[Any]` annotation above).

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_tpm_l1_advisory.py -k "persists_theme or skips_theme" -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Run the full file to confirm no regression**

Run: `pytest tests/test_tpm_l1_advisory.py -v`
Expected: PASS, all tests green (the pre-existing tests that create `approval_tickets` without `constituent_story_ids` or `theme` must still pass unchanged)

- [ ] **Step 6: Commit**

```bash
git add synlynk/tpm_sweep.py tests/test_tpm_l1_advisory.py
git commit -m "feat: persist release-proposal theme into approval_tickets.theme"
```

---

### Task 3: Return theme on the read path (`roadmap_studio.py`)

**Files:**
- Modify: `synlynk/roadmap_studio.py:55-85` (`studio_data()`)
- Test: `tests/test_roadmap_studio.py`, `tests/test_viz_roadmap_studio_routes.py`

Both test files' `_seed()` helpers hand-write a `CREATE TABLE approval_tickets (...)` without a `theme` column. `tests/test_viz_roadmap_studio_routes.py`'s seeding connects with plain `sqlite3.connect()` (no migrations run), so `studio_data()`'s `SELECT` must not break against that fixture once `theme` is unconditionally selected — the fixture itself needs the column added.

- [ ] **Step 1: Update both test fixtures to include the `theme` column**

In `tests/test_roadmap_studio.py`, in `_seed()` (around line 26), add `theme` to the `CREATE TABLE approval_tickets` columns and set it on the inserted row:

```python
    conn.execute(
        """CREATE TABLE IF NOT EXISTS approval_tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            story_id TEXT,
            action TEXT,
            issue_url TEXT,
            status TEXT,
            opened_at TIMESTAMP,
            resolved_at TIMESTAMP,
            constituent_story_ids TEXT,
            theme TEXT
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS stories (...)"""
    )
```

(Keep the `stories` table and its `INSERT` statements unchanged; only the `approval_tickets` `CREATE TABLE` and its `INSERT` change.) Update the `INSERT INTO approval_tickets` statement two lines below it to:

```python
    conn.execute(
        "INSERT INTO approval_tickets (id, story_id, action, issue_url, status, constituent_story_ids, theme) VALUES "
        "(1, 'v0.33.0', 'release_proposal', 'https://github.com/test/1', 'open', ?, 'Test Theme')",
        (json.dumps(["s1", "s2"]),),
    )
```

In `tests/test_viz_roadmap_studio_routes.py`'s `_seed()` (lines 26-38), make the same two edits — add `theme TEXT` to the `CREATE TABLE`, and add `, theme` / `, 'Test Theme'` to the `INSERT`:

```python
    conn.execute(
        """CREATE TABLE IF NOT EXISTS approval_tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT, story_id TEXT, action TEXT,
            issue_url TEXT, status TEXT, opened_at TIMESTAMP, resolved_at TIMESTAMP,
            constituent_story_ids TEXT, theme TEXT
        )"""
    )
    conn.execute("INSERT INTO stories (story_id, title, readiness, status) VALUES ('s1','T1','ready','open')")
    conn.execute(
        "INSERT INTO approval_tickets (id, story_id, action, issue_url, status, constituent_story_ids, theme) "
        "VALUES (1, 'v1', 'release_proposal', 'https://x/1', 'open', ?, 'Test Theme')",
        (json.dumps(["s1"]),),
    )
    conn.commit()
```

- [ ] **Step 2: Add failing assertions for theme in both test files**

In `tests/test_roadmap_studio.py`'s `test_studio_data_returns_open_tickets_and_backlog`, after the existing `assert ticket["release_version"] == "v0.33.0"` line, add:

```python
        assert ticket["theme"] == "Test Theme"
```

In `tests/test_viz_roadmap_studio_routes.py`'s `test_scoped_get_returns_roadmap_studio_json_for_registered_workspace`, after the existing `assert payload["tickets"][0]["release_version"] == "v1"` line, add:

```python
        assert payload["tickets"][0]["theme"] == "Test Theme"
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `pytest tests/test_roadmap_studio.py tests/test_viz_roadmap_studio_routes.py -v`
Expected: FAIL — both new assertions fail with `KeyError: 'theme'` (the dict returned by `studio_data()` doesn't have that key yet)

- [ ] **Step 4: Update `studio_data()` to select and return theme**

In `synlynk/roadmap_studio.py`, change the `SELECT` on line 55-58:

```python
        ticket_rows = active_conn.execute(
            "SELECT id, story_id AS release_version, issue_url, status, constituent_story_ids, theme "
            "FROM approval_tickets WHERE action=? AND status IN ('open','held')",
            (RELEASE_PROPOSAL_ACTION,),
        ).fetchall()
```

And add `theme` to the returned dict on lines 77-85:

```python
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

- [ ] **Step 5: Run the tests to verify they pass**

Run: `pytest tests/test_roadmap_studio.py tests/test_viz_roadmap_studio_routes.py -v`
Expected: PASS, all tests green — including `test_scoped_get_returns_empty_fallback_for_pre_migration_database`, which creates `approval_tickets` with neither `constituent_story_ids` nor `theme` and must still hit the existing `OperationalError` fallback in `synlynk/viz/server.py`, not a new crash.

- [ ] **Step 6: Commit**

```bash
git add synlynk/roadmap_studio.py tests/test_roadmap_studio.py tests/test_viz_roadmap_studio_routes.py
git commit -m "feat: return theme from roadmap_studio.studio_data()"
```

---

### Task 4: Provisional-state language, button redesign, and Drop/Pin controls (UI)

**Files:**
- Modify: `synlynk/viz/roadmap_studio.py` (the entire file is the single-page HTML/CSS/JS shell — see current content below)
- Test: `tests/test_viz_roadmap_studio.py` (existing substring-based tests, must still pass unmodified)

No JS test harness exists for this page (confirmed in the spec); this task's acceptance is the existing Python-level rendering test plus a manual browser verification checklist at the end.

- [ ] **Step 1: Confirm the existing rendering test still describes required strings**

Run: `pytest tests/test_viz_roadmap_studio.py -v`
Expected: PASS (2 passed) — this is the baseline before editing; `test_generate_roadmap_studio_html_has_shell_and_actions` asserts `api/roadmap_studio/{approve,hold,revise,drop,reorder,pin}` all appear in the output, which the new markup must keep true.

- [ ] **Step 2: Add new CSS variables and button classes**

In `synlynk/viz/roadmap_studio.py`, replace the `:root{...}` block and the dark-mode `@media` block (lines 17-20) with:

```python
:root{--bg:#f6f8fa;--panel:#fff;--panel-2:#f1f5f9;--ink:#1f2328;--muted:#667085;--line:#d8dee4;--accent:#0d9e87;--accent-bg:#e6f7f4;--warn:#dc2626;--shadow:0 2px 8px rgba(31,35,40,0.06);--provisional:#d97706;--hold-bg:#fef3c7;--hold-border:#d97706;--hold-ink:#92400e;--drop-bg:#fee2e2;--drop-border:#dc2626;--drop-ink:#991b1b}
@media (prefers-color-scheme: dark){
  :root{--bg:#0d1117;--panel:#161b22;--panel-2:#21262d;--ink:#f0f6fc;--muted:#8b949e;--line:#30363d;--accent:#3de0c0;--accent-bg:#0d2137;--warn:#f87171;--shadow:0 2px 12px rgba(0,0,0,0.4);--provisional:#fbbf24;--hold-bg:#3a2e0f;--hold-border:#d97706;--hold-ink:#fbbf24;--drop-bg:#3a1414;--drop-border:#dc2626;--drop-ink:#f87171}
}
```

Replace the `.btn{...}` and `.btn:hover{...}` lines (lines 33-34) with:

```python
.btn{border:1px solid var(--line);background:var(--panel);border-radius:4px;padding:4px 8px;font-size:11px;cursor:pointer;font-family:inherit;font-weight:600}
.btn:hover{border-color:var(--accent)}
.btn-approve{border:none;background:var(--accent);color:#fff;font-weight:700}
.btn-approve:hover{opacity:.85}
.btn-hold{border:1px solid var(--hold-border);background:var(--hold-bg);color:var(--hold-ink)}
.btn-drop{border:1px solid var(--drop-border);background:var(--drop-bg);color:var(--drop-ink);font-size:10px;padding:2px 6px}
.btn-pin{border:1px solid var(--accent);background:var(--accent-bg);color:var(--accent);font-size:10px;padding:2px 6px}
.pin-select{font-size:10px;padding:2px;border-radius:4px;border:1px solid var(--line);background:var(--bg);color:var(--ink)}
.provisional-banner{background:var(--accent-bg);border:1px solid var(--accent);border-radius:8px;padding:8px 12px;font-size:12px;color:var(--ink);margin-bottom:16px}
.column.provisional{border-left:3px solid var(--provisional)}
.column-theme{color:var(--muted);font-size:11px;font-weight:400;margin:2px 0 0}
.card-actions{margin-top:6px}
```

- [ ] **Step 3: Add the provisional banner to the page shell**

In the `<main>` block (after the existing `<p class="subtitle">...</p>` line, around line 46), add:

```python
<p class="subtitle">Drag, approve, hold, revise, drop, and pin stories against open release proposals. Writes go straight to the product <code>state.db</code> via the same paths as the GitHub-comment grammar.</p>
<div class="provisional-banner">Nothing below is final. A release only ships once you Approve it.</div>
```

- [ ] **Step 4: Rework column header, buttons, and revise submit button in `draw()`**

Replace the `draw()` function (lines 63-83) with:

```python
function draw(){
  const openTickets=(studioData.tickets||[]).filter(t=>t.status==='open'||t.status==='held');
  document.getElementById('board').innerHTML=studioData.tickets.map(t=>{
    const overCap=(t.stories||[]).length>5;
    const statusLabel=t.status==='held'?'ON HOLD — still a proposal':'PROPOSAL — awaiting /approve';
    const themeLine=t.theme?`<div class="column-theme">${esc(t.theme)}</div>`:'';
    return `<section class="column provisional" data-ticket-id="${t.id}">
      <div class="column-header">
        <div>
          <h2>${esc(t.release_version)} &middot; ${statusLabel}</h2>
          ${themeLine}
        </div>
        ${overCap?`<span class="cap-warn">${t.stories.length} of 5 suggested</span>`:''}
      </div>
      <div class="column-actions">
        <button class="btn btn-approve" onclick="approveTicket(${t.id})">Approve</button>
        <button class="btn btn-hold" onclick="holdTicket(${t.id})">Hold</button>
      </div>
      <div class="column-actions">
        <input class="revise-box" placeholder="Revise instructions..." id="revise-${t.id}" onkeydown="if(event.key==='Enter')reviseTicket(${t.id},this.value)">
        <button class="btn" onclick="reviseTicket(${t.id},document.getElementById('revise-${t.id}').value)">Submit</button>
      </div>
      <div class="cards" data-ticket-id="${t.id}">${(t.stories||[]).map(s=>cardHtml(s,t.id,openTickets)).join('')||'<div class="empty">No stories</div>'}</div>
    </section>`;
  }).join('')||'<div class="empty">No open proposals</div>';

  document.getElementById('backlog-list').innerHTML=(studioData.backlog||[]).map(s=>cardHtml(s,null,openTickets)).join('')||'<div class="empty">Backlog empty</div>';

  wireDragAndDrop();
}
```

- [ ] **Step 5: Add the Drop button and Pin picker to `cardHtml()`**

Replace `cardHtml()` (lines 56-61) with a version that takes the list of open tickets as a third parameter, and branches on whether the card is already inside a ticket column (`ticketId != null`, gets a Drop button) or still in the backlog (`ticketId == null`, gets a Pin picker — only rendered when at least one ticket is open):

```python
function cardHtml(story,ticketId,openTickets){
  let action='';
  if(ticketId!=null){
    action=`<button class="btn btn-drop" onclick="dropStory('${esc(story.story_id)}')">Drop</button>`;
  }else if((openTickets||[]).length){
    const pinId=`pin-${esc(story.story_id)}`;
    const options=openTickets.map(t=>`<option value="${t.id}">${esc(t.release_version)}</option>`).join('');
    action=`<select class="pin-select" id="${pinId}">${options}</select> <button class="btn btn-pin" onclick="pinStory(Number(document.getElementById('${pinId}').value),'${esc(story.story_id)}')">Pin</button>`;
  }
  return `<article class="card" draggable="true" data-story-id="${esc(story.story_id)}" data-ticket-id="${ticketId??''}">
    <h3>${esc(story.title||story.story_id)}</h3>
    <div class="meta">${esc(story.story_id)} &middot; ${esc(story.role||'')}</div>
    <div class="card-actions">${action}</div>
  </article>`;
}
```

- [ ] **Step 6: Run the existing rendering test to confirm no regression**

Run: `pytest tests/test_viz_roadmap_studio.py -v`
Expected: PASS (2 passed) — all six `api/roadmap_studio/{action}` substrings and `vizorAuthHeaders` are still present in the JS, since no function names or fetch paths changed.

- [ ] **Step 7: Run the nav and write-route viz tests to confirm no regression**

Run: `pytest tests/test_viz_nav_roadmap_studio.py tests/test_viz_write_routes_roadmap_studio.py -v`
Expected: PASS, no failures (neither file asserts on button markup or CSS)

- [ ] **Step 8: Manual browser verification**

This page has no JS test harness, so the following must be checked by hand against a running Vizor daemon before this task is considered done:

1. Seed 2-3 fixture `approval_tickets` rows (`open`/`held` status, varying `theme` values) directly in a local `state.db` copy.
2. Load `/w/<slug>/roadmap_studio.html` (or whatever route serves this page) in a browser.
3. Confirm: the provisional banner renders above the board; each column header reads `"{version} · PROPOSAL — awaiting /approve"` (or the `held` variant) with the theme as a sub-line; each column has a visible amber left border.
4. Confirm: Approve renders as a filled accent-colored button, Hold as an outlined amber button, both legible against the dark-mode panel background (toggle OS dark mode to check).
5. Confirm: each card inside a ticket column shows a red-outlined Drop button; clicking it calls `/api/roadmap_studio/drop` and the card disappears from that column after reload.
6. Confirm: each backlog card shows a release-version picker + Pin button; selecting a version and clicking Pin calls `/api/roadmap_studio/pin` with that ticket's id and moves the card into that column after reload.
7. Confirm: typing into the Revise box and either pressing Enter or clicking the new Submit button both call `/api/roadmap_studio/revise` with the typed text.
8. Confirm: with 3 seeded open tickets, the board lays out 3 columns side-by-side with horizontal scroll if the viewport is narrow — no layout break.

- [ ] **Step 9: Commit**

```bash
git add synlynk/viz/roadmap_studio.py
git commit -m "feat: redesign Roadmap Studio buttons, provisional-state language, and Drop/Pin controls"
```

---

### Task 5: Full-suite verification

**Files:** none (verification only)

- [ ] **Step 1: Run every test file touched by this plan together**

Run: `pytest tests/test_migrations_framework.py tests/test_db_migration.py tests/test_tpm_l1_advisory.py tests/test_roadmap_studio.py tests/test_viz_roadmap_studio_routes.py tests/test_viz_roadmap_studio.py tests/test_viz_nav_roadmap_studio.py tests/test_viz_write_routes_roadmap_studio.py -v`
Expected: PASS, 0 failures

- [ ] **Step 2: Run the full test suite to catch any unrelated regression**

Run: `pytest -q`
Expected: PASS, 0 failures (aside from any pre-existing flaky tests already known to the project, e.g. the `realghwrite` end-to-end test documented in project memory — if that one fails, confirm it's the known flake, not a new failure, before proceeding)

- [ ] **Step 3: Push the branch and open the PR**

```bash
git push -u origin chore/roadmap-studio-v2-theming-provisional-ux
```

Open the PR via `gh pr create` (or the project's `synlynk gh --role <role> --` wrapper per this repo's GitHub-write routing), referencing the spec at `docs/superpowers/specs/2026-11-16-roadmap-studio-v2-theming-provisional-ux-design.md` and linking the GOVERNS goal/story this work is tracked under, per this project's PR discipline requirements.
