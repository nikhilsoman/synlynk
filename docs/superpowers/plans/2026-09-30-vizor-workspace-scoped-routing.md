# Vizor Workspace-Scoped Slug Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish a secure, hierarchical URL routing engine (`/w/<slug>/api/...`) in Vizor that resolves workspace context strictly server-side, eliminates daemon process CWD dependencies, and ensures full multi-workspace isolation.

**Architecture:** The persistent Vizor daemon intercepts `/w/<slug>/api/...` requests, resolves `<slug>` to an authorized `(repo_path, canonical_path)` pair via `state_registry`, and executes dynamic operations with an immutable `WorkspaceContext`. Frontend templates switch to relative `api/...` fetching, while legacy unscoped `/api/...` endpoints redirect safely.

**Tech Stack:** Python 3.10+, `http.server.SimpleHTTPRequestHandler`, SQLite3 (WAL mode), `unittest` / `pytest`.

**Spec:** [`docs/superpowers/specs/2026-09-30-vizor-workspace-scoped-routing-design.md`](file:///Users/nikhilsoman/dev/synlynk/docs/superpowers/specs/2026-09-30-vizor-workspace-scoped-routing-design.md)

## Global Constraints

- **Server-Side Registry Resolution:** Slug resolution must strictly query `synlynk.state_registry`. No filesystem path from query strings or request headers may ever be trusted.
- **Zero Daemon CWD Coupling:** Handlers must never call `os.getcwd()` or depend on current working directory.
- **Relative URL Invariant:** All client-side fetch calls in Vizor HTML views must use relative paths (`api/...`, no leading slash).
- **Test Isolation:** Integration tests must use temporary directories or mock state registries without mutating live workspace ledgers.

---

### Task 1: `WorkspaceContext` Data Model & Registry Resolver

**Files:**
- Modify: `synlynk/vizor_daemon.py:35-80`
- Test: `tests/test_vizor_workspace_context.py`

**Interfaces:**
- Produces:
  ```python
  @dataclasses.dataclass(frozen=True)
  class WorkspaceContext:
      slug: str
      repo_path: Path
      db_path: Path

  def resolve_workspace_context(slug: str) -> Optional[WorkspaceContext]: ...
  ```

- [ ] **Step 1: Write the failing test**

Create `tests/test_vizor_workspace_context.py`:
```python
import json
from pathlib import Path
import pytest
from synlynk.vizor_daemon import WorkspaceContext, resolve_workspace_context

def test_resolve_workspace_context_valid(tmp_path, monkeypatch):
    reg_file = tmp_path / "product-registry.json"
    repo_dir = tmp_path / "repo_a"
    repo_dir.mkdir()
    db_file = tmp_path / "state.db"
    db_file.write_text("")
    
    registry_data = {
        "products": {
            "demo-app": {
                "slug": "demo-app",
                "repo_path": str(repo_dir),
                "canonical_path": str(db_file),
            }
        },
        "version": 1
    }
    reg_file.write_text(json.dumps(registry_data))
    monkeypatch.setenv("SYNLYNK_REGISTRY_PATH", str(reg_file))

    ctx = resolve_workspace_context("demo-app")
    assert ctx is not None
    assert isinstance(ctx, WorkspaceContext)
    assert ctx.slug == "demo-app"
    assert ctx.repo_path == repo_dir
    assert ctx.db_path == db_file

def test_resolve_workspace_context_rejects_invalid_or_missing(tmp_path, monkeypatch):
    reg_file = tmp_path / "product-registry.json"
    reg_file.write_text(json.dumps({"products": {}, "version": 1}))
    monkeypatch.setenv("SYNLYNK_REGISTRY_PATH", str(reg_file))

    assert resolve_workspace_context("nonexistent") is None
    assert resolve_workspace_context("") is None
    assert resolve_workspace_context("../../etc/passwd") is None
    assert resolve_workspace_context("slug with spaces") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_vizor_workspace_context.py -v`  
Expected: FAIL with `ImportError: cannot import name 'WorkspaceContext' from 'synlynk.vizor_daemon'`

- [ ] **Step 3: Implement minimal code**

In `synlynk/vizor_daemon.py`:
```python
import dataclasses
import re

@dataclasses.dataclass(frozen=True)
class WorkspaceContext:
    slug: str
    repo_path: Path
    db_path: Path

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

    products = data.get("products", {}) if isinstance(data, dict) else {}
    entry = products.get(slug)
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

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_vizor_workspace_context.py -v`  
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add synlynk/vizor_daemon.py tests/test_vizor_workspace_context.py
git commit -m "feat(vizor): add WorkspaceContext and registry resolver

Co-Authored-By: AGY <noreply@antigravity.dev>"
```

---

### Task 2: Context-Aware Board Data & Mutation Operations

**Files:**
- Modify: `synlynk/board.py:90-213`
- Test: `tests/test_board_context_scoping.py`

**Interfaces:**
- Consumes: `WorkspaceContext` from Task 1
- Produces:
  ```python
  def board_data_for_context(
      ctx: WorkspaceContext,
      *,
      repo_id: Optional[str] = None,
      type_id: Optional[str] = None,
      goal_id: Optional[str] = None,
  ) -> dict: ...

  def update_stage_for_context(
      ctx: WorkspaceContext,
      story_id: str,
      stage: str,
  ) -> bool: ...

  def update_status_for_context(
      ctx: WorkspaceContext,
      story_id: str,
      status: str,
  ) -> bool: ...
  ```

- [ ] **Step 1: Write the failing test**

Create `tests/test_board_context_scoping.py`:
```python
import sqlite3
from pathlib import Path
import pytest
from synlynk.vizor_daemon import WorkspaceContext
from synlynk.board import (
    board_data_for_context,
    update_stage_for_context,
    update_status_for_context,
)

@pytest.fixture
def sample_workspace(tmp_path):
    repo_dir = tmp_path / "repo_test"
    repo_dir.mkdir()
    db_path = tmp_path / "state.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE stories (
            id INTEGER PRIMARY KEY,
            story_id TEXT UNIQUE,
            title TEXT,
            status TEXT DEFAULT 'open',
            stage TEXT DEFAULT 'open',
            governs_stage TEXT DEFAULT 'open',
            goal_id TEXT,
            repo_id TEXT,
            type_id TEXT
        )
    """)
    conn.execute("""
        INSERT INTO stories (story_id, title, status, stage, governs_stage, goal_id)
        VALUES ('story-001', 'Test Story', 'open', 'open', 'open', 'goal-123')
    """)
    conn.commit()
    conn.close()
    return WorkspaceContext(slug="test-slug", repo_path=repo_dir, db_path=db_path)

def test_board_data_for_context_reads_explicit_db(sample_workspace):
    res = board_data_for_context(sample_workspace)
    assert res["identity_slug"] == "test-slug"
    assert len(res["cards"]) == 1
    assert res["cards"][0]["story_id"] == "story-001"
    assert res["filters"]["goals"] == ["goal-123"]

def test_update_stage_for_context_mutates_explicit_db(sample_workspace):
    ok = update_stage_for_context(sample_workspace, "story-001", "visualize")
    assert ok is True
    res = board_data_for_context(sample_workspace)
    assert res["cards"][0]["governs_stage"] == "visualize"

def test_update_status_for_context_mutates_explicit_db(sample_workspace):
    ok = update_status_for_context(sample_workspace, "story-001", "in_progress")
    assert ok is True
    res = board_data_for_context(sample_workspace)
    assert res["cards"][0]["status"] == "in_progress"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_board_context_scoping.py -v`  
Expected: FAIL with `ImportError: cannot import name 'board_data_for_context'`

- [ ] **Step 3: Implement minimal code**

In `synlynk/board.py`:
```python
def board_data_for_context(
    ctx: WorkspaceContext,
    *,
    repo_id: Optional[str] = None,
    type_id: Optional[str] = None,
    goal_id: Optional[str] = None,
) -> dict:
    """Return product-scoped board cards using explicit WorkspaceContext."""
    conn = _get_db(db_path=str(ctx.db_path), read_only=True, migrate=False)
    conn.row_factory = sqlite3.Row
    try:
        story_cols = _columns(conn, "stories")
        if not story_cols:
            return {
                "identity_slug": ctx.slug,
                "cards": [],
                "filters": {"repos": [], "types": [], "goals": []},
                "statuses": list(BOARD_STATUSES),
                "governs_stages": list(GOVERNS_STAGES),
            }

        repo_names = _repo_names(ctx.slug)
        has_governs_stage = "governs_stage" in story_cols
        has_goal = "goal_id" in story_cols
        has_repo = "repo_id" in story_cols
        has_type = "type_id" in story_cols

        clauses, params = [], []
        if repo_id and has_repo:
            clauses.append("repo_id = ?")
            params.append(repo_id)
        if type_id and has_type:
            clauses.append("type_id = ?")
            params.append(type_id)
        if goal_id and has_goal:
            clauses.append("goal_id = ?")
            params.append(goal_id)

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        query = f"SELECT * FROM stories {where} ORDER BY id DESC"
        rows = conn.execute(query, params).fetchall()

        cards = []
        repos, types, goals = set(), set(), set()
        for r in rows:
            item = dict(r)
            raw_stage = str(item.get("governs_stage") or item.get("stage") or "open").strip().lower()
            stage = raw_stage if raw_stage in GOVERNS_STAGES else "open"
            raw_status = str(item.get("status") or "open").strip().lower()
            status = raw_status if raw_status in BOARD_STATUSES else "open"
            gid = item.get("goal_id")
            rid = item.get("repo_id")
            tid = item.get("type_id")
            if gid: goals.add(gid)
            if rid: repos.add(rid)
            if tid: types.add(tid)

            cards.append({
                "story_id": item.get("story_id"),
                "title": item.get("title"),
                "status": status,
                "stage": stage,
                "governs_stage": stage,
                "goal_id": gid,
                "repo_id": rid,
                "type_id": tid,
                "repo_name": repo_names.get(str(rid or "")),
                "tracker": _pointer(item, repo_names),
                "pr_url": None,
            })

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


def update_stage_for_context(ctx: WorkspaceContext, story_id: str, stage: str) -> bool:
    stage_val = stage.strip().lower()
    if stage_val not in GOVERNS_STAGES:
        raise ValueError(f"invalid stage: {stage!r}")
    conn = _get_db(db_path=str(ctx.db_path), read_only=False, migrate=False)
    try:
        story_cols = _columns(conn, "stories")
        updates = ["stage=?"]
        params = [stage_val]
        if "governs_stage" in story_cols:
            updates.append("governs_stage=?")
            params.append(stage_val)
        params.append(story_id)
        cur = conn.execute(f"UPDATE stories SET {', '.join(updates)} WHERE story_id = ?", params)
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def update_status_for_context(ctx: WorkspaceContext, story_id: str, status: str) -> bool:
    status_val = status.strip().lower()
    if status_val not in BOARD_STATUSES:
        raise ValueError(f"invalid status: {status!r}")
    conn = _get_db(db_path=str(ctx.db_path), read_only=False, migrate=False)
    try:
        cur = conn.execute("UPDATE stories SET status = ? WHERE story_id = ?", (status_val, story_id))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_board_context_scoping.py -v`  
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add synlynk/board.py tests/test_board_context_scoping.py
git commit -m "feat(board): add context-aware board data and mutation handlers

Co-Authored-By: AGY <noreply@antigravity.dev>"
```

---

### Task 3: Scoped Routing Dispatcher & HTTP Handler in `vizor_daemon.py`

**Files:**
- Modify: `synlynk/vizor_daemon.py:160-230, 520-565`
- Test: `tests/test_vizor_scoped_routing.py`

**Interfaces:**
- Consumes: `resolve_workspace_context` from Task 1, `board_data_for_context` from Task 2
- Handles:
  `GET /w/<slug>/api/board`
  `POST /w/<slug>/api/board/status`
  `POST /w/<slug>/api/board/stage`
  `GET /api/board` (legacy redirect)

- [ ] **Step 1: Write the failing test**

Create `tests/test_vizor_scoped_routing.py`:
```python
import http.server
import json
import sqlite3
import threading
from urllib.request import urlopen, Request
from urllib.error import HTTPError
import pytest
from synlynk.vizor_daemon import build_workspace_routing_handler

@pytest.fixture
def running_test_server(tmp_path, monkeypatch):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    monkeypatch.setattr("synlynk.vizor_daemon.CACHE_ROOT", cache_dir)

    # Setup 2 workspaces in registry
    reg_file = tmp_path / "product-registry.json"
    repo1 = tmp_path / "repo1"
    repo1.mkdir()
    db1 = tmp_path / "db1.sqlite"
    c1 = sqlite3.connect(str(db1))
    c1.execute("CREATE TABLE stories (id INTEGER PRIMARY KEY, story_id TEXT, title TEXT, status TEXT, stage TEXT, governs_stage TEXT, goal_id TEXT, repo_id TEXT, type_id TEXT)")
    c1.execute("INSERT INTO stories (story_id, title) VALUES ('s1', 'Repo 1 Task')")
    c1.commit(); c1.close()

    repo2 = tmp_path / "repo2"
    repo2.mkdir()
    db2 = tmp_path / "db2.sqlite"
    c2 = sqlite3.connect(str(db2))
    c2.execute("CREATE TABLE stories (id INTEGER PRIMARY KEY, story_id TEXT, title TEXT, status TEXT, stage TEXT, governs_stage TEXT, goal_id TEXT, repo_id TEXT, type_id TEXT)")
    c2.execute("INSERT INTO stories (story_id, title) VALUES ('s2', 'Repo 2 Task')")
    c2.commit(); c2.close()

    reg_data = {
        "products": {
            "ws-one": {"slug": "ws-one", "repo_path": str(repo1), "canonical_path": str(db1)},
            "ws-two": {"slug": "ws-two", "repo_path": str(repo2), "canonical_path": str(db2)},
        },
        "version": 1
    }
    reg_file.write_text(json.dumps(reg_data))
    monkeypatch.setenv("SYNLYNK_REGISTRY_PATH", str(reg_file))

    handler_cls = build_workspace_routing_handler()
    server = http.server.HTTPServer(("127.0.0.1", 0), handler_cls)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    yield port
    server.shutdown()
    server.server_close()

def test_scoped_api_board_returns_correct_workspace(running_test_server):
    port = running_test_server
    # Test ws-one
    with urlopen(f"http://127.0.0.1:{port}/w/ws-one/api/board") as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode())
        assert data["identity_slug"] == "ws-one"
        assert len(data["cards"]) == 1
        assert data["cards"][0]["story_id"] == "s1"

    # Test ws-two
    with urlopen(f"http://127.0.0.1:{port}/w/ws-two/api/board") as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode())
        assert data["identity_slug"] == "ws-two"
        assert len(data["cards"]) == 1
        assert data["cards"][0]["story_id"] == "s2"

def test_scoped_api_rejects_unknown_workspace(running_test_server):
    port = running_test_server
    with pytest.raises(HTTPError) as exc:
        urlopen(f"http://127.0.0.1:{port}/w/unknown-ws/api/board")
    assert exc.value.code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_vizor_scoped_routing.py -v`  
Expected: FAIL with 404 or connection error on `/w/ws-one/api/board`

- [ ] **Step 3: Implement minimal code**

In `synlynk/vizor_daemon.py`, enhance `WorkspaceRoutingHandler`:
```python
        def _route_path(self) -> bool:
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(self.path)
            path = parsed.path

            if path in ("", "/"):
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                if self.command == "GET":
                    self.wfile.write(_workspace_index_html().encode("utf-8"))
                return False

            if path.startswith("/w/"):
                remainder = path[len("/w/"):]
                slug, sep, subpath = remainder.partition("/")
                if not sep or not slug:
                    self.send_error(404, "Invalid workspace path")
                    return False

                ctx = resolve_workspace_context(slug)
                if ctx is None:
                    self.send_error(404, f"Unknown workspace: {slug}")
                    return False

                # Route dynamic API calls: /w/<slug>/api/...
                if subpath.startswith("api/"):
                    api_route = subpath[len("api/"):]
                    if api_route == "board":
                        from synlynk.board import board_data_for_context
                        filters = parse_qs(parsed.query)
                        data = board_data_for_context(
                            ctx,
                            repo_id=(filters.get("repo_id") or [None])[0],
                            type_id=(filters.get("type_id") or [None])[0],
                            goal_id=(filters.get("goal_id") or [None])[0],
                        )
                        body = json.dumps(data).encode("utf-8")
                        self.send_response(200)
                        self.send_header("Content-Type", "application/json; charset=utf-8")
                        self.send_header("Content-Length", str(len(body)))
                        self.end_headers()
                        if self.command == "GET":
                            self.wfile.write(body)
                        return False

                    if api_route == "board/stage" and self.command == "POST":
                        from synlynk.board import update_stage_for_context
                        length = int(self.headers.get("Content-Length", 0))
                        payload = json.loads(self.rfile.read(length))
                        ok = update_stage_for_context(ctx, payload["story_id"], payload["stage"])
                        res = json.dumps({"ok": ok}).encode("utf-8")
                        self.send_response(200 if ok else 400)
                        self.send_header("Content-Type", "application/json")
                        self.end_headers()
                        self.wfile.write(res)
                        return False

                    if api_route == "board/status" and self.command == "POST":
                        from synlynk.board import update_status_for_context
                        length = int(self.headers.get("Content-Length", 0))
                        payload = json.loads(self.rfile.read(length))
                        ok = update_status_for_context(ctx, payload["story_id"], payload["status"])
                        res = json.dumps({"ok": ok}).encode("utf-8")
                        self.send_response(200 if ok else 400)
                        self.send_header("Content-Type", "application/json")
                        self.end_headers()
                        self.wfile.write(res)
                        return False

                # Static view routing
                slug, rewritten = parse_workspace_path(path)
                if slug is None:
                    self.send_error(404, "Unknown workspace view")
                    return False
                self.path = rewritten + (("?" + parsed.query) if parsed.query else "")
                return True

            return True

        def do_POST(self):
            if self._route_path():
                super().do_POST()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_vizor_scoped_routing.py -v`  
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add synlynk/vizor_daemon.py tests/test_vizor_scoped_routing.py
git commit -m "feat(vizor): add scoped dynamic API dispatcher to WorkspaceRoutingHandler

Co-Authored-By: AGY <noreply@antigravity.dev>"
```

---

### Task 4: Template Fetch Relative Path Conversion in `viz.py`

**Files:**
- Modify: `synlynk/viz.py:9470-9495`
- Test: `tests/test_vizor_html_relative_routes.py`

**Interfaces:**
- Updates `generate_board_html()` to emit `api/board`, `api/board/status`, `api/board/stage` without leading slash.

- [ ] **Step 1: Write the failing test**

Create `tests/test_vizor_html_relative_routes.py`:
```python
from synlynk.viz import generate_board_html

def test_board_html_uses_relative_api_routes():
    html = generate_board_html(8721)
    # Must use relative paths without leading slash
    assert "fetch('api/board" in html or "fetch(\"api/board" in html
    assert "fetch('api/board/status'" in html or "fetch(\"api/board/status\"" in html
    assert "fetch('api/board/stage'" in html or "fetch(\"api/board/stage\"" in html
    # Must NOT contain hardcoded root paths
    assert "fetch('/api/board" not in html
    assert "fetch('/api/board/status'" not in html
    assert "fetch('/api/board/stage'" not in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_vizor_html_relative_routes.py -v`  
Expected: FAIL with `AssertionError: assert "fetch('/api/board" not in html`

- [ ] **Step 3: Implement minimal code**

In `synlynk/viz.py`, lines ~9470-9495:
Replace:
```javascript
const r=await fetch('/api/board?'+q.toString());
...
const r=await fetch('/api/board/status',{method:'POST' ...
...
const r=await fetch('/api/board/stage',{method:'POST' ...
...
fetch('/api/board').then(r=>r.json()).then(d=>{
```
With:
```javascript
const r=await fetch('api/board?'+q.toString());
...
const r=await fetch('api/board/status',{method:'POST' ...
...
const r=await fetch('api/board/stage',{method:'POST' ...
...
fetch('api/board').then(r=>r.json()).then(d=>{
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_vizor_html_relative_routes.py -v`  
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add synlynk/viz.py tests/test_vizor_html_relative_routes.py
git commit -m "fix(vizor): convert board.html fetch calls to relative api paths

Co-Authored-By: AGY <noreply@antigravity.dev>"
```

---

### Task 5: Multi-Workspace Concurrent Regression Suite

**Files:**
- Test: `tests/test_vizor_multi_workspace_e2e.py`

**Interfaces:**
- Tests live concurrent requests, `CWD = /` immunity, and cross-workspace isolation.

- [ ] **Step 1: Write the integration test**

Create `tests/test_vizor_multi_workspace_e2e.py`:
```python
import concurrent.futures
import http.server
import json
import os
from pathlib import Path
import sqlite3
import threading
from urllib.request import urlopen, Request
import pytest
from synlynk.vizor_daemon import build_workspace_routing_handler

def test_concurrent_multi_workspace_and_root_cwd(tmp_path, monkeypatch):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    monkeypatch.setattr("synlynk.vizor_daemon.CACHE_ROOT", cache_dir)

    # Workspace A: alpha
    repo_a = tmp_path / "alpha_repo"
    repo_a.mkdir()
    db_a = tmp_path / "alpha.db"
    ca = sqlite3.connect(str(db_a))
    ca.execute("CREATE TABLE stories (id INTEGER PRIMARY KEY, story_id TEXT, title TEXT, status TEXT, stage TEXT, governs_stage TEXT, goal_id TEXT, repo_id TEXT, type_id TEXT)")
    ca.execute("INSERT INTO stories (story_id, title, status, stage, governs_stage) VALUES ('alpha-1', 'Alpha Card', 'open', 'open', 'open')")
    ca.commit(); ca.close()

    # Workspace B: beta
    repo_b = tmp_path / "beta_repo"
    repo_b.mkdir()
    db_b = tmp_path / "beta.db"
    cb = sqlite3.connect(str(db_b))
    cb.execute("CREATE TABLE stories (id INTEGER PRIMARY KEY, story_id TEXT, title TEXT, status TEXT, stage TEXT, governs_stage TEXT, goal_id TEXT, repo_id TEXT, type_id TEXT)")
    cb.execute("INSERT INTO stories (story_id, title, status, stage, governs_stage) VALUES ('beta-1', 'Beta Card', 'open', 'open', 'open')")
    cb.commit(); cb.close()

    reg_file = tmp_path / "product-registry.json"
    reg_data = {
        "products": {
            "alpha": {"slug": "alpha", "repo_path": str(repo_a), "canonical_path": str(db_a)},
            "beta": {"slug": "beta", "repo_path": str(repo_b), "canonical_path": str(db_b)},
        },
        "version": 1
    }
    reg_file.write_text(json.dumps(reg_data))
    monkeypatch.setenv("SYNLYNK_REGISTRY_PATH", str(reg_file))

    # Simulate launchd CWD = /
    monkeypatch.chdir("/")

    server = http.server.HTTPServer(("127.0.0.1", 0), build_workspace_routing_handler())
    port = server.server_address[1]
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()

    try:
        def fetch_board(slug):
            url = f"http://127.0.0.1:{port}/w/{slug}/api/board"
            with urlopen(url) as r:
                return json.loads(r.read().decode())

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
            f_alpha = ex.submit(fetch_board, "alpha")
            f_beta = ex.submit(fetch_board, "beta")
            res_alpha = f_alpha.result()
            res_beta = f_beta.result()

        assert res_alpha["identity_slug"] == "alpha"
        assert res_alpha["cards"][0]["story_id"] == "alpha-1"

        assert res_beta["identity_slug"] == "beta"
        assert res_beta["cards"][0]["story_id"] == "beta-1"

        # Mutate alpha stage to execute
        req = Request(
            f"http://127.0.0.1:{port}/w/alpha/api/board/stage",
            data=json.dumps({"story_id": "alpha-1", "stage": "execute"}).encode(),
            headers={"Content-Type": "application/json"}
        )
        with urlopen(req) as r:
            assert r.status == 200

        # Verify alpha updated, beta unaffected
        res_alpha_2 = fetch_board("alpha")
        res_beta_2 = fetch_board("beta")
        assert res_alpha_2["cards"][0]["governs_stage"] == "execute"
        assert res_beta_2["cards"][0]["governs_stage"] == "open"

    finally:
        server.shutdown()
        server.server_close()
```

- [ ] **Step 2: Run test to verify it passes**

Run: `pytest tests/test_vizor_multi_workspace_e2e.py -v`  
Expected: PASS (1 passed)

- [ ] **Step 3: Run the full test suite for vizor**

Run: `pytest tests/test_vizor_workspace_context.py tests/test_board_context_scoping.py tests/test_vizor_scoped_routing.py tests/test_vizor_html_relative_routes.py tests/test_vizor_multi_workspace_e2e.py -v`  
Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_vizor_multi_workspace_e2e.py
git commit -m "test(vizor): add multi-workspace concurrent regression suite with CWD root immunity

Co-Authored-By: AGY <noreply@antigravity.dev>"
```
