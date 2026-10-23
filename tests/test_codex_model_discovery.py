"""Codex model discovery and tier validation (gh:#2291)."""

import json

from synlynk.models import (
    probe_cli_harness,
    resolve_tier_model,
    valid_harness_model_ids,
)


_CODEX_TIERS = {
    "fast": {"codex": "gpt-5.6-luna"},
    "pro": {"codex": "gpt-5.6-terra"},
    "reasoning": {"codex": "gpt-5.6-sol"},
}


def _write_codex_catalog(tmp_path, tiers=None, model_ids=None):
    path = tmp_path / ".synlynk"
    path.mkdir(exist_ok=True)
    ids = model_ids or ("gpt-5.6-luna", "gpt-5.6-terra", "gpt-5.6-sol")
    catalog = {
        "schema_version": 1,
        "tiers": tiers or _CODEX_TIERS,
        "models": [{"model_id": model_id, "harness": "codex"} for model_id in ids],
    }
    (path / "models.json").write_text(json.dumps(catalog))
    return path


def _force_codex_config(tmp_path, monkeypatch, model_id):
    codex_home = tmp_path / "codex"
    codex_home.mkdir()
    (codex_home / "config.toml").write_text(f'model = "{model_id}"\n')
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    monkeypatch.setenv("SYNLYNK_FORCE_MODEL_DISCOVERY", "1")
    from synlynk.models import _DISCOVERY_CACHE
    _DISCOVERY_CACHE.clear()


def test_codex_probe_reads_config_toml(tmp_path, monkeypatch):
    codex_home = tmp_path / "codex"
    codex_home.mkdir()
    (codex_home / "config.toml").write_text('model = "gpt-6-luna"\n')
    monkeypatch.setenv("CODEX_HOME", str(codex_home))

    specs = probe_cli_harness("codex")
    assert len(specs) == 1
    assert specs[0].model_id == "gpt-6-luna"
    assert specs[0].harness_binding == "codex"
    assert specs[0].discovery_source == "config_file"


def test_resolve_tier_model_replaces_stale_codex_catalog_id(tmp_path, monkeypatch):
    catalog = {
        "schema_version": 1,
        "tiers": {
            "fast": {"codex": "gpt-5.6-luna"},
            "pro": {"codex": "gpt-5.6-terra"},
            "reasoning": {"codex": "gpt-5.6-sol"},
        },
    }
    path = tmp_path / ".synlynk"
    path.mkdir()
    (path / "models.json").write_text(json.dumps(catalog))

    codex_home = tmp_path / "codex"
    codex_home.mkdir()
    (codex_home / "config.toml").write_text('model = "gpt-6-luna"\n')
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    monkeypatch.setenv("SYNLYNK_FORCE_MODEL_DISCOVERY", "1")
    from synlynk.models import _DISCOVERY_CACHE
    _DISCOVERY_CACHE.clear()

    # Same-tier successor replaces only fast. Pro and reasoning stay curated.
    assert resolve_tier_model("fast", "codex", repo_path=str(tmp_path)) == "gpt-6-luna"
    assert resolve_tier_model("pro", "codex", repo_path=str(tmp_path)) == "gpt-5.6-terra"
    assert resolve_tier_model("reasoning", "codex", repo_path=str(tmp_path)) == "gpt-5.6-sol"


def test_resolve_tier_model_keeps_codex_catalog_id_when_probe_is_empty(tmp_path, monkeypatch):
    catalog = {"tiers": {"fast": {"codex": "gpt-5.6-luna"}}}
    path = tmp_path / ".synlynk"
    path.mkdir()
    (path / "models.json").write_text(json.dumps(catalog))
    monkeypatch.delenv("SYNLYNK_FORCE_MODEL_DISCOVERY", raising=False)

    assert resolve_tier_model("fast", "codex", repo_path=str(tmp_path)) == "gpt-5.6-luna"


def test_resolve_tier_model_replaces_stale_active_codex_row(tmp_path, monkeypatch):
    """Live Codex discovery must validate persisted rows before returning them (gh:#2291)."""
    from synlynk import _get_db
    from synlynk.db import upsert_harness_model

    path = tmp_path / ".synlynk"
    path.mkdir()
    (path / "models.json").write_text(json.dumps({
        "tiers": {"fast": {"codex": "retired-codex-model"}},
    }))

    codex_home = tmp_path / "codex"
    codex_home.mkdir()
    (codex_home / "config.toml").write_text('model = "gpt-6-luna"\n')
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    monkeypatch.setenv("SYNLYNK_FORCE_MODEL_DISCOVERY", "1")
    from synlynk.models import _DISCOVERY_CACHE
    _DISCOVERY_CACHE.clear()

    conn = _get_db()
    upsert_harness_model(
        conn, "codex", "retired-codex-model", complexity_tier="fast",
        discovered_at="2026-10-14T00:00:00+00:00",
    )
    conn.commit()
    conn.close()

    assert resolve_tier_model("fast", "codex", repo_path=str(tmp_path)) == "gpt-6-luna"


def test_single_unrelated_codex_discovery_keeps_allowlisted_tiers(tmp_path, monkeypatch):
    """A one-model config.toml probe must not overwrite other curated tiers (gh:#2552)."""
    _write_codex_catalog(tmp_path)
    _force_codex_config(tmp_path, monkeypatch, "gpt-5.6-terra")

    assert resolve_tier_model("fast", "codex", repo_path=str(tmp_path)) == "gpt-5.6-luna"
    assert resolve_tier_model("pro", "codex", repo_path=str(tmp_path)) == "gpt-5.6-terra"
    assert resolve_tier_model("reasoning", "codex", repo_path=str(tmp_path)) == "gpt-5.6-sol"


def test_codex_tier_mapping_prefers_tier_specific_roster_over_stale_catalog(tmp_path, monkeypatch):
    """When discovery lists each tier, mapping follows that roster, not a stale id."""
    import synlynk.models as models

    _write_codex_catalog(
        tmp_path,
        tiers={
            "fast": {"codex": "retired-fast"},
            "pro": {"codex": "retired-pro"},
            "reasoning": {"codex": "retired-reasoning"},
        },
        model_ids=(
            "retired-fast", "retired-pro", "retired-reasoning",
            "gpt-5.6-luna", "gpt-5.6-terra", "gpt-5.6-sol",
        ),
    )
    monkeypatch.setattr(
        models, "discovered_model_ids",
        lambda harness: ["gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna"] if harness == "codex" else [],
    )

    assert resolve_tier_model("fast", "codex", repo_path=str(tmp_path)) == "gpt-5.6-luna"
    assert resolve_tier_model("pro", "codex", repo_path=str(tmp_path)) == "gpt-5.6-terra"
    assert resolve_tier_model("reasoning", "codex", repo_path=str(tmp_path)) == "gpt-5.6-sol"


def test_codex_fallback_keeps_configured_when_discovery_is_not_tier_specific(tmp_path, monkeypatch):
    """Safe fallback is the allowlisted configured id, not an arbitrary discovered id."""
    import synlynk.models as models

    _write_codex_catalog(tmp_path)
    monkeypatch.setattr(
        models, "discovered_model_ids",
        lambda harness: ["unrelated-codex-model"] if harness == "codex" else [],
    )

    assert resolve_tier_model("fast", "codex", repo_path=str(tmp_path)) == "gpt-5.6-luna"
    assert resolve_tier_model("pro", "codex", repo_path=str(tmp_path)) == "gpt-5.6-terra"
    assert resolve_tier_model("reasoning", "codex", repo_path=str(tmp_path)) == "gpt-5.6-sol"


def test_codex_explicit_allowlist_survives_single_discovery_and_rejects_invalid(tmp_path, monkeypatch):
    """Explicit model validation still accepts curated tiers and rejects unknown ids."""
    _write_codex_catalog(tmp_path)
    _force_codex_config(tmp_path, monkeypatch, "gpt-5.6-terra")

    valid = valid_harness_model_ids("codex", repo_path=str(tmp_path))
    assert "gpt-5.6-luna" in valid
    assert "gpt-5.6-terra" in valid
    assert "gpt-5.6-sol" in valid
    assert "gpt-5.1-codex" not in valid
