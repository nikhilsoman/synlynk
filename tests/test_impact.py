import json
import pytest
from synlynk.impact import calculate_impact


def test_calculate_impact_returns_callers_and_tests(tmp_path):
    out_dir = tmp_path / ".synlynk" / "graphify-out"
    out_dir.mkdir(parents=True)
    graph = {
        "nodes": [
            {"id": "synlynk.db:get_user", "label": "get_user", "file": "synlynk/db.py", "line": 50},
            {"id": "synlynk.auth:login", "label": "login", "file": "synlynk/auth.py", "line": 20},
            {"id": "tests.test_auth:test_login", "label": "test_login", "file": "tests/test_auth.py", "line": 10},
        ],
        "edges": [
            {"source": "synlynk.auth:login", "target": "synlynk.db:get_user", "kind": "calls"},
            {"source": "tests.test_auth:test_login", "target": "synlynk.auth:login", "kind": "calls"},
        ]
    }
    (out_dir / "graph.json").write_text(json.dumps(graph))

    report = calculate_impact(str(tmp_path), target="get_user")
    assert report["target"] == "get_user"
    assert "login" in [c["label"] for c in report["upstream_callers"]]
    assert "test_login" in [t["label"] for t in report["associated_tests"]]


def test_calculate_impact_fallback_when_no_graph(tmp_path):
    report = calculate_impact(str(tmp_path), target="get_user")
    assert report["target"] == "get_user"
    assert report["upstream_callers"] == []
    assert report["associated_tests"] == []
    assert report["downstream_callees"] == []


def test_calculate_impact_by_file(tmp_path):
    out_dir = tmp_path / ".synlynk" / "graphify-out"
    out_dir.mkdir(parents=True)
    graph = {
        "nodes": [
            {"id": "synlynk.db:get_user", "label": "get_user", "file": "synlynk/db.py", "line": 50},
            {"id": "synlynk.auth:login", "label": "login", "file": "synlynk/auth.py", "line": 20},
            {"id": "tests.test_auth:test_login", "label": "test_login", "file": "tests/test_auth.py", "line": 10},
        ],
        "edges": [
            {"source": "synlynk.auth:login", "target": "synlynk.db:get_user", "kind": "calls"},
            {"source": "tests.test_auth:test_login", "target": "synlynk.auth:login", "kind": "calls"},
        ]
    }
    (out_dir / "graph.json").write_text(json.dumps(graph))

    report = calculate_impact(str(tmp_path), target="synlynk/db.py")
    assert report["target"] == "synlynk/db.py"
    assert "login" in [c["label"] for c in report["upstream_callers"]]
    assert "test_login" in [t["label"] for t in report["associated_tests"]]


def test_cmd_impact_cli(tmp_path, capsys):
    import argparse
    from synlynk.impact import cmd_impact

    out_dir = tmp_path / ".synlynk" / "graphify-out"
    out_dir.mkdir(parents=True)
    graph = {
        "nodes": [
            {"id": "synlynk.db:get_user", "label": "get_user", "file": "synlynk/db.py", "line": 50},
            {"id": "synlynk.auth:login", "label": "login", "file": "synlynk/auth.py", "line": 20},
            {"id": "tests.test_auth:test_login", "label": "test_login", "file": "tests/test_auth.py", "line": 10},
        ],
        "edges": [
            {"source": "synlynk.auth:login", "target": "synlynk.db:get_user", "kind": "calls"},
            {"source": "tests.test_auth:test_login", "target": "synlynk.auth:login", "kind": "calls"},
        ]
    }
    (out_dir / "graph.json").write_text(json.dumps(graph))

    args = argparse.Namespace(target="get_user", repo_root=str(tmp_path), depth=10, json=False)
    ret = cmd_impact(args)
    assert ret == 0
    captured = capsys.readouterr()
    assert "Blast Radius & Impact Analysis" in captured.out
    assert "get_user" in captured.out
    assert "login" in captured.out
    assert "test_login" in captured.out

