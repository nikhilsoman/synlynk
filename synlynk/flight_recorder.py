"""Best-effort local ring buffer of recent CLI invocations."""
from __future__ import annotations

import fcntl
import json
import time
from pathlib import Path

CAP = 50


def _enabled(root: Path) -> bool:
    config_path = root / ".synlynk" / "config.json"
    try:
        return json.loads(config_path.read_text()).get("flight_recorder", True) is not False
    except Exception:
        return True


def _append(path: Path, line: str) -> None:
    with path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        handle.seek(0)
        lines = handle.read().splitlines()
        handle.seek(0)
        handle.truncate()
        handle.write("\n".join([*lines, line][-CAP:]) + "\n")


def _flag_names(flags: list[str]) -> list[str]:
    return [flag.split("=", 1)[0] for flag in flags if flag.startswith("-")]


def record(
    root,
    command: str,
    flags: list[str],
    exit_code: int,
    duration: float,
    error: str,
) -> None:
    """Record one invocation without creating state or surfacing failures."""
    try:
        root = Path(root)
        if not (root / ".synlynk").is_dir() or not _enabled(root):
            return

        from synlynk.logs import _redact_secret_patterns
        from synlynk.report_scan import find_secrets

        error_line = _redact_secret_patterns(error.splitlines()[0] if error else "")
        if find_secrets(error_line):
            error_line = "[redacted]"
        payload = {
            "ts": int(time.time()),
            "command": command,
            "flags": _flag_names(flags),
            "exit_code": exit_code,
            "duration": round(duration, 3),
            "error": error_line,
            "failed": exit_code != 0,
        }
        _append(root / ".synlynk" / "flight.jsonl", json.dumps(payload))
    except Exception:
        pass


def last_failed(root) -> dict | None:
    """Return the newest failed invocation, if the buffer can be read."""
    try:
        path = Path(root) / ".synlynk" / "flight.jsonl"
        for line in reversed(path.read_text(encoding="utf-8").splitlines()):
            payload = json.loads(line)
            if payload.get("failed"):
                return payload
    except Exception:
        pass
    return None


def clear(root) -> None:
    """Remove the buffer, swallowing missing-file and filesystem failures."""
    try:
        (Path(root) / ".synlynk" / "flight.jsonl").unlink()
    except Exception:
        pass
