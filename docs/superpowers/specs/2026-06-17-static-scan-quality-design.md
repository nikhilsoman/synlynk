# Static Scan Quality — Design Spec
**Version:** v0.7.0  
**Date:** 2026-06-17  
**Status:** Approved for implementation

---

## Goal

`generate_context()` currently reads only `project-docs/` (todo, roadmap, memory, devlog). It has zero visibility into the source code of the repo it is operating on. This means every agent session starts blind to the structural, boundary, vocabulary, and change signals that are the most durable facts about any codebase.

Static Scan Quality adds a language-agnostic source scan that surfaces those signals into every `synlynk exec` session — without AI calls, without build tools, and without breaking the single-file stdlib-only constraint.

---

## Scope

Works on arbitrary repos: any language, any scale (single repo, monorepo, multi-repo), any industry or domain. synlynk is a general harness; the scan must be general too.

Signal priority (A→D):
- **A — Structural:** what exists (modules, public symbols)
- **B — Dependency/boundary:** how things connect (import graph surface, module groupings)
- **C — Vocabulary/domain:** naming conventions, domain terms
- **D — Change surface:** what is in motion (git activity)

v0.7.0 implements A fully, uses D as a prioritization signal, and surfaces B/C implicitly through symbol naming.

---

## Architecture

Three new capabilities in `bin/synlynk.py`, two new storage locations:

```
synlynk exec
  → generate_context()
      → _check_scan_cache()        # compare git rev-parse HEAD to scan-meta.json
          → _scan_source_skeleton() # if HEAD changed or no cache
      → inject ## Source Architecture into context.md

synlynk scan --deep
  → _scan_full_repo()
      → _extract_symbols() per file
      → write source_symbols table in state.db
      → materialize project-docs/source-map.md from DB
      → update scan-meta.json
```

### Storage

| Artifact | Location | Purpose |
|---|---|---|
| `scan-meta.json` | `.synlynk/scan-meta.json` | Hot skeleton cache — HEAD SHA + top-15 file skeleton |
| `source_symbols` | `state.db` (SQLite) | Full structured record, queryable, Tokq-sync-ready |
| `source-map.md` | `project-docs/source-map.md` | Git-versioned materialized export for human/agent reference |

**Dual storage rationale:** `state.db` is the authoritative structured store (queryable, future Tokq bridge sync target). `source-map.md` is a materialized export — any collaborator (human or agent) who clones the repo gets the last deep scan without running any tooling. Same data, two surfaces. `scan-meta.json` is the hot cache that avoids a DB query on every `exec`.

---

## File Prioritization

The skeleton surfaces the top 15 files by importance score. Score per file:

| Signal | Weight |
|---|---|
| Matches known entry-point names | +3 |
| Appears in last 50 commits (`git log --name-only --pretty=format: -50`) | +1 per appearance |
| Depth penalty | −1 per directory level beyond 2 |

Entry point names: `main.py`, `app.py`, `server.py`, `index.js`, `index.ts`, `main.go`, `lib.rs`, `main.rs`, `app.rb`, `manage.py`, `wsgi.py`, `asgi.py`, `__init__.py` at root, `cmd/main.go`.

Top 15 by score go into the skeleton. Ties broken by git activity descending. Hard cap at 15 to keep `## Source Architecture` under ~100 lines in `context.md`.

**Skip dirs** (extends existing `_SCAN_SKIP_DIRS`):
`node_modules`, `.git`, `__pycache__`, `dist`, `build`, `vendor`, `.venv`, `venv`, `env`, `.worktrees`, `coverage`, `.nyc_output`, `target`, `.next`, `out`, `tmp`.

---

## Symbol Extraction

Language detected by file extension. Regex applied line-by-line, reading at most 300 lines per file.

| Language | Extensions | Patterns |
|---|---|---|
| Python | `.py` | `^def `, `^async def `, `^class ` at indent 0; `^[A-Z_]{2,}\s*=` for constants |
| JavaScript | `.js` `.mjs` `.cjs` | `export (function\|class\|const\|default)`, top-level `function `, `class ` |
| TypeScript | `.ts` `.tsx` | JS patterns + `export interface`, `export type`, `export enum` |
| Go | `.go` | `^func `, `^type .+ struct`, `^type .+ interface` |
| Rust | `.rs` | `^pub fn `, `^pub struct `, `^pub trait `, `^pub enum `, `^pub type ` |
| Ruby | `.rb` | `^def `, `^class `, `^module ` at indent 0 |
| Java | `.java` | `(public\|protected) (class\|interface\|enum)`, `(public\|protected) \w+ \w+\(` |
| Kotlin | `.kt` | `^fun `, `^class `, `^object `, `^interface ` |
| Shell | `.sh` | `^\w+\(\)` (function definitions) |
| Generic | any other | no symbol extraction — file listed by name only |

**Symbol types** recorded: `function`, `async_function`, `class`, `interface`, `struct`, `trait`, `enum`, `type`, `constant`, `module`.

**Symbol output per file:** skeleton shows top 8 symbols (by line order = declaration order ≈ importance). `source-map.md` and DB show all extracted symbols with line numbers.

---

## SQLite Schema

New table in `state.db`:

```sql
CREATE TABLE IF NOT EXISTS source_symbols (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    head_sha    TEXT NOT NULL,
    file        TEXT NOT NULL,
    language    TEXT NOT NULL,
    symbol      TEXT NOT NULL,
    symbol_type TEXT NOT NULL,
    line        INTEGER,
    scanned_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_source_symbols_head ON source_symbols(head_sha);
CREATE INDEX IF NOT EXISTS idx_source_symbols_file ON source_symbols(file);
```

On every deep scan: `DELETE FROM source_symbols WHERE head_sha != ?` (current SHA), then bulk insert. Single-SHA retention — history is git's job.

---

## `scan-meta.json` Schema

```json
{
  "schema_version": 1,
  "head_sha": "a3f2b1c",
  "scanned_at": "2026-06-17 21:14:00",
  "file_count": 15,
  "skeleton": [
    {
      "file": "src/auth/service.ts",
      "language": "typescript",
      "symbols": ["AuthService", "verifyToken()", "hashPassword()", "createSession()"]
    }
  ]
}
```

---

## Context Injection Format

`## Source Architecture` section injected in `context.md` between `## Active Tasks` and `## Roadmap (active)`:

```markdown
## Source Architecture
_Scanned: 2026-06-17 21:14 · HEAD: a3f2b1c · 15 files · cache hit_

### src/  [typescript · 3 files]
`src/index.ts` — AuthService, UserRouter, app
`src/auth/service.ts` — AuthService, verifyToken(), hashPassword(), createSession()
`src/auth/middleware.ts` — requireAuth(), optionalAuth(), AdminGuard

### cmd/  [go · 2 files]
`cmd/main.go` — main(), initDB(), startServer()
`cmd/migrate.go` — RunMigrations(), rollbackMigration()

### [root]  [python · 1 file]
`manage.py` — main()

> 9 more files in source-map.md — run `synlynk scan --deep` to refresh
---
```

Files grouped by directory. Language shown as metadata per group. Overflow line always present when full repo exceeds skeleton cap.

Cache status in the header line: `cache hit` (skeleton read from `scan-meta.json`) vs `refreshed` (re-scanned because HEAD changed).

---

## `source-map.md` Format

Full symbol list per file, no cap, grouped by directory. Written to `project-docs/source-map.md` by `synlynk scan --deep` — the agent or user decides whether to commit it. Committing is recommended so collaborators get it on clone:

```markdown
# Source Map
_Generated: 2026-06-17 21:14 · HEAD: a3f2b1c · 47 files_

## src/billing/  [typescript · 4 files]
`src/billing/service.ts` · 7 symbols
  BillingService [class:12], createInvoice() [function:34],
  voidInvoice() [function:58], applyDiscount() [function:79],
  calculateTax() [function:101], syncStripe() [function:134],
  handleWebhook() [function:167]

`src/billing/models.ts` · 4 symbols
  Invoice [interface:1], LineItem [interface:18],
  Discount [interface:32], PaymentMethod [interface:47]
...
```

---

## CLI Surface

```
synlynk scan              # force-refresh skeleton (runs even if HEAD unchanged)
synlynk scan --deep       # full tree walk → state.db + project-docs/source-map.md
synlynk scan --status     # show cache age, HEAD SHA, file/symbol counts
```

**`synlynk scan --status` output:**
```
Source scan status:
  Skeleton:    15 files · cached · HEAD a3f2b1c · 4 hours ago
  source-map:  47 files · 312 symbols · project-docs/source-map.md · 4 hours ago
  Next refresh: on next commit (HEAD change)
```

`synlynk scan --deep` does not require a HEAD change — it always re-scans. Use after large merges or initial repo setup.

---

## Passive Cache Invalidation

`generate_context()` is called on every `exec` and every `checkpoint`. The invalidation check is added there:

```python
def _check_scan_cache() -> list:
    """Returns skeleton from cache if HEAD unchanged, else re-scans."""
    current_sha = _git_head_sha()
    meta = _load_scan_meta()
    if meta and meta.get("head_sha") == current_sha:
        return meta["skeleton"]
    skeleton = _scan_source_skeleton()
    _save_scan_meta(current_sha, skeleton)
    return skeleton
```

`_git_head_sha()` runs `git rev-parse HEAD` — fast, always available. If the repo has no commits yet, returns `None` and the scan is skipped gracefully.

---

## Error Handling

- **No git history:** skip scan, omit `## Source Architecture` from context silently
- **File read error:** skip that file, continue scan
- **DB unavailable:** write `scan-meta.json` skeleton only; omit `source_symbols` insert; log warning
- **Scan exceeds 2 seconds:** abort, use whatever skeleton has been built so far, emit `⚠ scan truncated` in status line
- **Empty repo / no source files:** omit `## Source Architecture` section entirely

---

## Testing

New test file: `tests/test_static_scan.py`

Key test cases:
- `_extract_symbols()` for each supported language against fixture snippets
- `_scan_source_skeleton()` returns ≤15 files
- `_check_scan_cache()` returns cached skeleton when HEAD unchanged
- `_check_scan_cache()` re-scans when HEAD changes
- `generate_context()` includes `## Source Architecture` when source files present
- `generate_context()` omits `## Source Architecture` gracefully when repo has no commits
- `synlynk scan --deep` writes `source-map.md` and populates `source_symbols` table
- `synlynk scan --status` prints expected fields

---

## What This Does Not Do (v0.7.0)

- No cross-file import graph (B signal) — file grouping by directory is the only boundary signal
- No semantic/vocabulary extraction beyond symbol names (C signal)
- No `synlynk scan --query` (DB query surface) — rows are in the DB but no query CLI yet
- No Tokq sync of `source_symbols` — table is designed for it, wiring is future work
- No incremental scan (changed files only) — full rescan on HEAD change
