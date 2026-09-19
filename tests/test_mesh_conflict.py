import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from synlynk.mesh import (
    extract_file_ast_symbols,
    parse_diff_line_ranges,
    map_diff_to_ast_symbols,
    detect_worktree_ast_conflicts,
    merge_fleet_graphs,
    infer_cross_repo_edges,
    cmd_multirepo_mesh,
)


def test_extract_file_ast_symbols():
    code = """
import os
from pathlib import Path

GLOBAL_VAR = 42

def helper_func(x):
    return x * 2

async def async_fetch():
    return True

class ServiceManager:
    \"\"\"Service manager class docstring.\"\"\"
    
    def start(self):
        print("start")

    async def poll_events(self):
        return []
"""
    symbols = extract_file_ast_symbols(code)
    names = [s.name for s in symbols]
    assert "os" in names
    assert "Path" in names or "pathlib.Path" in names
    assert "GLOBAL_VAR" in names
    assert "helper_func" in names
    assert "async_fetch" in names
    assert "ServiceManager" in names
    assert "ServiceManager.start" in names
    assert "ServiceManager.poll_events" in names


def test_parse_diff_line_ranges():
    diff_text = """diff --git a/synlynk/relay.py b/synlynk/relay.py
index 111..222 100644
--- a/synlynk/relay.py
+++ b/synlynk/relay.py
@@ -10,3 +10,6 @@ import sys
@@ -45,0 +48,12 @@ class RelayBroker:
diff --git a/synlynk/jobs.py b/synlynk/jobs.py
--- a/synlynk/jobs.py
+++ b/synlynk/jobs.py
@@ -100,5 +100,0 @@ def old_func():
"""
    ranges = parse_diff_line_ranges(diff_text)
    assert "synlynk/relay.py" in ranges
    assert (10, 15) in ranges["synlynk/relay.py"]
    assert (48, 59) in ranges["synlynk/relay.py"]
    assert "synlynk/jobs.py" in ranges
    assert (100, 100) in ranges["synlynk/jobs.py"]


def test_map_diff_to_ast_symbols():
    code = """def func_one():
    return 1

def func_two():
    return 2

class App:
    def method_a(self):
        return 'a'

    def method_b(self):
        return 'b'
"""
    # Diff on line 1-2 (func_one)
    syms_1 = map_diff_to_ast_symbols(code, [(1, 2)])
    assert any(s["name"] == "func_one" for s in syms_1)
    assert not any(s["name"] == "func_two" for s in syms_1)

    # Diff on line 8 (method_a)
    syms_2 = map_diff_to_ast_symbols(code, [(8, 9)])
    assert any(s["name"] == "App.method_a" for s in syms_2)
    assert not any(s["name"] == "App.method_b" for s in syms_2)


def test_detect_worktree_ast_conflicts_disjoint_and_conflict():
    wt_a_data = {
        "path": "/tmp/wt_a",
        "branch": "feat/branch-a",
        "files": {
            "synlynk/relay.py": [
                {"name": "RelayBroker.handle_message", "type": "method", "start_line": 50, "end_line": 80}
            ],
            "synlynk/jobs.py": [
                {"name": "acquire_lease", "type": "function", "start_line": 10, "end_line": 30}
            ]
        }
    }
    wt_b_data = {
        "path": "/tmp/wt_b",
        "branch": "feat/branch-b",
        "files": {
            "synlynk/relay.py": [
                {"name": "RelayBroker.send_frame", "type": "method", "start_line": 90, "end_line": 120}
            ],
            "synlynk/jobs.py": [
                {"name": "acquire_lease", "type": "function", "start_line": 10, "end_line": 35}
            ]
        }
    }

    with patch("synlynk.mesh.get_worktree_modified_symbols") as mock_get:
        mock_get.side_effect = lambda p, **kw: wt_a_data if "wt_a" in str(p) else wt_b_data
        report = detect_worktree_ast_conflicts(worktrees=["/tmp/wt_a", "/tmp/wt_b"])

    assert report["status"] == "CONFLICT"
    assert len(report["critical_conflicts"]) == 1
    conflict = report["critical_conflicts"][0]
    assert conflict["file"] == "synlynk/jobs.py"
    assert conflict["conflicting_symbols"] == ["acquire_lease"]
    assert "rebase" in conflict["recommendation"]

    # synlynk/relay.py should be marked ast_compatible
    assert len(report["ast_compatible"]) == 1
    compatible = report["ast_compatible"][0]
    assert compatible["file"] == "synlynk/relay.py"
    assert "RelayBroker.handle_message" in compatible["symbols_a"]
    assert "RelayBroker.send_frame" in compatible["symbols_b"]


def test_cmd_multirepo_mesh_conflicts_json(capsys):
    args = MagicMock()
    args.conflicts = True
    args.json = True
    args.worktrees = None
    args.repo_root = "."
    args.base = "main"
    args.fail_on_conflict = False

    ret = cmd_multirepo_mesh(args)
    assert ret == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert "status" in data
    assert "analyzed_worktrees" in data


def test_merge_fleet_graphs_and_inferred_edges():
    with tempfile.TemporaryDirectory() as tmp_dir:
        repo1 = Path(tmp_dir) / "repo1"
        repo2 = Path(tmp_dir) / "repo2"
        repo1.mkdir(); repo2.mkdir()

        g1_dir = repo1 / ".synlynk" / "graphify-out"
        g2_dir = repo2 / ".synlynk" / "graphify-out"
        g1_dir.mkdir(parents=True); g2_dir.mkdir(parents=True)

        (g1_dir / "graph.json").write_text(json.dumps({
            "nodes": [
                {"id": "api_route", "kind": "route", "label": "/v1/stories"}
            ],
            "edges": []
        }))
        (g2_dir / "graph.json").write_text(json.dumps({
            "nodes": [
                {"id": "client_call", "kind": "fetch", "label": "fetch('/v1/stories')"}
            ],
            "edges": []
        }))

        merged = merge_fleet_graphs([str(repo1), str(repo2)])
        assert len(merged["nodes"]) == 2

        inferred = infer_cross_repo_edges(merged)
        assert len(inferred) == 1
        assert inferred[0]["kind"] == "cross-repo-call"
