import pytest

from synlynk.harness_adapters.request import DispatchRequest


def test_dispatch_request_holds_core_fields():
    request = DispatchRequest(
        agent="codex",
        task="implement task",
        permissions=["run:shell"],
    )

    assert request.agent == "codex"
    assert request.task == "implement task"
    assert request.permissions == ["run:shell"]


def test_dispatch_request_is_frozen():
    request = DispatchRequest(agent="codex", task="implement task")

    with pytest.raises((AttributeError, TypeError)):
        request.agent = "agy"
