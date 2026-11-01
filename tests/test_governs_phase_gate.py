import pytest

from synlynk import _get_db
from synlynk.db import cmd_story_create
from synlynk.governs_cli import cmd_governs_start
from synlynk.governs_gate import dispatch_governs_linkage, story_governs_linkage


def _seed_goal_story(*, placed):
    conn = _get_db()
    conn.execute("INSERT INTO roadmap_arcs (version, title) VALUES ('v-gate', 'Gate')")
    conn.commit()
    conn.close()
    if placed:
        goal_id, _ = cmd_governs_start(
            outcome="Placed goal", criterion="Placed", version="v-gate", phase_title="Phase", role="pm"
        )
    else:
        goal_id, _ = cmd_governs_start(
            outcome="Unplaced goal", criterion="Unplaced", unplaced=True,
            placement_reason="Strategic exploration", role="pm"
        )
    story_id = cmd_story_create(title="Governed story")
    conn = _get_db()
    conn.execute("UPDATE stories SET goal_id=? WHERE story_id=?", (goal_id, story_id))
    conn.commit()
    return conn, story_id


def test_story_linkage_reports_phase_placement():
    conn, story_id = _seed_goal_story(placed=True)
    result = story_governs_linkage(conn, story_id)
    conn.close()
    assert result["linked"] is True
    assert result["phase_placed"] is True


def test_dispatch_rejects_unplaced_goal():
    conn, story_id = _seed_goal_story(placed=False)
    result = dispatch_governs_linkage(conn, story_id)
    conn.close()
    assert result["passed"] is False
    assert result["sentinel"] == "GOVERNS_PHASE_MISSING"

