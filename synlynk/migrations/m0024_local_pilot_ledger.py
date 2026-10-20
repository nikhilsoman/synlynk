"""Migration 24: canonical, append-only Local pilot evidence ledger."""

import sqlite3

from synlynk.migrations import Migration


def _up(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS local_pilot_cohort_summaries (
            cohort TEXT PRIMARY KEY CHECK (cohort = 'historical'),
            accepted INTEGER NOT NULL CHECK (accepted >= 0),
            eligible INTEGER NOT NULL CHECK (eligible >= accepted)
        );

        CREATE TABLE IF NOT EXISTS local_pilot_evidence (
            job_id TEXT PRIMARY KEY,
            cohort TEXT NOT NULL CHECK (cohort IN ('validation', 'expansion')),
            task_class TEXT NOT NULL,
            task_digest TEXT NOT NULL,
            receipt_json TEXT NOT NULL,
            receipt_digest TEXT NOT NULL,
            admitted_at TEXT NOT NULL,
            safety_verdict TEXT NOT NULL DEFAULT 'pending'
                CHECK (safety_verdict IN ('pending', 'passed', 'failed')),
            safety_reason TEXT,
            safety_receipt_json TEXT,
            safety_receipt_digest TEXT,
            safety_recorded_at TEXT,
            quality_verdict TEXT NOT NULL DEFAULT 'pending'
                CHECK (quality_verdict IN ('pending', 'accepted', 'rejected')),
            reviewer_harness TEXT,
            reviewer_rationale TEXT,
            reviewer_selection_reason TEXT,
            quality_recorded_at TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_local_pilot_evidence_cohort
        ON local_pilot_evidence(cohort, admitted_at);

        CREATE TRIGGER IF NOT EXISTS local_pilot_evidence_immutable_fields
        BEFORE UPDATE ON local_pilot_evidence
        WHEN OLD.job_id != NEW.job_id
          OR OLD.cohort != NEW.cohort
          OR OLD.task_class != NEW.task_class
          OR OLD.task_digest != NEW.task_digest
          OR OLD.receipt_json != NEW.receipt_json
          OR OLD.receipt_digest != NEW.receipt_digest
          OR OLD.admitted_at != NEW.admitted_at
        BEGIN
            SELECT RAISE(ABORT, 'local pilot evidence is immutable');
        END;

        CREATE TRIGGER IF NOT EXISTS local_pilot_evidence_safety_terminal
        BEFORE UPDATE ON local_pilot_evidence
        WHEN OLD.safety_verdict != 'pending'
          AND (OLD.safety_verdict != NEW.safety_verdict
               OR OLD.safety_reason IS NOT NEW.safety_reason
               OR OLD.safety_receipt_json IS NOT NEW.safety_receipt_json
               OR OLD.safety_receipt_digest IS NOT NEW.safety_receipt_digest
               OR OLD.safety_recorded_at IS NOT NEW.safety_recorded_at)
        BEGIN
            SELECT RAISE(ABORT, 'local pilot safety outcome is terminal');
        END;

        CREATE TRIGGER IF NOT EXISTS local_pilot_evidence_quality_terminal
        BEFORE UPDATE ON local_pilot_evidence
        WHEN OLD.quality_verdict != 'pending'
          AND (OLD.quality_verdict != NEW.quality_verdict
               OR OLD.reviewer_harness IS NOT NEW.reviewer_harness
               OR OLD.reviewer_rationale IS NOT NEW.reviewer_rationale
               OR OLD.reviewer_selection_reason IS NOT NEW.reviewer_selection_reason
               OR OLD.quality_recorded_at IS NOT NEW.quality_recorded_at)
        BEGIN
            SELECT RAISE(ABORT, 'local pilot quality verdict is terminal');
        END;
        """
    )
    conn.execute(
        "INSERT OR IGNORE INTO local_pilot_cohort_summaries (cohort, accepted, eligible) "
        "VALUES ('historical', 8, 12)"
    )


MIGRATION = Migration(version=24, name="local_pilot_ledger", up=_up)
