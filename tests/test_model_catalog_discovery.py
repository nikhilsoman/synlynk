"""Discovery-pass coverage for harness model catalog refresh."""

import json

from synlynk.models import (
    ModelSpec,
    RateCard,
    probe_cli_harness,
)


CLAUDE_LISTING = json.dumps({
    "models": [
        {
            "id": "priced-high",
            "rates": {"input_per_1k": 0.004, "output_per_1k": 0.02},
            "context_window_tokens": 200000,
        },
        {
            "id": "claude-sonnet-4-6",
            "input_per_mtok": 3.0,
            "output_per_mtok": 15.0,
            "cache_read_per_mtok": 0.3,
            "cache_write_per_mtok": 3.75,
            "tool_use_per_mtok": 0.5,
        },
    ]
})


def _conn():
    from synlynk import _get_db

    return _get_db()


def _only(monkeypatch, *names):
    import synlynk._constants as constants

    monkeypatch.setattr(
        constants,
        "HARNESS_CAPABILITY_BASELINES",
        {name: {} for name in names},
    )


def _row(conn, harness, model_id, provider="native"):
    found = conn.execute(
        "SELECT * FROM harness_models WHERE harness_name=? AND model_id=? AND provider=?",
        (harness, model_id, provider),
    ).fetchone()
    assert found is not None
    columns = [item[0] for item in conn.execute("SELECT * FROM harness_models LIMIT 0").description]
    return dict(zip(columns, found))


def test_cli_probe_parses_rates_effort_and_leaves_unencoded_tier_null(monkeypatch):
    class Result:
        stdout = CLAUDE_LISTING
        stderr = "noise that must not break json"

    monkeypatch.setattr("synlynk.models.shutil.which", lambda exe: "/usr/bin/claude" if exe == "claude" else None)
    monkeypatch.setattr("synlynk.models.subprocess.run", lambda cmd, **kwargs: Result())

    specs = probe_cli_harness("claude")
    by_id = {spec.model_id: spec for spec in specs}
    assert set(by_id) == {"priced-high", "claude-sonnet-4-6"}
    assert by_id["priced-high"].probe_rates["input_per_mtok"] == 4.0
    assert by_id["priced-high"].probe_rates["output_per_mtok"] == 20.0
    assert by_id["priced-high"].probe_rates["context_window_tokens"] == 200000
    assert "complexity_tier" not in by_id["claude-sonnet-4-6"].probe_rates

    _only(monkeypatch, "claude")
    conn = _conn()
    from synlynk.models import run_model_catalog_discovery

    rows = {row["model_id"]: row for row in run_model_catalog_discovery(conn)}
    priced = rows["priced-high"]
    assert priced["discovery_source"] == "cli:claude"
    assert priced["rate_source"] == "cli_probe"
    assert priced["rate_input_per_mtok"] == 4.0
    assert priced["rate_output_per_mtok"] == 20.0
    assert priced["complexity_tier"] == "high"
    assert priced["max_effort_level"] == "high"
    assert priced["context_window_tokens"] == 200000
    plain = rows["claude-sonnet-4-6"]
    assert plain["complexity_tier"] is None
    assert plain["max_effort_level"] is None
    assert plain["rate_tool_use_per_mtok"] == 0.5
    assert plain["rate_cache_write_per_mtok"] == 3.75
    stored = _row(conn, "claude", "priced-high")
    assert stored["status"] == "active"
    assert stored["provider"] == "native"
    conn.close()


def test_agy_suffix_sets_tier_and_curated_fallback_does_not(monkeypatch):
    _only(monkeypatch, "agy")

    def fake_probe(harness, executable=None, timeout=5.0):
        assert harness == "agy"
        return [
            ModelSpec("gemini-3.8-flash-low", "discovered", "agy", discovered=True, discovery_source="cli:agy"),
            ModelSpec("claude-opus-4-6-thinking", "discovered", "agy", discovered=True, discovery_source="cli:agy"),
            ModelSpec("agy-session-only", "discovered", "agy", discovered=True, discovery_source="cli:agy"),
        ]

    monkeypatch.setattr("synlynk.models.probe_cli_harness", fake_probe)
    conn = _conn()
    from synlynk.models import run_model_catalog_discovery

    rows = {row["model_id"]: row for row in run_model_catalog_discovery(conn)}
    assert rows["gemini-3.8-flash-low"]["complexity_tier"] == "low"
    assert rows["gemini-3.8-flash-low"]["max_effort_level"] == "low"
    assert rows["claude-opus-4-6-thinking"]["complexity_tier"] is None
    assert rows["claude-opus-4-6-thinking"]["max_effort_level"] is None
    assert "gemini-3.8-flash-high" not in rows

    monkeypatch.setattr("synlynk.models.probe_cli_harness", lambda *args, **kwargs: [])
    fallback = {row["model_id"]: row for row in run_model_catalog_discovery(conn)}
    curated = fallback["gemini-3.8-flash-high"]
    assert curated["discovery_source"] == "curated_fallback"
    assert curated["rate_source"] == "curated_fallback"
    assert curated["complexity_tier"] is None
    assert curated["max_effort_level"] is None
    assert curated["context_window_tokens"] == 1_000_000
    assert _row(conn, "agy", "agy-session-only")["status"] == "stale"
    assert _row(conn, "agy", "gemini-3.8-flash-low")["status"] == "active"
    assert _row(conn, "agy", "gemini-3.8-flash-low")["discovery_source"] == "curated_fallback"
    conn.close()


def test_catalog_rate_card_used_when_probe_omits_prices(monkeypatch):
    _only(monkeypatch, "claude")
    priced = ModelSpec(
        "claude-haiku-4-5-20251001",
        "claude-5",
        "claude",
        rates=RateCard(input_per_1k=0.003, output_per_1k=0.015, cache_read_per_1k=0.0003),
    )
    monkeypatch.setattr("synlynk.models.BUILTIN_MODEL_CATALOG", (priced,))
    monkeypatch.setattr(
        "synlynk.models.probe_cli_harness",
        lambda *args, **kwargs: [
            ModelSpec(
                "claude-haiku-4-5-20251001",
                "discovered",
                "claude",
                discovered=True,
                discovery_source="cli:claude",
            )
        ],
    )
    conn = _conn()
    from synlynk.models import run_model_catalog_discovery

    row = run_model_catalog_discovery(conn)[0]
    assert row["rate_source"] == "curated_fallback"
    assert row["rate_input_per_mtok"] == 3.0
    assert row["rate_output_per_mtok"] == 15.0
    assert row["rate_cache_read_per_mtok"] == 0.3
    assert row["rate_cache_write_per_mtok"] is None
    assert row["complexity_tier"] is None
    conn.close()


def test_codex_reads_config_file_and_falls_back_when_absent(monkeypatch, tmp_path):
    _only(monkeypatch, "codex")
    codex_home = tmp_path / "codex"
    codex_home.mkdir()
    (codex_home / "config.toml").write_text('model = "gpt-5.4-mini"\n')
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    conn = _conn()
    from synlynk.models import run_model_catalog_discovery

    rows = run_model_catalog_discovery(conn)
    assert len(rows) == 1
    assert rows[0]["model_id"] == "gpt-5.4-mini"
    assert rows[0]["discovery_source"] == "config_file"
    assert rows[0]["rate_source"] is None
    assert rows[0]["complexity_tier"] is None
    assert rows[0]["max_effort_level"] is None

    (codex_home / "config.toml").unlink()
    fallback = run_model_catalog_discovery(conn)
    assert {row["model_id"] for row in fallback} == {"gpt-5.6-luna"}
    assert fallback[0]["discovery_source"] == "curated_fallback"
    assert _row(conn, "codex", "gpt-5.4-mini")["status"] == "stale"
    assert _row(conn, "codex", "gpt-5.6-luna")["status"] == "active"
    conn.close()


def test_local_runtime_hit_skips_curated_fallback(monkeypatch):
    _only(monkeypatch, "local")
    monkeypatch.setattr(
        "synlynk.models.probe_local_runtimes",
        lambda timeout=1.5: [
            ModelSpec(
                "qwen-live",
                "discovered",
                "local",
                locality="on_device_local",
                discovered=True,
                discovery_source="ollama:/api/tags",
            )
        ],
    )
    conn = _conn()
    from synlynk.models import run_model_catalog_discovery

    rows = run_model_catalog_discovery(conn)
    assert [row["model_id"] for row in rows] == ["qwen-live"]
    assert rows[0]["discovery_source"] == "ollama:/api/tags"
    assert rows[0]["complexity_tier"] is None
    assert "qwen2.5" not in {row["model_id"] for row in rows}
    conn.close()


def test_stale_marking_ignores_unscanned_harness_and_gateway_rows(monkeypatch):
    _only(monkeypatch, "claude")
    monkeypatch.setattr(
        "synlynk.models.probe_cli_harness",
        lambda *args, **kwargs: [
            ModelSpec("claude-sonnet-5", "discovered", "claude", discovered=True, discovery_source="cli:claude")
        ],
    )
    from synlynk.db import upsert_harness_model
    from synlynk.models import run_model_catalog_discovery

    conn = _conn()
    upsert_harness_model(conn, "claude", "gone-model", provider="native", discovery_source="cli:claude")
    upsert_harness_model(conn, "muse", "muse-spark", provider="native", discovery_source="curated")
    upsert_harness_model(conn, "claude", "via-router", provider="openrouter", discovery_source="provider_api")
    run_model_catalog_discovery(conn)
    assert _row(conn, "claude", "gone-model")["status"] == "stale"
    assert _row(conn, "claude", "claude-sonnet-5")["status"] == "active"
    assert _row(conn, "muse", "muse-spark")["status"] == "active"
    assert _row(conn, "claude", "via-router", provider="openrouter")["status"] == "active"
    conn.close()


def test_empty_gateway_list_does_not_probe_or_stale(monkeypatch):
    _only(monkeypatch, "claude")
    calls = []
    monkeypatch.setattr("synlynk.models.probe_cli_harness", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        "synlynk.models.probe_gateway_provider",
        lambda provider: calls.append(provider) or [],
    )
    monkeypatch.setattr("synlynk.models.BUILTIN_MODEL_CATALOG", ())
    from synlynk.db import upsert_harness_model
    from synlynk.models import CONFIGURED_GATEWAY_PROVIDERS, run_model_catalog_discovery

    assert CONFIGURED_GATEWAY_PROVIDERS == ()
    conn = _conn()
    upsert_harness_model(conn, "openrouter", "some-model", provider="openrouter", discovery_source="provider_api")
    rows = run_model_catalog_discovery(conn)
    assert rows == []
    assert calls == []
    assert _row(conn, "openrouter", "some-model", provider="openrouter")["status"] == "active"
    conn.close()


def test_configured_gateway_without_adapter_is_still_a_noop(monkeypatch):
    _only(monkeypatch, "claude")
    monkeypatch.setattr("synlynk.models.probe_cli_harness", lambda *args, **kwargs: [])
    monkeypatch.setattr("synlynk.models.BUILTIN_MODEL_CATALOG", ())
    monkeypatch.setattr("synlynk.models.CONFIGURED_GATEWAY_PROVIDERS", ("openrouter",))
    monkeypatch.setattr("synlynk.models.probe_gateway_provider", lambda provider: [])
    from synlynk.db import upsert_harness_model
    from synlynk.models import run_model_catalog_discovery

    conn = _conn()
    upsert_harness_model(conn, "claude", "kept", provider="openrouter")
    run_model_catalog_discovery(conn)
    assert _row(conn, "claude", "kept", provider="openrouter")["status"] == "active"
    conn.close()


def test_cmd_models_discover_uses_catalog_discovery(monkeypatch, capsys):
    seen = {}

    def fake(conn):
        seen["called"] = True
        return [{"harness_name": "grok", "model_id": "grok-4.7", "discovery_source": "cli:grok"}]

    monkeypatch.setattr("synlynk.models.run_model_catalog_discovery", fake)
    from synlynk.models import cmd_models_discover

    rows = cmd_models_discover(json_output=True)
    payload = json.loads(capsys.readouterr().out)
    assert seen["called"] is True
    assert rows == payload
    assert payload[0]["model_id"] == "grok-4.7"
