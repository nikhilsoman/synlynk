import json
from unittest.mock import Mock
from urllib.error import HTTPError

import pytest

from synlynk.local_credentials import LocalCredentialStore
from synlynk.local_lifecycle import (
    LIFECYCLE_MODEL_ID,
    LifecycleError,
    OmlxClient,
    HostMemorySnapshot,
    check_memory_admission,
    parse_memory_pressure,
    parse_swap_usage,
    parse_vm_stat,
)


class Credentials:
    def get(self):
        return "sk-do-not-leak"


def test_model_api_uses_authenticated_model_specific_paths(monkeypatch):
    seen = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b'{"data":[{"id":"Ornith-1.0-9B-4bit"}]}'

    def fake_urlopen(request, timeout=None):
        seen.append((request.full_url, request.get_method(), request.get_header("Authorization")))
        return Response()

    monkeypatch.setattr("synlynk.local_lifecycle.urllib.request.urlopen", fake_urlopen)
    client = OmlxClient("http://127.0.0.1:8000", Credentials())
    assert client.list_models() == [LIFECYCLE_MODEL_ID]
    client.load_model(LIFECYCLE_MODEL_ID)
    client.unload_model(LIFECYCLE_MODEL_ID)
    assert seen == [
        ("http://127.0.0.1:8000/v1/models", "GET", "Bearer sk-do-not-leak"),
        ("http://127.0.0.1:8000/v1/models/Ornith-1.0-9B-4bit/load", "POST", "Bearer sk-do-not-leak"),
        ("http://127.0.0.1:8000/v1/models/Ornith-1.0-9B-4bit/unload", "POST", "Bearer sk-do-not-leak"),
    ]


@pytest.mark.parametrize("status,reason", [(401, "authentication_failed"), (404, "unsupported_load_contract"), (507, "insufficient_memory")])
def test_api_errors_are_classified_without_echoing_credentials(monkeypatch, status, reason):
    def fail(*args, **kwargs):
        raise HTTPError("http://127.0.0.1:8000", status, "sk-do-not-leak rejected", {}, None)

    monkeypatch.setattr("synlynk.local_lifecycle.urllib.request.urlopen", fail)
    client = OmlxClient("http://127.0.0.1:8000", Credentials())
    with pytest.raises(LifecycleError) as error:
        client.load_model(LIFECYCLE_MODEL_ID)
    assert error.value.reason_code == reason
    assert "sk-do-not-leak" not in str(error.value)


def test_model_allowlist_rejects_everything_except_ornith():
    client = OmlxClient("http://127.0.0.1:8000", Credentials())
    with pytest.raises(LifecycleError, match="approved Ornith model"):
        client.load_model("Qwen2.5-Coder-14B-Instruct-4bit")


def test_version_validation_accepts_only_verified_omlx_053():
    client = OmlxClient("http://127.0.0.1:8000", Credentials())
    assert client.validate_version("0.5.3") == "0.5.3"
    with pytest.raises(LifecycleError) as error:
        client.validate_version("0.6.0")
    assert error.value.reason_code == "unsupported_omlx_version"


def test_omlx_subprocess_does_not_receive_api_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-do-not-leak")
    seen = {}

    def run(args, **kwargs):
        seen.update(args=args, **kwargs)
        return Mock(returncode=0, stdout="0.5.3", stderr="")

    monkeypatch.setattr("synlynk.local_lifecycle.subprocess.run", run)
    client = OmlxClient("http://127.0.0.1:8000", Credentials())
    client.installed_version()
    assert "sk-do-not-leak" not in repr(seen["args"])
    assert "sk-do-not-leak" not in repr(seen["env"])


def test_memory_output_parsers_and_gate_fail_closed():
    vm_stat = "Mach Virtual Memory Statistics: (page size of 16384 bytes)\nPages free: 100.\nPages inactive: 200.\nPages speculative: 10.\nPages purgeable: 5.\n"
    assert parse_vm_stat(vm_stat) == 315 * 16384
    assert parse_memory_pressure("System-wide memory free percentage: 45%") == "normal"
    assert parse_memory_pressure("System-wide memory free percentage: 4%") == "warning"
    assert parse_swap_usage("vm.swapusage: total = 2048.00M used = 1024.00M free = 1024.00M") == 1024 * 1024**2
    baseline = HostMemorySnapshot(24 * 1024**3, 9 * 1024**3, "normal", 100 * 1024**2)
    latest = HostMemorySnapshot(24 * 1024**3, 8 * 1024**3, "normal", 300 * 1024**2)
    check_memory_admission(baseline, latest)
    with pytest.raises(LifecycleError) as error:
        check_memory_admission(baseline, HostMemorySnapshot(24 * 1024**3, 7 * 1024**3, "normal", 100 * 1024**2))
    assert error.value.reason_code == "insufficient_memory"


def test_memory_gate_rejects_swap_growth_and_unavailable_signals():
    before = HostMemorySnapshot(24 * 1024**3, 9 * 1024**3, "normal", 100 * 1024**2)
    with pytest.raises(LifecycleError) as error:
        check_memory_admission(before, HostMemorySnapshot(24 * 1024**3, 9 * 1024**3, "normal", 357 * 1024**2))
    assert error.value.reason_code == "memory_pressure"
    with pytest.raises(LifecycleError):
        check_memory_admission(before, None)
