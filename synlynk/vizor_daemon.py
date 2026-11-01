"""Vizor cross-workspace daemon: polls every registered workspace and serves
their rendered views from one persistent, OS-supervised background process.

Standalone from synlynk/daemon.py's WatchDaemon — that daemon is repo-scoped
(pidfile/state resolve via git rev-parse --git-common-dir); this one is
machine-scoped and must not anchor to whichever repo happened to start it.
"""
from __future__ import annotations

import contextlib
import dataclasses
import json
import os
import re
import threading
from pathlib import Path
from typing import Optional

DAEMON_HOME = Path(os.environ.get("SYNLYNK_VIZOR_DAEMON_HOME", os.path.expanduser("~/.synlynk/vizor-daemon")))
PIDFILE = DAEMON_HOME / "pidfile"
PORTFILE = DAEMON_HOME / "port"
LOGFILE = DAEMON_HOME / "daemon.log"
CACHE_ROOT = Path(os.environ.get("SYNLYNK_VIZOR_CACHE_ROOT", os.path.expanduser("~/.synlynk/vizor-cache")))
DEFAULT_POLL_INTERVAL = 15
LOG_MAX_BYTES = 1_048_576
STALL_GRACE_S = 120.0
# One workspace render may run this long before its heartbeat pump stops.
# The stall watch can then exit. A render inside this limit is still working.
RENDER_LIMIT_S = 30 * 60
ENSURE_INTERVAL_S = 60
ENSURE_BACKOFF_LIMIT = 3
ENSURE_BACKOFF_WINDOW_S = 600
_LAUNCHD_ENSURE_LABEL = "com.synlynk.vizor-ensure"
_SYSTEMD_ENSURE_SERVICE = "synlynk-vizor-ensure.service"
_SYSTEMD_ENSURE_TIMER = "synlynk-vizor-ensure.timer"

_RENDER_LOCK = threading.Lock()


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


@contextlib.contextmanager
def _workspace_cwd(repo_path: Path):
    """Chdir to a workspace repo for the duration of a board_governance/autonomy call.

    Those modules resolve their state (`.synlynk/proposals`, `.synlynk/config.json`)
    relative to os.getcwd(), same CWD-coupling rationale as workspace_render_context above.
    """
    with _RENDER_LOCK:
        old_cwd = os.getcwd()
        try:
            os.chdir(repo_path)
            yield
        finally:
            os.chdir(old_cwd)


def _list_proposals_for_context(ctx: "WorkspaceContext") -> list:
    from synlynk.board_governance import _proposals_dir

    with _workspace_cwd(ctx.repo_path):
        proposals_dir = _proposals_dir()
        results = []
        for name in sorted(os.listdir(proposals_dir)):
            if not name.endswith(".json"):
                continue
            with open(os.path.join(proposals_dir, name), "r", encoding="utf-8") as f:
                results.append(json.load(f))
        return results


def _sign_proposal_for_context(ctx: "WorkspaceContext", proposal_id: str, key_path: Optional[str]) -> dict:
    from synlynk.board_governance import sign_proposal

    if not proposal_id:
        raise ValueError("proposal_id is required")

    with _workspace_cwd(ctx.repo_path):
        signed = sign_proposal(proposal_id, key_path=key_path)
        return signed.to_dict()


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


def _without_pytest_basetemp(norm: str) -> str:
    """Drop pytest's runner directories before the transient-path check.

    ``tmp_path`` is ``.../pytest-of-<user>/pytest-<n>/...``. That prefix
    contains ``/pytest-``, which would mark a durable dev clone such as
    ``dev/coldtest`` ephemeral. ``/pytest-`` segments outside that prefix
    still count.
    """
    parts = [part for part in norm.split("/") if part]
    cleaned: list[str] = []
    index = 0
    while index < len(parts):
        part = parts[index]
        nxt = parts[index + 1] if index + 1 < len(parts) else ""
        if part.startswith("pytest-of-") and nxt.startswith("pytest-"):
            index += 2
            continue
        cleaned.append(part)
        index += 1
    return "/" + "/".join(cleaned)


def workspace_kind(entry: dict, slug: str) -> str:
    raw = str((entry or {}).get("kind") or "").strip().lower()
    if raw in {"local", "hosted", "ephemeral"}:
        return raw
    path = str((entry or {}).get("path_root") or (entry or {}).get("repo_path") or slug)
    norm = path.replace("\\", "/")
    if "/.worktrees/" in f"/{norm}/" or "/worktrees/job-" in norm or "/worktrees/djob-" in norm:
        return "ephemeral"
    classified = _without_pytest_basetemp(norm)
    if _is_transient_test_path(classified) or _is_transient_test_path(slug):
        return "ephemeral"
    return "local"


def is_durable_hub_entry(slug: str, entry: dict) -> bool:
    return workspace_kind(entry, slug) != "ephemeral"


def stamp_workspace_kind(slug: str, entry: dict) -> dict:
    """Persist the derived workspace classification during a refresh write path."""
    kind = workspace_kind(entry, slug)
    path_root = str(entry.get("path_root") or entry.get("repo_path") or "")
    if entry.get("kind") == kind and entry.get("path_root") == path_root:
        return entry
    from synlynk.state_registry import update_registered_product

    return update_registered_product(slug, kind=kind, path_root=path_root)


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
        if not is_durable_hub_entry(slug, entry):
            continue
        valid_workspaces[slug] = entry
    return valid_workspaces


def refresh_workspace(slug: str, entry: dict, port: int) -> None:
    """Render one workspace's views into CACHE_ROOT/<slug>/. Raises on failure."""
    import synlynk.viz as viz_module

    entry = stamp_workspace_kind(slug, entry)
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


def _safe_heartbeat(action) -> None:
    """Keep a heartbeat failure from changing the poll result."""
    try:
        action()
    except Exception as exc:
        _log(f"heartbeat write failed: {exc}")


def _remember_beat(*, pid: int, status: str, cycle_count: int, active_task: Optional[str]) -> None:
    from datetime import datetime, timezone

    from synlynk._constants import VERSION
    from synlynk.viz.heartbeats import upsert_beat

    upsert_beat(
        DAEMON_HOME,
        pid=pid,
        status=status,
        last_beat_at=datetime.now(timezone.utc),
        cycle_count=cycle_count,
        active_task=active_task,
        version=VERSION,
    )


def render_limit_s() -> float:
    """How long one workspace render may keep its own heartbeat fresh."""
    raw = os.environ.get("SYNLYNK_VIZOR_RENDER_LIMIT_S")
    if not raw:
        return RENDER_LIMIT_S
    try:
        value = float(raw)
    except ValueError:
        return RENDER_LIMIT_S
    if value <= 0:
        return RENDER_LIMIT_S
    return value


def beat_while_render_s() -> float:
    """Pump interval while a render is in progress. Stays inside the stall grace."""
    return max(min(stall_grace_s() / 4.0, 30.0), 0.05)


def _pump_render_beat(slug: str, cycle_count: int, stop_event: threading.Event, started: float) -> None:
    """Refresh the beat until the render finishes or passes the render limit."""
    import time

    pid = os.getpid()
    limit = render_limit_s()
    interval = beat_while_render_s()
    while not stop_event.is_set():
        if time.monotonic() - started >= limit:
            _log(f"render beat stopped for {slug!r}: still running after {limit:.0f}s")
            return
        _safe_heartbeat(lambda: _remember_beat(
            pid=pid,
            status="running",
            cycle_count=cycle_count,
            active_task=slug,
        ))
        if stop_event.wait(interval):
            return


@contextlib.contextmanager
def keep_render_beat(slug: str, cycle_count: int):
    """Keep the heartbeat fresh while one workspace render is still working.

    The stall watch reads beat age. A render that outlasts the grace is not a
    wedged poll loop, so the beat moves until ``render_limit_s`` elapses.
    """
    import time

    stop_event = threading.Event()
    started = time.monotonic()
    thread = threading.Thread(
        target=_pump_render_beat,
        args=(slug, cycle_count, stop_event, started),
        daemon=True,
        name="vizor-render-beat",
    )
    thread.start()
    try:
        yield
    finally:
        stop_event.set()
        thread.join(timeout=2)


def poll_once(port: int) -> dict:
    """Refresh every registered workspace once. Never lets one failure stop another."""
    from synlynk.viz.heartbeats import pid_alive, read_beat

    def mark_dead_pid() -> None:
        existing = read_beat(DAEMON_HOME, poll_interval_s=poll_interval())
        if not existing:
            return
        if pid_alive(int(existing["pid"])):
            return
        _remember_beat(
            pid=int(existing["pid"]),
            status="stale",
            cycle_count=int(existing["cycle_count"]),
            active_task=existing.get("active_task"),
        )

    _safe_heartbeat(mark_dead_pid)
    cycle_count = 0
    try:
        existing = read_beat(DAEMON_HOME, poll_interval_s=poll_interval())
        if existing:
            cycle_count = int(existing["cycle_count"])
    except Exception as exc:
        _log(f"heartbeat read failed: {exc}")

    results = {}
    current_pid = os.getpid()
    for slug, entry in _registered_workspaces().items():
        if not isinstance(entry, dict):
            continue
        _safe_heartbeat(lambda slug=slug: _remember_beat(
            pid=current_pid,
            status="running",
            cycle_count=cycle_count,
            active_task=slug,
        ))
        try:
            with keep_render_beat(slug, cycle_count):
                refresh_workspace(slug, entry, port)
            results[slug] = "ok"
        except Exception as exc:
            results[slug] = f"error: {exc}"
            _log(f"refresh failed for {slug!r}: {exc}")
    _safe_heartbeat(lambda: _remember_beat(
        pid=current_pid,
        status="running",
        cycle_count=cycle_count + 1,
        active_task="idle",
    ))
    return results


def cap_log() -> None:
    """Keep daemon.log from growing without bound. Retain the newest half."""
    try:
        size = LOGFILE.stat().st_size
    except OSError:
        return
    if size <= LOG_MAX_BYTES:
        return
    keep = LOG_MAX_BYTES // 2
    try:
        with open(LOGFILE, "rb") as handle:
            handle.seek(max(size - keep, 0))
            tail = handle.read(keep)
        newline = tail.find(b"\n")
        if newline >= 0:
            tail = tail[newline + 1:]
        LOGFILE.write_bytes(tail)
    except OSError as exc:
        try:
            LOGFILE.write_text(f"log cap failed: {exc}\n")
        except OSError:
            return


def _log(message: str) -> None:
    import time

    DAEMON_HOME.mkdir(parents=True, exist_ok=True)
    cap_log()
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
    elif rest in ("/graphify", "/graph"):
        rest = "/graphify.html"
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
                graphify_chip = ""
                if (cache_dir / "graphify.html").is_file() or (cache_dir / "graph.html").is_file():
                    graphify_chip = f'\n                  <a href="/w/{s}/graphify.html" class="view-chip">Graphify</a>'
                views_html = f"""
                <div class="view-links">
                  <a href="/w/{s}/index.html" class="view-chip primary">Overview</a>
                  <a href="/w/{s}/effort.html" class="view-chip">Effort & Cost</a>
                  <a href="/w/{s}/roles.html" class="view-chip">Roles</a>
                  <a href="/w/{s}/tube.html" class="view-chip">Architect</a>{graphify_chip}
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
            from urllib.parse import parse_qs, urlparse

            parsed = urlparse(self.path)
            path = parsed.path
            if path == "/" or path == "":
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                if self.command == "GET":
                    self.wfile.write(_workspace_index_html().encode("utf-8"))
                return False
            if path.startswith("/w/"):
                remainder = path[len("/w/"):]
                slug, separator, subpath = remainder.partition("/")
                if not separator or not slug:
                    self.send_error(404, "Invalid workspace path")
                    return False

                ctx = resolve_workspace_context(slug)
                if ctx is None:
                    self.send_error(404, f"Unknown workspace: {slug}")
                    return False

                if subpath == "board":
                    from synlynk.autonomy import get_autonomy_mode
                    from synlynk.viz import generate_boardroom_html

                    with _workspace_cwd(ctx.repo_path):
                        mode = get_autonomy_mode()
                    html_body = generate_boardroom_html(
                        workspace_slug=slug, autonomy_mode=mode.value
                    ).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(html_body)))
                    self.end_headers()
                    if self.command == "GET":
                        self.wfile.write(html_body)
                    return False

                if subpath.startswith("api/"):
                    api_route = subpath[len("api/"):]
                    if api_route == "board/proposals" and self.command == "GET":
                        proposals = _list_proposals_for_context(ctx)
                        body = json.dumps({"proposals": proposals}).encode("utf-8")
                        self.send_response(200)
                        self.send_header("Content-Type", "application/json; charset=utf-8")
                        self.send_header("Content-Length", str(len(body)))
                        self.end_headers()
                        self.wfile.write(body)
                        return False

                    if api_route == "board/proposals/sign" and self.command == "POST":
                        length = int(self.headers.get("Content-Length", 0))
                        payload = json.loads(self.rfile.read(length)) if length else {}
                        proposal_id = payload.get("proposal_id")
                        key_path = payload.get("key_path")
                        try:
                            signed = _sign_proposal_for_context(ctx, proposal_id, key_path)
                            res = json.dumps({"ok": True, "proposal": signed}).encode("utf-8")
                            self.send_response(200)
                        except Exception as exc:
                            res = json.dumps({"ok": False, "error": str(exc)}).encode("utf-8")
                            self.send_response(400)
                        self.send_header("Content-Type", "application/json")
                        self.end_headers()
                        self.wfile.write(res)
                        return False

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

                    if api_route == "logical" and self.command == "GET":
                        from synlynk.viz.logical_expand import (
                            load_logical_graph,
                            logical_community_payload,
                        )

                        filters = parse_qs(parsed.query)
                        raw_community = (filters.get("community") or [None])[0]
                        if raw_community is None or str(raw_community).strip() == "":
                            body = json.dumps({"error": "community required"}).encode("utf-8")
                            self.send_response(400)
                            self.send_header("Content-Type", "application/json; charset=utf-8")
                            self.send_header("Content-Length", str(len(body)))
                            self.end_headers()
                            self.wfile.write(body)
                            return False
                        nodes, edges = load_logical_graph(ctx.repo_path, ctx.db_path)
                        payload = logical_community_payload(
                            nodes, edges, str(raw_community).strip()
                        )
                        body = json.dumps(payload).encode("utf-8")
                        self.send_response(200)
                        self.send_header("Content-Type", "application/json; charset=utf-8")
                        self.send_header("Content-Length", str(len(body)))
                        self.end_headers()
                        self.wfile.write(body)
                        return False

                    if api_route == "sentinel" and self.command == "GET":
                        from synlynk.viz.constants import SENTINEL_ACKS_PATH
                        from synlynk.viz.data import (
                            group_workspace_sentinel_alerts,
                            load_sentinel_acks,
                            load_workspace_sentinel_alerts,
                        )

                        sentinel_path = os.path.join(str(ctx.repo_path), ".synlynk", "sentinel.md")
                        acks_path = os.path.join(str(ctx.repo_path), SENTINEL_ACKS_PATH)
                        hud = group_workspace_sentinel_alerts(
                            load_workspace_sentinel_alerts(sentinel_path, active_only=True),
                            load_sentinel_acks(acks_path),
                        )
                        body = json.dumps(hud).encode("utf-8")
                        self.send_response(200)
                        self.send_header("Content-Type", "application/json; charset=utf-8")
                        self.send_header("Content-Length", str(len(body)))
                        self.end_headers()
                        self.wfile.write(body)
                        return False

                    if api_route in ("sentinel/ack", "sentinel/issue") and self.command == "POST":
                        from datetime import datetime, timezone
                        from synlynk.sentinel import _alert_identity
                        from synlynk.viz.constants import SENTINEL_ACKS_PATH
                        from synlynk.viz.data import (
                            group_workspace_sentinel_alerts,
                            load_sentinel_acks,
                            load_workspace_sentinel_alerts,
                            raise_sentinel_issue,
                            save_sentinel_ack,
                        )

                        length = int(self.headers.get("Content-Length", 0) or 0)
                        try:
                            payload = json.loads(self.rfile.read(length) or b"{}")
                            scope = str(payload.get("scope") or "")
                            code = str(payload.get("code") or "").strip().upper()
                            identity = payload.get("identity")
                            if scope not in ("occurrence", "pattern") or not code:
                                raise ValueError("invalid sentinel scope or code")
                            if scope == "occurrence" and not isinstance(identity, list):
                                raise ValueError("occurrence scope requires identity")
                        except (ValueError, json.JSONDecodeError) as exc:
                            body = json.dumps({"ok": False, "error": str(exc)}).encode("utf-8")
                            self.send_response(400)
                            self.send_header("Content-Type", "application/json")
                            self.end_headers()
                            self.wfile.write(body)
                            return False

                        sentinel_path = os.path.join(
                            str(ctx.repo_path), ".synlynk", "sentinel.md"
                        )
                        acks_path = os.path.join(
                            str(ctx.repo_path), SENTINEL_ACKS_PATH
                        )
                        alerts = load_workspace_sentinel_alerts(
                            sentinel_path, active_only=True
                        )
                        hud = group_workspace_sentinel_alerts(
                            alerts, {}, member_cap=max(50, len(alerts))
                        )
                        groups = list(hud.get("groups") or []) + list(hud.get("acked") or [])
                        group = next((item for item in groups if item.get("code") == code), None)
                        if group is None:
                            body = json.dumps({"ok": False, "error": "sentinel_not_found"}).encode("utf-8")
                            self.send_response(404)
                            self.send_header("Content-Type", "application/json")
                            self.end_headers()
                            self.wfile.write(body)
                            return False

                        member = None
                        if scope == "occurrence":
                            member = next((item for item in group.get("members") or [] if list(_alert_identity({
                                "severity": item.get("severity"),
                                "code": "" if code == "UNPARSED" else code,
                                "message": item.get("message") or "",
                            })) == identity), None)
                            if member is None:
                                body = json.dumps({"ok": False, "error": "sentinel_not_found"}).encode("utf-8")
                                self.send_response(404)
                                self.send_header("Content-Type", "application/json")
                                self.end_headers()
                                self.wfile.write(body)
                                return False

                        issue_url = None
                        if api_route == "sentinel/issue":
                            issue_group = group
                            if member is not None:
                                issue_group = {
                                    "code": code,
                                    "severity": member.get("severity"),
                                    "count": 1,
                                    "first_seen": member.get("first_seen") or member.get("ts"),
                                    "last_seen": member.get("last_seen") or member.get("ts"),
                                    "members": [member],
                                }
                            try:
                                issue_url = raise_sentinel_issue(
                                    slug, str(ctx.repo_path), issue_group
                                )
                            except Exception:
                                body = json.dumps({"ok": False, "error": "gh_failed"}).encode("utf-8")
                                self.send_response(502)
                                self.send_header("Content-Type", "application/json")
                                self.end_headers()
                                self.wfile.write(body)
                                return False

                        last_seen = (
                            (member or {}).get("last_seen")
                            or (member or {}).get("ts")
                            or group.get("last_seen")
                            or ""
                        )
                        row = {
                            "kind": scope,
                            "code": code,
                            "identity": identity if scope == "occurrence" else None,
                            "acked_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                            "last_seen_at_ack": str(last_seen),
                            "issue_url": issue_url,
                        }
                        save_sentinel_ack(acks_path, row, slug=slug)
                        result = {"ok": True}
                        if issue_url:
                            result["issue_url"] = issue_url
                        body = json.dumps(result).encode("utf-8")
                        self.send_response(200)
                        self.send_header("Content-Type", "application/json")
                        self.end_headers()
                        self.wfile.write(body)
                        return False

                    if api_route == "note" and self.command == "POST":
                        from synlynk.viz.server import save_viz_note, _pkg

                        length = int(self.headers.get("Content-Length", 0) or 0)
                        payload = json.loads(self.rfile.read(length) or b"{}")
                        try:
                            result = save_viz_note(_pkg().VIZ_NOTES_PATH, payload)
                        except ValueError as exc:
                            body = json.dumps({"ok": False, "error": str(exc)}).encode("utf-8")
                            self.send_response(400)
                            self.send_header("Content-Type", "application/json")
                            self.end_headers()
                            self.wfile.write(body)
                            return False
                        body = json.dumps(result).encode("utf-8")
                        self.send_response(200)
                        self.send_header("Content-Type", "application/json")
                        self.end_headers()
                        self.wfile.write(body)
                        return False

                    if api_route == "daemon/stream" and self.command == "GET":
                        from synlynk.viz.server import serve_daemon_stream

                        serve_daemon_stream(self, repo_path=ctx.repo_path)
                        return False

                    if api_route == "goals" and self.command == "GET":
                        from synlynk.viz import collect_data

                        payload = collect_data(db_path=str(ctx.db_path))
                        body = json.dumps(payload).encode("utf-8")
                        self.send_response(200)
                        self.send_header("Content-Type", "application/json; charset=utf-8")
                        self.send_header("Content-Length", str(len(body)))
                        self.end_headers()
                        self.wfile.write(body)
                        return False

                    if api_route == "board/stage" and self.command == "POST":
                        from synlynk.board import update_stage_for_context

                        length = int(self.headers.get("Content-Length", 0))
                        payload = json.loads(self.rfile.read(length))
                        ok = update_stage_for_context(
                            ctx, payload["story_id"], payload["stage"],
                            unlocked=bool(payload.get("unlocked")),
                        )
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

                app_route = _rewrite_workspace_app_route(path)
                if app_route is not None:
                    self.path = app_route + (("?" + parsed.query) if parsed.query else "")
                    return True
                slug, rewritten = parse_workspace_path(path)
                if slug is None:
                    self.send_error(404, "Unknown workspace")
                    return False
                self.path = rewritten + (("?" + parsed.query) if parsed.query else "")
                return True
            return True

        def do_GET(self):
            if self._route_path():
                super().do_GET()

        def do_HEAD(self):
            if self._route_path():
                super().do_HEAD()

        def do_POST(self):
            from synlynk.local_http_auth import authorize_local_request

            ok, code, message = authorize_local_request(self.headers)
            if not ok:
                self.send_error(code, message)
                return
            if self._route_path():
                super().do_POST()

    return WorkspaceRoutingHandler


def _write_state(pid: int, port: int) -> None:
    DAEMON_HOME.mkdir(parents=True, exist_ok=True)
    PIDFILE.write_text(str(pid))
    PORTFILE.write_text(str(port))


def _read_pid() -> Optional[int]:
    try:
        return int(PIDFILE.read_text().strip())
    except (OSError, ValueError):
        return None


def _read_port() -> Optional[int]:
    try:
        return int(PORTFILE.read_text().strip())
    except (OSError, ValueError):
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


def resolve_listen_port(port: Optional[int] = None) -> Optional[int]:
    """Return a bindable port, or None when a live Vizor pid already owns the home."""
    if is_running():
        _log(f"already running pid={_read_pid()} port={_read_port()}")
        return None
    from synlynk.viz.constants import DEFAULT_PORT
    from synlynk.viz.ports import find_available_vizor_port

    return find_available_vizor_port(port or DEFAULT_PORT)


def mark_daemon_stopped() -> None:
    """Record a clean shutdown without raising into the server finally path."""
    from synlynk.viz.heartbeats import read_beat

    existing = None
    try:
        existing = read_beat(DAEMON_HOME, poll_interval_s=poll_interval())
    except Exception as exc:
        _log(f"heartbeat read failed: {exc}")
    cycle_count = int(existing["cycle_count"]) if existing else 0
    active_task = existing.get("active_task") if existing else "idle"
    _safe_heartbeat(lambda: _remember_beat(
        pid=os.getpid(),
        status="stopped",
        cycle_count=cycle_count,
        active_task=active_task,
    ))


def stall_grace_s() -> float:
    """How long a missing beat may last before the process asks launchd to restart it."""
    raw = os.environ.get("SYNLYNK_VIZOR_STALL_GRACE_S")
    if not raw:
        return STALL_GRACE_S
    try:
        value = float(raw)
    except ValueError:
        return STALL_GRACE_S
    if value <= 0:
        return STALL_GRACE_S
    return value


def _heartbeat_is_fresh(grace_s: float) -> bool:
    from synlynk.viz.heartbeats import read_beat

    try:
        row = read_beat(DAEMON_HOME, poll_interval_s=max(int(grace_s / 2), 1))
    except Exception:
        return False
    return bool(row) and row.get("status") == "running"


def _watch_for_stall(stop_event: threading.Event) -> None:
    """Exit only when the poll loop is still supposed to be running and the beat is old.

    The first action waits on ``stop_event``. ``run_forever`` sets that event
    before it returns, so a normal shutdown cannot ``os._exit`` the caller.
    """
    grace = stall_grace_s()
    if stop_event.wait(grace):
        return
    while not stop_event.is_set():
        if _heartbeat_is_fresh(grace):
            if stop_event.wait(grace):
                return
            continue
        if stop_event.is_set():
            return
        _log("stall: heartbeat older than grace; exiting for supervisor restart")
        if stop_event.is_set():
            return
        os._exit(1)


def make_httpd(handler_cls, port: int):
    """One thread per request.

    Overview holds ``/api/daemon/stream`` open for the life of that page.
    ``HTTPServer`` serves a single request at a time, so Board and every other
    view wait behind that socket. ``ThreadingHTTPServer`` accepts the next
    request while the stream is still open.
    """
    import http.server

    return http.server.ThreadingHTTPServer(("127.0.0.1", port), handler_cls)


def run_forever(port: Optional[int] = None) -> None:
    """Daemon entrypoint: serve forever, refreshing every registered workspace on a timer."""
    import threading

    extra_paths = [
        os.path.expanduser("~/.local/bin"),
        os.path.expanduser("~/.pyenv/shims"),
        "/opt/homebrew/bin",
        "/usr/local/bin",
    ]
    for p in extra_paths:
        if p not in os.environ.get("PATH", ""):
            os.environ["PATH"] = p + ":" + os.environ.get("PATH", "")

    resolved_port = resolve_listen_port(port)
    if resolved_port is None:
        return

    probe_health()

    CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    handler_cls = build_workspace_routing_handler()
    server = make_httpd(handler_cls, resolved_port)
    _write_state(pid=os.getpid(), port=resolved_port)
    _log(f"daemon starting on port {resolved_port}")

    stop_event = threading.Event()

    def _poll_loop():
        while not stop_event.is_set():
            poll_once(resolved_port)
            stop_event.wait(poll_interval())

    poll_thread = threading.Thread(target=_poll_loop, daemon=True)
    poll_thread.start()
    stall_thread = threading.Thread(
        target=_watch_for_stall,
        args=(stop_event,),
        daemon=True,
        name="vizor-stall-watch",
    )
    stall_thread.start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop_event.set()
        mark_daemon_stopped()
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


def _launchd_ensure_plist_path() -> Path:
    return _launchd_plist_path().with_name(f"{_LAUNCHD_ENSURE_LABEL}.plist")


def _systemd_unit_path() -> Path:
    return Path(os.path.expanduser("~/.config/systemd/user/synlynk-vizor-daemon.service"))


def _systemd_ensure_service_path() -> Path:
    return _systemd_unit_path().with_name(_SYSTEMD_ENSURE_SERVICE)


def _systemd_ensure_timer_path() -> Path:
    return _systemd_unit_path().with_name(_SYSTEMD_ENSURE_TIMER)


_LAUNCHD_LABEL = "com.synlynk.vizor-daemon"
_SYSTEMD_UNIT_NAME = "synlynk-vizor-daemon.service"


def _service_environment() -> dict:
    local_bin = os.path.expanduser("~/.local/bin")
    pyenv_shims = os.path.expanduser("~/.pyenv/shims")
    default_path = f"/opt/homebrew/bin:/usr/local/bin:{local_bin}:{pyenv_shims}:/usr/bin:/bin:/usr/sbin:/sbin"
    return {
        "PATH": default_path,
        "PYTHONPATH": _synlynk_import_root(),
        "SYNLYNK_VIZOR_DAEMON": "1",
    }


def _synlynk_import_root() -> str:
    """Directory that must be on PYTHONPATH for `python -m synlynk.vizor_daemon`.

    Launchd/systemd start with cwd `/` or `$HOME`. An editable install that
    points at a deleted worktree is invisible from those cwds, which is the
    LIVE-16 crash-loop.
    """
    import synlynk

    return str(Path(synlynk.__file__).resolve().parent.parent)


def _plist_env_xml(env: dict) -> str:
    lines = ["    <key>EnvironmentVariables</key>", "    <dict>"]
    for key, value in env.items():
        lines.append(f"        <key>{key}</key>")
        lines.append(f"        <string>{value}</string>")
    lines.append("    </dict>")
    return "\n".join(lines)


def _launchd_plist_contents(python_exe: str) -> str:
    env = _service_environment()
    working = str(DAEMON_HOME)
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
    <key>WorkingDirectory</key>
    <string>{working}</string>
{_plist_env_xml(env)}
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>ThrottleInterval</key>
    <integer>30</integer>
    <key>StandardOutPath</key>
    <string>{LOGFILE}</string>
    <key>StandardErrorPath</key>
    <string>{LOGFILE}</string>
</dict>
</plist>
"""


def _launchd_ensure_plist_contents(python_exe: str) -> str:
    env = _service_environment()
    working = str(DAEMON_HOME)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{_LAUNCHD_ENSURE_LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{python_exe}</string>
        <string>-m</string>
        <string>synlynk.vizor_ensure</string>
    </array>
    <key>WorkingDirectory</key>
    <string>{working}</string>
{_plist_env_xml(env)}
    <key>RunAtLoad</key>
    <false/>
    <key>StartInterval</key>
    <integer>{ENSURE_INTERVAL_S}</integer>
    <key>StandardOutPath</key>
    <string>{LOGFILE}</string>
    <key>StandardErrorPath</key>
    <string>{LOGFILE}</string>
</dict>
</plist>
"""


def _systemd_unit_contents(python_exe: str) -> str:
    env = _service_environment()
    return f"""[Unit]
Description=synlynk Vizor cross-workspace daemon

[Service]
WorkingDirectory={DAEMON_HOME}
Environment=PYTHONPATH={env["PYTHONPATH"]}
Environment=SYNLYNK_VIZOR_DAEMON=1
ExecStart={python_exe} -m synlynk.vizor_daemon
Restart=on-failure
RestartSec=30

[Install]
WantedBy=default.target
"""


def _systemd_ensure_service_contents(python_exe: str) -> str:
    env = _service_environment()
    return f"""[Unit]
Description=synlynk Vizor ensure tick

[Service]
Type=oneshot
WorkingDirectory={DAEMON_HOME}
Environment=PYTHONPATH={env["PYTHONPATH"]}
Environment=SYNLYNK_VIZOR_DAEMON=1
ExecStart={python_exe} -m synlynk.vizor_ensure
"""


def _systemd_ensure_timer_contents() -> str:
    return f"""[Unit]
Description=synlynk Vizor ensure timer

[Timer]
OnBootSec={ENSURE_INTERVAL_S}
OnUnitActiveSec={ENSURE_INTERVAL_S}
AccuracySec=10
Persistent=true

[Install]
WantedBy=timers.target
"""


def probe_health() -> dict:
    """Detect launchd/systemd import crash-loop or a registered-but-dead service.

    Writes a CRITICAL sentinel. Does not inspect exec/dispatch stdout — that
    is why LIVE-16 was silent for thousands of KeepAlive failures.
    """
    from synlynk.sentinel import _write_sentinel_alert

    running = is_running()
    registered = False
    try:
        registered = bool(status().get("service_registered"))
    except Exception:
        registered = False

    crashloop = False
    try:
        if LOGFILE.exists():
            tail = LOGFILE.read_text(errors="replace")[-8000:]
            crashloop = "ModuleNotFoundError: No module named 'synlynk'" in tail
    except OSError:
        tail = ""

    if (crashloop and not running) or (registered and not running):
        code = "VIZOR_DAEMON_CRASHLOOP" if crashloop else "VIZOR_DAEMON_DOWN"
        message = (
            "OS-supervised Vizor daemon cannot import synlynk (launchd KeepAlive "
            "crash-loop). HUD may be served by a session workaround; GitHub App "
            "token refresh in vizor_daemon is not running."
            if crashloop
            else "Vizor daemon is registered but not running."
        )
        _write_sentinel_alert("CRITICAL", code, message)
        return {"ok": False, "code": code, "running": running, "registered": registered}

    return {"ok": True, "code": "ok", "running": running, "registered": registered}


def _launchctl(args: list) -> subprocess.CompletedProcess:
    return subprocess.run(["launchctl", *args], capture_output=True, text=True)


def _activate_launchd(plist_path: Path, label: str, *, kickstart: bool) -> Optional[str]:
    """Reload one plist. ``bootout`` is best effort because the unit may be new.

    Returns an error string, or None when the unit is loaded.
    """
    domain = f"gui/{os.getuid()}"
    _launchctl(["bootout", domain, str(plist_path)])
    boot = _launchctl(["bootstrap", domain, str(plist_path)])
    if boot.returncode != 0:
        loaded = _launchctl(["load", str(plist_path)])
        if loaded.returncode != 0:
            reason = (getattr(boot, "stderr", "") or getattr(loaded, "stderr", "") or "").strip()
            return reason or f"launchctl bootstrap exited with code {boot.returncode}"
    if kickstart:
        kicked = _launchctl(["kickstart", "-k", f"{domain}/{label}"])
        if kicked.returncode != 0:
            reason = (getattr(kicked, "stderr", "") or "").strip()
            return reason or f"launchctl kickstart exited with code {kicked.returncode}"
    return None


def _systemctl(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["systemctl", "--user", *args], capture_output=True, text=True)


def install() -> dict:
    """Write and load the daemon plus the ensure timer from this interpreter."""
    python_exe = sys.executable
    system = platform_name()
    if system == "Darwin":
        plist_path = _launchd_plist_path()
        ensure_path = _launchd_ensure_plist_path()
        plist_path.parent.mkdir(parents=True, exist_ok=True)
        plist_path.write_text(_launchd_plist_contents(python_exe))
        ensure_path.write_text(_launchd_ensure_plist_contents(python_exe))
        reason = _activate_launchd(plist_path, _LAUNCHD_LABEL, kickstart=True)
        if reason:
            return {
                "installed": False,
                "manager": "launchd",
                "unit_path": str(plist_path),
                "reason": reason,
            }
        timer_reason = _activate_launchd(ensure_path, _LAUNCHD_ENSURE_LABEL, kickstart=False)
        if timer_reason:
            return {
                "installed": False,
                "manager": "launchd",
                "unit_path": str(ensure_path),
                "reason": timer_reason,
            }
        return {"installed": True, "manager": "launchd", "unit_path": str(plist_path)}
    elif system == "Linux":
        unit_path = _systemd_unit_path()
        service_path = _systemd_ensure_service_path()
        timer_path = _systemd_ensure_timer_path()
        unit_path.parent.mkdir(parents=True, exist_ok=True)
        unit_path.write_text(_systemd_unit_contents(python_exe))
        service_path.write_text(_systemd_ensure_service_contents(python_exe))
        timer_path.write_text(_systemd_ensure_timer_contents())
        res = _systemctl("enable", "--now", _SYSTEMD_UNIT_NAME)
        if res.returncode != 0:
            return {
                "installed": False,
                "manager": "systemd",
                "unit_path": str(unit_path),
                "reason": (getattr(res, "stderr", "") or "").strip() or f"systemctl enable exited with code {res.returncode}",
            }
        timer = _systemctl("enable", "--now", _SYSTEMD_ENSURE_TIMER)
        if timer.returncode != 0:
            return {
                "installed": False,
                "manager": "systemd",
                "unit_path": str(timer_path),
                "reason": (getattr(timer, "stderr", "") or "").strip() or f"systemctl enable exited with code {timer.returncode}",
            }
        return {"installed": True, "manager": "systemd", "unit_path": str(unit_path)}
    return {"installed": False, "reason": f"unsupported platform: {system}"}


def uninstall() -> dict:
    """Unload/disable the daemon and ensure units and remove them."""
    system = platform_name()
    if system == "Darwin":
        plist_path = _launchd_plist_path()
        ensure_path = _launchd_ensure_plist_path()
        if plist_path.exists():
            res = subprocess.run(["launchctl", "unload", str(plist_path)], capture_output=True, text=True)
            if res.returncode != 0:
                return {
                    "uninstalled": False,
                    "manager": "launchd",
                    "reason": (getattr(res, "stderr", "") or "").strip() or f"launchctl unload exited with code {res.returncode}",
                }
            plist_path.unlink()
        if ensure_path.exists():
            subprocess.run(["launchctl", "unload", str(ensure_path)], capture_output=True, text=True)
            ensure_path.unlink()
        return {"uninstalled": True, "manager": "launchd"}
    elif system == "Linux":
        unit_path = _systemd_unit_path()
        res = _systemctl("disable", "--now", _SYSTEMD_UNIT_NAME)
        if res.returncode != 0:
            return {
                "uninstalled": False,
                "manager": "systemd",
                "reason": (getattr(res, "stderr", "") or "").strip() or f"systemctl disable exited with code {res.returncode}",
            }
        _systemctl("disable", "--now", _SYSTEMD_ENSURE_TIMER)
        for path in (unit_path, _systemd_ensure_service_path(), _systemd_ensure_timer_path()):
            if path.exists():
                path.unlink()
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


def _unit_matches() -> bool:
    """True when the on-disk units already match this interpreter and package root."""
    python_exe = sys.executable
    system = platform_name()
    try:
        if system == "Darwin":
            return (
                _launchd_plist_path().read_text() == _launchd_plist_contents(python_exe)
                and _launchd_ensure_plist_path().read_text() == _launchd_ensure_plist_contents(python_exe)
            )
        if system == "Linux":
            return (
                _systemd_unit_path().read_text() == _systemd_unit_contents(python_exe)
                and _systemd_ensure_service_path().read_text() == _systemd_ensure_service_contents(python_exe)
                and _systemd_ensure_timer_path().read_text() == _systemd_ensure_timer_contents()
            )
    except OSError:
        return False
    return False


def unhealthy_reason() -> Optional[str]:
    """Why the daemon should be restarted, or None when it is healthy."""
    if not _unit_matches():
        return "unit-drift"
    if not is_running():
        return "dead-pid"
    from synlynk._constants import VERSION
    from synlynk.viz.heartbeats import read_beat

    try:
        beat = read_beat(DAEMON_HOME, poll_interval_s=poll_interval())
    except Exception as exc:
        _log(f"ensure heartbeat read failed: {exc}")
        return "missing-beat"
    if not beat:
        return "missing-beat"
    if beat.get("status") != "running":
        return str(beat.get("status") or "stale")
    if (beat.get("version") or "") != VERSION:
        return "version-mismatch"
    return None


def _ensure_state_path() -> Path:
    return DAEMON_HOME / "ensure-state.json"


def _load_ensure_state() -> dict:
    try:
        return json.loads(_ensure_state_path().read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def _ensure_clock() -> float:
    import time

    return time.time()


def _format_attempt(epoch: float) -> str:
    import time

    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(epoch))


def _parse_attempt(text: str) -> Optional[float]:
    from datetime import datetime, timezone

    stamp = (text or "").strip()
    if not stamp:
        return None
    if stamp.endswith("Z"):
        stamp = stamp[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(stamp)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


def _recent_attempts(reason: str, now: float) -> list:
    """Attempt times for this reason that are still inside the backoff window."""
    state = _load_ensure_state()
    if state.get("reason") != reason:
        return []
    kept = []
    for stamp in state.get("attempts") or []:
        parsed = _parse_attempt(str(stamp))
        if parsed is None:
            continue
        if now - parsed < ENSURE_BACKOFF_WINDOW_S:
            kept.append(parsed)
    return kept


def _note_ensure_attempt(reason: str) -> None:
    now = _ensure_clock()
    kept = _recent_attempts(reason, now)
    kept.append(now)
    DAEMON_HOME.mkdir(parents=True, exist_ok=True)
    _ensure_state_path().write_text(json.dumps({
        "reason": reason,
        "count": len(kept),
        "attempts": [_format_attempt(item) for item in kept],
        "last_at": _format_attempt(now),
    }))


def _should_backoff(reason: str) -> bool:
    return len(_recent_attempts(reason, _ensure_clock())) >= ENSURE_BACKOFF_LIMIT


def _clear_ensure_state() -> None:
    try:
        _ensure_state_path().unlink()
    except OSError:
        return


def ensure() -> dict:
    """Restart when the unit, pid, beat, or version is wrong. No-op when healthy.

    The same reason backs off after three attempts inside ten minutes so a
    timer cannot kickstart a crash loop forever. This function does not start
    the ensure timer's own program (that would recurse through install).
    """
    cap_log()
    reason = unhealthy_reason()
    if reason is None:
        _clear_ensure_state()
        return {"ensured": True, "action": "noop"}
    if _should_backoff(reason):
        _log(f"ensure backoff: {reason}")
        return {"ensured": True, "action": "backoff", "reason": reason}
    _note_ensure_attempt(reason)
    result = install()
    result["action"] = "restart"
    result["reason"] = reason
    result["ensured"] = bool(result.get("installed"))
    return result


def _slug_for_checkout(cwd: str) -> Optional[str]:
    repo = Path(cwd)
    try:
        probe = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=str(repo),
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    if probe.returncode != 0 or probe.stdout.strip() != "true":
        return None
    try:
        from synlynk.product_store import identity_slug_from_config

        slug = identity_slug_from_config(repo)
    except Exception:
        return None
    return slug or None


def fence_hint(cwd: str = ".") -> Optional[str]:
    """Vizor URL for a task fence. None when the port file is absent.

    Does not call launchctl and does not read a product ledger.
    """
    port = _read_port()
    if not port:
        return None
    slug = _slug_for_checkout(cwd)
    if slug:
        return f"http://127.0.0.1:{port}/w/{slug}/overview.html"
    return f"http://127.0.0.1:{port}/"


if __name__ == "__main__":
    run_forever()
