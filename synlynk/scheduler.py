"""Batch fleet dispatch scheduler.

Assigns ready stories to agents using the existing capability -> quota -> cost
routing helpers in synlynk/__init__.py, with fleet-level in-batch headroom
accounting layered on top (single-story routing has no notion of "already
spent this token budget on story A three rows up in the same run").

Uses deferred/local imports from synlynk (not the dispatch.py _pkg() helper)
because this module is imported into synlynk/cli.py directly, not re-exported
through synlynk/__init__.py at module-load time -- no import cycle to avoid.
"""

MAX_STORY_RETRIES = 2


def _story_failed_agents(conn, story_id: str) -> set:
    """Agents that have a 'failed' daemon_jobs row for this story."""
    rows = conn.execute(
        "SELECT DISTINCT agent FROM daemon_jobs WHERE story_id=? AND status='failed'",
        (story_id,),
    ).fetchall()
    return {r[0] for r in rows}


def _story_retry_count(conn, story_id: str) -> int:
    """Number of failed daemon_jobs attempts recorded for this story."""
    row = conn.execute(
        "SELECT COUNT(*) FROM daemon_jobs WHERE story_id=? AND status='failed'",
        (story_id,),
    ).fetchone()
    return row[0] if row else 0
