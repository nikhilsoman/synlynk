"""Migration 34: persist the per-release theme string on approval_tickets.

Roadmap Studio needs to display each proposal's theme, but today the theme
computed in tpm_sweep.package_next_release_proposal() is only ever baked
into the GitHub issue title text (``[Proposal] {ver}: {theme}``) and is not
written to a column Studio's read path can reach.

See docs/superpowers/specs/2026-11-16-roadmap-studio-v2-theming-provisional-ux-design.md.
"""
import sqlite3

from synlynk.migrations import Migration


def _up(conn: sqlite3.Connection) -> None:
    table_exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='approval_tickets'"
    ).fetchone()
    if not table_exists:
        return
    cols = {row[1] for row in conn.execute("PRAGMA table_info(approval_tickets)")}
    if "theme" not in cols:
        try:
            conn.execute("ALTER TABLE approval_tickets ADD COLUMN theme TEXT")
        except sqlite3.OperationalError as exc:
            if "duplicate column name" not in str(exc).lower():
                raise
    conn.execute(
        "UPDATE approval_tickets SET theme=? "
        "WHERE action='release_proposal' AND story_id='v0.36.1' AND theme IS NULL",
        ("Milestone v0.36.1",),
    )


MIGRATION = Migration(version=34, name="add_approval_tickets_theme", up=_up)
