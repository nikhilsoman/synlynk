"""Maintainer graph sweep and non-blocking mesh contract drift."""

import json
from pathlib import Path

from synlynk.cli import build_parser
from synlynk.maintainer import cmd_maintainer_sweep
from synlynk.mesh import contract_drift


def test_contract_drift_reports_missing_route_when_client_remains():
    previous = [
        {"source": "web::fetch_users", "target": "api::GET /users", "kind": "cross-repo-call"},
        {"source": "web::other", "target": "api::kept", "kind": "calls"},
    ]
    current = [
        {"source": "web::fetch_users", "target": "api::GET /health", "kind": "calls"},
        {"source": "web::other", "target": "api::kept", "kind": "cross-repo-call"},
    ]
    rows = contract_drift(previous, current)
    assert rows == [{
        "source": "web::fetch_users",
        "target": "api::GET /users",
        "kind": "cross-repo-call",
    }]
    assert contract_drift(previous, previous) == []


def test_sweep_parser_accepts_refresh_graph():
    args = build_parser("maintainer").parse_args(["maintainer", "sweep", "--refresh-graph"])
    assert args.maintainer_action == "sweep"
    assert args.refresh_graph is True


def test_sweep_without_flag_is_a_dry_report(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / ".synlynk" / "workspace.json").write_text(json.dumps({
        "repos": [str(tmp_path), str(tmp_path / "other")],
    }))
    called = []
    monkeypatch.setattr(
        "synlynk.scan.ensure_graph_for_head",
        lambda root: called.append(root) or True,
    )
    code = cmd_maintainer_sweep(repo_root=str(tmp_path), refresh_graph=False)
    assert code == 0
    assert called == []
    out = capsys.readouterr().out
    assert "would ensure graph" in out
    assert "would rebuild mesh" in out


def test_sweep_refresh_exits_1_when_extract_fails(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("synlynk.scan.ensure_graph_for_head", lambda root: False)
    code = cmd_maintainer_sweep(repo_root=str(tmp_path), refresh_graph=True)
    assert code == 1


def test_sweep_refresh_records_drift_and_exits_0(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    syn = tmp_path / ".synlynk"
    syn.mkdir()
    other = tmp_path / "other"
    other.mkdir()
    (syn / "workspace.json").write_text(json.dumps({"repos": [str(tmp_path), str(other)]}))
    previous = {
        "edges": [{
            "source": "web::client",
            "target": "api::GET /users",
            "kind": "cross-repo-call",
        }],
    }
    (syn / "mesh.json").write_text(json.dumps(previous))
    monkeypatch.setattr("synlynk.scan.ensure_graph_for_head", lambda root: True)
    monkeypatch.setattr("synlynk.graph_cache.write_traversal_cache", lambda root: {"paths": []})

    def fake_mesh(repos, output_path):
        assert len(repos) >= 2
        result = {
            "nodes": [],
            "edges": [{"source": "web::client", "target": "api::GET /health", "kind": "calls"}],
            "repos": ["a", "b"],
        }
        Path(output_path).write_text(json.dumps(result))
        return result

    monkeypatch.setattr("synlynk.mesh.build_federated_mesh", fake_mesh)
    code = cmd_maintainer_sweep(repo_root=str(tmp_path), refresh_graph=True)
    assert code == 0
    sentinel = (syn / "sentinel.md").read_text()
    assert "MESH_CONTRACT_DRIFT" in sentinel
    assert "GET /users" in sentinel
