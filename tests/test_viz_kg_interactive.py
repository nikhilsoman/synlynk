import json
import pytest
from synlynk.viz import generate_architect_map_html, generate_logical_html, _enrich_graphify_html

def test_architect_map_contains_kg_source_drawer_and_interactive_features():
    data = {
        "nodes": [
            {"id": "synlynk.viz:generate_html", "label": "generate_html", "file": "synlynk/viz.py", "line": 10},
        ],
        "edges": [],
        "repos": [{"name": "synlynk", "path": ".", "primary": True}],
        "is_stale": False,
        "head_commit": "abc1234",
    }
    html = generate_architect_map_html(data, port=27472)
    assert "kg-source-drawer" in html
    assert "am-kg-kind-filters" in html
    assert "filter-kind-l0" in html
    assert "open-source-drawer" in html or "openKgSourceDrawer" in html
    assert "Escape" in html
    assert "resetInspectMode" in html

def test_logical_html_contains_kg_source_drawer_and_filters():
    data = {
        "nodes": [
            {"id": "node-1", "label": "CoreService", "kind": "service"},
        ],
        "edges": [],
        "workspace_views": {
            "logical": {
                "nodes": [{"id": "node-1", "label": "CoreService", "kind": "service"}],
                "edges": [],
            }
        },
        "repos": [{"name": "synlynk", "path": ".", "primary": True}],
    }
    html = generate_logical_html(data, port=27472)
    assert "kg-source-drawer" in html
    assert "bs6-kg-kind-filters" in html
    assert "openKgSourceDrawer" in html
    assert "toggleAmKindFilter" in html

def test_enrich_graphify_html_injects_interactive_ux():
    mock_html = """<!DOCTYPE html>
<html>
<head>
</head>
<body>
<div id="graph"></div>
<script>
const RAW_NODES = [{"id": "a", "label": "A", "degree": 4, "source_file": "src/a.py", "community": 0}];
const LEGEND = [{"cid": 0, "name": "Comm 0"}];
let hiddenCommunities = new Set();
let nodesDS = { update: function() {}, get: function(id) { return RAW_NODES[0]; } };
let network = { getConnectedNodes: function(id) { return []; }, fit: function() {}, moveTo: function() {}, on: function() {}, once: function() {} };
</script>
</body>
</html>"""
    graph_data = {
        "nodes": [{"id": "a", "label": "A", "file": "src/a.py", "community": 0}]
    }
    enriched = _enrich_graphify_html(mock_html, graph_data)
    assert "filter-kind-l0" in enriched
    assert "grow-ego-network" in enriched
    assert "open-source-drawer" in enriched
    assert "inspectedEgoSet" in enriched
    assert "inspectSourceCode" in enriched
    assert "vis-map-zoom-bar" in enriched
