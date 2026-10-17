import pytest

from synlynk.harness_adapters.local import LocalAdapter, PermissionEnforcementError
from synlynk.harness_adapters.request import DispatchRequest


def test_local_translate_permissions_raises_if_any_requested():
    adapter = LocalAdapter()
    with pytest.raises(PermissionEnforcementError):
        adapter.translate_permissions(["write:repo"], read_only=False)


def test_local_translate_permissions_empty_returns_empty():
    assert LocalAdapter().translate_permissions([], read_only=False) == []


def test_local_build_cmd_includes_dispatch_flags():
    cmd = LocalAdapter().build_cmd(DispatchRequest(agent="local", task="fix it"))
    assert "--no-auto-commits" in cmd


def test_local_parse_output_returns_event():
    parsed = LocalAdapter().parse_output("SYNLYNK_TASK_RECEIVED: abc123\nlocal output")
    assert parsed.raw_text.endswith("local output")
    assert parsed.compatibility_evidence["receipt"] == "abc123"


def test_local_classify_failure_returns_none():
    assert LocalAdapter().classify_failure(1, "unrelated error", "") is None


@pytest.mark.parametrize(
    ("output", "failure"),
    [
        ("401 unauthorized", "auth_expired"),
        ("model not found", "model_unavailable"),
        ("connection refused", "inventory_unavailable"),
        ("request timed out", "timeout"),
        ("malformed response", "malformed_response"),
        ("Aider error: failed", "aider_failure"),
        ("No changes made", "no_op"),
    ],
)
def test_local_classify_failure_is_structured(output, failure):
    result = LocalAdapter().classify_failure(1, output, "")
    assert result is not None
    assert result.value == failure


def test_local_resolve_model():
    assert LocalAdapter().resolve_model("fast", None)


def test_local_resolve_model_supports_hermes_tier():
    assert LocalAdapter().resolve_model("hermes", None) == "Hermes-3-Llama-3.1-8B"


def test_local_resolve_model_preserves_existing_local_tiers():
    adapter = LocalAdapter()
    assert adapter.resolve_model("fast", None) == "qwen2.5"
    assert adapter.resolve_model("reasoning", None) == "deepseek-r1"
