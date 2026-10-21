import json
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from synlynk import local_agent


class TestLocalAgentConfigEditFormat(unittest.TestCase):
    def test_active_roster_pins_ornith_and_keeps_qwen_benchmark_only(self):
        repo_root = Path(__file__).resolve().parents[1]
        config_path = repo_root / ".agents" / "local.json"
        if not config_path.is_file():
            self.skipTest("local policy is omitted from this sparse worktree; full-checkout CI covers it")
        with open(config_path) as f:
            config = json.load(f)
        self.assertEqual(config["pinned_model"], "Ornith-1.0-9B-4bit")
        ornith = next(m for m in config["models"] if m["id"] == "Ornith-1.0-9B-4bit")
        self.assertEqual(ornith["edit_format"], "diff")
        qwen = next(
            m for m in config["models"] if m["id"] == "Qwen2.5-Coder-14B-Instruct-4bit"
        )
        self.assertFalse(qwen["dispatch_eligible"])
        self.assertEqual(qwen["qualification"], "benchmark-only")
        self.assertNotIn("Qwen3.6-27B-4bit", [m["id"] for m in config["models"]])
        self.assertNotIn("Ternary-Bonsai-2-27B-mlx-2bit", [m["id"] for m in config["models"]])


class TestPrismMlCheck(unittest.TestCase):
    def test_returns_true_when_prism_ml_importable(self):
        with patch("importlib.util.find_spec", return_value=object()):
            self.assertTrue(local_agent._check_prism_ml_available())

    def test_returns_false_when_prism_ml_missing(self):
        with patch("importlib.util.find_spec", return_value=None):
            self.assertFalse(local_agent._check_prism_ml_available())


class TestDetectHardwareTier(unittest.TestCase):
    def _run_with_ram(self, ram_bytes):
        with patch("subprocess.check_output", return_value=str(ram_bytes).encode()):
            with patch("sys.platform", "darwin"):
                return local_agent._detect_hardware_tier()

    def test_under_12gb_returns_8gb_light(self):
        self.assertEqual(self._run_with_ram(8 * 1024**3), "8gb-light")

    def test_16gb_returns_16gb_default(self):
        self.assertEqual(self._run_with_ram(16 * 1024**3), "16gb-default")

    def test_24gb_is_not_mislabeled_as_32gb_pro(self):
        self.assertEqual(self._run_with_ram(24 * 1024**3), "16gb-default")

    def test_32gb_returns_32gb_pro(self):
        self.assertEqual(self._run_with_ram(32 * 1024**3), "32gb-pro")

    def test_64gb_returns_64gb_fleet(self):
        self.assertEqual(self._run_with_ram(64 * 1024**3), "64gb-fleet")

    def test_linux_reads_meminfo(self):
        meminfo = "MemTotal:       25165824 kB\nMemFree: 1000 kB\n"
        with patch("builtins.open", unittest.mock.mock_open(read_data=meminfo)):
            with patch("sys.platform", "linux"):
                result = local_agent._detect_hardware_tier()
        self.assertEqual(result, "16gb-default")


class TestSelectModelForTier(unittest.TestCase):
    CONFIG = {
        "models": [
            {
                "id": "Ornith-1.0-9B-4bit",
                "edit_format": "diff",
                "tier": ["8gb-light", "16gb-default", "32gb-pro", "64gb-fleet"],
            },
            {
                "id": "Qwen2.5-Coder-14B-Instruct-4bit",
                "edit_format": "whole",
                "dispatch_eligible": False,
                "tier": ["64gb-fleet"],
            },
        ]
    }

    def test_64gb_fleet_falls_back_to_ornith_when_only_benchmark_model_matches(self):
        result = local_agent._select_model_for_tier("64gb-fleet", self.CONFIG)
        self.assertEqual(result, "Ornith-1.0-9B-4bit")

    def test_8gb_light_returns_ornith(self):
        result = local_agent._select_model_for_tier("8gb-light", self.CONFIG)
        self.assertEqual(result, "Ornith-1.0-9B-4bit")


class TestNewRosterSchema(unittest.TestCase):
    def test_pinned_model_top_level_key_used_when_present(self):
        config = {"models": [{"id": "a", "pinned": False}], "pinned_model": "a"}
        self.assertEqual(local_agent._pinned_model(config), "a")

    def test_falls_back_to_model_pinned_field_when_top_level_absent(self):
        config = {"models": [{"id": "a", "pinned": True}]}
        self.assertEqual(local_agent._pinned_model(config), "a")

    def test_ignores_benchmark_only_pinned_model(self):
        config = {
            "pinned_model": "qwen",
            "models": [
                {"id": "ornith", "pinned": True},
                {"id": "qwen", "dispatch_eligible": False},
            ],
        }
        self.assertEqual(local_agent._pinned_model(config), "ornith")

    def test_refuses_dispatch_flags_when_no_model_is_eligible(self):
        config = {
            "endpoint": "http://127.0.0.1:8000",
            "models": [{"id": "qwen", "dispatch_eligible": False}],
            "pinned_model": "qwen",
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config, f)
            path = f.name
        try:
            with self.assertRaisesRegex(ValueError, "no dispatch-eligible models"):
                local_agent._local_dispatch_model_flags(path)
        finally:
            os.unlink(path)

    def test_bonsai_refused_when_prism_ml_absent_without_silent_fallback(self):
        config = {
            "endpoint": "http://127.0.0.1:8000",
            "pinned_model": "Ternary-Bonsai-2-27B-mlx-2bit",
            "models": [
                {"id": "Ornith-1.0-9B-4bit", "edit_format": "diff"},
                {"id": "Ternary-Bonsai-2-27B-mlx-2bit", "edit_format": "diff", "loader": "prism-ml"},
            ],
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config, f)
            path = f.name
        try:
            with patch("importlib.util.find_spec", return_value=None):
                with self.assertRaisesRegex(ValueError, "refusing to substitute"):
                    local_agent._local_dispatch_model_flags(config_path=path)
        finally:
            os.unlink(path)


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


class TestEffectiveLocalModelResolution(unittest.TestCase):
    def _policy_path(self):
        handle = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        json.dump(
            {
                "endpoint": "http://127.0.0.1:8000",
                "pinned_model": "ornith",
                "models": [
                    {"id": "ornith", "pinned": True, "edit_format": "diff"},
                    {"id": "qwen", "dispatch_eligible": False, "edit_format": "whole"},
                ],
            },
            handle,
        )
        handle.close()
        return handle.name

    def test_reports_effective_model_and_all_three_source_layers(self):
        path = self._policy_path()
        try:
            result = local_agent.resolve_effective_local_model(
                config_path=path,
                live_model_ids=["ornith", "qwen", "gemma"],
                catalog={
                    "models": [
                        {"model_id": "ornith", "harness": "local"},
                        {"model_id": "gemma", "harness": "local"},
                    ]
                },
            )
        finally:
            os.unlink(path)
        self.assertEqual(result["effective_model"], "ornith")
        self.assertEqual(result["edit_format"], "diff")
        self.assertEqual(result["health"], "available")
        self.assertEqual(result["sources"], {
            "policy": "ornith", "catalog": "ornith", "live_inventory": "ornith"
        })
        self.assertEqual(result["drift"]["live_but_unapproved"], ["gemma", "qwen"])
        self.assertEqual(result["drift"]["catalog_only"], ["gemma"])

    def test_rejects_benchmark_only_model_for_dispatch_selection(self):
        path = self._policy_path()
        try:
            with self.assertRaisesRegex(ValueError, "not dispatch-approved"):
                local_agent.resolve_effective_local_model(path, requested_model="qwen")
        finally:
            os.unlink(path)

    def test_selects_exact_approved_live_model_and_preserves_other_layers(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as handle:
            json.dump({
                "endpoint": "http://127.0.0.1:8000",
                "pinned_model": "ornith",
                "models": [
                    {"id": "ornith", "pinned": True, "edit_format": "diff"},
                    {"id": "other", "dispatch_eligible": True, "edit_format": "whole"},
                ],
            }, handle)
            path = handle.name
        try:
            result = local_agent.resolve_effective_local_model(
                config_path=path,
                requested_model="other",
                live_model_ids=["ornith", "other", "unapproved"],
                catalog={"models": [{"model_id": "other", "harness": "local"}]},
            )
        finally:
            os.unlink(path)

        self.assertEqual(result["requested_model"], "other")
        self.assertEqual(result["effective_model"], "other")
        self.assertEqual(result["edit_format"], "whole")
        self.assertEqual(result["sources"], {
            "policy": "other", "catalog": "other", "live_inventory": "other"
        })
        self.assertEqual(result["drift"]["live_but_unapproved"], ["unapproved"])
        self.assertEqual(result["catalog_model"]["model_id"], "other")

    def test_rejects_policy_model_absent_from_live_inventory_without_fallback(self):
        path = self._policy_path()
        try:
            with self.assertRaisesRegex(ValueError, "not currently served.*Start oMLX"):
                local_agent.resolve_effective_local_model(
                    config_path=path, live_model_ids=["qwen-coder"]
                )
        finally:
            os.unlink(path)

    @patch("synlynk.local_agent._health_check")
    def test_requires_healthy_live_inventory_for_production_resolution(self, mock_health):
        path = self._policy_path()
        mock_health.return_value = {
            "reachable": True,
            "status": "healthy",
            "available_models": ["ornith"],
        }
        try:
            result = local_agent.resolve_effective_local_model(
                config_path=path, require_live_inventory=True
            )
        finally:
            os.unlink(path)
        self.assertEqual(result["inventory_status"], "healthy")
        self.assertEqual(result["health"], "available")

    @patch("synlynk.local_agent._health_check")
    def test_auth_failure_is_actionable_and_does_not_leak_api_key(self, mock_health):
        path = self._policy_path()
        mock_health.return_value = {
            "reachable": False, "status": "unauthenticated", "error": "HTTP 401 Unauthorized"
        }
        try:
            with self.assertRaisesRegex(ValueError, "local credentials import") as raised:
                local_agent.resolve_effective_local_model(
                    config_path=path,
                    require_live_inventory=True,
                    api_key="never-print-this-secret",
                )
        finally:
            os.unlink(path)
        self.assertNotIn("never-print-this-secret", str(raised.exception))


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
        self.assertEqual(result["status"], "healthy")
        self.assertIn("ornith-1.0-9b", result["available_models"])

    @patch("synlynk.local_agent.urllib.request.urlopen")
    def test_health_check_unreachable(self, mock_urlopen):
        import urllib.error

        mock_urlopen.side_effect = urllib.error.URLError("connection refused")
        result = local_agent._health_check("http://127.0.0.1:8080")
        self.assertFalse(result["reachable"])
        self.assertEqual(result["status"], "endpoint_unavailable")
        self.assertIn("connection refused", result["error"])

    @patch("synlynk.local_agent.urllib.request.urlopen")
    def test_health_check_rejects_malformed_inventory(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"models": [{"id": "ornith"}]}).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        result = local_agent._health_check("http://127.0.0.1:8080")

        self.assertFalse(result["reachable"])
        self.assertEqual(result["status"], "malformed_inventory")

    @patch("synlynk.local_agent.urllib.request.urlopen")
    def test_health_check_classifies_unauthenticated_without_echoing_key(self, mock_urlopen):
        import urllib.error

        mock_urlopen.side_effect = urllib.error.HTTPError(
            "http://127.0.0.1:8080/v1/models", 401, "Unauthorized", {}, None
        )
        result = local_agent._health_check(
            "http://127.0.0.1:8080", api_key="never-print-this-secret"
        )

        self.assertFalse(result["reachable"])
        self.assertEqual(result["status"], "unauthenticated")
        self.assertNotIn("never-print-this-secret", json.dumps(result))

    @patch("synlynk.local_agent.urllib.request.urlopen")
    def test_health_check_classifies_direct_timeout(self, mock_urlopen):
        mock_urlopen.side_effect = TimeoutError("timed out")

        result = local_agent._health_check("http://127.0.0.1:8080")

        self.assertFalse(result["reachable"])
        self.assertEqual(result["status"], "timeout")


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
        self.assertIn("effective model: Ornith-1.0-9B-4bit", printed)

    def test_doctor_reports_live_inventory_drift(self):
        healthy_response = {"reachable": True, "available_models": ["ornith", "qwen"]}
        with patch("synlynk.local_agent._health_check", return_value=healthy_response), \
             patch("synlynk.local_agent.shutil.which", return_value="/usr/local/bin/aider"), \
             patch("synlynk.local_agent._get_db"), \
             patch("synlynk.local_agent_seed.seed_local_capability_envelope"):
            with tempfile.TemporaryDirectory() as d:
                path = os.path.join(d, "local.json")
                with open(path, "w") as f:
                    json.dump({
                        "endpoint": "http://127.0.0.1:8000",
                        "models": [{"id": "ornith", "pinned": True, "edit_format": "whole"}],
                    }, f)
                with patch("builtins.print") as mock_print:
                    result = local_agent.cmd_local_doctor(path)
        printed = " ".join(str(call.args[0]) for call in mock_print.call_args_list)
        self.assertEqual(result, 0)
        self.assertIn("model drift [live_but_unapproved]: qwen", printed)


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
    def test_reads_keychain_credential_and_passes_to_health_check(self):
        healthy_response = {"reachable": True, "available_models": ["Ornith-1.0-9B-4bit"]}
        with patch("synlynk.local_agent._health_check", return_value=healthy_response) as mock_check, \
             patch("synlynk.local_agent.shutil.which", return_value="/usr/local/bin/aider"), \
             patch("synlynk.local_agent._get_db"), \
             patch("synlynk.local_agent_seed.seed_local_capability_envelope"), \
             patch("synlynk.local_credentials.LocalCredentialStore.get", return_value="sk-keychain-key"):
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
        mock_check.assert_called_once_with("http://127.0.0.1:8000", api_key="sk-keychain-key")

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
        self.assertIn("local credentials import", printed)
        self.assertNotIn("Start it with: omlx serve", printed)
