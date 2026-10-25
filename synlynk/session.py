"""Active-session marker file: which session is open in this working directory.

Mirrors the existing .synlynk/config.json / .synlynk/telemetry.json file-marker
convention rather than introducing a new state mechanism. Single active session
per working directory — concurrent dispatch across worktrees races on this file
(documented gap, see plan header).
"""

import json
import os


def _active_session_path() -> str:
    return os.path.join(".synlynk", "active_session.json")


def _read_active_session() -> str:
    """Returns the open session_id, or None if no session is active."""
    path = _active_session_path()
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None
    return data.get("session_id")


def _write_active_session(session_id: str) -> None:
    os.makedirs(".synlynk", exist_ok=True)
    with open(_active_session_path(), "w") as f:
        json.dump({"session_id": session_id}, f)


def _clear_active_session() -> None:
    path = _active_session_path()
    if os.path.exists(path):
        os.remove(path)


import fcntl
from contextlib import contextmanager

from synlynk import _write_json_atomic


def _active_claims_path() -> str:
    return os.path.join(".synlynk", "active_claims.json")


@contextmanager
def _claims_lock():
    path = _active_claims_path()
    lock_path = f"{path}.lock"
    os.makedirs(os.path.dirname(os.path.abspath(lock_path)), exist_ok=True)
    handle = open(lock_path, "a+")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        except Exception:
            pass
        try:
            handle.close()
        except Exception:
            pass


def _read_active_claim_leases_unlocked() -> dict:
    path = _active_claims_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}
    return data.get("claims", {})


def _read_active_claim_leases() -> dict:
    """Returns {story_id: lease_id} for every story this checkout has claimed."""
    with _claims_lock():
        return _read_active_claim_leases_unlocked()


def _read_active_claims() -> list:
    """Returns the list of story_ids this checkout has claimed via `synlynk story claim`."""
    return list(_read_active_claim_leases().keys())


def _add_active_claim(story_id: str, lease_id: str) -> None:
    with _claims_lock():
        claims = _read_active_claim_leases_unlocked()
        claims[story_id] = lease_id
        os.makedirs(".synlynk", exist_ok=True)
        _write_json_atomic(_active_claims_path(), {"claims": claims})


def _remove_active_claim(story_id: str) -> None:
    with _claims_lock():
        claims = _read_active_claim_leases_unlocked()
        claims.pop(story_id, None)
        os.makedirs(".synlynk", exist_ok=True)
        _write_json_atomic(_active_claims_path(), {"claims": claims})
