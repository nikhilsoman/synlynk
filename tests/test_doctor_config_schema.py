import json
import os


def test_doctor_flags_malformed_config_json(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk")
    with open(".synlynk/config.json", "w") as f:
        json.dump({"identity_slug": 123}, f)  # wrong type

    from synlynk.doctor import _hc_config_schema

    result = _hc_config_schema()
    assert result.status == "fail"
    assert "identity_slug" in result.message


def test_doctor_passes_valid_config_json(tmp_path, monkeypatch):
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
