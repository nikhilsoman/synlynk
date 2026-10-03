import pytest

from synlynk.harness_adapters.base import DispatchEvent, FailureKind, HarnessAdapter
from synlynk.harness_adapters.registry import get_adapter, register_adapter


def test_failure_kind_has_expected_members():
    assert FailureKind.AUTH_EXPIRED.value == "auth_expired"
    assert FailureKind.QUOTA_EXHAUSTED.value == "quota_exhausted"
    assert FailureKind.SANDBOX_DENIED.value == "sandbox_denied"


def test_dispatch_event_is_a_plain_data_holder():
    event = DispatchEvent(raw_text="hello", failure=None)
    assert event.raw_text == "hello"
    assert event.failure is None


def test_registry_rejects_unknown_harness():
    with pytest.raises(KeyError):
        get_adapter("not-a-real-harness")


def test_registry_register_and_get_roundtrip():
    class FakeAdapter:
        def build_cmd(self, request):
            return ["fake"]

        def parse_output(self, raw_text):
            return DispatchEvent(raw_text=raw_text, failure=None)

        def translate_permissions(self, permissions, read_only):
            return []

        def classify_failure(self, exit_code, stderr, raw_text):
            return None

        def resolve_model(self, tier, effort):
            return "fake-model"

    register_adapter("fake-harness-for-test", FakeAdapter())
    assert get_adapter("fake-harness-for-test").build_cmd(None) == ["fake"]
