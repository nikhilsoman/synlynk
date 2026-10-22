"""Redacted, deduplicated control-plane reporting for Local runtime failures."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
from contextlib import contextmanager

from synlynk.local_lifecycle import LifecycleError, LIFECYCLE_MODEL_ID, _host_subprocess_env

REPORT_INTERVAL_SECONDS = 3600


def _state_path() -> str:
    return os.path.join(
        os.path.expanduser("~"), "Library", "Application Support", "Synlynk",
        "local-failure-outbox.json",
    )


@contextmanager
def _locked(path: str):
    import fcntl

    lock_path = path + ".lock"
    os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def _fingerprint(error: LifecycleError, version: str = "unknown") -> str:
    material = "\0".join((error.phase, error.reason_code, version, LIFECYCLE_MODEL_ID))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _read(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as stream:
            value = json.load(stream)
        return value if isinstance(value, dict) else {}
    except FileNotFoundError:
        return {}
    except Exception:
        return {}


def _write(path: str, value: dict) -> None:
    os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
    temporary = path + ".tmp"
    fd = os.open(temporary, os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def _write_issue(fingerprint: str, error: LifecycleError, version: str) -> bool:
    """Use the host's normal gh identity; callers in the Local container never invoke this."""
    title = f"[local-runtime] {error.phase}: {error.reason_code} ({fingerprint[:12]})"
    body = (
        "Synlynk Local runtime readiness failed twice.\n\n"
        f"- Fingerprint: `{fingerprint}`\n"
        f"- Phase: `{error.phase}`\n"
        f"- Reason: `{error.reason_code}`\n"
        f"- oMLX version: `{version}`\n"
        f"- Approved model: `{LIFECYCLE_MODEL_ID}`\n"
    )
    env = _host_subprocess_env()
    search = subprocess.run(
        ["gh", "issue", "list", "--search", fingerprint[:12], "--state", "open",
         "--json", "number,title", "--limit", "20"],
        capture_output=True, text=True, timeout=20, env=env,
    )
    if search.returncode == 0:
        try:
            matches = [item for item in json.loads(search.stdout)
                       if fingerprint[:12] in item.get("title", "")]
        except Exception:
            matches = []
        if matches:
            result = subprocess.run(
                ["gh", "issue", "comment", str(matches[0]["number"]), "--body", body],
                capture_output=True, text=True, timeout=20, env=env,
            )
            return result.returncode == 0
    result = subprocess.run(
        ["gh", "issue", "create", "--title", title, "--body", body,
         "--label", "bug,local-runtime"], capture_output=True, text=True,
        timeout=20, env=env,
    )
    return result.returncode == 0


def report_local_failure(error: LifecycleError, *, path: str | None = None,
                         version: str = "unknown", now: float | None = None,
                         issue_writer=None) -> bool:
    """Record a rate-limited failure; retain only safe fields in offline outbox."""
    path = path or _state_path()
    now = time.time() if now is None else now
    fingerprint = _fingerprint(error, version)
    with _locked(path):
        state = _read(path)
        prior = state.get(fingerprint) or {}
        if prior and now - float(prior.get("last_attempt", 0)) < REPORT_INTERVAL_SECONDS:
            return False
        event = {
            "fingerprint": fingerprint, "phase": error.phase,
            "reason_code": error.reason_code, "version": version,
            "model_id": LIFECYCLE_MODEL_ID, "last_attempt": now,
        }
        writer = issue_writer or _write_issue
        try:
            sent = bool(writer(fingerprint, error, version))
        except Exception:
            sent = False
        event["outbox"] = not sent
        state[fingerprint] = event
        _write(path, state)
        return sent


def retry_pending_local_failures(*, path: str | None = None, now: float | None = None,
                                 issue_writer=None) -> int:
    """Retry one due outbox entry per daemon tick, serializing GitHub dedupe."""
    path = path or _state_path()
    now = time.time() if now is None else now
    writer = issue_writer or _write_issue
    with _locked(path):
        state = _read(path)
        for fingerprint, event in state.items():
            if not isinstance(event, dict) or event.get("outbox") is not True:
                continue
            if now - float(event.get("last_attempt", 0)) < REPORT_INTERVAL_SECONDS:
                continue
            error = LifecycleError(
                str(event.get("reason_code", "readiness_failed")),
                "Local runtime readiness failed",
                phase=str(event.get("phase", "readiness")),
            )
            try:
                sent = bool(writer(fingerprint, error, str(event.get("version", "unknown"))))
            except Exception:
                sent = False
            event["last_attempt"] = now
            event["outbox"] = not sent
            _write(path, state)
            return int(sent)
    return 0


def outbox_status(*, path: str | None = None) -> dict:
    """Return counts only; never expose raw error text or credentials."""
    state = _read(path or _state_path())
    pending = sum(1 for item in state.values()
                  if isinstance(item, dict) and item.get("outbox") is True)
    return {"pending": pending, "tracked": len(state)}
