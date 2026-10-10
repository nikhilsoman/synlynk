import json
import pytest
from synlynk.viz import generate_architect_map_html, _generate_bs6_view_html


def test_architect_map_renders_refresh_button_and_handler():
    data = {
        "workspace": {"name": "test-ws"},
        "repos": [{"name": "test-repo", "path": "/path/to/repo"}],
        "discovery": {"knowledge_graph": {"nodes": [], "communities": []}},
    }
    html = generate_architect_map_html(data, port=8721)
    assert 'id="am-kg-refresh-btn"' in html
    assert "triggerAmKgRefresh" in html
    assert "Refresh Graph" in html


def test_logical_view_renders_refresh_button_and_handler():
    data = {
        "workspace": {"name": "test-ws"},
        "repos": [{"name": "test-repo", "path": "/path/to/repo"}],
        "workspace_views": {
            "logical": {
                "nodes": [
                    {"id": "n1", "label": "node1", "attrs_json": json.dumps({"community": 1})}
                ],
                "edges": [],
            }
        },
    }
    html = _generate_bs6_view_html(data, port=8721, view_key="logical", view_title="Logical View")
    assert 'id="bs6-kg-refresh-btn"' in html
    assert "triggerBs6KgRefresh" in html
    assert "Refresh Graph" in html
