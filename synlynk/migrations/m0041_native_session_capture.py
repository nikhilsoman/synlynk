"""Migration 41: native-session capture storage (LIVE-35, gh:#5457).

SELECT * in a view freezes columns at creation; the migration drops and recreates
the view, and any later migration that adds cost_entries columns must recreate it too.
"""

import sqlite3

from synlynk.migrations import Migration


def _up(conn: sqlite3.Connection) -> None:
    conn.execute(
        """CREATE TABLE IF NOT EXISTS native_capture_cursor (
            session_id      TEXT PRIMARY KEY,
            transcript_path TEXT NOT NULL,
            byte_offset     INTEGER NOT NULL DEFAULT 0,
            anchor          TEXT NOT NULL DEFAULT '',
            final           INTEGER NOT NULL DEFAULT 0,
            updated_at      TEXT DEFAULT (datetime('now'))
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS session_pr_links (
            session_id    TEXT NOT NULL,
            pr_number     INTEGER NOT NULL,
            role          TEXT NOT NULL DEFAULT 'implementer',
            first_seen_ts TEXT,
            source        TEXT NOT NULL,
            PRIMARY KEY (session_id, pr_number, role)
        )"""
    )
    cost_entries_exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='cost_entries'"
    ).fetchone()
    if cost_entries_exists:
        # Ensure cost_entries has session_id column for legacy databases where it was not added
        cols = {row[1] for row in conn.execute("PRAGMA table_info(cost_entries)")}
        if "session_id" not in cols:
            conn.execute("ALTER TABLE cost_entries ADD COLUMN session_id TEXT")
        conn.execute(
            """CREATE UNIQUE INDEX IF NOT EXISTS idx_cost_entries_transcript_bucket
               ON cost_entries (session_id, model, substr(session_date, 1, 10))
               WHERE cost_source = 'transcript_derived'"""
        )
        conn.execute("DROP VIEW IF EXISTS cost_entries_effective")
        conn.execute(
            """CREATE VIEW cost_entries_effective AS
               SELECT * FROM cost_entries
               WHERE COALESCE(estimate_basis, '') != 'superseded_by_transcript'"""
        )


MIGRATION = Migration(version=41, name="native_session_capture", up=_up)
