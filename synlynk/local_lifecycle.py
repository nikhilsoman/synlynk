"""Authenticated oMLX lifecycle primitives and host memory admission guard."""

from __future__ import annotations

import json
import os
import re
import socket
import shutil
import subprocess
import sys
import tempfile
import uuid
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Callable
from urllib.parse import urlsplit


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


IDLE_TIMEOUT_SECONDS = 900


@dataclass(frozen=True)
class LocalRuntimeResult:
    ready: bool
    model_id: str
    managed: bool
    owner_pid: int | None = None


def prepare_local_pilot(repo_root: str, dispatch_key: str, pilot_class: str) -> LocalRuntimeResult:
    """Make the approved Local runtime ready, retry once, and report redacted failure."""
    del repo_root  # Lifecycle ownership is host-global, not repository-local.
    if not dispatch_key or not pilot_class:
        raise LifecycleError("invalid_dispatch_context", "Local readiness requires a dispatch identity")
    manager = LocalLifecycleManager()
    last_error = None
    for _attempt in range(2):
        try:
            result = manager.ensure_ready()
            manager.record_reservation_started(dispatch_key)
            return result
        except LifecycleError as exc:
            last_error = exc
    if last_error is not None:
        try:
            from synlynk.local_failure_reporter import report_local_failure
            report_local_failure(last_error)
        except Exception:
            pass
        raise last_error
    raise LifecycleError("readiness_failed", "Local runtime readiness failed")


def _process_start_identity(pid: int) -> float | None:
    """Return a process start timestamp suitable for guarding against PID reuse."""
    env = {key: value for key, value in os.environ.items() if key != "OPENAI_API_KEY"}
    try:
        result = subprocess.run(["ps", "-o", "lstart=", "-p", str(pid)], check=True,
                                capture_output=True, text=True, timeout=5, env=env)
        parsed = datetime.strptime(result.stdout.strip(), "%a %b %d %H:%M:%S %Y")
        return parsed.timestamp()
    except Exception:
        return None


def _listening_process_identity() -> tuple[int, float] | None:
    env = {key: value for key, value in os.environ.items() if key != "OPENAI_API_KEY"}
    try:
        result = subprocess.run(["lsof", "-nP", "-tiTCP:8000", "-sTCP:LISTEN"],
                                check=True, capture_output=True, text=True, timeout=5, env=env)
        pids = [int(line.strip()) for line in result.stdout.splitlines() if line.strip().isdigit()]
        if len(pids) != 1:
            return None
        started = _process_start_identity(pids[0])
        return (pids[0], started) if started is not None else None
    except Exception:
        return None


def _probe_local_endpoint(endpoint: str = "http://127.0.0.1:8000") -> bool:
    parsed = urlsplit(endpoint)
    try:
        with socket.create_connection((parsed.hostname or "127.0.0.1", parsed.port or 80), timeout=1):
            return True
    except OSError:
        return False


def _run_omlx_command(action: str) -> None:
    if action not in {"start", "stop"}:
        raise LifecycleError("unsupported_omlx_command", "oMLX command is not allowed", phase="service")
    executable = shutil.which("omlx")
    if not executable:
        raise LifecycleError("omlx_not_installed", "oMLX executable is unavailable", phase="service")
    env = {key: value for key, value in os.environ.items() if key != "OPENAI_API_KEY"}
    try:
        subprocess.run([executable, action, "--timeout", "30"], check=True,
                       capture_output=True, text=True, timeout=40, env=env)
    except Exception:
        raise LifecycleError("omlx_service_command_failed", f"oMLX {action} command failed", phase="service") from None


class LocalLifecycleManager:
    """Host-global owner, reservation registry, and 15-minute idle supervisor."""

    def __init__(self, *, client=None, endpoint: str = "http://127.0.0.1:8000",
                 credential_store=None, state_path: str | None = None,
                 lock_path: str | None = None, endpoint_probe=None,
                 process_identity=None, start_service=None, stop_service=None,
                 clock=None, sleeper=None, process_identity_alive=None,
                 memory_admission=None, current_process_identity=None):
        from synlynk.local_credentials import LocalCredentialStore
        home = os.path.expanduser("~")
        app_support = os.path.join(home, "Library", "Application Support", "Synlynk")
        self.endpoint = endpoint
        self.credential_store = credential_store or LocalCredentialStore()
        self.client = client or OmlxClient(endpoint, self.credential_store)
        self.state_path = state_path or os.path.join(app_support, "local-runtime.json")
        self.lock_path = lock_path or os.path.join(app_support, "local-runtime.lock")
        self.endpoint_probe = endpoint_probe or (lambda: _probe_local_endpoint(endpoint))
        self.process_identity = process_identity or _listening_process_identity
        self.start_service = start_service or (lambda: _run_omlx_command("start"))
        self.stop_service = stop_service or (lambda: _run_omlx_command("stop"))
        self.clock = clock or time.time
        self.sleeper = sleeper or time.sleep
        self.process_identity_alive = process_identity_alive or self._identity_alive
        self.memory_admission = memory_admission or require_memory_admission
        self.current_process_identity = current_process_identity or self._current_process_identity

    def _identity_alive(self, pid: int, start: float) -> bool:
        return _process_start_identity(pid) == start

    def _current_process_identity(self) -> tuple[int, float]:
        pid = os.getpid()
        started = _process_start_identity(pid)
        if started is None:
            raise LifecycleError("process_identity_unavailable", "cannot safely reserve Local runtime", phase="ownership")
        return pid, started

    def _require_current_process_identity(self) -> tuple[int, float]:
        identity = self.current_process_identity()
        if not identity or len(identity) != 2:
            raise LifecycleError("process_identity_unavailable", "cannot safely reserve Local runtime", phase="ownership")
        return int(identity[0]), float(identity[1])

    @contextmanager
    def _locked(self):
        try:
            import fcntl
        except ImportError:
            raise LifecycleError("host_lock_unavailable", "host lifecycle lock is unavailable", phase="ownership")
        os.makedirs(os.path.dirname(self.lock_path), mode=0o700, exist_ok=True)
        fd = os.open(self.lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    def _read_state(self) -> dict:
        try:
            with open(self.state_path, encoding="utf-8") as stream:
                value = json.load(stream)
            return value if isinstance(value, dict) else {}
        except FileNotFoundError:
            return {}
        except Exception:
            raise LifecycleError("ownership_state_invalid", "Local lifecycle ownership state is unreadable", phase="ownership") from None

    def _write_state(self, state: dict) -> None:
        os.makedirs(os.path.dirname(self.state_path), mode=0o700, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=".local-runtime-", dir=os.path.dirname(self.state_path))
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(state, stream, sort_keys=True)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.state_path)
        finally:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass

    def _reconcile_jobs(self, state: dict) -> dict:
        for registry_name in ("active_jobs", "active_reservations"):
            records = state.get(registry_name) or {}
            alive = {}
            for record_id, identity in records.items():
                try:
                    if self.process_identity_alive(int(identity["pid"]), float(identity["process_start"])):
                        alive[record_id] = identity
                except Exception:
                    # Unknown process identity means retain the reservation and fail closed.
                    alive[record_id] = identity
            state[registry_name] = alive
        return state

    def _owned_identity(self, state: dict) -> dict | None:
        ownership = state.get("ownership")
        if not ownership:
            return None
        try:
            current = self.process_identity()
            expected = (int(ownership["pid"]), float(ownership["process_start"]))
            if current == expected:
                return ownership
        except Exception:
            pass
        return None

    def _wait_for_endpoint(self, attempts: int = 30) -> bool:
        for _ in range(attempts):
            if self.endpoint_probe():
                return True
            self.sleeper(1)
        return False

    def _wait_for_model(self, model_id: str, attempts: int = 30) -> bool:
        for _ in range(attempts):
            if model_id in self.client.list_models():
                return True
            self.sleeper(1)
        return False

    def ensure_ready(self) -> LocalRuntimeResult:
        if sys.platform != "darwin":
            raise LifecycleError("unsupported_platform", "automatic Local lifecycle requires macOS", phase="service")
        with self._locked():
            state = self._reconcile_jobs(self._read_state())
            endpoint_running = self.endpoint_probe()
            ownership = self._owned_identity(state)
            if endpoint_running:
                models = self.client.list_models()
                if LIFECYCLE_MODEL_ID in models:
                    managed = ownership is not None
                    if managed:
                        state["last_activity"] = float(self.clock())
                        state["model_id"] = LIFECYCLE_MODEL_ID
                        self._write_state(state)
                    return LocalRuntimeResult(True, LIFECYCLE_MODEL_ID, managed,
                                             ownership.get("pid") if managed else None)
                if ownership is None:
                    raise LifecycleError("operator_owned_model_missing", "operator-owned oMLX is running without the approved Ornith model", phase="inventory")
                self.memory_admission()
                self.client.load_model(LIFECYCLE_MODEL_ID)
                if not self._wait_for_model(LIFECYCLE_MODEL_ID):
                    raise LifecycleError("model_not_ready", "approved Ornith model did not become ready", phase="model")
                state["model_id"] = LIFECYCLE_MODEL_ID
                state["last_activity"] = float(self.clock())
                self._write_state(state)
                return LocalRuntimeResult(True, LIFECYCLE_MODEL_ID, True, ownership.get("pid"))

            # A stale ownership record must not authorize control of a process
            # whose PID/start identity no longer matches.
            if ownership is None:
                state.pop("ownership", None)
            self.memory_admission()
            self.client.installed_version()
            requested_at = float(self.clock())
            self.start_service()
            if not self._wait_for_endpoint():
                raise LifecycleError("omlx_start_timeout", "oMLX did not become reachable after start", phase="service")
            identity = self.process_identity()
            if not identity or float(identity[1]) < requested_at:
                raise LifecycleError("ownership_ambiguous", "cannot prove Synlynk owns the started oMLX process", phase="ownership")
            pid, process_start = int(identity[0]), float(identity[1])
            ownership = {
                "pid": pid,
                "process_start": process_start,
                "generation": uuid.uuid4().hex,
                "model_id": LIFECYCLE_MODEL_ID,
            }
            state.update({"ownership": ownership, "last_activity": requested_at,
                          "model_id": LIFECYCLE_MODEL_ID,
                          "active_jobs": state.get("active_jobs", {}),
                          "active_reservations": state.get("active_reservations", {})})
            self._write_state(state)
            self.memory_admission()
            self.client.load_model(LIFECYCLE_MODEL_ID)
            if not self._wait_for_model(LIFECYCLE_MODEL_ID):
                raise LifecycleError("model_not_ready", "approved Ornith model did not become ready", phase="model")
            return LocalRuntimeResult(True, LIFECYCLE_MODEL_ID, True, pid)

    def record_job_started(self, job_id: str, *, pid: int | None = None) -> None:
        with self._locked():
            state = self._reconcile_jobs(self._read_state())
            if pid is None:
                pid, process_start = self._require_current_process_identity()
            else:
                process_start = _process_start_identity(int(pid))
                if process_start is None:
                    raise LifecycleError("process_identity_unavailable", "cannot safely track Local job", phase="ownership")
            state.setdefault("active_jobs", {})[job_id] = {
                "pid": int(pid),
                "process_start": process_start,
            }
            state["last_activity"] = float(self.clock())
            self._write_state(state)

    def record_job_finished(self, job_id: str) -> None:
        with self._locked():
            state = self._reconcile_jobs(self._read_state())
            state.setdefault("active_jobs", {}).pop(job_id, None)
            state["last_activity"] = float(self.clock())
            self._write_state(state)

    def record_reservation_started(self, reservation_id: str) -> None:
        with self._locked():
            state = self._reconcile_jobs(self._read_state())
            pid, process_start = self._require_current_process_identity()
            state.setdefault("active_reservations", {})[reservation_id] = {
                "pid": pid,
                "process_start": process_start,
            }
            state["last_activity"] = float(self.clock())
            self._write_state(state)

    def record_reservation_finished(self, reservation_id: str) -> None:
        with self._locked():
            state = self._reconcile_jobs(self._read_state())
            state.setdefault("active_reservations", {}).pop(reservation_id, None)
            self._write_state(state)

    def _stop_if_safe(self, state: dict) -> bool:
        ownership = self._owned_identity(state)
        if ownership is None:
            return False
        reconciled = self._reconcile_jobs(state)
        if reconciled.get("active_jobs") or reconciled.get("active_reservations"):
            return False
        try:
            if LIFECYCLE_MODEL_ID in self.client.list_models():
                self.client.unload_model(LIFECYCLE_MODEL_ID)
            # Revalidate PID and start identity immediately before stop.
            if self._owned_identity(state) is None:
                return False
            self.stop_service()
            state.pop("ownership", None)
            state.pop("model_id", None)
            state["active_jobs"] = {}
            self._write_state(state)
            return True
        except LifecycleError:
            raise
        except Exception:
            raise LifecycleError("omlx_stop_failed", "could not safely stop Synlynk-managed oMLX", phase="idle_shutdown") from None

    def tick(self, now: float | None = None) -> None:
        with self._locked():
            state = self._reconcile_jobs(self._read_state())
            self._write_state(state)
            if state.get("active_jobs") or state.get("active_reservations") or not state.get("ownership"):
                return
            last_activity = float(state.get("last_activity", self.clock()))
            if float(self.clock() if now is None else now) - last_activity < IDLE_TIMEOUT_SECONDS:
                return
            self._stop_if_safe(state)

    def stop_managed_service(self) -> bool:
        with self._locked():
            state = self._reconcile_jobs(self._read_state())
            if state.get("active_jobs") or state.get("active_reservations"):
                raise LifecycleError("local_jobs_active", "cannot stop oMLX while Local jobs or reservations are active", phase="idle_shutdown")
            return self._stop_if_safe(state)

    def status(self) -> dict:
        with self._locked():
            state = self._reconcile_jobs(self._read_state())
            ownership = self._owned_identity(state)
            running = bool(self.endpoint_probe())
            loaded = None
            if running:
                try:
                    loaded = LIFECYCLE_MODEL_ID in self.client.list_models()
                except LifecycleError:
                    loaded = None
            try:
                credential_configured = self.credential_store.is_configured()
            except Exception:
                credential_configured = False
            now = float(self.clock())
            last = float(state.get("last_activity", now))
            return {
                "running": running,
                "model_id": LIFECYCLE_MODEL_ID if loaded else state.get("model_id"),
                "model_loaded": loaded,
                "credential_configured": credential_configured,
                "managed": ownership is not None,
                "owner_pid": ownership.get("pid") if ownership else None,
                "active_jobs": len(state.get("active_jobs", {})),
                "active_reservations": len(state.get("active_reservations", {})),
                "idle_seconds": max(0, int(now - last)) if ownership else None,
                "idle_timeout_seconds": IDLE_TIMEOUT_SECONDS,
            }
