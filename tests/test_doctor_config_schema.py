import json
import os


def test_doctor_flags_malformed_config_json(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk")
    with open(".synlynk/workspace.json", "w") as f:
        json.dump({"schema_version": 1, "identity_slug": 123}, f)  # wrong type
    with open(".synlynk/billing.json", "w") as f:
        json.dump({"schema_version": 1, "budget": {"limit_usd": 10.0, "limit_requests": 100}, "harness_billing": {}}, f)

    from synlynk.doctor import _hc_config_schema

    result = _hc_config_schema()
    assert result.status == "fail"
    assert "identity_slug" in result.message


def test_doctor_passes_valid_config_json(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk")
    with open(".synlynk/workspace.json", "w") as f:
        json.dump({
            "schema_version": 1,
            "workspace_id": "ws-ok",
            "identity_slug": "ok",
        }, f)
    with open(".synlynk/billing.json", "w") as f:
        json.dump({
            "schema_version": 1,
            "budget": {"limit_usd": 10.0, "limit_requests": 100},
            "harness_billing": {},
        }, f)

    from synlynk.doctor import _hc_config_schema

    result = _hc_config_schema()
    assert result.status == "ok"


def test_doctor_falls_back_to_legacy_config_json(tmp_path, monkeypatch):
    """A not-yet-migrated repo with only legacy config.json should still validate."""
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk")
    with open(".synlynk/config.json", "w") as f:
        json.dump({
            "schema_version": 1,
            "budget": {"limit_usd": 10.0, "limit_requests": 100},
            "harness_billing": {},
            "workspace_id": "ws-ok",
            "identity_slug": "ok",
        }, f)

    from synlynk.doctor import _hc_config_schema

    result = _hc_config_schema()
    assert result.status == "ok"


def test_doctor_config_schema_warns_when_nothing_present(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk")

    from synlynk.doctor import _hc_config_schema

    result = _hc_config_schema()
    assert result.status == "warn"
