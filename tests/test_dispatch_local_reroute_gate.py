import pytest

from synlynk.dispatch import dispatch_agent


def test_local_reroute_without_allow_reroute_fails_closed(monkeypatch):
    """When agent="local" resolves through the pipeline to something else,
    and --allow-reroute was not passed, dispatch must refuse rather than
    silently substitute a different harness."""
    class _FakeRequest:
        agent = "agy"  # pipeline rerouted away from "local"

        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    monkeypatch.setattr("synlynk.dispatch_pipeline.resolve", lambda request: _FakeRequest())
    monkeypatch.setattr("synlynk.dispatch_pipeline.authorize", lambda request: None)
    with pytest.raises(RuntimeError) as exc:
        dispatch_agent("local", "test task", allow_reroute=False, skip_preflight=True)
    assert "allow-reroute" in str(exc.value).lower() or "allow_reroute" in str(exc.value).lower()


def test_local_reroute_with_allow_reroute_proceeds(monkeypatch):
    class _FakeRequest:
        agent = "agy"

        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    monkeypatch.setattr("synlynk.dispatch_pipeline.resolve", lambda request: _FakeRequest())
    monkeypatch.setattr("synlynk.dispatch_pipeline.authorize", lambda request: None)
    # Should not raise for the reroute-gate reason (may still fail later for
    # unrelated environment reasons in a unit-test sandbox — only assert the
    # specific RuntimeError from the gate is absent).
    try:
        dispatch_agent("local", "test task", allow_reroute=True, skip_preflight=True)
    except RuntimeError as exc:
        assert "allow-reroute" not in str(exc).lower()
    except Exception:
        pass
