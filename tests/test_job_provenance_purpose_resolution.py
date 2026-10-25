"""Tests for dispatch purpose defaulting and historical attestation resolution (gh:#2606)."""

from __future__ import annotations

import sqlite3
import pytest


def test_job_purpose_dispatch_defaults_for_dev_and_qa_when_task_type_unspecified():
    from synlynk.dispatch import _job_purpose

    # dev role defaults to implementation when task_type defaulted
    assert _job_purpose("dev", "implement", explicit=True) == "implementation"

    # qa role defaults to review when task_type defaulted
    assert _job_purpose("qa", "review", explicit=True) == "review"

    # when task_type is None, _job_purpose is other per spec
    assert _job_purpose("dev", None, explicit=False) == "other"
    assert _job_purpose(None, None, explicit=False) == "other"


def test_attestation_repairs_historical_job_with_purpose_other(tmp_path, monkeypatch):
    import synlynk
    import synlynk.db as db
    from synlynk.provenance import (
        get_valid_job_provenance_attestation,
        record_job_provenance_attestation,
    )

    db_path = tmp_path / "state.db"
    monkeypatch.setattr(synlynk, "DB_PATH", str(db_path))
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(db_path))

    conn = synlynk._get_db()
    try:
        # Simulate historical v0.25.5 job with purpose='other' and un-explicit task_type
        conn.execute(
            """INSERT INTO daemon_jobs
               (job_id, agent, harness, role, task, enqueued_at, resolved_model,
                purpose, task_type, task_type_explicit)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("job-historical-repair", "codex", "codex", "dev", "fix bug in parser",
             "2026-10-24T12:00:00Z", "gpt-5.6-sol", "other", "", 0),
        )
        conn.commit()
    finally:
        conn.close()

    conn = synlynk._get_db()
    try:
        # Before attestation, purpose='other' is NOT an implementation purpose
        assert not db._job_has_implementation_purpose(conn, "job-historical-repair")

        # Record human attestation
        record_job_provenance_attestation(
            conn,
            job_id="job-historical-repair",
            role="dev",
            task_type="implement",
            attested_by="@nikhilsoman",
            rationale="Verified code implementation in commit",
        )
        conn.commit()

        # Attestation must be considered valid
        attestation = get_valid_job_provenance_attestation(conn, "job-historical-repair")
        assert attestation is not None
        assert attestation["purpose"] == "implementation"

        # Now _job_has_implementation_purpose must return True!
        assert db._job_has_implementation_purpose(conn, "job-historical-repair")
    finally:
        conn.close()
