"""Fly.io Machines v2 runner driver using the standard-library HTTP client."""

from __future__ import annotations

import json
import os
import threading
import time
import urllib.request
import uuid

from synlynk.runners.base import SwarmRunnerDriver


class FlyRunnerDriver(SwarmRunnerDriver):
    def __init__(self, config=None, opener=None):
        self.config = config or {}
        self.base_url = self.config.get("base_url", "https://api.machines.dev/v1")
        self.app = self.config.get("app") or os.environ.get("FLY_APP")
        self.token = self.config.get("token") or os.environ.get("FLY_API_TOKEN")
        self.opener = opener or urllib.request.urlopen
        self.timeout_seconds = int(self.config.get("timeout_seconds", 900))
        self._watchdogs = {}

    def _request(self, method, path, payload=None):
        if not self.app:
            raise ValueError("Fly runner requires swarm_runners.fly.app or FLY_APP")
        request = urllib.request.Request(self.base_url.rstrip("/") + path,
                                         data=json.dumps(payload).encode() if payload is not None else None,
                                         method=method,
                                         headers={"Content-Type": "application/json", **({"Authorization": f"Bearer {self.token}"} if self.token else {})})
        with self.opener(request, timeout=30) as response:
            raw = response.read()
        return json.loads(raw) if raw else {}

    def provision(self, job_spec):
        runner_id = job_spec.get("runner_id") or f"synlynk-{uuid.uuid4().hex[:12]}"
        image = job_spec.get("image", self.config.get("image", "synlynk-worker:latest"))
        machine = {"name": runner_id, "config": {"image": image, "auto_destroy": True,
            "env": {"SYNLYNK_RUNNER_ID": runner_id, "TIMEOUT": str(self.timeout_seconds), **job_spec.get("env", {})},
            "guest": job_spec.get("guest", {"cpu_kind": "shared", "cpus": 1, "memory_mb": 512}),
            "init": {"cmd": job_spec.get("command", ["synlynk", "worker"])}}}
        result = self._request("POST", f"/apps/{self.app}/machines", machine)
        machine_id = result.get("id", runner_id)
        timer = threading.Timer(self.timeout_seconds, self.destroy, args=(machine_id,))
        timer.daemon = True
        timer.start()
        self._watchdogs[machine_id] = timer
        return machine_id

    def stream_telemetry(self, runner_id, callback):
        # Machines' exec/log endpoint is intentionally polled: it works with
        # the API's JSON response and remains easy to replace with SSE later.
        result = self._request("GET", f"/apps/{self.app}/machines/{runner_id}/logs")
        for line in result.get("logs", result.get("stdout", "")).splitlines():
            callback({"runner_id": runner_id, "stream": "stdout", "message": line})

    def collect_results(self, runner_id):
        return self._request("GET", f"/apps/{self.app}/machines/{runner_id}")

    def destroy(self, runner_id):
        timer = self._watchdogs.pop(runner_id, None)
        if timer:
            timer.cancel()
        try:
            self._request("DELETE", f"/apps/{self.app}/machines/{runner_id}")
            return True
        except (OSError, ValueError, urllib.error.HTTPError):
            return False
