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


def _active_claims_path() -> str:
    return os.path.join(".synlynk", "active_claims.json")


def _read_active_claim_leases() -> dict:
    """Returns {story_id: lease_id} for every story this checkout has claimed.

    lease_id binds the marker to the exact lease row it was issued for, so a
    later heartbeat can refuse to renew a *different* lease that now holds
    the same story_id (e.g. after another session force-took it via
    --override) instead of silently extending the new claimant's lease
    (found by cross-harness review on PR #2524).
    """
    path = _active_claims_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}
    return data.get("claims", {})


def _read_active_claims() -> list:
    """Returns the list of story_ids this checkout has claimed via `synlynk story claim`."""
    return list(_read_active_claim_leases().keys())


def _add_active_claim(story_id: str, lease_id: str) -> None:
    claims = _read_active_claim_leases()
    claims[story_id] = lease_id
    os.makedirs(".synlynk", exist_ok=True)
    with open(_active_claims_path(), "w") as f:
        json.dump({"claims": claims}, f)


def _remove_active_claim(story_id: str) -> None:
    claims = _read_active_claim_leases()
    claims.pop(story_id, None)
    os.makedirs(".synlynk", exist_ok=True)
    with open(_active_claims_path(), "w") as f:
        json.dump({"claims": claims}, f)
