"""Codex model discovery and tier validation (gh:#2291)."""

import json

from synlynk.models import (
    ModelSpec,
    probe_cli_harness,
    resolve_tier_model,
)


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

    # Stale catalog ID (gpt-5.6-luna) should drift to the live configured model (gpt-6-luna)
    assert resolve_tier_model("fast", "codex", repo_path=str(tmp_path)) == "gpt-6-luna"


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
