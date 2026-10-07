"""Cross-adapter HarnessAdapter conformance suite (gh:#2062)."""

import hashlib
import inspect

import pytest

from synlynk.costs import extract_tokens
from synlynk.harness_adapters.agy import AgyAdapter
from synlynk.harness_adapters.base import FailureKind, HarnessAdapter
from synlynk.harness_adapters.claude import ClaudeAdapter
from synlynk.harness_adapters.codex import CodexAdapter
from synlynk.harness_adapters.grok import GrokAdapter
from synlynk.harness_adapters.local import LocalAdapter
from synlynk.jobs import _check_task_receipt

ALL_ADAPTERS = [ClaudeAdapter, CodexAdapter, AgyAdapter, GrokAdapter, LocalAdapter]

_SIGNATURE_DRIFT_XFAIL = pytest.mark.xfail(
    reason="gh:#2078 — signature drift, tracked separately",
    strict=True,
)
_LOCAL_RECEIPT_XFAIL = pytest.mark.xfail(
    reason="gh:#2079 — LocalAdapter.parse_output omits compatibility_evidence",
    strict=True,
)

SIGNATURE_ADAPTERS = [
    pytest.param(ClaudeAdapter, marks=_SIGNATURE_DRIFT_XFAIL),
    pytest.param(CodexAdapter, marks=_SIGNATURE_DRIFT_XFAIL),
    pytest.param(AgyAdapter, marks=_SIGNATURE_DRIFT_XFAIL),
    GrokAdapter,
    LocalAdapter,
]

RECEIPT_ADAPTERS = [
    ClaudeAdapter,
    CodexAdapter,
    AgyAdapter,
    GrokAdapter,
    pytest.param(LocalAdapter, marks=_LOCAL_RECEIPT_XFAIL),
]


@pytest.mark.parametrize("adapter_cls", ALL_ADAPTERS)
def test_implements_protocol_methods(adapter_cls):
    for name in (
        "build_cmd",
        "parse_output",
        "translate_permissions",
        "classify_failure",
        "resolve_model",
    ):
        assert hasattr(adapter_cls, name), f"{adapter_cls.__name__} missing {name}"


@pytest.mark.parametrize("adapter_cls", SIGNATURE_ADAPTERS)
def test_translate_permissions_signature_matches_protocol(adapter_cls):
    protocol_params = list(inspect.signature(HarnessAdapter.translate_permissions).parameters)
    adapter_params = list(inspect.signature(adapter_cls.translate_permissions).parameters)
    assert adapter_params == protocol_params, (
        f"{adapter_cls.__name__}.translate_permissions{tuple(adapter_params)} "
        f"does not match Protocol{tuple(protocol_params)}"
    )


@pytest.mark.parametrize("adapter_cls", RECEIPT_ADAPTERS)
def test_parse_output_extracts_receipt_marker(adapter_cls):
    adapter = adapter_cls()
    task_sha = hashlib.sha256(b"example task").hexdigest()
    raw_text = f"SYNLYNK_TASK_RECEIVED: {task_sha}\nsome other output\n"
    event = adapter.parse_output(raw_text)
    assert event.compatibility_evidence is not None
    assert event.compatibility_evidence.get("receipt") == task_sha
    assert _check_task_receipt(raw_text, task_sha) == "ok"


@pytest.mark.parametrize("adapter_cls", RECEIPT_ADAPTERS)
def test_parse_output_flags_missing_receipt_marker(adapter_cls):
    """A deliberately broken fixture (no receipt line) must be caught, not silently passed."""
    adapter = adapter_cls()
    task_sha = hashlib.sha256(b"example task").hexdigest()
    raw_text = "no receipt marker here\n"
    event = adapter.parse_output(raw_text)
    assert event.compatibility_evidence.get("receipt") is None
    assert _check_task_receipt(raw_text, task_sha) == "absent"


@pytest.mark.parametrize("adapter_cls", ALL_ADAPTERS)
def test_classify_failure_returns_known_failure_kind_or_none(adapter_cls):
    adapter = adapter_cls()
    result = adapter.classify_failure(1, "not signed in", "")
    assert result is None or isinstance(result, FailureKind)


def test_extract_tokens_recognizes_claude_format():
    output = '{"type":"result","usage":{"input_tokens":100,"output_tokens":50}}\n'
    result = extract_tokens(output, agent="claude")
    assert result.basis == "structured_output"
    assert result.input_tokens == 100
    assert result.output_tokens == 50


def test_extract_tokens_recognizes_codex_format():
    output = '{"type":"turn.completed","usage":{"input_tokens":100,"output_tokens":50}}\n'
    result = extract_tokens(output, agent="codex")
    assert result.basis == "structured_output"
    assert result.input_tokens == 100
    assert result.output_tokens == 50


def test_extract_tokens_recognizes_agy_format():
    output = '{"status":"SUCCESS","usage":{"input_tokens":100,"output_tokens":50}}\n'
    result = extract_tokens(output, agent="agy")
    assert result.basis == "structured_output"
    assert result.input_tokens == 100
    assert result.output_tokens == 50


def test_extract_tokens_recognizes_grok_format():
    output = '{"usage": {"input_tokens": 100, "output_tokens": 50}}\n'
    result = extract_tokens(output, agent="grok")
    assert result.basis == "structured_output"
    assert result.input_tokens == 100
    assert result.output_tokens == 50


def test_extract_tokens_recognizes_local_format():
    output = "Input tokens: 100\nOutput tokens: 50\n"
    result = extract_tokens(output, agent="local")
    assert result.basis == "regex_pair"
    assert result.input_tokens == 100
    assert result.output_tokens == 50
