import json

import pytest

from synlynk.dispatch import (
    MODEL_TIER_FAST,
    MODEL_TIER_PRO,
    MODEL_TIER_REASONING,
    ast_blast_radius_score,
    calculate_dispatch_impact,
    resolve_dispatch_model,
    resolve_model_tier,
)


def test_ast_blast_radius_score_counts_all_graphify_relationships():
    report = {
        "target_nodes": [{"id": "target"}],
        "upstream_callers": [{"id": "caller"}],
        "downstream_callees": [{"id": "callee"}],
        "associated_tests": [{"id": "test"}],
    }
    assert ast_blast_radius_score(report) == 4


def test_resolve_model_tier_uses_leaf_multi_file_and_reasoning_paths():
    assert resolve_model_tier("rename a local variable") == MODEL_TIER_FAST
    assert resolve_model_tier("refactor this multi-file subsystem", impact_score=4) == MODEL_TIER_PRO
    assert resolve_model_tier("write an architecture spec") == MODEL_TIER_REASONING


def test_calculate_dispatch_impact_reads_graphify_reports(tmp_path):
    graph_dir = tmp_path / ".synlynk" / "graphify-out"
    graph_dir.mkdir(parents=True)
    (graph_dir / "graph.json").write_text(
        json.dumps(
            {
                "nodes": [
                    {"id": "pkg.api:save", "label": "save", "file": "pkg/api.py"},
                    {"id": "pkg.view:post", "label": "post", "file": "pkg/view.py"},
                ],
                "edges": [{"source": "pkg.view:post", "target": "pkg.api:save"}],
            }
        )
    )
    impact = calculate_dispatch_impact("update pkg/api.py", repo_root=str(tmp_path))
    assert impact["score"] == 2
    assert len(impact["reports"]) == 1


def test_tripartite_resolution_keeps_role_and_harness_separate(tmp_path):
    routed = resolve_dispatch_model(
        "codex",
        "update a leaf helper",
        role="qa",
        repo_root=str(tmp_path),
    )
    assert routed["harness"] == "codex"
    assert routed["role"] == "qa"
    assert routed["model_tier"] == MODEL_TIER_FAST
    assert routed["resolved_model"] == "gpt-4o-mini"
    assert routed["requested_model"] == routed["resolved_model"]


def test_explicit_model_and_tier_override_automatic_routing(tmp_path):
    routed = resolve_dispatch_model(
        "claude",
        "write an architecture spec",
        role="dev",
        model="my-private-model",
        model_tier=MODEL_TIER_FAST,
        repo_root=str(tmp_path),
    )
    assert routed["model_tier"] == MODEL_TIER_FAST
    assert routed["requested_model"] == "my-private-model"
    assert routed["resolved_model"] == "my-private-model"


def test_unknown_model_tier_fails_closed(tmp_path):
    with pytest.raises(ValueError, match="Unknown model tier"):
        resolve_dispatch_model("codex", "small task", model_tier="ultra", repo_root=str(tmp_path))
