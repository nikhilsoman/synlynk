import json
import os
import tempfile
import unittest
from unittest.mock import patch

from synlynk import dispatch as dispatch_mod
from synlynk._constants import HARNESS_CAPABILITY_BASELINES


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
            "--model", "openai/ornith-1.0-9b",
            "--edit-format", "whole",
            "--no-auto-lint", "--no-auto-test", "--map-tokens", "0",
        ])

    @patch("synlynk.dispatch._pkg")
    def test_other_agents_unaffected(self, mock_pkg):
        mock_pkg.return_value = {
            "codex": {"dispatch_flags": {"required_flags": ["-s", "read-only"]}},
        }
        flags = dispatch_mod._dispatch_flags_for_agent("codex")
        self.assertEqual(flags, ["-s", "read-only"])


class TestCodexComposedFlags(unittest.TestCase):
    def _compose(self, permissions, baseline=None):
        flags = list(baseline or HARNESS_CAPABILITY_BASELINES["codex"]["non_interactive_flags"])
        flags += dispatch_mod._dispatch_flags_for_agent("codex")
        permission_flags = dispatch_mod._permissions_to_flags("codex", permissions)
        return dispatch_mod._merge_codex_permission_flags(flags, permission_flags)

    def test_no_write_permission_replaces_baseline_sandbox(self):
        flags = self._compose(["read:*"])

        assert flags.count("-s") + flags.count("--sandbox") == 1
        assert flags[flags.index("-s") + 1] == "read-only"

    def test_write_permission_keeps_single_workspace_write_sandbox(self):
        flags = self._compose(["read:*", "write:src/"])

        assert flags.count("-s") + flags.count("--sandbox") == 1
        assert flags[flags.index("-s") + 1] == "workspace-write"
