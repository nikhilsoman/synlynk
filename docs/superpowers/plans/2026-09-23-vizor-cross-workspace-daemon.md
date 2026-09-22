# Vizor Cross-Workspace Daemon Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Vizor's per-repo, CWD-scoped server with one persistent, OS-supervised background daemon (`synlynk/vizor_daemon.py`) that polls every workspace registered in `~/.synlynk/registry.json`, renders each one's views into `~/.synlynk/vizor-cache/<slug>/`, and serves them all from a single port under path-prefixed URLs (`/w/<slug>/...`).

**Architecture:** A standalone daemon module reuses `synlynk/viz.py`'s existing `generate_viz_data()`, `generate_*_html()`, and `_write_cache()` functions unmodified, by wrapping each per-workspace poll in a context manager that temporarily chdirs into that workspace's repo path and monkeypatches `synlynk.viz._get_db`/`synlynk.viz.VIZ_CACHE_DIR` (a pattern the codebase already uses at `viz.py:577-592` for the same purpose — forcing read-only, explicitly-scoped DB access). HTTP serving is a `WorkspaceRoutingHandler(VizorHandler)` subclass that rewrites `/w/<slug>/...` request paths before delegating to the existing handler. Service lifecycle (install/uninstall/status) writes a launchd plist (macOS) or systemd `--user` unit (Linux) so the OS supervises the process — no custom watchdog.

**Tech Stack:** Python 3 stdlib only (`http.server`, `subprocess`, `threading`, `contextlib`, `json`, `pathlib`) — matches the rest of the codebase, no new dependencies.

---

## File Structure

- **Create:** `synlynk/vizor_daemon.py` — daemon paths/config, `workspace_render_context()`, poll loop (`poll_once()`, `run_forever()`), `WorkspaceRoutingHandler`, launchd/systemd writers, `install()`/`uninstall()`/`status()`.
- **Create:** `tests/test_vizor_daemon.py` — poll loop isolation tests, URL routing tests, lifecycle command tests (temp `HOME`).
- **Modify:** `synlynk/state_registry.py` — `ensure_registered_product()` gains an optional `repo_path` field persisted at creation time.
- **Modify:** `synlynk/__init__.py:1148-1150` — pass `repo_path=_project_root()` into `ensure_registered_product()`, and add an `update_registered_product(slug, repo_path=...)` call so the field self-heals for products registered before this change.
- **Modify:** `synlynk/viz.py` — `get_role_manifest_payload()` embeds `state=<slug>` in `redirect_url` when `project_slug` is given; `cmd_viz()` rewritten to the new thin CLI semantics.
- **Modify:** `synlynk/cli.py` — `viz_parser` gains `--install`/`--uninstall`/`--daemon-status`/`--run-daemon` flags.
- **Modify:** `install.sh` — stop using `exec` for the pipx install so a follow-up `synlynk viz --install` can run.
- **Modify:** `synlynk/upgrade.py` — `upgrade()` calls the same idempotent install step for existing users.

---

### Task 1: Registry entries persist `repo_path`

**Files:**
- Modify: `synlynk/state_registry.py:179-206` (`ensure_registered_product`)
- Modify: `synlynk/__init__.py:1148-1150`
- Test: `tests/test_state_registry.py` (new file if none exists — check first with `ls tests/test_state_registry.py`)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_state_registry.py
import json
from pathlib import Path

import pytest

from synlynk import state_registry


@pytest.fixture
def isolated_registry(tmp_path, monkeypatch):
    reg_path = tmp_path / "registry.json"
    monkeypatch.setenv("SYNLYNK_REGISTRY_PATH", str(reg_path))
    return reg_path


def test_ensure_registered_product_persists_repo_path(isolated_registry, tmp_path):
    db_path = tmp_path / "workspaces" / "acme" / "state.db"
    repo_path = tmp_path / "repos" / "acme"
    repo_path.mkdir(parents=True)

    entry = state_registry.ensure_registered_product(
        "acme", db_path, product_id="pid-1", repo_path=repo_path
    )

    assert entry["repo_path"] == str(repo_path.resolve())
    payload = json.loads(isolated_registry.read_text())
    assert payload["products"]["acme"]["repo_path"] == str(repo_path.resolve())


def test_ensure_registered_product_repo_path_optional(isolated_registry, tmp_path):
    db_path = tmp_path / "workspaces" / "acme" / "state.db"

    entry = state_registry.ensure_registered_product("acme", db_path, product_id="pid-1")

    assert "repo_path" not in entry
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_state_registry.py -v`
Expected: FAIL — `ensure_registered_product() got an unexpected keyword argument 'repo_path'`

- [ ] **Step 3: Implement `repo_path` support**

Replace `synlynk/state_registry.py:179-206`:

```python
def ensure_registered_product(
    slug: str,
    path: Path,
    product_id: Optional[str] = None,
    *,
    repo_path: Optional[Path] = None,
) -> dict:
    """Idempotently register a canonical product path and return its entry."""
    registry = registry_path()
    path = path.expanduser().resolve()
    with registry_lock(registry):
        payload = _read_unlocked(registry)
        products = payload["products"]
        entry = products.get(slug)
        if entry is not None:
            if not isinstance(entry, dict):
                raise StateRegistryError(f"registry entry for {slug!r} is invalid")
            registered_path = Path(str(entry.get("canonical_path", ""))).expanduser().resolve()
            if registered_path != path:
                raise StateRegistryError(
                    f"canonical path mismatch for {slug!r}: registry={registered_path} requested={path}"
                )
            return entry
        entry = {
            "product_id": product_id or _legacy_product_id(slug),
            "slug": slug,
            "canonical_path": str(path),
            "mode": "canonical",
            "lineage_generation": 1,
            "state": "active",
        }
        if repo_path is not None:
            entry["repo_path"] = str(Path(repo_path).expanduser().resolve())
        products[slug] = entry
        _write_unlocked(registry, payload)
        return entry
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_state_registry.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Wire the call site in `synlynk/__init__.py`**

Replace `synlynk/__init__.py:1148-1150`:

```python
                slug = identity_slug_from_config(_project_root())
                repo_root = Path(_project_root())
                entry = ensure_registered_product(
                    slug, Path(path), product_identity(slug, _project_root()), repo_path=repo_root
                )
                if entry.get("repo_path") != str(repo_root.resolve()):
                    from synlynk.state_registry import update_registered_product

                    update_registered_product(slug, repo_path=str(repo_root.resolve()))
```

- [ ] **Step 6: Verify existing registry tests still pass**

Run: `pytest tests/test_state_registry.py -v` (if a pre-existing file was found in Step 0, run that path instead)
Expected: PASS, no regressions

- [ ] **Step 7: Commit**

```bash
git add synlynk/state_registry.py synlynk/__init__.py tests/test_state_registry.py
git commit -m "feat: persist repo_path on registered product entries

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 2: Daemon paths, config, and the workspace render context

**Files:**
- Create: `synlynk/vizor_daemon.py`
- Test: `tests/test_vizor_daemon.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_vizor_daemon.py
import os
from pathlib import Path

import pytest

from synlynk import vizor_daemon


def test_poll_interval_default(monkeypatch):
    monkeypatch.delenv("SYNLYNK_VIZOR_POLL_INTERVAL", raising=False)
    assert vizor_daemon.poll_interval() == 15


def test_poll_interval_override(monkeypatch):
    monkeypatch.setenv("SYNLYNK_VIZOR_POLL_INTERVAL", "5")
    assert vizor_daemon.poll_interval() == 5


def test_poll_interval_invalid_falls_back(monkeypatch):
    monkeypatch.setenv("SYNLYNK_VIZOR_POLL_INTERVAL", "not-a-number")
    assert vizor_daemon.poll_interval() == 15


def test_workspace_render_context_chdirs_and_restores(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    db_path = tmp_path / "state.db"
    db_path.write_bytes(b"")
    original_cwd = os.getcwd()

    seen_cwd = {}
    with vizor_daemon.workspace_render_context(repo, db_path, tmp_path / "cache"):
        seen_cwd["inside"] = Path(os.getcwd())

    assert seen_cwd["inside"] == repo.resolve()
    assert Path(os.getcwd()) == Path(original_cwd)


def test_workspace_render_context_restores_get_db_on_exception(tmp_path):
    import synlynk.viz as viz_module

    repo = tmp_path / "repo"
    repo.mkdir()
    db_path = tmp_path / "state.db"
    db_path.write_bytes(b"")
    original_get_db = viz_module._get_db

    with pytest.raises(RuntimeError):
        with vizor_daemon.workspace_render_context(repo, db_path, tmp_path / "cache"):
            raise RuntimeError("boom")

    assert viz_module._get_db is original_get_db
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_vizor_daemon.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.vizor_daemon'`

- [ ] **Step 3: Write `synlynk/vizor_daemon.py`**

```python
"""Vizor cross-workspace daemon: polls every registered workspace and serves
their rendered views from one persistent, OS-supervised background process.

Standalone from synlynk/daemon.py's WatchDaemon — that daemon is repo-scoped
(pidfile/state resolve via git rev-parse --git-common-dir); this one is
machine-scoped and must not anchor to whichever repo happened to start it.
"""
from __future__ import annotations

import contextlib
import os
from pathlib import Path
from typing import Optional

DAEMON_HOME = Path(os.path.expanduser("~/.synlynk/vizor-daemon"))
PIDFILE = DAEMON_HOME / "pidfile"
PORTFILE = DAEMON_HOME / "port"
LOGFILE = DAEMON_HOME / "daemon.log"
CACHE_ROOT = Path(os.path.expanduser("~/.synlynk/vizor-cache"))
DEFAULT_POLL_INTERVAL = 15


def poll_interval() -> int:
    """Fixed polling interval in seconds, overridable via SYNLYNK_VIZOR_POLL_INTERVAL."""
    raw = os.environ.get("SYNLYNK_VIZOR_POLL_INTERVAL")
    if not raw:
        return DEFAULT_POLL_INTERVAL
    try:
        return int(raw)
    except ValueError:
        return DEFAULT_POLL_INTERVAL


@contextlib.contextmanager
def workspace_render_context(repo_path: Path, db_path: Path, cache_dir: Path):
    """Let unmodified viz.py render functions operate on one workspace at a time.

    generate_viz_data() and _write_cache() are CWD-coupled and read the
    module-global synlynk.viz._get_db / VIZ_CACHE_DIR. This mirrors the
    existing uxcore._get_db monkeypatch-with-restore pattern at viz.py:577-592
    to force read-only, explicitly-scoped DB access and per-slug cache output
    without modifying those functions.
    """
    import synlynk.viz as viz_module

    old_cwd = os.getcwd()
    original_get_db = viz_module._get_db
    original_cache_dir = viz_module.VIZ_CACHE_DIR
    try:
        os.chdir(repo_path)
        viz_module._get_db = lambda *a, **k: viz_module._open_state_db(
            db_path=str(db_path), read_only=True
        )
        viz_module.VIZ_CACHE_DIR = str(cache_dir)
        yield
    finally:
        viz_module._get_db = original_get_db
        viz_module.VIZ_CACHE_DIR = original_cache_dir
        os.chdir(old_cwd)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_vizor_daemon.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add synlynk/vizor_daemon.py tests/test_vizor_daemon.py
git commit -m "feat: add vizor daemon module with workspace render context

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 3: Poll loop over the registry

**Files:**
- Modify: `synlynk/vizor_daemon.py` (append)
- Test: `tests/test_vizor_daemon.py` (append)

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_vizor_daemon.py
import json


def _seed_registry(reg_path, slug, repo_path, db_path):
    reg_path.parent.mkdir(parents=True, exist_ok=True)
    reg_path.write_text(json.dumps({
        "version": 1,
        "products": {
            slug: {
                "product_id": f"pid-{slug}",
                "slug": slug,
                "canonical_path": str(db_path),
                "repo_path": str(repo_path),
                "mode": "canonical",
                "lineage_generation": 1,
                "state": "active",
            }
        },
    }))


def test_poll_once_writes_cache_per_workspace(tmp_path, monkeypatch):
    monkeypatch.setenv("SYNLYNK_REGISTRY_PATH", str(tmp_path / "registry.json"))

    repo_a = tmp_path / "repo-a"
    repo_a.mkdir()
    (repo_a / ".synlynk").mkdir()
    (repo_a / ".synlynk" / "config.json").write_text(json.dumps({"identity_slug": "a"}))
    db_a = tmp_path / "a-state.db"
    db_a.write_bytes(b"")

    reg_path = tmp_path / "registry.json"
    _seed_registry(reg_path, "a", repo_a, db_a)

    cache_root = tmp_path / "cache-root"
    monkeypatch.setattr("synlynk.vizor_daemon.CACHE_ROOT", cache_root)

    def fake_generate_viz_data():
        return {
            "workspace": {"name": "a", "updated_at": "now", "repos": []},
            "notes": {},
            "workspace_map": {"edges": [], "edge_types": {}},
            "observatory": {},
        }

    import synlynk.viz as viz_module
    monkeypatch.setattr(viz_module, "generate_viz_data", fake_generate_viz_data)

    from synlynk import vizor_daemon
    results = vizor_daemon.poll_once(port=8721)

    assert results == {"a": "ok"}
    assert (cache_root / "a" / "manifest.json").exists()


def test_poll_once_isolates_failures(tmp_path, monkeypatch):
    monkeypatch.setenv("SYNLYNK_REGISTRY_PATH", str(tmp_path / "registry.json"))

    repo_a = tmp_path / "repo-a"
    repo_a.mkdir()
    repo_b = tmp_path / "repo-b"
    repo_b.mkdir()
    db_a = tmp_path / "a-state.db"
    db_a.write_bytes(b"")
    db_b = tmp_path / "b-state.db"
    db_b.write_bytes(b"")

    reg_path = tmp_path / "registry.json"
    reg_path.write_text(json.dumps({
        "version": 1,
        "products": {
            "a": {
                "product_id": "pid-a", "slug": "a", "canonical_path": str(db_a),
                "repo_path": str(repo_a), "mode": "canonical",
                "lineage_generation": 1, "state": "active",
            },
            "b": {
                "product_id": "pid-b", "slug": "b", "canonical_path": str(db_b),
                "repo_path": str(repo_b), "mode": "canonical",
                "lineage_generation": 1, "state": "active",
            },
        },
    }))

    cache_root = tmp_path / "cache-root"
    monkeypatch.setattr("synlynk.vizor_daemon.CACHE_ROOT", cache_root)

    import synlynk.viz as viz_module

    def flaky_generate_viz_data():
        if Path(os.getcwd()) == repo_a.resolve():
            raise RuntimeError("boom")
        return {
            "workspace": {"name": "b", "updated_at": "now", "repos": []},
            "notes": {},
            "workspace_map": {"edges": [], "edge_types": {}},
            "observatory": {},
        }

    monkeypatch.setattr(viz_module, "generate_viz_data", flaky_generate_viz_data)

    from synlynk import vizor_daemon
    results = vizor_daemon.poll_once(port=8721)

    assert results["a"].startswith("error:")
    assert results["b"] == "ok"
    assert (cache_root / "b" / "manifest.json").exists()
```

Add `import os` and `from pathlib import Path` at the top of `tests/test_vizor_daemon.py` if not already present from Task 2's test file.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_vizor_daemon.py -k poll_once -v`
Expected: FAIL with `AttributeError: module 'synlynk.vizor_daemon' has no attribute 'poll_once'`

- [ ] **Step 3: Implement the poll loop**

Append to `synlynk/vizor_daemon.py`:

```python
def _registered_workspaces() -> dict:
    """Return {slug: entry} for every registered product, or {} if no registry yet."""
    from synlynk.state_registry import _read_unlocked, registry_path

    path = registry_path()
    if not path.exists():
        return {}
    payload = _read_unlocked(path)
    return payload.get("products", {})


def refresh_workspace(slug: str, entry: dict, port: int) -> None:
    """Render one workspace's views into CACHE_ROOT/<slug>/. Raises on failure."""
    import synlynk.viz as viz_module

    repo_path = entry.get("repo_path")
    db_path = entry.get("canonical_path")
    if not repo_path or not db_path:
        raise RuntimeError(f"workspace {slug!r} is missing repo_path or canonical_path")

    cache_dir = CACHE_ROOT / slug
    with workspace_render_context(Path(repo_path), Path(db_path), cache_dir):
        data = viz_module.generate_viz_data()
        viz_module._write_cache(data, port)


def poll_once(port: int) -> dict:
    """Refresh every registered workspace once. Never lets one failure stop another."""
    results = {}
    for slug, entry in _registered_workspaces().items():
        if not isinstance(entry, dict):
            continue
        try:
            refresh_workspace(slug, entry, port)
            results[slug] = "ok"
        except Exception as exc:
            results[slug] = f"error: {exc}"
            _log(f"refresh failed for {slug!r}: {exc}")
    return results


def _log(message: str) -> None:
    import time

    DAEMON_HOME.mkdir(parents=True, exist_ok=True)
    with open(LOGFILE, "a") as f:
        f.write(f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} {message}\n")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_vizor_daemon.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add synlynk/vizor_daemon.py tests/test_vizor_daemon.py
git commit -m "feat: add per-workspace poll loop with failure isolation

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 4: `WorkspaceRoutingHandler` for `/w/<slug>/...` URLs

**Files:**
- Modify: `synlynk/vizor_daemon.py` (append)
- Test: `tests/test_vizor_daemon.py` (append)

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_vizor_daemon.py
def test_resolve_slug_from_path_valid(tmp_path, monkeypatch):
    from synlynk import vizor_daemon

    monkeypatch.setattr(vizor_daemon, "_known_slugs", lambda: {"acme"})
    slug, rest = vizor_daemon.parse_workspace_path("/w/acme/overview.html")
    assert slug == "acme"
    assert rest == "/acme/overview.html"


def test_resolve_slug_from_path_unknown_slug(monkeypatch):
    from synlynk import vizor_daemon

    monkeypatch.setattr(vizor_daemon, "_known_slugs", lambda: {"acme"})
    slug, rest = vizor_daemon.parse_workspace_path("/w/ghost/overview.html")
    assert slug is None
    assert rest is None


def test_resolve_slug_from_path_non_workspace_path(monkeypatch):
    from synlynk import vizor_daemon

    monkeypatch.setattr(vizor_daemon, "_known_slugs", lambda: {"acme"})
    slug, rest = vizor_daemon.parse_workspace_path("/onboarding")
    assert slug is None
    assert rest is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_vizor_daemon.py -k resolve_slug -v`
Expected: FAIL with `AttributeError: module 'synlynk.vizor_daemon' has no attribute 'parse_workspace_path'`

- [ ] **Step 3: Implement routing helpers and the handler**

Append to `synlynk/vizor_daemon.py`:

```python
def _known_slugs() -> set:
    return set(_registered_workspaces().keys())


def parse_workspace_path(path: str):
    """Split '/w/<slug>/rest' into (slug, '/<slug>/rest'), or (None, None).

    The rewritten path keeps the slug segment so it maps 1:1 onto
    CACHE_ROOT/<slug>/... when SimpleHTTPRequestHandler joins it against
    directory=str(CACHE_ROOT).
    """
    if not path.startswith("/w/"):
        return None, None
    remainder = path[len("/w/"):]
    slug = remainder.split("/", 1)[0]
    if not slug or slug not in _known_slugs():
        return None, None
    return slug, "/" + remainder


def _workspace_index_html() -> str:
    slugs = sorted(_known_slugs())
    if not slugs:
        return "<html><body><p>No workspaces registered yet.</p></body></html>"
    items = "".join(f'<li><a href="/w/{s}/overview.html">{s}</a></li>' for s in slugs)
    return f"<html><body><ul>{items}</ul></body></html>"


def build_workspace_routing_handler():
    """Return a WorkspaceRoutingHandler class bound to the current VizorHandler.

    Deferred import: synlynk.viz is heavy and importing it at vizor_daemon
    module load time would pull HTTP-serving machinery into every caller
    (including tests that only need poll_once/registry helpers).
    """
    from synlynk.viz import VizorHandler

    class WorkspaceRoutingHandler(VizorHandler):
        def __init__(self, *args, **kwargs):
            http_server_module = __import__("http.server", fromlist=["SimpleHTTPRequestHandler"])
            http_server_module.SimpleHTTPRequestHandler.__init__(
                self, *args, directory=str(CACHE_ROOT), **kwargs
            )

        def do_GET(self):
            from urllib.parse import urlparse

            path = urlparse(self.path).path
            if path == "/" or path == "":
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(_workspace_index_html().encode("utf-8"))
                return
            if path.startswith("/w/"):
                slug, rewritten = parse_workspace_path(path)
                if slug is None:
                    self.send_error(404, "Unknown workspace")
                    return
                self.path = rewritten + (("?" + urlparse(self.path).query) if urlparse(self.path).query else "")
                super().do_GET()
                return
            super().do_GET()

    return WorkspaceRoutingHandler
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_vizor_daemon.py -v`
Expected: PASS (10 tests)

- [ ] **Step 5: Add a routing integration test**

```python
# append to tests/test_vizor_daemon.py
def test_workspace_index_lists_registered_slugs(monkeypatch):
    from synlynk import vizor_daemon

    monkeypatch.setattr(vizor_daemon, "_known_slugs", lambda: {"acme", "beta"})
    html = vizor_daemon._workspace_index_html()
    assert "acme" in html and "beta" in html


def test_workspace_index_empty():
    from synlynk import vizor_daemon

    html = vizor_daemon._workspace_index_html.__wrapped__() if hasattr(
        vizor_daemon._workspace_index_html, "__wrapped__"
    ) else None
```

Replace the second test above (it's a placeholder that doesn't assert anything useful) with:

```python
def test_workspace_index_empty(monkeypatch):
    from synlynk import vizor_daemon

    monkeypatch.setattr(vizor_daemon, "_known_slugs", lambda: set())
    html = vizor_daemon._workspace_index_html()
    assert "No workspaces registered" in html
```

Run: `pytest tests/test_vizor_daemon.py -v`
Expected: PASS (12 tests)

- [ ] **Step 6: Commit**

```bash
git add synlynk/vizor_daemon.py tests/test_vizor_daemon.py
git commit -m "feat: add workspace-scoped URL routing handler

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 5: Daemon entrypoint — `run_forever()` and pidfile/port bookkeeping

**Files:**
- Modify: `synlynk/vizor_daemon.py` (append)
- Test: `tests/test_vizor_daemon.py` (append)

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_vizor_daemon.py
def test_write_and_read_pidfile(tmp_path, monkeypatch):
    from synlynk import vizor_daemon

    monkeypatch.setattr(vizor_daemon, "DAEMON_HOME", tmp_path)
    monkeypatch.setattr(vizor_daemon, "PIDFILE", tmp_path / "pidfile")
    monkeypatch.setattr(vizor_daemon, "PORTFILE", tmp_path / "port")

    vizor_daemon._write_state(pid=1234, port=8721)

    assert vizor_daemon._read_pid() == 1234
    assert vizor_daemon._read_port() == 8721


def test_read_pid_missing_returns_none(tmp_path, monkeypatch):
    from synlynk import vizor_daemon

    monkeypatch.setattr(vizor_daemon, "PIDFILE", tmp_path / "nope")
    assert vizor_daemon._read_pid() is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_vizor_daemon.py -k pidfile -v`
Expected: FAIL with `AttributeError: module 'synlynk.vizor_daemon' has no attribute '_write_state'`

- [ ] **Step 3: Implement state bookkeeping and the run loop**

Append to `synlynk/vizor_daemon.py`:

```python
def _write_state(pid: int, port: int) -> None:
    DAEMON_HOME.mkdir(parents=True, exist_ok=True)
    PIDFILE.write_text(str(pid))
    PORTFILE.write_text(str(port))


def _read_pid() -> Optional[int]:
    try:
        return int(PIDFILE.read_text().strip())
    except (FileNotFoundError, ValueError):
        return None


def _read_port() -> Optional[int]:
    try:
        return int(PORTFILE.read_text().strip())
    except (FileNotFoundError, ValueError):
        return None


def is_running() -> bool:
    pid = _read_pid()
    if pid is None:
        return False
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False
    except OSError:
        return False


def run_forever(port: Optional[int] = None) -> None:
    """Daemon entrypoint: serve forever, refreshing every registered workspace on a timer."""
    import http.server
    import threading
    import time

    from synlynk.viz import DEFAULT_PORT

    resolved_port = port or DEFAULT_PORT
    CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    handler_cls = build_workspace_routing_handler()
    server = http.server.HTTPServer(("127.0.0.1", resolved_port), handler_cls)
    _write_state(pid=os.getpid(), port=resolved_port)
    _log(f"daemon starting on port {resolved_port}")

    stop_event = threading.Event()

    def _poll_loop():
        while not stop_event.is_set():
            poll_once(resolved_port)
            stop_event.wait(poll_interval())

    poll_thread = threading.Thread(target=_poll_loop, daemon=True)
    poll_thread.start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop_event.set()
        server.shutdown()
        server.server_close()
        _log("daemon stopped")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_vizor_daemon.py -v`
Expected: PASS (14 tests)

- [ ] **Step 5: Commit**

```bash
git add synlynk/vizor_daemon.py tests/test_vizor_daemon.py
git commit -m "feat: add vizor daemon run_forever entrypoint and pid/port state

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 6: launchd/systemd install, uninstall, status

**Files:**
- Modify: `synlynk/vizor_daemon.py` (append)
- Test: `tests/test_vizor_daemon.py` (append)

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_vizor_daemon.py
def test_launchd_plist_path(monkeypatch, tmp_path):
    from synlynk import vizor_daemon

    monkeypatch.setattr(vizor_daemon.os.path, "expanduser", lambda p: str(tmp_path) + p[1:] if p.startswith("~") else p)
    path = vizor_daemon._launchd_plist_path()
    assert str(path).endswith("Library/LaunchAgents/com.synlynk.vizor-daemon.plist")


def test_systemd_unit_path(monkeypatch, tmp_path):
    from synlynk import vizor_daemon

    monkeypatch.setattr(vizor_daemon.os.path, "expanduser", lambda p: str(tmp_path) + p[1:] if p.startswith("~") else p)
    path = vizor_daemon._systemd_unit_path()
    assert str(path).endswith(".config/systemd/user/synlynk-vizor-daemon.service")


def test_install_writes_unit_and_starts(tmp_path, monkeypatch):
    from synlynk import vizor_daemon

    monkeypatch.setattr(vizor_daemon, "platform_name", lambda: "Darwin")
    monkeypatch.setattr(vizor_daemon, "_launchd_plist_path", lambda: tmp_path / "com.synlynk.vizor-daemon.plist")
    calls = []
    monkeypatch.setattr(vizor_daemon.subprocess, "run", lambda *a, **k: calls.append(a) or type("R", (), {"returncode": 0})())

    result = vizor_daemon.install()

    assert result["installed"] is True
    assert (tmp_path / "com.synlynk.vizor-daemon.plist").exists()
    assert calls, "expected launchctl load to be invoked"


def test_status_reports_not_installed(tmp_path, monkeypatch):
    from synlynk import vizor_daemon

    monkeypatch.setattr(vizor_daemon, "_launchd_plist_path", lambda: tmp_path / "missing.plist")
    monkeypatch.setattr(vizor_daemon, "_systemd_unit_path", lambda: tmp_path / "missing.service")
    monkeypatch.setattr(vizor_daemon, "is_running", lambda: False)

    status = vizor_daemon.status()

    assert status["service_registered"] is False
    assert status["running"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_vizor_daemon.py -k "launchd or systemd or install_writes or status_reports" -v`
Expected: FAIL with `AttributeError: module 'synlynk.vizor_daemon' has no attribute '_launchd_plist_path'`

- [ ] **Step 3: Implement lifecycle commands**

Append to `synlynk/vizor_daemon.py`:

```python
import platform as _platform_module
import subprocess
import sys


def platform_name() -> str:
    return _platform_module.system()


def _launchd_plist_path() -> Path:
    return Path(os.path.expanduser("~/Library/LaunchAgents/com.synlynk.vizor-daemon.plist"))


def _systemd_unit_path() -> Path:
    return Path(os.path.expanduser("~/.config/systemd/user/synlynk-vizor-daemon.service"))


_LAUNCHD_LABEL = "com.synlynk.vizor-daemon"
_SYSTEMD_UNIT_NAME = "synlynk-vizor-daemon.service"


def _launchd_plist_contents(python_exe: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{_LAUNCHD_LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{python_exe}</string>
        <string>-m</string>
        <string>synlynk.vizor_daemon</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>{LOGFILE}</string>
    <key>StandardErrorPath</key>
    <string>{LOGFILE}</string>
</dict>
</plist>
"""


def _systemd_unit_contents(python_exe: str) -> str:
    return f"""[Unit]
Description=synlynk Vizor cross-workspace daemon

[Service]
ExecStart={python_exe} -m synlynk.vizor_daemon
Restart=on-failure

[Install]
WantedBy=default.target
"""


def install() -> dict:
    """Write and load/enable the OS service unit, starting the daemon immediately."""
    python_exe = sys.executable
    system = platform_name()
    if system == "Darwin":
        plist_path = _launchd_plist_path()
        plist_path.parent.mkdir(parents=True, exist_ok=True)
        plist_path.write_text(_launchd_plist_contents(python_exe))
        subprocess.run(["launchctl", "load", str(plist_path)], capture_output=True, text=True)
        return {"installed": True, "manager": "launchd", "unit_path": str(plist_path)}
    elif system == "Linux":
        unit_path = _systemd_unit_path()
        unit_path.parent.mkdir(parents=True, exist_ok=True)
        unit_path.write_text(_systemd_unit_contents(python_exe))
        subprocess.run(["systemctl", "--user", "enable", "--now", _SYSTEMD_UNIT_NAME],
                        capture_output=True, text=True)
        return {"installed": True, "manager": "systemd", "unit_path": str(unit_path)}
    return {"installed": False, "reason": f"unsupported platform: {system}"}


def uninstall() -> dict:
    """Unload/disable the service unit and remove it."""
    system = platform_name()
    if system == "Darwin":
        plist_path = _launchd_plist_path()
        if plist_path.exists():
            subprocess.run(["launchctl", "unload", str(plist_path)], capture_output=True, text=True)
            plist_path.unlink()
        return {"uninstalled": True, "manager": "launchd"}
    elif system == "Linux":
        unit_path = _systemd_unit_path()
        subprocess.run(["systemctl", "--user", "disable", "--now", _SYSTEMD_UNIT_NAME],
                        capture_output=True, text=True)
        if unit_path.exists():
            unit_path.unlink()
        return {"uninstalled": True, "manager": "systemd"}
    return {"uninstalled": False, "reason": f"unsupported platform: {system}"}


def status() -> dict:
    """Report whether the service is registered/running, its port, and pidfile state."""
    system = platform_name()
    registered = (
        _launchd_plist_path().exists() if system == "Darwin"
        else _systemd_unit_path().exists() if system == "Linux"
        else False
    )
    return {
        "platform": system,
        "service_registered": registered,
        "running": is_running(),
        "pid": _read_pid(),
        "port": _read_port(),
    }


if __name__ == "__main__":
    run_forever()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_vizor_daemon.py -v`
Expected: PASS (18 tests)

- [ ] **Step 5: Commit**

```bash
git add synlynk/vizor_daemon.py tests/test_vizor_daemon.py
git commit -m "feat: add launchd/systemd install, uninstall, status commands

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 7: OAuth callback workspace-carry

**Files:**
- Modify: `synlynk/viz.py:5058-5119` (`get_role_manifest_payload`)
- Modify: `synlynk/viz.py:5632-5647` (`/auth/callback` handler, inside `VizorHandler.do_GET`)
- Test: `tests/test_viz.py`

- [ ] **Step 1: Write the failing test**

Check existing conventions first: `grep -n "get_role_manifest_payload" tests/test_viz.py`. Add:

```python
# append to tests/test_viz.py
def test_get_role_manifest_payload_embeds_state_when_slug_given():
    from synlynk.viz import get_role_manifest_payload

    payload = get_role_manifest_payload("qa", port=8721, project_slug="acme")
    assert "state=acme" in payload["redirect_url"]


def test_get_role_manifest_payload_omits_state_without_slug():
    from synlynk.viz import get_role_manifest_payload

    payload = get_role_manifest_payload("qa", port=8721)
    assert "state=" not in payload["redirect_url"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_viz.py -k get_role_manifest_payload_embeds -v`
Expected: FAIL — `assert "state=acme" in payload["redirect_url"]` fails (no `state` param today)

- [ ] **Step 3: Implement the redirect_url change**

In `synlynk/viz.py`, replace line 5115:

```python
        "redirect_url": (
            f"http://localhost:{port}/auth/callback?role={role}&state={slug}"
            if project_slug else f"http://localhost:{port}/auth/callback?role={role}"
        ),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_viz.py -k get_role_manifest_payload_embeds -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Update the callback handler to redirect back to the workspace**

Replace `synlynk/viz.py:5632-5647`:

```python
        if path == "/auth/callback":
            params = parse_qs(parsed.query)
            code = params.get("code", [""])[0]
            role = params.get("role", [""])[0] or "qa"
            state_slug = params.get("state", [""])[0]
            redirect_target = (
                f"/w/{state_slug}/onboarding/roles?success={role}"
                if state_slug else f"/onboarding/roles?success={role}"
            )
            if code:
                try:
                    handle_github_app_conversion(code=code, role=role)
                    self.send_response(302)
                    self.send_header("Location", redirect_target)
                    self.end_headers()
                    return
                except Exception as e:
                    self.send_error(500, f"GitHub App conversion error: {e}")
                    return
            self.send_error(400, "Missing code query param")
            return
```

- [ ] **Step 6: Run the full viz test suite**

Run: `pytest tests/test_viz.py -v`
Expected: PASS, no regressions

- [ ] **Step 7: Commit**

```bash
git add synlynk/viz.py tests/test_viz.py
git commit -m "feat: carry initiating workspace slug through OAuth callback

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 8: Rewrite `cmd_viz()` to thin browser-open semantics

**Files:**
- Modify: `synlynk/viz.py:6104-6166` (`cmd_viz`)
- Modify: `synlynk/cli.py:1465-1478` (`viz_parser`)
- Modify: `synlynk/cli.py:2535-2536` (dispatch, unchanged signature — still `cmd_viz(args)`)
- Test: `tests/test_viz.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_viz.py
import argparse


def test_cmd_viz_opens_browser_to_workspace_url(monkeypatch):
    from synlynk import viz

    opened = {}
    monkeypatch.setattr(viz.webbrowser, "open", lambda url: opened.setdefault("url", url))
    monkeypatch.setattr(viz, "_current_workspace_slug", lambda: "acme")
    monkeypatch.setattr(viz.vizor_daemon, "is_running", lambda: True)
    monkeypatch.setattr(viz.vizor_daemon, "_read_port", lambda: 8721)

    args = argparse.Namespace(hosted=False, install=False, uninstall=False, daemon_status=False)
    viz.cmd_viz(args)

    assert opened["url"] == "http://localhost:8721/w/acme/overview.html"


def test_cmd_viz_prints_hint_when_daemon_not_running(monkeypatch, capsys):
    from synlynk import viz

    monkeypatch.setattr(viz, "_current_workspace_slug", lambda: "acme")
    monkeypatch.setattr(viz.vizor_daemon, "is_running", lambda: False)

    args = argparse.Namespace(hosted=False, install=False, uninstall=False, daemon_status=False)
    viz.cmd_viz(args)

    out = capsys.readouterr().out
    assert "synlynk viz --install" in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_viz.py -k cmd_viz_opens -v`
Expected: FAIL — old `cmd_viz` reads `.synlynk/config.json` and calls `generate_viz_data()`/`_write_cache()` directly, no `vizor_daemon` reference exists yet in `viz.py`

- [ ] **Step 3: Implement the new `cmd_viz()`**

Replace `synlynk/viz.py:6104-6166` in full:

```python
def _current_workspace_slug() -> str:
    from synlynk.product_store import identity_slug_from_config

    return identity_slug_from_config(".")


def cmd_viz(args) -> None:
    """Entry point for `synlynk viz` subcommand."""
    from synlynk import vizor_daemon

    if getattr(args, "hosted", False):
        from synlynk.product_store import identity_slug_from_config
        from synlynk.wave6 import hosted_vizor_placeholder
        print(json.dumps(hosted_vizor_placeholder(identity_slug_from_config(".")), indent=2))
        return

    if getattr(args, "install", False):
        result = vizor_daemon.install()
        if result.get("installed"):
            print(f"  ✓ Vizor daemon installed via {result['manager']} ({result['unit_path']})")
        else:
            print(f"  ✗ Install failed: {result.get('reason', 'unknown error')}")
        return

    if getattr(args, "uninstall", False):
        result = vizor_daemon.uninstall()
        if result.get("uninstalled"):
            print(f"  ✓ Vizor daemon uninstalled ({result['manager']})")
        else:
            print(f"  ✗ Uninstall failed: {result.get('reason', 'unknown error')}")
        return

    if getattr(args, "daemon_status", False):
        status = vizor_daemon.status()
        print(json.dumps(status, indent=2))
        return

    slug = _current_workspace_slug()
    if not vizor_daemon.is_running():
        print("  ✗ Vizor daemon is not running.")
        print("  Run: synlynk viz --install")
        print("  Or check: synlynk viz --daemon-status")
        return

    port = vizor_daemon._read_port() or DEFAULT_PORT
    url = f"http://localhost:{port}/w/{slug}/overview.html"
    webbrowser.open(url)
    print(f"  ✓ Opened {url}")
```

Add the import near the top of `synlynk/viz.py` (after the existing `from synlynk.viz_views import build_workspace_views_snapshot` line):

```python
from synlynk import vizor_daemon
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_viz.py -k cmd_viz -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Update the CLI parser**

Replace `synlynk/cli.py:1465-1478`:

```python
    viz_parser = subparsers.add_parser("viz", help="Open Vizor dashboard for this workspace")
    viz_parser.add_argument("--install", action="store_true",
                            help="Install the Vizor daemon as an OS-supervised background service")
    viz_parser.add_argument("--uninstall", action="store_true",
                            help="Uninstall the Vizor daemon service")
    viz_parser.add_argument("--daemon-status", action="store_true",
                            help="Report Vizor daemon install/running state")
    viz_parser.add_argument("--hosted", action="store_true",
                            help="Show the fail-closed hosted Vizor placeholder")
```

- [ ] **Step 6: Run the full CLI + viz test suites**

Run: `pytest tests/test_viz.py tests/test_cli.py -v`
Expected: PASS. If any pre-existing test asserts on the retired `--serve`/`--generate`/`--open`/`--stop`/`--port` flags or the old `cmd_viz` cache-write behavior, update or remove that test — the spec's CLI-semantics section explicitly retires that code path rather than keeping it alongside the new one.

- [ ] **Step 7: Commit**

```bash
git add synlynk/viz.py synlynk/cli.py tests/test_viz.py
git commit -m "feat: replace cmd_viz with thin daemon-backed browser-open semantics

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 9: `install.sh` and `synlynk upgrade` auto-install the daemon

**Files:**
- Modify: `install.sh`
- Modify: `synlynk/upgrade.py:105-157` (`upgrade`)
- Test: `tests/test_upgrade.py` (check `ls tests/test_upgrade.py` first; create if absent)

- [ ] **Step 1: Read `install.sh` to confirm the exact `exec` line before editing**

Run: `grep -n "exec pipx install" install.sh`

- [ ] **Step 2: Replace the `exec` call in `install.sh`**

Change:
```bash
exec pipx install git+https://github.com/nikhilsoman/synlynk
```
(or the `--force` variant, matching whatever the grep in Step 1 showed) to:
```bash
pipx install git+https://github.com/nikhilsoman/synlynk
synlynk viz --install || true
```

- [ ] **Step 3: Write the failing test for `upgrade.py`**

```python
# tests/test_upgrade.py
def test_upgrade_installs_vizor_daemon_on_success(monkeypatch, capsys):
    import synlynk.upgrade as upgrade_module

    monkeypatch.setattr(upgrade_module.subprocess, "run", lambda *a, **k: type(
        "R", (), {"returncode": 0, "stdout": "v99.0.0"}
    )())
    calls = []
    monkeypatch.setattr(upgrade_module, "_ensure_vizor_daemon_installed", lambda: calls.append(1))
    monkeypatch.setattr(upgrade_module, "_run_upgrade", lambda latest: None)
    monkeypatch.setattr(upgrade_module, "_warn_stale_script_install", lambda: None)

    upgrade_module.upgrade(dry_run=False)

    assert calls == [1]


def test_upgrade_dry_run_skips_daemon_install(monkeypatch):
    import synlynk.upgrade as upgrade_module

    calls = []
    monkeypatch.setattr(upgrade_module, "_ensure_vizor_daemon_installed", lambda: calls.append(1))

    upgrade_module.upgrade(dry_run=True)

    assert calls == []
```

- [ ] **Step 4: Run test to verify it fails**

Run: `pytest tests/test_upgrade.py -v`
Expected: FAIL with `AttributeError: module 'synlynk.upgrade' has no attribute '_ensure_vizor_daemon_installed'`

- [ ] **Step 5: Implement the idempotent install hook**

In `synlynk/upgrade.py`, add after `_warn_stale_script_install` (before `def upgrade`):

```python
def _ensure_vizor_daemon_installed() -> None:
    """Idempotently register the Vizor daemon service for existing installs."""
    try:
        from synlynk import vizor_daemon

        if vizor_daemon.status().get("service_registered"):
            return
        vizor_daemon.install()
    except Exception:
        pass
```

Replace the `finally` block at the end of `upgrade()` (currently `finally: warn_stale_script_install()`):

```python
    finally:
        warn_stale_script_install()
        package = sys.modules.get("synlynk")
        ensure_vizor_daemon_installed = getattr(
            package, "_ensure_vizor_daemon_installed", _ensure_vizor_daemon_installed
        )
        ensure_vizor_daemon_installed()
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/test_upgrade.py -v`
Expected: PASS (2 tests)

- [ ] **Step 7: Commit**

```bash
git add install.sh synlynk/upgrade.py tests/test_upgrade.py
git commit -m "feat: auto-install vizor daemon on fresh install and upgrade

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 10: Lifecycle command tests against a temp HOME

**Files:**
- Modify: `tests/test_vizor_daemon.py` (append)

- [ ] **Step 1: Write the test**

```python
# append to tests/test_vizor_daemon.py
def test_install_uninstall_use_home_relative_paths(tmp_path, monkeypatch):
    from synlynk import vizor_daemon

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(vizor_daemon, "platform_name", lambda: "Darwin")
    monkeypatch.setattr(vizor_daemon.subprocess, "run", lambda *a, **k: type("R", (), {"returncode": 0})())

    result = vizor_daemon.install()
    plist_path = Path(os.path.expanduser("~/Library/LaunchAgents/com.synlynk.vizor-daemon.plist"))

    assert result["installed"] is True
    assert plist_path.exists()

    uninstall_result = vizor_daemon.uninstall()
    assert uninstall_result["uninstalled"] is True
    assert not plist_path.exists()
```

Note: `_launchd_plist_path()` reads `os.path.expanduser("~/...")` fresh each call, so setting `HOME` via `monkeypatch.setenv` before calling `install()`/`uninstall()` is sufficient — no need to monkeypatch the path functions themselves in this test, unlike Task 6's unit tests which isolate the path computation directly.

- [ ] **Step 2: Run test to verify it fails, then implement if needed**

Run: `pytest tests/test_vizor_daemon.py -k install_uninstall_use_home -v`
Expected: This should already PASS given Task 6's implementation (`_launchd_plist_path()` already calls `os.path.expanduser` fresh, and `install()`/`uninstall()` call it, not a cached value). If it fails, the bug is that `install()`/`uninstall()` cached `_launchd_plist_path()`'s result somewhere at import time — confirm `_launchd_plist_path()` is called, not memoized, inside both functions.

- [ ] **Step 3: Run the full daemon test suite**

Run: `pytest tests/test_vizor_daemon.py -v`
Expected: PASS (19 tests)

- [ ] **Step 4: Commit**

```bash
git add tests/test_vizor_daemon.py
git commit -m "test: verify vizor daemon lifecycle commands respect temp HOME

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage:**
- Section 1 (Process & lifecycle) → Tasks 2, 5, 6, 9.
- Section 2 (Refresh loop) → Tasks 1, 2, 3.
- Section 3 (HTTP serving & URL scheme) → Task 4.
- Section 4 (OAuth callback workspace-carry) → Task 7.
- Section 5 (CLI semantics) → Task 8.
- Section 6 (Testing) → every task's own test steps + Task 10's temp-HOME isolation.
- Non-goal "no `state.db`/registry format changes" respected: Task 1 only adds an optional field via the registry's existing generic-update mechanism, no schema migration.
- Non-goal "no changes to `synlynk/daemon.py`" respected: `vizor_daemon.py` is fully standalone, confirmed by grep — no import of `synlynk.daemon` anywhere in this plan.

**Placeholder scan:** No TBD/TODO markers; every step has literal code or an exact command with expected output.

**Type/signature consistency:** `ensure_registered_product(slug, path, product_id=None, *, repo_path=None)` (Task 1) is called with the same keyword shape in `__init__.py` (Task 1, Step 5). `workspace_render_context(repo_path, db_path, cache_dir)` (Task 2) is called identically in `refresh_workspace()` (Task 3). `poll_once(port)` (Task 3) is called identically from `run_forever()` (Task 5) and from every test. `parse_workspace_path(path)` (Task 4) returns `(slug, rewritten_path)` consistently across its three unit tests and its one caller in `WorkspaceRoutingHandler.do_GET`. `vizor_daemon.install()/uninstall()/status()` (Task 6) return dict shapes (`installed`/`uninstalled`/`service_registered` keys) that Task 8's `cmd_viz()` reads with matching key names.
