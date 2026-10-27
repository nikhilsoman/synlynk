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
    assert routed["resolved_model"] == "gpt-5.6-luna"
    assert routed["requested_model"] == routed["resolved_model"]


def test_god_neighborhood_target_floors_fast_tier_at_pro(tmp_path):
    cache_dir = tmp_path / ".synlynk" / "graph-cache"
    cache_dir.mkdir(parents=True)
    (cache_dir / "traversals.json").write_text(json.dumps({
        "schema": 1,
        "paths": [{"kind": "god_neighborhood", "nodes": [{"id": "core.god"}]}],
    }))
    assert resolve_model_tier(
        "rename a local variable",
        target_ids=["core.god"],
        repo_root=str(tmp_path),
    ) == MODEL_TIER_PRO
    assert resolve_model_tier(
        "write an architecture spec",
        target_ids=["core.god"],
        repo_root=str(tmp_path),
    ) == MODEL_TIER_REASONING


def test_explicit_model_bypasses_god_node_floor(tmp_path, monkeypatch):
    cache_dir = tmp_path / ".synlynk" / "graph-cache"
    cache_dir.mkdir(parents=True)
    (cache_dir / "traversals.json").write_text(json.dumps({
        "schema": 1,
        "paths": [{"kind": "god_neighborhood", "nodes": [{"id": "core.god"}]}],
    }))
    monkeypatch.setattr(
        "synlynk.dispatch.calculate_dispatch_impact",
        lambda *args, **kwargs: {
            "score": 0,
            "reports": [{"target_nodes": [{"id": "core.god"}]}],
        },
    )
    routed = resolve_dispatch_model(
        "codex",
        "rename a local variable",
        model="gpt-explicit",
        repo_root=str(tmp_path),
    )
    assert routed["model_tier"] == MODEL_TIER_FAST
    assert routed["resolved_model"] == "gpt-explicit"


def test_dispatch_floors_tier_when_impact_target_is_a_god_node(tmp_path, monkeypatch):
    cache_dir = tmp_path / ".synlynk" / "graph-cache"
    cache_dir.mkdir(parents=True)
    (cache_dir / "traversals.json").write_text(json.dumps({
        "schema": 1,
        "paths": [{"kind": "god_neighborhood", "nodes": [{"id": "core.god"}]}],
    }))
    monkeypatch.setattr(
        "synlynk.dispatch.calculate_dispatch_impact",
        lambda *args, **kwargs: {
            "score": 0,
            "reports": [{"target_nodes": [{"id": "core.god"}]}],
        },
    )
    routed = resolve_dispatch_model(
        "codex",
        "rename a local variable",
        repo_root=str(tmp_path),
    )
    assert routed["model_tier"] == MODEL_TIER_PRO


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


def test_local_resolution_uses_policy_model_not_legacy_catalog_tier(tmp_path):
    policy_dir = tmp_path / ".agents"
    policy_dir.mkdir()
    (policy_dir / "local.json").write_text(
        json.dumps(
            {
                "endpoint": "http://127.0.0.1:8000",
                "pinned_model": "Ornith-1.0-9B-4bit",
                "models": [
                    {
                        "id": "Ornith-1.0-9B-4bit",
                        "pinned": True,
                        "edit_format": "diff",
                    }
                ],
            }
        )
    )
    routed = resolve_dispatch_model("local", "summarize a test failure", repo_root=str(tmp_path))
    assert routed["resolved_model"] == "Ornith-1.0-9B-4bit"
    assert routed["local_resolution"]["effective_model"] == routed["resolved_model"]
    assert routed["local_resolution"]["edit_format"] == "diff"


def test_local_model_resolution_accepts_only_exact_policy_and_live_id(tmp_path):
    policy_dir = tmp_path / ".agents"
    policy_dir.mkdir()
    (policy_dir / "local.json").write_text(json.dumps({
        "endpoint": "http://127.0.0.1:8000",
        "pinned_model": "ornith",
        "models": [
            {"id": "ornith", "pinned": True, "edit_format": "diff"},
            {"id": "qwen", "dispatch_eligible": False, "edit_format": "whole"},
        ],
    }))

    routed = resolve_dispatch_model(
        "local",
        "summarize a test failure",
        model="ornith",
        repo_root=str(tmp_path),
        live_model_ids=["ornith", "qwen", "other"],
    )

    assert routed["requested_model"] == "ornith"
    assert routed["resolved_model"] == "ornith"
    assert routed["local_resolution"]["drift"]["live_but_unapproved"] == ["other", "qwen"]
    with pytest.raises(ValueError, match="not dispatch-approved"):
        resolve_dispatch_model(
            "local", "summarize", model="qwen", repo_root=str(tmp_path),
            live_model_ids=["ornith", "qwen"],
        )
    with pytest.raises(ValueError, match="not currently served"):
        resolve_dispatch_model(
            "local", "summarize", repo_root=str(tmp_path), live_model_ids=["other"]
        )


def test_unknown_model_tier_fails_closed(tmp_path):
    with pytest.raises(ValueError, match="Unknown model tier"):
        resolve_dispatch_model("codex", "small task", model_tier="ultra", repo_root=str(tmp_path))


def test_codex_dispatch_probes_config_toml_when_unspecified(tmp_path, monkeypatch):
    codex_home = tmp_path / "codex_home"
    codex_home.mkdir()
    (codex_home / "config.toml").write_text('model = "gpt-5.6-luna"\nmodel_reasoning_effort = "medium"\n')
    monkeypatch.setenv("CODEX_HOME", str(codex_home))

    routed = resolve_dispatch_model(
        "codex",
        "implement feature",
        role="dev",
        repo_root=str(tmp_path),
    )
    assert routed["resolved_model"] == "gpt-5.6-luna"
