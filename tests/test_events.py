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


def test_emit_awaiting_approval_event_recorded(project_dir):
    from synlynk.events import emit_awaiting_approval
    from synlynk import _get_db

    event_id = emit_awaiting_approval(
        story_id="story-1", action="release_cut", reason="named_release", emitted_by="tpm_sweep",
    )
    assert event_id is not None
    conn = _get_db()
    row = conn.execute(
        "SELECT event_type, payload_json FROM events WHERE id=?", (event_id,)
    ).fetchone()
    conn.close()
    assert row[0] == "awaiting_approval"
    assert '"story-1"' in row[1]
    assert '"release_cut"' in row[1]
    assert '"named_release"' in row[1]


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


def test_cmd_events_tail_filters_by_type(project_dir, capsys):
    from synlynk.events import cmd_events_tail

    emit_event("pr_merged", {"pr_number": 1}, emitted_by="test")
    emit_event("job_terminal", {"job_id": "job-a", "status": "done"}, emitted_by="test")
    emit_event("job_terminal", {"job_id": "job-b", "status": "failed"}, emitted_by="test")

    cmd_events_tail(event_type="job_terminal", limit=20)

    out = capsys.readouterr().out
    assert "job-a" in out
    assert "job-b" in out
    assert "pr_merged" not in out


def test_cmd_events_tail_respects_limit_and_orders_newest_first(project_dir, capsys):
    from synlynk.events import cmd_events_tail

    for i in range(5):
        emit_event("cron_heartbeat", {"tick": i}, emitted_by="test")

    cmd_events_tail(event_type="cron_heartbeat", limit=2)

    out = capsys.readouterr().out
    lines = [l for l in out.splitlines() if l.strip()]
    assert len(lines) == 2
    # Newest first: tick 4 appears before tick 3.
    assert out.index('"tick": 4') < out.index('"tick": 3')


def test_cmd_events_tail_with_no_type_shows_all_types(project_dir, capsys):
    from synlynk.events import cmd_events_tail

    emit_event("pr_merged", {"pr_number": 1}, emitted_by="test")
    emit_event("job_terminal", {"job_id": "job-a", "status": "done"}, emitted_by="test")

    cmd_events_tail(event_type=None, limit=20)

    out = capsys.readouterr().out
    assert "pr_merged" in out
    assert "job_terminal" in out


def test_scan_local_events_emits_spec_verified_when_pr_references_spec(project_dir, tmp_path, monkeypatch):
    from unittest.mock import patch, MagicMock

    spec_dir = tmp_path / "docs" / "superpowers" / "specs"
    spec_dir.mkdir(parents=True)
    (spec_dir / "2026-08-20-example-design.md").write_text("# Example\n\nDo the thing")
    monkeypatch.chdir(tmp_path)

    pr_list_stdout = json.dumps([{
        "number": 501, "title": "Test PR", "mergedAt": "2026-08-22T00:00:00Z",
        "body": "Implements docs/superpowers/specs/2026-08-20-example-design.md",
    }])
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=pr_list_stdout),
            MagicMock(returncode=0, stdout=json.dumps({"reviews": []})),
            MagicMock(returncode=0, stdout="diff --git a/x b/x\n+the thing"),
            MagicMock(returncode=0, stdout=json.dumps({"verdict": "fulfilled", "rationale": "Matches spec"})),
            MagicMock(returncode=0, stdout=""),
        ]
        scan_local_events("workspace-lifecycle-nudge")

    pending = pending_events("test-observer", "spec_verified")
    assert len(pending) == 1
    payload = pending[0]["payload"]
    assert payload["pr_number"] == 501
    assert payload["spec_path"] == "docs/superpowers/specs/2026-08-20-example-design.md"
    assert payload["verdict"] == "fulfilled"
    assert payload["rationale"] == "Matches spec"
    assert payload["reviewer_role"] == "qa"


def test_scan_local_events_skips_spec_verified_when_pr_body_has_no_reference(project_dir):
    from unittest.mock import patch, MagicMock

    pr_list_stdout = json.dumps([{
        "number": 502, "title": "Small typo fix", "mergedAt": "2026-08-22T00:00:00Z",
        "body": "Fixes a typo, no ticket.",
    }])
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=pr_list_stdout),
            MagicMock(returncode=0, stdout=json.dumps({"reviews": []})),
            MagicMock(returncode=0, stdout=""),
        ]
        scan_local_events("workspace-lifecycle-nudge")

    assert pending_events("test-observer", "spec_verified") == []


def test_scan_local_events_no_duplicate_spec_verified_on_rescan(project_dir, tmp_path, monkeypatch):
    from unittest.mock import patch, MagicMock

    spec_dir = tmp_path / "docs" / "superpowers" / "specs"
    spec_dir.mkdir(parents=True)
    (spec_dir / "x.md").write_text("spec")
    monkeypatch.chdir(tmp_path)

    pr_list_stdout = json.dumps([{
        "number": 503, "title": "Test PR", "mergedAt": "2026-08-22T00:00:00Z",
        "body": "Implements docs/superpowers/specs/x.md",
    }])

    def run_side_effect():
        return [
            MagicMock(returncode=0, stdout=pr_list_stdout),
            MagicMock(returncode=0, stdout=json.dumps({"reviews": []})),
            MagicMock(returncode=0, stdout="diff"),
            MagicMock(returncode=0, stdout=json.dumps({"verdict": "fulfilled", "rationale": "ok"})),
            MagicMock(returncode=0, stdout=""),
        ]

    with patch("subprocess.run", side_effect=run_side_effect()):
        scan_local_events("workspace-lifecycle-nudge")
    assert len(pending_events("test-observer", "spec_verified")) == 1

    # Second scan: only the gh pr list / reviews / git log calls happen --
    # no diff/claude calls, since 503 already has a spec_verified event.
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=pr_list_stdout),
            MagicMock(returncode=0, stdout=json.dumps({"reviews": []})),
            MagicMock(returncode=0, stdout=""),
        ]
        scan_local_events("workspace-lifecycle-nudge")
        assert mock_run.call_count == 3

    assert len(pending_events("test-observer", "spec_verified")) == 1


def test_scan_local_events_skips_spec_verified_when_verdict_uncomputable(project_dir):
    from unittest.mock import patch, MagicMock

    pr_list_stdout = json.dumps([{
        "number": 504, "title": "Test PR", "mergedAt": "2026-08-22T00:00:00Z",
        "body": "Implements docs/superpowers/specs/does-not-exist.md",
    }])
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=pr_list_stdout),
            MagicMock(returncode=0, stdout=json.dumps({"reviews": []})),
            MagicMock(returncode=0, stdout=""),
        ]
        scan_local_events("workspace-lifecycle-nudge")

    assert pending_events("test-observer", "spec_verified") == []
