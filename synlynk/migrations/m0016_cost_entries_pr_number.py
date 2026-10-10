"""Migration 16: add the pr_number column cost_entries was missing.

gh:#2086 / LIVE-23 (gh:#2087): PR #2059's native-session provenance carve-out
reads and writes a cost_entries.pr_number column that no migration ever
added, crashing `synlynk pr check` and `synlynk cost log --pr` with
sqlite3.OperationalError for any PR not attributable via capability_ratings
or dispatch/<harness>/job-<id> branch naming.
"""
import sqlite3

from synlynk.migrations import Migration


def _up(conn: sqlite3.Connection) -> None:
    table_exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='cost_entries'"
    ).fetchone()
    if not table_exists:
        return
    cols = {row[1] for row in conn.execute("PRAGMA table_info(cost_entries)")}
    if "pr_number" not in cols:
        conn.execute("ALTER TABLE cost_entries ADD COLUMN pr_number INTEGER")


MIGRATION = Migration(version=16, name="add_cost_entries_pr_number", up=_up)
