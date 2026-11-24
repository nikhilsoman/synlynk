"""Hetzner Cloud ephemeral swarm runner driver using Python stdlib HTTP."""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
import urllib.request
import urllib.error
import uuid
from typing import Any, Callable, Dict, Optional

from synlynk.runners.base import SwarmRunnerDriver


def calculate_vertical_host_size(task_count: int, prefer_arm: bool = False) -> str:
    """Calculate the cost-optimal Hetzner server type based on concurrent tasks."""
    if prefer_arm:
        return "cax41"
    if task_count <= 3:
        return "cpx21"  # 3 vCPUs, 4 GB RAM (~€0.010/hr)
    elif task_count <= 8:
        return "cpx31"  # 4 vCPUs, 8 GB RAM (~€0.019/hr)
    else:
        return "cpx51"  # 16 vCPUs, 32 GB RAM (~€0.045/hr)


class HetznerRunnerDriver(SwarmRunnerDriver):
    """Provisions, supervises, and tears down ephemeral single-tenant Hetzner Cloud VMs."""

    SERVER_TYPES = {
        "small": "cpx21",
        "medium": "cpx31",
        "large": "cpx51",
        "arm_large": "cax41",
    }
    HOURLY_RATES_EUR = {
        "cpx21": 0.010,
        "cpx31": 0.019,
        "cpx51": 0.045,
        "cax41": 0.038,
    }

    def __init__(self, config: Optional[dict] = None, opener: Any = None):
        self.config = config or {}
        self.base_url = self.config.get("base_url", "https://api.hetzner.cloud/v1").rstrip("/")
        self.token = self.config.get("token") or os.environ.get("HCLOUD_TOKEN") or os.environ.get("HETZNER_API_TOKEN")
        self.location = self.config.get("location", "nbg1")
        self.image = self.config.get("image", "ubuntu-24.04")
        self.ssh_key = self.config.get("ssh_key")
        self.timeout_seconds = int(self.config.get("timeout_seconds", 3600))
        self.opener = opener or urllib.request.urlopen
        self._watchdogs: Dict[str, threading.Timer] = {}
        self._provisioned_at: Dict[str, datetime] = {}

    def _request(self, method: str, path: str, payload: Optional[dict] = None) -> dict:
        """Execute authenticated JSON request against Hetzner Cloud REST API."""
        if not self.token:
            raise ValueError("Hetzner runner requires swarm_runners.hetzner.token or HCLOUD_TOKEN environment variable")

        url = f"{self.base_url}{path}"
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}",
        }

        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with self.opener(req, timeout=30) as resp:
                body = resp.read()
                return json.loads(body.decode("utf-8")) if body else {}
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Hetzner API error ({e.code}) on {method} {path}: {err_body}") from e

    def build_cloud_init(self, job_spec: dict) -> str:
        """Build cloud-init user-data script enforcing Layer 1 hardware shutdown watchdog."""
        ttl_minutes = max(1, self.timeout_seconds // 60)
        command = job_spec.get("command", ["echo", "synlynk-worker-ready"])
        cmd_str = " ".join(command) if isinstance(command, list) else str(command)

        lines = [
            "#cloud-config",
            "package_update: true",
            "packages:",
            "  - git",
            "  - python3",
            "  - python3-pip",
            "runcmd:",
            f"  - shutdown -h +{ttl_minutes}",  # Layer 1 OS watchdog
            f"  - {cmd_str}",
            "  - poweroff",  # Layer 2 process completion shutdown
        ]
        return "\n".join(lines)

    def provision(self, job_spec: dict) -> str:
        """Create a dedicated single-tenant KVM VM on Hetzner Cloud."""
        runner_id = job_spec.get("runner_id") or f"synlynk-{uuid.uuid4().hex[:12]}"
        task_count = job_spec.get("task_count", 1)
        server_type = job_spec.get("server_type") or calculate_vertical_host_size(task_count)

        payload = {
            "name": runner_id,
            "server_type": server_type,
            "image": self.image,
            "location": self.location,
            "user_data": self.build_cloud_init(job_spec),
            "labels": {
                "manager": "synlynk",
                "runner_id": runner_id,
                "epic_id": job_spec.get("epic_id", "none"),
            },
        }

        if self.ssh_key:
            payload["ssh_keys"] = [self.ssh_key]

        result = self._request("POST", "/servers", payload)
        server = result.get("server", {})
        server_id = str(server.get("id", runner_id))

        # Layer 3 Client/Relay watchdog timer
        timer = threading.Timer(self.timeout_seconds, self.destroy, args=(server_id,))
        timer.daemon = True
        timer.start()
        self._watchdogs[server_id] = timer
        self._provisioned_at[server_id] = datetime.now(timezone.utc)

        return server_id

    def stream_telemetry(self, runner_id: str, callback: Callable) -> None:
        """Poll server status and emit telemetry records to callback."""
        try:
            status = self.collect_results(runner_id)
            state = status.get("status", "unknown")
            callback({"runner_id": runner_id, "stream": "status", "message": f"Server status: {state}"})
        except Exception as e:
            callback({"runner_id": runner_id, "stream": "error", "message": str(e)})

    def collect_results(self, runner_id: str) -> dict:
        """Return a normalized lease receipt with runtime and compute telemetry."""
        response = self._request("GET", f"/servers/{runner_id}")
        server = response.get("server", response)
        server_type = server.get("server_type", {})
        if isinstance(server_type, dict):
            server_type_name = server_type.get("name", "unknown")
            vcpus = server_type.get("cores", server_type.get("vcpus"))
            ram_gb = server_type.get("memory", server_type.get("memory_gb"))
        else:
            server_type_name = str(server_type)
            vcpus = None
            ram_gb = None

        provisioned_at = self._parse_timestamp(server.get("created"))
        if provisioned_at is None:
            provisioned_at = self._provisioned_at.get(runner_id, datetime.now(timezone.utc))
        now = datetime.now(timezone.utc)
        active_seconds = max(0, int((now - provisioned_at).total_seconds()))
        rate = float(self.config.get("rate_eur_per_hour", self.HOURLY_RATES_EUR.get(server_type_name, 0.0)))
        labels = server.get("labels") or {}
        return {
            "event": "milestone_lease_completed",
            "lease_id": labels.get("lease_id", server.get("name", runner_id)),
            "workspace_id": labels.get("workspace_id"),
            "epic_id": labels.get("epic_id"),
            "provider": "hetzner",
            "server_id": server.get("id", runner_id),
            "server_type": server_type_name,
            "vcpus": vcpus,
            "ram_gb": ram_gb,
            "location": self.location,
            "provisioned_at": provisioned_at.isoformat(),
            "destroyed_at": None,
            "active_seconds": active_seconds,
            "raw_compute_cost_eur": round(active_seconds * rate / 3600, 6),
            "status": server.get("status", "unknown"),
            "exit_code": server.get("exit_code"),
            "tasks_completed": labels.get("tasks_completed", 0),
        }

    @staticmethod
    def _parse_timestamp(value: Any) -> Optional[datetime]:
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)

    def destroy(self, runner_id: str) -> bool:
        """Unconditionally terminate server and zero underlying NVMe storage."""
        timer = self._watchdogs.pop(runner_id, None)
        if timer:
            timer.cancel()
        try:
            self._request("DELETE", f"/servers/{runner_id}")
            return True
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return True
            return False
        except RuntimeError as exc:
            if "(404)" in str(exc):
                return True
            return False
        except Exception:
            return False
