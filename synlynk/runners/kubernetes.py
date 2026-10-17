"""Kubernetes Job runner using the standard-library HTTP client."""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
import uuid

from synlynk.runners.base import SwarmRunnerDriver


class KubernetesRunnerDriver(SwarmRunnerDriver):
    """Provision one auto-expiring Kubernetes Job per swarm task."""

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

    def _namespace_path(self):
        return urllib.parse.quote(self.namespace, safe="")

    def provision(self, job_spec):
        runner_id = job_spec.get("runner_id") or f"synlynk-{uuid.uuid4().hex[:12]}"
        command = job_spec.get("command", ["synlynk", "worker"])
        if isinstance(command, str):
            command = ["sh", "-c", command]
        env = [{"name": "SYNLYNK_RUNNER_ID", "value": runner_id}]
        env.extend({"name": str(key), "value": str(value)} for key, value in job_spec.get("env", {}).items())
        body = {
            "apiVersion": "batch/v1", "kind": "Job",
            "metadata": {"name": runner_id, "labels": {"app": "synlynk-runner"}},
            "spec": {
                "backoffLimit": 0,
                "ttlSecondsAfterFinished": int(self.config.get("ttl_seconds", 900)),
                "template": {"metadata": {"labels": {"app": "synlynk-runner", "job-name": runner_id}},
                             "spec": {"restartPolicy": "Never", "containers": [{
                                 "name": "worker", "image": job_spec.get("image", self.image),
                                 "command": command, "env": env,
                             }]}},
            },
        }
        self._request("POST", f"/apis/batch/v1/namespaces/{self._namespace_path()}/jobs", body)
        return runner_id

    def stream_telemetry(self, runner_id, callback):
        namespace = self._namespace_path()
        selector = urllib.parse.quote(f"job-name={runner_id}", safe="")
        pods = self._request("GET", f"/api/v1/namespaces/{namespace}/pods?labelSelector={selector}")
        items = pods.get("items", []) if isinstance(pods, dict) else []
        if not items:
            return
        pod_name = items[0].get("metadata", {}).get("name")
        if not pod_name:
            return
        logs = self._request("GET", f"/api/v1/namespaces/{namespace}/pods/{urllib.parse.quote(pod_name, safe='')}/log")
        output = logs.get("logs", logs.get("stdout", "")) if isinstance(logs, dict) else str(logs)
        for line in output.splitlines():
            callback({"runner_id": runner_id, "stream": "stdout", "message": line})

    def collect_results(self, runner_id):
        namespace = self._namespace_path()
        result = self._request("GET", f"/apis/batch/v1/namespaces/{namespace}/jobs/{urllib.parse.quote(runner_id, safe='')}")
        status = result.get("status", {}) if isinstance(result, dict) else {}
        if not isinstance(status, dict):
            return result
        result["provider_status"] = status
        if status.get("succeeded"):
            result.update(status="completed", exit_code=0)
        elif status.get("failed"):
            result.update(status="failed", exit_code=1)
        else:
            result["status"] = "running"
        return result

    def destroy(self, runner_id):
        try:
            self._request("DELETE", f"/apis/batch/v1/namespaces/{self._namespace_path()}/jobs/{urllib.parse.quote(runner_id, safe='')}")
            return True
        except (OSError, ValueError):
            return False
