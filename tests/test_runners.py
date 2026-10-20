import json
import sqlite3
import subprocess
import sys

from synlynk.cli import build_parser
from synlynk.db import _migrate_db
from synlynk.runners.docker import DockerRunnerDriver
from synlynk.runners.k8s import KubernetesJobRunnerDriver
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


def test_docker_driver_lifecycle_uses_bounded_container_and_reports_receipt():
    calls = []

    def run(args, **kwargs):
        calls.append((args, kwargs))
        if args[1] == "run":
            return subprocess.CompletedProcess(args, 0, "container-123\n", "")
        if args[1] == "logs":
            return subprocess.CompletedProcess(args, 0, "hello\n", "")
        if args[1] == "inspect":
            return subprocess.CompletedProcess(args, 0, '[{"State":{"Running":false,"ExitCode":0}}]', "")
        return subprocess.CompletedProcess(args, 0, "", "")

    driver = DockerRunnerDriver({"timeout_seconds": 45}, run=run)
    runner_id = driver.provision({"command": ["echo", "hello"], "runner_id": "container-123"})
    assert runner_id == "container-123"
    assert "--memory" in calls[0][0]
    assert "TIMEOUT=45" in calls[0][0]
    events = []
    driver.stream_telemetry(runner_id, events.append)
    assert events[0]["message"] == "hello"
    assert driver.collect_results(runner_id) == {
        "runner_id": runner_id, "status": "completed", "exit_code": 0,
    }
    assert driver.destroy(runner_id)


def test_kubernetes_driver_applies_ttl_job_and_reports_status():
    calls = []

    def run(args, **kwargs):
        calls.append((args, kwargs))
        if args[1] == "get":
            output = json.dumps({"status": {"succeeded": 1}})
        elif args[1] == "logs":
            output = "worker ready\n"
        else:
            output = ""
        return subprocess.CompletedProcess(args, 0, output, "")

    driver = KubernetesJobRunnerDriver({"namespace": "workers", "ttl_seconds_after_finished": 30}, run=run)
    runner_id = driver.provision({"runner_id": "swarm-job-1", "command": "echo ready"})
    manifest = json.loads(calls[0][1]["input"])
    assert runner_id == "swarm-job-1"
    assert manifest["spec"]["ttlSecondsAfterFinished"] == 30
    assert manifest["spec"]["activeDeadlineSeconds"] == 900
    assert manifest["spec"]["template"]["spec"]["containers"][0]["command"] == ["sh", "-c", "echo ready"]
    assert driver.collect_results(runner_id)["status"] == "completed"
    events = []
    driver.stream_telemetry(runner_id, events.append)
    assert events[0]["message"] == "worker ready"
    assert driver.destroy(runner_id)
    assert "--namespace" in calls[-1][0]


def test_runner_manager_registers_configured_docker_and_k8s_drivers():
    manager = RunnerManager({"swarm_runners": {"enabled": ["local", "docker", "k8s"]}})
    assert manager.driver("docker") is not None
    assert manager.driver("k8s") is not None


def test_swarm_dispatch_parser_accepts_cloud_drivers_and_positive_batch():
    args = build_parser().parse_args(["swarm", "dispatch", "--driver", "k8s", "--batch-size", "3"])
    assert args.driver == "k8s"
    assert args.batch_size == 3
