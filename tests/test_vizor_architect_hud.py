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


def test_generate_all_views_never_omits_graphify_html(tmp_path, monkeypatch):
    """Even if an external repo has never been scanned, graphify.html must exist and contain a valid HUD shell."""
    repo = tmp_path / "rxcc_unindexed"
    repo.mkdir()
    
    # Change cache dir to isolated temp dir
    cache_dir = tmp_path / "viz_cache"
    cache_dir.mkdir()
    monkeypatch.setattr("synlynk.viz.VIZ_CACHE_DIR", str(cache_dir))
    
    data = {"workspace": {"name": "rxcc", "repos": [{"path": str(repo), "name": "rxcc"}]}}
    _write_cache(data=data, port=8721)
    
    graphify_file = cache_dir / "graphify.html"
    assert graphify_file.is_file(), "graphify.html was missing from cache dir, which would cause an iframe 404!"
    
    content = graphify_file.read_text(encoding="utf-8")
    assert "404" not in content
    assert "AST" in content
