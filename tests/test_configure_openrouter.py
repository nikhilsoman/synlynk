"""Tests for synlynk configure openrouter BYOK command and registry configuration."""

import json
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from synlynk.cli import build_parser
from synlynk.gateway import cmd_configure_openrouter
from synlynk.registry import configure_openrouter, load_registry, save_registry


class TestConfigureOpenrouter(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = os.path.join(self.temp_dir.name, "registry.json")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_configure_openrouter_defaults(self):
        registry = configure_openrouter(config_path=self.config_path)
        self.assertTrue(os.path.exists(self.config_path))
        cfg = registry["gateways"]["openrouter"]
        self.assertTrue(cfg["enabled"])
        self.assertTrue(cfg["dispatch_active"])
        self.assertEqual(cfg["base_url"], "https://openrouter.ai/api/v1")
        self.assertIn("anthropic/claude-sonnet-4", cfg["models"])
        self.assertTrue(registry["openrouter"]["enabled"])

    def test_configure_openrouter_custom_models_and_base_url(self):
        custom_models = ["meta-llama/llama-3-70b", "mistralai/mixtral-8x7b"]
        registry = configure_openrouter(
            models=custom_models,
            base_url="https://custom.openrouter.proxy/v1",
            config_path=self.config_path,
        )
        cfg = registry["gateways"]["openrouter"]
        self.assertEqual(cfg["models"], custom_models)
        self.assertEqual(cfg["base_url"], "https://custom.openrouter.proxy/v1")
        self.assertTrue(cfg["enabled"])
        self.assertTrue(cfg["dispatch_active"])

    def test_configure_openrouter_disable(self):
        configure_openrouter(config_path=self.config_path)
        registry = configure_openrouter(disable=True, config_path=self.config_path)
        cfg = registry["gateways"]["openrouter"]
        self.assertFalse(cfg["enabled"])
        self.assertFalse(cfg["dispatch_active"])
        self.assertFalse(registry["openrouter"]["enabled"])

    def test_cmd_configure_openrouter_execution(self):
        with patch.dict(os.environ, {}, clear=True):
            code = cmd_configure_openrouter(
                key="sk-or-test-key-12345",
                models="openai/gpt-4o,anthropic/claude-3-opus",
                config_path=self.config_path,
                probe=False,
            )
            self.assertEqual(code, 0)
            self.assertEqual(os.environ.get("OPENROUTER_API_KEY"), "sk-or-test-key-12345")

            loaded = load_registry(self.config_path)
            cfg = loaded["gateways"]["openrouter"]
            self.assertTrue(cfg["enabled"])
            self.assertTrue(cfg["dispatch_active"])
            self.assertEqual(cfg["models"], ["openai/gpt-4o", "anthropic/claude-3-opus"])

    def test_cmd_configure_openrouter_with_probe(self):
        with patch("synlynk.gateway.cmd_gateway_probe", return_value=0) as mock_probe:
            code = cmd_configure_openrouter(
                key="sk-probe-key",
                config_path=self.config_path,
                probe=True,
            )
            self.assertEqual(code, 0)
            mock_probe.assert_called_once_with(gateway="openrouter", config_path=self.config_path)

    def test_cli_parser_configure_openrouter(self):
        parser = build_parser()
        args = parser.parse_args([
            "configure", "openrouter",
            "--key", "sk-cli-key",
            "--models", "anthropic/claude-sonnet-4,openai/gpt-4o",
            "--base-url", "https://api.openrouter.ai/v1",
            "--probe",
        ])
        self.assertEqual(args.command, "configure")
        self.assertEqual(args.configure_target, "openrouter")
        self.assertEqual(args.key, "sk-cli-key")
        self.assertEqual(args.models, "anthropic/claude-sonnet-4,openai/gpt-4o")
        self.assertEqual(args.base_url, "https://api.openrouter.ai/v1")
        self.assertTrue(args.probe)
        self.assertFalse(args.disable)
