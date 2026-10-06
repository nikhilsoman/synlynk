"""Durable logging for auto-routing fallback decisions (#2064)."""

def test_local_unreachable_fallback_writes_sentinel_entry(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from synlynk import dispatch

    monkeypatch.setattr(dispatch, "_preflight_local_silent", lambda: False)
    monkeypatch.setattr(
        dispatch, "_read_local_fallback", lambda config_path=".synlynk/config.json": "codex"
    )

    result = dispatch._resolve_dispatch_agent("auto", "implement", None)

    assert result == "codex"
    sentinel_path = tmp_path / ".synlynk" / "sentinel.md"
    assert sentinel_path.exists()
    text = sentinel_path.read_text()
    assert "codex" in text
    assert "local oMLX unreachable" in text
    assert "DISPATCH_ROUTING_FALLBACK" in text


def test_low_capability_fallback_writes_sentinel_entry(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from synlynk import dispatch

    monkeypatch.setattr(dispatch, "_preflight_local_silent", lambda: True)
    monkeypatch.setattr(dispatch, "_get_local_capability_score", lambda task_type, db: 0.1)
    monkeypatch.setattr(
        dispatch, "_read_local_fallback", lambda config_path=".synlynk/config.json": "codex"
    )
    monkeypatch.setattr(
        dispatch, "_read_local_threshold", lambda config_path=".synlynk/config.json": 0.5
    )

    result = dispatch._resolve_dispatch_agent("auto", "implement", None)

    assert result == "codex"
    text = (tmp_path / ".synlynk" / "sentinel.md").read_text()
    assert "local capability score 0.10" in text
    assert "threshold 0.50" in text
    assert "codex" in text


def test_local_selection_does_not_write_fallback_sentinel(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from synlynk import dispatch

    monkeypatch.setattr(dispatch, "_preflight_local_silent", lambda: True)
    monkeypatch.setattr(dispatch, "_get_local_capability_score", lambda task_type, db: 0.8)
    monkeypatch.setattr(
        dispatch, "_read_local_threshold", lambda config_path=".synlynk/config.json": 0.5
    )

    result = dispatch._resolve_dispatch_agent("auto", "implement", None)

    assert result == "local"
    assert not (tmp_path / ".synlynk" / "sentinel.md").exists()
