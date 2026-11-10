"""Tests for Zero-Drift Graph Currency Contract and Dual Stamping."""

import json
import os
from unittest.mock import MagicMock, patch
import pytest

from synlynk.dispatch import (
    _GRAPH_STALE_COMMIT_THRESHOLD,
    _commits_since_graph_build,
    _graph_needs_refresh,
    _read_graph_built_at_commit,
)
from synlynk.scan import _run_graphify_extract


def test_stale_commit_threshold_is_zero():
    """Zero-drift invariant: graph must never tolerate 25 commits of drift."""
    assert _GRAPH_STALE_COMMIT_THRESHOLD == 0


def test_graph_needs_refresh_zero_drift(tmp_path):
    """Even a single commit delta marks the graph as stale."""
    repo = tmp_path
    out_dir = repo / ".synlynk" / "graphify-out"
    out_dir.mkdir(parents=True)
    manifest = out_dir / "manifest.json"
    manifest.write_text(json.dumps({"built_at_commit": "commit_aaa"}))
    graph = out_dir / "graph.json"
    graph.write_text(json.dumps({"built_at_commit": "commit_aaa", "nodes": []}))

    # When commits_since_graph_build is 0 -> not stale
    with patch("synlynk.dispatch._commits_since_graph_build", return_value=0):
        assert _graph_needs_refresh(str(repo), str(graph)) is False

    # When commits_since_graph_build is 1 -> stale!
    with patch("synlynk.dispatch._commits_since_graph_build", return_value=1):
        assert _graph_needs_refresh(str(repo), str(graph)) is True

    # When commits_since_graph_build is 5 -> stale!
    with patch("synlynk.dispatch._commits_since_graph_build", return_value=5):
        assert _graph_needs_refresh(str(repo), str(graph)) is True


def test_run_graphify_extract_stamps_both_manifest_and_graph(tmp_path):
    """Dual atomic commit stamping: manifest.json AND graph.json receive HEAD commit."""
    repo = tmp_path
    out_dir = repo / ".synlynk" / "graphify-out"
    out_dir.mkdir(parents=True)
    manifest = out_dir / "manifest.json"
    manifest.write_text(json.dumps({"old_file.py": {}}))
    graph = out_dir / "graph.json"
    graph.write_text(json.dumps({"nodes": [], "edges": [], "built_at_commit": "old_hash"}))

    target_head = "head_commit_xyz_999"

    with patch("synlynk.scan.is_tool_available", return_value=True), \
         patch("subprocess.run", return_value=MagicMock(returncode=0)), \
         patch("synlynk.discovery._get_head_commit", return_value=target_head), \
         patch("synlynk.graph_cache.write_traversal_cache"):
        ok = _run_graphify_extract(str(repo))
        assert ok is True

        # Check manifest.json
        saved_manifest = json.loads(manifest.read_text(encoding="utf-8"))
        assert saved_manifest.get("built_at_commit") == target_head

        # Check graph.json
        saved_graph = json.loads(graph.read_text(encoding="utf-8"))
        assert saved_graph.get("built_at_commit") == target_head
