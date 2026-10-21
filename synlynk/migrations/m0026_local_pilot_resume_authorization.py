"""Migration 26: append-only resume authorizations for Local pilot epochs."""

import sqlite3

from synlynk.migrations import Migration


def _up(conn: sqlite3.Connection) -> None:
    statements = (
        """CREATE TABLE IF NOT EXISTS local_pilot_resume_authorizations (
            authorization_id TEXT PRIMARY KEY, created_at TEXT NOT NULL,
            signed_payload_json TEXT NOT NULL, signed_payload_digest TEXT NOT NULL,
            config_fingerprint TEXT NOT NULL, remediation_reference TEXT NOT NULL,
            verification_reference TEXT NOT NULL,
            safety_watermark INTEGER NOT NULL CHECK (safety_watermark >= 0),
            preflight_receipt_json TEXT NOT NULL, preflight_receipt_digest TEXT NOT NULL,
            state TEXT NOT NULL CHECK (state IN ('activating', 'active', 'revoked', 'failed')),
            activated_at TEXT, revoked_at TEXT, terminal_reason TEXT
        )""",
        """CREATE UNIQUE INDEX IF NOT EXISTS idx_local_pilot_resume_one_active
        ON local_pilot_resume_authorizations(state) WHERE state = 'active'""",
        """CREATE TRIGGER IF NOT EXISTS local_pilot_resume_authorization_no_delete
        BEFORE DELETE ON local_pilot_resume_authorizations BEGIN
            SELECT RAISE(ABORT, 'local pilot resume authorization is append-only');
        END""",
        """CREATE TRIGGER IF NOT EXISTS local_pilot_resume_authorization_immutable_fields
        BEFORE UPDATE ON local_pilot_resume_authorizations
        WHEN OLD.authorization_id != NEW.authorization_id OR OLD.created_at != NEW.created_at
          OR OLD.signed_payload_json != NEW.signed_payload_json
          OR OLD.signed_payload_digest != NEW.signed_payload_digest
          OR OLD.config_fingerprint != NEW.config_fingerprint
          OR OLD.remediation_reference != NEW.remediation_reference
          OR OLD.verification_reference != NEW.verification_reference
          OR OLD.safety_watermark != NEW.safety_watermark
          OR OLD.preflight_receipt_json != NEW.preflight_receipt_json
          OR OLD.preflight_receipt_digest != NEW.preflight_receipt_digest
        BEGIN SELECT RAISE(ABORT, 'local pilot resume authorization is append-only'); END""",
        """CREATE TRIGGER IF NOT EXISTS local_pilot_resume_authorization_lifecycle
        BEFORE UPDATE ON local_pilot_resume_authorizations
        WHEN NOT (
            (OLD.state = 'activating' AND NEW.state = 'active'
             AND OLD.activated_at IS NULL AND NEW.activated_at IS NOT NULL
             AND OLD.revoked_at IS NULL AND NEW.revoked_at IS NULL
             AND OLD.terminal_reason IS NULL AND NEW.terminal_reason IS NULL)
            OR (OLD.state = 'activating' AND NEW.state = 'failed'
             AND OLD.activated_at IS NULL AND NEW.activated_at IS NULL
             AND OLD.revoked_at IS NULL AND NEW.revoked_at IS NOT NULL
             AND OLD.terminal_reason IS NULL AND NEW.terminal_reason IS NOT NULL)
            OR (OLD.state = 'active' AND NEW.state = 'revoked'
             AND OLD.activated_at IS NOT NULL AND NEW.activated_at = OLD.activated_at
             AND OLD.revoked_at IS NULL AND NEW.revoked_at IS NOT NULL
             AND OLD.terminal_reason IS NULL AND NEW.terminal_reason IS NOT NULL)
        ) BEGIN SELECT RAISE(ABORT, 'local pilot resume authorization is append-only'); END""",
    )
    for statement in statements:
        conn.execute(statement)


MIGRATION = Migration(version=26, name="local_pilot_resume_authorization", up=_up)
