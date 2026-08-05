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


def test_dispatch_calls_dispatch_agent_and_wraps_result(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with patch("synlynk.dispatch.dispatch_agent", return_value={"job_id": "job-xyz", "ok": True}):
        result = uxcore.dispatch(agent="codex", task="fix the bug")
    assert result.ok is True
    assert result.job_id == "job-xyz"


def test_dispatch_denied_for_viewer(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    viewer = uxcore.Actor(id="v", role=uxcore.Role.VIEWER)
    with patch("synlynk.dispatch.dispatch_agent") as mock_dispatch:
        result = uxcore.dispatch(agent="codex", task="fix the bug", actor=viewer)
    assert result.ok is False
    mock_dispatch.assert_not_called()


def test_approve_pr_runs_gh_commands(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = ""
        result = uxcore.approve_pr(pr_number=715)
    assert result.ok is True
    called_cmds = [call.args[0] for call in mock_run.call_args_list]
    assert any("merge" in cmd for cmd in called_cmds)


def test_kill_job_sends_sigterm_to_tracked_pid(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk")
    with open(".synlynk/jobs.json", "w") as f:
        json.dump([{"job_id": "job-abc", "pid": 99999, "status": "running"}], f)
    with patch("os.kill") as mock_kill:
        result = uxcore.kill_job(job_id="job-abc")
    assert result.ok is True
    mock_kill.assert_called_once()
    assert mock_kill.call_args.args[0] == 99999


def test_kill_job_unknown_id_returns_not_ok(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk")
    with open(".synlynk/jobs.json", "w") as f:
        json.dump([], f)
    result = uxcore.kill_job(job_id="job-does-not-exist")
    assert result.ok is False


def test_subscribe_yields_existing_events_filtered_by_type(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk")
    with open(".synlynk/events.jsonl", "w") as f:
        f.write(json.dumps({
            "actor_id": "local", "action": "dispatch", "params": {}, "timestamp": "t1",
            "result": {"ok": True},
        }) + "\n")
        f.write(json.dumps({
            "actor_id": "local", "action": "approve_pr", "params": {}, "timestamp": "t2",
            "result": {"ok": True},
        }) + "\n")
    events = list(uxcore.subscribe(event_types=["approve_pr"]))
    assert len(events) == 1
    assert events[0].action == "approve_pr"


def test_subscribe_no_filter_returns_all(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk")
    with open(".synlynk/events.jsonl", "w") as f:
        f.write(json.dumps({
            "actor_id": "local", "action": "dispatch", "params": {}, "timestamp": "t1",
            "result": {"ok": True},
        }) + "\n")
    events = list(uxcore.subscribe())
    assert len(events) == 1


def test_subscribe_missing_file_yields_nothing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert list(uxcore.subscribe()) == []
