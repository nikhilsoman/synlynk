"""Tests for tier-0 zero-trust local auto-routing."""

import json
import os
import unittest
from unittest.mock import MagicMock, patch


def test_read_local_fallback_reads_workspace_json(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk")
    with open(".synlynk/workspace.json", "w") as f:
        json.dump({"local_fallback": "codex"}, f)
    import synlynk.dispatch as dispatch_mod
    assert dispatch_mod._read_local_fallback() == "codex"


def test_read_local_threshold_reads_workspace_json(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk")
    with open(".synlynk/workspace.json", "w") as f:
        json.dump({"local_auto_threshold": 0.9}, f)
    import synlynk.dispatch as dispatch_mod
    assert dispatch_mod._read_local_threshold() == 0.9


class TestResolveDispatchAgent(unittest.TestCase):
    def _resolve(self, requested, task_type="testing", preflight_ok=True, cap_score=0.8):
        import synlynk.dispatch as dispatch_mod

        with patch.object(dispatch_mod, "_preflight_local_silent", return_value=preflight_ok), \
                patch.object(dispatch_mod, "_get_local_capability_score", return_value=cap_score), \
                patch.object(dispatch_mod, "_read_local_fallback", return_value="agy"), \
                patch.object(dispatch_mod, "_read_local_threshold", return_value=0.5):
            return dispatch_mod._resolve_dispatch_agent(
                requested, task_type, MagicMock()
            )

    def test_explicit_agent_bypasses_routing(self):
        self.assertEqual(self._resolve("agy"), "agy")

    def test_explicit_local_bypasses_routing(self):
        self.assertEqual(self._resolve("local"), "local")

    def test_auto_routes_to_local_when_healthy_and_capable(self):
        self.assertEqual(self._resolve("auto", cap_score=0.8), "local")

    def test_auto_routes_to_fallback_when_local_unhealthy(self):
        self.assertEqual(self._resolve("auto", preflight_ok=False), "agy")

    def test_auto_routes_to_fallback_when_capability_is_below_threshold(self):
        self.assertEqual(self._resolve("auto", cap_score=0.3), "agy")

    def test_none_is_treated_as_auto(self):
        self.assertEqual(self._resolve(None, cap_score=0.8), "local")

    def test_auto_prints_routing_decision(self):
        with patch("sys.stdout") as stdout:
            self._resolve("auto", cap_score=0.72)
        self.assertIn("Routing to:", stdout.write.call_args_list[0].args[0])
