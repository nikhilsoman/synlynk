import sqlite3

from synlynk.db import _migrate_db
from synlynk.uxcore import get_gantt_data, get_gantt_goal_pivot_data


def _db(tmp_path):
    path = tmp_path / "state.db"
    conn = sqlite3.connect(path)
    _migrate_db(conn)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS state_identity ("
        "product_id TEXT NOT NULL, mode TEXT NOT NULL DEFAULT 'repo', "
        "canonical_path TEXT NOT NULL DEFAULT ''"
        ")"
    )
    conn.execute(
        "INSERT INTO state_identity (product_id, mode, canonical_path) VALUES (?, ?, ?)",
        ("prod-p", "repo", str(tmp_path)),
    )
    conn.execute(
        "INSERT INTO goals (goal_id, product_id, outcome, criterion, status) "
        "VALUES ('goal-g1', 'prod-p', 'Outcome 1', 'Criterion', 'active')"
    )
    conn.commit()
    return path, conn


def _story(conn, story_id, title, phase="build"):
    conn.execute(
        "INSERT INTO stories (story_id, title, status, phase) VALUES (?, ?, 'open', ?)",
        (story_id, title, phase),
    )


def test_contribution_edge_attaches_tasks(tmp_path):
    path, conn = _db(tmp_path)
    conn.execute(
        "INSERT INTO roadmap_arcs (version, title, notes, goal_id, status) "
        "VALUES ('arc-1', 'Arc 1', 'Governed by goal-g1', 'goal-g1', 'active')"
    )
    conn.execute(
        "INSERT INTO roadmap_phases (arc_version, phase_title, status) "
        "VALUES ('arc-1', 'Execution', 'active')"
    )
    _story(conn, "story-s1", "Story S1")
    conn.execute(
        "INSERT INTO goal_contributions (goal_id, story_id, link_status) "
        "VALUES ('goal-g1', 'story-s1', 'linked')"
    )
    conn.commit()
    conn.close()

    releases = get_gantt_data(str(path))
    assert sum(len(stage.tasks) for stage in releases[0].stages) == 1


def test_phase_label_join_is_a_fallback(tmp_path):
    path, conn = _db(tmp_path)
    conn.execute("INSERT INTO roadmap_arcs (version, title) VALUES ('arc-1', 'Arc 1')")
    conn.execute(
        "INSERT INTO roadmap_phases (arc_version, phase_title) VALUES ('arc-1', 'Build')"
    )
    _story(conn, "story-label", "Legacy story", phase="build")
    conn.commit()
    conn.close()

    assert len(get_gantt_data(str(path))[0].stages[0].tasks) == 1


def test_story_matching_multiple_tiers_attaches_once(tmp_path):
    path, conn = _db(tmp_path)
    conn.execute(
        "INSERT INTO roadmap_arcs (version, title, notes, goal_id) "
        "VALUES ('arc-1', 'Arc 1', 'goal-g1', 'goal-g1')"
    )
    conn.execute(
        "INSERT INTO roadmap_phases (arc_version, phase_title, story_id) "
        "VALUES ('arc-1', 'Build', 'story-once')"
    )
    _story(conn, "story-once", "One story", phase="build")
    conn.execute(
        "INSERT INTO goal_contributions (goal_id, story_id, link_status) "
        "VALUES ('goal-g1', 'story-once', 'linked')"
    )
    conn.commit()
    conn.close()

    releases = get_gantt_data(str(path))
    assert sum(len(stage.tasks) for stage in releases[0].stages) == 1


def test_goal_pivot_has_synthetic_lane_for_arc_less_goal(tmp_path):
    path, conn = _db(tmp_path)
    _story(conn, "story-synthetic", "Unscheduled story")
    conn.execute(
        "INSERT INTO goal_contributions (goal_id, story_id, link_status) "
        "VALUES ('goal-g1', 'story-synthetic', 'linked')"
    )
    conn.commit()
    conn.close()

    goals = get_gantt_goal_pivot_data(str(path))
    assert goals[0]["lanes"][0]["name"] == "Unscheduled"
    assert goals[0]["lanes"][0]["stages"][0].tasks[0].id == "story-synthetic"


def test_goal_pivot_has_unmapped_lane(tmp_path):
    path, conn = _db(tmp_path)
    _story(conn, "story-unresolved", "Unresolved story")
    conn.execute(
        "INSERT INTO goal_contributions (goal_id, story_id, link_status, skip_reason) "
        "VALUES ('none', 'story-unresolved', 'unresolved', 'no matching workspace goal')"
    )
    conn.commit()
    conn.close()

    goals = get_gantt_goal_pivot_data(str(path))
    unmapped = next(item for item in goals if item["id"] == "unmapped")
    assert unmapped["lanes"][0]["name"] == "Unmapped"
    assert unmapped["lanes"][0]["stages"][0].tasks[0].id == "story-unresolved"
