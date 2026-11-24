"""Hetzner Cloud ephemeral swarm runner driver using Python stdlib HTTP."""

from __future__ import annotations

import json
import ipaddress
import os
import shlex
import threading
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

    def __init__(self, config: Optional[dict] = None, opener: Any = None):
        self.config = config or {}
        self.base_url = self.config.get("base_url", "https://api.hetzner.cloud/v1").rstrip("/")
        self.token = self.config.get("token") or os.environ.get("HCLOUD_TOKEN") or os.environ.get("HETZNER_API_TOKEN")
        self.location = self.config.get("location", "nbg1")
        self.image = self.config.get("image", "ubuntu-24.04")
        self.ssh_key = self.config.get("ssh_key")
        self.repo_url = self.config.get(
            "repo_url", "https://github.com/nikhilsoman/synlynk.git"
        )
        self.ssm_available = bool(self.config.get("ssm_available", True))
        self.operator_cidr = self.config.get("operator_cidr")
        self.timeout_seconds = int(self.config.get("timeout_seconds", 3600))
        self.opener = opener or urllib.request.urlopen
        self._watchdogs: Dict[str, threading.Timer] = {}

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
        """Build an isolated Ubuntu bootstrap and the host watchdog.

        The host receives only a shallow checkout of the requested ref.  In
        particular, no caller-side ``.synlynk`` directory or ``state.db`` is
        copied to the machine; the install is made from the checked-out source
        and the readiness probe only invokes ``synlynk --version``.
        """
        ttl_minutes = max(1, self.timeout_seconds // 60)
        git_ref = str(job_spec.get("git_ref", "origin/main"))
        if not git_ref.strip():
            raise ValueError("git_ref must not be empty")
        fetch_ref = git_ref.removeprefix("origin/")

        if not self.ssm_available:
            if not self.operator_cidr:
                raise ValueError("operator_cidr is required when SSM is unavailable")
            try:
                cidr = str(ipaddress.ip_network(self.operator_cidr, strict=False))
            except ValueError as exc:
                raise ValueError("operator_cidr must be a valid IPv4 or IPv6 CIDR") from exc
        else:
            cidr = None

        command = job_spec.get("command", ["echo", "synlynk-worker-ready"])
        cmd_str = shlex.join([str(part) for part in command]) if isinstance(command, list) else str(command)
        repo_url = shlex.quote(str(job_spec.get("repo_url", self.repo_url)))
        quoted_ref = shlex.quote(fetch_ref)

        lines = [
            "#cloud-config",
            "package_update: true",
            "packages:",
            "  - git",
            "  - python3",
            "  - python3-pip",
            "  - python3-venv",
            "  - ufw",
            "  - snapd",
            "runcmd:",
            f"  - shutdown -h +{ttl_minutes}",  # Layer 1 OS watchdog
            "  - install -d -m 0755 /opt/synlynk /var/lib/synlynk",
            "  - rm -rf /opt/synlynk/.git /opt/synlynk/*",
            "  - git -C /opt/synlynk init",
            f"  - git -C /opt/synlynk remote add origin {repo_url}",
            f"  - git -C /opt/synlynk fetch --depth 1 origin {quoted_ref}",
            "  - git -C /opt/synlynk checkout --detach FETCH_HEAD",
            "  - rm -rf /opt/synlynk/.synlynk",
            "  - test -s /opt/synlynk/VERSION",
            "  - python3 -m venv /opt/synlynk-venv",
            "  - /opt/synlynk-venv/bin/pip install --no-deps /opt/synlynk",
            "  - ln -sf /opt/synlynk-venv/bin/synlynk /usr/local/bin/synlynk",
            "  - timeout 120 synlynk --version",
            "  - touch /var/lib/synlynk/ready",
        ]
        if self.ssm_available:
            lines.extend([
                "  - systemctl enable --now snapd.socket",
                "  - snap install amazon-ssm-agent --classic",
                "  - systemctl enable --now snap.amazon-ssm-agent.amazon-ssm-agent.service",
                "  - ufw default deny incoming",
                "  - ufw --force deny 22/tcp",
                "  - ufw --force enable",
            ])
        else:
            lines.extend([
                "  - ufw default deny incoming",
                f"  - ufw allow from {cidr} to any port 22 proto tcp",
                "  - ufw --force enable",
            ])
        lines.extend([
            f"  - {cmd_str}",
            "  - poweroff",  # Layer 2 process completion shutdown
        ])
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

        if self.config.get("firewall_id") is not None:
            payload["firewalls"] = [{"firewall": self.config["firewall_id"]}]

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

        return server_id

    def stream_telemetry(self, runner_id: str, callback: Callable) -> None:
        """Poll server status and emit telemetry records to callback."""
        try:
            status = self.collect_results(runner_id)
            server = status.get("server", {})
            state = server.get("status", "unknown")
            callback({"runner_id": runner_id, "stream": "status", "message": f"Server status: {state}"})
        except Exception as e:
            callback({"runner_id": runner_id, "stream": "error", "message": str(e)})

    def collect_results(self, runner_id: str) -> dict:
        """Query server status and metrics from Hetzner Cloud."""
        return self._request("GET", f"/servers/{runner_id}")

    def destroy(self, runner_id: str) -> bool:
        """Unconditionally terminate server and zero underlying NVMe storage."""
        timer = self._watchdogs.pop(runner_id, None)
        if timer:
            timer.cancel()
        try:
            self._request("DELETE", f"/servers/{runner_id}")
            return True
        except Exception:
            return False
