"""Durable evidence primitives for the disabled-by-default Local pilot."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import subprocess
import tempfile
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from synlynk._constants import GH_WRITE_HARNESS_PRIORITY
from synlynk.migrations.runner import run_pending_migrations
from synlynk.wal_ledger import write_transaction


_COHORTS = frozenset({"validation", "expansion"})
_SAFETY_VERDICTS = frozenset({"passed", "failed"})
_QUALITY_VERDICTS = frozenset({"accepted", "rejected"})
_REVIEW_VERDICTS = {"accept": "accepted", "reject": "rejected"}
_RESUME_SIGN_NAMESPACE = "synlynk-local-pilot-resume"
_RESUME_SIGN_PRINCIPAL = "local-pilot-resume"
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


def _host_identity_public_key_path() -> str:
    return os.path.expanduser("~/.synlynk/identity.key.pub")


def _verify_resume_signature(approval_payload: dict, signature: str) -> bool:
    """Verify a canonical approval payload using the host identity public key."""
    public_key_path = _host_identity_public_key_path()
    if not os.path.isfile(public_key_path):
        return False
    try:
        with open(public_key_path, encoding="utf-8") as public_key_file:
            public_key = public_key_file.read().strip()
    except OSError:
        return False
    if not public_key:
        return False
    signature_path = signers_path = None
    try:
        canonical, _ = _canonical_receipt(approval_payload)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=False) as signature_file:
            signature_file.write(signature)
            signature_path = signature_file.name
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=False) as signers_file:
            signers_file.write(f"{_RESUME_SIGN_PRINCIPAL} {public_key}\n")
            signers_path = signers_file.name
        result = subprocess.run(
            ["ssh-keygen", "-Y", "verify", "-f", signers_path, "-I", _RESUME_SIGN_PRINCIPAL,
             "-n", _RESUME_SIGN_NAMESPACE, "-s", signature_path],
            input=canonical.encode("utf-8"), capture_output=True,
        )
        return result.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False
    finally:
        for path in (signature_path, signers_path):
            if path:
                try:
                    os.unlink(path)
                except OSError:
                    pass


def _row_as_dict(conn: sqlite3.Connection, job_id: str) -> dict:
    row = conn.execute("SELECT * FROM local_pilot_evidence WHERE job_id = ?", (job_id,)).fetchone()
    if row is None:
        raise ValueError(f"unknown Local pilot job_id: {job_id}")
    return {column[0]: value for column, value in zip(conn.execute("SELECT * FROM local_pilot_evidence LIMIT 0").description, row)}


def ensure_local_pilot_ledger(conn: sqlite3.Connection) -> None:
    """Install the ledger through the canonical versioned migration runner."""
    run_pending_migrations(conn)


def _authorization_as_dict(conn: sqlite3.Connection, authorization_id: str) -> dict:
    row = conn.execute(
        "SELECT * FROM local_pilot_resume_authorizations WHERE authorization_id = ?",
        (authorization_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"unknown Local pilot resume authorization: {authorization_id}")
    columns = conn.execute("SELECT * FROM local_pilot_resume_authorizations LIMIT 0").description
    return {column[0]: value for column, value in zip(columns, row)}


def resume_authorization_context(conn: sqlite3.Connection) -> dict:
    """Return the fresh event identity and evidence watermark to include in a signed envelope."""
    ensure_local_pilot_ledger(conn)
    watermark = conn.execute("SELECT COALESCE(MAX(rowid), 0) FROM local_pilot_evidence").fetchone()[0]
    return {"authorization_id": str(uuid.uuid4()), "safety_watermark": watermark}


def create_resume_authorization(conn: sqlite3.Connection, payload: dict) -> dict:
    """Append an activating resume authority at the current safety watermark."""
    ensure_local_pilot_ledger(conn)
    payload = dict(payload or {})
    if set(payload) != {"signed_payload"}:
        raise ValueError("resume authorization accepts only a signed_payload envelope")
    signed_payload = payload["signed_payload"]
    if not isinstance(signed_payload, dict):
        raise ValueError("signed_payload is required")
    authorization = signed_payload.get("authorization")
    signature = signed_payload.get("signature")
    if not isinstance(authorization, dict) or not isinstance(signature, str) or not signature.strip():
        raise ValueError("signed_payload must contain authorization and signature")
    required_fields = {
        "authorization_id", "config_fingerprint", "remediation_reference", "verification_reference",
        "preflight_receipt", "preflight_receipt_digest", "safety_watermark",
    }
    if set(authorization) != required_fields:
        raise ValueError("signed authorization has an invalid field set")
    if not _verify_resume_signature(authorization, signature):
        raise ValueError("signed authorization signature is invalid for the host identity key")
    authorization_id = str(authorization["authorization_id"] or "").strip()
    config_fingerprint = str(authorization["config_fingerprint"] or "").strip()
    remediation_reference = str(authorization["remediation_reference"] or "").strip()
    verification_reference = str(authorization["verification_reference"] or "").strip()
    preflight_receipt = authorization["preflight_receipt"]
    if not config_fingerprint or not remediation_reference or not verification_reference:
        raise ValueError("config_fingerprint, remediation_reference, and verification_reference are required")
    if not isinstance(preflight_receipt, dict) or preflight_receipt.get("result") != "passed":
        raise ValueError("a passed preflight_receipt is required")
    signed_payload_json, signed_payload_digest = _canonical_receipt(signed_payload)
    preflight_receipt_json, preflight_receipt_digest = _canonical_receipt(preflight_receipt)
    if authorization["preflight_receipt_digest"] != preflight_receipt_digest:
        raise ValueError("signed authorization preflight receipt digest does not match")
    try:
        safety_watermark = int(authorization["safety_watermark"])
    except (TypeError, ValueError):
        raise ValueError("signed authorization safety watermark is invalid") from None
    if safety_watermark < 0:
        raise ValueError("signed authorization safety watermark is invalid")
    with write_transaction(conn):
        existing = conn.execute(
            "SELECT state FROM local_pilot_resume_authorizations "
            "WHERE state IN ('activating', 'active')"
        ).fetchone()
        if existing:
            if existing[0] == "active":
                raise ValueError("a resume authorization is already active")
            raise ValueError("resume authorization activation in progress")
        watermark = conn.execute("SELECT COALESCE(MAX(rowid), 0) FROM local_pilot_evidence").fetchone()[0]
        if safety_watermark != watermark:
            raise ValueError("signed authorization safety watermark is stale")
        try:
            conn.execute(
                """INSERT INTO local_pilot_resume_authorizations
                   (authorization_id, created_at, signed_payload_json, signed_payload_digest,
                    config_fingerprint, remediation_reference, verification_reference, safety_watermark,
                    preflight_receipt_json, preflight_receipt_digest, state)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'activating')""",
                (authorization_id, _utc_now(), signed_payload_json, signed_payload_digest,
                 config_fingerprint, remediation_reference, verification_reference, safety_watermark,
                 preflight_receipt_json, preflight_receipt_digest),
            )
        except sqlite3.IntegrityError as error:
            raise ValueError(f"duplicate resume authorization_id: {authorization_id}") from error
        return _authorization_as_dict(conn, authorization_id)


def activate_resume_authorization(conn: sqlite3.Connection, authorization_id: str) -> dict:
    """Mark one prepared authorization active; SQLite enforces one active authority."""
    ensure_local_pilot_ledger(conn)
    with write_transaction(conn):
        authorization = _authorization_as_dict(conn, authorization_id)
        post_watermark_failure = conn.execute(
            "SELECT 1 FROM local_pilot_evidence WHERE safety_verdict = 'failed' AND rowid > ?",
            (authorization["safety_watermark"],),
        ).fetchone()
        if post_watermark_failure is not None:
            raise ValueError("post-watermark safety failure requires a fresh resume authorization")
        try:
            result = conn.execute(
                "UPDATE local_pilot_resume_authorizations SET state = 'active', activated_at = ? "
                "WHERE authorization_id = ? AND state = 'activating'",
                (_utc_now(), authorization_id),
            )
        except sqlite3.IntegrityError as error:
            raise ValueError("a resume authorization is already active") from error
        if result.rowcount != 1:
            _authorization_as_dict(conn, authorization_id)
            raise ValueError(f"resume authorization is not activating: {authorization_id}")
        return _authorization_as_dict(conn, authorization_id)


def fail_resume_authorization(conn: sqlite3.Connection, authorization_id: str, reason: str) -> dict:
    """Reconcile a crash-boundary activating record into the terminal failed state."""
    ensure_local_pilot_ledger(conn)
    reason = str(reason or "").strip()
    if not reason:
        raise ValueError("failure reason is required")
    with write_transaction(conn):
        result = conn.execute(
            "UPDATE local_pilot_resume_authorizations SET state = 'failed', revoked_at = ?, terminal_reason = ? "
            "WHERE authorization_id = ? AND state = 'activating'",
            (_utc_now(), reason, authorization_id),
        )
        if result.rowcount != 1:
            _authorization_as_dict(conn, authorization_id)
            raise ValueError(f"resume authorization is not activating: {authorization_id}")
        return _authorization_as_dict(conn, authorization_id)


def revoke_active_resume_authorization(conn: sqlite3.Connection, reason: str) -> dict | None:
    """Terminally revoke the one active authority, if present."""
    ensure_local_pilot_ledger(conn)
    reason = str(reason or "").strip()
    if not reason:
        raise ValueError("revocation reason is required")
    with write_transaction(conn):
        active = conn.execute(
            "SELECT authorization_id FROM local_pilot_resume_authorizations WHERE state = 'active'"
        ).fetchone()
        if active is None:
            return None
        authorization_id = active[0]
        conn.execute(
            "UPDATE local_pilot_resume_authorizations SET state = 'revoked', revoked_at = ?, terminal_reason = ? "
            "WHERE authorization_id = ?",
            (_utc_now(), reason, authorization_id),
        )
        return _authorization_as_dict(conn, authorization_id)


def active_resume_authorization(conn: sqlite3.Connection) -> dict | None:
    """Return the sole active authorization, never an activating authority."""
    ensure_local_pilot_ledger(conn)
    row = conn.execute(
        "SELECT authorization_id FROM local_pilot_resume_authorizations WHERE state = 'active'"
    ).fetchone()
    return _authorization_as_dict(conn, row[0]) if row else None


def active_resume_authorization_matches_runtime(
    conn: sqlite3.Connection, *, share: float, max_concurrent: int,
    effective_model: str | None = None,
) -> bool:
    """Return whether durable approval authorizes this exact Local runtime.

    The signed preflight receipt is the authority's immutable declaration of
    the narrow target.  An enabled config is deliberately insufficient.
    """
    authorization = active_resume_authorization(conn)
    if authorization is None:
        return False
    try:
        receipt = json.loads(authorization["preflight_receipt_json"])
    except (KeyError, TypeError, json.JSONDecodeError):
        return False
    return (
        receipt.get("result") == "passed"
        and receipt.get("requested_share") == share
        and receipt.get("requested_max_concurrent") == max_concurrent
        and (effective_model is None or receipt.get("resolved_model") == effective_model)
    )


@contextmanager
def local_pilot_control_lock(repo_root: str | None = None):
    """Serialize Local config, authority lifecycle, and final slot admission."""
    import fcntl

    root = os.path.abspath(repo_root or os.getcwd())
    lock_path = os.path.join(root, ".synlynk", "local-pilot-control.lock")
    os.makedirs(os.path.dirname(lock_path), exist_ok=True)
    with open(lock_path, "a+") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


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
        harness for harness in GH_WRITE_HARNESS_PRIORITY
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
        eligible=list(GH_WRITE_HARNESS_PRIORITY),
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


def pause_local_pilot(reason: str, *, conn: sqlite3.Connection | None = None) -> None:
    """Revoke Local authority before disabling its owned workspace config."""
    from synlynk import _get_db, _update_config, load_workspace

    owns_connection = conn is None
    if conn is None:
        conn = _get_db()
    try:
        with local_pilot_control_lock():
            with write_transaction(conn):
                staged = conn.execute(
                    "SELECT authorization_id FROM local_pilot_resume_authorizations WHERE state = 'activating'"
                ).fetchone()
                if staged is not None:
                    conn.execute(
                        "UPDATE local_pilot_resume_authorizations "
                        "SET state = 'failed', revoked_at = ?, terminal_reason = ? "
                        "WHERE authorization_id = ? AND state = 'activating'",
                        (_utc_now(), str(reason), staged[0]),
                    )
                active = conn.execute(
                    "SELECT authorization_id FROM local_pilot_resume_authorizations WHERE state = 'active'"
                ).fetchone()
                if active is not None:
                    conn.execute(
                        "UPDATE local_pilot_resume_authorizations "
                        "SET state = 'revoked', revoked_at = ?, terminal_reason = ? "
                        "WHERE authorization_id = ? AND state = 'active'",
                        (_utc_now(), str(reason), active[0]),
                    )
            workspace = load_workspace()
            settings = dict(workspace.get("local_pilot") or {})
            settings.update({"enabled": False, "pause_reason": str(reason)})
            _update_config({"local_pilot": settings})
    finally:
        if owns_connection:
            conn.close()


def load_pilot_status(conn: sqlite3.Connection) -> dict:
    """Return intentionally separate historical, validation, and expansion cohorts."""
    historical = conn.execute(
        "SELECT cohort, accepted, eligible FROM local_pilot_cohort_summaries WHERE cohort = 'historical'"
    ).fetchone()
    if historical is None:
        raise RuntimeError("Local pilot ledger has not been initialized")
    latest_row = conn.execute(
        "SELECT authorization_id FROM local_pilot_resume_authorizations ORDER BY rowid DESC LIMIT 1"
    ).fetchone()
    active = active_resume_authorization(conn)
    watermark = int(active["safety_watermark"]) if active else None
    status = {
        "historical": dict(zip(("cohort", "accepted", "eligible"), historical)),
        "latest_authorization": _authorization_as_dict(conn, latest_row[0]) if latest_row else None,
        "active_authorization": active,
    }
    epoch_clause = " AND rowid > ?" if watermark is not None else ""
    epoch_args = (watermark,) if watermark is not None else ()
    for cohort in ("validation", "expansion"):
        accepted, pending, rejected, safety_failed = conn.execute(
            "SELECT "
            "COUNT(*) FILTER (WHERE safety_verdict = 'passed' AND quality_verdict = 'accepted'), "
            "COUNT(*) FILTER (WHERE safety_verdict != 'failed' AND quality_verdict != 'rejected' "
            "AND (safety_verdict = 'pending' OR quality_verdict = 'pending')), "
            "COUNT(*) FILTER (WHERE safety_verdict != 'failed' AND quality_verdict = 'rejected'), "
            "COUNT(*) FILTER (WHERE safety_verdict = 'failed') "
            f"FROM local_pilot_evidence WHERE cohort = ?{epoch_clause}",
            (cohort, *epoch_args),
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
        f"WHERE cohort = 'expansion'{epoch_clause} "
        "ORDER BY COALESCE(quality_recorded_at, admitted_at), rowid",
        epoch_args,
    ):
        if safety_verdict == "passed" and quality_verdict == "accepted":
            consecutive_accepted += 1
        elif safety_verdict == "passed" and quality_verdict == "rejected":
            consecutive_accepted = 0
    status["expansion"]["consecutive_accepted"] = consecutive_accepted
    status["historical_safety_failures"] = conn.execute(
        "SELECT COUNT(*) FROM local_pilot_evidence WHERE safety_verdict = 'failed'"
    ).fetchone()[0]
    status["active_epoch_safety_failures"] = (
        conn.execute(
            "SELECT COUNT(*) FROM local_pilot_evidence WHERE safety_verdict = 'failed' AND rowid > ?",
            (watermark,),
        ).fetchone()[0]
        if watermark is not None else 0
    )
    return status
