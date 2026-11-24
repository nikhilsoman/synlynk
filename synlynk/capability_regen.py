"""Regenerate the empirical capability fields in ``.synlynk/policy.json``."""

from __future__ import annotations

import difflib
import json
import os
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from synlynk.routing import SAMPLE_SIZE_FLOOR, is_calibrated


_REWRITTEN_FIELDS = (
    "calibration_detail",
    "not_yet_calibrated",
    "note",
    "eligibility",
)


def _json_bool(value) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "verified", "passed"}:
        return True
    if normalized in {"0", "false", "no", "unverified", "failed"}:
        return False
    return None


def _policy_fields(policy: dict) -> dict:
    capability = policy.get("capability_policy")
    if not isinstance(capability, dict):
        capability = {}
        policy["capability_policy"] = capability
    return capability


def _load_policy(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"malformed existing policy.json: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"malformed existing policy.json: {path}: root must be an object")
    return value


def _gh_write_states(conn: sqlite3.Connection, harnesses: Iterable[str]) -> dict[str, bool | str]:
    columns = {row[1] for row in conn.execute("PRAGMA table_info(daemon_jobs)")}
    if "daemon_jobs" not in {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}:  # noqa: E501
        return {harness: False for harness in harnesses}
    identity = "COALESCE(NULLIF(harness, ''), NULLIF(actual_harness, ''), agent)"
    required = "requires_gh_write" if "requires_gh_write" in columns else "0"
    verified = "gh_write_verified" if "gh_write_verified" in columns else "NULL"
    query = f"SELECT {identity}, {required}, {verified} FROM daemon_jobs"
    states: dict[str, list[bool | None]] = {harness: [] for harness in harnesses}
    for harness, required_value, verified_value in conn.execute(query):
        if not _json_bool(required_value):
            continue
        if harness in states:
            states[harness].append(_json_bool(verified_value))
    result: dict[str, bool | str] = {}
    for harness, values in states.items():
        if any(value is True for value in values):
            result[harness] = True
        elif values and all(value is False for value in values):
            result[harness] = False
        elif values:
            result[harness] = "unproven"
        else:
            result[harness] = False
    return result


def _task_types_from_policy(policy: dict) -> list[str]:
    allocation = (
        policy.get("overrides", {})
        .get("dev_authority", {})
        .get("task_allocation", {})
    )
    return list(allocation) if isinstance(allocation, dict) else []


def _harnesses_from_policy(policy: dict) -> list[str]:
    capability = _policy_fields(policy)
    eligibility = capability.get("eligibility", {})
    names = list(eligibility) if isinstance(eligibility, dict) else []
    for task in _task_types_from_policy(policy):
        entry = policy["overrides"]["dev_authority"]["task_allocation"][task]
        if isinstance(entry, dict):
            for name in [entry.get("harness"), *entry.get("fallback", [])]:
                if name and name not in names:
                    names.append(name)
    return names


def _note(detail: dict[str, dict[str, bool]], timestamp: str) -> str:
    counts = ", ".join(
        f"{harness}: calibrated on {sum(values.values())}/{len(values)} task_types"
        for harness, values in detail.items()
    )
    return f"Generated from canonical state.db at {timestamp}; {counts}."


def _atomic_write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    finally:
        try:
            os.unlink(name)
        except FileNotFoundError:
            pass


def _canonical_state_db() -> Path:
    from synlynk.product_store import identity_slug_from_config
    from synlynk.state_registry import registered_canonical_path
    from synlynk import _project_root

    slug = identity_slug_from_config(_project_root())
    path = registered_canonical_path(slug)
    if path is None or not path.is_file():
        raise RuntimeError(f"canonical state.db cannot be resolved for product {slug!r}")
    return path


def regenerate_capability_policy(
    *,
    db_path: str | Path | None = None,
    policy_path: str | Path = ".synlynk/policy.json",
    harnesses: Iterable[str] | None = None,
    task_types: Iterable[str] | None = None,
    dry_run: bool = False,
) -> dict:
    """Regenerate only capability-derived policy values and return the result."""
    database = Path(db_path) if db_path is not None else _canonical_state_db()
    if not database.is_file():
        raise RuntimeError(f"canonical state.db does not exist: {database}")
    target = Path(policy_path)
    policy = _load_policy(target)
    names = list(harnesses) if harnesses is not None else _harnesses_from_policy(policy)
    tasks = list(task_types) if task_types is not None else _task_types_from_policy(policy)

    try:
        conn = sqlite3.connect(database, timeout=1.0)
        conn.execute("PRAGMA busy_timeout = 1000")
        detail = {harness: {task: is_calibrated(harness, task, conn) for task in tasks} for harness in names}
        gh_states = _gh_write_states(conn, names)
    except sqlite3.OperationalError as exc:
        raise RuntimeError(f"could not read canonical state.db (it may be locked): {exc}") from exc
    finally:
        if "conn" in locals():
            conn.close()

    capability = _policy_fields(policy)
    capability["calibration_detail"] = detail
    capability["not_yet_calibrated"] = sorted(h for h, values in detail.items() if not any(values.values()))
    capability["note"] = _note(detail, datetime.now(timezone.utc).isoformat())
    eligibility = capability.setdefault("eligibility", {})
    for harness, state in gh_states.items():
        entry = eligibility.setdefault(harness, {})
        if not isinstance(entry, dict):
            entry = {}
            eligibility[harness] = entry
        entry["can_gh_write"] = state

    if dry_run:
        before = {key: _policy_fields(_load_policy(target)).get(key) for key in _REWRITTEN_FIELDS}
        after = {key: capability.get(key) for key in _REWRITTEN_FIELDS}
        diff = difflib.unified_diff(
            json.dumps(before, indent=2, sort_keys=True).splitlines(),
            json.dumps(after, indent=2, sort_keys=True).splitlines(),
            fromfile=f"{target} (current)", tofile=f"{target} (proposed)", lineterm="",
        )
        print("\n".join(diff))
        return policy
    _atomic_write(target, policy)
    return policy


def cmd_capability_regen(*, dry_run: bool = False) -> int:
    regenerate_capability_policy(dry_run=dry_run)
    if not dry_run:
        print("Regenerated capability policy from canonical state.db.")
    return 0
