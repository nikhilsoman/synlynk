import synlynk

from synlynk.db import cmd_story_create, cmd_story_done
from synlynk.events import pending_events


def test_story_done_sets_status_and_emits_event(project_dir):
    story_id = cmd_story_create(title="Test story")
    cmd_story_done(story_id)
    conn = synlynk._get_db()
    status = conn.execute(
        "SELECT status FROM stories WHERE story_id=?", (story_id,)
    ).fetchone()[0]
    conn.close()
    assert status == "done"
    pending = pending_events("test-observer", "story_done")
    assert len(pending) == 1
    assert pending[0]["payload"]["story_id"] == story_id


def test_story_done_includes_linked_goal_ids_in_payload(project_dir):
    from synlynk.db import cmd_goal_create, cmd_goal_link

    story_id = cmd_story_create(title="Test story")
    goal_id = cmd_goal_create("Outcome", "Criterion")
    cmd_goal_link(story_id, goal_id)
    cmd_story_done(story_id)
    pending = pending_events("test-observer", "story_done")
    assert pending[0]["payload"]["goal_ids"] == [goal_id]


def test_story_done_unknown_story_prints_error(project_dir, capsys):
    cmd_story_done("story-doesnotexist")
    captured = capsys.readouterr()
    assert "not found" in captured.out
