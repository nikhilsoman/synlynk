from synlynk.harness_adapters.legacy import LegacyAdapter
from synlynk.harness_adapters.request import DispatchRequest
from synlynk.harness_adapters.base import FailureKind


def test_legacy_adapter_translate_permissions_matches_existing_codex_logic():
    adapter = LegacyAdapter(agent="codex")
    flags = adapter.translate_permissions(["write:repo"], read_only=False)
    assert flags == ["-s", "workspace-write"]


def test_legacy_adapter_translate_permissions_matches_existing_grok_logic():
    adapter = LegacyAdapter(agent="grok")
    flags = adapter.translate_permissions(["write:repo"], read_only=False)
    assert flags == ["--always-approve", "--permission-mode", "bypassPermissions"]


def test_legacy_adapter_classify_failure_returns_none_by_default():
    adapter = LegacyAdapter(agent="codex")
    assert adapter.classify_failure(1, "some generic error", "some generic error") is None


def test_legacy_adapter_resolve_model_delegates_to_resolve_tier_model():
    adapter = LegacyAdapter(agent="grok")
    model = adapter.resolve_model(tier="standard", effort=None)
    assert isinstance(model, str) and model
