"""Auditable attestations for incomplete legacy job provenance."""
from __future__ import annotations

import sqlite3
import sys
from datetime import datetime, timezone


def _purpose_for_attestation(role: str, task_type: str) -> str:
    from synlynk.dispatch import _job_purpose
    from synlynk.policy import load_policy

    policy = load_policy(repo_path=".")
    compatible = policy.get("role_task_type_compat", {}).get(role, [])
    allocated = policy.get("dev_authority", {}).get("task_allocation", {})
    if task_type not in compatible or task_type not in allocated:
        raise ValueError(f"role {role!r} is not authorized for task_type {task_type!r}")
    purpose = _job_purpose(role, task_type, explicit=True)
    if purpose not in {"implementation", "review"}:
        raise ValueError(f"role/task_type pair {role!r}/{task_type!r} has no attestable purpose")
    return purpose


def get_job_provenance_snapshot(conn: sqlite3.Connection, job_id: str) -> dict | None:
    row = conn.execute(
        """SELECT job_id, role, task_type, task_type_explicit, purpose,
                  COALESCE(NULLIF(harness, ''), agent) AS harness,
                  COALESCE(NULLIF(resolved_model, ''), NULLIF(requested_model, '')) AS model
             FROM daemon_jobs WHERE job_id=?""",
        (job_id,),
    ).fetchone()
    if not row:
        return None
    return dict(zip(("job_id", "role", "task_type", "task_type_explicit", "purpose", "harness", "model"), row))


def get_valid_job_provenance_attestation(conn: sqlite3.Connection, job_id: str) -> dict | None:
    """Return a unique valid attestation only when dispatch data does not conflict."""
    rows = conn.execute(
        """SELECT id, job_id, role, task_type, purpose, attested_by, rationale,
                  source, created_at
             FROM job_provenance_attestations WHERE job_id=? ORDER BY id""",
        (job_id,),
    ).fetchall()
    if len(rows) != 1:
        return None
    attestation = dict(zip(
        ("id", "job_id", "role", "task_type", "purpose", "attested_by", "rationale", "source", "created_at"),
        rows[0],
    ))
    if not attestation["attested_by"] or not attestation["rationale"] or attestation["source"] != "local-cli":
        return None
    snapshot = get_job_provenance_snapshot(conn, job_id)
    if not snapshot:
        return None
    if snapshot["purpose"] is not None:
        return None
    if snapshot["role"] and snapshot["role"] != attestation["role"]:
        return None
    if snapshot["task_type"] and snapshot["task_type"] != attestation["task_type"]:
        return None
    try:
        expected = _purpose_for_attestation(attestation["role"], attestation["task_type"])
    except ValueError:
        return None
    if expected != attestation["purpose"]:
        return None
    return attestation


def record_job_provenance_attestation(
    conn: sqlite3.Connection,
    *,
    job_id: str,
    role: str,
    task_type: str,
    attested_by: str,
    rationale: str,
) -> tuple[bool, dict]:
    """Append one attestation, returning (inserted, record); identical repeats are idempotent."""
    job_id, role, task_type = job_id.strip(), role.strip(), task_type.strip()
    attested_by, rationale = attested_by.strip().lstrip("@"), rationale.strip()
    if not all((job_id, role, task_type, attested_by, rationale)):
        raise ValueError("job, role, task type, attestor, and rationale are required")
    if attested_by == "unknown":
        raise ValueError("cannot attest with an unknown operator identity")
    purpose = _purpose_for_attestation(role, task_type)
    now = datetime.now(timezone.utc).isoformat()

    conn.execute("BEGIN IMMEDIATE")
    try:
        snapshot = get_job_provenance_snapshot(conn, job_id)
        if not snapshot:
            raise ValueError(f"job {job_id!r} does not exist")
        if snapshot["purpose"] is not None:
            raise ValueError(
                f"job {job_id} already has typed purpose {snapshot['purpose']!r}; "
                "an attestation cannot replace it"
            )
        if snapshot["role"] and snapshot["role"] != role:
            raise ValueError(f"attested role {role!r} conflicts with recorded role {snapshot['role']!r}")
        if snapshot["task_type"] and snapshot["task_type"] != task_type:
            raise ValueError(
                f"attested task type {task_type!r} conflicts with recorded task type {snapshot['task_type']!r}"
            )

        existing = conn.execute(
            """SELECT id, job_id, role, task_type, purpose, attested_by, rationale,
                      source, created_at
                 FROM job_provenance_attestations WHERE job_id=?""",
            (job_id,),
        ).fetchone()
        if existing:
            record = dict(zip(
                ("id", "job_id", "role", "task_type", "purpose", "attested_by", "rationale", "source", "created_at"),
                existing,
            ))
            if (
                record["role"], record["task_type"], record["purpose"], record["attested_by"], record["rationale"]
            ) == (role, task_type, purpose, attested_by, rationale):
                conn.commit()
                return False, record
            raise ValueError(f"job {job_id} already has a conflicting provenance attestation")

        cursor = conn.execute(
            """INSERT INTO job_provenance_attestations
                   (job_id, role, task_type, purpose, attested_by, rationale, source, created_at)
               VALUES (?, ?, ?, ?, ?, ?, 'local-cli', ?)""",
            (job_id, role, task_type, purpose, attested_by, rationale, now),
        )
        row = conn.execute(
            """SELECT id, job_id, role, task_type, purpose, attested_by, rationale,
                      source, created_at
                 FROM job_provenance_attestations WHERE id=?""",
            (cursor.lastrowid,),
        ).fetchone()
        conn.commit()
        return True, dict(zip(
            ("id", "job_id", "role", "task_type", "purpose", "attested_by", "rationale", "source", "created_at"),
            row,
        ))
    except Exception:
        conn.rollback()
        raise


def cmd_provenance_attest(
    job_id: str, role: str, task_type: str, reason: str, confirmation: str,
) -> int:
    expected_confirmation = f"{job_id}:{role}:{task_type}"
    if confirmation != expected_confirmation:
        print(
            "Attestation refused. Set --confirm to the exact value "
            f"{expected_confirmation!r} after reviewing the job and classification.",
            file=sys.stderr,
        )
        return 1

    from synlynk import _get_db
    from synlynk.team import get_username

    attestor = get_username()
    if not attestor or attestor == "unknown":
        print("Attestation refused: Synlynk could not identify the local operator.", file=sys.stderr)
        return 1
    conn = _get_db()
    try:
        snapshot = get_job_provenance_snapshot(conn, job_id)
        if not snapshot:
            print(f"Attestation refused: job {job_id!r} does not exist.", file=sys.stderr)
            return 1
        try:
            purpose = _purpose_for_attestation(role, task_type)
            print(
                f"Job {job_id}: role={snapshot['role']!r}, task_type={snapshot['task_type']!r}, "
                f"task_type_explicit={snapshot['task_type_explicit']!r}, purpose={snapshot['purpose']!r}, "
                f"harness={snapshot['harness']!r}, model={snapshot['model']!r}"
            )
            print(
                f"Attestation: role={role!r}, task_type={task_type!r}, purpose={purpose!r}, "
                f"attested_by=@{attestor}, source='local-cli'"
            )
            inserted, record = record_job_provenance_attestation(
                conn, job_id=job_id, role=role, task_type=task_type,
                attested_by=attestor, rationale=reason,
            )
        except ValueError as exc:
            print(f"Attestation refused: {exc}", file=sys.stderr)
            return 1
        action = "recorded" if inserted else "already recorded"
        print(f"Human provenance attestation {action} for {job_id} (id={record['id']}).")
        return 0
    finally:
        conn.close()
