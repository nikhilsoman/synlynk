import json


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
