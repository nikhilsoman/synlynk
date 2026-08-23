from unittest.mock import MagicMock, patch

import synlynk
from synlynk.db import cmd_story_create, cmd_story_ready
from synlynk.tpm_sweep import _ready_stories
from synlynk.tpm_sweep import run_sweep_pass


def test_run_sweep_pass_advances_authorized_story(isolated_db, project_dir):
    story_id = cmd_story_create(title="test story", story_id="story-1")
    cmd_story_ready(story_id)
    with patch("synlynk.tpm_sweep.check_authority") as mock_auth, \
            patch("synlynk.tpm_sweep.dispatch_agent") as mock_dispatch:
        mock_auth.return_value = MagicMock(allowed=True, requires_approval=False)
        mock_dispatch.return_value = {"id": "job-1", "agent": "codex"}
        summary = run_sweep_pass()
    assert summary["advanced"] == 1
    assert summary["parked"] == 0


def test_run_sweep_pass_parks_story_requiring_approval(isolated_db, project_dir):
    story_id = cmd_story_create(title="release story", story_id="story-2")
    cmd_story_ready(story_id)
    with patch("synlynk.tpm_sweep.check_authority") as mock_auth, \
            patch("synlynk.tpm_sweep.raise_approval_ticket") as mock_ticket, \
            patch("synlynk.tpm_sweep.emit_awaiting_approval") as mock_event:
        mock_auth.return_value = MagicMock(
            allowed=True, requires_approval=True, reason="named_release"
        )
        mock_ticket.return_value = "https://github.com/x/y/issues/1"
        summary = run_sweep_pass()
    assert summary["parked"] == 1
    assert summary["advanced"] == 0


def test_run_sweep_pass_reuses_open_ticket_without_refiling(isolated_db, project_dir):
    from synlynk.db import _find_ticket

    story_id = cmd_story_create(title="release story", story_id="story-3")
    cmd_story_ready(story_id)
    with patch("synlynk.tpm_sweep.check_authority") as mock_auth, \
            patch("synlynk.tpm_sweep.raise_approval_ticket") as mock_ticket, \
            patch("synlynk.tpm_sweep.emit_awaiting_approval") as mock_event:
        mock_auth.return_value = MagicMock(
            allowed=True, requires_approval=True, reason="named_release"
        )
        mock_ticket.return_value = "https://example.com/x/y/issues/5"
        # First pass: files a ticket
        summary1 = run_sweep_pass()
        # Second pass: same story, same open ticket already recorded
        summary2 = run_sweep_pass()
    assert summary1["parked"] == 1
    assert summary2["parked"] == 1
    assert mock_ticket.call_count == 1  # not re-filed on the second pass
    ticket = _find_ticket(story_id, "task_dispatch:implement", "open")
    assert ticket is not None


def test_run_sweep_pass_dispatches_and_consumes_resolved_ticket(isolated_db, project_dir):
    from synlynk.db import _find_ticket, _insert_ticket

    story_id = cmd_story_create(title="release story", story_id="story-4")
    cmd_story_ready(story_id)
    _insert_ticket(story_id, "task_dispatch:implement", "https://example.com/x/y/issues/6")
    conn = synlynk._get_db()
    conn.execute(
        "UPDATE approval_tickets SET status='resolved' WHERE story_id=?", (story_id,)
    )
    conn.commit()
    conn.close()
    with patch("synlynk.tpm_sweep.check_authority") as mock_auth, \
            patch("synlynk.tpm_sweep.raise_approval_ticket") as mock_ticket, \
            patch("synlynk.tpm_sweep.dispatch_agent") as mock_dispatch:
        mock_auth.return_value = MagicMock(
            allowed=True, requires_approval=True, reason="named_release"
        )
        mock_dispatch.return_value = {"id": "job-2", "agent": "codex"}
        summary = run_sweep_pass()
    assert summary["advanced"] == 1
    assert summary["parked"] == 0
    mock_ticket.assert_not_called()
    assert _find_ticket(story_id, "task_dispatch:implement", "resolved") is None
    assert _find_ticket(story_id, "task_dispatch:implement", "consumed") is not None


def _story_with_job(project_dir, job_status):
    story_id = cmd_story_create(title=f"Story with {job_status} job")
    cmd_story_ready(story_id)
    conn = synlynk._get_db()
    conn.execute(
        "INSERT INTO daemon_jobs "
        "(job_id, agent, task, story_id, status, enqueued_at) "
        "VALUES (?, 'codex', 'test task', ?, ?, '2026-01-01T00:00:00')",
        (f"job-{job_status}", story_id, job_status),
    )
    conn.commit()
    conn.close()
    return story_id


def test_ready_stories_excludes_story_with_done_job(project_dir):
    story_id = _story_with_job(project_dir, "done")

    assert story_id not in {story["story_id"] for story in _ready_stories()}


def test_ready_stories_includes_story_with_failed_job(project_dir):
    story_id = _story_with_job(project_dir, "failed")

    assert story_id in {story["story_id"] for story in _ready_stories()}
