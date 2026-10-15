import json
import sqlite3
import sys

from synlynk.db import _migrate_db
from synlynk.runners.local import LocalRunnerDriver
from synlynk.runners.manager import RunnerManager


def test_swarm_runner_schema_and_local_lifecycle(tmp_path):
    conn = sqlite3.connect(str(tmp_path / "state.db"))
    _migrate_db(conn)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(swarm_runners)")}
    assert {"runner_id", "driver", "status", "job_spec", "destroyed_at"} <= columns

    manager = RunnerManager({"swarm_runners": {"enabled": ["local"]}}, conn)
    runner_id = manager.provision({"command": [sys.executable, "-c", "print('ok')"]}, "local")
    events = []
    manager.driver("local").stream_telemetry(runner_id, events.append)
    result = manager.driver("local").collect_results(runner_id)
    assert result["exit_code"] == 0
    assert events[0]["message"] == "ok"
    assert manager.list()[0]["runner_id"] == runner_id
    assert manager.destroy(runner_id)
    assert manager.list() == []


def test_local_driver_accepts_shell_command():
    driver = LocalRunnerDriver()
    runner_id = driver.provision({"command": "printf hello"})
    output = []
    driver.stream_telemetry(runner_id, output.append)
    assert output[0]["message"] == "hello"


def test_manager_persists_telemetry_and_results(tmp_path):
    conn = sqlite3.connect(str(tmp_path / "state.db"))
    _migrate_db(conn)
    manager = RunnerManager({"swarm_runners": {"enabled": ["local"]}}, conn)
    runner_id = manager.provision({"command": [sys.executable, "-c", "print('managed')"]})
    events = []
    manager.stream_telemetry(runner_id, events.append)
    result = manager.collect_results(runner_id)

    row = conn.execute(
        "SELECT status, exit_code, results_json, last_telemetry_at FROM swarm_runners WHERE runner_id=?",
        (runner_id,),
    ).fetchone()
    assert events[0]["message"] == "managed"
    assert result["exit_code"] == 0
    assert row[0:2] == ("completed", 0)
    assert json.loads(row[2])["runner_id"] == runner_id
    assert row[3]


def test_local_driver_merges_environment():
    driver = LocalRunnerDriver()
    runner_id = driver.provision({
        "command": [sys.executable, "-c", "import os; print(os.environ['SYNLYNK_TEST_ENV'])"],
        "env": {"SYNLYNK_TEST_ENV": "present"},
    })
    output = []
    driver.stream_telemetry(runner_id, output.append)
    assert output[0]["message"] == "present"
