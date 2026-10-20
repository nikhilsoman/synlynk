"""Durable evidence primitives for the disabled-by-default Local pilot."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from synlynk.migrations.runner import run_pending_migrations
from synlynk.wal_ledger import write_transaction


_COHORTS = frozenset({"validation", "expansion"})
_SAFETY_VERDICTS = frozenset({"passed", "failed"})
_QUALITY_VERDICTS = frozenset({"accepted", "rejected"})
_REVIEW_VERDICTS = {"accept": "accepted", "reject": "rejected"}
# Keep this aligned with dispatch._GH_WRITE_HARNESS_PRIORITY: it is the
# current measured frontier routing order, used here as a read-only ranking
# input. Review selection grants no GitHub or operational authority.
_FRONTIER_REVIEWER_ORDER = ("codex", "grok", "claude", "agy")


@dataclass(frozen=True)
class ReviewerSelection:
    candidates: tuple[str, ...]
    reviewer: str
    reason: str


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


def select_local_pilot_reviewer(
    conn: sqlite3.Connection, *, author_harness: str, eligible: list[str]
) -> ReviewerSelection:
    """Select one independent frontier reviewer in deterministic capability order."""
    del conn  # Selection is derived only from current routing inputs.
    author = str(author_harness or "").strip().casefold()
    available = {str(name).strip().casefold() for name in eligible if str(name).strip()}
    candidates = tuple(
        harness for harness in _FRONTIER_REVIEWER_ORDER
        if harness in available and harness not in {"local", author}
    )
    if not candidates:
        raise ValueError("no independent eligible frontier reviewer")
    reviewer = candidates[0]
    return ReviewerSelection(
        candidates=candidates,
        reviewer=reviewer,
        reason=f"selected {reviewer} as highest-ranked eligible frontier reviewer",
    )


def _review_brief(row: dict, selection: ReviewerSelection) -> dict:
    """Project only factual, allowlisted evidence into a reviewer brief."""
    receipt = json.loads(row["receipt_json"])
    claims = receipt.get("expected_factual_claims", [])
    if not isinstance(claims, list) or not all(isinstance(claim, str) for claim in claims):
        claims = []
    return {
        "job_id": row["job_id"],
        "reviewer": selection.reviewer,
        "selection_reason": selection.reason,
        "task_intent": str(receipt.get("task_intent") or row["task_class"]),
        "expected_factual_claims": claims,
        "local_answer_log_reference": str(
            receipt.get("answer_log_reference") or receipt.get("result_receipt_file") or ""
        ),
        "automated_receipt_result": row["safety_verdict"],
    }


def start_local_pilot_review(conn: sqlite3.Connection, job_id: str) -> dict:
    """Persist selection before returning the safety-gated factual review brief."""
    ensure_local_pilot_ledger(conn)
    row = _row_as_dict(conn, job_id)
    if row["safety_verdict"] != "passed":
        raise ValueError("Local pilot review requires a passed safety receipt")
    receipt = json.loads(row["receipt_json"])
    author = str(receipt.get("author_harness") or "local")
    selection = select_local_pilot_reviewer(
        conn,
        author_harness=author,
        eligible=list(_FRONTIER_REVIEWER_ORDER),
    )
    with write_transaction(conn):
        existing = conn.execute(
            "SELECT candidate_json, selected_harness, selection_reason "
            "FROM local_pilot_review_selections WHERE job_id = ?",
            (job_id,),
        ).fetchone()
        if existing is None:
            conn.execute(
                "INSERT INTO local_pilot_review_selections "
                "(job_id, candidate_json, selected_harness, selection_reason, selected_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (job_id, json.dumps(selection.candidates, separators=(",", ":")), selection.reviewer,
                 selection.reason, _utc_now()),
            )
        else:
            selection = ReviewerSelection(
                candidates=tuple(json.loads(existing[0])), reviewer=existing[1], reason=existing[2]
            )
    return _review_brief(row, selection)


def record_local_pilot_review(
    conn: sqlite3.Connection, job_id: str, reviewer: str, verdict: str, rationale: str
) -> dict:
    """Record exactly one selected review verdict, affecting quality evidence only."""
    mapped_verdict = _REVIEW_VERDICTS.get(str(verdict).strip().casefold())
    if mapped_verdict is None:
        raise ValueError(f"unknown review verdict: {verdict}")
    rationale = str(rationale).strip()
    if not rationale:
        raise ValueError("rationale is required")
    selected = conn.execute(
        "SELECT selected_harness, selection_reason FROM local_pilot_review_selections WHERE job_id = ?",
        (job_id,),
    ).fetchone()
    if selected is None:
        raise ValueError("review has not been started")
    if str(reviewer).strip().casefold() != selected[0]:
        raise ValueError("reviewer is not the selected reviewer")
    return record_quality_verdict(
        conn, job_id, selected[0], mapped_verdict, rationale, selected[1]
    )


def pause_local_pilot(reason: str) -> None:
    """Disable future Local admission through the owned workspace config path."""
    from synlynk import _update_config, load_workspace

    workspace = load_workspace()
    settings = dict(workspace.get("local_pilot") or {})
    settings.update({"enabled": False, "pause_reason": str(reason)})
    _update_config({"local_pilot": settings})


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
