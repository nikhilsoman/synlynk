from synlynk import uxcore
import sqlite3
import json
from unittest.mock import patch

from tests.test_viz import make_test_db


def test_local_actor_default_role_is_owner():
    actor = uxcore.LocalActor()
    assert actor.role == uxcore.Role.OWNER


def test_default_actor_singleton_is_local_owner():
    assert uxcore.DEFAULT_ACTOR.role == uxcore.Role.OWNER


def test_get_costs_returns_typed_dataclass(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    db_path = tmp_path / "state.db"
    make_test_db(str(db_path))
    with patch("synlynk.uxcore._get_db", return_value=sqlite3.connect(str(db_path))):
        costs = uxcore.get_costs()
    assert costs.total_usd == 1.20
    assert costs.by_agent["agy"]["actual"] == 1.20


def test_get_gantt_data_returns_dreams_with_stages(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    db_path = tmp_path / "state.db"
    make_test_db(str(db_path))
    with patch("synlynk.uxcore._get_db", return_value=sqlite3.connect(str(db_path))):
        dreams = uxcore.get_gantt_data()
    assert len(dreams) == 1
    assert dreams[0].id == "v0.11.0"
    assert dreams[0].stages[0].key == "Plan"


def test_get_jobs_reads_telemetry(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / ".synlynk" / "telemetry.json").write_text(json.dumps([
        {"ts": "2026-08-05T00:00:00Z", "agent": "codex", "duration_s": 12.5,
         "exit_code": 0, "cost_usd": 0.05},
    ]))
    jobs = uxcore.get_jobs()
    assert len(jobs) == 1
    assert jobs[0].agent == "codex"
    assert jobs[0].exit_code == 0


def test_get_jobs_missing_telemetry_returns_empty(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert uxcore.get_jobs() == []


def test_get_fleet_state_counts_agent_runs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / ".synlynk" / "telemetry.json").write_text(json.dumps([
        {"agent": "codex", "exit_code": 0},
        {"agent": "codex", "exit_code": 1},
    ]))
    fleet = uxcore.get_fleet_state()
    assert fleet["codex"].success_rate == 0.5
