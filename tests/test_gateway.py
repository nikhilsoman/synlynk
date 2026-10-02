"""Tests for synlynk.gateway gateway probes and registry configuration."""

import json
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch


class TestReadGatewayConfig(unittest.TestCase):
    def _write_registry(self, content):
        directory = tempfile.mkdtemp()
        path = os.path.join(directory, "registry.json")
        with open(path, "w", encoding="utf-8") as registry_file:
            json.dump(content, registry_file)
        return path

    def test_returns_gateways_dict(self):
        path = self._write_registry({"gateways": {"openrouter": {"enabled": True}}})
        from synlynk.gateway import _read_gateway_config

        self.assertIn("openrouter", _read_gateway_config(path))

    def test_returns_empty_dict_when_no_gateways_key(self):
        path = self._write_registry({"products": {}})
        from synlynk.gateway import _read_gateway_config

        self.assertEqual(_read_gateway_config(path), {})

    def test_returns_empty_dict_on_missing_file(self):
        from synlynk.gateway import _read_gateway_config

        self.assertEqual(_read_gateway_config("/nonexistent/registry.json"), {})


class TestGatewayProbe(unittest.TestCase):
    REGISTRY = {
        "gateways": {
            "openrouter": {
                "enabled": True,
                "base_url": "https://openrouter.ai/api/v1",
                "api_key_env": "OPENROUTER_API_KEY",
                "models": [],
            }
        }
    }

    def _probe(self, registry_content, env=None, gateway=None, mock_response=None):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "registry.json")
            with open(path, "w", encoding="utf-8") as registry_file:
                json.dump(registry_content, registry_file)
            with patch.dict(os.environ, env or {}, clear=False):
                if mock_response is None:
                    from synlynk.gateway import cmd_gateway_probe

                    return cmd_gateway_probe(gateway=gateway, config_path=path)

                mock_response_object = MagicMock()
                mock_response_object.read.return_value = json.dumps(mock_response).encode()
                mock_response_object.__enter__ = lambda response: response
                mock_response_object.__exit__ = MagicMock(return_value=False)
                with patch("urllib.request.urlopen", return_value=mock_response_object):
                    from synlynk.gateway import cmd_gateway_probe

                    return cmd_gateway_probe(gateway=gateway, config_path=path)

    def test_returns_0_when_reachable(self):
        result = self._probe(
            self.REGISTRY,
            env={"OPENROUTER_API_KEY": "test-key"},
            mock_response={"data": [{"id": "model-a"}, {"id": "model-b"}]},
        )
        self.assertEqual(result, 0)

    def test_returns_1_when_api_key_missing(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(self._probe(self.REGISTRY, gateway="openrouter"), 1)

    def test_returns_0_when_gateway_disabled(self):
        registry = {
            "gateways": {
                "openrouter": {
                    "enabled": False,
                    "base_url": "https://x.ai",
                    "api_key_env": "X_KEY",
                    "models": [],
                }
            }
        }
        self.assertEqual(self._probe(registry), 0)

    def test_filters_by_gateway_name(self):
        registry = {
            "gateways": {
                "openrouter": {
                    "enabled": True,
                    "base_url": "https://or.ai/api/v1",
                    "api_key_env": "OR_KEY",
                    "models": [],
                },
                "other": {
                    "enabled": True,
                    "base_url": "https://other.ai/api/v1",
                    "api_key_env": "OTHER_KEY",
                    "models": [],
                },
            }
        }
        response = MagicMock()
        response.read.return_value = json.dumps({"data": [{"id": "m1"}]}).encode()
        response.__enter__ = lambda value: value
        response.__exit__ = MagicMock(return_value=False)
        with patch("urllib.request.urlopen", return_value=response) as urlopen:
            self.assertEqual(
                self._probe(registry, env={"OR_KEY": "k"}, gateway="openrouter"),
                0,
            )
        self.assertEqual(urlopen.call_count, 1)
