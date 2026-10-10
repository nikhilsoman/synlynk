import json
import pytest
from pathlib import Path
from synlynk.pack import synthesize_context_pack, _cut_to_token_budget


def test_synthesize_context_pack_rich_features(tmp_path):
    out_dir = tmp_path / ".synlynk" / "graphify-out"
    out_dir.mkdir(parents=True)
    graph = {
        "nodes": [
            {
                "id": "synlynk.worktree_sparse:create_sparse_cone_worktree",
                "label": "create_sparse_cone_worktree",
                "file": "synlynk/worktree_sparse.py",
                "line": 33,
                "signature": "def create_sparse_cone_worktree(repo_root: str, worktree_path: str, branch: str, base_ref: str, scoped_paths: Optional[Sequence[str]] = None) -> bool",
                "docstring": "Creates an isolated git worktree configured with cone-mode sparse checkout.",
                "community_name": "synlynk/worktree_sparse.py · SparseWorktree",
                "community": 1,
            },
            {
                "id": "synlynk.dispatch:dispatch_job",
                "label": "dispatch_job",
                "file": "synlynk/dispatch.py",
                "line": 1420,
                "community_name": "synlynk/dispatch.py · DispatchEngine",
                "community": 2,
            },
            {
                "id": "tests.test_worktree_sparse:test_create_sparse_cone_worktree",
                "label": "test_create_sparse_cone_worktree",
                "file": "tests/test_worktree_sparse.py",
                "line": 22,
                "community_name": "tests/test_worktree_sparse.py · TestSuite",
                "community": 3,
            },
        ],
        "edges": [
            {
                "source": "synlynk.dispatch:dispatch_job",
                "target": "synlynk.worktree_sparse:create_sparse_cone_worktree",
                "kind": "calls",
            },
            {
                "source": "tests.test_worktree_sparse:test_create_sparse_cone_worktree",
                "target": "synlynk.worktree_sparse:create_sparse_cone_worktree",
                "kind": "calls",
            },
        ],
    }
    (out_dir / "graph.json").write_text(json.dumps(graph))

    pack = synthesize_context_pack(
        str(tmp_path),
        task_text="Implement sparse cone directory scoping in create_sparse_cone_worktree",
    )

    # 1. Header & Section structure
    assert "## Task Context Pack" in pack
    assert "### Primary Subsystems & Communities" in pack
    assert "synlynk/worktree_sparse.py" in pack

    # 2. Target symbols and inlined docstring / signature
    assert "### Target Symbols & Interfaces" in pack
    assert "create_sparse_cone_worktree" in pack
    assert "Creates an isolated git worktree configured with cone-mode sparse checkout" in pack

    # 3. Callers
    assert "Inbound Callers:" in pack
    assert "dispatch_job" in pack or "dispatch.py" in pack

    # 4. Reverse test suite discovery
    assert "### Suggested Verification Test Targets" in pack
    assert "pytest tests/test_worktree_sparse.py" in pack


def test_synthesize_context_pack_falls_back_when_no_docstring(tmp_path):
    out_dir = tmp_path / ".synlynk" / "graphify-out"
    out_dir.mkdir(parents=True)
    graph = {
        "nodes": [
            {
                "id": "synlynk.util:helper",
                "label": "helper",
                "file": "synlynk/util.py",
                "line": 10,
            }
        ],
        "edges": [],
    }
    (out_dir / "graph.json").write_text(json.dumps(graph))

    pack = synthesize_context_pack(str(tmp_path), task_text="Use helper in util")
    assert "helper" in pack
    assert "synlynk/util.py:L10" in pack
