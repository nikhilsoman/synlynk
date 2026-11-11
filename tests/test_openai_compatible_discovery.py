import json
import urllib.request
import pytest
from unittest.mock import patch, MagicMock

from synlynk.models import probe_local_runtimes, EntitlementTier


def test_probe_local_runtimes_dgx_spark_openai_compatible(monkeypatch):
    """Test discovery of models served from DGX Spark / vLLM via OPENAI_BASE_URL."""
    monkeypatch.setenv("OPENAI_BASE_URL", "http://dgx-spark.local:8000/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "test-dgx-key")
    # Point default ollama/omlx elsewhere to isolate
    monkeypatch.setenv("OLLAMA_HOST", "http://127.0.0.1:99999")
    monkeypatch.setenv("OMLX_BASE_URL", "http://127.0.0.1:99998")

    fake_openai_response = {
        "object": "list",
        "data": [
            {"id": "deepseek-ai/DeepSeek-R1", "object": "model", "owned_by": "vllm"},
            {"id": "meta-llama/Llama-3.3-70B-Instruct", "object": "model", "owned_by": "vllm"}
        ]
    }

    class MockResponse:
        def __init__(self, data):
            self.data = json.dumps(data).encode("utf-8")
        def read(self):
            return self.data
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass

    def mock_urlopen(req, timeout=1.5):
        url = req.full_url if hasattr(req, "full_url") else req
        headers = getattr(req, "headers", {})
        if "dgx-spark.local:8000/v1/models" in url:
            assert headers.get("Authorization") == "Bearer test-dgx-key"
            return MockResponse(fake_openai_response)
        raise OSError("Connection refused")

    with patch("urllib.request.urlopen", side_effect=mock_urlopen):
        specs = probe_local_runtimes()

    model_ids = [m.model_id for m in specs]
    assert "deepseek-ai/DeepSeek-R1" in model_ids
    assert "meta-llama/Llama-3.3-70B-Instruct" in model_ids

    spec_map = {m.model_id: m for m in specs}
    ds = spec_map["deepseek-ai/DeepSeek-R1"]
    assert ds.locality == "on_device_local"
    assert ds.entitlement_tier == EntitlementTier.ZERO_COST_LOCAL
    assert ds.discovery_source == "openai_gateway:http://dgx-spark.local:8000/v1/models"


def test_probe_local_runtimes_vllm_env_var(monkeypatch):
    """Test discovery via VLLM_BASE_URL without trailing /v1."""
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.setenv("VLLM_BASE_URL", "http://localhost:8000")
    monkeypatch.setenv("OLLAMA_HOST", "http://127.0.0.1:99999")
    monkeypatch.setenv("OMLX_BASE_URL", "http://127.0.0.1:99998")

    fake_vllm_response = {
        "object": "list",
        "data": [
            {"id": "Qwen/Qwen2.5-Coder-32B-Instruct", "object": "model"}
        ]
    }

    class MockResponse:
        def read(self):
            return json.dumps(fake_vllm_response).encode("utf-8")
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass

    with patch("urllib.request.urlopen", return_value=MockResponse()):
        specs = probe_local_runtimes()

    model_ids = [m.model_id for m in specs]
    assert "Qwen/Qwen2.5-Coder-32B-Instruct" in model_ids
    spec = next(m for m in specs if m.model_id == "Qwen/Qwen2.5-Coder-32B-Instruct")
    assert spec.discovery_source == "vllm:http://localhost:8000/models"


def test_probe_local_runtimes_unreachable_graceful(monkeypatch):
    """Test that when gateway URLs are unreachable, probe does not crash and returns empty/cached."""
    monkeypatch.setenv("OPENAI_BASE_URL", "http://nonexistent.local:9999/v1")
    monkeypatch.setenv("OLLAMA_HOST", "http://127.0.0.1:99999")
    monkeypatch.setenv("OMLX_BASE_URL", "http://127.0.0.1:99998")

    def mock_urlopen_fail(req, timeout=1.5):
        raise OSError("DNS lookup failed")

    with patch("urllib.request.urlopen", side_effect=mock_urlopen_fail):
        specs = probe_local_runtimes()

    assert isinstance(specs, list)
