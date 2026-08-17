# Workspace Context Write-Through: Fixing #936

**Status:** approved, ready for planning
**Scope:** GitHub issue #936 — "Workspace context divergence: state.db silently disagrees with project-docs/* markdown (devlogs, decisions, more TBD)"
**Roadmap link:** `docs/strategy/2026-08-15-two-imperatives-roadmap.md`, Definition of Done — "Workspace-context-governance's 11 action items are either shipped or explicitly deferred with a reason, and issue #936 is closed." This spec closes #936 directly; it does not touch the 11 governance action items (already tracked separately, several already shipped via PR #988).

## Background

`docs/strategy/2026-08-10-roadmap-todo-governance.md` established the precedent that `state.db`/SQLite is authoritative for structured project state, with markdown files (`roadmap.md`, `todo.md`) as generated projections — never hand-edited, regenerated from DB rows. Issue #936 identified that this precedent was never extended to two other structured, per-event data types: **devlog entries** and **decision records**. Both are currently written by hand-rolled flat-file I/O with no DB backing at all, silently drifting from whatever `state.db` may separately believe about the same events.

A working example of the correct pattern already exists in `synlynk/db.py`: `cmd_memory_add()` writes to `state.db` first, then conditionally regenerates `memory.md` via `_write_memory_md()` (gated on `_is_migrated()`), then syncs via `_dr_sync()`. `cmd_devlog_append()` follows the identical shape but is currently orphaned — nothing calls it for the live devlog-append path (`checkpoint()` bypasses it entirely with direct file I/O).

## Decisions (locked before this spec was written)

1. **Authority model:** `state.db` is authoritative for devlogs and decisions, same as roadmap/todo. Markdown becomes a generated view.
2. **Sweep scope:** full audit of all 5 `_docs_dir()`-calling files in this same spec/plan — `synlynk/__init__.py`, `synlynk/cli.py`, `synlynk/db.py`, `synlynk/doctor.py`, `synlynk/sentinel.py` — not deferred to a fast-follow.
3. **Fix approach:** targeted (Approach A) — mirror the existing good pattern (`cmd_devlog_append`/`cmd_memory_add`/`_write_memory_md`) exactly, rather than building a new shared path-resolution helper or a generic write-through abstraction. Only two write-paths are in scope today (devlogs, decisions); a generic abstraction is premature (YAGNI) when copying the proven pattern once suffices.

## File-by-file classification

| File | Finding | Fix |
|---|---|---|
| `synlynk/__init__.py` | `checkpoint()` (lines ~2924-2965) appends to devlog markdown via direct `open(devlog_path, "a")`, never touches `state.db`. `_docs_dir()` itself (line 1526) is migration-unaware by design — it's the pre-migration fallback, correctly used only when `_is_migrated()` is false elsewhere in the codebase. | Rewire `checkpoint()` to call `cmd_devlog_append()` instead of direct file I/O. |
| `synlynk/db.py` | Already has the correct pattern (`cmd_memory_add`, `_write_memory_md`, `cmd_devlog_append`). ~18 other `_docs_dir()`/`_synlynk_project_docs_dir()` call sites already correctly branch on `_is_migrated()`. | No fix needed to existing code. Add `cmd_decision_record()` and `_write_decision_record_md()` here, alongside their siblings. |
| `synlynk/team.py` | `cmd_decide(..., record=True)` → `_write_decision_record()` (lines ~489-606) writes decisions straight to `os.path.join(_docs_dir(), "decisions")` — no DB backing at all (no `decisions` table exists), no `_is_migrated()` branch anywhere in the file. `_build_team_digest()` also reads `devlogs_dir` via raw `_docs_dir()` (read-only, migration-unaware — would silently read the stale pre-migration path after migration, showing incomplete/stale team status). | `cmd_decide()` calls new `cmd_decision_record()` (in `db.py`) instead of the local `_write_decision_record()`. The MD/JSON-regeneration half moves to `db.py` as `_write_decision_record_md()`. `_build_team_digest()`'s devlogs_dir read gets the same `_is_migrated()` branch as the read-only fixes below. |
| `synlynk/doctor.py` | `_hc_docs_dir()` (line 98) is a read-only health check — calls raw `_docs_dir()`, migration-unaware. Post-migration, could report a false "ok" (checking the stale pre-migration dir which may still have leftover files) or a false "warn" (missing files that actually exist at the migrated path). | Branch on `_is_migrated()` before resolving `docs`. |
| `synlynk/sentinel.py` | Defines its own **private, duplicate** `_docs_dir()` (line 24) instead of importing the canonical one — independent drift risk. Its one call site, `_check_costs_freshness()`, is read-only (staleness warning) but migration-unaware, so post-migration it would check the wrong `costs.md` path and could silently suppress a real staleness warning. | Delete the private duplicate; import and branch on `_is_migrated()`/`_synlynk_project_docs_dir()` from `synlynk/__init__.py`, same as doctor.py. |
| `synlynk/cli.py` | Line 1055 is a comment referencing `_docs_dir()`, not an actual call site (`_update_config({"project_docs_dir": args.docs_dir})` is the real code, unrelated to migration state). | No fix needed. Confirmed false positive. |

## Data model: new `decisions` table

```sql
CREATE TABLE IF NOT EXISTS decisions (
    decision_id TEXT PRIMARY KEY,
    topic TEXT NOT NULL,
    date TEXT NOT NULL,
    panel TEXT NOT NULL,        -- JSON array of panel member names
    status TEXT NOT NULL,       -- 'approved' (matches current record shape)
    inputs TEXT NOT NULL,       -- JSON object {member: text}
    synthesis TEXT NOT NULL,
    decision_text TEXT NOT NULL,
    signature TEXT,             -- nullable; matches today's "unsigned" fallback when no identity key
    created_at TEXT NOT NULL
);
```

One row per decision; `panel`/`inputs` stored as JSON rather than normalized into child tables, since decisions are always read as a whole record — nothing in the codebase queries by individual panel member, so normalization would add joins with no consumer. Mirrors how `devlog_entries` already stores structured per-event data.

## Write-through functions

**`cmd_decision_record(decision_id, topic, date, panel, inputs, synthesis, decision_text)`** — new function in `synlynk/db.py`, placed next to `cmd_devlog_append`/`cmd_memory_add`:
1. Computes signature via existing `_sign_capability_rating()` (unsigned fallback + warning print preserved from current behavior).
2. INSERTs into `decisions`, commits.
3. If `_is_migrated()`: calls `_write_decision_record_md(decision_id)` to regenerate the `.md`/`.json` pair at `_synlynk_project_docs_dir()/decisions/`, then `_dr_sync()` on both generated paths.
4. If not migrated: calls the same regeneration logic targeted at `_docs_dir()/decisions/` (mirrors `_write_memory_md`'s existence-check-gated pre-migration behavior).

**`_write_decision_record_md(decision_id)`** — new function in `synlynk/db.py` (moved/renamed from `team.py`'s current `_write_decision_record`): reads the just-inserted row back from `state.db` (not the in-memory dict passed to `cmd_decision_record`) and writes the `.md` + `.json` pair with the same content shape as today's output, plus a generated-file header: `"<!-- generated - source of truth is state.db -->\n"`.

**`checkpoint()`** (`synlynk/__init__.py`): replace the current `open(devlog_path, "a")` block with a call to `cmd_devlog_append(canonical_id, entry_date, body_text)`, passing the same completed-task text `checkpoint()` already formats. No change to *what* text gets written — only *how* it gets persisted (DB row first, file regenerated from DB).

**`cmd_decide(..., record=True)`** (`synlynk/team.py`): replace the call to the old `_write_decision_record()` with `_pkg("cmd_decision_record")(...)`. `team.py` no longer performs direct file I/O for decisions.

## Error handling

Same posture as the existing `cmd_memory_add` pattern: the DB write commits inside its own transaction before any file regeneration is attempted. File regeneration is best-effort — a failure there does not roll back the DB write, since the DB is authoritative and a stale/missing generated file is recoverable drift (re-run `synlynk audit-docs --fix` or equivalent), not data loss. `_write_decision_record_md()` and `cmd_devlog_append`'s existing MD-regeneration path both re-read from the DB row just committed, not the caller's in-memory dict, so the generated file can never diverge from what was actually persisted even if the caller's local variables are stale.

## Testing

- `decisions` table creation is idempotent (`CREATE TABLE IF NOT EXISTS`, safe to call on every `_get_db()`).
- `cmd_decision_record()`: writes a `decisions` row; regenerates `.md`/`.json` when migrated; skips regeneration when not migrated but existence-checks the legacy path (mirrors `cmd_memory_add`'s existing test structure).
- `cmd_decide(..., record=True)`: asserts a `decisions` row now exists post-call, in addition to today's existing file-existence assertions (regression-safe — old behavior preserved, new behavior added).
- `checkpoint()`: existing devlog-append tests continue to pass unchanged (behavior-preserving from the caller's perspective — same text ends up in the same file location). New test asserts a `devlog_entries` DB row now exists after `checkpoint()` runs (previously it did not).
- `_hc_docs_dir()` (doctor.py) and `_check_costs_freshness()` (sentinel.py): one test each under a migrated-fixture (`.synlynk/.synlynk_migrated` marker present), asserting they resolve `_synlynk_project_docs_dir()` rather than the raw pre-migration `_docs_dir()` path. These are the regression tests that would have caught the current bug.
- `sentinel.py`'s private `_docs_dir()` duplicate is deleted; any existing test importing it directly gets updated to import the canonical one from `synlynk/__init__.py`.

## Out of scope

- The 11 action items in `docs/superpowers/specs/2026-08-14-workspace-context-governance-design.md` — tracked separately, not modified by this spec.
- Issue #860 (job self-report status recurrence) — the other unmet Definition-of-Done gate, entirely separate root cause, not addressed here.
- A generic write-through abstraction for future DB-backed markdown views — deferred until a third write-path emerges (YAGNI; two proven copies of the pattern, devlogs and decisions, don't yet justify one).
