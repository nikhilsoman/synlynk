# tests/test_viz_graphify.py
import json
import sqlite3
import pytest
from pathlib import Path
from synlynk.viz_views import extract_logical_nodes, init_workspace_view_tables, build_workspace_views_snapshot
from synlynk.viz import generate_logical_html


def test_extract_logical_nodes_enriches_from_graphify_when_present(tmp_path, monkeypatch):
    conn = sqlite3.connect(":memory:")
    init_workspace_view_tables(conn)

    out_dir = tmp_path / ".synlynk" / "graphify-out"
    out_dir.mkdir(parents=True)
    graph_data = {
        "nodes": [
            {"id": "synlynk.discovery:scan_workspace_static", "label": "scan_workspace_static", "kind": "function", "community": 2},
            {"id": "synlynk.cli:main", "label": "main", "kind": "function", "community": 2},
        ],
        "edges": [
            {"source": "synlynk.cli:main", "target": "synlynk.discovery:scan_workspace_static", "kind": "calls"}
        ]
    }
    (out_dir / "graph.json").write_text(json.dumps(graph_data))
    (out_dir / "manifest.json").write_text(json.dumps({"built_at_commit": "sha123"}))

    nodes, edges = extract_logical_nodes(conn, str(tmp_path))
    node_labels = [n["label"] for n in nodes]
    assert "scan_workspace_static" in node_labels
    assert "main" in node_labels
    assert len(edges) >= 1
    assert all(n["provenance"] == "graphify" for n in nodes)
    assert all(e["provenance"] == "graphify" for e in edges)


def test_extract_logical_nodes_records_community_and_centrality(tmp_path):
    conn = sqlite3.connect(":memory:")
    init_workspace_view_tables(conn)

    out_dir = tmp_path / ".synlynk" / "graphify-out"
    out_dir.mkdir(parents=True)
    graph_data = {
        "nodes": [
            {"id": "a", "label": "alpha", "kind": "module", "community": 5, "centrality": 0.95},
            {"id": "b", "label": "beta", "kind": "module", "community": 5},
        ],
        "edges": [
            {"source": "a", "target": "b", "kind": "imports"}
        ]
    }
    (out_dir / "graph.json").write_text(json.dumps(graph_data))
    (out_dir / "manifest.json").write_text(json.dumps({"built_at_commit": "sha123"}))

    nodes, edges = extract_logical_nodes(conn, str(tmp_path))
    node_map = {n["label"]: n for n in nodes}
    attrs_a = json.loads(node_map["alpha"]["attrs_json"])
    assert attrs_a["community"] == 5
    assert attrs_a["centrality"] == 0.95
    attrs_b = json.loads(node_map["beta"]["attrs_json"])
    assert attrs_b["community"] == 5
    assert "centrality" in attrs_b


def test_extract_logical_nodes_flags_stale_when_head_advanced(tmp_path, monkeypatch):
    conn = sqlite3.connect(":memory:")
    init_workspace_view_tables(conn)

    out_dir = tmp_path / ".synlynk" / "graphify-out"
    out_dir.mkdir(parents=True)
    graph_data = {
        "nodes": [
            {"id": "x", "label": "x_func", "kind": "function", "community": 1},
        ],
        "edges": []
    }
    (out_dir / "graph.json").write_text(json.dumps(graph_data))
    (out_dir / "manifest.json").write_text(json.dumps({"built_at_commit": "sha123"}))

    # Mock head sha to be different
    monkeypatch.setattr("synlynk.viz_views._head_sha", lambda r: "sha456_advanced")

    nodes, edges = extract_logical_nodes(conn, str(tmp_path))
    row = conn.execute("SELECT stale FROM workspace_view_meta WHERE view = 'logical'").fetchone()
    assert row is not None
    assert row[0] == 1

    snapshot = build_workspace_views_snapshot(conn, str(tmp_path))
    assert snapshot["logical"]["stale"] is True


def test_generate_logical_html_renders_amber_staleness_banner():
    data = {
        "workspace": {"name": "test-repo"},
        "workspace_views": {
            "logical": {
                "nodes": [{"id": "n1", "label": "main", "kind": "function", "attrs_json": "{}"}],
                "edges": [],
                "stale": True,
            }
        }
    }
    html = generate_logical_html(data, 8721)
    assert 'id="graph-stale-banner"' in html
    assert "Graph Stale" in html

    # Verify when not stale, banner is not rendered
    data["workspace_views"]["logical"]["stale"] = False
    html_clean = generate_logical_html(data, 8721)
    assert 'id="graph-stale-banner"' not in html_clean
    assert "Graph Stale" not in html_clean


def test_extract_logical_nodes_malformed_graph_json_falls_back(tmp_path):
    conn = sqlite3.connect(":memory:")
    init_workspace_view_tables(conn)

    out_dir = tmp_path / ".synlynk" / "graphify-out"
    out_dir.mkdir(parents=True)
    # Malformed graph.json with unexpected schema
    (out_dir / "graph.json").write_text(json.dumps({"nodes": 123, "edges": "bad"}))

    # Add a python file in the repository root
    (tmp_path / "app.py").write_text("print('hello')\n")

    nodes, edges = extract_logical_nodes(conn, str(tmp_path))
    assert any(n["label"] == "app.py" for n in nodes)
    assert all(n["provenance"] == "extracted" for n in nodes)


def test_generate_logical_html_string_community():
    data = {
        "workspace": {"name": "test-repo"},
        "workspace_views": {
            "logical": {
                "nodes": [{"id": "n1", "label": "core_module", "kind": "module", "attrs_json": json.dumps({"community": "core"})}],
                "edges": [],
            }
        }
    }
    html = generate_logical_html(data, 8721)
    assert "core_module" in html
    assert "bs6RenderGraph" in html
