"""Grok model discovery and tier validation (gh:#2291)."""

import json

from synlynk.models import (
    ModelSpec,
    _parse_grok_models_listing,
    probe_cli_harness,
    resolve_tier_model,
)

GROK_MODELS_OUTPUT = """\
You are logged in with grok.com.

Default model: grok-4.7

Available models:
  * grok-4.7 (default)
  - grok-4.7-build-fast
  - grok-4.6
  - grok-4.5
"""


def test_grok_models_listing_extracts_models_and_drops_site_urls():
    names = _parse_grok_models_listing(GROK_MODELS_OUTPUT)
    assert names == [
        "grok-4.7",
        "grok-4.7-build-fast",
        "grok-4.6",
        "grok-4.5",
    ]
    assert "grok.com" not in names


def test_grok_probe_uses_models_subcommand(monkeypatch):
    calls = []

    class Result:
        stdout = GROK_MODELS_OUTPUT
        stderr = ""

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return Result()

    monkeypatch.setattr("synlynk.models.shutil.which", lambda _exe: "/usr/bin/grok")
    monkeypatch.setattr("synlynk.models.subprocess.run", fake_run)

    specs = probe_cli_harness("grok")
    assert calls == [["grok", "models"]]
    assert [spec.model_id for spec in specs] == [
        "grok-4.7",
        "grok-4.7-build-fast",
        "grok-4.6",
        "grok-4.5",
    ]
    assert {spec.harness_binding for spec in specs} == {"grok"}


def test_resolve_tier_model_replaces_stale_grok_catalog_id(tmp_path, monkeypatch):
    catalog = {
        "schema_version": 1,
        "tiers": {
            "fast": {"grok": "retired-grok-fast"},
            "pro": {"grok": "retired-grok-pro"},
            "reasoning": {"grok": "retired-grok-reasoning"},
        },
    }
    path = tmp_path / ".synlynk"
    path.mkdir()
    (path / "models.json").write_text(json.dumps(catalog))

    monkeypatch.setenv("SYNLYNK_FORCE_MODEL_DISCOVERY", "1")
    monkeypatch.setattr(
        "synlynk.models.probe_cli_harness",
        lambda harness, executable=None, timeout=5.0: [
            ModelSpec(model_id, "discovered", "grok", discovered=True)
            for model_id in _parse_grok_models_listing(GROK_MODELS_OUTPUT)
        ] if harness == "grok" else [],
    )
    from synlynk.models import _DISCOVERY_CACHE
    _DISCOVERY_CACHE.clear()

    assert resolve_tier_model("fast", "grok", repo_path=str(tmp_path)) == "grok-4.6"
    assert resolve_tier_model("pro", "grok", repo_path=str(tmp_path)) == "grok-4.7"
    assert resolve_tier_model("reasoning", "grok", repo_path=str(tmp_path)) == "grok-4.7"


def test_resolve_tier_model_keeps_grok_catalog_id_when_probe_is_empty(tmp_path, monkeypatch):
    catalog = {"tiers": {"fast": {"grok": "grok-4.6"}}}
    path = tmp_path / ".synlynk"
    path.mkdir()
    (path / "models.json").write_text(json.dumps(catalog))
    monkeypatch.delenv("SYNLYNK_FORCE_MODEL_DISCOVERY", raising=False)

    assert resolve_tier_model("fast", "grok", repo_path=str(tmp_path)) == "grok-4.6"


def test_resolve_tier_model_keeps_live_grok_catalog_id(tmp_path, monkeypatch):
    catalog = {"tiers": {"fast": {"grok": "grok-4.6"}}}
    path = tmp_path / ".synlynk"
    path.mkdir()
    (path / "models.json").write_text(json.dumps(catalog))
    monkeypatch.setenv("SYNLYNK_FORCE_MODEL_DISCOVERY", "1")
    monkeypatch.setattr(
        "synlynk.models.probe_cli_harness",
        lambda harness, executable=None, timeout=5.0: [
            ModelSpec("grok-4.6", "discovered", "grok", discovered=True),
            ModelSpec("grok-4.7", "discovered", "grok", discovered=True),
        ] if harness == "grok" else [],
    )
    from synlynk.models import _DISCOVERY_CACHE
    _DISCOVERY_CACHE.clear()

    assert resolve_tier_model("fast", "grok", repo_path=str(tmp_path)) == "grok-4.6"


def test_resolve_tier_model_replaces_stale_active_grok_row(tmp_path, monkeypatch):
    """Live Grok discovery must validate persisted rows before returning them (gh:#2291)."""
    from synlynk import _get_db
    from synlynk.db import upsert_harness_model

    path = tmp_path / ".synlynk"
    path.mkdir()
    (path / "models.json").write_text(json.dumps({
        "tiers": {"fast": {"grok": "retired-grok-fast"}},
    }))

    monkeypatch.setenv("SYNLYNK_FORCE_MODEL_DISCOVERY", "1")
    monkeypatch.setattr(
        "synlynk.models.probe_cli_harness",
        lambda harness, executable=None, timeout=5.0: [
            ModelSpec("grok-4.6", "discovered", "grok", discovered=True),
        ] if harness == "grok" else [],
    )
    from synlynk.models import _DISCOVERY_CACHE
    _DISCOVERY_CACHE.clear()

    conn = _get_db()
    upsert_harness_model(
        conn, "grok", "retired-grok-fast", complexity_tier="fast",
        discovered_at="2026-10-14T00:00:00+00:00",
    )
    conn.commit()
    conn.close()

    assert resolve_tier_model("fast", "grok", repo_path=str(tmp_path)) == "grok-4.6"
