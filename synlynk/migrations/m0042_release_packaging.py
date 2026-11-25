"""Migration 42: goal-cohesive release packaging state (gh:#5525)."""

import sqlite3

from synlynk.migrations import Migration


_LIVE_35_PARENT_ISSUES = ("5498", "5499", "5500", "5501", "5502", "5503", "5504")


def _up(conn: sqlite3.Connection) -> None:
    story_columns = {row[1] for row in conn.execute("PRAGMA table_info(stories)")}
    if story_columns and "umbrella" not in story_columns:
        conn.execute(
            "ALTER TABLE stories ADD COLUMN umbrella INTEGER NOT NULL DEFAULT 0"
        )

    conn.execute(
        """CREATE TABLE IF NOT EXISTS story_dependencies (
            story_id           TEXT NOT NULL,
            depends_on_story_id TEXT NOT NULL,
            PRIMARY KEY (story_id, depends_on_story_id)
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS release_split_approvals (
            goal_id     TEXT NOT NULL,
            phase       TEXT NOT NULL,
            approved_by TEXT,
            approved_at TEXT DEFAULT (datetime('now')),
            PRIMARY KEY (goal_id, phase)
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS goal_packaging_flags (
            goal_id            TEXT PRIMARY KEY,
            independent_phases INTEGER NOT NULL DEFAULT 0
        )"""
    )

    app_cols = {row[1] for row in conn.execute("PRAGMA table_info(approval_tickets)")}
    if app_cols:
        if "goal_id" not in app_cols:
            try:
                conn.execute("ALTER TABLE approval_tickets ADD COLUMN goal_id TEXT")
            except Exception:
                pass
        if "part_index" not in app_cols:
            try:
                conn.execute("ALTER TABLE approval_tickets ADD COLUMN part_index INTEGER DEFAULT 1")
            except Exception:
                pass
        if "total_parts" not in app_cols:
            try:
                conn.execute("ALTER TABLE approval_tickets ADD COLUMN total_parts INTEGER DEFAULT 1")
            except Exception:
                pass
        if "continuation_ticket_url" not in app_cols:
            try:
                conn.execute("ALTER TABLE approval_tickets ADD COLUMN continuation_ticket_url TEXT")
            except Exception:
                pass
        if "split_reason" not in app_cols:
            try:
                conn.execute("ALTER TABLE approval_tickets ADD COLUMN split_reason TEXT")
            except Exception:
                pass

    if "gh_issue" in story_columns:
        placeholders = ", ".join("?" for _ in _LIVE_35_PARENT_ISSUES)
        conn.execute(
            f"UPDATE stories SET umbrella = 1 WHERE gh_issue IN ({placeholders})",
            _LIVE_35_PARENT_ISSUES,
        )


MIGRATION = Migration(version=42, name="release_packaging", up=_up)
