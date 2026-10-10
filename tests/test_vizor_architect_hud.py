import os
import tempfile
import pytest
from synlynk.viz import generate_architect_map_html, _write_cache, VIZ_CACHE_DIR


def test_generate_architect_map_html_renders_hud_when_unindexed():
    """When graphify code graph is absent, tube.html must render an interactive glassmorphic HUD shell, never a 404."""
    data = {
        "workspace": {"name": "rxcc", "updated_at": "2026-09-30T10:00:00Z", "repos": []},
        "workspace_map": {"edges": [], "edge_types": {}},
        "has_graphify": False,
    }
    
    html_output = generate_architect_map_html(data, port=8721)
    
    # Must contain the native HUD indicators and action
    assert "am-empty-hud" in html_output or "AWAITING AST INDEXING" in html_output
    assert "synlynk scan --deep" in html_output


def test_generate_architect_map_html_has_no_active_404_iframe_src():
    """When graphify is absent, tube.html must not attempt to fetch graphify.html via active iframe src."""
    data = {
        "workspace": {"name": "rxcc", "updated_at": "2026-09-30T10:00:00Z", "repos": []},
        "workspace_map": {"edges": [], "edge_types": {}},
        "has_graphify": False,
    }
    
    html_output = generate_architect_map_html(data, port=8721)
    assert '<iframe id="am-graphify-frame" src="graphify.html"' not in html_output
    assert 'data-src="graphify.html"' in html_output
