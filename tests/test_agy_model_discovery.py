"""Agy model discovery and tier validation (gh:#2268)."""

import json

from synlynk.models import (
    ModelSpec,
    _parse_agy_models_listing,
    discover_models,
    probe_cli_harness,
    resolve_tier_model,
)


AGY_MODELS_OUTPUT = """\
Fetching available models...
gemini-3.8-flash-high\tGemini 3.8 Flash (High)
gemini-3.8-flash-medium\tGemini 3.8 Flash (Medium)
gemini-3.8-flash-low\tGemini 3.8 Flash (Low)
claude-sonnet-4-6\tClaude Sonnet 4.6 (Thinking)
claude-opus-4-6-thinking\tClaude Opus 4.6 (Thinking)
gpt-oss-120b-medium\tGPT-OSS 120B (Medium)
"""


def test_agy_models_listing_keeps_ids_and_drops_display_names():
    names = _parse_agy_models_listing(AGY_MODELS_OUTPUT)
    assert names == [
        "gemini-3.8-flash-high",
        "gemini-3.8-flash-medium",
        "gemini-3.8-flash-low",
        "claude-sonnet-4-6",
        "claude-opus-4-6-thinking",
        "gpt-oss-120b-medium",
    ]
    assert "Gemini" not in names


def test_agy_probe_uses_models_subcommand(monkeypatch):
    calls = []

    class Result:
        stdout = AGY_MODELS_OUTPUT
        stderr = ""

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return Result()

    monkeypatch.setattr("synlynk.models.shutil.which", lambda _exe: "/usr/bin/agy")
    monkeypatch.setattr("synlynk.models.subprocess.run", fake_run)

    specs = probe_cli_harness("agy")
    assert calls == [["agy", "models"]]
    assert [spec.model_id for spec in specs] == _parse_agy_models_listing(AGY_MODELS_OUTPUT)
    assert {spec.harness_binding for spec in specs} == {"agy"}


def test_discover_models_keeps_agy_binding_when_ids_overlap(monkeypatch):
    def fake_probe(harness, executable=None, timeout=5.0):
        if harness == "claude":
            return [ModelSpec("claude-sonnet-4-6", "discovered", "claude", discovered=True)]
        if harness == "agy":
            return [ModelSpec("claude-sonnet-4-6", "discovered", "agy", discovered=True),
                    ModelSpec("gemini-3.8-flash-medium", "discovered", "agy", discovered=True)]
        return []

    monkeypatch.setattr("synlynk.models.probe_cli_harness", fake_probe)
    monkeypatch.setattr("synlynk.models.probe_local_runtimes", lambda timeout=1.5: [])

    found = {(spec.harness_binding, spec.model_id) for spec in discover_models()}
    assert ("agy", "gemini-3.8-flash-medium") in found
    assert ("agy", "claude-sonnet-4-6") in found
    assert ("claude", "claude-sonnet-4-6") in found


def test_resolve_tier_model_replaces_stale_agy_catalog_id(tmp_path, monkeypatch):
    catalog = {
        "schema_version": 1,
        "tiers": {
            "fast": {"agy": "gemini-3.7-flash-medium"},
            "pro": {"agy": "gemini-3.1-pro-low"},
            "reasoning": {"agy": "gemini-3.1-pro-high"},
        },
    }
    path = tmp_path / ".synlynk"
    path.mkdir()
    (path / "models.json").write_text(json.dumps(catalog))

    monkeypatch.setenv("SYNLYNK_FORCE_MODEL_DISCOVERY", "1")
    monkeypatch.setattr(
        "synlynk.models.probe_cli_harness",
        lambda harness, executable=None, timeout=5.0: [
            ModelSpec(model_id, "discovered", "agy", discovered=True)
            for model_id in _parse_agy_models_listing(AGY_MODELS_OUTPUT)
        ] if harness == "agy" else [],
    )
    from synlynk.models import _DISCOVERY_CACHE
    _DISCOVERY_CACHE.clear()

    assert resolve_tier_model("fast", "agy", repo_path=str(tmp_path)) == "gemini-3.8-flash-medium"
    assert resolve_tier_model("pro", "agy", repo_path=str(tmp_path)) == "gemini-3.8-flash-high"
    assert resolve_tier_model("reasoning", "agy", repo_path=str(tmp_path)) == "claude-opus-4-6-thinking"


def test_resolve_tier_model_uses_harness_scoped_discover_models_results(tmp_path, monkeypatch):
    path = tmp_path / ".synlynk"
    path.mkdir()
    (path / "models.json").write_text(json.dumps({"tiers": {"fast": {"agy": "retired-model"}}}))
    monkeypatch.setenv("SYNLYNK_FORCE_MODEL_DISCOVERY", "1")

    def fake_discover_models():
        return [
            ModelSpec("claude-sonnet-4-6", "discovered", "claude", discovered=True),
            ModelSpec("gemini-3.8-flash-medium", "discovered", "agy", discovered=True),
        ]

    monkeypatch.setattr("synlynk.models.discover_models", fake_discover_models)
    from synlynk.models import _DISCOVERY_CACHE
    _DISCOVERY_CACHE.clear()

    assert resolve_tier_model("fast", "agy", repo_path=str(tmp_path)) == "gemini-3.8-flash-medium"


def test_resolve_tier_model_keeps_catalog_id_when_probe_is_empty(tmp_path, monkeypatch):
    catalog = {"tiers": {"fast": {"agy": "gemini-3.7-flash-medium"}}}
    path = tmp_path / ".synlynk"
    path.mkdir()
    (path / "models.json").write_text(json.dumps(catalog))
    monkeypatch.delenv("SYNLYNK_FORCE_MODEL_DISCOVERY", raising=False)

    assert resolve_tier_model("fast", "agy", repo_path=str(tmp_path)) == "gemini-3.7-flash-medium"


def test_resolve_tier_model_keeps_live_catalog_id(tmp_path, monkeypatch):
    catalog = {"tiers": {"fast": {"agy": "gemini-3.8-flash-low"}}}
    path = tmp_path / ".synlynk"
    path.mkdir()
    (path / "models.json").write_text(json.dumps(catalog))
    monkeypatch.setenv("SYNLYNK_FORCE_MODEL_DISCOVERY", "1")
    monkeypatch.setattr(
        "synlynk.models.probe_cli_harness",
        lambda harness, executable=None, timeout=5.0: [
            ModelSpec("gemini-3.8-flash-low", "discovered", "agy", discovered=True),
            ModelSpec("gemini-3.8-flash-medium", "discovered", "agy", discovered=True),
        ] if harness == "agy" else [],
    )
    from synlynk.models import _DISCOVERY_CACHE
    _DISCOVERY_CACHE.clear()

    assert resolve_tier_model("fast", "agy", repo_path=str(tmp_path)) == "gemini-3.8-flash-low"
