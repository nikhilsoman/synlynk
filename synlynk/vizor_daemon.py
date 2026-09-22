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
