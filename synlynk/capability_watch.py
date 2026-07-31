"""Local staleness triggers for harness capability data.

Two independent thresholds, checked once per CLI invocation:
Free tier (TC1-TC5 structural probe, no LLM spend): default 24h
- Paid tier (selftest --live smoke test): default 7 days, opt-in only
  via config['auto_smoke_test']
See docs/superpowers/specs/2026-07-31-harness-capability-drift-regression-classification-design.md
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
import sqlite3
from typing import Optional


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _parse_iso(ts: Optional[str]) -> Optional[float]:
    if not ts:
        return None
    try:
        return time.mktime(time.strptime(ts, "%Y-%m-%dT%H:%M:%SZ"))
    except (TypeError, ValueError):
        return None


def is_probe_stale(conn, threshold_hours: int = 24) -> bool:
    row = conn.execute("SELECT last_probe_at FROM capability_watch WHERE id = 1").fetchone()
    last = _parse_iso(row[0] if row else None)
    if last is None:
        return True
    return (time.time() - last) > threshold_hours * 3600


def is_smoke_test_stale(conn, threshold_days: int = 7) -> bool:
    row = conn.execute("SELECT last_smoke_test_at FROM capability_watch WHERE id = 1").fetchone()
    last = _parse_iso(row[0] if row else None)
    if last is None:
        return True
    return (time.time() - last) > threshold_days * 86400


def mark_probe_run(conn, green: bool) -> None:
    now = _now_iso()
    if green:
        conn.execute(
            "UPDATE capability_watch SET last_probe_at = ?, last_green_probe_at = ? WHERE id = 1",
            (now, now),
        )
    else:
        conn.execute("UPDATE capability_watch SET last_probe_at = ? WHERE id = 1", (now,))
    conn.commit()


def mark_smoke_test_run(conn, green: bool) -> None:
    now = _now_iso()
    if green:
        conn.execute(
            "UPDATE capability_watch SET last_smoke_test_at = ?, last_green_smoke_at = ? WHERE id = 1",
            (now, now),
        )
    else:
        conn.execute("UPDATE capability_watch SET last_smoke_test_at = ? WHERE id = 1", (now,))
    conn.commit()


def _run_free_probe(conn) -> None:
    """Runs the structural TC1-5 probe for every discovered agent."""
    from synlynk import discover_agents
    from synlynk.capability_classifier import classify_failure

    ok = True
    for agent in discover_agents():
        result = subprocess.run(
            [sys.executable, "-m", "synlynk", "probe", agent["name"]],
            capture_output=True,
            text=True,
            cwd=os.getcwd(),
            check=False,
        )
        if result.returncode != 0:
            ok = False
            row = conn.execute(
                "SELECT last_green_probe_at FROM capability_watch WHERE id = 1"
            ).fetchone()
            last_green = row[0] if row else None
            if last_green:
                classify_failure(
                    conn,
                    harness=agent["name"],
                    failing_path="synlynk/probe.py",
                    repo_path=os.getcwd(),
                    last_green_sha=_last_commit_before(os.getcwd(), last_green),
                    harness_fingerprint_changed=False,
                )
    mark_probe_run(conn, green=ok)


def _last_commit_before(repo_path: str, iso_timestamp: str) -> str:
    """Resolves the last commit sha at or before a given ISO timestamp."""
    result = subprocess.run(
        ["git", "rev-list", "-1", f"--before={iso_timestamp}", "HEAD"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=False,
    )
    sha = result.stdout.strip()
    return sha if sha else "HEAD"


def _run_paid_smoke_test(conn) -> None:
    """Runs `synlynk selftest --live`, respecting its own $2 budget cap."""
    result = subprocess.run(
        [sys.executable, "-m", "synlynk", "selftest", "--live"],
        capture_output=True,
        text=True,
        cwd=os.getcwd(),
        check=False,
    )
    mark_smoke_test_run(conn, green=result.returncode == 0)


def maybe_trigger_staleness_checks(
    conn,
    config: dict,
    probe_threshold_hours: int = 24,
    smoke_threshold_days: int = 7,
) -> None:
    """Runs due checks synchronously.

    Callers that want non-blocking behavior (e.g. the CLI entrypoint) should
    invoke this inside a background thread.
    """
    if is_probe_stale(conn, threshold_hours=probe_threshold_hours):
        _run_free_probe(conn)
        return
    if config.get("auto_smoke_test", False) and is_smoke_test_stale(
        conn, threshold_days=smoke_threshold_days
    ):
        _run_paid_smoke_test(conn)


def _db_path_for_conn(conn) -> Optional[str]:
    try:
        row = conn.execute("PRAGMA database_list").fetchone()
    except Exception:
        return None
    if not row:
        return None
    return row[2] or None


def _maybe_trigger_staleness_checks_in_thread(db_path: Optional[str], config: dict) -> None:
    if not db_path:
        return
    conn = sqlite3.connect(db_path)
    try:
        maybe_trigger_staleness_checks(conn, config)
    finally:
        conn.close()


def spawn_staleness_check_thread(conn, config: dict) -> threading.Thread:
    """Fire-and-forget: never blocks the invoking command."""
    db_path = _db_path_for_conn(conn)
    thread = threading.Thread(
        target=_maybe_trigger_staleness_checks_in_thread, args=(db_path, config), daemon=True
    )
    thread.start()
    return thread
