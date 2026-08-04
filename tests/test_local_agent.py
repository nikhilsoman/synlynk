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
            "--model", "openai/ornith-1.0-9b",
            "--edit-format", "whole",
            "--no-auto-lint", "--no-auto-test", "--map-tokens", "0",
        ])

    def test_returns_empty_list_when_config_missing(self):
        flags = local_agent._local_dispatch_model_flags(config_path="/nonexistent/local.json")
        self.assertEqual(flags, [])


class TestLocalDispatchModelFlagsProviderPrefix(unittest.TestCase):
    def test_model_flag_has_openai_provider_prefix(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "local.json")
            with open(path, "w") as f:
                json.dump({
                    "name": "local",
                    "endpoint": "http://127.0.0.1:8000",
                    "models": [{"id": "Ornith-1.0-9B-4bit", "pinned": True, "edit_format": "whole"}],
                    "hardware_tier": "16gb-default",
                }, f)
            flags = local_agent._local_dispatch_model_flags(path)
        self.assertIn("--model", flags)
        model_index = flags.index("--model")
        self.assertEqual(flags[model_index + 1], "openai/Ornith-1.0-9B-4bit")

    def test_doctor_roster_matching_unaffected_by_prefix(self):
        healthy_response = {"reachable": True, "available_models": ["Ornith-1.0-9B-4bit"]}
        with patch("synlynk.local_agent._health_check", return_value=healthy_response), \
             patch("synlynk.local_agent.shutil.which", return_value="/usr/local/bin/aider"), \
             patch("synlynk.local_agent._get_db"), \
             patch("synlynk.local_agent_seed.seed_local_capability_envelope"):
            with tempfile.TemporaryDirectory() as d:
                path = os.path.join(d, "local.json")
                with open(path, "w") as f:
                    json.dump({
                        "name": "local",
                        "endpoint": "http://127.0.0.1:8000",
                        "models": [{"id": "Ornith-1.0-9B-4bit", "pinned": True, "edit_format": "whole"}],
                        "hardware_tier": "16gb-default",
                    }, f)
                with patch("builtins.print") as mock_print:
                    result = local_agent.cmd_local_doctor(path)
        printed = " ".join(str(call.args[0]) for call in mock_print.call_args_list)
        self.assertEqual(result, 0)
        self.assertIn("Ornith-1.0-9B-4bit", printed)
        self.assertNotIn("Missing models", printed)


class TestLocalDispatchStarterTierGuardrails(unittest.TestCase):
    def test_includes_no_auto_lint(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "local.json")
            with open(path, "w") as f:
                json.dump({
                    "name": "local",
                    "endpoint": "http://127.0.0.1:8000",
                    "models": [
                        {"id": "Ornith-1.0-9B-4bit", "pinned": True, "edit_format": "diff"},
                    ],
                    "hardware_tier": "16gb-default",
                }, f)
            flags = local_agent._local_dispatch_model_flags(path)
        self.assertIn("--no-auto-lint", flags)

    def test_includes_no_auto_test(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "local.json")
            with open(path, "w") as f:
                json.dump({
                    "name": "local",
                    "endpoint": "http://127.0.0.1:8000",
                    "models": [
                        {"id": "Ornith-1.0-9B-4bit", "pinned": True, "edit_format": "diff"},
                    ],
                    "hardware_tier": "16gb-default",
                }, f)
            flags = local_agent._local_dispatch_model_flags(path)
        self.assertIn("--no-auto-test", flags)

    def test_caps_map_tokens_to_zero(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "local.json")
            with open(path, "w") as f:
                json.dump({
                    "name": "local",
                    "endpoint": "http://127.0.0.1:8000",
                    "models": [
                        {"id": "Ornith-1.0-9B-4bit", "pinned": True, "edit_format": "diff"},
                    ],
                    "hardware_tier": "16gb-default",
                }, f)
            flags = local_agent._local_dispatch_model_flags(path)
        map_tokens_index = flags.index("--map-tokens")
        self.assertEqual(flags[map_tokens_index + 1], "0")

    def test_never_includes_architect_flag(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "local.json")
            with open(path, "w") as f:
                json.dump({
                    "name": "local",
                    "endpoint": "http://127.0.0.1:8000",
                    "models": [
                        {"id": "Ornith-1.0-9B-4bit", "pinned": True, "edit_format": "diff"},
                    ],
                    "hardware_tier": "16gb-default",
                }, f)
            flags = local_agent._local_dispatch_model_flags(path)
        self.assertNotIn("--architect", flags)


class TestCmdLocalDoctorAiderCheck(unittest.TestCase):
    def test_reports_missing_aider_even_when_omlx_healthy(self):
        healthy_response = {
            "reachable": True,
            "available_models": ["ornith-1.0-9b", "qwen-coder", "gemma-coder"],
        }
        with patch("synlynk.local_agent._health_check", return_value=healthy_response), \
             patch("synlynk.local_agent.shutil.which", return_value=None), \
             patch("synlynk.local_agent._get_db"), \
             patch("synlynk.local_agent_seed.seed_local_capability_envelope"):
            with tempfile.TemporaryDirectory() as d:
                path = os.path.join(d, "local.json")
                with open(path, "w") as f:
                    json.dump({
                        "name": "local",
                        "endpoint": "http://127.0.0.1:8080",
                        "models": [
                            {"id": "ornith-1.0-9b", "pinned": True, "edit_format": "whole"},
                            {"id": "qwen-coder", "pinned": False, "edit_format": "whole"},
                            {"id": "gemma-coder", "pinned": False, "edit_format": "diff"},
                        ],
                        "hardware_tier": "16gb-default",
                    }, f)
                result = local_agent.cmd_local_doctor(path)
        self.assertEqual(result, 1)

    def test_healthy_when_aider_and_omlx_both_present(self):
        healthy_response = {
            "reachable": True,
            "available_models": ["ornith-1.0-9b", "qwen-coder", "gemma-coder"],
        }
        with patch("synlynk.local_agent._health_check", return_value=healthy_response), \
             patch("synlynk.local_agent.shutil.which", return_value="/usr/local/bin/aider"), \
             patch("synlynk.local_agent._get_db"), \
             patch("synlynk.local_agent_seed.seed_local_capability_envelope"):
            with tempfile.TemporaryDirectory() as d:
                path = os.path.join(d, "local.json")
                with open(path, "w") as f:
                    json.dump({
                        "name": "local",
                        "endpoint": "http://127.0.0.1:8080",
                        "models": [
                            {"id": "ornith-1.0-9b", "pinned": True, "edit_format": "whole"},
                            {"id": "qwen-coder", "pinned": False, "edit_format": "whole"},
                            {"id": "gemma-coder", "pinned": False, "edit_format": "diff"},
                        ],
                        "hardware_tier": "16gb-default",
                    }, f)
                result = local_agent.cmd_local_doctor(path)
        self.assertEqual(result, 0)


class TestHealthCheckApiKey(unittest.TestCase):
    def test_sends_authorization_header_when_api_key_provided(self):
        captured = {}

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return b'{"data": [{"id": "Ornith-1.0-9B-4bit"}]}'

        def fake_urlopen(req, timeout=None):
            captured["headers"] = dict(req.header_items())
            return FakeResponse()

        with patch("synlynk.local_agent.urllib.request.urlopen", side_effect=fake_urlopen):
            result = local_agent._health_check("http://127.0.0.1:8000", api_key="sk-test-123")
        self.assertTrue(result["reachable"])
        self.assertEqual(captured["headers"].get("Authorization"), "Bearer sk-test-123")

    def test_no_authorization_header_when_api_key_absent(self):
        captured = {}

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return b'{"data": []}'

        def fake_urlopen(req, timeout=None):
            captured["headers"] = dict(req.header_items())
            return FakeResponse()

        with patch("synlynk.local_agent.urllib.request.urlopen", side_effect=fake_urlopen):
            local_agent._health_check("http://127.0.0.1:8000")
        self.assertNotIn("Authorization", captured["headers"])


class TestCmdLocalDoctorApiKey(unittest.TestCase):
    def test_reads_openai_api_key_env_and_passes_to_health_check(self):
        healthy_response = {"reachable": True, "available_models": ["Ornith-1.0-9B-4bit"]}
        with patch("synlynk.local_agent._health_check", return_value=healthy_response) as mock_check, \
             patch("synlynk.local_agent.shutil.which", return_value="/usr/local/bin/aider"), \
             patch("synlynk.local_agent._get_db"), \
             patch("synlynk.local_agent_seed.seed_local_capability_envelope"), \
             patch.dict(os.environ, {"OPENAI_API_KEY": "sk-env-key"}):
            with tempfile.TemporaryDirectory() as d:
                path = os.path.join(d, "local.json")
                with open(path, "w") as f:
                    json.dump({
                        "name": "local",
                        "endpoint": "http://127.0.0.1:8000",
                        "models": [{"id": "Ornith-1.0-9B-4bit", "pinned": True, "edit_format": "whole"}],
                        "hardware_tier": "16gb-default",
                    }, f)
                local_agent.cmd_local_doctor(path)
        mock_check.assert_called_once_with("http://127.0.0.1:8000", api_key="sk-env-key")

    def test_401_reports_auth_hint_not_unreachable_hint(self):
        unauthorized_response = {"reachable": False, "error": "HTTP Error 401: Unauthorized"}
        with patch("synlynk.local_agent._health_check", return_value=unauthorized_response), \
             patch.dict(os.environ, {}, clear=False):
            os.environ.pop("OPENAI_API_KEY", None)
            with tempfile.TemporaryDirectory() as d:
                path = os.path.join(d, "local.json")
                with open(path, "w") as f:
                    json.dump({
                        "name": "local",
                        "endpoint": "http://127.0.0.1:8000",
                        "models": [{"id": "Ornith-1.0-9B-4bit", "pinned": True, "edit_format": "whole"}],
                        "hardware_tier": "16gb-default",
                    }, f)
                with patch("builtins.print") as mock_print:
                    result = local_agent.cmd_local_doctor(path)
        printed = " ".join(str(call.args[0]) for call in mock_print.call_args_list)
        self.assertEqual(result, 1)
        self.assertIn("401", printed)
        self.assertIn("OPENAI_API_KEY", printed)
        self.assertNotIn("Start it with: omlx serve", printed)
