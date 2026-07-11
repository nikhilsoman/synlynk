from synlynk.db import _parse_roadmap_md


def test_parse_roadmap_md_extracts_goal_tag():
    content = "## v0.11.0 - Agent Ecosystem <!-- goal:goal-a1b2c3d4 -->\nShip the thing\n"
    arcs, phases = _parse_roadmap_md(content)
    assert arcs[0]["goal_id"] == "goal-a1b2c3d4"


def test_parse_roadmap_md_goal_id_none_when_untagged():
    content = "## v0.10.0 - Untagged\nShip the thing\n"
    arcs, phases = _parse_roadmap_md(content)
    assert arcs[0]["goal_id"] is None
