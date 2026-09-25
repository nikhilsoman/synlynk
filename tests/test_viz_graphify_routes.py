import io
import os
import shutil
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import synlynk.viz as viz_module
from synlynk.viz import _write_cache, VIZ_CACHE_DIR, VizorHandler
import synlynk.vizor_daemon as daemon_module


def test_write_cache_copies_graphify_html(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cache_dir = tmp_path / "viz-cache"
    monkeypatch.setattr(viz_module, "VIZ_CACHE_DIR", str(cache_dir))

    repo_graphify = tmp_path / ".synlynk" / "graphify-out" / "graph.html"
    repo_graphify.parent.mkdir(parents=True, exist_ok=True)
    repo_graphify.write_text("<html><body>Graphify Visualizer</body></html>")

    data = {"workspace": {"name": "testws"}}
    _write_cache(data, 8721)

    cached_graphify = cache_dir / "graphify.html"
    assert cached_graphify.is_file()
    assert "Graphify Visualizer" in cached_graphify.read_text()

    cached_graph = cache_dir / "graph.html"
    assert cached_graph.is_file()
    assert "Graphify Visualizer" in cached_graph.read_text()


def test_write_cache_without_graphify_html(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cache_dir = tmp_path / "viz-cache"
    monkeypatch.setattr(viz_module, "VIZ_CACHE_DIR", str(cache_dir))

    data = {"workspace": {"name": "testws"}}
    _write_cache(data, 8721)

    cached_graphify = cache_dir / "graphify.html"
    assert not cached_graphify.exists()


def test_vizor_handler_graphify_redirect(tmp_path, monkeypatch):
    monkeypatch.setattr(viz_module, "VIZ_CACHE_DIR", str(tmp_path))

    class DummyServer:
        server_port = 8721

    handler = VizorHandler.__new__(VizorHandler)
    handler.directory = str(tmp_path)
    handler.server = DummyServer()
    handler.send_response = MagicMock()
    handler.send_header = MagicMock()
    handler.end_headers = MagicMock()

    handler.path = "/graphify"
    handler.do_GET()
    handler.send_response.assert_called_with(302)
    handler.send_header.assert_called_with("Location", "/graphify.html")


def test_vizor_daemon_parse_workspace_path_graphify(monkeypatch):
    monkeypatch.setattr(daemon_module, "_known_slugs", lambda: {"myws"})

    slug, rewritten = daemon_module.parse_workspace_path("/w/myws/graphify")
    assert slug == "myws"
    assert rewritten == "/myws/graphify.html"

    slug2, rewritten2 = daemon_module.parse_workspace_path("/w/myws/graph")
    assert slug2 == "myws"
    assert rewritten2 == "/myws/graphify.html"

    slug3, rewritten3 = daemon_module.parse_workspace_path("/w/myws/graphify.html")
    assert slug3 == "myws"
    assert rewritten3 == "/myws/graphify.html"


def test_vizor_daemon_index_shows_graphify_chip(tmp_path, monkeypatch):
    ws_slug = "demo-ws"
    cache_dir = tmp_path / ws_slug
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / "index.html").write_text("<html>demo</html>")
    (cache_dir / "graphify.html").write_text("<html>graphify</html>")

    monkeypatch.setattr(daemon_module, "CACHE_ROOT", tmp_path)
    monkeypatch.setattr(
        daemon_module,
        "_registered_workspaces",
        lambda: {ws_slug: {"repo_path": "/fake/demo"}},
    )
    monkeypatch.setattr(daemon_module, "_known_slugs", lambda: {ws_slug})

    html = daemon_module._workspace_index_html()
    assert f"/w/{ws_slug}/graphify.html" in html
    assert "Graphify" in html
