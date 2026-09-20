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
                "agy": "gemini-3.7-flash",
                "codex": "gpt-5-mini",
            },
            "pro": {
                "claude": "claude-sonnet-5",
                "agy": "gemini-3.0-pro",
                "codex": "gpt-5",
            },
            "reasoning": {
                "claude": "claude-opus-5",
                "agy": "gemini-3.5-pro",
                "codex": "o3",
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
                "model_id": "gemini-3.7-flash",
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
    assert catalog["tiers"]["fast"]["agy"] == "gemini-3.7-flash"

    # Test tier resolution
    assert resolve_tier_model("fast", "agy", repo_path=str(tmp_path)) == "gemini-3.7-flash"
    assert resolve_tier_model("pro", "claude", repo_path=str(tmp_path)) == "claude-sonnet-5"
    assert resolve_tier_model("reasoning", "codex", repo_path=str(tmp_path)) == "o3"


def test_load_model_catalog_fallback_on_missing(tmp_path):
    # Missing catalog loads default/builtin gracefully
    catalog = load_model_catalog(repo_path=str(tmp_path))
    assert "tiers" in catalog
    assert "models" in catalog
    assert resolve_tier_model("fast", "agy", repo_path=str(tmp_path)) is not None


def test_get_models_from_catalog(tmp_path):
    catalog_path = tmp_path / ".synlynk" / "models.json"
    catalog_path.parent.mkdir(parents=True)
    catalog_data = {
        "schema_version": 1,
        "tiers": {"fast": {"agy": "gemini-3.7-flash"}},
        "models": [
            {
                "model_id": "gemini-3.7-flash",
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
    m = next(x for x in models if x.model_id == "gemini-3.7-flash")
    assert m.harness_binding == "agy"
    assert m.rates.input_per_1k == 0.0001
