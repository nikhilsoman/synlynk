import json


def test_doctor_identity_slug_fails_closed(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / ".synlynk" / "config.json").write_text(json.dumps({}))
    from synlynk.doctor import _hc_identity_slug
    result = _hc_identity_slug()
    assert result.status == "fail"


def test_dispatch_rejects_config_without_identity_slug(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / ".synlynk" / "config.json").write_text(json.dumps({}))
    from synlynk.dispatch import dispatch_agent
    import pytest
    with pytest.raises(RuntimeError, match="identity_slug"):
        dispatch_agent("codex", "run tests")
