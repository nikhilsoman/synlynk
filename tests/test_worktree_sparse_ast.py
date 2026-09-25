import json
import pytest
from pathlib import Path
from synlynk.worktree_sparse import (
    derive_sparse_cone_paths_from_graph,
    MANDATORY_SPARSE_CONE_DIRS,
)


def test_derive_sparse_cone_paths_from_graph_extracts_directories(tmp_path):
    out_dir = tmp_path / ".synlynk" / "graphify-out"
    out_dir.mkdir(parents=True)
    graph = {
        "nodes": [
            {
                "id": "synlynk.viz:generate_html",
                "label": "generate_html",
                "file": "synlynk/viz.py",
            },
            {
                "id": "website.build:render",
                "label": "render",
                "file": "website/build.py",
            },
            {
                "id": "tests.test_viz:test_render",
                "label": "test_render",
                "file": "tests/test_viz.py",
            },
        ],
        "edges": [
            {
                "source": "website.build:render",
                "target": "synlynk.viz:generate_html",
            }
        ],
    }
    (out_dir / "graph.json").write_text(json.dumps(graph))

    cone = derive_sparse_cone_paths_from_graph(
        str(tmp_path), task_text="Fix website rendering in viz generate_html"
    )

    # Mandatory dirs must always be included
    for d in MANDATORY_SPARSE_CONE_DIRS:
        assert d in cone

    # Discovered external top-level dir 'website' must be included
    assert "website" in cone


def test_derive_sparse_cone_paths_fallback_when_no_graph(tmp_path):
    cone = derive_sparse_cone_paths_from_graph(
        str(tmp_path), task_text="Some random task"
    )
    assert set(cone) == set(MANDATORY_SPARSE_CONE_DIRS)
