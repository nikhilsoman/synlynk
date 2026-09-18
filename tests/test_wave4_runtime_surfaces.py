import json

import pytest


def test_doctor_identity_slug_warns_when_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / ".synlynk" / "config.json").write_text(json.dumps({}))
    from synlynk.doctor import _hc_identity_slug
    result = _hc_identity_slug()
    assert result.status == "warn"


def test_dispatch_allows_config_without_identity_slug(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / ".synlynk" / "config.json").write_text(json.dumps({}))
    from synlynk.dispatch import dispatch_agent
    dispatch_agent("codex", "run tests", skip_preflight=True)


def test_dispatch_resolves_product_type_when_registry_exists(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / ".synlynk" / "config.json").write_text(
        json.dumps({"identity_slug": "vdowrx"})
    )
    from synlynk.product_store import types_yaml_path
    types_yaml_path("vdowrx").parent.mkdir(parents=True, exist_ok=True)
    types_yaml_path("vdowrx").write_text(
        json.dumps({"types": {"frontend-qa": {"kind": "qa", "canonical": False}}})
    )
    from synlynk.dispatch import dispatch_agent

    with pytest.raises(ValueError, match="unknown product type"):
        dispatch_agent("codex", "run tests", role="missing", skip_preflight=True)
