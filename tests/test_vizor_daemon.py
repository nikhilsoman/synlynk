import os
import json
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
    home = tmp_path / "daemon-home"
    monkeypatch.setattr("synlynk.vizor_daemon.DAEMON_HOME", home)
    monkeypatch.setattr("synlynk.vizor_daemon.LOGFILE", home / "daemon.log")

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
    home = tmp_path / "daemon-home"
    monkeypatch.setattr("synlynk.vizor_daemon.DAEMON_HOME", home)
    monkeypatch.setattr("synlynk.vizor_daemon.LOGFILE", home / "daemon.log")

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


def test_resolve_slug_from_path_valid(tmp_path, monkeypatch):
    from synlynk import vizor_daemon

    monkeypatch.setattr(vizor_daemon, "_known_slugs", lambda: {"acme"})
    slug, rest = vizor_daemon.parse_workspace_path("/w/acme/overview.html")
    assert slug == "acme"
    assert rest == "/acme/overview.html"

    slug, rest = vizor_daemon.parse_workspace_path("/w/acme/")
    assert slug == "acme"
    assert rest == "/acme/index.html"

    slug, rest = vizor_daemon.parse_workspace_path("/w/acme/manifest.json")
    assert slug == "acme"
    assert rest == "/acme/manifest.json"


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


def test_rewrite_workspace_app_route_for_known_slug(monkeypatch):
    monkeypatch.setattr(vizor_daemon, "_known_slugs", lambda: {"acme"})

    assert vizor_daemon._rewrite_workspace_app_route("/w/acme/onboarding/roles") == "/onboarding/roles"
    assert vizor_daemon._rewrite_workspace_app_route("/w/acme/onboarding/roles/") == "/onboarding/roles/"


def test_rewrite_workspace_app_route_rejects_unknown_slug(monkeypatch):
    monkeypatch.setattr(vizor_daemon, "_known_slugs", lambda: {"acme"})

    assert vizor_daemon._rewrite_workspace_app_route("/w/ghost/onboarding/roles") is None


def test_workspace_index_lists_registered_slugs(monkeypatch):
    from synlynk import vizor_daemon

    monkeypatch.setattr(vizor_daemon, "_known_slugs", lambda: {"acme", "beta"})
    html = vizor_daemon._workspace_index_html()
    assert "acme" in html and "beta" in html


def test_workspace_index_empty(monkeypatch):
    from synlynk import vizor_daemon

    monkeypatch.setattr(vizor_daemon, "_known_slugs", lambda: set())
    html = vizor_daemon._workspace_index_html()
    assert "No registered workspaces" in html


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


def test_install_nonzero_returncode_reports_failure(tmp_path, monkeypatch):
    from synlynk import vizor_daemon

    monkeypatch.setattr(vizor_daemon, "platform_name", lambda: "Darwin")
    monkeypatch.setattr(vizor_daemon, "_launchd_plist_path", lambda: tmp_path / "com.synlynk.vizor-daemon.plist")
    monkeypatch.setattr(
        vizor_daemon.subprocess,
        "run",
        lambda *a, **k: type("R", (), {"returncode": 1, "stderr": "service already loaded"})(),
    )

    result = vizor_daemon.install()
    assert result["installed"] is False
    assert "service already loaded" in result["reason"]


def test_uninstall_nonzero_returncode_reports_failure(tmp_path, monkeypatch):
    from synlynk import vizor_daemon

    monkeypatch.setattr(vizor_daemon, "platform_name", lambda: "Darwin")
    plist_path = tmp_path / "com.synlynk.vizor-daemon.plist"
    plist_path.write_text("dummy")
    monkeypatch.setattr(vizor_daemon, "_launchd_plist_path", lambda: plist_path)
    monkeypatch.setattr(
        vizor_daemon.subprocess,
        "run",
        lambda *a, **k: type("R", (), {"returncode": 1, "stderr": "permission denied"})(),
    )

    result = vizor_daemon.uninstall()
    assert result["uninstalled"] is False
    assert "permission denied" in result["reason"]
    assert plist_path.exists(), "plist should not be unlinked when unload fails"


def test_launchd_plist_sets_pythonpath_and_throttle():
    from synlynk import vizor_daemon

    xml = vizor_daemon._launchd_plist_contents("/usr/bin/python3")
    root = vizor_daemon._synlynk_import_root()
    assert "<key>PYTHONPATH</key>" in xml
    assert f"<string>{root}</string>" in xml
    assert "<key>ThrottleInterval</key>" in xml
    assert "<integer>30</integer>" in xml
    assert str(vizor_daemon.DAEMON_HOME) in xml


def test_systemd_unit_sets_pythonpath():
    from synlynk import vizor_daemon

    unit = vizor_daemon._systemd_unit_contents("/usr/bin/python3")
    root = vizor_daemon._synlynk_import_root()
    assert f"Environment=PYTHONPATH={root}" in unit
    assert "RestartSec=30" in unit


def test_probe_health_alerts_on_import_crashloop(tmp_path, monkeypatch):
    from synlynk import vizor_daemon
    from synlynk.sentinel import _write_sentinel_alert

    log = tmp_path / "daemon.log"
    log.write_text(
        "/opt/homebrew/opt/python@3.14/bin/python3.14: Error while finding "
        "module specification for 'synlynk.vizor_daemon' "
        "(ModuleNotFoundError: No module named 'synlynk')\n" * 3
    )
    sentinel = tmp_path / "sentinel.md"
    monkeypatch.setattr(vizor_daemon, "LOGFILE", log)
    monkeypatch.setattr(vizor_daemon, "is_running", lambda: False)
    monkeypatch.setattr(vizor_daemon, "status", lambda: {"service_registered": True, "running": False})

    alerts = []

    def capture(severity, code, message, sentinel_path=None):
        alerts.append((severity, code, message))
        return _write_sentinel_alert(severity, code, message, sentinel_path=str(sentinel))

    monkeypatch.setattr("synlynk.sentinel._write_sentinel_alert", capture)
    result = vizor_daemon.probe_health()
    assert result["ok"] is False
    assert result["code"] == "VIZOR_DAEMON_CRASHLOOP"
    assert alerts and alerts[0][0] == "CRITICAL"


def test_install_systemd_nonzero_returncode_reports_failure(tmp_path, monkeypatch):
    from synlynk import vizor_daemon

    monkeypatch.setattr(vizor_daemon, "platform_name", lambda: "Linux")
    monkeypatch.setattr(vizor_daemon, "_systemd_unit_path", lambda: tmp_path / "synlynk-vizor-daemon.service")
    monkeypatch.setattr(
        vizor_daemon.subprocess,
        "run",
        lambda *a, **k: type("R", (), {"returncode": 1, "stderr": "Failed to connect to bus"})(),
    )

    result = vizor_daemon.install()
    assert result["installed"] is False
    assert "Failed to connect to bus" in result["reason"]


def test_workspace_render_context_uses_mutex_lock(tmp_path):
    from synlynk import vizor_daemon

    repo = tmp_path / "repo"
    repo.mkdir()
    db_path = tmp_path / "state.db"
    db_path.write_bytes(b"")

    assert not vizor_daemon._RENDER_LOCK.locked()
    with vizor_daemon.workspace_render_context(repo, db_path, tmp_path / "cache"):
        assert vizor_daemon._RENDER_LOCK.locked()
    assert not vizor_daemon._RENDER_LOCK.locked()


def test_workspace_render_context_thread_safety(tmp_path):
    import time
    import threading
    from synlynk import vizor_daemon
    import synlynk.viz as viz_module

    repo_a = tmp_path / "repo_a"
    repo_a.mkdir()
    db_a = tmp_path / "a.db"
    db_a.write_bytes(b"")

    repo_b = tmp_path / "repo_b"
    repo_b.mkdir()
    db_b = tmp_path / "b.db"
    db_b.write_bytes(b"")

    results = []

    def run_a():
        with vizor_daemon.workspace_render_context(repo_a, db_a, tmp_path / "cache_a"):
            time.sleep(0.05)
            results.append(("a", os.getcwd(), viz_module.VIZ_CACHE_DIR))

    def run_b():
        time.sleep(0.01)
        with vizor_daemon.workspace_render_context(repo_b, db_b, tmp_path / "cache_b"):
            results.append(("b", os.getcwd(), viz_module.VIZ_CACHE_DIR))

    t1 = threading.Thread(target=run_a)
    t2 = threading.Thread(target=run_b)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert len(results) == 2
    # Ensure sequential serialized execution with consistent CWD and cache dir
    assert results[0][0] == "a"
    assert results[0][1] == str(repo_a.resolve())
    assert results[0][2] == str(tmp_path / "cache_a")
    assert results[1][0] == "b"
    assert results[1][1] == str(repo_b.resolve())
    assert results[1][2] == str(tmp_path / "cache_b")


def _isolate_daemon_home(monkeypatch, home):
    home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(vizor_daemon, "DAEMON_HOME", home)
    monkeypatch.setattr(vizor_daemon, "PIDFILE", home / "pidfile")
    monkeypatch.setattr(vizor_daemon, "PORTFILE", home / "port")
    monkeypatch.setattr(vizor_daemon, "LOGFILE", home / "daemon.log")


def test_poll_once_records_slug_then_idle(tmp_path, monkeypatch):
    from synlynk.viz.heartbeats import read_beat

    _isolate_daemon_home(monkeypatch, tmp_path / "home")
    monkeypatch.setenv("SYNLYNK_REGISTRY_PATH", str(tmp_path / "registry.json"))
    repo = tmp_path / "repo"
    repo.mkdir()
    db = tmp_path / "state.db"
    db.write_bytes(b"")
    _seed_registry(tmp_path / "registry.json", "acme", repo, db)
    seen = []

    def spy(slug, entry, port):
        row = read_beat(vizor_daemon.DAEMON_HOME, poll_interval_s=15)
        seen.append(row["active_task"])

    monkeypatch.setattr(vizor_daemon, "refresh_workspace", spy)
    results = vizor_daemon.poll_once(port=8721)
    assert results == {"acme": "ok"}
    assert seen == ["acme"]
    done = read_beat(vizor_daemon.DAEMON_HOME, poll_interval_s=15)
    assert done["active_task"] == "idle"
    assert done["cycle_count"] == 1
    assert done["harness"] == "vizor"


def test_poll_once_survives_heartbeat_errors(tmp_path, monkeypatch):
    import sqlite3

    from synlynk.viz import heartbeats

    _isolate_daemon_home(monkeypatch, tmp_path / "home")
    monkeypatch.setenv("SYNLYNK_REGISTRY_PATH", str(tmp_path / "registry.json"))
    repo = tmp_path / "repo"
    repo.mkdir()
    db = tmp_path / "state.db"
    db.write_bytes(b"")
    _seed_registry(tmp_path / "registry.json", "acme", repo, db)
    monkeypatch.setattr(vizor_daemon, "refresh_workspace", lambda *a, **k: None)

    def boom(*args, **kwargs):
        raise sqlite3.OperationalError("disk")

    monkeypatch.setattr(heartbeats, "upsert_beat", boom)
    monkeypatch.setattr(heartbeats, "read_beat", boom)
    results = vizor_daemon.poll_once(port=8721)
    assert results == {"acme": "ok"}


def test_run_forever_marks_stopped_when_the_server_exits(tmp_path, monkeypatch):
    import http.server

    from synlynk.viz.heartbeats import read_beat

    _isolate_daemon_home(monkeypatch, tmp_path / "home")
    monkeypatch.setattr(vizor_daemon, "probe_health", lambda: {"ok": True})
    monkeypatch.setattr(vizor_daemon, "resolve_listen_port", lambda port=None: 0)
    monkeypatch.setattr(vizor_daemon, "poll_once", lambda port: {})
    monkeypatch.setattr(vizor_daemon, "build_workspace_routing_handler", lambda: object)

    class FakeServer:
        def __init__(self, addr, handler):
            self.addr = addr

        def serve_forever(self):
            raise KeyboardInterrupt

        def shutdown(self):
            return None

        def server_close(self):
            return None

    monkeypatch.setattr(http.server, "HTTPServer", FakeServer)
    vizor_daemon.run_forever()
    row = read_beat(vizor_daemon.DAEMON_HOME, poll_interval_s=15)
    assert row["status"] == "stopped"


def test_resolve_listen_port_skips_a_taken_port(tmp_path, monkeypatch):
    import socket
    from synlynk.viz.constants import MEMORABLE_VIZOR_PORTS

    _isolate_daemon_home(monkeypatch, tmp_path / "home")
    held = socket.socket()
    held.bind(("127.0.0.1", 0))
    held.listen(1)
    preferred = held.getsockname()[1]
    try:
        chosen = vizor_daemon.resolve_listen_port(preferred)
    finally:
        held.close()
    assert chosen != preferred
    assert chosen in MEMORABLE_VIZOR_PORTS or chosen == 8721


def test_cap_log_keeps_the_tail(tmp_path, monkeypatch):
    _isolate_daemon_home(monkeypatch, tmp_path / "home")
    payload = b"A" * (vizor_daemon.LOG_MAX_BYTES + 100) + b"\nTAIL\n"
    vizor_daemon.LOGFILE.write_bytes(payload)
    vizor_daemon.cap_log()
    text = vizor_daemon.LOGFILE.read_text()
    assert "TAIL" in text
    assert vizor_daemon.LOGFILE.stat().st_size < vizor_daemon.LOG_MAX_BYTES


def test_ensure_noop_does_not_install(monkeypatch):
    calls = []
    monkeypatch.setattr(vizor_daemon, "cap_log", lambda: None)
    monkeypatch.setattr(vizor_daemon, "unhealthy_reason", lambda: None)
    monkeypatch.setattr(vizor_daemon, "install", lambda: calls.append("install"))
    result = vizor_daemon.ensure()
    assert result["action"] == "noop"
    assert calls == []


def test_ensure_restarts_a_dead_daemon(tmp_path, monkeypatch):
    _isolate_daemon_home(monkeypatch, tmp_path / "home")
    monkeypatch.setattr(vizor_daemon, "unhealthy_reason", lambda: "dead-pid")
    monkeypatch.setattr(vizor_daemon, "install", lambda: {"installed": True, "manager": "launchd"})
    result = vizor_daemon.ensure()
    assert result["action"] == "restart"
    assert result["reason"] == "dead-pid"
    assert result["ensured"] is True


def test_ensure_backs_off_after_repeated_failures(tmp_path, monkeypatch):
    _isolate_daemon_home(monkeypatch, tmp_path / "home")
    monkeypatch.setattr(vizor_daemon, "unhealthy_reason", lambda: "dead-pid")
    installs = []
    monkeypatch.setattr(
        vizor_daemon,
        "install",
        lambda: installs.append("install") or {"installed": False, "reason": "boom"},
    )
    for _ in range(vizor_daemon.ENSURE_BACKOFF_LIMIT):
        vizor_daemon.ensure()
    result = vizor_daemon.ensure()
    assert result["action"] == "backoff"
    assert result["reason"] == "dead-pid"
    assert len(installs) == vizor_daemon.ENSURE_BACKOFF_LIMIT


def test_unhealthy_reason_flags_version_mismatch(tmp_path, monkeypatch):
    from datetime import datetime, timezone

    from synlynk.viz.heartbeats import upsert_beat

    _isolate_daemon_home(monkeypatch, tmp_path / "home")
    monkeypatch.setattr(vizor_daemon, "_unit_matches", lambda: True)
    monkeypatch.setattr(vizor_daemon, "is_running", lambda: True)
    upsert_beat(
        vizor_daemon.DAEMON_HOME,
        pid=os.getpid(),
        status="running",
        last_beat_at=datetime.now(timezone.utc),
        cycle_count=1,
        active_task="idle",
        version="0.0.0",
    )
    assert vizor_daemon.unhealthy_reason() == "version-mismatch"


def test_stall_watch_returns_when_stop_is_already_set():
    import threading

    stop = threading.Event()
    stop.set()
    vizor_daemon._watch_for_stall(stop)


def test_fence_hint_uses_port_and_slug(tmp_path, monkeypatch):
    home = tmp_path / "home"
    _isolate_daemon_home(monkeypatch, home)
    (home / "port").write_text("8721")
    monkeypatch.setattr(vizor_daemon, "_slug_for_checkout", lambda cwd=".": "acme")
    assert vizor_daemon.fence_hint() == "http://127.0.0.1:8721/w/acme/overview.html"


def test_fence_hint_is_hub_url_without_a_checkout(tmp_path, monkeypatch):
    home = tmp_path / "home"
    _isolate_daemon_home(monkeypatch, home)
    (home / "port").write_text("8721")
    monkeypatch.setattr(vizor_daemon, "_slug_for_checkout", lambda cwd=".": None)
    assert vizor_daemon.fence_hint() == "http://127.0.0.1:8721/"


def test_fence_hint_absent_without_a_port_file(tmp_path, monkeypatch):
    _isolate_daemon_home(monkeypatch, tmp_path / "home")
    assert vizor_daemon.fence_hint() is None


def test_launchd_plist_marks_the_daemon_process(tmp_path, monkeypatch):
    xml = vizor_daemon._launchd_plist_contents("/usr/bin/python3")
    ensure_xml = vizor_daemon._launchd_ensure_plist_contents("/usr/bin/python3")
    assert "<key>SYNLYNK_VIZOR_DAEMON</key>" in xml
    assert "<string>1</string>" in xml
    assert "<key>StartInterval</key>" in ensure_xml
    assert "<integer>60</integer>" in ensure_xml
    assert "synlynk.vizor_ensure" in ensure_xml
    assert "<false/>" in ensure_xml


def test_daemon_import_skips_product_root_outside_a_checkout(tmp_path):
    import subprocess
    import sys

    home = tmp_path / "not-a-repo"
    home.mkdir()
    root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    for key in (
        "SYNLYNK_ALLOW_CWD_FALLBACK",
        "SYNLYNK_STATE_DB_PATH",
        "SYNLYNK_VIZOR_DAEMON",
    ):
        env.pop(key, None)
    env["PYTHONPATH"] = str(root) + os.pathsep + env.get("PYTHONPATH", "")
    env["SYNLYNK_VIZOR_DAEMON"] = "1"
    env["SYNLYNK_VIZOR_DAEMON_HOME"] = str(tmp_path / "daemon-home")
    script = "import os, synlynk; assert synlynk.DB_PATH == os.devnull; print('ok')"
    proc = subprocess.run(
        [sys.executable, "-c", script],
        cwd=home,
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert not (home / "state.db").exists()
    assert not (tmp_path / "daemon-home" / "state.db").exists()


def test_non_daemon_import_still_refuses_a_non_git_cwd(tmp_path):
    import subprocess
    import sys

    home = tmp_path / "not-a-repo"
    home.mkdir()
    root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    for key in (
        "SYNLYNK_ALLOW_CWD_FALLBACK",
        "SYNLYNK_STATE_DB_PATH",
        "SYNLYNK_VIZOR_DAEMON",
    ):
        env.pop(key, None)
    env["PYTHONPATH"] = str(root) + os.pathsep + env.get("PYTHONPATH", "")
    proc = subprocess.run(
        [sys.executable, "-c", "import synlynk"],
        cwd=home,
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode != 0
    assert "1831" in proc.stderr


def test_resolve_listen_port_returns_none_when_already_running(tmp_path, monkeypatch):
    home = tmp_path / "home"
    _isolate_daemon_home(monkeypatch, home)
    (home / "pidfile").write_text(str(os.getpid()))
    (home / "port").write_text("33333")
    assert vizor_daemon.resolve_listen_port(33333) is None


def test_mark_daemon_stopped_records_stopped(tmp_path, monkeypatch):
    from synlynk.viz.heartbeats import read_beat

    _isolate_daemon_home(monkeypatch, tmp_path / "home")
    vizor_daemon.mark_daemon_stopped()
    row = read_beat(vizor_daemon.DAEMON_HOME, poll_interval_s=15)
    assert row["status"] == "stopped"
    assert row["harness"] == "vizor"

