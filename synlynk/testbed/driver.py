"""Dual-backend driver layer for OrbStack VMs and Docker containers."""
from __future__ import annotations

import os
import subprocess
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Protocol


@dataclass
class NodeHandle:
    node_id: str
    ip: str
    driver_type: str
    status: str = "running"
    created_at: float = 0.0


@dataclass
class ExecResult:
    returncode: int
    stdout: str
    stderr: str
    duration_seconds: float = 0.0

    @property
    def ok(self) -> bool:
        return self.returncode == 0


class TestbedDriver(Protocol):
    def create_node(self, node_id: str, base_image: str = "ubuntu:noble") -> NodeHandle: ...
    def exec_command(self, node_id: str, command: str, env: Optional[Dict[str, str]] = None) -> ExecResult: ...
    def copy_file(self, node_id: str, src_path: str, dst_path: str) -> None: ...
    def get_ip_address(self, node_id: str) -> str: ...
    def inject_fault(self, node_id: str, fault_type: str) -> None: ...
    def destroy_node(self, node_id: str) -> None: ...
    def list_nodes(self) -> list[NodeHandle]: ...


class OrbDriver:
    """Orchestrates lightweight Linux VMs on macOS via OrbStack's orbctl CLI."""

    def __init__(self, orbctl_bin: str = "orbctl"):
        self.orbctl_bin = orbctl_bin

    def create_node(self, node_id: str, base_image: str = "ubuntu:noble") -> NodeHandle:
        # Create VM instance
        subprocess.run(
            [self.orbctl_bin, "create", base_image, node_id],
            capture_output=True,
            text=True,
            check=True,
        )
        ip = self.get_ip_address(node_id)
        return NodeHandle(
            node_id=node_id,
            ip=ip,
            driver_type="orbstack",
            status="running",
            created_at=time.time(),
        )

    def exec_command(self, node_id: str, command: str, env: Optional[Dict[str, str]] = None) -> ExecResult:
        start_t = time.time()
        env_prefix = []
        if env:
            for k, v in env.items():
                env_prefix.extend(["-e", f"{k}={v}"])

        cmd = [self.orbctl_bin, "-m", node_id] + env_prefix + ["run", "--", "bash", "-c", command]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        duration = time.time() - start_t
        return ExecResult(
            returncode=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
            duration_seconds=duration,
        )

    def copy_file(self, node_id: str, src_path: str, dst_path: str) -> None:
        subprocess.run(
            [self.orbctl_bin, "push", "-m", node_id, src_path, dst_path],
            capture_output=True,
            text=True,
            check=True,
        )

    def get_ip_address(self, node_id: str) -> str:
        # Query IP via orbctl or hostname inside node
        proc = subprocess.run(
            [self.orbctl_bin, "-m", node_id, "run", "--", "hostname", "-I"],
            capture_output=True,
            text=True,
            check=True,
        )
        ips = proc.stdout.strip().split()
        return ips[0] if ips else "127.0.0.1"

    def inject_fault(self, node_id: str, fault_type: str) -> None:
        if fault_type == "kill":
            subprocess.run(
                [self.orbctl_bin, "stop", "-f", node_id],
                capture_output=True,
                text=True,
                check=True,
            )
        elif fault_type == "partition":
            # Drop all incoming / outgoing traffic using iptables
            self.exec_command(node_id, "sudo iptables -A INPUT -j DROP && sudo iptables -A OUTPUT -j DROP")
        elif fault_type == "heal_partition":
            self.exec_command(node_id, "sudo iptables -F")
        elif fault_type == "delay":
            # Add 100ms latency via tc netem
            self.exec_command(node_id, "sudo tc qdisc add dev eth0 root netem delay 100ms 10ms")
        else:
            raise ValueError(f"Unknown fault type: {fault_type}")

    def destroy_node(self, node_id: str) -> None:
        subprocess.run(
            [self.orbctl_bin, "delete", "-f", node_id],
            capture_output=True,
            text=True,
            check=True,
        )

    def list_nodes(self) -> list[NodeHandle]:
        proc = subprocess.run(
            [self.orbctl_bin, "list", "--format", "json"],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            return []
        import json
        try:
            items = json.loads(proc.stdout)
            return [
                NodeHandle(
                    node_id=item.get("name", ""),
                    ip=item.get("ip", ""),
                    driver_type="orbstack",
                    status=item.get("status", "unknown"),
                )
                for item in items
                if "testbed" in item.get("name", "")
            ]
        except Exception:
            return []


class DockerDriver:
    """Orchestrates isolated Docker containers sharing a dedicated bridge network."""

    def __init__(self, docker_bin: str = "docker", network: str = "synlynk-testbed"):
        self.docker_bin = docker_bin
        self.network = network
        self._ensure_network()

    def _ensure_network(self) -> None:
        proc = subprocess.run(
            [self.docker_bin, "network", "inspect", self.network],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            subprocess.run(
                [self.docker_bin, "network", "create", self.network],
                capture_output=True,
                text=True,
            )

    def create_node(self, node_id: str, base_image: str = "ubuntu:noble") -> NodeHandle:
        self._ensure_network()
        subprocess.run(
            [
                self.docker_bin,
                "run",
                "-d",
                "--name",
                node_id,
                "--network",
                self.network,
                "--cap-add=NET_ADMIN",
                base_image,
                "tail",
                "-f",
                "/dev/null",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        ip = self.get_ip_address(node_id)
        return NodeHandle(
            node_id=node_id,
            ip=ip,
            driver_type="docker",
            status="running",
            created_at=time.time(),
        )

    def exec_command(self, node_id: str, command: str, env: Optional[Dict[str, str]] = None) -> ExecResult:
        start_t = time.time()
        env_flags = []
        if env:
            for k, v in env.items():
                env_flags.extend(["-e", f"{k}={v}"])

        cmd = [self.docker_bin, "exec"] + env_flags + [node_id, "bash", "-c", command]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        duration = time.time() - start_t
        return ExecResult(
            returncode=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
            duration_seconds=duration,
        )

    def copy_file(self, node_id: str, src_path: str, dst_path: str) -> None:
        subprocess.run(
            [self.docker_bin, "cp", src_path, f"{node_id}:{dst_path}"],
            capture_output=True,
            text=True,
            check=True,
        )

    def get_ip_address(self, node_id: str) -> str:
        proc = subprocess.run(
            [
                self.docker_bin,
                "inspect",
                "-f",
                f"{{{{.NetworkSettings.Networks.{self.network}.IPAddress}}}}",
                node_id,
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return proc.stdout.strip()

    def inject_fault(self, node_id: str, fault_type: str) -> None:
        if fault_type == "kill":
            subprocess.run([self.docker_bin, "kill", node_id], capture_output=True, check=True)
        elif fault_type == "partition":
            self.exec_command(node_id, "iptables -A INPUT -j DROP && iptables -A OUTPUT -j DROP")
        elif fault_type == "heal_partition":
            self.exec_command(node_id, "iptables -F")
        elif fault_type == "delay":
            self.exec_command(node_id, "tc qdisc add dev eth0 root netem delay 100ms 10ms")
        else:
            raise ValueError(f"Unknown fault type: {fault_type}")

    def destroy_node(self, node_id: str) -> None:
        subprocess.run(
            [self.docker_bin, "rm", "-f", node_id],
            capture_output=True,
            text=True,
            check=True,
        )

    def list_nodes(self) -> list[NodeHandle]:
        proc = subprocess.run(
            [self.docker_bin, "ps", "--filter", f"network={self.network}", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            return []
        names = [n for n in proc.stdout.strip().split("\n") if n]
        return [
            NodeHandle(
                node_id=name,
                ip=self.get_ip_address(name),
                driver_type="docker",
                status="running",
            )
            for name in names
        ]
