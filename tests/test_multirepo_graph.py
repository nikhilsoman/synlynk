import json
import pytest
from pathlib import Path
from synlynk.multirepo_graph import merge_fleet_graphs, infer_cross_repo_edges, write_global_graph


def test_merge_fleet_graphs_combines_multiple_repos(tmp_path):
    repo_a = tmp_path / "repo_a"
    repo_b = tmp_path / "repo_b"
    for r in (repo_a, repo_b):
        (r / ".synlynk" / "graphify-out").mkdir(parents=True)

    (repo_a / ".synlynk" / "graphify-out" / "graph.json").write_text(json.dumps({
        "nodes": [{"id": "repo_a:api_endpoint", "label": "/users", "kind": "route"}],
        "edges": []
    }))
    (repo_b / ".synlynk" / "graphify-out" / "graph.json").write_text(json.dumps({
        "nodes": [{"id": "repo_b:client_fetch", "label": "fetch('/users')", "kind": "fetch"}],
        "edges": []
    }))

    merged = merge_fleet_graphs([str(repo_a), str(repo_b)])
    assert len(merged["nodes"]) == 2

    edges = infer_cross_repo_edges(merged)
    assert len(edges) == 1
    assert edges[0]["source"] == "repo_b:client_fetch"
    assert edges[0]["target"] == "repo_a:api_endpoint"


def test_merge_fleet_graphs_skips_missing_directories(tmp_path):
    repo_missing = tmp_path / "nonexistent"
    merged = merge_fleet_graphs([str(repo_missing)])
    assert merged["nodes"] == []
    assert merged["edges"] == []


def test_write_global_graph(tmp_path):
    out_file = tmp_path / "global-graph.json"
    graph = {
        "nodes": [{"id": "node1", "label": "node1"}],
        "edges": [{"source": "node1", "target": "node2"}]
    }
    path = write_global_graph(graph, output_path=str(out_file))
    assert Path(path).is_file()
    saved = json.loads(Path(path).read_text())
    assert len(saved["nodes"]) == 1


def test_cmd_multirepo_mesh_cli(tmp_path, capsys):
    import argparse
    from synlynk.multirepo_graph import cmd_multirepo_mesh

    repo_a = tmp_path / "repo_a"
    (repo_a / ".synlynk" / "graphify-out").mkdir(parents=True)
    (repo_a / ".synlynk" / "graphify-out" / "graph.json").write_text(json.dumps({
        "nodes": [{"id": "repo_a:api", "label": "api"}],
        "edges": []
    }))

    out_file = tmp_path / "mesh.json"
    args = argparse.Namespace(repos=str(repo_a), output=str(out_file))
    ret = cmd_multirepo_mesh(args)
    assert ret == 0
    assert out_file.is_file()
    captured = capsys.readouterr()
    assert "Federated Knowledge Mesh Synthesized" in captured.out

