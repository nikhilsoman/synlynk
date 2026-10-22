"""Safe capture and termination of dispatch-owned process domains."""

from __future__ import annotations

import os
import signal
import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from synlynk.container_exec import inspect_container as _inspect_container
from synlynk.container_exec import stop_container as _stop_container


def capture_process_identity(pid: int, process=None):
    from synlynk.sentinel import capture_process_identity as capture

    return capture(pid, process)


@dataclass(frozen=True)
class TerminationResult:
    process_state: str
    attempted: bool
    method: str
    reason_code: str
    evidence: tuple[Mapping[str, Any], ...] = ()


def _unknown_domain(reason_code: str, *, proc=None, parent_job_id=None, **extra) -> dict:
    return {
        "version": 1,
        "kind": "unknown",
        "leader_pid": getattr(proc, "pid", None),
        "parent_job_id": parent_job_id,
        "reason_code": reason_code,
        **extra,
    }


def capture_termination_domain(
    proc,
    *,
    container_id: str | None = None,
    parent_job_id: str | None = None,
) -> dict:
    """Capture immutable launch identity before a job is treated as running."""
    try:
        if proc.poll() is not None:
            return _unknown_domain(
                "leader_already_exited", proc=proc, parent_job_id=parent_job_id
            )
    except (AttributeError, OSError):
        pass

    pid = getattr(proc, "pid", None)
    if isinstance(pid, bool) or not isinstance(pid, int) or pid in (0, 1) or pid < 0:
        return _unknown_domain("unsafe_leader_pid", proc=proc, parent_job_id=parent_job_id)
    identity = capture_process_identity(pid, proc)

    if container_id is not None:
        if not str(container_id).strip():
            return _unknown_domain(
                "container_identity_unavailable",
                proc=proc,
                parent_job_id=parent_job_id,
                leader_identity=identity,
            )
        return {
            "version": 1,
            "kind": "container",
            "container_id": str(container_id).strip(),
            "leader_pid": pid,
            "leader_identity": identity,
            "parent_job_id": parent_job_id,
        }

    if os.name != "posix" or not hasattr(os, "getpgid"):
        return _unknown_domain(
            "unsupported_platform",
            proc=proc,
            parent_job_id=parent_job_id,
            leader_identity=identity,
        )
    if not identity:
        return _unknown_domain(
            "leader_identity_unavailable", proc=proc, parent_job_id=parent_job_id
        )
    try:
        pgid = os.getpgid(pid)
        dispatcher_pgid = os.getpgrp()
    except (OSError, ValueError):
        return _unknown_domain(
            "process_group_capture_failed",
            proc=proc,
            parent_job_id=parent_job_id,
            leader_identity=identity,
        )
    if pgid in (0, 1) or pgid == dispatcher_pgid:
        return _unknown_domain(
            "unsafe_process_group",
            proc=proc,
            parent_job_id=parent_job_id,
            leader_identity=identity,
            pgid=pgid,
            dispatcher_pgid=dispatcher_pgid,
        )
    return {
        "version": 1,
        "kind": "host_process_group",
        "leader_pid": pid,
        "leader_identity": identity,
        "pgid": pgid,
        "dispatcher_pgid": dispatcher_pgid,
        "parent_job_id": parent_job_id,
    }


def _default_inspect_process_group(domain: Mapping[str, Any]) -> dict[str, Any]:
    pid = domain.get("leader_pid")
    pgid = domain.get("pgid")
    expected = domain.get("leader_identity") or {}
    try:
        current = capture_process_identity(int(pid))
    except (TypeError, ValueError):
        return {"state": "error", "reason": "invalid_leader_pid"}
    if current:
        expected_start = expected.get("start_time")
        expected_command = expected.get("command")
        if expected_start and current.get("start_time") != expected_start:
            return {"state": "identity_mismatch", "identity_match": False}
        if expected_command and expected_command not in current.get("command", ""):
            return {"state": "identity_mismatch", "identity_match": False}
    try:
        os.killpg(int(pgid), 0)
    except ProcessLookupError:
        return {"state": "stopped", "identity_match": True}
    except (PermissionError, OSError, TypeError, ValueError) as exc:
        return {"state": "error", "reason": type(exc).__name__}
    if current:
        return {"state": "running", "identity_match": True}
    if pid == pgid:
        return {"state": "running", "identity_match": True, "leader_exited": True}
    return {"state": "error", "reason": "leader_identity_unverifiable"}


def _default_signal_process_group(pgid: int, sig: int) -> None:
    os.killpg(pgid, sig)


def _observation(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if value is True:
        return {"state": "running", "identity_match": True}
    if value is False:
        return {"state": "stopped", "identity_match": True}
    return {"state": "error", "reason": "invalid_inspection_result"}


def _result(
    process_state: str,
    attempted: bool,
    method: str,
    reason_code: str,
    evidence: list[Mapping[str, Any]],
) -> TerminationResult:
    return TerminationResult(
        process_state=process_state,
        attempted=attempted,
        method=method,
        reason_code=reason_code,
        evidence=tuple(dict(item) for item in evidence),
    )


def terminate_job_domain(
    domain: Mapping[str, Any],
    *,
    grace_seconds: float = 5.0,
    inspect_process_group: Callable[[Mapping[str, Any]], Any] | None = None,
    signal_process_group: Callable[[int, int], None] | None = None,
    stop_container: Callable[[str, float], Any] | None = None,
    inspect_container: Callable[[str], Any] | None = None,
    sleep: Callable[[float], None] | None = None,
    platform_name: str | None = None,
    signal_process: Callable[[int, int], None] | None = None,
) -> TerminationResult:
    """Stop an owned domain and report success only after observing it stopped."""
    inspect_process_group = inspect_process_group or _default_inspect_process_group
    signal_process_group = signal_process_group or _default_signal_process_group
    stop_container = stop_container or _stop_container
    inspect_container = inspect_container or _inspect_container
    sleep = sleep or time.sleep
    signal_process = signal_process or os.kill
    evidence: list[Mapping[str, Any]] = []
    kind = domain.get("kind")
    grace = max(0.0, float(grace_seconds))
    if domain.get("version") != 1:
        return _result("cleanup_unverified", False, "none", "unsupported_domain_version", evidence)

    if kind == "container":
        container_id = str(domain.get("container_id") or "").strip()
        if not container_id:
            return _result("cleanup_unverified", False, "container", "container_identity_unavailable", evidence)
        before = _observation(inspect_container(container_id))
        evidence.append({"phase": "before_stop", **before})
        if before.get("state") == "stopped":
            return _result("stopped_verified", False, "container", "already_stopped", evidence)
        if before.get("state") != "running":
            return _result("cleanup_unverified", False, "container", "inspection_error", evidence)
        try:
            stop_container(container_id, grace)
        except Exception as exc:
            evidence.append({"phase": "stop", "state": "error", "reason": type(exc).__name__})
            return _result("cleanup_unverified", True, "container", "container_stop_failed", evidence)
        after = _observation(inspect_container(container_id))
        evidence.append({"phase": "after_stop", **after})
        if after.get("state") == "stopped":
            return _result("stopped_verified", True, "container", "container_stopped", evidence)
        return _result("cleanup_unverified", True, "container", "container_still_running", evidence)

    if kind == "legacy_process":
        pid = domain.get("leader_pid")
        if isinstance(pid, bool) or not isinstance(pid, int) or pid in (0, 1) or pid < 0:
            return _result("cleanup_unverified", False, "legacy_process", "unsafe_leader_pid", evidence)
        if not domain.get("identity_verified"):
            return _result("cleanup_unverified", False, "legacy_process", "leader_identity_unverified", evidence)
        try:
            signal_process(pid, signal.SIGTERM)
            if grace:
                sleep(grace)
            signal_process(pid, 0)
            signal_process(pid, signal.SIGKILL)
        except ProcessLookupError:
            return _result("cleanup_unverified", True, "legacy_process", "leader_stopped_descendants_unknown", evidence)
        except Exception as exc:
            evidence.append({"phase": "legacy_signal", "state": "error", "reason": type(exc).__name__})
            return _result("cleanup_unverified", True, "legacy_process", "legacy_cleanup_unverified", evidence)
        return _result("cleanup_unverified", True, "legacy_process", "descendants_unverified", evidence)

    if kind != "host_process_group":
        return _result("cleanup_unverified", False, "none", str(domain.get("reason_code") or "unknown_domain"), evidence)
    if (platform_name or os.name) != "posix":
        return _result("cleanup_unverified", False, "host_process_group", "unsupported_platform", evidence)

    pid = domain.get("leader_pid")
    pgid = domain.get("pgid")
    dispatcher_pgid = domain.get("dispatcher_pgid")
    unsafe = (
        isinstance(pid, bool)
        or isinstance(pgid, bool)
        or not isinstance(pid, int)
        or not isinstance(pgid, int)
        or pid in (0, 1)
        or pgid in (0, 1)
        or pgid == dispatcher_pgid
        or pgid == os.getpgrp()
    )
    if unsafe:
        return _result("cleanup_unverified", False, "host_process_group", "unsafe_process_group", evidence)

    before = _observation(inspect_process_group(domain))
    evidence.append({"phase": "before_signal", **before})
    if before.get("state") == "stopped":
        return _result("stopped_verified", False, "host_process_group", "already_stopped", evidence)
    if before.get("state") == "identity_mismatch" or before.get("identity_match") is False:
        return _result("cleanup_unverified", False, "host_process_group", "leader_identity_mismatch", evidence)
    if before.get("state") != "running":
        return _result("cleanup_unverified", False, "host_process_group", "inspection_error", evidence)

    try:
        signal_process_group(pgid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    except Exception as exc:
        evidence.append({"phase": "sigterm", "state": "error", "reason": type(exc).__name__})
        return _result("cleanup_unverified", True, "host_process_group", "signal_failed", evidence)
    if grace:
        sleep(grace)
    after_term = _observation(inspect_process_group(domain))
    evidence.append({"phase": "after_sigterm", **after_term})
    if after_term.get("state") == "stopped":
        return _result("stopped_verified", True, "host_process_group", "graceful_stop_verified", evidence)
    if after_term.get("state") != "running" or after_term.get("identity_match") is False:
        reason = "leader_identity_mismatch" if after_term.get("identity_match") is False else "inspection_error"
        return _result("cleanup_unverified", True, "host_process_group", reason, evidence)

    try:
        signal_process_group(pgid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    except Exception as exc:
        evidence.append({"phase": "sigkill", "state": "error", "reason": type(exc).__name__})
        return _result("cleanup_unverified", True, "host_process_group", "signal_failed", evidence)
    after_kill = _observation(inspect_process_group(domain))
    evidence.append({"phase": "after_sigkill", **after_kill})
    if after_kill.get("state") == "stopped":
        return _result("stopped_verified", True, "host_process_group", "forced_stop_verified", evidence)
    return _result("cleanup_unverified", True, "host_process_group", "termination_unverified", evidence)
