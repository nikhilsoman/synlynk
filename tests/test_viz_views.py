import sqlite3

from synlynk.viz_views import (
    build_workspace_views_snapshot,
    extract_infra_nodes,
    extract_logical_nodes,
    extract_product_nodes,
    extract_world_nodes,
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


def test_extract_world_nodes_egress(tmp_path):
    conn = sqlite3.connect(":memory:")
    # Create fake integration file
    app_file = tmp_path / "app.py"
    app_file.write_text("import stripe\nimport openai\nimport boto3\n")
    nodes, edges = extract_world_nodes(conn, str(tmp_path))
    assert any(n["kind"] == "workspace" for n in nodes)
    assert any("stripe" in n["label"].lower() for n in nodes)
    assert any("openai" in n["label"].lower() for n in nodes)
    assert any("aws" in n["label"].lower() for n in nodes)
    assert len(edges) >= 3


def test_build_workspace_views_snapshot(tmp_path):
    conn = sqlite3.connect(":memory:")
    snapshot = build_workspace_views_snapshot(conn, str(tmp_path))
    assert {"product", "logical", "infra", "world"} <= snapshot.keys()
    assert conn.execute("SELECT COUNT(*) FROM workspace_view_meta").fetchone()[0] == 4


def test_build_workspace_views_snapshot_with_readonly_db(tmp_path):
    db_file = tmp_path / "state.db"
    conn = sqlite3.connect(str(db_file))
    init_workspace_view_tables(conn)
    conn.close()

    # Open connection in read-only URI mode
    ro_conn = sqlite3.connect(f"file:{db_file}?mode=ro", uri=True)
    pkg_dir = tmp_path / "synlynk"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text("# init")
    (pkg_dir / "viz.py").write_text("import os\n")

    snapshot = build_workspace_views_snapshot(ro_conn, str(tmp_path))
    ro_conn.close()

    assert {"product", "logical", "infra", "world"} <= snapshot.keys()
    assert len(snapshot["logical"]["nodes"]) >= 2
    assert len(snapshot["infra"]["nodes"]) == 2
    assert len(snapshot["world"]["nodes"]) >= 1


def test_query_repo_file_tree_with_explicit_conn():
    from synlynk.scan import _query_repo_file_tree
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE source_symbols (id INTEGER PRIMARY KEY, file TEXT, language TEXT, "
        "symbol_type TEXT, symbol_name TEXT, line_number INTEGER, head_sha TEXT, scanned_at TEXT)"
    )
    conn.execute(
        "INSERT INTO source_symbols (file, language, symbol_type, symbol_name, line_number, head_sha, scanned_at) "
        "VALUES ('synlynk/viz.py', 'python', 'function', 'cmd_viz', 10, 'sha1', '2026-09-25T00:00:00')"
    )
    conn.commit()

    tree = _query_repo_file_tree(conn=conn)
    assert "synlynk" in tree["dirs"]
    assert any(f["name"] == "viz.py" for f in tree["dirs"]["synlynk"]["files"])
    conn.close()


