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


def test_logical_view_embeds_graphify_and_communities_sidebar():
    data = {
        "workspace": {"name": "synlynk"},
        "workspace_views": {
            "logical": {
                "nodes": [
                    {"id": "c1", "label": "auth_handler", "kind": "function", "attrs_json": '{"community": 1}'},
                    {"id": "c2", "label": "db_pool", "kind": "class", "attrs_json": '{"community": 2}'}
                ],
                "edges": []
            }
        }
    }
    html = generate_logical_html(data, 8721)
    assert "graphify.html" in html or "vis-network" in html or "bs6-graph-view" in html
    assert "Community" in html or "Communities" in html or "am-communities" in html
    assert "theme-change" in html or "data-theme" in html
