"""Tests for the Jev sub-20ms AST Decision Engine (#1712)."""

import time

from synlynk.jev import JevDecision, evaluate_task_ast_features


def test_jev_fast_tier_classification(tmp_path):
    graph_data = {
        "nodes": [{"id": "docs/readme.md", "degree": 1}],
        "edges": [],
    }
    start = time.perf_counter()
    decision = evaluate_task_ast_features(
        files_touched=["docs/readme.md"],
        task_prompt="docs: update readme link",
        graph_data=graph_data,
    )
    elapsed_ms = (time.perf_counter() - start) * 1000

    assert elapsed_ms < 20.0  # Invariant: sub-20ms execution
    assert decision.recommended_tier == "fast"
    assert decision.blast_radius == 1


def test_jev_reasoning_tier_for_high_degree_nodes(tmp_path):
    graph_data = {
        "nodes": [{"id": "synlynk/__init__.py", "degree": 45}],
        "edges": [
            {"source": "synlynk/__init__.py", "target": f"m_{i}"} for i in range(45)
        ],
    }
    decision = evaluate_task_ast_features(
        files_touched=["synlynk/__init__.py"],
        task_prompt="refactor god module init.py",
        graph_data=graph_data,
    )
    assert decision.recommended_tier == "reasoning"
    assert decision.blast_radius >= 45


def test_jev_reasoning_tier_for_architectural_keywords():
    decision = evaluate_task_ast_features(
        files_touched=["synlynk/policy.py"],
        task_prompt="harden the security invariant on merge authority",
        graph_data=None,
    )
    assert decision.recommended_tier == "reasoning"
    assert decision.requires_architect_review is True


def test_jev_pro_tier_for_moderate_blast_radius():
    decision = evaluate_task_ast_features(
        files_touched=[f"synlynk/mod_{i}.py" for i in range(5)],
        task_prompt="wire up the new cli flag",
        graph_data=None,
    )
    assert decision.recommended_tier == "pro"
    assert decision.blast_radius == 5
    assert decision.requires_architect_review is False


def test_jev_decision_is_a_dataclass_with_rationale():
    decision = evaluate_task_ast_features(
        files_touched=["README.md"],
        task_prompt="fix typo",
    )
    assert isinstance(decision, JevDecision)
    assert decision.rationale
    assert decision.recommended_tier == "fast"


def test_jev_executes_under_20ms_on_large_graph():
    """The heuristic matrix must stay sub-20ms with a realistic graph size."""
    graph_data = {
        "nodes": [{"id": f"synlynk/mod_{i}.py", "degree": i % 40} for i in range(5000)],
        "edges": [],
    }
    files = [f"synlynk/mod_{i}.py" for i in range(50)]

    start = time.perf_counter()
    decision = evaluate_task_ast_features(
        files_touched=files,
        task_prompt="bulk rename helper",
        graph_data=graph_data,
    )
    elapsed_ms = (time.perf_counter() - start) * 1000

    assert elapsed_ms < 20.0
    assert decision.blast_radius >= 50


def test_jev_handles_missing_and_malformed_graph_data():
    for graph in (None, {}, {"nodes": []}):
        decision = evaluate_task_ast_features(
            files_touched=["a.py"],
            task_prompt="tweak",
            graph_data=graph,
        )
        assert decision.recommended_tier == "fast"
        assert decision.blast_radius == 1
