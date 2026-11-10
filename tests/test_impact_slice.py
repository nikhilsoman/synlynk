"""Tests for 1-hop AST graph slicing and blast radius extraction."""

import json
from pathlib import Path
import pytest

from synlynk.impact import slice_1hop_impact


def test_slice_1hop_impact_bounded(tmp_path):
    out_dir = tmp_path / ".synlynk" / "graphify-out"
    out_dir.mkdir(parents=True)
    graph_file = out_dir / "graph.json"

    # Construct mock graph:
    # caller_1 -> target_fn -> callee_1
    # caller_2 -> target_fn -> callee_2
    # test_fn -> target_fn
    mock_data = {
        "nodes": [
            {"id": "mod.py::target_fn", "label": "target_fn", "file": "mod.py"},
            {"id": "caller_a.py::call_a", "label": "call_a", "file": "caller_a.py"},
            {"id": "caller_b.py::call_b", "label": "call_b", "file": "caller_b.py"},
            {"id": "callee_x.py::util_x", "label": "util_x", "file": "callee_x.py"},
            {"id": "tests/test_mod.py::test_target", "label": "test_target", "file": "tests/test_mod.py"},
            # 2-hop node that should NOT be in 1-hop slice
            {"id": "distant.py::far_away", "label": "far_away", "file": "distant.py"},
        ],
        "edges": [
            {"source": "caller_a.py::call_a", "target": "mod.py::target_fn"},
            {"source": "caller_b.py::call_b", "target": "mod.py::target_fn"},
            {"source": "mod.py::target_fn", "target": "callee_x.py::util_x"},
            {"source": "tests/test_mod.py::test_target", "target": "mod.py::target_fn"},
            # 2-hop edge: far_away -> call_a -> target_fn
            {"source": "distant.py::far_away", "target": "caller_a.py::call_a"},
        ],
    }
    graph_file.write_text(json.dumps(mock_data), encoding="utf-8")

    res = slice_1hop_impact(str(tmp_path), "target_fn", max_callers=2, max_callees=2, max_tests=2)
    assert res["target"] == "target_fn"
    assert len(res["target_nodes"]) == 1
    assert res["target_nodes"][0]["id"] == "mod.py::target_fn"

    # Inbound callers (1-hop only)
    caller_ids = [n["id"] for n in res["inbound_callers"]]
    assert "caller_a.py::call_a" in caller_ids
    assert "caller_b.py::call_b" in caller_ids
    assert "distant.py::far_away" not in caller_ids  # 2-hop excluded!

    # Outbound callees (1-hop only)
    callee_ids = [n["id"] for n in res["outbound_callees"]]
    assert callee_ids == ["callee_x.py::util_x"]

    # Associated tests
    test_ids = [n["id"] for n in res["associated_tests"]]
    assert test_ids == ["tests/test_mod.py::test_target"]


def test_slice_1hop_impact_empty_on_missing_graph(tmp_path):
    res = slice_1hop_impact(str(tmp_path), "non_existent_symbol")
    assert res["target_nodes"] == []
    assert res["inbound_callers"] == []
    assert res["outbound_callees"] == []
    assert res["associated_tests"] == []
