"""Unit coverage for the first-class model registry and discovery boundaries."""

import json
import sqlite3


def test_active_harness_models_treats_unavailable_catalog_as_empty():
    from synlynk.db import get_active_harness_models

    assert get_active_harness_models(None, harness="codex") == []

    conn = sqlite3.connect(":memory:")
    assert get_active_harness_models(conn, harness="codex") == []
    conn.close()
    assert get_active_harness_models(conn, harness="codex") == []


def test_builtin_catalog_has_entitlement_and_geometry():
    from synlynk.models import BUILTIN_FAMILIES, BUILTIN_MODEL_CATALOG, EntitlementTier

    assert {tier for tier in EntitlementTier} == {
        EntitlementTier.INCLUDED_IN_BASE,
        EntitlementTier.SUBSCRIPTION_CAPPED,
        EntitlementTier.METERED_EXTRA_USAGE_ONLY,
        EntitlementTier.ZERO_COST_LOCAL,
    }
    assert any(f.context_geometry.max_input_tokens for f in BUILTIN_FAMILIES)
    assert any(m.entitlement_tier == EntitlementTier.ZERO_COST_LOCAL for m in BUILTIN_MODEL_CATALOG)


def test_builtin_catalog_uses_current_remote_models_and_preserves_local_models():
    from synlynk.models import BUILTIN_MODEL_CATALOG

    model_ids = {model.model_id for model in BUILTIN_MODEL_CATALOG}
    assert {
        "claude-opus-5", "claude-opus-5-5", "claude-sonnet-5",
        "claude-fable-5-1", "claude-fable-5", "claude-haiku-4-5-20251001",
        "gemini-3.8-flash-medium", "gemini-3.8-flash-high", "claude-opus-4-6-thinking",
        "gpt-5.6-luna", "grok-4.7", "grok-4.6",
    } <= model_ids
    assert {"deepseek-r1", "gemma-2-9b-it-q4", "qwen2.5"} <= model_ids
    assert {
        "Hermes-3-Llama-3.1-8B",
        "Hermes-3-Llama-3.1-70B",
        "Hermes-3-Llama-3.1-405B",
    } <= model_ids
    assert not model_ids & {
        "claude-3-5-sonnet-20241022", "claude-3-5-opus-20240229",
        "gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.0-flash",
        "gemini-3-pro", "gemini-3-flash", "gemini-3.1-pro", "gemini-3.5-flash-base",
        "gemini-3-flash-preview", "gemini-3.1-pro-preview",
        "grok-2-latest", "gpt-4o-2024-11-20", "o3",
    }


def test_model_registry_persists_and_queries(project_dir):
    from synlynk import _get_db
    from synlynk.db import get_model, list_models
    from synlynk.models import register_builtin_models

    conn = _get_db()
    register_builtin_models(conn)
    conn.commit()
    rows = list_models(conn, harness="codex")
    assert rows and rows[0]["model_id"] == "gpt-5.6-luna"
    assert get_model(conn, rows[0]["model_id"])["entitlement_tier"] == "included_in_base"
    assert json.loads(conn.execute("SELECT rates FROM models LIMIT 1").fetchone()[0])["input_per_1k"] == 0.0
    conn.close()


def test_cli_probe_is_safe_when_binary_is_missing(monkeypatch):
    from synlynk.models import probe_cli_harness

    monkeypatch.setattr("synlynk.models.shutil.which", lambda _: None)
    assert probe_cli_harness("claude") == []


def test_ollama_response_becomes_zero_cost_local(monkeypatch):
    from synlynk.models import EntitlementTier, probe_ollama

    monkeypatch.setattr("synlynk.models._probe_http", lambda url, timeout: ["qwen2.5"] if url.endswith("/api/tags") else [])
    assert probe_ollama()[0].entitlement_tier == EntitlementTier.ZERO_COST_LOCAL


def test_model_commands_seed_and_render_json(project_dir, capsys):
    from synlynk.models import cmd_models_list

    cmd_models_list(json_output=True)
    payload = json.loads(capsys.readouterr().out)
    assert any(item["model_id"] == "gpt-5.6-luna" for item in payload)


def test_resolve_tier_model_uses_static_bootstrap_when_discovery_is_empty(project_dir, monkeypatch):
    import synlynk.models as models

    monkeypatch.setattr(models, "_static_tier_model", lambda tier, harness, repo_path=None: "seed-model")
    assert models.resolve_tier_model("pro", "codex") == "seed-model"


def test_resolve_tier_model_prefers_state_db_discovery_over_static_catalog(project_dir, monkeypatch):
    import synlynk as sl
    import synlynk.models as models
    from synlynk.db import upsert_harness_model

    monkeypatch.setattr(models, "_static_tier_model", lambda tier, harness, repo_path=None: "stale-static-model")
    conn = sl._get_db()
    upsert_harness_model(
        conn, "codex", "discovered-model", complexity_tier="pro",
        discovered_at="2026-10-14T00:00:00+00:00",
    )
    conn.commit()
    conn.close()

    assert models.resolve_tier_model("pro", "codex") == "discovered-model"
