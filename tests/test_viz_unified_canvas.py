from synlynk.viz import generate_architect_map_html, generate_logical_html


def test_architect_map_single_repo_renders_graphify_or_ast():
    data = {
        "workspace": {
            "name": "synlynk",
            "repos": [{"name": "synlynk", "path": "/path/synlynk"}]
        }
    }
    html = generate_architect_map_html(data, 8721)
    assert "synlynk" in html
    assert "graphify.html" in html or "bs6-graph-view" in html or "vis-network" in html


def test_logical_view_embeds_graphify_or_vis():
    data = {
        "workspace": {"name": "synlynk"},
        "workspace_views": {
            "logical": {"nodes": [{"id": "1", "label": "test", "kind": "function"}], "edges": []}
        }
    }
    html = generate_logical_html(data, 8721)
    assert "Logical View" in html
    assert "graphify.html" in html or "bs6-svg" in html or "vis-network" in html


def test_architect_map_multi_repo_renders_clustered_canvas_and_bridges():
    data = {
        "workspace": {
            "name": "multi-ws",
            "repos": [
                {"name": "repo-frontend", "path": "/path/frontend"},
                {"name": "repo-backend", "path": "/path/backend"}
            ]
        },
        "workspace_map": {
            "edges": [{"from": "repo-frontend", "to": "repo-backend", "type": "api-bridge"}],
            "edge_types": {"api-bridge": {"label": "API Bridge", "color": "#0d9e87"}}
        }
    }
    html = generate_architect_map_html(data, 8721)
    assert "repo-frontend" in html
    assert "repo-backend" in html
    assert "am-cluster" in html or "am-repo-box" in html or "am-compound" in html or "cluster" in html
    assert "api-bridge" in html or "bridge" in html
    assert "zoom" in html or "scale" in html


def test_architect_map_theme_synchronization():
    data = {
        "workspace": {
            "name": "synlynk",
            "repos": [{"name": "synlynk", "path": "/path/synlynk"}]
        }
    }
    html = generate_architect_map_html(data, 8721)
    assert "theme-change" in html or "data-theme" in html


def test_logical_view_embeds_graphify_and_communities_dropdown():
    data = {
        "workspace": {"name": "synlynk"},
        "workspace_views": {
            "logical": {
                "nodes": [
                    {"id": "c1", "label": "auth_handler", "kind": "function", "source_file": "synlynk/auth.py", "attrs_json": '{"community": 1}'},
                    {"id": "c2", "label": "db_pool", "kind": "class", "source_file": "synlynk/db.py", "attrs_json": '{"community": 2}'}
                ],
                "edges": []
            }
        }
    }
    html = generate_logical_html(data, 8721)
    assert "graphify.html" in html or "vis-network" in html or "bs6-graph-view" in html
    assert "Communities" in html or "am-dropdown" in html
    assert "synlynk/auth.py" in html or "synlynk/db.py" in html
    assert "am-kg-topbar" in html
    assert "am-kg-canvas-full" in html
    assert "theme-change" in html or "data-theme" in html


def test_architect_map_monorepo_tabs_and_topbar_dropdown():
    data = {
        "workspace": {
            "name": "synlynk",
            "repos": [{"name": "synlynk", "path": "/path/synlynk"}]
        },
        "workspace_views": {
            "logical": {
                "nodes": [
                    {"id": "c1", "label": "auth_handler", "kind": "function", "source_file": "synlynk/auth.py", "attrs_json": '{"community": 1}'},
                    {"id": "c2", "label": "AuthService", "kind": "class", "source_file": "synlynk/auth.py", "_callable_class": True, "attrs_json": '{"community": 1}'},
                    {"id": "c3", "label": "DatabasePool", "kind": "class", "source_file": "synlynk/db.py", "attrs_json": '{"community": 2}'}
                ],
                "edges": []
            }
        }
    }
    html = generate_architect_map_html(data, 8721)
    # Monorepo switcher should have Knowledge Graph and File Tree, but NOT Topology button
    assert "Knowledge Graph" in html
    assert "File Tree" in html
    assert '<button class="am-tab" data-view="graph" onclick="setArchitectView(\'graph\')">Topology</button>' not in html
    # Topbar dropdown and canonical labels
    assert "am-kg-topbar" in html
    assert "am-dropdown" in html
    assert "am-kg-canvas-full" in html
    assert "synlynk/auth.py · AuthService" in html
    assert "synlynk/db.py · DatabasePool" in html


def test_enrich_graphify_html_canonical_labels_and_batch_listeners():
    from synlynk.viz import _enrich_graphify_html

    sample_html = """<!DOCTYPE html><html><head></head><body><script>
const RAW_NODES = [{"id": "1", "label": "Community 1", "title": "Community 1", "community": 1}];
</script></body></html>"""

    graph_data = {
        "nodes": [
            {"id": "n1", "label": "AuthService", "kind": "class", "source_file": "synlynk/auth.py", "community": 1}
        ]
    }

    enriched = _enrich_graphify_html(sample_html, graph_data)
    assert "synlynk/auth.py" in enriched
    assert "Community 1" not in enriched or "synlynk/auth.py" in enriched
    assert "filter-communities-batch" in enriched
    assert "filter-community" in enriched


def test_enrich_graphify_html_lod_zoom_and_rich_sidebar():
    from synlynk.viz import _enrich_graphify_html

    sample_html = """<!DOCTYPE html><html><head></head><body>
<div id="graph"></div>
<div id="sidebar">
  <div id="info-panel"><div id="info-content"></div></div>
</div>
<script>
const RAW_NODES = [
  {"id": "1", "label": "Community 1", "title": "Community 1", "community": 1, "degree": 5},
  {"id": "2", "label": "Community 2", "title": "Community 2", "community": 2, "degree": 1}
];
const LEGEND = [{"cid": 1, "label": "C1", "count": 1, "color": "#fff"}, {"cid": 2, "label": "C2", "count": 1, "color": "#fff"}];
function showInfo(nodeId) {}
</script></body></html>"""

    graph_data = {
        "nodes": [
            {"id": "n1", "label": "AuthService", "kind": "class", "source_file": "synlynk/auth.py", "community": 1, "docstring": "Core authentication handler."},
            {"id": "n2", "label": "helper_fn", "kind": "function", "source_file": "synlynk/util.py", "community": 2}
        ]
    }

    enriched = _enrich_graphify_html(sample_html, graph_data)
    # Check LOD controls and thresholds
    assert "vis-map-zoom-bar" in enriched
    assert 'id="graph-wrap"' in enriched
    # vis-network owns #graph; the zoom bar must be a sibling, not a child.
    graph_open = enriched.find('<div id="graph"')
    graph_close = enriched.find("</div>", graph_open)
    graph_inner = enriched[graph_open:graph_close]
    assert "vis-zoom-bar" not in graph_inner
    assert enriched.find("vis-zoom-bar") < graph_open
    assert "LOD_THRESHOLDS" in enriched or "currentLODLevel" in enriched or "setLODLevel" in enriched
    assert "Level 0" in enriched or "L0" in enriched
    # Check default degree threshold >= 3 for Level 0
    assert "3" in enriched
    # Check rich sidebar and tooltips
    assert "synlynk/auth.py" in enriched
    assert "Contained Symbols" in enriched or "symbols" in enriched
    assert "Connectivity" in enriched or "degree" in enriched
    assert "lod-status-update" in enriched or "set-lod" in enriched


