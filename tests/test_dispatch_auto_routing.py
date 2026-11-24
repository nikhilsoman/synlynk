"""Tests for tier-0 zero-trust local auto-routing."""

import json
import os
import unittest
from unittest.mock import MagicMock, patch

import pytest


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
                 pilot_class="test_summary", dispatch_key="test-2", requested_model=None):
        import synlynk.dispatch as dispatch_mod
        def resolve_model(**_kwargs):
            if not preflight_ok or _kwargs.get("requested_model") not in (None, "Ornith-1.0-9B-4bit"):
                raise ValueError("cannot resolve local model without healthy live oMLX inventory")
            return {
                "effective_model": "Ornith-1.0-9B-4bit",
                "edit_format": "diff",
                "health": "available",
            }

        with patch.object(dispatch_mod, "_get_local_capability_score", return_value=cap_score), \
                patch.object(dispatch_mod, "_read_local_fallback", return_value="agy"), \
                patch.object(dispatch_mod, "_read_local_threshold", return_value=0.5), \
                patch("synlynk.local_pilot_ledger.active_resume_authorization_matches_runtime", return_value=True), \
                patch("synlynk.local_agent.resolve_effective_local_model", side_effect=resolve_model), \
                patch("synlynk.local_pilot_ledger.load_pilot_status", return_value={
                    "historical": {"cohort": "historical", "accepted": 8, "eligible": 12},
                    "validation": {"accepted": 0, "rejected": 0, "safety_failed": 0},
                    "expansion": {"accepted": 0, "rejected": 0, "safety_failed": 0, "consecutive_accepted": 0},
                }), \
                patch("synlynk.local_pilot.load_pilot_runtime", return_value={
                    "enabled": True, "qualified": True, "isolated": True,
                    "share": 0.2, "max_concurrent": 1,
                    "qualified_models": ["Ornith-1.0-9B-4bit"],
                }):
            return dispatch_mod._resolve_dispatch_agent(
                requested, task_type, MagicMock(), task="summarize tests",
                role="dev", pilot_class=pilot_class, dispatch_key=dispatch_key,
                scope_paths=["test.log"], requested_model=requested_model,
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

    def test_unqualified_explicit_model_falls_back_instead_of_entering_pilot(self):
        self.assertEqual(
            self._resolve("auto", requested_model="Qwen2.5-Coder-14B-Instruct-4bit"),
            "agy",
        )

    def test_qualified_pilot_gate_replaces_legacy_capability_threshold(self):
        self.assertEqual(self._resolve("auto", cap_score=0.3), "local")

    def test_none_is_treated_as_auto(self):
        self.assertEqual(self._resolve(None, cap_score=0.8), "local")

    def test_auto_prints_routing_decision(self):
        with patch("sys.stdout") as stdout:
            self._resolve("auto", cap_score=0.72)
        self.assertIn("Routing to:", stdout.write.call_args_list[0].args[0])


def _make_db_with_floor(agent: str, task_type: str, cycles: float, n: int):
    import sqlite3
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE capability_ratings (story_id TEXT, agent TEXT, discipline TEXT, pr_review_cycles REAL)")
    conn.execute("CREATE TABLE cost_entries (agent TEXT, type_id TEXT, total_cost_usd REAL)")
    conn.execute("CREATE TABLE routing_rotation_state (task_type TEXT PRIMARY KEY, cursor INTEGER NOT NULL DEFAULT 0, updated_at TEXT)")
    for i in range(n):
        conn.execute(
            "INSERT INTO capability_ratings (story_id, agent, discipline, pr_review_cycles) VALUES (?, ?, ?, ?)",
            (f"s{i}", agent, task_type, cycles),
        )
    conn.commit()
    return conn


def test_auto_consults_live_router_instead_of_static_fallback(tmp_path):
    from synlynk.dispatch import _resolve_dispatch_agent
    config_path = tmp_path / "workspace.json"
    config_path.write_text(json.dumps({"local_fallback": "agy", "local_auto_threshold": 0.5}))
    conn = _make_db_with_floor("codex", "implement", 1.0, 5)
    for i in range(5):
        conn.execute(
            "INSERT INTO capability_ratings (story_id, agent, discipline, pr_review_cycles) VALUES (?, ?, ?, ?)",
            (f"g{i}", "grok", "implement", 3.0),
        )
    conn.commit()
    with patch("synlynk.dispatch._preflight_local_silent", return_value=False), \
         patch("synlynk.dispatch._eligible_harnesses_for_task_type", return_value=["codex", "grok"]):
        result = _resolve_dispatch_agent("auto", "implement", conn, config_path=str(config_path))
    # codex has the better (lower) score, must win over the hardcoded "agy" default.
    assert result == "codex"


def test_enforce_mode_blocks_sub_floor_exploration_for_high_blast_radius_task(tmp_path, monkeypatch):
    from synlynk.dispatch import _resolve_dispatch_agent

    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / ".synlynk" / "policy.json").write_text(
        json.dumps({"overrides": {"sub_floor_exploration_mode": "enforce"}})
    )
    conn = _make_db_with_floor("codex", "infra", 1.0, 1)
    with patch("synlynk.dispatch._preflight_local_silent", return_value=False), \
         patch("synlynk.dispatch._eligible_harnesses_for_task_type", return_value=["codex", "grok"]):
        with pytest.raises(RuntimeError, match="sub-floor exploration requires human approval"):
            _resolve_dispatch_agent("auto", "infra", conn)


def test_observe_mode_allows_sub_floor_exploration_for_high_blast_radius_task(tmp_path, monkeypatch):
    from synlynk.dispatch import _resolve_dispatch_agent

    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / ".synlynk" / "policy.json").write_text(
        json.dumps({"overrides": {"sub_floor_exploration_mode": "observe"}})
    )
    conn = _make_db_with_floor("codex", "infra", 1.0, 1)
    with patch("synlynk.dispatch._preflight_local_silent", return_value=False), \
         patch("synlynk.dispatch._eligible_harnesses_for_task_type", return_value=["codex", "grok"]):
        assert _resolve_dispatch_agent("auto", "infra", conn) == "codex"


def test_enforce_mode_blocks_sub_floor_exploration_for_github_write(tmp_path, monkeypatch):
    from synlynk.dispatch import _resolve_dispatch_agent

    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / ".synlynk" / "policy.json").write_text(
        json.dumps({"overrides": {"sub_floor_exploration_mode": "enforce"}})
    )
    conn = _make_db_with_floor("codex", "implement", 1.0, 1)
    with patch("synlynk.dispatch._preflight_local_silent", return_value=False), \
         patch("synlynk.dispatch._eligible_harnesses_for_task_type", return_value=["codex", "grok"]):
        with pytest.raises(RuntimeError, match="sub-floor exploration requires human approval"):
            _resolve_dispatch_agent("auto", "implement", conn, requires_gh_write=True)

