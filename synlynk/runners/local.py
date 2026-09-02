"""A deterministic subprocess-backed runner used for development and tests."""

from __future__ import annotations

import os
import subprocess
import threading
import time
import uuid

from synlynk.runners.base import SwarmRunnerDriver


class LocalRunnerDriver(SwarmRunnerDriver):
    def __init__(self, timeout_seconds=900):
        self.timeout_seconds = int(timeout_seconds)
        self.processes = {}
        self.receipts = {}
        self.specs = {}

    def provision(self, job_spec):
        runner_id = str(job_spec.get("runner_id") or f"local-{uuid.uuid4().hex[:12]}")
        command = job_spec.get("command") or job_spec.get("cmd") or ["true"]
        if isinstance(command, str):
            command = ["sh", "-c", command]
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   text=True, cwd=job_spec.get("cwd"), env=job_spec.get("env"))
        self.processes[runner_id] = process
        self.specs[runner_id] = job_spec
        threading.Thread(target=self._wait, args=(runner_id,), daemon=True).start()
        return runner_id

    def _wait(self, runner_id):
        process = self.processes[runner_id]
        try:
            exit_code = process.wait(timeout=self.timeout_seconds)
        except subprocess.TimeoutExpired:
            process.kill()
            exit_code = process.wait()
        self._set_receipt(runner_id, exit_code)

    def _set_receipt(self, runner_id, exit_code):
        self.receipts[runner_id] = {"runner_id": runner_id, "exit_code": exit_code,
                                    "status": "completed" if exit_code == 0 else "failed"}

    def stream_telemetry(self, runner_id, callback):
        process = self.processes[runner_id]
        if process.stdout is not None:
            for line in process.stdout:
                callback({"runner_id": runner_id, "stream": "stdout", "message": line.rstrip("\n")})
        process.wait(timeout=self.timeout_seconds)
        if runner_id not in self.receipts:
            self._set_receipt(runner_id, process.returncode)

    def collect_results(self, runner_id):
        process = self.processes.get(runner_id)
        if process is not None and runner_id not in self.receipts:
            process.wait(timeout=self.timeout_seconds)
            if runner_id not in self.receipts:
                self._set_receipt(runner_id, process.returncode)
        receipt = dict(self.receipts.get(runner_id, {"runner_id": runner_id, "exit_code": None, "status": "running"}))
        if runner_id in self.specs and self.specs[runner_id].get("commit_sha"):
            receipt["commit_sha"] = self.specs[runner_id]["commit_sha"]
        return receipt

    def destroy(self, runner_id):
        process = self.processes.get(runner_id)
        if process is None:
            return runner_id in self.receipts
        if process.poll() is None:
            process.kill()
            process.wait()
        self.receipts.setdefault(runner_id, {"runner_id": runner_id, "exit_code": process.returncode, "status": "destroyed"})
        return True
