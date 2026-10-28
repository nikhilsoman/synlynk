"""Machine-scoped Vizor heartbeat store.

The database lives under the Vizor daemon home, not in a workspace state.db.
Only the literal harness value ``vizor`` is legal.
"""
from __future__ import annotations

import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Union

HARNESS = "vizor"
STATUSES = frozenset({"running", "stale", "stopped"})

BeatTime = Union[datetime, str]


def heartbeats_path(home: Path) -> Path:
    return Path(home) / "heartbeats.db"


def daemon_id(home: Path) -> str:
    """Return the stable id for this daemon home, creating it once."""
    path = Path(home) / "daemon_id"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        existing = path.read_text(encoding="utf-8").strip()
        if existing:
            return existing
    value = str(uuid.uuid4())
    path.write_text(value + "\n", encoding="utf-8")
    return value


def open_heartbeats(home: Path) -> sqlite3.Connection:
    """Open the heartbeat database and create the table when it is missing."""
    root = Path(home)
    root.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(heartbeats_path(root))
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS daemon_heartbeats (
            daemon_id TEXT PRIMARY KEY,
            pid INTEGER NOT NULL,
            harness TEXT NOT NULL,
            status TEXT NOT NULL,
            last_beat_at TEXT NOT NULL,
            cycle_count INTEGER NOT NULL,
            active_task TEXT
        )
        """
    )
    conn.commit()
    return conn


def upsert_beat(
    home: Path,
    *,
    pid: int,
    status: str,
    last_beat_at: BeatTime,
    cycle_count: int,
    active_task: Optional[str],
    harness: str = HARNESS,
) -> None:
    """Replace the single heartbeat row for this daemon home."""
    if harness != HARNESS:
        raise ValueError(f"harness must be {HARNESS!r}")
    if status not in STATUSES:
        raise ValueError(f"status must be one of {sorted(STATUSES)}")
    stamp = _format_time(last_beat_at)
    identity = daemon_id(home)
    conn = open_heartbeats(home)
    try:
        conn.execute(
            """
            INSERT INTO daemon_heartbeats (
                daemon_id, pid, harness, status, last_beat_at, cycle_count, active_task
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(daemon_id) DO UPDATE SET
                pid = excluded.pid,
                harness = excluded.harness,
                status = excluded.status,
                last_beat_at = excluded.last_beat_at,
                cycle_count = excluded.cycle_count,
                active_task = excluded.active_task
            """,
            (identity, int(pid), harness, status, stamp, int(cycle_count), active_task),
        )
        conn.commit()
    finally:
        conn.close()


def read_beat(
    home: Path,
    *,
    now: Optional[datetime] = None,
    poll_interval_s: int = 15,
) -> Optional[dict]:
    """Return the single row with a computed status, or None when no beat exists."""
    path = heartbeats_path(home)
    if not path.exists():
        return None
    conn = open_heartbeats(home)
    try:
        row = conn.execute(
            """
            SELECT daemon_id, pid, harness, status, last_beat_at, cycle_count, active_task
            FROM daemon_heartbeats
            LIMIT 1
            """
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    stored = dict(row)
    stored["status"] = _computed_status(stored, now=now, poll_interval_s=poll_interval_s)
    stored["pid"] = int(stored["pid"])
    stored["cycle_count"] = int(stored["cycle_count"])
    return stored


def _computed_status(row: dict, *, now: Optional[datetime], poll_interval_s: int) -> str:
    if row.get("status") == "stopped":
        return "stopped"
    pid = int(row["pid"])
    if not pid_alive(pid):
        return "stale"
    stamp = _parse_time(str(row.get("last_beat_at") or ""))
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    if stamp is None:
        return "stale"
    age = (current - stamp).total_seconds()
    if age > (2 * int(poll_interval_s)):
        return "stale"
    return "running"


def pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _format_time(value: BeatTime) -> str:
    if isinstance(value, str):
        return value
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_time(value: str) -> Optional[datetime]:
    text = (value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
