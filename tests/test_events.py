import json
import sqlite3
import pytest
from synlynk.events import emit_event, pending_events, advance_checkpoint, scan_local_events


def test_emit_event_writes_row_and_returns_id(project_dir):
    event_id = emit_event(
        "story_done",
        {"story_id": "story-abc123", "goal_ids": ["goal-xyz789"]},
        emitted_by="cmd_story_done",
    )
    assert isinstance(event_id, int) and event_id > 0

    import synlynk
    conn = synlynk._get_db()
    row = conn.execute(
        "SELECT event_type, payload_json, emitted_by, parent_event_id FROM events WHERE id=?",
        (event_id,),
    ).fetchone()
    conn.close()
    assert row[0] == "story_done"
    assert json.loads(row[1]) == {"story_id": "story-abc123", "goal_ids": ["goal-xyz789"]}
    assert row[2] == "cmd_story_done"
    assert row[3] is None


def test_pending_events_returns_only_events_after_checkpoint(project_dir):
    e1 = emit_event("story_done", {"story_id": "s1"}, emitted_by="test")
    e2 = emit_event("story_done", {"story_id": "s2"}, emitted_by="test")
    advance_checkpoint("workspace-lifecycle-nudge", "story_done", e1)

    pending = pending_events("workspace-lifecycle-nudge", "story_done")

    assert [p["id"] for p in pending] == [e2]
    assert pending[0]["payload"] == {"story_id": "s2"}


def test_pending_events_ignores_other_event_types(project_dir):
    emit_event("pr_merged", {"pr": 1}, emitted_by="test")
    story_event_id = emit_event("story_done", {"story_id": "s1"}, emitted_by="test")

    pending = pending_events("workspace-lifecycle-nudge", "story_done")

    assert [p["id"] for p in pending] == [story_event_id]


def test_advance_checkpoint_never_moves_backward(project_dir):
    e1 = emit_event("story_done", {"story_id": "s1"}, emitted_by="test")
    e2 = emit_event("story_done", {"story_id": "s2"}, emitted_by="test")
    advance_checkpoint("workspace-lifecycle-nudge", "story_done", e2)
    advance_checkpoint("workspace-lifecycle-nudge", "story_done", e1)

    pending = pending_events("workspace-lifecycle-nudge", "story_done")

    assert pending == []


def test_migration_adds_link_status_and_skip_reason_columns(project_dir):
    import synlynk
    conn = synlynk._get_db()
    cols = {row[1] for row in conn.execute("PRAGMA table_info(goal_contributions)")}
    conn.close()
    assert "link_status" in cols
    assert "skip_reason" in cols


def test_scan_local_events_always_emits_cron_heartbeat(project_dir):
    from unittest.mock import patch, MagicMock

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="[]")
        scan_local_events("workspace-lifecycle-nudge")
    pending = pending_events("test-observer", "cron_heartbeat")
    assert len(pending) == 1


def test_scan_local_events_emits_pr_merged_from_gh_output(project_dir):
    from unittest.mock import patch, MagicMock

    gh_stdout = json.dumps([{"number": 99, "title": "Test PR", "mergedAt": "2026-08-08T00:00:00Z"}])
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=gh_stdout),
            MagicMock(returncode=0, stdout=json.dumps({"reviews": []})),
            MagicMock(returncode=0, stdout=""),
        ]
        scan_local_events("workspace-lifecycle-nudge")
    pending = pending_events("test-observer", "pr_merged")
    assert len(pending) == 1
    assert pending[0]["payload"]["pr_number"] == 99


def test_scan_local_events_advances_own_checkpoint(project_dir):
    from unittest.mock import patch, MagicMock

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="[]")
        scan_local_events("workspace-lifecycle-nudge")
        first_pending = pending_events("workspace-lifecycle-nudge", "cron_heartbeat")
        assert first_pending == []


def test_scan_local_events_emits_review_submitted_with_role_derived_from_bot_login(project_dir):
    from unittest.mock import patch, MagicMock

    pr_list_stdout = json.dumps([{"number": 919, "title": "Test PR", "mergedAt": "2026-08-12T00:00:00Z"}])
    reviews_stdout = json.dumps({
        "reviews": [
            {"author": {"login": "synlynk-vdowrx-qa[bot]"}, "state": "COMMENTED", "submittedAt": "2026-08-12T01:00:00Z"},
        ]
    })
    git_log_stdout = ""

    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=pr_list_stdout),
            MagicMock(returncode=0, stdout=reviews_stdout),
            MagicMock(returncode=0, stdout=git_log_stdout),
        ]
        scan_local_events("workspace-lifecycle-nudge")

    pending = pending_events("test-observer", "review_submitted")
    assert len(pending) == 1
    payload = pending[0]["payload"]
    assert payload["pr_number"] == 919
    assert payload["reviewer_login"] == "synlynk-vdowrx-qa[bot]"
    assert payload["reviewer_role"] == "qa"
    assert payload["verdict"] == "COMMENTED"
    assert payload["submitted_at"] == "2026-08-12T01:00:00Z"


def test_scan_local_events_review_submitted_role_null_for_non_matching_login(project_dir):
    from unittest.mock import patch, MagicMock

    pr_list_stdout = json.dumps([{"number": 920, "title": "Test PR 2", "mergedAt": "2026-08-12T00:00:00Z"}])
    reviews_stdout = json.dumps({
        "reviews": [
            {"author": {"login": "some-human"}, "state": "APPROVED", "submittedAt": "2026-08-12T02:00:00Z"},
        ]
    })

    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=pr_list_stdout),
            MagicMock(returncode=0, stdout=reviews_stdout),
            MagicMock(returncode=0, stdout=""),
        ]
        scan_local_events("workspace-lifecycle-nudge")

    pending = pending_events("test-observer", "review_submitted")
    assert len(pending) == 1
    assert pending[0]["payload"]["reviewer_role"] is None


def test_scan_local_events_review_submitted_no_duplicate_on_rescan(project_dir):
    from unittest.mock import patch, MagicMock

    pr_list_stdout = json.dumps([{"number": 921, "title": "Test PR 3", "mergedAt": "2026-08-12T00:00:00Z"}])
    reviews_stdout = json.dumps({
        "reviews": [
            {"author": {"login": "synlynk-vdowrx-dev[bot]"}, "state": "APPROVED", "submittedAt": "2026-08-12T03:00:00Z"},
        ]
    })

    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=pr_list_stdout),
            MagicMock(returncode=0, stdout=reviews_stdout),
            MagicMock(returncode=0, stdout=""),
        ]
        scan_local_events("workspace-lifecycle-nudge")

    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=pr_list_stdout),
            MagicMock(returncode=0, stdout=reviews_stdout),
            MagicMock(returncode=0, stdout=""),
        ]
        scan_local_events("workspace-lifecycle-nudge")

    pending = pending_events("test-observer2", "review_submitted")
    assert len(pending) == 1
