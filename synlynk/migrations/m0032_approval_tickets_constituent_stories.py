"""Migration 32: persist the constituent story-id set on approval_tickets.

gh:#5246: poll_and_process_proposal_comments() was re-querying live story
eligibility at comment-processing time instead of reading back the exact
set of stories that were proposed-and-reviewed, so a readiness/status
change between proposal-filing and human /approve could cause the wrong
stories to be promoted.
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
    if "constituent_story_ids" not in cols:
        conn.execute("ALTER TABLE approval_tickets ADD COLUMN constituent_story_ids TEXT")


MIGRATION = Migration(version=32, name="add_approval_tickets_constituent_story_ids", up=_up)
