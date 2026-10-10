import json
from synlynk.mesh import build_federated_mesh


def test_build_federated_mesh_two_repos(tmp_path):
    repo1 = tmp_path / "repo1"
    repo2 = tmp_path / "repo2"
    for r in (repo1, repo2):
        gdir = r / ".synlynk" / "graphify-out"
        gdir.mkdir(parents=True)

    (repo1 / ".synlynk" / "graphify-out" / "graph.json").write_text(json.dumps({
        "nodes": [{"id": "apiClient", "label": "ApiClient", "kind": "class", "community": 1}],
        "edges": []
    }))
    (repo2 / ".synlynk" / "graphify-out" / "graph.json").write_text(json.dumps({
        "nodes": [{"id": "postJobs", "label": "POST /api/jobs", "kind": "route", "community": 2}],
        "edges": []
    }))

    out_file = tmp_path / "federated.json"
    mesh = build_federated_mesh([str(repo1), str(repo2)], str(out_file))
    assert len(mesh["nodes"]) == 2
    assert mesh["nodes"][0]["repo"] == "repo1"
    assert mesh["nodes"][0]["id"] == "repo1::apiClient"
    assert mesh["nodes"][0]["original_id"] == "apiClient"
    assert mesh["nodes"][1]["repo"] == "repo2"
    assert mesh["nodes"][1]["id"] == "repo2::postJobs"
    assert mesh["nodes"][1]["original_id"] == "postJobs"
    assert mesh["repos"] == ["repo1", "repo2"]
    assert out_file.is_file()

    saved_data = json.loads(out_file.read_text())
    assert saved_data["nodes"] == mesh["nodes"]
    assert saved_data["edges"] == mesh["edges"]


def test_build_federated_mesh_cross_repo_bridges(tmp_path):
    repo_fe = tmp_path / "frontend"
    repo_be = tmp_path / "backend"
    for r in (repo_fe, repo_be):
        gdir = r / ".synlynk" / "graphify-out"
        gdir.mkdir(parents=True)

    (repo_fe / ".synlynk" / "graphify-out" / "graph.json").write_text(json.dumps({
        "nodes": [
            {"id": "fetchStories", "label": "fetch('/api/v1/stories')", "kind": "fetch", "community": 1}
        ],
        "edges": []
    }))
    (repo_be / ".synlynk" / "graphify-out" / "graph.json").write_text(json.dumps({
        "nodes": [
            {"id": "storiesRoute", "label": "GET /api/v1/stories", "kind": "route", "community": 2}
        ],
        "edges": []
    }))

    out_file = tmp_path / "federated.json"
    mesh = build_federated_mesh([str(repo_fe), str(repo_be)], str(out_file))
    assert len(mesh["nodes"]) == 2
    assert len(mesh["edges"]) == 1
    edge = mesh["edges"][0]
    assert edge["source"] == "frontend::fetchStories"
    assert edge["target"] == "backend::storiesRoute"
    assert edge["kind"] == "cross-repo-call"
    assert edge["inferred"] is True


def test_build_federated_mesh_missing_and_corrupt(tmp_path):
    repo_good = tmp_path / "good"
    repo_missing = tmp_path / "missing"
    repo_corrupt = tmp_path / "corrupt"

    (repo_good / ".synlynk" / "graphify-out").mkdir(parents=True)
    (repo_corrupt / ".synlynk" / "graphify-out").mkdir(parents=True)

    (repo_good / ".synlynk" / "graphify-out" / "graph.json").write_text(json.dumps({
        "nodes": [{"id": "n1", "label": "GoodNode"}],
        "edges": [{"source": "n1", "target": "n1"}]
    }))
    (repo_corrupt / ".synlynk" / "graphify-out" / "graph.json").write_text("NOT_VALID_JSON{{{")

    out_file = tmp_path / "sub" / "dir" / "federated.json"
    mesh = build_federated_mesh([str(repo_good), str(repo_missing), str(repo_corrupt)], str(out_file))
    assert len(mesh["nodes"]) == 1
    assert mesh["nodes"][0]["id"] == "good::n1"
    assert len(mesh["edges"]) == 1
    assert mesh["edges"][0]["source"] == "good::n1"
    assert mesh["edges"][0]["target"] == "good::n1"
    assert out_file.is_file()
