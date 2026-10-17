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
    def _resolve(self, requested, task_type="testing", preflight_ok=True, cap_score=0.8,
                 pilot_class="test_summary", dispatch_key="test-2"):
        import synlynk.dispatch as dispatch_mod
        def resolve_model(**_kwargs):
            if not preflight_ok:
                raise ValueError("cannot resolve local model without healthy live oMLX inventory")
            return {
                "effective_model": "Ornith-1.0-9B-4bit",
                "edit_format": "diff",
                "health": "available",
            }

        with patch.object(dispatch_mod, "_get_local_capability_score", return_value=cap_score), \
                patch.object(dispatch_mod, "_read_local_fallback", return_value="agy"), \
                patch.object(dispatch_mod, "_read_local_threshold", return_value=0.5), \
                patch("synlynk.local_agent.resolve_effective_local_model", side_effect=resolve_model), \
                patch("synlynk.local_pilot.load_pilot_runtime", return_value={
                    "enabled": True, "qualified": True, "isolated": True,
                    "share": 0.2, "qualified_models": ["Ornith-1.0-9B-4bit"],
                }):
            return dispatch_mod._resolve_dispatch_agent(
                requested, task_type, MagicMock(), task="summarize tests",
                role="dev", pilot_class=pilot_class, dispatch_key=dispatch_key,
                scope_paths=["test.log"],
            )

    def test_explicit_agent_bypasses_routing(self):
        self.assertEqual(self._resolve("agy"), "agy")

    def test_explicit_local_bypasses_routing(self):
        self.assertEqual(self._resolve("local"), "local")

    def test_auto_routes_to_local_when_healthy_and_capable(self):
        self.assertEqual(self._resolve("auto", cap_score=0.8), "local")

    def test_auto_routes_to_frontier_without_explicit_pilot_class(self):
        self.assertEqual(self._resolve("auto", pilot_class=None), "agy")

    def test_auto_routes_to_frontier_when_outside_twenty_percent_cohort(self):
        self.assertEqual(self._resolve("auto", dispatch_key="test-0"), "agy")

    def test_auto_routes_to_frontier_for_github_write_even_if_class_is_allowlisted(self):
        import synlynk.dispatch as dispatch_mod
        from synlynk.local_pilot import load_pilot_runtime

        with patch("synlynk.local_pilot.load_pilot_runtime", return_value={
            "enabled": True, "qualified": True, "isolated": True,
            "share": 0.2, "qualified_models": ["Ornith-1.0-9B-4bit"],
        }), patch.object(dispatch_mod, "_read_local_fallback", return_value="codex"):
            self.assertEqual(
                dispatch_mod._resolve_dispatch_agent(
                    "auto", "testing", MagicMock(), task="test summary",
                    role="dev", requires_gh_write=True,
                    pilot_class="test_summary", dispatch_key="test-2",
                ),
                "codex",
            )

    def test_auto_routes_to_fallback_when_local_unhealthy(self):
        self.assertEqual(self._resolve("auto", preflight_ok=False), "agy")

    def test_qualified_pilot_gate_replaces_legacy_capability_threshold(self):
        self.assertEqual(self._resolve("auto", cap_score=0.3), "local")

    def test_none_is_treated_as_auto(self):
        self.assertEqual(self._resolve(None, cap_score=0.8), "local")

    def test_auto_prints_routing_decision(self):
        with patch("sys.stdout") as stdout:
            self._resolve("auto", cap_score=0.72)
        self.assertIn("Routing to:", stdout.write.call_args_list[0].args[0])
