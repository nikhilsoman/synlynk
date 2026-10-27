"""Warm traversal cache built from a fixture graph. No graphify binary."""

import json
import time
from pathlib import Path

from synlynk.graph_cache import lookup_traversal, write_traversal_cache
from scripts.benchmark_graph_cache import cache_median_is_faster
from synlynk.pack import synthesize_context_pack


def _write_graph(root: Path, graph: dict, stamp: str = "abc123", lifecycle: str = "brownfield") -> None:
    out = root / ".synlynk" / "graphify-out"
    out.mkdir(parents=True)
    (out / "graph.json").write_text(json.dumps(graph))
    (out / "manifest.json").write_text(json.dumps({
        "built_at_commit": stamp,
        "lifecycle": lifecycle,
        "node_count": len(graph.get("nodes") or []),
    }))


def _fixture_graph() -> dict:
    nodes = [
        {"id": "cli", "label": "main", "file": "synlynk/cli.py", "kind": "function", "signature": "def main():"},
        {"id": "dispatch", "label": "dispatch_agent", "file": "synlynk/dispatch.py", "kind": "function", "signature": "def dispatch_agent():"},
        {"id": "scan", "label": "cmd_scan", "file": "synlynk/scan.py", "kind": "function", "signature": "def cmd_scan():"},
        {"id": "pack", "label": "synthesize_context", "file": "synlynk/pack.py", "kind": "function", "signature": "def synthesize_context():"},
        {"id": "route", "label": "GET /health", "file": "synlynk/http.py", "kind": "route", "signature": "GET /health"},
        {"id": "handler", "label": "health_handler", "file": "synlynk/http.py", "kind": "function", "signature": "def health_handler():"},
        {"id": "test1", "label": "test_scan_calls_cli", "file": "tests/test_scan.py", "kind": "function", "signature": "def test_scan_calls_cli():"},
        {"id": "god", "label": "god_node", "file": "synlynk/core.py", "kind": "function", "signature": "def god_node():"},
        {"id": "leaf", "label": "leaf_symbol", "file": "synlynk/leaf.py", "kind": "function", "signature": "def leaf_symbol():"},
    ]
    edges = [
        {"source": "cli", "target": "dispatch"},
        {"source": "dispatch", "target": "scan"},
        {"source": "scan", "target": "pack"},
        {"source": "route", "target": "handler"},
        {"source": "test1", "target": "cli"},
        {"source": "god", "target": "leaf"},
        {"source": "leaf", "target": "god"},
        {"source": "dispatch", "target": "god"},
        {"source": "scan", "target": "god"},
        {"source": "pack", "target": "god"},
        {"source": "handler", "target": "god"},
    ]
    return {"nodes": nodes, "edges": edges}


def test_write_traversal_cache_builds_four_kinds(tmp_path):
    _write_graph(tmp_path, _fixture_graph())
    write_traversal_cache(str(tmp_path))
    cache = json.loads((tmp_path / ".synlynk" / "graph-cache" / "traversals.json").read_text())
    assert cache["schema"] == 1
    assert cache["built_at_commit"] == "abc123"
    assert cache["lifecycle"] == "brownfield"
    kinds = {path["kind"] for path in cache["paths"]}
    assert {"entrypoint", "route", "test_closure", "god_neighborhood"} <= kinds
    assert len(cache["paths"]) <= 40
    for path in cache["paths"]:
        assert len(path["nodes"]) <= 8
        for node in path["nodes"]:
            assert {"id", "label", "file", "kind", "signature"} <= set(node)
    entry = next(path for path in cache["paths"] if path["kind"] == "entrypoint")
    entry_ids = [node["id"] for node in entry["nodes"]]
    assert entry_ids[0] == "cli"
    assert "dispatch" in entry_ids
    assert "scan" in entry_ids
    route = next(path for path in cache["paths"] if path["kind"] == "route")
    assert route["nodes"][0]["id"] == "route"
    test_path = next(path for path in cache["paths"] if path["kind"] == "test_closure")
    assert test_path["nodes"][0]["file"] == "tests/test_scan.py"
    assert "cli" in [node["id"] for node in test_path["nodes"]]


def test_empty_graph_writes_no_paths(tmp_path):
    _write_graph(tmp_path, {"nodes": [], "edges": []}, stamp="", lifecycle="greenfield")
    write_traversal_cache(str(tmp_path))
    cache = json.loads((tmp_path / ".synlynk" / "graph-cache" / "traversals.json").read_text())
    assert cache["paths"] == []
    assert cache["built_at_commit"] == ""
    assert cache["lifecycle"] == "greenfield"


def test_lookup_requires_schema_stamp_and_two_keywords(tmp_path):
    _write_graph(tmp_path, _fixture_graph())
    write_traversal_cache(str(tmp_path))
    hit = lookup_traversal(str(tmp_path), {"dispatch", "scan"})
    assert hit is not None
    assert {"dispatch", "scan"} <= set(hit["keywords"])
    assert lookup_traversal(str(tmp_path), {"dispatch"}) is None

    cache_path = tmp_path / ".synlynk" / "graph-cache" / "traversals.json"
    cache = json.loads(cache_path.read_text())
    cache["schema"] = 2
    cache_path.write_text(json.dumps(cache))
    assert lookup_traversal(str(tmp_path), {"dispatch", "scan"}) is None

    cache["schema"] = 1
    cache["built_at_commit"] = "other"
    cache_path.write_text(json.dumps(cache))
    assert lookup_traversal(str(tmp_path), {"dispatch", "scan"}) is None


def test_lookup_prefers_more_hits_then_shorter_chain(tmp_path):
    _write_graph(tmp_path, {"nodes": [], "edges": []})
    cache = {
        "schema": 1,
        "built_at_commit": "abc123",
        "lifecycle": "brownfield",
        "paths": [
            {
                "id": "long",
                "kind": "entrypoint",
                "keywords": ["dispatch", "scan", "extra"],
                "nodes": [{"id": str(i), "label": "n", "file": "a.py", "kind": "function", "signature": "def n():"} for i in range(6)],
            },
            {
                "id": "short",
                "kind": "route",
                "keywords": ["dispatch", "scan"],
                "nodes": [
                    {"id": "r", "label": "route", "file": "b.py", "kind": "route", "signature": "def route():"},
                    {"id": "h", "label": "handler", "file": "b.py", "kind": "function", "signature": "def handler():"},
                ],
            },
            {
                "id": "best",
                "kind": "god_neighborhood",
                "keywords": ["dispatch", "scan", "health", "handler"],
                "nodes": [
                    {"id": "g", "label": "god", "file": "c.py", "kind": "function", "signature": "def god():"},
                    {"id": "l", "label": "leaf", "file": "c.py", "kind": "function", "signature": "def leaf():"},
                    {"id": "m", "label": "mid", "file": "c.py", "kind": "function", "signature": "def mid():"},
                ],
            },
        ],
    }
    cache_dir = tmp_path / ".synlynk" / "graph-cache"
    cache_dir.mkdir(parents=True)
    (cache_dir / "traversals.json").write_text(json.dumps(cache))
    winner = lookup_traversal(str(tmp_path), {"dispatch", "scan", "health", "handler"})
    assert winner["id"] == "best"
    tied = lookup_traversal(str(tmp_path), {"dispatch", "scan"})
    assert tied["id"] == "short"


def test_lookup_on_forty_paths_is_under_five_milliseconds(tmp_path):
    paths = []
    for index in range(40):
        paths.append({
            "id": f"entrypoint:{index}",
            "kind": "entrypoint",
            "keywords": ["alpha", "beta"] if index == 39 else [f"kw{index}", "other"],
            "nodes": [
                {"id": f"n{index}", "label": "main", "file": "cli.py", "kind": "function", "signature": "def main():"}
            ],
        })
    _write_graph(tmp_path, {"nodes": [{"id": "n", "label": "main"}], "edges": []})
    cache = {"schema": 1, "built_at_commit": "abc123", "lifecycle": "brownfield", "paths": paths}
    cache_dir = tmp_path / ".synlynk" / "graph-cache"
    cache_dir.mkdir(parents=True)
    (cache_dir / "traversals.json").write_text(json.dumps(cache))
    started = time.perf_counter()
    hit = lookup_traversal(str(tmp_path), {"alpha", "beta"})
    elapsed = time.perf_counter() - started
    assert hit["id"] == "entrypoint:39"
    assert elapsed < 0.005


def test_god_neighborhood_file_is_a_legal_sparse_cone_input(tmp_path):
    from synlynk.worktree_sparse import derive_sparse_cone_paths_from_graph

    _write_graph(tmp_path, {
        "nodes": [{
            "id": "god",
            "label": "god_node",
            "file": "synlynk/core.py",
            "kind": "function",
            "signature": "def god_node():",
        }],
        "edges": [],
    })
    cache_dir = tmp_path / ".synlynk" / "graph-cache"
    cache_dir.mkdir(parents=True)
    (cache_dir / "traversals.json").write_text(json.dumps({
        "schema": 1,
        "built_at_commit": "abc123",
        "paths": [{
            "kind": "god_neighborhood",
            "nodes": [{"id": "god", "file": "synlynk/core.py", "label": "god_node"}],
        }],
    }))
    cone = derive_sparse_cone_paths_from_graph(str(tmp_path), task_text="god_node blast radius")
    assert "synlynk" in cone


def test_pack_uses_cache_before_live_walk(tmp_path):
    graph = {
        "nodes": [
            {"id": "live", "label": "unrelated_symbol", "file": "synlynk/other.py", "kind": "function", "signature": "def unrelated_symbol():"},
        ],
        "edges": [],
    }
    _write_graph(tmp_path, graph)
    cache = {
        "schema": 1,
        "built_at_commit": "abc123",
        "lifecycle": "brownfield",
        "paths": [{
            "id": "entrypoint:cli",
            "kind": "entrypoint",
            "keywords": ["dispatch", "scan"],
            "nodes": [{
                "id": "cli",
                "label": "main",
                "file": "synlynk/cli.py",
                "kind": "function",
                "signature": "def main():",
            }],
        }],
    }
    cache_dir = tmp_path / ".synlynk" / "graph-cache"
    cache_dir.mkdir(parents=True)
    (cache_dir / "traversals.json").write_text(json.dumps(cache))
    pack = synthesize_context_pack(str(tmp_path), task_text="dispatch the scan command")
    assert "def main():" in pack
    assert "unrelated_symbol" not in pack


def test_pack_bad_graph_json_records_context_sentinel(tmp_path):
    out = tmp_path / ".synlynk" / "graphify-out"
    out.mkdir(parents=True)
    (out / "graph.json").write_text("{not json")
    pack = synthesize_context_pack(str(tmp_path), task_text="dispatch scan")
    assert pack == ""
    sentinel = (tmp_path / ".synlynk" / "sentinel.md").read_text()
    assert "CONTEXT_BUILD_DEGRADED" in sentinel


def test_daemon_matching_built_at_commit_does_not_refresh(tmp_path, monkeypatch):
    from synlynk.daemon import WatchDaemon

    daemon = WatchDaemon.__new__(WatchDaemon)
    daemon.workspace_root = str(tmp_path)
    daemon._last_graph_refresh_attempt = 0.0
    out = tmp_path / ".synlynk" / "graphify-out"
    out.mkdir(parents=True)
    (out / "graph.json").write_text("{}")
    (out / "manifest.json").write_text(json.dumps({"built_at_commit": "abc123"}))
    monkeypatch.setattr("synlynk.daemon._current_repo_revision", lambda root: "abc123")
    started = []

    class FakeThread:
        def __init__(self, *args, **kwargs):
            started.append(kwargs.get("name"))

        def start(self):
            started.append("start")

    monkeypatch.setattr("synlynk.daemon.threading.Thread", FakeThread)
    daemon._check_graph_staleness_and_refresh()
    assert started == []


def test_cache_median_is_faster_only_when_median_drops():
    assert cache_median_is_faster([0.001, 0.002, 0.003], [0.01, 0.02, 0.03]) is True
    assert cache_median_is_faster([0.02, 0.03, 0.04], [0.001, 0.002, 0.003]) is False
    assert cache_median_is_faster([0.002, 0.002], [0.002, 0.002]) is False


def test_pack_misses_when_stamp_differs(tmp_path):
    _write_graph(tmp_path, {
        "nodes": [{"id": "live", "label": "unrelated_symbol", "file": "synlynk/other.py", "signature": "def unrelated_symbol():"}],
        "edges": [],
    }, stamp="head")
    cache = {
        "schema": 1,
        "built_at_commit": "old",
        "lifecycle": "brownfield",
        "paths": [{
            "id": "entrypoint:cli",
            "kind": "entrypoint",
            "keywords": ["dispatch", "scan"],
            "nodes": [{"id": "cli", "label": "main", "file": "cli.py", "kind": "function", "signature": "def main():"}],
        }],
    }
    cache_dir = tmp_path / ".synlynk" / "graph-cache"
    cache_dir.mkdir(parents=True)
    (cache_dir / "traversals.json").write_text(json.dumps(cache))
    pack = synthesize_context_pack(str(tmp_path), task_text="dispatch the scan command")
    assert "def main():" not in pack
