import pytest

from synlynk import _get_db
from synlynk.governs_cli import cmd_governs_start


def test_governs_start_creates_goal_and_phase_atomically():
    conn = _get_db()
    conn.execute("INSERT INTO roadmap_arcs (version, title) VALUES ('v-test', 'Test')")
    conn.commit()
    conn.close()
    goal_id, phase_id = cmd_governs_start(
        outcome="Make governed work traceable",
        criterion="Every durable initiative has a goal and phase",
        version="v-test",
        phase_title="Governance hardening",
        role="pm",
    )

    conn = _get_db()
    goal = conn.execute(
        "SELECT goal_id, phase_id, placement_status, placement_reason FROM goals WHERE goal_id=?",
        (goal_id,),
    ).fetchone()
    phase = conn.execute(
        "SELECT id, arc_version, phase_title FROM roadmap_phases WHERE id=?",
        (phase_id,),
    ).fetchone()
    conn.close()

    assert goal == (goal_id, phase_id, "placed", None)
    assert phase == (phase_id, "v-test", "Governance hardening")


def test_governs_start_rolls_back_goal_when_phase_creation_fails():
    with pytest.raises(ValueError, match="no roadmap arc"):
        cmd_governs_start(
            outcome="Should roll back",
            criterion="No partial goal",
            version="missing-arc",
            phase_title="Impossible",
            role="pm",
        )

    conn = _get_db()
    assert conn.execute(
        "SELECT 1 FROM goals WHERE outcome='Should roll back'"
    ).fetchone() is None
    conn.close()


def test_governs_start_requires_reason_for_unplaced_goal():
    with pytest.raises(ValueError, match="reason"):
        cmd_governs_start(
            outcome="Speculative idea",
            criterion="It remains explicitly speculative",
            unplaced=True,
            role="pm",
        )


def test_governs_start_can_create_explicit_unplaced_goal():
    goal_id, phase_id = cmd_governs_start(
        outcome="Speculative idea",
        criterion="It remains explicitly speculative",
        unplaced=True,
        placement_reason="Waiting for product boundary decision",
        role="pm",
    )

    assert phase_id is None
    conn = _get_db()
    row = conn.execute(
        "SELECT phase_id, placement_status, placement_reason FROM goals WHERE goal_id=?",
        (goal_id,),
    ).fetchone()
    conn.close()
    assert row == (None, "unplaced", "Waiting for product boundary decision")
