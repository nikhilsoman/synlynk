"""Kubernetes Job runner using kubectl and a TTL cleanup policy."""

from __future__ import annotations

import json
import subprocess
import uuid

from synlynk.runners.base import SwarmRunnerDriver


class KubernetesJobRunnerDriver(SwarmRunnerDriver):
    """Create one isolated Kubernetes Job for each swarm task."""

    def __init__(self, config=None, run=subprocess.run):
        self.config = config or {}
        self._run = run
        self.timeout_seconds = int(self.config.get("timeout_seconds", 900))

    def _exec(self, args, *, input=None):
        return self._run(
            ["kubectl", *args], input=input, text=True, capture_output=True,
            check=True, timeout=self.config.get("command_timeout_seconds", 60),
        )

    def _job_name(self, runner_id):
        return runner_id.lower().replace("_", "-")[:63].rstrip("-")

    def provision(self, job_spec):
        runner_id = str(job_spec.get("runner_id") or f"synlynk-{uuid.uuid4().hex[:12]}")
        name = self._job_name(runner_id)
        command = job_spec.get("command", ["synlynk", "worker"])
        if isinstance(command, str):
            command = ["sh", "-c", command]
        container = {
            "name": "worker",
            "image": job_spec.get("image", self.config.get("image", "synlynk-worker:latest")),
            "command": command,
            "env": [
                {"name": "SYNLYNK_RUNNER_ID", "value": runner_id},
                {"name": "TIMEOUT", "value": str(self.timeout_seconds)},
            ] + [
                {"name": key, "value": str(value)}
                for key, value in (job_spec.get("env") or {}).items()
            ],
            "resources": {"limits": job_spec.get("resources", self.config.get("resources", {"memory": "4Gi", "cpu": "2"}))},
            "securityContext": {"runAsNonRoot": True},
        }
        manifest = {
            "apiVersion": "batch/v1",
            "kind": "Job",
            "metadata": {"name": name, "labels": {"app.kubernetes.io/managed-by": "synlynk", "synlynk-runner-id": runner_id}},
            "spec": {
                "ttlSecondsAfterFinished": int(self.config.get("ttl_seconds_after_finished", 120)),
                "activeDeadlineSeconds": self.timeout_seconds,
                "backoffLimit": 0,
                "template": {"spec": {"restartPolicy": "Never", "containers": [container]}},
            },
        }
        namespace = job_spec.get("namespace", self.config.get("namespace"))
        args = ["apply", "-f", "-"]
        if namespace:
            args.extend(("--namespace", str(namespace)))
        self._exec(args, input=json.dumps(manifest))
        return runner_id

    def stream_telemetry(self, runner_id, callback):
        name = self._job_name(runner_id)
        args = ["logs", "--follow", f"job/{name}"]
        namespace = self.config.get("namespace")
        if namespace:
            args.extend(("--namespace", str(namespace)))
        result = self._exec(args)
        for line in result.stdout.splitlines():
            callback({"runner_id": runner_id, "stream": "stdout", "message": line})

    def collect_results(self, runner_id):
        name = self._job_name(runner_id)
        args = ["get", "job", name, "--output", "json"]
        namespace = self.config.get("namespace")
        if namespace:
            args.extend(("--namespace", str(namespace)))
        data = json.loads(self._exec(args).stdout)
        status = data.get("status", {})
        if status.get("succeeded"):
            state, exit_code = "completed", 0
        elif status.get("failed"):
            state, exit_code = "failed", 1
        else:
            state, exit_code = "running", None
        return {"runner_id": runner_id, "status": state, "exit_code": exit_code}

    def destroy(self, runner_id):
        args = ["delete", "job", self._job_name(runner_id), "--ignore-not-found=true", "--wait=false"]
        namespace = self.config.get("namespace")
        if namespace:
            args.extend(("--namespace", str(namespace)))
        try:
            self._exec(args)
        except subprocess.CalledProcessError:
            return False
        return True
