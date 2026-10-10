import json
import os
import subprocess
from unittest.mock import patch, MagicMock
import pytest

from synlynk.discovery import scan_workspace_static
from synlynk.scan import _run_graphify_extract
from synlynk.viz import VizorHandler


def test_discovery_not_stale_when_built_at_commit_empty(tmp_path):
    out_dir = tmp_path / ".synlynk" / "graphify-out"
    out_dir.mkdir(parents=True)
    manifest_file = out_dir / "manifest.json"
    manifest_file.write_text(json.dumps({"some/file.py": {"ast_hash": "abc"}}))

    with patch("synlynk.discovery._is_graphify_installed", return_value=True), \
         patch("synlynk.discovery._get_head_commit", return_value="deadbeef1234"):
        disc = scan_workspace_static(str(tmp_path))
        kg = disc.get("knowledge_graph", {})
        assert kg.get("available") is True
        assert kg.get("stale") is False


def test_discovery_stale_only_when_commits_differ(tmp_path):
    out_dir = tmp_path / ".synlynk" / "graphify-out"
    out_dir.mkdir(parents=True)
    manifest_file = out_dir / "manifest.json"
    manifest_file.write_text(json.dumps({"built_at_commit": "oldcommit1234"}))

    with patch("synlynk.discovery._is_graphify_installed", return_value=True), \
         patch("synlynk.discovery._get_head_commit", return_value="newcommit5678"):
        disc = scan_workspace_static(str(tmp_path))
        kg = disc.get("knowledge_graph", {})
        assert kg.get("available") is True
        assert kg.get("stale") is True

    with patch("synlynk.discovery._is_graphify_installed", return_value=True), \
         patch("synlynk.discovery._get_head_commit", return_value="oldcommit1234"):
        disc = scan_workspace_static(str(tmp_path))
        kg = disc.get("knowledge_graph", {})
        assert kg.get("available") is True
        assert kg.get("stale") is False


def test_run_graphify_extract_stamps_built_at_commit(tmp_path):
    out_dir = tmp_path / ".synlynk" / "graphify-out"
    out_dir.mkdir(parents=True)
    manifest_file = out_dir / "manifest.json"
    manifest_file.write_text(json.dumps({"file.py": {"hash": "123"}}))

    with patch("synlynk.scan.is_tool_available", return_value=True), \
         patch("subprocess.run", return_value=MagicMock(returncode=0)), \
         patch("synlynk.discovery._get_head_commit", return_value="commithash9999"):
        ok = _run_graphify_extract(str(tmp_path))
        assert ok is True
        saved_manifest = json.loads(manifest_file.read_text())
        assert saved_manifest.get("built_at_commit") == "commithash9999"


def test_vizor_handler_handles_graph_refresh_standalone(tmp_path):
    handler = VizorHandler.__new__(VizorHandler)
    handler.path = "/api/graph/refresh"
    handler.command = "POST"
    handler.headers = {"Content-Length": "2"}
    handler.rfile = MagicMock()
    handler.rfile.read.return_value = b"{}"
    handler._authorize_write = MagicMock(return_value=True)
    handler._send_json_ok = MagicMock()
    handler.send_error = MagicMock()

    with patch("synlynk.scan._run_graphify_extract", return_value=True) as mock_extract, \
         patch("synlynk.viz.generate_viz_data", return_value={}), \
         patch("synlynk.viz._write_cache") as mock_write:
        handler.do_POST()
        mock_extract.assert_called_once()
        handler._send_json_ok.assert_called_once()
        args = handler._send_json_ok.call_args[0][0]
        assert args.get("status") == "ok"


def test_vizor_handler_handles_graph_refresh_workspace_scoped(tmp_path):
    handler = VizorHandler.__new__(VizorHandler)
    handler.path = "/w/test-workspace/api/graph/refresh"
    handler.command = "POST"
    handler.headers = {"Content-Length": "2"}
    handler.rfile = MagicMock()
    handler.rfile.read.return_value = b"{}"
    handler._authorize_write = MagicMock(return_value=True)
    handler._send_json_ok = MagicMock()
    handler.send_error = MagicMock()

    mock_workspaces = {
        "test-workspace": {
            "repo_path": str(tmp_path),
            "canonical_path": str(tmp_path / "state.db"),
        }
    }

    with patch("synlynk.vizor_daemon._registered_workspaces", return_value=mock_workspaces), \
         patch("synlynk.scan._run_graphify_extract", return_value=True) as mock_extract, \
         patch("synlynk.vizor_daemon.refresh_workspace") as mock_refresh:
        handler.do_POST()
        mock_extract.assert_called_once_with(str(tmp_path))
        mock_refresh.assert_called_once()
        handler._send_json_ok.assert_called_once()
        args = handler._send_json_ok.call_args[0][0]
        assert args.get("status") == "ok"
        assert args.get("workspace") == "test-workspace"
