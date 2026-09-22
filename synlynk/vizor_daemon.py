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
