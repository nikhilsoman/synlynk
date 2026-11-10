"""Tests for Sub-3k Token Adaptive AST Context Packager."""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

from synlynk.pack import (
    synthesize_sub3k_context_pack,
    _compact_ast_signature,
    cmd_pack,
)


def test_compact_ast_signature():
    """Verify AST compaction extracts 1-line signature and condensed docstring."""
    sample_code = '''
def calculate_metrics(alpha: float, beta: int = 10) -> dict[str, float]:
    """Calculate the operational metrics for the fleet.
    
    This is an extended explanation that should be stripped
    to keep token usage minimal.
    """
    total = alpha * beta
    return {"result": total}
'''
    sig_info = _compact_ast_signature(sample_code, "calculate_metrics")
    assert sig_info is not None
    assert sig_info["signature"] == "def calculate_metrics(alpha: float, beta: int = 10) -> dict[str, float]:"
    assert sig_info["docstring"] == "Calculate the operational metrics for the fleet."
    assert "extended explanation" not in sig_info["docstring"]


def test_synthesize_sub3k_context_pack_budget_floor(tmp_path):
    """Verify synthesized sub-3k pack strictly satisfies <= 3000 token budget."""
    out_dir = tmp_path / ".synlynk" / "graphify-out"
    out_dir.mkdir(parents=True)
    graph_file = out_dir / "graph.json"

    # Create dummy source file
    src_file = tmp_path / "engine.py"
    src_file.write_text('''
def process_task(task_id: str, priority: int = 1) -> bool:
    """Execute prioritized task processing."""
    return True
''', encoding="utf-8")

    mock_nodes = [
        {"id": "engine.py::process_task", "label": "process_task", "file": "engine.py", "community_name": "Engine Core"},
    ]
    mock_edges = []
    graph_file.write_text(json.dumps({"nodes": mock_nodes, "edges": mock_edges}), encoding="utf-8")

    pack = synthesize_sub3k_context_pack(
        repo_root=str(tmp_path),
        task_text="process_task priority",
        story_id=None,
        max_tokens=3000,
    )
    assert pack != ""
    assert "## Task Context Pack" in pack
    assert "process_task" in pack
    # Token estimate (chars // 4) must be strictly <= 3000
    token_est = len(pack) // 4
    assert token_est <= 3000


def test_cmd_pack_inspect_mode(capsys, tmp_path):
    """Verify synlynk pack --inspect prints section token breakdown."""
    out_dir = tmp_path / ".synlynk" / "graphify-out"
    out_dir.mkdir(parents=True)
    graph_file = out_dir / "graph.json"
    graph_file.write_text(json.dumps({"nodes": [], "edges": []}), encoding="utf-8")

    args = MagicMock()
    args.target = "test_query"
    args.repo_root = str(tmp_path)
    args.budget = 3000
    args.inspect = True

    with patch("synlynk.pack.synthesize_sub3k_context_pack", return_value="## Task Context Pack\n- `def dummy()`"):
        code = cmd_pack(args)
        assert code == 0
        captured = capsys.readouterr().out
        assert "Sub-3k Task Context Pack Inspection" in captured
        assert "PASSED" in captured
