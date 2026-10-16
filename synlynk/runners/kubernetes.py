"""Kubernetes Job runner using the standard-library HTTP client."""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
import uuid

from synlynk.runners.base import SwarmRunnerDriver


class KubernetesRunnerDriver(SwarmRunnerDriver):
    def __init__(self, config=None, opener=None):
        self.config = config or {}
        self.base_url = self.config.get("base_url") or os.environ.get("KUBERNETES_API")
        self.token = self.config.get("token") or os.environ.get("KUBERNETES_TOKEN")
        self.namespace = self.config.get("namespace", "default")
        self.image = self.config.get("image", "synlynk-worker:latest")
        self.opener = opener or urllib.request.urlopen

    def _request(self, method, path, payload=None):
        if not self.base_url:
            raise ValueError("Kubernetes runner requires swarm_runners.k8s.base_url or KUBERNETES_API")
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        request = urllib.request.Request(
            self.base_url.rstrip("/") + path,
            data=json.dumps(payload).encode() if payload is not None else None,
            method=method,
            headers=headers,
        )
        with self.opener(request, timeout=30) as response:
            raw = response.read()
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except (TypeError, ValueError):
            return raw.decode() if isinstance(raw, bytes) else str(raw)

    def provision(self, job_spec):
        runner_id = job_spec.get("runner_id") or f"synlynk-{uuid.uuid4().hex[:12]}"
        command = job_spec.get("command", ["synlynk", "worker"])
        if isinstance(command, str):
            command = ["sh", "-c", command]
        env = [{"name": "SYNLYNK_RUNNER_ID", "value": runner_id}]
        env.extend({"name": str(key), "value": str(value)} for key, value in job_spec.get("env", {}).items())
        body = {
            "apiVersion": "batch/v1",
            "kind": "Job",
            "metadata": {"name": runner_id},
            "spec": {
                "backoffLimit": 0,
                "ttlSecondsAfterFinished": int(self.config.get("ttl_seconds", 900)),
                "template": {"spec": {"restartPolicy": "Never", "containers": [{
                    "name": "worker", "image": job_spec.get("image", self.image),
                    "command": command, "env": env,
                }]}}},
        }
        self._request("POST", f"/apis/batch/v1/namespaces/{urllib.parse.quote(self.namespace, safe='')}/jobs", body)
        return runner_id

    def stream_telemetry(self, runner_id, callback):
        namespace = urllib.parse.quote(self.namespace, safe="")
        pod = urllib.parse.quote(runner_id, safe="")
        result = self._request("GET", f"/api/v1/namespaces/{namespace}/pods/{pod}/log")
        logs = result.get("logs", result.get("stdout", "")) if isinstance(result, dict) else str(result)
        for line in str(logs).splitlines():
            callback({"runner_id": runner_id, "stream": "stdout", "message": line})

    def collect_results(self, runner_id):
        namespace = urllib.parse.quote(self.namespace, safe="")
        result = self._request("GET", f"/apis/batch/v1/namespaces/{namespace}/jobs/{urllib.parse.quote(runner_id, safe='')}")
        status = result.get("status", {}) if isinstance(result, dict) else {}
        if not isinstance(status, dict):
            return result
        result["provider_status"] = status
        if status.get("succeeded"):
            result["status"] = "completed"
            result["exit_code"] = 0
        elif status.get("failed"):
            result["status"] = "failed"
            result["exit_code"] = 1
        else:
            result["status"] = "running"
        return result

    def destroy(self, runner_id):
        namespace = urllib.parse.quote(self.namespace, safe="")
        path = f"/apis/batch/v1/namespaces/{namespace}/jobs/{urllib.parse.quote(runner_id, safe='')}"
        try:
            self._request("DELETE", path)
            return True
        except (OSError, ValueError):
            return False
