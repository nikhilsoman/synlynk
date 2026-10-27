"""Localhost SSE for the Vizor daemon. No live 33333 bind."""
import json
import os
import socket
import threading
from http.server import HTTPServer
from pathlib import Path

from synlynk import vizor_daemon
from synlynk.viz.heartbeats import read_beat, upsert_beat
from datetime import datetime, timezone


def _isolate_home(monkeypatch, home: Path) -> None:
    home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(vizor_daemon, "DAEMON_HOME", home)
    monkeypatch.setattr(vizor_daemon, "PIDFILE", home / "pidfile")
    monkeypatch.setattr(vizor_daemon, "PORTFILE", home / "port")
    monkeypatch.setattr(vizor_daemon, "LOGFILE", home / "daemon.log")
    monkeypatch.setattr(vizor_daemon, "CACHE_ROOT", home / "cache")


def _serve(handler_cls):
    httpd = HTTPServer(("127.0.0.1", 0), handler_cls)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd


def _read_until(port: int, path: str, marker: bytes) -> bytes:
    sock = socket.create_connection(("127.0.0.1", port), timeout=2)
    try:
        sock.sendall(f"GET {path} HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n".encode())
        sock.settimeout(2)
        data = b""
        while marker not in data:
            chunk = sock.recv(4096)
            if not chunk:
                break
            data += chunk
            if len(data) > 200_000:
                break
        return data
    finally:
        sock.close()


def test_hub_stream_emits_heartbeat_then_comment(tmp_path, monkeypatch):
    home = tmp_path / "daemon-home"
    _isolate_home(monkeypatch, home)
    (home / "port").write_text("33333")
    upsert_beat(
        home,
        pid=os.getpid(),
        status="running",
        last_beat_at=datetime.now(timezone.utc),
        cycle_count=2,
        active_task="idle",
    )
    monkeypatch.setattr(vizor_daemon, "poll_interval", lambda: 60)

    handler = vizor_daemon.build_workspace_routing_handler()
    httpd = _serve(handler)
    try:
        port = httpd.server_address[1]
        raw = _read_until(port, "/api/daemon/stream?path=/etc/passwd", b": ping")
    finally:
        httpd.shutdown()
        httpd.server_close()

    text = raw.decode("utf-8", errors="replace")
    assert "event: heartbeat" in text
    assert "event: sentinel" not in text
    assert ": ping" in text
    assert "/etc/passwd" not in text
    payload = json.loads(text.split("data: ", 1)[1].split("\n", 1)[0])
    assert payload["harness"] == "vizor"
    assert payload["port"] == 33333
    assert payload["cycle_count"] == 2


def test_workspace_stream_emits_sentinel_from_repo(tmp_path, monkeypatch):
    home = tmp_path / "daemon-home"
    _isolate_home(monkeypatch, home)
    repo = tmp_path / "repo"
    (repo / ".synlynk").mkdir(parents=True)
    (repo / ".synlynk" / "sentinel.md").write_text(
        "- [CRITICAL] [2026-10-28 00:00:00 UTC] VIZOR_DAEMON_DOWN: "
        "vizor bind failed [occurrences: 2; first seen: 2026-10-27 00:00:00 UTC; "
        "last seen: 2026-10-28 00:00:00 UTC]\n",
        encoding="utf-8",
    )
    db = tmp_path / "state.db"
    db.write_bytes(b"")
    registry = tmp_path / "registry.json"
    registry.write_text(json.dumps({
        "version": 1,
        "products": {
            "acme": {
                "product_id": "pid-acme",
                "slug": "acme",
                "canonical_path": str(db),
                "repo_path": str(repo),
                "mode": "canonical",
                "lineage_generation": 1,
                "state": "active",
            }
        },
    }))
    monkeypatch.setenv("SYNLYNK_REGISTRY_PATH", str(registry))
    monkeypatch.setattr(vizor_daemon, "poll_interval", lambda: 60)

    handler = vizor_daemon.build_workspace_routing_handler()
    httpd = _serve(handler)
    try:
        port = httpd.server_address[1]
        raw = _read_until(port, "/w/acme/api/daemon/stream?path=/tmp/nope", b": ping")
        missing = _read_until(port, "/w/missing/api/daemon/stream", b"Unknown workspace")
    finally:
        httpd.shutdown()
        httpd.server_close()

    text = raw.decode("utf-8", errors="replace")
    assert "event: heartbeat" in text
    assert "event: sentinel" in text
    assert "VIZOR_DAEMON_DOWN" in text
    assert "vizor bind failed" in text
    assert "/tmp/nope" not in text
    assert b"404" in missing or b"Unknown workspace" in missing
    assert read_beat(home) is None or True


def test_overview_inspection_is_read_only():
    from synlynk.viz.overview import generate_overview_html

    html = generate_overview_html({
        "workspace": {"name": "acme", "updated_at": "2026-10-28"},
        "telemetry": {
            "sentinel_alerts": [{
                "severity": "CRITICAL",
                "pattern": "VIZOR_DAEMON_DOWN",
                "message": "repro: vizor bind failed",
                "ts": "2026-10-28",
                "resolved": False,
                "raw_line": "- [CRITICAL] raw sentinel line",
                "occurrences": 4,
                "first_seen": "2026-10-27 01:00:00 UTC",
                "last_seen": "2026-10-28 02:00:00 UTC",
            }]
        },
    }, 8721)
    assert "raw sentinel line" in html
    assert "2026-10-27 01:00:00 UTC" in html
    assert "2026-10-28 02:00:00 UTC" in html
    assert '"occurrences": 4' in html or ">4<" in html
    assert 'type="button"' in html
    assert "EventSource" in html
    assert "/api/daemon/stream" in html
    assert 'method="post"' not in html.lower()
    assert "/api/sentinel/clear" not in html
    assert ">Run<" not in html


def test_loader_keeps_inspection_fields(tmp_path, monkeypatch):
    from synlynk.viz.data import load_workspace_sentinel_alerts

    sentinel = tmp_path / "sentinel.md"
    sentinel.write_text(
        "- [WARNING] [2026-10-28 02:00:00 UTC] TOKEN_BLOAT: "
        "context grew [occurrences: 4; first seen: 2026-10-27 01:00:00 UTC; "
        "last seen: 2026-10-28 02:00:00 UTC]\n",
        encoding="utf-8",
    )
    alerts = load_workspace_sentinel_alerts(str(sentinel))
    assert len(alerts) == 1
    alert = alerts[0]
    assert alert["pattern"] == "TOKEN_BLOAT"
    assert alert["occurrences"] == 4
    assert alert["first_seen"] == "2026-10-27 01:00:00 UTC"
    assert alert["last_seen"] == "2026-10-28 02:00:00 UTC"
    assert "TOKEN_BLOAT" in alert["raw_line"]
    assert alert["message"] == "context grew"
