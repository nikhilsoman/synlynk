import json
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from synlynk import local_agent


class TestLoadLocalConfig(unittest.TestCase):
    def test_loads_valid_config(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "local.json")
            with open(path, "w") as f:
                json.dump({
                    "name": "local",
                    "endpoint": "http://127.0.0.1:8080",
                    "models": [
                        {"id": "ornith-1.0-9b", "pinned": True, "edit_format": "whole"},
                        {"id": "qwen-coder", "pinned": False, "edit_format": "whole"},
                    ],
                    "hardware_tier": "16gb-default",
                }, f)
            config = local_agent._load_local_config(path)
        self.assertEqual(config["endpoint"], "http://127.0.0.1:8080")
        self.assertEqual(len(config["models"]), 2)

    def test_missing_config_raises_clear_error(self):
        with self.assertRaises(FileNotFoundError):
            local_agent._load_local_config("/nonexistent/local.json")


class TestPinnedModel(unittest.TestCase):
    def test_returns_pinned_model(self):
        config = {"models": [
            {"id": "a", "pinned": False, "edit_format": "diff"},
            {"id": "b", "pinned": True, "edit_format": "whole"},
        ]}
        self.assertEqual(local_agent._pinned_model(config), "b")

    def test_falls_back_to_first_model_when_none_pinned(self):
        config = {"models": [
            {"id": "a", "pinned": False, "edit_format": "diff"},
            {"id": "b", "pinned": False, "edit_format": "whole"},
        ]}
        self.assertEqual(local_agent._pinned_model(config), "a")


class TestHealthCheck(unittest.TestCase):
    """oMLX's OpenAI-compatible /v1/models endpoint."""

    @patch("synlynk.local_agent.urllib.request.urlopen")
    def test_health_check_ok(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(
            {"data": [{"id": "ornith-1.0-9b"}, {"id": "qwen-coder"}]}
        ).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_resp
        result = local_agent._health_check("http://127.0.0.1:8080")
        self.assertTrue(result["reachable"])
        self.assertIn("ornith-1.0-9b", result["available_models"])

    @patch("synlynk.local_agent.urllib.request.urlopen")
    def test_health_check_unreachable(self, mock_urlopen):
        import urllib.error

        mock_urlopen.side_effect = urllib.error.URLError("connection refused")
        result = local_agent._health_check("http://127.0.0.1:8080")
        self.assertFalse(result["reachable"])
        self.assertIn("connection refused", result["error"])


class TestLocalDispatchModelFlags(unittest.TestCase):
    def test_builds_openai_base_model_and_edit_format_flags(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "local.json")
            with open(path, "w") as f:
                json.dump({
                    "endpoint": "http://127.0.0.1:8080",
                    "models": [
                        {"id": "ornith-1.0-9b", "pinned": True, "edit_format": "whole"},
                        {"id": "gemma-coder", "pinned": False, "edit_format": "diff"},
                    ],
                }, f)
            flags = local_agent._local_dispatch_model_flags(config_path=path)
        self.assertEqual(flags, [
            "--openai-api-base", "http://127.0.0.1:8080/v1",
            "--model", "ornith-1.0-9b",
            "--edit-format", "whole",
        ])

    def test_returns_empty_list_when_config_missing(self):
        flags = local_agent._local_dispatch_model_flags(config_path="/nonexistent/local.json")
        self.assertEqual(flags, [])
