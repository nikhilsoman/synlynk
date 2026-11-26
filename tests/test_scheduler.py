def test_run_maintainer_triage_pass_calls_wake_cycle(monkeypatch):
    from synlynk import scheduler

    called = {}

    def fake_wake_cycle(**kwargs):
        called["ran"] = True
        return {"sentinel_triage": {"mode": "dry_run"}}

    monkeypatch.setattr("synlynk.maintainer.run_maintainer_wake_cycle", fake_wake_cycle)
    scheduler._run_maintainer_triage_pass()
    assert called.get("ran") is True
