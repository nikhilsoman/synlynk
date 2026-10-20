"""Tests for synlynk.models catalog loading, validation, and tier resolution."""
import json
from pathlib import Path
from unittest.mock import patch
import pytest

from synlynk.models import (
    load_model_catalog,
    get_models_from_catalog,
    resolve_tier_model,
    BUILTIN_MODEL_CATALOG,
)


def test_load_model_catalog_default(tmp_path):
    catalog_path = tmp_path / ".synlynk" / "models.json"
    catalog_path.parent.mkdir(parents=True)
    catalog_data = {
        "schema_version": 1,
        "as_of": "2026-09-20",
        "tiers": {
            "fast": {
                "claude": "claude-haiku-4.5",
                "agy": "gemini-3.7-flash-medium",
                "codex": "gpt-5-mini",
            },
            "pro": {
                "claude": "claude-sonnet-5",
                "agy": "gemini-3.1-pro-low",
                "codex": "gpt-5",
            },
            "reasoning": {
                "claude": "claude-opus-5",
                "agy": "gemini-3.1-pro-low",
                "codex": "gpt-5.6-luna",
            },
        },
        "models": [
            {
                "model_id": "claude-sonnet-5",
                "family": "claude-5",
                "harness": "claude",
                "context_window": 200000,
                "max_output": 16384,
                "rates": {"input_per_1k": 0.003, "output_per_1k": 0.015},
            },
            {
                "model_id": "gemini-3.7-flash-medium",
                "family": "gemini-3",
                "harness": "agy",
                "context_window": 1000000,
                "max_output": 8192,
                "rates": {"input_per_1k": 0.0001, "output_per_1k": 0.0004},
            },
        ],
    }
    catalog_path.write_text(json.dumps(catalog_data))

    catalog = load_model_catalog(repo_path=str(tmp_path))
    assert catalog["schema_version"] == 1
    assert catalog["tiers"]["fast"]["agy"] == "gemini-3.7-flash-medium"

    # Test tier resolution
    assert resolve_tier_model("fast", "agy", repo_path=str(tmp_path)) == "gemini-3.7-flash-medium"
    assert resolve_tier_model("pro", "claude", repo_path=str(tmp_path)) == "claude-sonnet-5"
    assert resolve_tier_model("reasoning", "codex", repo_path=str(tmp_path)) == "gpt-5.6-luna"


def test_load_model_catalog_fallback_on_missing(tmp_path):
    # Missing catalog loads default/builtin gracefully
    catalog = load_model_catalog(repo_path=str(tmp_path))
    assert "tiers" in catalog
    assert "models" in catalog
    assert resolve_tier_model("fast", "agy", repo_path=str(tmp_path)) is not None


@pytest.mark.parametrize(
    ("tier", "codex_model"),
    (
        ("fast", "gpt-5.6-luna"),
        ("pro", "gpt-5.6-terra"),
        ("reasoning", "gpt-5.6-sol"),
    ),
)
def test_project_catalog_resolves_codex_and_local_tiers(monkeypatch, tier, codex_model):
    """Catalog tiers remain intentional even when no discovery DB is available."""
    import synlynk

    repo_root = Path(__file__).resolve().parents[1]
    monkeypatch.setattr(synlynk, "_get_db", lambda: None)

    catalog = load_model_catalog(repo_path=str(repo_root))
    assert resolve_tier_model(tier, "codex", repo_path=str(repo_root)) == codex_model
    assert resolve_tier_model(tier, "local", repo_path=str(repo_root)) == "Ornith-1.0-9B-4bit"
    assert catalog["tiers"][tier]["codex"] == codex_model
    assert catalog["tiers"][tier]["local"] == "Ornith-1.0-9B-4bit"


def test_project_catalog_has_verified_codex_rates_and_local_roster():
    repo_root = Path(__file__).resolve().parents[1]
    catalog = load_model_catalog(repo_path=str(repo_root))
    models = {model["model_id"]: model for model in catalog["models"]}

    assert {
        model_id: models[model_id]["rates"]
        for model_id in ("gpt-5.6-luna", "gpt-5.6-terra", "gpt-5.6-sol")
    } == {
        "gpt-5.6-luna": {"input_per_1k": 0.0002, "output_per_1k": 0.0012},
        "gpt-5.6-terra": {"input_per_1k": 0.002, "output_per_1k": 0.012},
        "gpt-5.6-sol": {"input_per_1k": 0.004, "output_per_1k": 0.02},
    }
    assert {
        model_id for model_id, model in models.items() if model["harness"] == "local"
    } == {
        "Ornith-1.0-9B-4bit",
        "Qwen2.5-Coder-14B-Instruct-4bit",
        "gemma-4-12B-it-qat-4bit",
    }
    assert models["Qwen2.5-Coder-14B-Instruct-4bit"]["dispatch_eligible"] is False
    assert models["Qwen2.5-Coder-14B-Instruct-4bit"]["qualification"] == "benchmark-only"
    assert models["gemma-4-12B-it-qat-4bit"]["dispatch_eligible"] is False
    assert models["gemma-4-12B-it-qat-4bit"]["qualification"] == "non-qualifying"


def test_get_models_from_catalog(tmp_path):
    catalog_path = tmp_path / ".synlynk" / "models.json"
    catalog_path.parent.mkdir(parents=True)
    catalog_data = {
        "schema_version": 1,
        "tiers": {"fast": {"agy": "gemini-3.7-flash-medium"}},
        "models": [
            {
                "model_id": "gemini-3.7-flash-medium",
                "family": "gemini-3",
                "harness": "agy",
                "context_window": 1000000,
                "rates": {"input_per_1k": 0.0001, "output_per_1k": 0.0004},
            }
        ],
    }
    catalog_path.write_text(json.dumps(catalog_data))

    models = get_models_from_catalog(repo_path=str(tmp_path))
    assert len(models) >= 1
    m = next(x for x in models if x.model_id == "gemini-3.7-flash-medium")
    assert m.harness_binding == "agy"
    assert m.rates.input_per_1k == 0.0001
