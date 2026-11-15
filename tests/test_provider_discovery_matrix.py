import io
import json
import os
import urllib.request
from unittest.mock import MagicMock, patch
import pytest
from synlynk.models import probe_local_runtimes


def mock_urlopen(req, timeout=1.5):
    url = req.full_url if hasattr(req, "full_url") else str(req)
    mock_resp = MagicMock()
    if "/api/tags" in url:
        data = {
            "models": [
                {"name": "llama3:latest", "model": "llama3:latest"},
                {"name": "qwen2.5-coder:7b", "model": "qwen2.5-coder:7b"},
            ]
        }
    elif "/models" in url:
        data = {
            "object": "list",
            "data": [
                {"id": "anthropic/claude-3-5-sonnet", "object": "model"},
                {"id": "meta-llama/llama-3-70b-instruct", "object": "model"},
            ],
        }
    else:
        raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)

    body = json.dumps(data).encode("utf-8")
    mock_resp.read.return_value = body
    mock_resp.__enter__.return_value = mock_resp
    return mock_resp


def test_ollama_discovery(monkeypatch):
    """Test auto-discovery of Ollama local tags endpoint."""
    monkeypatch.setenv("OLLAMA_HOST", "http://127.0.0.1:11434")
    with patch("urllib.request.urlopen", side_effect=mock_urlopen):
        specs = probe_local_runtimes(timeout=2.0)
    model_ids = {s.model_id for s in specs}
    assert "llama3:latest" in model_ids
    assert "qwen2.5-coder:7b" in model_ids


def test_litellm_openai_gateway_discovery(monkeypatch):
    """Test auto-discovery of LiteLLM / OpenAI compatible gateway models endpoint."""
    monkeypatch.setenv("OPENAI_BASE_URL", "http://127.0.0.1:4000/v1")
    monkeypatch.setenv("OLLAMA_HOST", "http://127.0.0.1:1")  # non-existent to test gateway specifically
    with patch("urllib.request.urlopen", side_effect=mock_urlopen):
        specs = probe_local_runtimes(timeout=2.0)
    model_ids = {s.model_id for s in specs}
    assert "anthropic/claude-3-5-sonnet" in model_ids
    assert "meta-llama/llama-3-70b-instruct" in model_ids

