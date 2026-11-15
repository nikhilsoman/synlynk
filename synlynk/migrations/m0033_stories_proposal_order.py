"""Migration 33: add stories.proposal_order for Roadmap Studio drag-to-reorder.

See docs/superpowers/specs/2026-11-15-roadmap-studio-visual-proposal-ui-design.md.
This is a display-ordering hint local to a single release_proposal ticket — it
does not feed goals.roadmap_priority or the Approach C roadmap_arcs/roadmap_phases
views, and today's /prioritize binary flag (stories.priority) is untouched.
"""
import sqlite3

from synlynk.migrations import Migration


def _up(conn: sqlite3.Connection) -> None:
    table_exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='stories'"
    ).fetchone()
    if not table_exists:
        return
    cols = {row[1] for row in conn.execute("PRAGMA table_info(stories)")}
    if "proposal_order" not in cols:
        conn.execute("ALTER TABLE stories ADD COLUMN proposal_order INTEGER")


MIGRATION = Migration(version=33, name="add_stories_proposal_order", up=_up)
