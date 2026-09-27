"""synlynk.worktree_lease: Leased Worktree Locks with TTL and Dead-PID Autonomous Recovery.

Invariant 4: Guarantees that every active worktree is guarded by an explicit
leased lock in SQLite (state.db) and on-disk JSON metadata, with automatic
TTL expiration and dead-PID reclamation to eliminate stale lock contention.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sqlite3
import time
from typing import Dict, List, Optional, Any

from synlynk.wal_ledger import write_transaction, ensure_wal_pragmas

logger = logging.getLogger("synlynk.worktree_lease")

LEASE_JSON_FILENAME = os.path.join(".synlynk", "lease.json")
DEFAULT_LEASE_DURATION_SECONDS = 900  # 15 minutes


def init_worktree_lease_schema(conn: sqlite3.Connection) -> None:
    """Ensure the worktree_leases table and indexes exist in the ledger."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS worktree_leases (
            worktree_id    TEXT PRIMARY KEY,
            job_id         TEXT,
            worktree_path  TEXT NOT NULL,
            leased_by      TEXT NOT NULL,
            pid            INTEGER NOT NULL,
            acquired_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            heartbeat_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at     TIMESTAMP NOT NULL,
            status         TEXT NOT NULL DEFAULT 'active'
        );
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_worktree_leases_status ON worktree_leases(status, expires_at);"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_worktree_leases_path ON worktree_leases(worktree_path, status);"
    )


def _is_pid_alive(pid: int) -> bool:
    """Check if a process with given PID is currently alive on the host system."""
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        # Process exists but owned by different user
        return True
    except OSError:
        return False


def _write_disk_lease_file(worktree_path: str, data: Dict[str, Any]) -> None:
    """Write or overwrite the on-disk lease.json file in the worktree's .synlynk directory."""
    synlynk_dir = os.path.join(worktree_path, ".synlynk")
    if not os.path.exists(synlynk_dir):
        try:
            os.makedirs(synlynk_dir, exist_ok=True)
        except OSError:
            pass

    file_path = os.path.join(synlynk_dir, "lease.json")
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except OSError as exc:
        logger.debug("Failed to write disk lease file at %s: %s", file_path, exc)


def _remove_disk_lease_file(worktree_path: str) -> None:
    """Safely remove the on-disk lease.json file (and legacy .synlynk-lease.json)."""
    for candidate in [
        os.path.join(worktree_path, ".synlynk", "lease.json"),
        os.path.join(worktree_path, ".synlynk-lease.json"),
    ]:
        if os.path.exists(candidate):
            try:
                os.remove(candidate)
            except OSError:
                pass


def acquire_worktree_lease(
    worktree_path: str,
    leased_by: str,
    job_id: Optional[str] = None,
    pid: Optional[int] = None,
    duration_seconds: int = DEFAULT_LEASE_DURATION_SECONDS,
    conn: Optional[sqlite3.Connection] = None,
) -> Dict[str, Any]:
    """Acquire a leased lock on a worktree path in state.db and on disk.

    If an active lease already exists:
      - If holding PID is dead or TTL is expired: reclaims the lease.
      - If holding PID is alive and TTL is active: refuses acquisition (acquired: False).

    Returns:
        dict with `acquired: bool`, `lease_id`, `worktree_path`, `expires_at`, etc.
    """
    owns_conn = False
    if conn is None:
        from synlynk import _get_db
        conn = _get_db()
        owns_conn = True

    try:
        init_worktree_lease_schema(conn)
        abs_path = os.path.abspath(worktree_path)
        effective_pid = pid if pid is not None else os.getpid()
        now = time.time()
        now_str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now))
        expires_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now + duration_seconds))
        lease_id = f"wtlease-{hashlib.md5(f'{abs_path}:{leased_by}:{now}'.encode()).hexdigest()[:8]}"

        stolen_from_dead_pid = False

        with write_transaction(conn):
            row = conn.execute(
                """SELECT worktree_id, leased_by, pid, expires_at FROM worktree_leases
                   WHERE worktree_path=? AND status='active' ORDER BY rowid DESC LIMIT 1""",
                (abs_path,),
            ).fetchone()

            if row:
                curr_id, curr_holder, curr_pid, curr_exp = row
                is_expired = curr_exp < now_str
                is_dead = not _is_pid_alive(curr_pid)
                is_same_holder = curr_holder == leased_by

                if is_expired or is_dead or is_same_holder:
                    if is_dead and not is_expired and not is_same_holder:
                        stolen_from_dead_pid = True
                        logger.warning(
                            "Reclaiming stale worktree lease %s on %s from dead PID %s",
                            curr_id, abs_path, curr_pid
                        )
                    conn.execute(
                        "UPDATE worktree_leases SET status='expired' WHERE worktree_id=?",
                        (curr_id,),
                    )
                else:
                    return {
                        "acquired": False,
                        "reason": "already_leased",
                        "leased_by": curr_holder,
                        "pid": curr_pid,
                        "expires_at": curr_exp,
                        "worktree_path": abs_path,
                    }

            conn.execute(
                """INSERT INTO worktree_leases
                   (worktree_id, job_id, worktree_path, leased_by, pid, acquired_at, heartbeat_at, expires_at, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active')""",
                (lease_id, job_id or "", abs_path, leased_by, effective_pid, now_str, now_str, expires_at),
            )

        lease_data = {
            "lease_id": lease_id,
            "job_id": job_id or "",
            "worktree_path": abs_path,
            "leased_by": leased_by,
            "pid": effective_pid,
            "acquired_at": now_str,
            "expires_at": expires_at,
            "status": "active",
        }
        _write_disk_lease_file(worktree_path, lease_data)

        res = {
            "acquired": True,
            "lease_id": lease_id,
            "job_id": job_id or "",
            "worktree_path": abs_path,
            "leased_by": leased_by,
            "pid": effective_pid,
            "expires_at": expires_at,
        }
        if stolen_from_dead_pid:
            res["stolen_from_dead_pid"] = True
        return res
    finally:
        if owns_conn:
            conn.close()


def renew_worktree_lease(
    worktree_path: str,
    leased_by: str,
    extend_seconds: int = DEFAULT_LEASE_DURATION_SECONDS,
    conn: Optional[sqlite3.Connection] = None,
) -> bool:
    """Send a heartbeat to renew the active worktree lease."""
    owns_conn = False
    if conn is None:
        from synlynk import _get_db
        conn = _get_db()
        owns_conn = True

    try:
        abs_path = os.path.abspath(worktree_path)
        now = time.time()
        now_str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now))
        expires_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now + extend_seconds))

        with write_transaction(conn):
            res = conn.execute(
                """UPDATE worktree_leases SET heartbeat_at=?, expires_at=?
                   WHERE worktree_path=? AND leased_by=? AND status='active'""",
                (now_str, expires_at, abs_path, leased_by),
            )
            success = res.rowcount > 0

        if success:
            file_path = os.path.join(worktree_path, LEASE_JSON_FILENAME)
            if not os.path.exists(file_path):
                file_path = os.path.join(worktree_path, ".synlynk-lease.json")
            if os.path.exists(file_path):
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    data["heartbeat_at"] = now_str
                    data["expires_at"] = expires_at
                    _write_disk_lease_file(worktree_path, data)
                except Exception:
                    pass
        return success
    finally:
        if owns_conn:
            conn.close()


def release_worktree_lease(
    worktree_path: str,
    leased_by: Optional[str] = None,
    conn: Optional[sqlite3.Connection] = None,
) -> bool:
    """Release an active worktree lease and remove on-disk lease metadata."""
    owns_conn = False
    if conn is None:
        from synlynk import _get_db
        conn = _get_db()
        owns_conn = True

    try:
        abs_path = os.path.abspath(worktree_path)
        with write_transaction(conn):
            if leased_by:
                conn.execute(
                    "UPDATE worktree_leases SET status='released' WHERE worktree_path=? AND leased_by=? AND status='active'",
                    (abs_path, leased_by),
                )
            else:
                conn.execute(
                    "UPDATE worktree_leases SET status='released' WHERE worktree_path=? AND status='active'",
                    (abs_path,),
                )

        _remove_disk_lease_file(worktree_path)
        return True
    finally:
        if owns_conn:
            conn.close()


def get_active_worktree_lease(
    worktree_path: str,
    conn: Optional[sqlite3.Connection] = None,
) -> Optional[Dict[str, Any]]:
    """Retrieve active lease details for a worktree path if present."""
    owns_conn = False
    if conn is None:
        from synlynk import _get_db
        conn = _get_db()
        owns_conn = True

    try:
        init_worktree_lease_schema(conn)
        abs_path = os.path.abspath(worktree_path)
        row = conn.execute(
            """SELECT worktree_id, job_id, worktree_path, leased_by, pid, acquired_at, heartbeat_at, expires_at, status
               FROM worktree_leases WHERE worktree_path=? AND status='active' ORDER BY rowid DESC LIMIT 1""",
            (abs_path,),
        ).fetchone()
        if not row:
            return None
        return {
            "worktree_id": row[0],
            "job_id": row[1],
            "worktree_path": row[2],
            "leased_by": row[3],
            "pid": row[4],
            "acquired_at": row[5],
            "heartbeat_at": row[6],
            "expires_at": row[7],
            "status": row[8],
        }
    finally:
        if owns_conn:
            conn.close()


def audit_and_reclaim_stale_worktree_leases(
    conn: Optional[sqlite3.Connection] = None,
) -> List[Dict[str, Any]]:
    """Audit all active worktree leases and reclaim those whose TTL expired or PID is dead."""
    owns_conn = False
    if conn is None:
        from synlynk import _get_db
        conn = _get_db()
        owns_conn = True

    reclaimed = []
    try:
        init_worktree_lease_schema(conn)
        now_str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        rows = conn.execute(
            """SELECT worktree_id, job_id, worktree_path, leased_by, pid, expires_at
               FROM worktree_leases WHERE status='active'"""
        ).fetchall()

        for row in rows:
            wt_id, job_id, wt_path, holder, pid, exp = row
            is_expired = exp < now_str
            is_dead = not _is_pid_alive(pid)

            if is_expired or is_dead:
                with write_transaction(conn):
                    conn.execute(
                        "UPDATE worktree_leases SET status='expired' WHERE worktree_id=?",
                        (wt_id,),
                    )
                _remove_disk_lease_file(wt_path)
                reclaimed.append({
                    "worktree_id": wt_id,
                    "job_id": job_id,
                    "worktree_path": wt_path,
                    "leased_by": holder,
                    "pid": pid,
                    "reason": "expired_ttl" if is_expired else "dead_pid",
                })
        return reclaimed
    finally:
        if owns_conn:
            conn.close()
