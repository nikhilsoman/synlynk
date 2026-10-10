# Design Spec: Vizor Workspace-Scoped Slug Routing & Daemon Contract

**Date:** 2026-09-30  
**Status:** Draft (Approved in Principle by Synlynk Decision Panel)  
**Authors:** AGY (Lead), Claude, Codex, Grok  
**Decision Record:** [`project-docs/decisions/2026-09-30-synlynk-v2-architecture-vizor-generaliza.md`](file:///Users/nikhilsoman/dev/synlynk/project-docs/decisions/2026-09-30-synlynk-v2-architecture-vizor-generaliza.md)  
**Sub-Project:** 1 of 5 (Synlynk V2 Platform Architecture)

---

## 1. Executive Summary & Problem Statement

Synlynk Vizor is designed as a machine-level, zero-SaaS, multi-workspace visualization and governance control plane. Currently, Vizor serves cached static HTML pages per workspace under `/w/<slug>/<page>.html`, but all dynamic API interactions (such as the GOVERNS Board cards, status updates, and stage progressions) hit global, unscoped endpoints like `/api/board` and `/api/board/stage`.

### The Core Failure Modes
1. **Unscoped Dynamic Endpoints:**
   In [`synlynk/viz.py`](file:///Users/nikhilsoman/dev/synlynk/synlynk/viz.py#L9470-L9478), `generate_board_html()` injects client-side JavaScript that calls `fetch('/api/board')`. This request carries no workspace identity.
2. **Daemon Process CWD Coupling (`CWD = /`):**
   The persistent Vizor daemon ([`synlynk/vizor_daemon.py`](file:///Users/nikhilsoman/dev/synlynk/synlynk/vizor_daemon.py)) is supervised by `launchd` or `systemd`, running with working directory `/`. When `GET /api/board` hits `VizorHandler`, it delegates to `board_data()` with default `repo_path="."`. Looking for `.synlynk/config.json` in `/` raises `FileNotFoundError`, causing `/api/board` to return empty card lists (`cards: []`) for every workspace.
3. **Cross-Tenant Contamination & Enterprise Impasse:**
   Because dynamic APIs do not resolve the target workspace, any write operation (such as updating a story's status or stage) either fails or mutates the wrong repository's `state.db`. Furthermore, this unscoped model cannot transition to Synlynk Team & Enterprise (`synlynk.com/{org_or_user}/{workspace}/...`).

### Goal of This Specification
Establish a strict, hierarchical, URL-namespaced routing engine (`/w/<slug>/api/...`) where the server-side daemon alone resolves `<slug>` to an authorized `(repo_path, canonical_path)` pair via `state_registry`. Eliminate all dependencies on process `os.getcwd()`, enforce zero client-supplied paths (preventing path traversal), and ensure all Vizor views use relative path fetching.

---

## 2. Architectural Principles & Invariants

1. **Strict Server-Side Registry Resolution (Security Invariant):**
   The daemon must resolve the target workspace exclusively through [`synlynk/state_registry.py`](file:///Users/nikhilsoman/dev/synlynk/synlynk/state_registry.py). A client may never supply a filesystem path (e.g., `?repo_path=/...` or `?db_path=/...`). Any request for an unregistered slug returns an immediate HTTP 404.
2. **Relative Path Portability (Local $\rightarrow$ Cloud Invariant):**
   All client-side JavaScript in Vizor pages must use relative URLs (`api/board` instead of `/api/board`).
   * Local: `http://localhost:8721/w/rxcc/board.html` $\rightarrow$ browser requests `/w/rxcc/api/board`.
   * Cloud: `https://synlynk.com/acme/rxcc/board.html` $\rightarrow$ browser requests `/acme/rxcc/api/board`.
   No JavaScript bundle or HTML template requires hardcoded domain or workspace prefixes.
3. **Immutable `WorkspaceContext` Injection:**
   Handlers must never invoke `os.getcwd()` or call database helpers with default `.` paths. Every request within a workspace scope receives an explicit, validated `WorkspaceContext` data structure containing the verified `slug`, `repo_path`, and `db_path`.
4. **Concurrent Multi-Workspace Isolation:**
   Concurrent HTTP requests to `/w/synlynk/api/...` and `/w/rxcc/api/...` must execute independently with zero mutex contention or shared mutable global state.

---

## 3. URL Route Hierarchy

### Route Namespace Definition

| Pattern | Type | Handler | Purpose |
| :--- | :--- | :--- | :--- |
| `/` | Static HTML | `_workspace_index_html()` | Machine Workspace Hub (list of registered repos) |
| `/w/<slug>/` or `/w/<slug>/index.html` | Static HTML | `SimpleHTTPRequestHandler` | Workspace Overview Dashboard |
| `/w/<slug>/<view>.html` | Static HTML | `SimpleHTTPRequestHandler` | Individual Workspace View (`board.html`, `gantt.html`, etc.) |
| `/w/<slug>/api/board` | Dynamic JSON | `handle_scoped_board_get()` | Workspace-scoped GOVERNS Board cards & filters |
| `/w/<slug>/api/board/status` | Dynamic JSON (POST) | `handle_scoped_board_status()` | Update story status in workspace `state.db` |
| `/w/<slug>/api/board/stage` | Dynamic JSON (POST) | `handle_scoped_board_stage()` | Update story GOVERNS stage in workspace `state.db` |
| `/w/<slug>/api/note` | Dynamic JSON (POST) | `handle_scoped_note()` | Save note attached to story/task in workspace |
| `/w/<slug>/api/meta` | Dynamic JSON | `handle_scoped_meta()` | Workspace identity, scan status, and telemetry summary |
| `/api/...` (unscoped) | Redirect / Shim | `handle_legacy_api_fallback()` | 308 Permanent Redirect or 400 Bad Request with guidance |

---

## 4. Server-Side Routing & WorkspaceContext Engine

### 4.1 Data Model
In [`synlynk/vizor_daemon.py`](file:///Users/nikhilsoman/dev/synlynk/synlynk/vizor_daemon.py):

```python
@dataclasses.dataclass(frozen=True)
class WorkspaceContext:
    slug: str
    repo_path: Path
    db_path: Path
```

### 4.2 Slug Resolver Function
```python
def resolve_workspace_context(slug: str) -> Optional[WorkspaceContext]:
    """Look up slug in machine state_registry and return verified WorkspaceContext.
    
    Rejects unregistered slugs or missing filesystem targets.
    Never accepts client-provided filesystem paths.
    """
    from synlynk.state_registry import _read_unlocked, registry_path
    
    if not slug or not re.match(r"^[a-zA-Z0-9_-]+$", slug):
        return None
        
    p = registry_path()
    if not p.exists():
        return None
        
    try:
        data = _read_unlocked(p)
    except Exception:
        return None
        
    entry = data.get("products", {}).get(slug)
    if not isinstance(entry, dict):
        return None
        
    repo_path = entry.get("repo_path")
    db_path = entry.get("canonical_path")
    if not repo_path or not db_path:
        return None
        
    repo_p = Path(repo_path)
    db_p = Path(db_path)
    if not repo_p.is_dir() or not db_p.is_file():
        return None
        
    return WorkspaceContext(slug=slug, repo_path=repo_p, db_path=db_p)
```

### 4.3 Dispatching Dynamic Scoped Routes
In `WorkspaceRoutingHandler`:

1. Parse path using `urllib.parse.urlparse`.
2. If `path.startswith("/w/")`:
   * Extract `slug` and `subpath`:
     `/w/<slug>/api/<rest>` $\rightarrow$ `(slug, "/api/<rest>")`.
   * Resolve `ctx = resolve_workspace_context(slug)`. If `ctx is None`, respond with `404 Not Found: Unknown or unregistered workspace`.
   * If `subpath.startswith("/api/")`:
     Route directly to the scoped API dispatcher, passing `ctx` explicitly.
   * Else (Static View request):
     Rewrite path to `/<slug>/<view>` and allow `SimpleHTTPRequestHandler` to serve the file from `CACHE_ROOT`.

---

## 5. Dynamic Scoped API Implementations

### 5.1 `GET /w/<slug>/api/board`
Modifies [`synlynk/board.py`](file:///Users/nikhilsoman/dev/synlynk/synlynk/board.py) to accept an explicit `WorkspaceContext`:

```python
def board_data_for_context(
    ctx: WorkspaceContext,
    *,
    repo_id: Optional[str] = None,
    type_id: Optional[str] = None,
    goal_id: Optional[str] = None,
) -> dict:
    """Return product-scoped board cards using explicit db_path and repo_path."""
    conn = _get_db(db_path=str(ctx.db_path), read_only=True, migrate=False)
    conn.row_factory = sqlite3.Row
    try:
        # Load stories and filters directly from ctx.db_path
        ...
        return {
            "identity_slug": ctx.slug,
            "cards": cards,
            "filters": {
                "repos": sorted(list(repos)),
                "types": sorted(list(types)),
                "goals": sorted(list(goals)),
            },
            "statuses": list(BOARD_STATUSES),
            "governs_stages": list(GOVERNS_STAGES),
        }
    finally:
        conn.close()
```

### 5.2 `POST /w/<slug>/api/board/status` and `POST /w/<slug>/api/board/stage`
Mutations must be applied strictly to `ctx.db_path` using transactional SQLite connection:
* Authenticate request using local Ed25519 token header (`window.vizorAuthHeaders()`).
* Execute parameterized SQL update on `ctx.db_path`.
* Return JSON response `{"ok": true, "story_id": id, "new_value": value}`.
* Never touch global process state or alter `os.getcwd()`.

---

## 6. Client-Side Template Modifications

In [`synlynk/viz.py`](file:///Users/nikhilsoman/dev/synlynk/synlynk/viz.py#L9470-L9495), all fetch calls inside `generate_board_html()` are updated from absolute `/api/...` to relative `api/...`:

```javascript
// BEFORE (Broken):
const r = await fetch('/api/board?' + q.toString());
const r = await fetch('/api/board/status', { ... });
const r = await fetch('/api/board/stage', { ... });

// AFTER (Fully Scoped & Relative):
const r = await fetch('api/board?' + q.toString());
const r = await fetch('api/board/status', { ... });
const r = await fetch('api/board/stage', { ... });
```

When the user visits `http://localhost:8721/w/rxcc/board.html`, the browser evaluates `'api/board'` as `http://localhost:8721/w/rxcc/api/board`.

---

## 7. Backward Compatibility & Legacy Shims

To avoid breaking any existing headless integrations or bookmarked tabs:
1. Requests to `/api/board` without `/w/<slug>`:
   * Inspect referer header for `/w/<slug>/`. If present, extract `slug` and issue `307 Temporary Redirect` to `/w/<slug>/api/board`.
   * If referer is absent: check if exactly one active workspace exists in `state_registry`. If single-workspace, redirect to that workspace's API.
   * If multiple workspaces exist and no referer is present: return HTTP 400 Bad Request with JSON:
     ```json
     {
       "error": "unscoped_request",
       "message": "Vizor APIs require workspace scoping. Use /w/<slug>/api/board"
     }
     ```

---

## 8. Verification & Automated Test Matrix

A comprehensive automated test suite will be created in `tests/test_vizor_scoped_routing.py`:

| Test Case | Scenario | Expected Outcome |
| :--- | :--- | :--- |
| `test_resolve_workspace_context_valid` | Lookup registered slug `rxcc` | Returns `WorkspaceContext` with valid `repo_path` and `db_path` |
| `test_resolve_workspace_context_invalid` | Lookup unregistered slug `nonexistent` | Returns `None` |
| `test_reject_path_traversal` | Request `/w/../../etc/passwd` or `/w/slug?db_path=...` | HTTP 404 or 400; path parameter ignored |
| `test_board_api_scoped_rxcc` | `GET /w/rxcc/api/board` | HTTP 200, `identity_slug == 'rxcc'`, cards count matches `rxcc/state.db` |
| `test_board_api_scoped_synlynk` | `GET /w/synlynk/api/board` | HTTP 200, `identity_slug == 'synlynk'`, cards count matches `synlynk/state.db` |
| `test_concurrent_multi_workspace_serving`| Concurrent async fetches to `/w/rxcc/api/board` and `/w/synlynk/api/board` | Both succeed with independent card lists and zero cross-talk |
| `test_board_stage_mutation_scoped` | `POST /w/rxcc/api/board/stage` | Mutates only `rxcc/state.db`; `synlynk/state.db` untouched |
| `test_daemon_cwd_root_isolation` | Run handler test with `os.chdir('/')` | Handler resolves paths from `WorkspaceContext` without raising `FileNotFoundError` |
