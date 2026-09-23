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


def _rewrite_workspace_app_route(path: str) -> Optional[str]:
    """Return the unscoped path for a known workspace app route."""
    if not path.startswith("/w/"):
        return None
    remainder = path[len("/w/"):]
    slug, separator, route = remainder.partition("/")
    if not separator or slug not in _known_slugs():
        return None
    if route in ("onboarding/roles", "onboarding/roles/"):
        return "/onboarding/roles" if route == "onboarding/roles" else "/onboarding/roles/"
    return None


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
                app_route = _rewrite_workspace_app_route(path)
                if app_route is not None:
                    self.path = app_route + (("?" + urlparse(self.path).query) if urlparse(self.path).query else "")
                    super().do_GET()
                    return
                slug, rewritten = parse_workspace_path(path)
                if slug is None:
                    self.send_error(404, "Unknown workspace")
                    return
                self.path = rewritten + (("?" + urlparse(self.path).query) if urlparse(self.path).query else "")
                super().do_GET()
                return
            super().do_GET()

    return WorkspaceRoutingHandler


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
        res = subprocess.run(["launchctl", "load", str(plist_path)], capture_output=True, text=True)
        if res.returncode != 0:
            return {
                "installed": False,
                "manager": "launchd",
                "unit_path": str(plist_path),
                "reason": res.stderr.strip() or f"launchctl load exited with code {res.returncode}",
            }
        return {"installed": True, "manager": "launchd", "unit_path": str(plist_path)}
    elif system == "Linux":
        unit_path = _systemd_unit_path()
        unit_path.parent.mkdir(parents=True, exist_ok=True)
        unit_path.write_text(_systemd_unit_contents(python_exe))
        res = subprocess.run(["systemctl", "--user", "enable", "--now", _SYSTEMD_UNIT_NAME],
                        capture_output=True, text=True)
        if res.returncode != 0:
            return {
                "installed": False,
                "manager": "systemd",
                "unit_path": str(unit_path),
                "reason": res.stderr.strip() or f"systemctl enable exited with code {res.returncode}",
            }
        return {"installed": True, "manager": "systemd", "unit_path": str(unit_path)}
    return {"installed": False, "reason": f"unsupported platform: {system}"}


def uninstall() -> dict:
    """Unload/disable the service unit and remove it."""
    system = platform_name()
    if system == "Darwin":
        plist_path = _launchd_plist_path()
        if plist_path.exists():
            res = subprocess.run(["launchctl", "unload", str(plist_path)], capture_output=True, text=True)
            if res.returncode != 0:
                return {
                    "uninstalled": False,
                    "manager": "launchd",
                    "reason": res.stderr.strip() or f"launchctl unload exited with code {res.returncode}",
                }
            plist_path.unlink()
        return {"uninstalled": True, "manager": "launchd"}
    elif system == "Linux":
        unit_path = _systemd_unit_path()
        res = subprocess.run(["systemctl", "--user", "disable", "--now", _SYSTEMD_UNIT_NAME],
                        capture_output=True, text=True)
        if res.returncode != 0:
            return {
                "uninstalled": False,
                "manager": "systemd",
                "reason": res.stderr.strip() or f"systemctl disable exited with code {res.returncode}",
            }
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
