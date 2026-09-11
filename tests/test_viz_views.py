import sqlite3

from synlynk.viz_views import (
    build_workspace_views_snapshot,
    extract_infra_nodes,
    extract_logical_nodes,
    extract_product_nodes,
    init_workspace_view_tables,
)


def test_init_workspace_view_tables():
    conn = sqlite3.connect(":memory:")
    init_workspace_view_tables(conn)
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"workspace_view_nodes", "workspace_view_edges", "workspace_view_meta"} <= tables


def test_extract_product_nodes_with_journeys(tmp_path):
    conn = sqlite3.connect(":memory:")
    journeys_dir = tmp_path / "docs" / "journeys"
    journeys_dir.mkdir(parents=True)
    (journeys_dir / "onboarding.md").write_text(
        "# Developer Onboarding\n\n## CLI Init\nroute: /cli/init\ndesc: First setup\n"
    )
    nodes, edges = extract_product_nodes(conn, str(tmp_path))
    assert any(n["kind"] == "journey" for n in nodes)
    assert any(n["kind"] == "route" for n in nodes)
    assert edges and conn.execute("SELECT COUNT(*) FROM workspace_view_nodes").fetchone()[0] == 2


def test_extract_logical_nodes_structure(tmp_path):
    conn = sqlite3.connect(":memory:")
    pkg_dir = tmp_path / "synlynk"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text("# init")
    (pkg_dir / "viz.py").write_text("import os\n")
    nodes, _ = extract_logical_nodes(conn, str(tmp_path))
    assert any(n["kind"] == "package" and n["label"] == "synlynk" for n in nodes)
    assert conn.execute("SELECT COUNT(*) FROM workspace_view_edges").fetchone()[0] == 2


def test_extract_infra_nodes_daemon(tmp_path):
    conn = sqlite3.connect(":memory:")
    nodes, edges = extract_infra_nodes(conn, str(tmp_path))
    assert any(n["kind"] == "service" and "vizor" in n["label"].lower() for n in nodes)
    assert edges[0]["kind"] == "manages"


def test_build_workspace_views_snapshot(tmp_path):
    conn = sqlite3.connect(":memory:")
    snapshot = build_workspace_views_snapshot(conn, str(tmp_path))
    assert {"product", "logical", "infra"} <= snapshot.keys()
    assert conn.execute("SELECT COUNT(*) FROM workspace_view_meta").fetchone()[0] == 3
