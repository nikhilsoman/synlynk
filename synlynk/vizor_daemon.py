"""Vizor cross-workspace daemon: polls every registered workspace and serves
their rendered views from one persistent, OS-supervised background process.

Standalone from synlynk/daemon.py's WatchDaemon — that daemon is repo-scoped
(pidfile/state resolve via git rev-parse --git-common-dir); this one is
machine-scoped and must not anchor to whichever repo happened to start it.
"""
from __future__ import annotations

import contextlib
import os
import threading
from pathlib import Path
from typing import Optional

DAEMON_HOME = Path(os.path.expanduser("~/.synlynk/vizor-daemon"))
PIDFILE = DAEMON_HOME / "pidfile"
PORTFILE = DAEMON_HOME / "port"
LOGFILE = DAEMON_HOME / "daemon.log"
CACHE_ROOT = Path(os.path.expanduser("~/.synlynk/vizor-cache"))
DEFAULT_POLL_INTERVAL = 15

_RENDER_LOCK = threading.Lock()


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

    with _RENDER_LOCK:
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


def _is_transient_test_path(path_str: str) -> bool:
    test_markers = (
        "/pytest-",
        "test_run_",
        "synlynk-selftest",
        "test-instructions-",
        "test_featonboarding",
        "test_cmd_wizard",
        "test-doctor-",
        "test-synlynk-",
    )
    return any(marker in path_str for marker in test_markers)


def _registered_workspaces() -> dict:
    """Return {slug: entry} for every registered product, or {} if no registry yet."""
    from synlynk.state_registry import _read_unlocked, registry_path

    path = registry_path()
    if not path.exists():
        return {}
    try:
        payload = _read_unlocked(path)
    except Exception:
        return {}
    products = payload.get("products", {})
    if not isinstance(products, dict):
        return {}

    is_custom_registry = bool(os.environ.get("SYNLYNK_REGISTRY_PATH"))
    valid_workspaces = {}
    for slug, entry in products.items():
        if not isinstance(entry, dict):
            continue
        repo_path = entry.get("repo_path")
        db_path = entry.get("canonical_path")
        if not repo_path or not db_path:
            continue
        repo_p = Path(repo_path)
        db_p = Path(db_path)
        if not repo_p.is_dir() or not db_p.is_file():
            continue
        if not is_custom_registry and (_is_transient_test_path(str(repo_path)) or _is_transient_test_path(str(slug))):
            continue
        valid_workspaces[slug] = entry
    return valid_workspaces


def refresh_workspace(slug: str, entry: dict, port: int) -> None:
    """Render one workspace's views into CACHE_ROOT/<slug>/. Raises on failure."""
    import synlynk.viz as viz_module

    repo_path = entry.get("repo_path")
    db_path = entry.get("canonical_path")
    if not repo_path or not db_path:
        raise RuntimeError(f"workspace {slug!r} is missing repo_path or canonical_path")
    if not Path(repo_path).is_dir():
        raise RuntimeError(f"workspace {slug!r} repo_path {repo_path!r} does not exist")
    if not Path(db_path).is_file():
        raise RuntimeError(f"workspace {slug!r} db_path {db_path!r} does not exist")

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
    rest = remainder[len(slug):]
    if not rest or rest == "/":
        rest = "/index.html"
    return slug, "/" + slug + rest


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
    workspaces = _registered_workspaces()
    slugs = sorted(_known_slugs())
    if not slugs:
        cards_html = """
        <div style="grid-column: 1/-1; text-align: center; padding: 60px 20px; color: var(--text-muted);">
          <p style="font-size: 16px; margin-bottom: 8px;">No registered workspaces found.</p>
          <p style="font-size: 13px;">Run <code>synlynk init</code> or <code>synlynk workspace register</code> in a repository to connect it to Vizor.</p>
        </div>
        """
    else:
        cards = []
        for s in slugs:
            entry = workspaces.get(s, {})
            repo_path = entry.get("repo_path") or ""
            cache_dir = CACHE_ROOT / s
            is_rendered = (cache_dir / "index.html").is_file()
            status_badge = '<span class="badge" style="background:rgba(13,158,135,0.15);color:#14b8a6;">● Rendered</span>' if is_rendered else '<span class="badge" style="background:rgba(234,179,8,0.15);color:#eab308;">○ Registering</span>'

            if is_rendered:
                views_html = f"""
                <div class="view-links">
                  <a href="/w/{s}/index.html" class="view-chip primary">Overview</a>
                  <a href="/w/{s}/effort.html" class="view-chip">Effort & Cost</a>
                  <a href="/w/{s}/roles.html" class="view-chip">Roles</a>
                  <a href="/w/{s}/tube.html" class="view-chip">Architect</a>
                  <a href="/w/{s}/efficiency.html" class="view-chip">Efficiency</a>
                  <a href="/w/{s}/observatory.html" class="view-chip">Observatory</a>
                </div>
                """
            else:
                views_html = f"""
                <div class="view-links">
                  <a href="/w/{s}/index.html" class="view-chip primary">Open Dashboard</a>
                </div>
                """

            cards.append(f"""
            <div class="workspace-card" data-slug="{s}">
              <div>
                <div class="card-header">
                  <a href="/w/{s}/index.html" class="workspace-name">{s}</a>
                  {status_badge}
                </div>
                <div class="repo-path">{repo_path or 'Standalone Product'}</div>
              </div>
              {views_html}
            </div>
            """)
        cards_html = "\n".join(cards)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Synlynk Vizor — Workspace Hub</title>
  <style>
    :root {{
      --bg: #0b0f19;
      --card-bg: #111827;
      --card-border: #1f2937;
      --card-hover: #1e293b;
      --text: #f3f4f6;
      --text-muted: #9ca3af;
      --accent: #0d9e87;
      --accent-glow: rgba(13, 158, 135, 0.2);
      --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      --font-mono: "SF Mono", Monaco, Inconsolata, monospace;
    }}
    @media (prefers-color-scheme: light) {{
      :root {{
        --bg: #f8fafc;
        --card-bg: #ffffff;
        --card-border: #e2e8f0;
        --card-hover: #f1f5f9;
        --text: #0f172a;
        --text-muted: #64748b;
        --accent: #0d9e87;
        --accent-glow: rgba(13, 158, 135, 0.1);
      }}
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: var(--bg);
      color: var(--text);
      font-family: var(--font-sans);
      min-height: 100vh;
      display: flex;
      flex-direction: column;
    }}
    header {{
      background: var(--card-bg);
      border-bottom: 1px solid var(--card-border);
      padding: 16px 32px;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }}
    .brand {{
      display: flex;
      align-items: center;
      gap: 12px;
      text-decoration: none;
      color: inherit;
    }}
    .logo-badge {{
      background: var(--accent);
      color: #fff;
      font-weight: 700;
      font-size: 13px;
      padding: 4px 8px;
      border-radius: 6px;
      letter-spacing: 0.5px;
    }}
    .brand-title {{
      font-size: 17px;
      font-weight: 600;
      letter-spacing: -0.3px;
    }}
    .header-meta {{
      display: flex;
      align-items: center;
      gap: 16px;
      font-size: 13px;
      color: var(--text-muted);
    }}
    .status-dot {{
      color: var(--accent);
      font-weight: 600;
    }}
    .nav-btn {{
      background: var(--card-hover);
      color: var(--text);
      text-decoration: none;
      padding: 6px 14px;
      border-radius: 6px;
      border: 1px solid var(--card-border);
      font-size: 13px;
      font-weight: 500;
      transition: all 0.15s ease;
    }}
    .nav-btn:hover {{
      border-color: var(--accent);
      color: var(--accent);
    }}
    main {{
      flex: 1;
      max-width: 1280px;
      width: 100%;
      margin: 0 auto;
      padding: 40px 32px;
    }}
    .hero-banner {{
      margin-bottom: 32px;
    }}
    .hero-banner h1 {{
      font-size: 26px;
      font-weight: 700;
      margin-bottom: 8px;
      letter-spacing: -0.5px;
    }}
    .hero-banner p {{
      color: var(--text-muted);
      font-size: 14px;
    }}
    .search-bar {{
      margin-bottom: 24px;
    }}
    .search-input {{
      width: 100%;
      max-width: 420px;
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      color: var(--text);
      font-size: 14px;
      padding: 10px 14px;
      border-radius: 8px;
      outline: none;
      transition: border-color 0.15s ease;
    }}
    .search-input:focus {{
      border-color: var(--accent);
    }}
    .workspaces-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
      gap: 20px;
    }}
    .workspace-card {{
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 12px;
      padding: 22px;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      transition: transform 0.15s ease, border-color 0.15s ease, box-shadow 0.15s ease;
    }}
    .workspace-card:hover {{
      border-color: var(--accent);
      transform: translateY(-2px);
      box-shadow: 0 8px 24px var(--accent-glow);
    }}
    .card-header {{
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      margin-bottom: 8px;
      gap: 8px;
    }}
    .workspace-name {{
      font-size: 17px;
      font-weight: 600;
      color: var(--text);
      text-decoration: none;
      word-break: break-all;
    }}
    .workspace-name:hover {{
      color: var(--accent);
    }}
    .badge {{
      font-size: 11px;
      font-weight: 600;
      padding: 3px 8px;
      border-radius: 4px;
      letter-spacing: 0.3px;
      white-space: nowrap;
    }}
    .repo-path {{
      font-family: var(--font-mono);
      font-size: 11px;
      color: var(--text-muted);
      margin-bottom: 16px;
      word-break: break-all;
    }}
    .view-links {{
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      margin-top: 14px;
      padding-top: 14px;
      border-top: 1px solid var(--card-border);
    }}
    .view-chip {{
      background: var(--bg);
      color: var(--text);
      text-decoration: none;
      font-size: 11px;
      padding: 4px 8px;
      border-radius: 6px;
      border: 1px solid var(--card-border);
      transition: all 0.15s ease;
    }}
    .view-chip:hover {{
      background: var(--card-hover);
      border-color: var(--accent);
      color: var(--accent);
    }}
    .view-chip.primary {{
      background: var(--accent);
      border-color: var(--accent);
      color: #fff;
      font-weight: 600;
    }}
    footer {{
      border-top: 1px solid var(--card-border);
      padding: 16px 32px;
      text-align: center;
      font-size: 12px;
      color: var(--text-muted);
    }}
  </style>
</head>
<body>
  <header>
    <a href="/" class="brand">
      <span class="logo-badge">VIZOR</span>
      <span class="brand-title">Synlynk Workspace Hub</span>
    </a>
    <div class="header-meta">
      <span class="status-dot">● Daemon Live</span>
      <a href="/onboarding/roles" class="nav-btn">Agent Roles</a>
    </div>
  </header>
  <main>
    <div class="hero-banner">
      <h1>Active Workspaces</h1>
      <p>OS-supervised persistent Vizor dashboard daemon polling registered workspaces.</p>
    </div>
    <div class="search-bar">
      <input type="text" id="search-input" class="search-input" placeholder="Filter workspaces..." oninput="filterWorkspaces(this.value)">
    </div>
    <div class="workspaces-grid" id="workspaces-grid">
      {cards_html}
    </div>
  </main>
  <footer>
    synlynk vizor daemon · persistent multi-workspace renderer & server
  </footer>
  <script>
    function filterWorkspaces(query) {{
      const q = query.toLowerCase().trim();
      const cards = document.querySelectorAll('.workspace-card');
      cards.forEach(card => {{
        const slug = card.dataset.slug.toLowerCase();
        const text = card.innerText.toLowerCase();
        card.style.display = (slug.includes(q) || text.includes(q)) ? 'flex' : 'none';
      }});
    }}
  </script>
</body>
</html>
"""


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

        def _route_path(self) -> bool:
            from urllib.parse import urlparse

            path = urlparse(self.path).path
            if path == "/" or path == "":
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                if self.command == "GET":
                    self.wfile.write(_workspace_index_html().encode("utf-8"))
                return False
            if path.startswith("/w/"):
                app_route = _rewrite_workspace_app_route(path)
                if app_route is not None:
                    self.path = app_route + (("?" + urlparse(self.path).query) if urlparse(self.path).query else "")
                    return True
                slug, rewritten = parse_workspace_path(path)
                if slug is None:
                    self.send_error(404, "Unknown workspace")
                    return False
                self.path = rewritten + (("?" + urlparse(self.path).query) if urlparse(self.path).query else "")
                return True
            return True

        def do_GET(self):
            if self._route_path():
                super().do_GET()

        def do_HEAD(self):
            if self._route_path():
                super().do_HEAD()

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
