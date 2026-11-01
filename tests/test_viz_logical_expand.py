"""Logical detail-on-expand: slim community JSON, skinny first paint (gh:#2671)."""
import importlib.util
import json
import socket
import threading
from http.server import HTTPServer
from pathlib import Path

from synlynk import vizor_daemon
from synlynk.viz import generate_logical_html
from synlynk.viz.logical_expand import load_logical_graph, logical_community_payload

_skinny_spec = importlib.util.spec_from_file_location(
    "test_viz_skinny_payloads",
    Path(__file__).resolve().parent / "test_viz_skinny_payloads.py",
)
_skinny = importlib.util.module_from_spec(_skinny_spec)
_skinny_spec.loader.exec_module(_skinny)
FAT_SENTINEL = _skinny.FAT_SENTINEL
MAX_HTML_BYTES = _skinny.MAX_HTML_BYTES
_fat_data = _skinny._fat_data


def _read_response(port: int, path: str) -> bytes:
    sock = socket.create_connection(("127.0.0.1", port), timeout=5)
    try:
        sock.sendall(
            f"GET {path} HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n".encode()
        )
        sock.settimeout(5)
        chunks = []
        while True:
            chunk = sock.recv(65536)
            if not chunk:
                break
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        sock.close()


def _registry(tmp_path, repo):
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
    return registry


def _serve(handler_cls):
    httpd = HTTPServer(("127.0.0.1", 0), handler_cls)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd


def test_fat_fixture_community_payload_omits_sentinel_and_attrs():
    logical = _fat_data()["workspace_views"]["logical"]
    payload = logical_community_payload(logical["nodes"], logical["edges"], "1")
    encoded = json.dumps(payload)
    assert FAT_SENTINEL not in encoded
    assert "attrs_json" not in encoded
    assert payload["community"] == "1"
    assert payload["nodes"]
    assert len(payload["nodes"]) <= 500
    for node in payload["nodes"]:
        assert set(node) == {"id", "label", "kind", "source_file", "community"}
        assert node["community"] == 1
    for edge in payload["edges"]:
        assert set(edge) <= {"from", "to", "kind"}
        assert isinstance(edge["from"], int)
        assert isinstance(edge["to"], int)
        assert edge["from"] < len(payload["nodes"])
        assert edge["to"] < len(payload["nodes"])


def test_logical_community_payload_caps_nodes_and_edges():
    nodes = [
        {
            "id": f"n{i}",
            "label": f"Node {i}",
            "kind": "function",
            "source_file": "synlynk/mod.py",
            "community": 7,
        }
        for i in range(501)
    ]
    edges = [
        {"from_id": "n0", "to_id": "n1", "kind": "calls", "attrs_json": '{"mark": "nope"}'}
        for _ in range(1001)
    ]
    payload = logical_community_payload(nodes, edges, "7")
    assert len(payload["nodes"]) == 500
    assert len(payload["edges"]) == 1000
    assert payload["truncated"] is True
    assert "attrs_json" not in json.dumps(payload)
    assert payload["edges"][0] == {"from": 0, "to": 1, "kind": "calls"}


def test_load_logical_graph_uses_projection_tables_without_graph_json(tmp_path):
    import sqlite3

    from synlynk.viz_views import init_workspace_view_tables

    db = tmp_path / "state.db"
    conn = sqlite3.connect(db)
    init_workspace_view_tables(conn)
    conn.execute(
        "INSERT INTO workspace_view_nodes "
        "(id, view, repo, kind, label, attrs_json, provenance, source_path, scanned_at, head_sha) "
        "VALUES (?, 'logical', 'acme', 'function', 'Alpha', ?, 'extracted', 'synlynk/alpha.py', "
        "'2026-11-01T00:00:00Z', 'abc')",
        ("n1", json.dumps({"community": 3, "mark": FAT_SENTINEL})),
    )
    conn.execute(
        "INSERT INTO workspace_view_edges "
        "(id, view, from_id, to_id, kind, provenance, attrs_json, scanned_at) "
        "VALUES ('e1', 'logical', 'n1', 'n1', 'calls', 'extracted', ?, '2026-11-01T00:00:00Z')",
        (json.dumps({"mark": FAT_SENTINEL}),),
    )
    conn.commit()
    conn.close()
    repo = tmp_path / "repo"
    repo.mkdir()

    nodes, edges = load_logical_graph(repo, db)
    payload = logical_community_payload(nodes, edges, "3")
    encoded = json.dumps(payload)
    assert FAT_SENTINEL not in encoded
    assert "attrs_json" not in encoded
    assert payload["nodes"][0]["source_file"] == "synlynk/alpha.py"
    assert payload["edges"] == [{"from": 0, "to": 0, "kind": "calls"}]


def test_logical_first_paint_stays_a_projection():
    html = generate_logical_html(_fat_data(), 33333)
    assert len(html.encode("utf-8")) < MAX_HTML_BYTES
    assert html.count('"id": "n') <= 16
    assert FAT_SENTINEL not in html
    assert "attrs_json" not in html
    assert "head_sha" not in html
    assert "scanned_at" not in html
    assert "workspace_views" not in html
    assert "api/logical?community=" in html
    assert "fetch('/logical')" not in html
    assert "fetch(\"/logical\")" not in html
    assert "graph/refresh" not in html
    assert "tools/install" not in html
    assert "hld-comp-card" in html
    assert "am-community-checkbox" in html
    assert "Presentation" in html


def test_daemon_get_logical_community_uses_registry(tmp_path, monkeypatch):
    home = tmp_path / "daemon-home"
    home.mkdir()
    monkeypatch.setattr(vizor_daemon, "DAEMON_HOME", home)
    monkeypatch.setattr(vizor_daemon, "PIDFILE", home / "pidfile")
    monkeypatch.setattr(vizor_daemon, "PORTFILE", home / "port")
    monkeypatch.setattr(vizor_daemon, "LOGFILE", home / "daemon.log")
    monkeypatch.setattr(vizor_daemon, "CACHE_ROOT", home / "cache")

    repo = tmp_path / "repo"
    out = repo / ".synlynk" / "graphify-out"
    out.mkdir(parents=True)
    (out / "graph.json").write_text(json.dumps({
        "nodes": [
            {
                "id": "n1",
                "label": "Alpha",
                "kind": "function",
                "source_file": "synlynk/alpha.py",
                "community": 1,
                "attrs_json": json.dumps({"mark": FAT_SENTINEL, "community": 1}),
                "head_sha": "a" * 40,
                "provenance": "graphify",
            },
            {
                "id": "n2",
                "label": "Beta",
                "kind": "class",
                "file": "synlynk/beta.py",
                "community": 1,
            },
            {
                "id": "n3",
                "label": "Gamma",
                "kind": "function",
                "community": 2,
                "attrs_json": json.dumps({"mark": FAT_SENTINEL}),
            },
        ],
        "edges": [
            {
                "source": "n1",
                "target": "n2",
                "kind": "calls",
                "attrs_json": json.dumps({"mark": FAT_SENTINEL}),
            },
            {"source": "n1", "target": "n3", "kind": "calls"},
        ],
    }))
    registry = _registry(tmp_path, repo)
    monkeypatch.setenv("SYNLYNK_REGISTRY_PATH", str(registry))

    handler = vizor_daemon.build_workspace_routing_handler()
    httpd = _serve(handler)
    try:
        port = httpd.server_address[1]
        ok = _read_response(port, "/w/acme/api/logical?community=1")
        missing_community = _read_response(port, "/w/acme/api/logical")
        blank_community = _read_response(port, "/w/acme/api/logical?community=")
        unknown = _read_response(port, "/w/missing/api/logical?community=1")
    finally:
        httpd.shutdown()
        httpd.server_close()

    ok_text = ok.decode("utf-8", errors="replace")
    assert " 200 " in ok_text
    body = json.loads(ok_text.split("\r\n\r\n", 1)[1])
    encoded = json.dumps(body)
    assert FAT_SENTINEL not in encoded
    assert "attrs_json" not in encoded
    assert "head_sha" not in encoded
    assert "provenance" not in encoded
    assert body["community"] == "1"
    assert [node["id"] for node in body["nodes"]] == ["n1", "n2"]
    assert body["nodes"][0]["source_file"] == "synlynk/alpha.py"
    assert body["nodes"][1]["source_file"] == "synlynk/beta.py"
    assert body["edges"] == [{"from": 0, "to": 1, "kind": "calls"}]
    assert "truncated" not in body

    for raw in (missing_community, blank_community):
        text = raw.decode("utf-8", errors="replace")
        assert " 400 " in text

    unknown_text = unknown.decode("utf-8", errors="replace")
    assert " 404 " in unknown_text
    assert "Unknown workspace" in unknown_text
