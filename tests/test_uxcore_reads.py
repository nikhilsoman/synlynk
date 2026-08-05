from synlynk import uxcore
import sqlite3
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
