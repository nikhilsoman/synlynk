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
    parsed = LocalAdapter().parse_output("local output")
    assert parsed.raw_text == "local output"
    assert parsed.failure is None


def test_local_classify_failure_returns_none():
    assert LocalAdapter().classify_failure(1, "unrelated error", "") is None


def test_local_resolve_model():
    assert LocalAdapter().resolve_model("fast", None)


def test_local_resolve_model_supports_hermes_tier():
    assert LocalAdapter().resolve_model("hermes", None) == "Hermes-3-Llama-3.1-8B"


def test_local_resolve_model_preserves_existing_local_tiers():
    adapter = LocalAdapter()
    assert adapter.resolve_model("fast", None) == "qwen2.5"
    assert adapter.resolve_model("reasoning", None) == "deepseek-r1"
