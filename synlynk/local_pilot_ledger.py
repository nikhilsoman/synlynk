"""Durable evidence primitives for the disabled-by-default Local pilot."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from typing import Any

from synlynk.migrations.runner import run_pending_migrations
from synlynk.wal_ledger import write_transaction


_COHORTS = frozenset({"validation", "expansion"})
_SAFETY_VERDICTS = frozenset({"passed", "failed"})
_QUALITY_VERDICTS = frozenset({"accepted", "rejected"})


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_receipt(receipt: Any) -> tuple[str, str]:
    serialized = json.dumps(receipt if receipt is not None else {}, sort_keys=True, separators=(",", ":"))
    return serialized, hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _row_as_dict(conn: sqlite3.Connection, job_id: str) -> dict:
    row = conn.execute("SELECT * FROM local_pilot_evidence WHERE job_id = ?", (job_id,)).fetchone()
    if row is None:
        raise ValueError(f"unknown Local pilot job_id: {job_id}")
    return {column[0]: value for column, value in zip(conn.execute("SELECT * FROM local_pilot_evidence LIMIT 0").description, row)}


def ensure_local_pilot_ledger(conn: sqlite3.Connection) -> None:
    """Install the ledger through the canonical versioned migration runner."""
    run_pending_migrations(conn)


def record_admission(conn: sqlite3.Connection, sample: dict) -> dict:
    """Append an admitted validation or expansion sample exactly once."""
    job_id = str(sample.get("job_id", "")).strip()
    cohort = sample.get("cohort")
    if not job_id:
        raise ValueError("job_id is required")
    if cohort not in _COHORTS:
        raise ValueError(f"unknown cohort: {cohort}")
    task_class = str(sample.get("task_class", "")).strip()
    task_digest = str(sample.get("task_digest", "")).strip()
    if not task_class or not task_digest:
        raise ValueError("task_class and task_digest are required")
    receipt_json, receipt_digest = _canonical_receipt(sample.get("receipt"))
    def insert() -> dict:
        if conn.execute("SELECT 1 FROM local_pilot_evidence WHERE job_id = ?", (job_id,)).fetchone():
            raise ValueError(f"duplicate job_id: {job_id}")
        conn.execute(
            """INSERT INTO local_pilot_evidence
               (job_id, cohort, task_class, task_digest, receipt_json, receipt_digest, admitted_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (job_id, cohort, task_class, task_digest, receipt_json, receipt_digest, _utc_now()),
        )
        return _row_as_dict(conn, job_id)

    # Dispatch reserves the Local slot and calls us inside that transaction.
    # Keeping this write in the reservation transaction means either both the
    # reservation and immutable admission exist, or neither does.
    if conn.in_transaction:
        return insert()
    with write_transaction(conn):
        return insert()


def record_safety_outcome(
    conn: sqlite3.Connection, job_id: str, verdict: str, reason: str, receipt: dict | None
) -> dict:
    """Set a pending sample's immutable terminal safety outcome."""
    if verdict not in _SAFETY_VERDICTS:
        raise ValueError(f"unknown safety verdict: {verdict}")
    receipt_json, receipt_digest = _canonical_receipt(receipt)
    with write_transaction(conn):
        result = conn.execute(
            """UPDATE local_pilot_evidence
               SET safety_verdict = ?, safety_reason = ?, safety_receipt_json = ?,
                   safety_receipt_digest = ?, safety_recorded_at = ?
               WHERE job_id = ? AND safety_verdict = 'pending'""",
            (verdict, reason, receipt_json, receipt_digest, _utc_now(), job_id),
        )
        if result.rowcount != 1:
            _row_as_dict(conn, job_id)
            raise ValueError(f"safety outcome already recorded for job_id: {job_id}")
        return _row_as_dict(conn, job_id)


def record_quality_verdict(
    conn: sqlite3.Connection,
    job_id: str,
    reviewer: str,
    verdict: str,
    rationale: str,
    selection_reason: str,
) -> dict:
    """Set a pending sample's immutable terminal independent-review verdict."""
    if verdict not in _QUALITY_VERDICTS:
        raise ValueError(f"unknown quality verdict: {verdict}")
    if not str(reviewer).strip() or not str(selection_reason).strip():
        raise ValueError("reviewer and selection_reason are required")
    with write_transaction(conn):
        result = conn.execute(
            """UPDATE local_pilot_evidence
               SET quality_verdict = ?, reviewer_harness = ?, reviewer_rationale = ?,
                   reviewer_selection_reason = ?, quality_recorded_at = ?
               WHERE job_id = ? AND quality_verdict = 'pending'""",
            (verdict, reviewer, rationale, selection_reason, _utc_now(), job_id),
        )
        if result.rowcount != 1:
            _row_as_dict(conn, job_id)
            raise ValueError(f"quality verdict already recorded for job_id: {job_id}")
        return _row_as_dict(conn, job_id)


def load_pilot_status(conn: sqlite3.Connection) -> dict:
    """Return intentionally separate historical, validation, and expansion cohorts."""
    historical = conn.execute(
        "SELECT cohort, accepted, eligible FROM local_pilot_cohort_summaries WHERE cohort = 'historical'"
    ).fetchone()
    if historical is None:
        raise RuntimeError("Local pilot ledger has not been initialized")
    status = {"historical": dict(zip(("cohort", "accepted", "eligible"), historical))}
    for cohort in ("validation", "expansion"):
        accepted, pending, rejected, safety_failed = conn.execute(
            "SELECT "
            "COUNT(*) FILTER (WHERE safety_verdict = 'passed' AND quality_verdict = 'accepted'), "
            "COUNT(*) FILTER (WHERE safety_verdict != 'failed' AND quality_verdict != 'rejected' "
            "AND (safety_verdict = 'pending' OR quality_verdict = 'pending')), "
            "COUNT(*) FILTER (WHERE safety_verdict != 'failed' AND quality_verdict = 'rejected'), "
            "COUNT(*) FILTER (WHERE safety_verdict = 'failed') "
            "FROM local_pilot_evidence WHERE cohort = ?",
            (cohort,),
        ).fetchone()
        status[cohort] = {
            "cohort": cohort,
            "accepted": accepted,
            "eligible": accepted,
            "pending": pending,
            "rejected": rejected,
            "safety_failed": safety_failed,
        }
    consecutive_accepted = 0
    for safety_verdict, quality_verdict in conn.execute(
        "SELECT safety_verdict, quality_verdict FROM local_pilot_evidence "
        "WHERE cohort = 'expansion' "
        "ORDER BY COALESCE(quality_recorded_at, admitted_at), rowid"
    ):
        if safety_verdict == "passed" and quality_verdict == "accepted":
            consecutive_accepted += 1
        elif safety_verdict == "passed" and quality_verdict == "rejected":
            consecutive_accepted = 0
    status["expansion"]["consecutive_accepted"] = consecutive_accepted
    return status
