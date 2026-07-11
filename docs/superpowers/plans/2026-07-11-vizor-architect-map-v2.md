# Vizor Architect Map v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Vizor's hand-authored tube map with a live, workspace-level "Architect Map" — a force-directed graph of tracked repos (nodes from the workspace config, typed edges from a small JSON file) with a click-to-open side drawer for high-level actions, plus a pinnable IDE-style file-tree sub-view sourced from the existing `source_symbols` DB table.

**Architecture:** All changes live in `synlynk/viz.py` (rendering + data plumbing) and `synlynk/__init__.py` (one new small DB query helper). No new files, no new dependencies — the force-directed layout and file tree are hand-rolled vanilla JS embedded the same way every other Vizor view already embeds its JS (Python string literals). The existing `VizorHandler.do_POST` gets one new route (`/dispatch`) alongside the existing `/note` route, following its exact pattern.

**Tech Stack:** Python 3 stdlib (`sqlite3`, `json`, `http.server`), vanilla JS/SVG in the browser (no CDN, no build step), pytest.

---

## Important Corrections to the Design Spec (read before starting)

The design spec (`docs/superpowers/specs/2026-07-11-vizor-architect-map-v2-design.md`) says nodes
come from `cfg["repos"]` in `.synlynk/config.json`. That's not quite where the data lives:

- `.synlynk/config.json` (per-repo, in the directory Vizor runs from) holds the `vizor` settings
  block (`second_view`, `port`, etc.) — **it does not have a `repos` key today.**
- The actual multi-repo list lives in a **separate** file:
  `~/.synlynk/workspaces/<workspace_name>/config.json`, written by `write_workspace_config()`
  (`synlynk/__init__.py:4659-4684`), with shape `{"workspace_name": ..., "repos": [{"path", "name",
  "stack_labels"}, ...]}`. It's keyed by `workspace_name`, which defaults to `"default"` at every
  existing call site that doesn't pass one explicitly (e.g. `_workspace_config_dir(workspace_name
  or "default")`).
- `.synlynk/config.json` has no field today linking back to which workspace name owns this repo.

Task 1 below adds a `_load_workspace_repos()` helper that defaults to the `"default"` workspace
(matching the rest of the codebase's fallback convention) and gracefully returns `[]` if no
workspace config exists yet — this is the correct, verified data source, not a literal `cfg["repos"]`
lookup on `.synlynk/config.json`.

Also: `generate_tube_html` is renamed to `generate_architect_map_html` (it's an internal function
with exactly one call site plus tests — safe, low-risk rename). The **output filename stays
`tube.html`** — `generate_index_html`'s nav link list (`viz.py:547`) and the `view-frame` iframe
loader both hardcode `"tube.html"`, and renaming the route adds risk for zero functional benefit.
Only the Python function name and the file's internal content change.

---

## File Structure

| File | Responsibility |
|---|---|
| `synlynk/viz.py` | `VIZ_WORKSPACE_MAP_PATH` constant, `_load_workspace_repos()`, `_load_workspace_map()`, `_repo_github_url()`, `_repo_dream_summary()` helpers; `generate_viz_data()` wiring; `generate_architect_map_html()` (renamed + rewritten body); `VizorHandler.do_POST` gets a `/dispatch` route and an `/architect-map/view-pref` route. |
| `synlynk/__init__.py` | One new helper, `_query_repo_file_tree(repo_name=None)`, next to `_scan_full_repo`/`_scan_source_skeleton` (~line 6604), building a nested tree from `source_symbols.file` paths. |
| `tests/test_viz.py` | Updated/renamed tests for the new function name and new data shape; new tests for `_load_workspace_repos`, `_load_workspace_map`, the graph/drawer/tree HTML output, and the two new POST routes. |
| `tests/test_scan.py` (or wherever `_scan_full_repo`/DB helpers are tested today — verify with `grep -rn "_scan_full_repo\|source_symbols" tests/`) | New test for `_query_repo_file_tree`. |
| `CLAUDE.md` | New "Workspace Map Update" conditional protocol paragraph, alongside the existing Blog Post Protocol section. |
| `docs/superpowers/specs/2026-07-03-bs21-vizor-design.md` | Remove/replace the `synlynk viz --setup-tube` references (lines ~164-180, ~292-294) so the design spec stops describing a command that doesn't exist. |

---

### Task 1: Data plumbing — workspace repos, edges, and `generate_viz_data()` wiring

**Files:**
- Modify: `synlynk/viz.py:19-22` (constants), `synlynk/viz.py:82-120` (`generate_viz_data`)
- Test: `tests/test_viz.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_viz.py` (near the top, after `make_test_db`):

```python
def test_load_workspace_repos_missing_returns_empty(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from synlynk.viz import _load_workspace_repos
    assert _load_workspace_repos({}) == []

def test_load_workspace_repos_reads_default_workspace(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    ws_dir = tmp_path / "fake-home" / ".synlynk" / "workspaces" / "default"
    ws_dir.mkdir(parents=True)
    (ws_dir / "config.json").write_text(json.dumps({
        "workspace_name": "default",
        "repos": [{"path": "/repo/a", "name": "repo-a", "stack_labels": ["python"]}],
    }))
    monkeypatch.setenv("HOME", str(tmp_path / "fake-home"))
    from synlynk.viz import _load_workspace_repos
    repos = _load_workspace_repos({})
    assert repos == [{"path": "/repo/a", "name": "repo-a", "stack_labels": ["python"]}]

def test_load_workspace_repos_honors_explicit_workspace_name(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    ws_dir = tmp_path / "fake-home" / ".synlynk" / "workspaces" / "acme"
    ws_dir.mkdir(parents=True)
    (ws_dir / "config.json").write_text(json.dumps({
        "workspace_name": "acme",
        "repos": [{"path": "/repo/b", "name": "repo-b", "stack_labels": []}],
    }))
    monkeypatch.setenv("HOME", str(tmp_path / "fake-home"))
    from synlynk.viz import _load_workspace_repos
    repos = _load_workspace_repos({"workspace_name": "acme"})
    assert repos == [{"path": "/repo/b", "name": "repo-b", "stack_labels": []}]

def test_load_workspace_map_missing_returns_empty_shape(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    from synlynk.viz import _load_workspace_map
    assert _load_workspace_map() == {"edges": [], "edge_types": {}}

def test_load_workspace_map_reads_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    with open(".synlynk/vizor-workspace-map.json", "w") as f:
        json.dump({
            "edges": [{"from": "a", "to": "b", "type": "api-call"}],
            "edge_types": {"api-call": {"label": "API Call", "color": "#0d9e87"}},
        }, f)
    from synlynk.viz import _load_workspace_map
    result = _load_workspace_map()
    assert result["edges"] == [{"from": "a", "to": "b", "type": "api-call"}]
    assert result["edge_types"]["api-call"]["color"] == "#0d9e87"
```

Update `test_generate_viz_data_structure` (currently at `tests/test_viz.py:37-57`): replace
`assert "tube_config" in data` with:

```python
    assert "workspace_map" in data
    assert "repos" in data["workspace"]
```

Search-and-replace every other `"tube_config": None,` fixture literal in `tests/test_viz.py`
(lines 129, 158, 345, 361, 383, 398, 413 per the current file) with `"workspace_map": {"edges": [], "edge_types": {}},`.
Do this with a real editor search/replace, not manually per line — there are 7 occurrences.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_viz.py -k "workspace_repos or workspace_map or viz_data_structure" -v`
Expected: FAIL — `_load_workspace_repos`/`_load_workspace_map` don't exist yet; `workspace_map` key missing from `generate_viz_data()` output.

- [ ] **Step 3: Implement the helpers and wire them in**

In `synlynk/viz.py`, replace line 22 (`VIZ_TUBE_PATH = ".synlynk/vizor-tube.json"`) with:

```python
VIZ_WORKSPACE_MAP_PATH = ".synlynk/vizor-workspace-map.json"
```

Add two new module-level functions directly below `_live_js` (after line 79, before
`generate_viz_data`):

```python
def _load_workspace_repos(config: dict) -> list:
    """Read the multi-repo list from the workspace config, defaulting to the 'default' workspace."""
    ws_name = config.get("workspace_name") or "default"
    ws_config_path = os.path.expanduser(f"~/.synlynk/workspaces/{ws_name}/config.json")
    if not os.path.exists(ws_config_path):
        ws_config_path = os.path.join(".synlynk", "workspaces", ws_name, "config.json")
    try:
        with open(ws_config_path) as f:
            ws_config = json.load(f)
        return ws_config.get("repos", [])
    except Exception:
        return []


def _load_workspace_map() -> dict:
    """Read typed edges between repos from .synlynk/vizor-workspace-map.json."""
    try:
        with open(VIZ_WORKSPACE_MAP_PATH) as f:
            data = json.load(f)
        return {"edges": data.get("edges", []), "edge_types": data.get("edge_types", {})}
    except Exception:
        return {"edges": [], "edge_types": {}}


def _repo_github_url(repo_path: str) -> Optional[str]:
    """Derive an https://github.com/<org>/<repo> URL from the repo's origin remote, if any."""
    try:
        result = subprocess.run(
            ["git", "-C", repo_path, "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            return None
        url = result.stdout.strip()
    except Exception:
        return None
    if url.startswith("git@github.com:"):
        slug = url[len("git@github.com:"):]
    elif "github.com/" in url:
        slug = url.split("github.com/", 1)[1]
    else:
        return None
    slug = slug[:-4] if slug.endswith(".git") else slug
    return f"https://github.com/{slug}" if slug else None
```

In `generate_viz_data()`'s `_base_data()` (currently `synlynk/viz.py:94-106`), replace the
`"tube_config": _load_json_optional(VIZ_TUBE_PATH, default=None),` line with:

```python
            "workspace_map": _load_workspace_map(),
```

and change the `"workspace"` entry (currently `{"name": _workspace_name(), "updated_at": _ts()}`)
to also carry the repo list and each repo's GitHub URL:

```python
            "workspace": {
                "name": _workspace_name(),
                "updated_at": _ts(),
                "repos": [
                    {**repo, "github_url": _repo_github_url(repo["path"])}
                    for repo in _load_workspace_repos(config)
                ],
            },
```

`_base_data()` doesn't currently have a `config` variable in scope — check the surrounding code
(`_workspace_name()` at lines 86-92 already opens `.synlynk/config.json` itself). Add a small
`_load_config()` helper next to `_load_json_optional` and call it once at the top of
`_base_data()`:

```python
    def _load_config() -> dict:
        try:
            with open(".synlynk/config.json") as f:
                return json.load(f)
        except Exception:
            return {}
```

Then at the start of `_base_data()`, add `config = _load_config()` and use `config` both in the
new `workspace.repos` wiring above and to replace `_workspace_name()`'s own internal
`open(".synlynk/config.json")` call with the shared `config` dict (keeps a single read instead of
two). If `_workspace_name()` is called from elsewhere too, leave it as-is and only wire the new
`config` variable into the new code — don't refactor a function outside this task's scope.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_viz.py -k "workspace_repos or workspace_map or viz_data_structure" -v`
Expected: PASS

- [ ] **Step 5: Run the full viz test file to check nothing else broke**

Run: `python3 -m pytest tests/test_viz.py -v`
Expected: Failures only in tests that reference `tube_config` or `generate_tube_html` directly
(handled in Task 4) — no failures in unrelated tests (Gantt, journeys, effort, efficiency,
observatory). If anything else breaks, stop and investigate before continuing.

- [ ] **Step 6: Commit**

```bash
git add synlynk/viz.py tests/test_viz.py
git commit -m "feat(viz): load workspace repos + typed edges for Architect Map v2"
```

---

### Task 2: File-tree data source — `_query_repo_file_tree()`

**Files:**
- Modify: `synlynk/__init__.py` (new function near `_scan_full_repo`, ~line 6604)
- Test: find the existing test file for `source_symbols`/scan helpers first:

Run: `grep -rln "source_symbols\|_scan_full_repo" tests/` — add the new test to whichever file
that returns (likely `tests/test_scan.py`).

- [ ] **Step 1: Write the failing test**

```python
def test_query_repo_file_tree_builds_nested_structure(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    db_path = str(tmp_path / "state.db")
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE source_symbols (
            id INTEGER PRIMARY KEY AUTOINCREMENT, head_sha TEXT NOT NULL,
            file TEXT NOT NULL, language TEXT NOT NULL, symbol TEXT NOT NULL,
            symbol_type TEXT NOT NULL, line INTEGER, scanned_at TEXT NOT NULL
        );
    """)
    conn.executemany(
        "INSERT INTO source_symbols (head_sha, file, language, symbol, symbol_type, line, scanned_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            ("abc123", "synlynk/viz.py", "python", "generate_gantt_html", "function", 930, "2026-07-11T00:00:00Z"),
            ("abc123", "synlynk/viz.py", "python", "generate_tube_html", "function", 1391, "2026-07-11T00:00:00Z"),
            ("abc123", "synlynk/__init__.py", "python", "init", "function", 1, "2026-07-11T00:00:00Z"),
            ("abc123", "tests/test_viz.py", "python", "test_dreams_populated", "function", 59, "2026-07-11T00:00:00Z"),
        ],
    )
    conn.commit()
    from synlynk import _query_repo_file_tree
    with patch("synlynk._get_db") as mock_db:
        mock_db.return_value = sqlite3.connect(db_path)
        tree = _query_repo_file_tree()
    assert tree["name"] == "."
    assert "synlynk" in tree["dirs"]
    assert "tests" in tree["dirs"]
    synlynk_dir = tree["dirs"]["synlynk"]
    file_names = {f["name"] for f in synlynk_dir["files"]}
    assert file_names == {"viz.py", "__init__.py"}
    viz_file = next(f for f in synlynk_dir["files"] if f["name"] == "viz.py")
    assert viz_file["symbol_count"] == 2

def test_query_repo_file_tree_empty_db_returns_empty_root(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    db_path = str(tmp_path / "state.db")
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE source_symbols (
            id INTEGER PRIMARY KEY AUTOINCREMENT, head_sha TEXT NOT NULL,
            file TEXT NOT NULL, language TEXT NOT NULL, symbol TEXT NOT NULL,
            symbol_type TEXT NOT NULL, line INTEGER, scanned_at TEXT NOT NULL
        );
    """)
    conn.commit()
    from synlynk import _query_repo_file_tree
    with patch("synlynk._get_db") as mock_db:
        mock_db.return_value = sqlite3.connect(db_path)
        tree = _query_repo_file_tree()
    assert tree == {"name": ".", "dirs": {}, "files": []}
```

Add `import sqlite3` and `from unittest.mock import patch` at the top of the test file if not
already present (check first — `tests/test_viz.py` already imports both at line 1-2; the scan
test file may not).

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_scan.py -k "query_repo_file_tree" -v`
Expected: FAIL with `ImportError: cannot import name '_query_repo_file_tree'`

- [ ] **Step 3: Implement `_query_repo_file_tree`**

Add to `synlynk/__init__.py`, directly above `_scan_source_skeleton` (before line 6604):

```python
def _query_repo_file_tree() -> dict:
    """Build a nested directory tree from source_symbols for the current HEAD.

    Returns {"name": ".", "dirs": {dirname: <same shape>}, "files": [{"name", "symbol_count"}]}.
    Reuses the existing source_symbols table (populated by `synlynk scan --deep`) instead of
    walking the filesystem again.
    """
    conn = _get_db()
    cur = conn.cursor()
    try:
        cur.execute("SELECT MAX(scanned_at) FROM source_symbols")
        row = cur.fetchone()
        if not row or not row[0]:
            return {"name": ".", "dirs": {}, "files": []}
        cur.execute(
            "SELECT file, COUNT(*) FROM source_symbols "
            "WHERE scanned_at = (SELECT MAX(scanned_at) FROM source_symbols) "
            "GROUP BY file"
        )
        file_counts = cur.fetchall()
    except sqlite3.OperationalError:
        return {"name": ".", "dirs": {}, "files": []}

    root = {"name": ".", "dirs": {}, "files": []}
    for file_path, symbol_count in file_counts:
        parts = file_path.split(os.sep) if os.sep in file_path else file_path.split("/")
        node = root
        for part in parts[:-1]:
            node = node["dirs"].setdefault(part, {"name": part, "dirs": {}, "files": []})
        node["files"].append({"name": parts[-1], "symbol_count": symbol_count})
    return root
```

`_get_db` and `sqlite3` are already imported/available in `synlynk/__init__.py` (used throughout
the file, e.g. by `_scan_full_repo`) — no new imports needed.

Note: the test seeds all rows with the same `scanned_at` so `MAX(scanned_at)` selects all of
them; in production, `_scan_full_repo`'s existing `DELETE FROM source_symbols WHERE head_sha !=
?` (line ~6656) already keeps only current-HEAD rows, so grouping by "latest scanned_at" is a
defensive extra filter, not the primary staleness guard.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_scan.py -k "query_repo_file_tree" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add synlynk/__init__.py tests/test_scan.py
git commit -m "feat(scan): add _query_repo_file_tree for Architect Map's file-tree sub-view"
```

---

### Task 3: `/dispatch` and `/architect-map/view-pref` POST routes

**Files:**
- Modify: `synlynk/viz.py:4410-4467` (`VizorHandler`)
- Test: `tests/test_viz.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_vizor_handler_dispatch_route_exists():
    from synlynk.viz import VizorHandler
    assert hasattr(VizorHandler, "do_POST")
    import inspect
    src = inspect.getsource(VizorHandler.do_POST)
    assert "/dispatch" in src
    assert "/architect-map/view-pref" in src
```

This is a light structural test — full HTTP-level testing of `do_POST` would require spinning up
a real server, which existing tests in this file don't do for `/note` either (confirmed: no test
calls `VizorHandler.do_POST` directly with a mock request — behavior is validated through the
`saveNote()` JS calling `fetch()`, not exercised by pytest). Follow the same convention: verify
the routing logic exists and is structured correctly, not a live socket test.

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_viz.py -k "dispatch_route_exists" -v`
Expected: FAIL — `/dispatch` and `/architect-map/view-pref` not in `do_POST` source yet.

- [ ] **Step 3: Implement the routes**

Replace `synlynk/viz.py:4429-4463` (`do_POST` — currently only handles `/note`) with:

```python
    def do_POST(self):
        if self.path == "/note":
            self._handle_note()
        elif self.path == "/dispatch":
            self._handle_dispatch()
        elif self.path == "/architect-map/view-pref":
            self._handle_view_pref()
        else:
            self.send_error(404)

    def _read_json_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        return json.loads(body)

    def _handle_note(self):
        try:
            note = self._read_json_body()
        except json.JSONDecodeError:
            self.send_error(400, "Invalid JSON")
            return
        notes = {}
        if os.path.exists(VIZ_NOTES_PATH):
            with open(VIZ_NOTES_PATH) as f:
                try:
                    notes = json.load(f)
                except json.JSONDecodeError:
                    notes = {}
        element_id = note.get("id", "")
        if not element_id:
            self.send_error(400, "Missing id")
            return
        notes[element_id] = {
            "text": note.get("text", ""),
            "tags": note.get("tags", []),
            "state": note.get("state", "info"),
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        with open(VIZ_NOTES_PATH, "w") as f:
            json.dump(notes, f, indent=2)
        self._send_json_ok()

    def _handle_dispatch(self):
        try:
            payload = self._read_json_body()
        except json.JSONDecodeError:
            self.send_error(400, "Invalid JSON")
            return
        repo_path = payload.get("repo_path", "")
        task = payload.get("task", "")
        if not repo_path or not task:
            self.send_error(400, "Missing repo_path or task")
            return
        from synlynk.dispatch import dispatch_agent
        try:
            job = dispatch_agent(payload.get("agent", "claude"), task, force_agent=True,
                                  context_mode="full")
        except Exception as e:
            self.send_error(500, str(e))
            return
        self._send_json_ok({"job_id": job.get("id")})

    def _handle_view_pref(self):
        try:
            payload = self._read_json_body()
        except json.JSONDecodeError:
            self.send_error(400, "Invalid JSON")
            return
        view = payload.get("view")
        if view not in ("graph", "tree"):
            self.send_error(400, "view must be 'graph' or 'tree'")
            return
        try:
            with open(".synlynk/config.json") as f:
                config = json.load(f)
        except Exception:
            config = {}
        config.setdefault("vizor", {})["architect_map_view"] = view
        with open(".synlynk/config.json", "w") as f:
            json.dump(config, f, indent=2)
        self._send_json_ok()

    def _send_json_ok(self, extra: dict = None):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self._send_cors_headers()
        self.end_headers()
        body = {"ok": True}
        if extra:
            body.update(extra)
        self.wfile.write(json.dumps(body).encode("utf-8"))
```

Also update `do_OPTIONS` (currently `synlynk/viz.py:4421-4427`, gated on `self.path != "/note"`)
to accept the two new paths:

```python
    def do_OPTIONS(self):
        if self.path not in ("/note", "/dispatch", "/architect-map/view-pref"):
            self.send_error(404)
            return
        self.send_response(204)
        self._send_cors_headers()
        self.end_headers()
```

`dispatch_agent` is imported lazily inside `_handle_dispatch` (not at module top) to avoid adding
a hard import-time dependency from `viz.py` on `synlynk.dispatch` for code paths that never touch
this route — this matches the existing codebase's pattern of narrow, function-local imports for
cross-module calls elsewhere in `synlynk/__init__.py`. Verify `dispatch_agent`'s signature matches
`synlynk/dispatch.py:650-656` (`agent: str, task: str, story_id=None, force_agent=False,
context_mode=None, cycle="work", skip_preflight=False, grants=None, revokes=None`) — this task
passes `force_agent=True, context_mode="full"` matching the existing CLAUDE.md dispatch
convention (`--force-agent --context-mode full`).

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_viz.py -k "dispatch_route_exists" -v`
Expected: PASS

- [ ] **Step 5: Run the full viz test suite**

Run: `python3 -m pytest tests/test_viz.py -v`
Expected: All pass (Task 1's changes should already be green; this task only touches
`VizorHandler`, which nothing else in the test file exercises directly).

- [ ] **Step 6: Commit**

```bash
git add synlynk/viz.py tests/test_viz.py
git commit -m "feat(viz): add /dispatch and /architect-map/view-pref POST routes"
```

---

### Task 4: `generate_architect_map_html()` — graph rendering + empty state

**Files:**
- Modify: `synlynk/viz.py:1391-1927` (rename + rewrite `generate_tube_html`), `synlynk/viz.py:4396` (`_write_cache` dict key)
- Test: `tests/test_viz.py`

This task replaces the SVG tube-map body with the force-directed node graph. The side drawer and
file-tree switcher are separate tasks (5 and 6) that extend this function's output — this task
gets the graph itself rendering correctly with a real empty state first.

- [ ] **Step 1: Write the failing tests**

Replace the two existing tests `test_generate_tube_html_no_config` and
`test_generate_tube_html_with_config` (`tests/test_viz.py:167-208`) with:

```python
def test_generate_architect_map_html_no_repos_shows_single_node():
    from synlynk.viz import generate_architect_map_html
    data = {
        "workspace": {"name": "test-ws", "updated_at": "2026-07-03T10:00:00Z", "repos": []},
        "workspace_map": {"edges": [], "edge_types": {}},
    }
    html = generate_architect_map_html(data, 8721)
    assert "🗺️ Architect Map" in html or "Architect Map" in html
    assert "synlynk viz --setup-tube" not in html
    assert "test-ws" in html

def test_generate_architect_map_html_renders_repo_nodes():
    from synlynk.viz import generate_architect_map_html
    data = {
        "workspace": {
            "name": "test-ws", "updated_at": "2026-07-03T10:00:00Z",
            "repos": [
                {"path": "/repo/core", "name": "synlynk-core", "stack_labels": ["python"], "github_url": "https://github.com/nikhilsoman/synlynk"},
                {"path": "/repo/web", "name": "synlynk-website", "stack_labels": ["node"], "github_url": None},
            ],
        },
        "workspace_map": {
            "edges": [{"from": "synlynk-website", "to": "synlynk-core", "type": "api-call"}],
            "edge_types": {"api-call": {"label": "API Call", "color": "#0d9e87"}},
        },
    }
    html = generate_architect_map_html(data, 8721)
    assert "synlynk-core" in html
    assert "synlynk-website" in html
    assert "api-call" in html
    assert "#0d9e87" in html
    assert "API Call" in html
```

Update the two loop-based tests that reference `generate_tube_html` by name
(`tests/test_viz.py:404-425` and the `_write_cache`-related test around line 340-351): change the
import and the loop list from `generate_tube_html` to `generate_architect_map_html`, and change
their `"tube_config": None,` fixture entries (already updated to `"workspace_map": {"edges": [],
"edge_types": {}}` in Task 1) — also add `"repos": []` to each `"workspace": {...}` fixture dict
in those same tests, since `generate_architect_map_html` reads `data["workspace"]["repos"]`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_viz.py -k "architect_map" -v`
Expected: FAIL — `generate_architect_map_html` doesn't exist yet.

- [ ] **Step 3: Rename and rewrite the function**

Rename `generate_tube_html` (`synlynk/viz.py:1391`) to `generate_architect_map_html` (same
signature: `(data: dict, port: int) -> str`).

Replace the entire body from the current empty-state check (`synlynk/viz.py:1537`, `tube_config =
data.get("tube_config")`) through the end of the function (line 1927) with:

```python
    workspace = data.get("workspace", {})
    workspace_name = str(workspace.get("name") or "workspace")
    updated_at = workspace.get("updated_at", "")
    repos = workspace.get("repos") or []
    workspace_map = data.get("workspace_map") or {"edges": [], "edge_types": {}}
    edges = workspace_map.get("edges", [])
    edge_types = workspace_map.get("edge_types", {})

    if not repos:
        repos = [{"path": os.getcwd(), "name": workspace_name, "stack_labels": [], "github_url": None}]

    nodes_json = json.dumps([
        {
            "id": r["name"],
            "label": r["name"],
            "path": r.get("path", ""),
            "stack_labels": r.get("stack_labels", []),
            "github_url": r.get("github_url"),
        }
        for r in repos
    ])
    edges_json = json.dumps(edges)
    edge_types_json = json.dumps(edge_types)

    legend_html = "".join(
        f'<div class="legend-item"><span class="legend-dot" style="background:{html.escape(et.get("color", "#94a3b8"))}"></span>{html.escape(et.get("label", key))}</div>'
        for key, et in edge_types.items()
    )

    style_content = _ARCHITECT_MAP_STYLE
    json_data = json.dumps(data)
    live_js_html = _live_js(port)

    template = """<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
<meta charset="UTF-8">
<title>synlynk Vizor — Architect Map</title>
<style>
__STYLE_CONTENT__
</style>
</head>
<body>
<div class="am-header">
  <h1>Architect Map — __WORKSPACE_NAME__</h1>
  <div class="am-switcher">
    <button class="am-tab active" data-view="graph" onclick="setArchitectView('graph')">Graph</button>
    <button class="am-tab" data-view="tree" onclick="setArchitectView('tree')">File Tree</button>
  </div>
</div>
<div class="am-legend">__LEGEND_HTML__</div>
<div id="am-graph-view" class="am-view active">
  <svg id="am-svg" width="100%" height="640"></svg>
</div>
<div id="am-tree-view" class="am-view">
  <div id="am-tree-root" class="am-tree"></div>
</div>
<div class="ov" id="am-ov" onclick="closeDrawer()"></div>
<div class="am-drawer" id="am-drawer">
  <div class="am-drawer-header">
    <span id="am-drawer-title">—</span>
    <button onclick="closeDrawer()">✕</button>
  </div>
  <div class="am-drawer-body" id="am-drawer-body"></div>
  <div class="am-drawer-actions">
    <button class="btn" onclick="drawerDispatch()">Dispatch to this repo</button>
    <button class="btn" onclick="drawerJumpGantt()">Jump to Gantt view</button>
    <a class="btn" id="am-drawer-github" href="#" target="_blank" rel="noopener">Open on GitHub</a>
  </div>
</div>
<script>
window.VIZOR_DATA = __JSON_DATA__;
window.ARCHITECT_NODES = __NODES_JSON__;
window.ARCHITECT_EDGES = __EDGES_JSON__;
window.ARCHITECT_EDGE_TYPES = __EDGE_TYPES_JSON__;
window.VIZOR_PORT = __PORT__;
__ARCHITECT_MAP_JS__
</script>
__LIVE_JS_HTML__
</body>
</html>"""
    return (
        template.replace("__STYLE_CONTENT__", style_content)
        .replace("__WORKSPACE_NAME__", html.escape(workspace_name))
        .replace("__LEGEND_HTML__", legend_html)
        .replace("__JSON_DATA__", json_data)
        .replace("__NODES_JSON__", nodes_json)
        .replace("__EDGES_JSON__", edges_json)
        .replace("__EDGE_TYPES_JSON__", edge_types_json)
        .replace("__PORT__", str(port))
        .replace("__ARCHITECT_MAP_JS__", _ARCHITECT_MAP_JS)
        .replace("__LIVE_JS_HTML__", live_js_html)
    )
```

Add two new module-level constants directly above `generate_architect_map_html` (`_ARCHITECT_MAP_STYLE`
holds the CSS, `_ARCHITECT_MAP_JS` holds the JS — Tasks 5 and 6 will append to `_ARCHITECT_MAP_JS`,
so define it now as a plain string constant, not inline in the function):

```python
_ARCHITECT_MAP_STYLE = """
body { margin:0; font-family:'SF Mono',monospace; background:#f6f8fa; color:#1f2328; }
.am-header { display:flex; justify-content:space-between; align-items:center; padding:14px 20px; border-bottom:1px solid #d1d5db; }
.am-header h1 { font-size:15px; margin:0; }
.am-switcher { display:flex; gap:6px; }
.am-tab { background:#fff; border:1px solid #d1d5db; border-radius:6px; padding:5px 12px; font-size:12px; cursor:pointer; font-family:inherit; }
.am-tab.active { background:#0d9e87; color:#fff; border-color:#0d9e87; }
.am-legend { display:flex; gap:14px; padding:8px 20px; font-size:11px; }
.legend-item { display:flex; align-items:center; gap:5px; }
.legend-dot { width:9px; height:9px; border-radius:50%; display:inline-block; }
.am-view { display:none; padding:10px 20px; }
.am-view.active { display:block; }
.am-node { cursor:pointer; }
.am-node rect { fill:#fff; stroke:#334155; stroke-width:1.5; }
.am-node text { font-size:11px; font-family:inherit; }
.am-edge { stroke-width:2; fill:none; }
.ov { display:none; position:fixed; inset:0; background:rgba(0,0,0,.35); z-index:999; }
.ov.open { display:block; }
.am-drawer { position:fixed; top:0; right:-360px; width:340px; height:100%; background:#fff; box-shadow:-2px 0 12px rgba(0,0,0,.15); z-index:1000; transition:right .2s ease; padding:16px; box-sizing:border-box; }
.am-drawer.open { right:0; }
.am-drawer-header { display:flex; justify-content:space-between; align-items:center; font-size:13px; font-weight:bold; margin-bottom:12px; }
.am-drawer-header button { background:none; border:none; cursor:pointer; font-size:14px; }
.am-drawer-body { font-size:12px; line-height:1.6; margin-bottom:16px; }
.am-drawer-actions { display:flex; flex-direction:column; gap:8px; }
.btn { background:#0d9e87; color:#fff; border:none; border-radius:5px; padding:7px 10px; font-size:12px; cursor:pointer; text-align:center; text-decoration:none; font-family:inherit; }
.am-tree { font-size:12px; }
.am-tree-dir > summary { cursor:pointer; padding:2px 0; }
.am-tree-file { padding:2px 0 2px 18px; color:#475569; }
"""
```

- [ ] **Step 4: Update the `_write_cache` call site**

In `synlynk/viz.py:4396`, change `"tube.html": generate_tube_html(data, port),` to
`"tube.html": generate_architect_map_html(data, port),`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_viz.py -v`
Expected: All pass. `_ARCHITECT_MAP_JS` is referenced but not yet defined — add a temporary
placeholder now so the module imports cleanly (Task 5 replaces this with real content):

```python
_ARCHITECT_MAP_JS = "// populated in Task 5/6"
```

Place this constant directly above `_ARCHITECT_MAP_STYLE`.

- [ ] **Step 6: Commit**

```bash
git add synlynk/viz.py tests/test_viz.py
git commit -m "feat(viz): render Architect Map as a force-directed repo graph"
```

---

### Task 5: Force-directed layout + node click → side drawer (JS)

**Files:**
- Modify: `synlynk/viz.py` — replace the `_ARCHITECT_MAP_JS` placeholder from Task 4.
- Test: `tests/test_viz.py`

- [ ] **Step 1: Write the failing test**

```python
def test_generate_architect_map_html_includes_layout_and_drawer_js():
    from synlynk.viz import generate_architect_map_html
    data = {
        "workspace": {"name": "test-ws", "updated_at": "", "repos": [
            {"path": "/r/a", "name": "repo-a", "stack_labels": [], "github_url": "https://github.com/x/a"},
        ]},
        "workspace_map": {"edges": [], "edge_types": {}},
    }
    html_out = generate_architect_map_html(data, 8721)
    assert "function layoutGraph" in html_out
    assert "function openDrawer" in html_out
    assert "function closeDrawer" in html_out
    assert "function drawerDispatch" in html_out
    assert "function drawerJumpGantt" in html_out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_viz.py -k "layout_and_drawer_js" -v`
Expected: FAIL — placeholder JS has none of these functions.

- [ ] **Step 3: Replace the `_ARCHITECT_MAP_JS` placeholder**

```python
_ARCHITECT_MAP_JS = """
function layoutGraph(nodes, edges) {
  const W = 900, H = 620, ITER = 200;
  const positions = {};
  nodes.forEach((n, i) => {
    const angle = (2 * Math.PI * i) / Math.max(nodes.length, 1);
    positions[n.id] = { x: W / 2 + 260 * Math.cos(angle), y: H / 2 + 220 * Math.sin(angle) };
  });
  for (let iter = 0; iter < ITER; iter++) {
    nodes.forEach(a => {
      let fx = 0, fy = 0;
      nodes.forEach(b => {
        if (a.id === b.id) return;
        const dx = positions[a.id].x - positions[b.id].x;
        const dy = positions[a.id].y - positions[b.id].y;
        const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 1);
        const repel = 4000 / (dist * dist);
        fx += (dx / dist) * repel;
        fy += (dy / dist) * repel;
      });
      edges.forEach(e => {
        if (e.from !== a.id && e.to !== a.id) return;
        const otherId = e.from === a.id ? e.to : e.from;
        if (!positions[otherId]) return;
        const dx = positions[otherId].x - positions[a.id].x;
        const dy = positions[otherId].y - positions[a.id].y;
        const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 1);
        const attract = dist * 0.01;
        fx += (dx / dist) * attract;
        fy += (dy / dist) * attract;
      });
      positions[a.id].x = Math.min(W - 70, Math.max(70, positions[a.id].x + fx));
      positions[a.id].y = Math.min(H - 40, Math.max(40, positions[a.id].y + fy));
    });
  }
  return positions;
}

function renderGraph() {
  const svg = document.getElementById('am-svg');
  const nodes = window.ARCHITECT_NODES || [];
  const edges = window.ARCHITECT_EDGES || [];
  const edgeTypes = window.ARCHITECT_EDGE_TYPES || {};
  const pos = layoutGraph(nodes, edges);
  let markup = '';
  edges.forEach(e => {
    const a = pos[e.from], b = pos[e.to];
    if (!a || !b) return;
    const color = (edgeTypes[e.type] || {}).color || '#94a3b8';
    markup += '<line class="am-edge" x1="' + a.x + '" y1="' + a.y + '" x2="' + b.x + '" y2="' + b.y + '" stroke="' + color + '"></line>';
  });
  nodes.forEach(n => {
    const p = pos[n.id];
    if (!p) return;
    const w = Math.max(90, n.label.length * 7 + 20);
    markup += '<g class="am-node" transform="translate(' + (p.x - w / 2) + ',' + (p.y - 18) + ')" onclick="openDrawer(\\'' + n.id + '\\')">' +
      '<rect width="' + w + '" height="36" rx="8"></rect>' +
      '<text x="' + (w / 2) + '" y="22" text-anchor="middle">' + n.label + '</text>' +
      '</g>';
  });
  svg.innerHTML = markup;
}

function setArchitectView(view) {
  document.querySelectorAll('.am-tab').forEach(t => t.classList.toggle('active', t.dataset.view === view));
  document.getElementById('am-graph-view').classList.toggle('active', view === 'graph');
  document.getElementById('am-tree-view').classList.toggle('active', view === 'tree');
  if (view === 'tree' && !window._treeRendered) {
    renderTree();
    window._treeRendered = true;
  }
  fetch('http://localhost:' + window.VIZOR_PORT + '/architect-map/view-pref', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ view: view }),
  }).catch(() => {});
}

let currentDrawerNode = null;

function openDrawer(nodeId) {
  const node = (window.ARCHITECT_NODES || []).find(n => n.id === nodeId);
  if (!node) return;
  currentDrawerNode = node;
  document.getElementById('am-drawer-title').textContent = node.label;
  const stack = (node.stack_labels || []).join(', ') || 'unlabeled';
  document.getElementById('am-drawer-body').innerHTML =
    '<div>Path: <code>' + node.path + '</code></div>' +
    '<div>Stack: ' + stack + '</div>';
  const githubLink = document.getElementById('am-drawer-github');
  if (node.github_url) {
    githubLink.href = node.github_url;
    githubLink.style.display = 'block';
  } else {
    githubLink.style.display = 'none';
  }
  document.getElementById('am-drawer').classList.add('open');
  document.getElementById('am-ov').classList.add('open');
}

function closeDrawer() {
  document.getElementById('am-drawer').classList.remove('open');
  document.getElementById('am-ov').classList.remove('open');
  currentDrawerNode = null;
}

async function drawerDispatch() {
  if (!currentDrawerNode) return;
  const task = prompt('Task to dispatch in ' + currentDrawerNode.label + ':');
  if (!task) return;
  await fetch('http://localhost:' + window.VIZOR_PORT + '/dispatch', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ repo_path: currentDrawerNode.path, task: task }),
  });
  closeDrawer();
}

function drawerJumpGantt() {
  if (!currentDrawerNode) return;
  window.top.postMessage({ type: 'vizor-navigate', view: 'gantt', repo: currentDrawerNode.id }, '*');
}

renderGraph();
"""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_viz.py -k "layout_and_drawer_js" -v`
Expected: PASS

- [ ] **Step 5: Run the full viz suite**

Run: `python3 -m pytest tests/test_viz.py -v`
Expected: All pass.

- [ ] **Step 6: Commit**

```bash
git add synlynk/viz.py tests/test_viz.py
git commit -m "feat(viz): force-directed layout + side drawer interaction for Architect Map"
```

---

### Task 6: File-tree sub-view rendering (JS) + wiring the DB-backed tree into `generate_viz_data`

**Files:**
- Modify: `synlynk/viz.py` (`generate_viz_data`, `_ARCHITECT_MAP_JS`)
- Test: `tests/test_viz.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_generate_viz_data_includes_file_tree(tmp_path, monkeypatch):
    db_path = str(tmp_path / "state.db")
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE roadmap_arcs (id INTEGER PRIMARY KEY, version TEXT UNIQUE, title TEXT, status TEXT DEFAULT 'active', target_date TEXT, notes TEXT);
        CREATE TABLE roadmap_phases (id INTEGER PRIMARY KEY, arc_version TEXT, phase_title TEXT, status TEXT DEFAULT 'planned', priority TEXT, story_id TEXT, notes TEXT);
        CREATE TABLE stories (id INTEGER PRIMARY KEY, story_id TEXT UNIQUE, title TEXT, status TEXT DEFAULT 'open', phase TEXT DEFAULT 'build', estimated_tokens INTEGER, created_at TEXT);
        CREATE TABLE cost_entries (id INTEGER PRIMARY KEY, session_date TEXT, agent TEXT, model TEXT, input_tokens INTEGER, output_tokens INTEGER, cache_read_tokens INTEGER, total_cost_usd REAL, notes TEXT);
        CREATE TABLE source_symbols (id INTEGER PRIMARY KEY AUTOINCREMENT, head_sha TEXT NOT NULL, file TEXT NOT NULL, language TEXT NOT NULL, symbol TEXT NOT NULL, symbol_type TEXT NOT NULL, line INTEGER, scanned_at TEXT NOT NULL);
        INSERT INTO source_symbols (head_sha, file, language, symbol, symbol_type, line, scanned_at)
            VALUES ('abc', 'synlynk/viz.py', 'python', 'generate_gantt_html', 'function', 930, '2026-07-11T00:00:00Z');
    """)
    conn.commit()
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    with open(".synlynk/config.json", "w") as f:
        json.dump({"project_name": "test-project"}, f)

    from synlynk.viz import generate_viz_data
    with patch("synlynk.viz._get_db") as mock_db:
        mock_db.return_value = sqlite3.connect(db_path)
        data = generate_viz_data()

    assert "file_tree" in data
    assert "synlynk" in data["file_tree"]["dirs"]

def test_generate_architect_map_html_includes_tree_render_js():
    from synlynk.viz import generate_architect_map_html
    data = {
        "workspace": {"name": "test-ws", "updated_at": "", "repos": []},
        "workspace_map": {"edges": [], "edge_types": {}},
        "file_tree": {"name": ".", "dirs": {}, "files": []},
    }
    html_out = generate_architect_map_html(data, 8721)
    assert "function renderTree" in html_out
    assert "window.ARCHITECT_FILE_TREE" in html_out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_viz.py -k "file_tree" -v`
Expected: FAIL — `generate_viz_data()` has no `file_tree` key; `_ARCHITECT_MAP_JS` has no
`renderTree` function; template has no `ARCHITECT_FILE_TREE` window var.

- [ ] **Step 3: Wire `_query_repo_file_tree` into `generate_viz_data`**

In `synlynk/viz.py`, add an import at the top of the file (with the existing `from synlynk import
_get_db` at line 13):

```python
from synlynk import _get_db, _query_repo_file_tree
```

In `_base_data()` (`synlynk/viz.py`, same block edited in Task 1), add one line after the
`workspace_map` line:

```python
            "file_tree": _query_repo_file_tree(),
```

- [ ] **Step 4: Add `file_tree` to `generate_architect_map_html`'s template wiring**

In `generate_architect_map_html` (edited in Task 4), after the line `edge_types_json =
json.dumps(edge_types)`, add:

```python
    file_tree_json = json.dumps(data.get("file_tree") or {"name": ".", "dirs": {}, "files": []})
```

In the `template` string's `<script>` block (Task 4), add a new line right after
`window.ARCHITECT_EDGE_TYPES = __EDGE_TYPES_JSON__;`:

```
window.ARCHITECT_FILE_TREE = __FILE_TREE_JSON__;
```

And add the matching `.replace(...)` call in the return statement, right after the
`__EDGE_TYPES_JSON__` replace:

```python
        .replace("__FILE_TREE_JSON__", file_tree_json)
```

- [ ] **Step 5: Add `renderTree` to `_ARCHITECT_MAP_JS`**

Append this function to the `_ARCHITECT_MAP_JS` string constant (edited in Task 5), right before
the trailing `renderGraph();` call:

```javascript
function renderTreeNode(node) {
  let html = '';
  const dirNames = Object.keys(node.dirs || {}).sort();
  dirNames.forEach(name => {
    html += '<details class="am-tree-dir" open><summary>📁 ' + name + '</summary>' + renderTreeNode(node.dirs[name]) + '</details>';
  });
  (node.files || []).slice().sort((a, b) => a.name.localeCompare(b.name)).forEach(f => {
    html += '<div class="am-tree-file">📄 ' + f.name + ' <span style="color:#94a3b8">(' + f.symbol_count + ')</span></div>';
  });
  return html;
}

function renderTree() {
  const root = document.getElementById('am-tree-root');
  const tree = window.ARCHITECT_FILE_TREE || { dirs: {}, files: [] };
  root.innerHTML = renderTreeNode(tree) || '<div class="am-tree-file">No scan data yet — run <code>synlynk scan --deep</code>.</div>';
}
```

Keep `renderGraph();` as the last line of the constant (it still needs to run on load; `renderTree()`
is only invoked lazily from `setArchitectView('tree')`, per Task 5's `setArchitectView`).

- [ ] **Step 6: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_viz.py -k "file_tree" -v`
Expected: PASS

- [ ] **Step 7: Run the full test suite**

Run: `python3 -m pytest tests/ -v`
Expected: All pass, project-wide (not just `test_viz.py` — confirm nothing in `test_scan.py` or
elsewhere regressed from the `synlynk/__init__.py` changes in Task 2).

- [ ] **Step 8: Commit**

```bash
git add synlynk/viz.py
git commit -m "feat(viz): render IDE-style file tree as an Architect Map sub-view"
```

---

### Task 7: Clean up dead references — old spec, old constant, migration note

**Files:**
- Modify: `docs/superpowers/specs/2026-07-03-bs21-vizor-design.md`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Remove the dead `--setup-tube` references from the original design spec**

In `docs/superpowers/specs/2026-07-03-bs21-vizor-design.md`, find the two references (originally
at lines ~164-180 and ~292-294 per the brainstorm's research — line numbers may have shifted;
search for the literal string `--setup-tube`):

Run: `grep -n "setup-tube" docs/superpowers/specs/2026-07-03-bs21-vizor-design.md`

Replace each match's surrounding sentence with a pointer to the new spec, e.g. change:

```
Auto-generation from codebase imports is a v2 feature.
```

to:

```
Superseded by docs/superpowers/specs/2026-07-11-vizor-architect-map-v2-design.md — the Architect
Map is now a live workspace-repo graph generated from `.synlynk/config.json`'s workspace repo
list, not a manually-authored tube map.
```

And remove the `synlynk viz --setup-tube` command-reference row entirely (it described a command
that was never implemented and no longer will be, per the v2 design's §7 Migration Notes).

- [ ] **Step 2: Add the "Workspace Map Update" protocol to CLAUDE.md**

In `CLAUDE.md`, find the `## Blog Post Protocol` section (this repo's root `CLAUDE.md`). Add a new
section immediately after it:

```markdown
## Workspace Map Update Protocol

**For any PR that changes how one tracked repo relates to another** (new API call between repos,
new shared dependency, a relationship removed), update `.synlynk/vizor-workspace-map.json` in the
same branch as that PR — add/edit/remove the relevant entry in its `edges` array. Most PRs touch
only one repo and don't need this step; it only applies when the PR's own description says it
adds, removes, or changes a cross-repo relationship. This keeps Vizor's Architect Map graph
(`docs/superpowers/specs/2026-07-11-vizor-architect-map-v2-design.md`) accurate without a manual
audit step — same discipline as the Blog Post Protocol above, but conditional rather than
mandatory on every PR.
```

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/specs/2026-07-03-bs21-vizor-design.md CLAUDE.md
git commit -m "docs: retire --setup-tube references, add Workspace Map Update protocol"
```

---

## Self-Review Notes

**Spec coverage:**
- §3.1 (nodes from repos + GitHub URL) → Task 1 (`_load_workspace_repos`, `_repo_github_url`).
- §3.2 (typed edges, PR-driven freshness) → Task 1 (`_load_workspace_map`) + Task 7 (CLAUDE.md
  protocol addition).
- §4 (force-directed layout, no CDN) → Task 5 (`layoutGraph`/`renderGraph`).
- §5 (side drawer, 4 actions) → Task 5 (`openDrawer`/`closeDrawer`/`drawerDispatch`/
  `drawerJumpGantt`; GitHub link handled inline in `openDrawer`; dreams/agents summary — see gap
  below).
- §6 (sub-view switcher, pinning, extensibility) → Task 4 (`am-switcher` tabs) + Task 6 (tree
  render) + Task 3 (`/architect-map/view-pref` persists to `.synlynk/config.json`).
- §7 (migration notes) → Task 7.

**Gap found during self-review:** §5's action #3, "Show active dreams/agents at a glance," is not
fully wired — Task 5's `openDrawer` only renders path and stack labels, not a dreams/agents
summary. The spec's §3.1 mentions deriving this from "the same source the Gantt view already
reads," but that source is per-repo dream/agent state in `state.db`, which isn't threaded into
`workspace.repos` anywhere in this plan. Fixing this properly needs a new query (dreams/agents
filtered by repo path) that doesn't exist yet and wasn't scoped in Tasks 1-6. Rather than leave a
silent gap, add it as an explicit Task 8 below instead of a placeholder comment in the code.

### Task 8: Drawer dreams/agents summary

**Files:**
- Modify: `synlynk/viz.py` (`_load_workspace_repos` call site in `_base_data`, `openDrawer` JS)
- Test: `tests/test_viz.py`

- [ ] **Step 1: Write the failing test**

```python
def test_workspace_repos_include_dream_agent_counts(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    ws_dir = tmp_path / "fake-home" / ".synlynk" / "workspaces" / "default"
    ws_dir.mkdir(parents=True)
    (ws_dir / "config.json").write_text(json.dumps({
        "workspace_name": "default",
        "repos": [{"path": "/repo/a", "name": "repo-a", "stack_labels": []}],
    }))
    monkeypatch.setenv("HOME", str(tmp_path / "fake-home"))
    db_path = str(tmp_path / "state.db")
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE stories (id INTEGER PRIMARY KEY, story_id TEXT UNIQUE, title TEXT,
            status TEXT DEFAULT 'open', phase TEXT DEFAULT 'build', repo_path TEXT,
            estimated_tokens INTEGER, created_at TEXT);
        INSERT INTO stories (story_id, title, status, phase, repo_path) VALUES
            ('story-1', 'Story One', 'active', 'build', '/repo/a');
    """)
    conn.commit()
    os.makedirs(".synlynk", exist_ok=True)
    with open(".synlynk/config.json", "w") as f:
        json.dump({}, f)

    from synlynk.viz import generate_viz_data
    with patch("synlynk.viz._get_db") as mock_db:
        mock_db.return_value = sqlite3.connect(db_path)
        data = generate_viz_data()
    repo_a = next(r for r in data["workspace"]["repos"] if r["name"] == "repo-a")
    assert repo_a["active_dream_count"] == 1
```

Before writing this test, run `grep -n "CREATE TABLE stories" synlynk/__init__.py` to check
whether the real `stories` table already has a `repo_path` column. If it does not (likely, since
synlynk is currently single-repo-per-`state.db` in practice), this test's premise (`repo_path` on
`stories`) does not match production schema — **stop and re-scope this task** rather than adding a
column that isn't part of this plan's approved design. In that case, the correct minimal
implementation is: `active_dream_count` = `len([s for s in stories if s.status == 'active'])` when
there is exactly one repo (today's dogfood case), and `0` for every repo when there are 2+ repos
and no `repo_path` column exists to attribute dreams per-repo. Write the test to match whichever
reality `grep` reveals before implementing — do not guess the schema.

- [ ] **Step 2: Run test, adjust to actual schema, implement, re-run — repeat the standard
  red/green/commit loop from Tasks 1-6 above using the schema facts gathered in Step 1.**

- [ ] **Step 3: Wire the count into `openDrawer`'s JS** (Task 5's function) by adding a line to
  the `am-drawer-body` HTML:

```javascript
  document.getElementById('am-drawer-body').innerHTML =
    '<div>Path: <code>' + node.path + '</code></div>' +
    '<div>Stack: ' + stack + '</div>' +
    '<div>Active dreams: ' + (node.active_dream_count || 0) + '</div>';
```

- [ ] **Step 4: Commit**

```bash
git add synlynk/viz.py tests/test_viz.py
git commit -m "feat(viz): surface active dream count in Architect Map drawer"
```

**Placeholder scan:** no TBD/TODO strings; the one deliberately open-ended step (Task 8, Step 1's
schema check) is a "verify before implementing" instruction with two fully-specified fallback
paths, not an unresolved placeholder.

**Type consistency:** `generate_architect_map_html(data, port)` signature is identical across
Tasks 4-6. `_load_workspace_repos(config)`, `_load_workspace_map()`, `_query_repo_file_tree()`
signatures are each defined once (Tasks 1-2) and never redeclared differently later. The JS
globals (`ARCHITECT_NODES`, `ARCHITECT_EDGES`, `ARCHITECT_EDGE_TYPES`, `ARCHITECT_FILE_TREE`,
`VIZOR_PORT`) are each set once in Task 4/6's template and read consistently by Task 5/6's JS
functions.
