import json
import os
import tempfile
import unittest
from unittest.mock import patch

from synlynk import dispatch as dispatch_mod


class TestDispatchFlagsForLocalAgent(unittest.TestCase):
    @patch("synlynk.dispatch._pkg")
    def test_appends_dynamic_model_flags_for_local(self, mock_pkg):
        mock_pkg.return_value = {
            "local": {
                "dispatch_flags": ["--no-auto-commits", "--yes-always"],
            }
        }
        with tempfile.TemporaryDirectory() as d:
            config_path = os.path.join(d, "local.json")
            with open(config_path, "w") as f:
                json.dump({
                    "endpoint": "http://127.0.0.1:8080",
                    "models": [{"id": "ornith-1.0-9b", "pinned": True, "edit_format": "whole"}],
                }, f)
            with patch("synlynk.local_agent._DEFAULT_CONFIG_PATH", config_path):
                flags = dispatch_mod._dispatch_flags_for_agent("local")
        self.assertEqual(flags, [
            "--no-auto-commits", "--yes-always",
            "--openai-api-base", "http://127.0.0.1:8080/v1",
            "--model", "ornith-1.0-9b",
            "--edit-format", "whole",
        ])

    @patch("synlynk.dispatch._pkg")
    def test_other_agents_unaffected(self, mock_pkg):
        mock_pkg.return_value = {
            "codex": {"dispatch_flags": {"required_flags": ["--approval-policy"]}},
        }
        flags = dispatch_mod._dispatch_flags_for_agent("codex")
        self.assertEqual(flags, ["--approval-policy"])
