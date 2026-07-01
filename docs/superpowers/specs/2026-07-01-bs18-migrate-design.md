# BS-18: synlynk migrate — Design Spec

**Date:** 2026-07-01  
**Status:** Design approved  
**Story:** `story-v010-migrate`

---

## Goal

Move `project-docs/` out of git tracking and into `.synlynk/project-docs/` as a local-only write-through backup. Import all flat-file project state into state.db. state.db becomes the permanent source of truth; flat files are a durable local fallback and DR mirror.

This is not a one-off migration — it is an architectural shift. From this point forward, all project state is written to state.db first, then flushed immediately to `.synlynk/project-docs/` (and optionally to a user-configured cloud-synced DR folder).

---

## Architecture

**Before migrate:**
```
project-docs/          ← git-tracked, flat files are source of truth
  todo.md              ← generated view of state.db stories (already DB-backed)
  memory.md            ← flat file only
  roadmap.md           ← flat file only
  costs.md             ← flat file only
  devlogs/<user>.md    ← flat file only
.synlynk/
  state.db             ← stories, capability_ratings, daemon_jobs, etc.
```

**After migrate:**
```
project-docs/          ← removed from git, entry in .gitignore
.synlynk/
  state.db             ← source of truth for ALL project state
  .synlynk_migrated    ← sentinel; presence = migrated
  project-docs/        ← write-through flat file backup (local only, never git-tracked)
    todo.md
    memory.md
    roadmap.md
    costs.md
    devlogs/<user>.md
<dr_sync_path>/        ← optional cloud-synced DR mirror (user-configured)
  project-docs/
    todo.md
    ...
```

---

## New state.db Tables

Added via `_migrate_db()` (idempotent, `CREATE TABLE IF NOT EXISTS`):

```sql
-- memory.md sections
CREATE TABLE memory_entries (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    section     TEXT NOT NULL,        -- ## section header text
    body        TEXT NOT NULL,        -- full markdown body of section
    author      TEXT,                 -- [@username] attribution if present in body
    created_at  TEXT DEFAULT (datetime('now')),
    updated_at  TEXT DEFAULT (datetime('now'))
);

-- roadmap.md release rows
CREATE TABLE roadmap_arcs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    version     TEXT NOT NULL UNIQUE, -- e.g. "v0.10.0"
    title       TEXT,                 -- e.g. "Developer Preview"
    status      TEXT DEFAULT 'planned', -- planned | in_progress | shipped
    target_date TEXT,
    notes       TEXT
);

CREATE TABLE roadmap_phases (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    arc_version TEXT NOT NULL REFERENCES roadmap_arcs(version),
    phase_title TEXT NOT NULL,
    status      TEXT DEFAULT 'planned',
    priority    TEXT,                 -- P0 | P1 | daily-driver
    story_id    TEXT REFERENCES stories(story_id),
    notes       TEXT
);

-- costs.md rows
CREATE TABLE cost_entries (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    session_date      TEXT NOT NULL,
    agent             TEXT,
    model             TEXT,
    input_tokens      INTEGER,
    output_tokens     INTEGER,
    cache_read_tokens INTEGER,
    total_cost_usd    REAL,
    notes             TEXT,
    recorded_at       TEXT DEFAULT (datetime('now'))
);

-- devlogs/<user>.md sections
CREATE TABLE devlog_entries (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    author        TEXT NOT NULL,     -- filename stem (e.g. nikhilsoman, agy)
    entry_date    TEXT NOT NULL,     -- YYYY-MM-DD from ## header
    session_title TEXT,              -- text after "— Session: " if present
    body          TEXT NOT NULL,     -- full markdown body of the entry block
    recorded_at   TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_devlog_author ON devlog_entries(author);
CREATE INDEX IF NOT EXISTS idx_devlog_date   ON devlog_entries(entry_date);
```

**`todo.md` does not get a new table.** Stories are already in state.db. Migrate syncs back any HTML-comment metadata hand-added directly to `todo.md` (`<!-- gh:#79 -->`, `<!-- priority:next -->`) that was never written to the DB.

---

## `synlynk migrate` Command

```
synlynk migrate [--dry-run] [--recover] [--setup-dr]
```

### Normal run (8 steps)

1. **Guard:** check `.synlynk/.synlynk_migrated` — print "already migrated" and exit if present
2. **Import flat files → state.db:**
   - `todo.md` → sync `gh_issue`, priority tags from HTML comments into `stories` rows (no new rows)
   - `memory.md` → parse `##` sections → insert rows into `memory_entries`
   - `roadmap.md` → parse release blocks → insert into `roadmap_arcs` + `roadmap_phases`
   - `costs.md` → parse data rows → insert into `cost_entries`
   - `devlogs/<user>.md` → parse `## YYYY-MM-DD` blocks, author from filename → insert into `devlog_entries`
3. **Copy:** `project-docs/` → `.synlynk/project-docs/` (full recursive copy)
4. **DR mirror:** if `dr_sync_path` in `.synlynk/config.json` and path exists → copy to `<dr_sync_path>/project-docs/`
5. **Untrack:** `git rm --cached project-docs/ -r`
6. **Gitignore:** append `project-docs/` to `.gitignore`
7. **Sentinel:** write `.synlynk/.synlynk_migrated` (content: ISO timestamp)
8. **Commit:** `git commit -m "chore: synlynk migrate — project-docs moved to .synlynk, state.db is now source of truth"`

### `--dry-run`

Runs steps 1–2 only. Prints a summary table:

```
Would import:
  memory.md       → 12 sections  → memory_entries
  roadmap.md      → 3 arcs, 18 phases → roadmap_arcs + roadmap_phases
  costs.md        → 47 rows      → cost_entries
  devlogs/        → 94 entries (3 authors) → devlog_entries
  todo.md         → 6 stories with gh_issue metadata to sync
No files moved. No git changes.
```

### `--recover`

Re-runs step 2 only, reading from `.synlynk/project-docs/` instead of `project-docs/`. Skips all git steps. Used when state.db is lost or corrupted. Prints count of rows re-imported per table.

### `--setup-dr`

Prompts: `DR sync folder path (e.g. ~/Library/Mobile Documents/com~apple~CloudDocs/synlynk):` Validates the path exists. Writes `dr_sync_path` to `.synlynk/config.json`. Prints confirmation. Does not trigger a sync immediately — next write-through will pick it up.

---

## Write-Through Hooks

All write-through functions are gated on `_is_migrated()` (`os.path.exists(".synlynk/.synlynk_migrated")`). Before migration: no-op. After migration: write to `.synlynk/project-docs/` (and DR path if set).

| DB write | Flat file updated | Hook location |
|---|---|---|
| `cmd_story_create()` / story status update | `.synlynk/project-docs/todo.md` | `_generate_todo_md()` — redirect output path post-migration |
| `cmd_memory_add(section, body, author)` | `.synlynk/project-docs/memory.md` | new function; regenerates full file from `memory_entries` |
| `update_costs()` | `.synlynk/project-docs/costs.md` | append new row after DB insert |
| `cmd_devlog_append(author, date, title, body)` | `.synlynk/project-docs/devlogs/<author>.md` | new function; appends entry block to flat file |
| roadmap arc/phase write | `.synlynk/project-docs/roadmap.md` | regenerates full file from `roadmap_arcs` + `roadmap_phases` |

**DR helper:** `_dr_sync(relative_path)` — copies `.synlynk/project-docs/<relative_path>` to `<dr_sync_path>/project-docs/<relative_path>`. Called at the end of every write-through function. Silently skips if `dr_sync_path` not set or path not reachable (no crash, no warning — DR is best-effort).

---

## `generate_context()` Switch

```python
def _is_migrated() -> bool:
    return os.path.exists(".synlynk/.synlynk_migrated")

def generate_context(...):
    if _is_migrated():
        return _generate_context_from_db(...)
    return _generate_context_from_files(...)   # current behavior, unchanged
```

`_generate_context_from_db()` reads:
- **Top open story** — `SELECT title FROM stories WHERE status='open' ORDER BY created_at LIMIT 1`
- **Recent devlog entries** — `SELECT author, entry_date, session_title, body FROM devlog_entries ORDER BY entry_date DESC LIMIT 5`
- **Active memory sections** — `SELECT section, body FROM memory_entries ORDER BY updated_at DESC`

Output shape is identical to the current flat-file path — no downstream breakage to `exec`, `status`, or `checkpoint`.

---

## DR Sync — Phase A (this story)

- User-configured local folder path (`dr_sync_path` in `.synlynk/config.json`)
- Designed for cloud-synced local folders: iCloud Drive (`~/Library/Mobile Documents/com~apple~CloudDocs/`), Google Drive desktop, OneDrive desktop
- OS handles the upload — no OAuth, no API keys, no new dependencies
- `synlynk migrate --setup-dr` sets the path interactively

**Phase B (future BS story):** Native cloud APIs (Google Drive API, OneDrive API, iCloud CloudKit). OAuth flows, token storage, per-provider implementation. Out of scope for this story.

---

## Parsing Rules

### `memory.md`
- Split on `## <section header>` lines
- Each block: `section` = header text (stripped of `##`), `body` = everything until next `##` or EOF
- Extract `[@username]` pattern from body → `author`

### `roadmap.md`
- Split on lines matching `## v\d+\.\d+` or `### v\d+` → one `roadmap_arcs` row each
- Sub-bullets / table rows within each arc → `roadmap_phases` rows
- Status inferred from keywords: `✅` or `Shipped` → `shipped`; `🚧` or `In Progress` → `in_progress`; else `planned`

### `costs.md`
- Skip header rows and separator lines
- Parse pipe-delimited table rows → `cost_entries`
- Skip rows where all numeric fields are empty or `~` prefix (estimates still imported, `~` stripped)

### `devlogs/<user>.md`
- Author = filename stem (`nikhilsoman.md` → `nikhilsoman`)
- Split on `## YYYY-MM-DD` lines (regex: `^## (\d{4}-\d{2}-\d{2})`)
- Session title = text after ` — ` on the same line if present
- Body = everything until next `## YYYY-MM-DD` or EOF

---

## Error Handling

- **Partial import failure:** if any parser raises, print the error with file name and line number, skip that file, continue with others. Never abort mid-migration on a parse error.
- **Git rm failure:** if `git rm --cached` fails (e.g. files not tracked), log warning, continue — files may already be untracked.
- **DR path unreachable:** silent skip — DR is best-effort, never blocks a write.
- **Already migrated:** `--recover` can be run at any time; normal `migrate` exits early with a clear message pointing to `--recover`.

---

## Testing

- `test_migrate_dry_run_imports_nothing` — `--dry-run` leaves state.db and filesystem unchanged
- `test_migrate_imports_memory_sections` — correct row count and content after import
- `test_migrate_imports_devlog_entries` — author, date, title, body parsed correctly for both devlog formats
- `test_migrate_imports_cost_rows` — numeric fields parsed, `~` prefix stripped
- `test_migrate_imports_roadmap_arcs_and_phases` — arc version + status inferred correctly
- `test_migrate_git_rm_called` — `git rm --cached` invoked with correct args (mock subprocess)
- `test_migrate_gitignore_updated` — `project-docs/` appended to `.gitignore`
- `test_migrate_sentinel_written` — `.synlynk/.synlynk_migrated` exists after run
- `test_migrate_copies_to_synlynk_project_docs` — flat files present at new location
- `test_migrate_dr_sync_copies_files` — files appear at `dr_sync_path` when configured
- `test_migrate_dr_sync_silent_skip_if_unreachable` — no crash when DR path missing
- `test_migrate_recover_reimports_from_backup` — after DB delete, `--recover` restores rows
- `test_migrate_idempotent_on_rerun` — second normal run exits early, no duplicate rows
- `test_is_migrated_false_before_sentinel` — `_is_migrated()` returns False before run
- `test_is_migrated_true_after_sentinel` — `_is_migrated()` returns True after run
- `test_generate_context_switches_to_db_post_migration` — `_generate_context_from_db` called when migrated
- `test_write_through_todo_updates_synlynk_path` — story create writes to `.synlynk/project-docs/todo.md`
- `test_write_through_memory_updates_flat_file` — `cmd_memory_add` updates memory.md
- `test_write_through_devlog_appends_entry` — `cmd_devlog_append` appends to correct devlog file
- `test_write_through_costs_appends_row` — `update_costs` appends to costs.md
- `test_write_through_noop_before_migration` — all write-through functions no-op when not migrated
