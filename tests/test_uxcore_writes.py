# tests/test_uxcore_writes.py
import json
import os
from unittest.mock import patch

from synlynk import uxcore


def test_feature_flags_missing_key_is_disabled(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk")
    with open(".synlynk/config.json", "w") as f:
        json.dump({}, f)
    assert uxcore.FeatureFlags.is_enabled("gantt_view", tier="individual") is False


def test_feature_flags_enabled_for_tier(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk")
    with open(".synlynk/config.json", "w") as f:
        json.dump({"features": {"gantt_view": ["individual", "team"]}}, f)
    assert uxcore.FeatureFlags.is_enabled("gantt_view", tier="individual") is True
    assert uxcore.FeatureFlags.is_enabled("gantt_view", tier="enterprise") is False


def test_list_capabilities_owner_gets_everything(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    caps = uxcore.list_capabilities(uxcore.DEFAULT_ACTOR)
    names = {c.name for c in caps}
    assert "dispatch" in names
    assert "approve_pr" in names
    assert "kill_job" in names


def test_execute_write_appends_event(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    def fake_op(**params):
        return {"ok": True, "job_id": "job-abc123"}

    result = uxcore._execute_write("dispatch", uxcore.DEFAULT_ACTOR, fake_op, agent="codex", task="do it")
    assert result.ok is True
    assert result.job_id == "job-abc123"
    with open(".synlynk/events.jsonl") as f:
        lines = f.read().strip().splitlines()
    assert len(lines) == 1
    event = json.loads(lines[0])
    assert event["action"] == "dispatch"
    assert event["actor_id"] == "local"


def test_execute_write_denies_when_capability_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    viewer = uxcore.Actor(id="test-viewer", role=uxcore.Role.VIEWER)

    def fake_op(**params):
        raise AssertionError("should never be called")

    result = uxcore._execute_write("dispatch", viewer, fake_op, agent="codex", task="do it")
    assert result.ok is False
    assert result.message == "not permitted"
