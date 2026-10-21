"""Authenticated oMLX lifecycle primitives and host memory admission guard."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable


LIFECYCLE_MODEL_ID = "Ornith-1.0-9B-4bit"
SUPPORTED_OMLX_VERSION = "0.5.3"
MIN_AVAILABLE_BYTES = 8 * 1024**3
MAX_SWAP_GROWTH_BYTES = 256 * 1024**2
_MEMORY_SAMPLE_SECONDS = 10


class LifecycleError(RuntimeError):
    """Classified, redacted failure from local runtime setup or readiness."""

    def __init__(self, reason_code: str, message: str, *, phase: str = "readiness"):
        self.reason_code = reason_code
        self.phase = phase
        super().__init__(message)


@dataclass(frozen=True)
class HostMemorySnapshot:
    physical_bytes: int
    available_bytes: int
    pressure: str
    swap_used_bytes: int


def _run_host_command(args: list[str], timeout: float = 5) -> str:
    env = {key: value for key, value in os.environ.items() if key != "OPENAI_API_KEY"}
    try:
        result = subprocess.run(args, check=True, capture_output=True, text=True,
                                timeout=timeout, env=env)
    except Exception as exc:
        raise LifecycleError("memory_signal_unavailable", "host memory signal unavailable", phase="memory") from None
    return result.stdout


def parse_vm_stat(output: str) -> int:
    page_match = re.search(r"page size of\s+(\d+) bytes", output)
    if not page_match:
        raise ValueError("vm_stat page size unavailable")
    pages = {}
    for label, count in re.findall(r"^Pages ([A-Za-z ]+):\s+(\d+)\.", output, re.MULTILINE):
        pages[label.strip().lower()] = int(count)
    required = {"free", "inactive", "speculative", "purgeable"}
    if not required.issubset(pages):
        raise ValueError("vm_stat available page counts unavailable")
    return sum(pages[name] for name in required) * int(page_match.group(1))


def parse_memory_pressure(output: str) -> str:
    match = re.search(r"System-wide memory free percentage:\s*(\d+(?:\.\d+)?)%", output, re.IGNORECASE)
    if not match:
        raise ValueError("memory pressure percentage unavailable")
    free_percent = float(match.group(1))
    if free_percent >= 10:
        return "normal"
    if free_percent >= 2:
        return "warning"
    return "critical"


def parse_swap_usage(output: str) -> int:
    match = re.search(r"used\s*=\s*([\d.]+)\s*([KMG])", output, re.IGNORECASE)
    if not match:
        raise ValueError("swap usage unavailable")
    scale = {"K": 1024, "M": 1024**2, "G": 1024**3}[match.group(2).upper()]
    return int(float(match.group(1)) * scale)


def read_host_memory() -> HostMemorySnapshot:
    """Read physical/available memory, pressure, and swap signals on macOS."""
    if sys.platform != "darwin":
        raise LifecycleError("unsupported_platform", "automatic Local lifecycle requires macOS", phase="memory")
    try:
        physical = int(_run_host_command(["sysctl", "-n", "hw.memsize"]).strip())
        available = parse_vm_stat(_run_host_command(["vm_stat"]))
        pressure = parse_memory_pressure(_run_host_command(["memory_pressure", "-Q"]))
        swap = parse_swap_usage(_run_host_command(["sysctl", "vm.swapusage"]))
        if physical <= 0 or available < 0:
            raise ValueError("invalid memory values")
        return HostMemorySnapshot(physical, available, pressure, swap)
    except LifecycleError:
        raise
    except Exception:
        raise LifecycleError("memory_signal_unavailable", "host memory signal unavailable", phase="memory") from None


def check_memory_admission(before: HostMemorySnapshot | None,
                           after: HostMemorySnapshot | None) -> None:
    if before is None or after is None:
        raise LifecycleError("memory_signal_unavailable", "host memory signal unavailable", phase="memory")
    if before.physical_bytes <= 0 or after.physical_bytes <= 0:
        raise LifecycleError("memory_signal_unavailable", "physical memory signal unavailable", phase="memory")
    if after.available_bytes < MIN_AVAILABLE_BYTES:
        raise LifecycleError("insufficient_memory", "less than 8 GiB host memory is available", phase="memory")
    if after.pressure != "normal":
        raise LifecycleError("memory_pressure", "host memory pressure is not normal", phase="memory")
    if after.swap_used_bytes - before.swap_used_bytes > MAX_SWAP_GROWTH_BYTES:
        raise LifecycleError("memory_pressure", "host swap grew by more than 256 MiB", phase="memory")


def require_memory_admission(snapshotter: Callable[[], HostMemorySnapshot] = read_host_memory,
                             sleeper: Callable[[float], None] = time.sleep) -> HostMemorySnapshot:
    before = snapshotter()
    sleeper(_MEMORY_SAMPLE_SECONDS)
    after = snapshotter()
    check_memory_admission(before, after)
    return after


class OmlxClient:
    """Small authenticated client for the verified oMLX 0.5.3 API contract."""

    def __init__(self, endpoint: str, credential_store):
        if endpoint.rstrip("/") != "http://127.0.0.1:8000":
            raise LifecycleError("unsupported_endpoint", "oMLX endpoint must be the fixed host loopback", phase="configuration")
        self.endpoint = endpoint.rstrip("/")
        self.credential_store = credential_store

    def validate_version(self, version: str) -> str:
        normalized = version.strip().removeprefix("oMLX ").removeprefix("v")
        if normalized != SUPPORTED_OMLX_VERSION:
            raise LifecycleError("unsupported_omlx_version", "installed oMLX version has no verified lifecycle contract", phase="version")
        return normalized

    def installed_version(self) -> str:
        executable = shutil.which("omlx")
        if not executable:
            raise LifecycleError("omlx_not_installed", "oMLX executable is unavailable", phase="version")
        env = {key: value for key, value in os.environ.items() if key != "OPENAI_API_KEY"}
        try:
            result = subprocess.run([executable, "--version"], check=True, capture_output=True,
                                    text=True, timeout=5, env=env)
        except Exception:
            raise LifecycleError("omlx_version_unavailable", "could not read oMLX version", phase="version") from None
        return self.validate_version(result.stdout or result.stderr)

    def _request(self, path: str, method: str = "GET") -> bytes:
        if not path.startswith("/v1/") or ".." in path:
            raise LifecycleError("unsupported_load_contract", "oMLX API path is not allowed")
        try:
            credential = self.credential_store.get()
            request = urllib.request.Request(
                self.endpoint + path,
                data=b"{}" if method == "POST" else None,
                headers={"Authorization": "Bearer " + credential, "Content-Type": "application/json"},
                method=method,
            )
            with urllib.request.urlopen(request, timeout=15) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            codes = {401: "authentication_failed", 404: "unsupported_load_contract", 507: "insufficient_memory"}
            reason = codes.get(exc.code, "omlx_request_failed")
            raise LifecycleError(reason, f"oMLX API request failed (HTTP {exc.code})") from None
        except LifecycleError:
            raise
        except Exception:
            raise LifecycleError("omlx_unreachable", "authenticated oMLX API request failed") from None

    def list_models(self) -> list[str]:
        try:
            payload = json.loads(self._request("/v1/models"))
            items = payload.get("data", payload.get("models", []))
            if not isinstance(items, list):
                raise ValueError
            return [str(item["id"]) for item in items if isinstance(item, dict) and item.get("id")]
        except LifecycleError:
            raise
        except Exception:
            raise LifecycleError("malformed_inventory", "oMLX returned malformed model inventory") from None

    def _model_action(self, model_id: str, action: str) -> None:
        if model_id != LIFECYCLE_MODEL_ID:
            raise LifecycleError("model_not_approved", "only the approved Ornith model may be loaded or unloaded", phase="model")
        self._request(f"/v1/models/{model_id}/{action}", method="POST")

    def load_model(self, model_id: str) -> None:
        self._model_action(model_id, "load")

    def unload_model(self, model_id: str) -> None:
        self._model_action(model_id, "unload")
