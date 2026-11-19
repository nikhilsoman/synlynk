import pytest

from synlynk.dispatch import dispatch_agent


def test_local_reroute_without_allow_reroute_fails_closed(monkeypatch):
    """A local dispatch must not silently switch to another harness."""
    class _FakeRequest:
        agent = "agy"

    monkeypatch.setattr(
        "synlynk.dispatch_pipeline.resolve", lambda request: _FakeRequest()
    )
    monkeypatch.setattr("synlynk.dispatch_pipeline.authorize", lambda request: None)

    with pytest.raises(RuntimeError, match="allow-reroute"):
        dispatch_agent("local", "test task", allow_reroute=False, skip_preflight=True)


def test_local_reroute_with_allow_reroute_proceeds(monkeypatch):
    class _FakeRequest:
        agent = "agy"

    monkeypatch.setattr(
        "synlynk.dispatch_pipeline.resolve", lambda request: _FakeRequest()
    )
    monkeypatch.setattr("synlynk.dispatch_pipeline.authorize", lambda request: None)

    try:
        dispatch_agent("local", "test task", allow_reroute=True, skip_preflight=True)
    except Exception as exc:
        assert "allow-reroute" not in str(exc).lower()


def test_dispatch_parser_accepts_allow_reroute():
    from synlynk.cli import build_parser

    args = build_parser().parse_args(
        ["dispatch", "local", "--task", "test task", "--allow-reroute"]
    )

    assert args.allow_reroute is True
