"""Docker CLI backed disposable swarm runner."""

from __future__ import annotations

import json
import subprocess
import threading
import uuid

from synlynk.runners.base import SwarmRunnerDriver


class DockerRunnerDriver(SwarmRunnerDriver):
    """Run a worker container with a bounded lifetime and resource budget."""

    def __init__(self, config=None, run=subprocess.run):
        self.config = config or {}
        self._run = run
        self.timeout_seconds = int(self.config.get("timeout_seconds", 900))
        self._watchdogs = {}

    def _exec(self, args, *, input=None):
        return self._run(
            ["docker", *args], input=input, text=True, capture_output=True,
            check=True, timeout=self.config.get("command_timeout_seconds", 60),
        )

    def provision(self, job_spec):
        runner_id = str(job_spec.get("runner_id") or f"synlynk-{uuid.uuid4().hex[:12]}")
        image = job_spec.get("image", self.config.get("image", "synlynk-worker:latest"))
        command = job_spec.get("command", ["synlynk", "worker"])
        if isinstance(command, str):
            command = ["sh", "-c", command]
        memory = str(job_spec.get("memory", self.config.get("memory", "4g")))
        args = [
            "run", "--detach", "--rm", "--name", runner_id,
            "--label", "synlynk.swarm=true",
            "--memory", memory,
            "--user", str(job_spec.get("user", self.config.get("user", "1000:1000"))),
            "--env", f"SYNLYNK_RUNNER_ID={runner_id}",
            "--env", f"TIMEOUT={self.timeout_seconds}",
        ]
        for key, value in (job_spec.get("env") or {}).items():
            args.extend(("--env", f"{key}={value}"))
        for source, target in (job_spec.get("mounts") or {}).items():
            args.extend(("--volume", f"{source}:{target}:ro"))
        args.append(image)
        args.extend(command)
        result = self._exec(args)
        container_id = result.stdout.strip() or runner_id
        timer = threading.Timer(self.timeout_seconds, self.destroy, args=(container_id,))
        timer.daemon = True
        timer.start()
        self._watchdogs[container_id] = timer
        return container_id

    def stream_telemetry(self, runner_id, callback):
        result = self._exec(["logs", "--follow", runner_id])
        for line in result.stdout.splitlines():
            callback({"runner_id": runner_id, "stream": "stdout", "message": line})

    def collect_results(self, runner_id):
        result = self._exec(["inspect", runner_id])
        data = json.loads(result.stdout)[0]
        state = data.get("State", {})
        exit_code = state.get("ExitCode")
        return {
            "runner_id": runner_id,
            "status": "running" if state.get("Running") else ("completed" if exit_code == 0 else "failed"),
            "exit_code": exit_code,
        }

    def destroy(self, runner_id):
        timer = self._watchdogs.pop(runner_id, None)
        if timer:
            timer.cancel()
        try:
            self._exec(["rm", "--force", runner_id])
        except subprocess.CalledProcessError as exc:
            if "No such container" not in (exc.stderr or ""):
                return False
        return True
