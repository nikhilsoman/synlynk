import sqlite3

import pytest


@pytest.fixture
def ledger_conn():
    return sqlite3.connect(":memory:")


def _sample(job_id: str, *, cohort: str = "validation") -> dict:
    return {
        "job_id": job_id,
        "cohort": cohort,
        "task_class": "test_summary",
        "task_digest": f"digest-{job_id}",
        "receipt": {"job_id": job_id, "isolated": True},
    }


def test_migration_seeds_the_immutable_historical_cohort_once(ledger_conn):
    from synlynk.local_pilot_ledger import load_pilot_status
    from synlynk.migrations.runner import run_pending_migrations

    run_pending_migrations(ledger_conn)
    first_status = load_pilot_status(ledger_conn)

    run_pending_migrations(ledger_conn)
    second_status = load_pilot_status(ledger_conn)

    expected = {"cohort": "historical", "accepted": 8, "eligible": 12}
    assert first_status["historical"] == expected
    assert second_status["historical"] == expected
    assert ledger_conn.execute(
        "SELECT COUNT(*) FROM local_pilot_cohort_summaries WHERE cohort = 'historical'"
    ).fetchone()[0] == 1


def test_admission_rejects_duplicate_jobs_and_unknown_cohorts(ledger_conn):
    from synlynk.local_pilot_ledger import ensure_local_pilot_ledger, record_admission

    ensure_local_pilot_ledger(ledger_conn)
    record_admission(ledger_conn, _sample("job-1"))

    with pytest.raises(ValueError, match="duplicate job_id"):
        record_admission(ledger_conn, _sample("job-1"))
    with pytest.raises(ValueError, match="unknown cohort"):
        record_admission(ledger_conn, _sample("job-2", cohort="unknown"))


def test_outcome_recording_rejects_unknown_verdicts(ledger_conn):
    from synlynk.local_pilot_ledger import (
        ensure_local_pilot_ledger,
        record_admission,
        record_quality_verdict,
        record_safety_outcome,
    )

    ensure_local_pilot_ledger(ledger_conn)
    record_admission(ledger_conn, _sample("job-1"))

    with pytest.raises(ValueError, match="unknown safety verdict"):
        record_safety_outcome(ledger_conn, "job-1", "unsafe-ish", "bad", None)
    with pytest.raises(ValueError, match="unknown quality verdict"):
        record_quality_verdict(ledger_conn, "job-1", "codex", "maybe", "bad", "rule")


def test_later_review_preserves_an_earlier_jobs_evidence(ledger_conn):
    from synlynk.local_pilot_ledger import (
        ensure_local_pilot_ledger,
        record_admission,
        record_quality_verdict,
        record_safety_outcome,
    )

    ensure_local_pilot_ledger(ledger_conn)
    earlier = record_admission(ledger_conn, _sample("job-1"))
    record_safety_outcome(ledger_conn, "job-1", "passed", "isolated", {"safe": True})
    record_admission(ledger_conn, _sample("job-2"))
    record_quality_verdict(ledger_conn, "job-2", "codex", "accepted", "correct", "qualified")

    stored = ledger_conn.execute(
        "SELECT receipt_digest, safety_verdict, safety_reason, quality_verdict "
        "FROM local_pilot_evidence WHERE job_id = 'job-1'"
    ).fetchone()
    assert stored == (earlier["receipt_digest"], "passed", "isolated", "pending")


def test_database_rejects_deleting_evidence_or_mutating_or_deleting_history(ledger_conn):
    """Removing audit rows or changing the fixed 8/12 record must fail in SQLite."""
    from synlynk.local_pilot_ledger import ensure_local_pilot_ledger, record_admission

    ensure_local_pilot_ledger(ledger_conn)
    record_admission(ledger_conn, _sample("job-1"))

    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        ledger_conn.execute("DELETE FROM local_pilot_evidence WHERE job_id = 'job-1'")
    with pytest.raises(sqlite3.IntegrityError, match="historical"):
        ledger_conn.execute(
            "UPDATE local_pilot_cohort_summaries SET accepted = 0 WHERE cohort = 'historical'"
        )
    with pytest.raises(sqlite3.IntegrityError, match="historical"):
        ledger_conn.execute("DELETE FROM local_pilot_cohort_summaries WHERE cohort = 'historical'")


def test_status_separates_pending_rejected_and_safety_failed_samples(ledger_conn):
    """Changing status to count raw admissions as eligible would break this ledger view."""
    from synlynk.local_pilot_ledger import (
        ensure_local_pilot_ledger,
        load_pilot_status,
        record_admission,
        record_quality_verdict,
        record_safety_outcome,
    )

    ensure_local_pilot_ledger(ledger_conn)
    record_admission(ledger_conn, _sample("pending"))
    record_admission(ledger_conn, _sample("rejected"))
    record_safety_outcome(ledger_conn, "rejected", "passed", "contained", {"safe": True})
    record_quality_verdict(ledger_conn, "rejected", "codex", "rejected", "incorrect", "qualified")
    record_admission(ledger_conn, _sample("unsafe"))
    record_safety_outcome(ledger_conn, "unsafe", "failed", "scope drift", {"safe": False})

    assert load_pilot_status(ledger_conn)["validation"] == {
        "cohort": "validation",
        "accepted": 0,
        "eligible": 0,
        "pending": 1,
        "rejected": 1,
        "safety_failed": 1,
    }


def test_ensure_uses_migration_history_and_rolls_back_a_failed_migration(ledger_conn, monkeypatch):
    """A failed schema install must leave neither schema nor migration history behind."""
    from synlynk.local_pilot_ledger import ensure_local_pilot_ledger
    from synlynk.migrations import Migration
    from synlynk.migrations import runner as migration_runner

    def fail_after_schema_creation(conn):
        conn.execute("CREATE TABLE local_pilot_atomicity_probe (id INTEGER PRIMARY KEY)")
        raise RuntimeError("forced migration failure")

    monkeypatch.setattr(
        migration_runner,
        "MIGRATIONS",
        [Migration(version=24, name="atomicity_probe", up=fail_after_schema_creation)],
    )

    with pytest.raises(RuntimeError, match="forced migration failure"):
        ensure_local_pilot_ledger(ledger_conn)

    assert ledger_conn.execute("PRAGMA user_version").fetchone()[0] == 0
    assert ledger_conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'local_pilot_atomicity_probe'"
    ).fetchone() is None
    assert ledger_conn.execute("SELECT COUNT(*) FROM migration_history").fetchone()[0] == 0
