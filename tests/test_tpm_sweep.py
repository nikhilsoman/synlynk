from unittest.mock import MagicMock, patch

import synlynk
from synlynk.db import cmd_story_create, cmd_story_ready
from synlynk.tpm_sweep import _ready_stories
from synlynk.tpm_sweep import run_sweep_pass
from synlynk.tpm_sweep import run_tpm_wake_cycle


def test_cmd_story_create_accepts_marketing_role(isolated_db, project_dir):
    story_id = cmd_story_create(title="marketing story", role="marketing")

    assert story_id


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


def test_run_sweep_pass_selects_ready_story_and_dispatches_it(isolated_db, project_dir):
    cmd_story_create(title="not ready", story_id="story-draft")
    ready_story_id = cmd_story_create(title="ready story", story_id="story-ready")
    cmd_story_ready(ready_story_id)

    with patch("synlynk.tpm_sweep.check_authority") as mock_auth, \
            patch("synlynk.tpm_sweep.dispatch_agent") as mock_dispatch:
        mock_auth.return_value = MagicMock(allowed=True, requires_approval=False)
        mock_dispatch.return_value = {"id": "job-ready", "agent": "codex"}

        summary = run_sweep_pass()

    assert summary == {"advanced": 1, "parked": 0, "failed": 0}
    mock_dispatch.assert_called_once_with(
        "codex",
        "ready story",
        story_id="story-ready",
        task_type="implement",
        context_mode="full",
        role="dev",
    )


def test_run_sweep_pass_routes_marketing_role_to_agy(isolated_db, project_dir):
    story_id = cmd_story_create(title="write blog post", story_id="story-5", role="marketing")
    cmd_story_ready(story_id)
    with patch("synlynk.tpm_sweep.check_authority") as mock_auth, \
            patch("synlynk.tpm_sweep.dispatch_agent") as mock_dispatch:
        mock_auth.return_value = MagicMock(allowed=True, requires_approval=False)
        mock_dispatch.return_value = {"id": "job-5", "agent": "agy"}
        summary = run_sweep_pass()
    assert summary["advanced"] == 1
    mock_dispatch.assert_called_once()
    called_harness = mock_dispatch.call_args[0][0]
    assert called_harness == "agy"


def test_run_sweep_pass_routes_dev_role_to_codex(isolated_db, project_dir):
    story_id = cmd_story_create(title="fix bug", story_id="story-6", role="dev")
    cmd_story_ready(story_id)
    with patch("synlynk.tpm_sweep.check_authority") as mock_auth, \
            patch("synlynk.tpm_sweep.dispatch_agent") as mock_dispatch:
        mock_auth.return_value = MagicMock(allowed=True, requires_approval=False)
        mock_dispatch.return_value = {"id": "job-6", "agent": "codex"}
        summary = run_sweep_pass()
    assert summary["advanced"] == 1
    called_harness = mock_dispatch.call_args[0][0]
    assert called_harness == "codex"


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


def test_run_sweep_pass_dispatches_story_approved_via_release_proposal(isolated_db, project_dir):
    import json
    story_id = cmd_story_create(title="story from release proposal")
    cmd_story_ready(story_id)
    conn = synlynk._get_db()
    conn.execute(
        "INSERT INTO approval_tickets (story_id, action, issue_url, status, constituent_story_ids) "
        "VALUES ('v0.38.1', 'release_proposal', 'https://github.com/example/issues/100', 'resolved', ?)",
        (json.dumps([story_id]),)
    )
    conn.commit()
    conn.close()

    with patch("synlynk.tpm_sweep.check_authority") as mock_auth, \
            patch("synlynk.tpm_sweep.raise_approval_ticket") as mock_ticket, \
            patch("synlynk.tpm_sweep.dispatch_agent") as mock_dispatch:
        mock_auth.return_value = MagicMock(
            allowed=True, requires_approval=True, reason="named_release"
        )
        mock_dispatch.return_value = {"id": "job-prop-1", "agent": "codex"}
        summary = run_sweep_pass()

    assert summary["advanced"] == 1
    assert summary["parked"] == 0
    mock_ticket.assert_not_called()


def test_derive_dynamic_bookends_without_hardcoded_v0322(isolated_db, project_dir):
    from synlynk.tpm_sweep import _derive_dynamic_bookends
    conn = synlynk._get_db()
    conn.execute(
        "INSERT INTO approval_tickets (story_id, action, issue_url, status, theme) "
        "VALUES ('v0.39.0', 'release_proposal', 'https://example/39', 'held', 'Theme 6 Cloud Wedge')"
    )
    conn.commit()

    with patch("subprocess.run") as mock_run:
        def fake_run(cmd, *args, **kwargs):
            m = MagicMock()
            m.returncode = 0
            if "tag" in cmd:
                m.stdout = "v0.38.0\nv0.37.0\nv0.36.0\n"
            elif "log" in cmd:
                m.stdout = "abc1234 Merge pull request #5344 from dispatch/codex\n"
            return m
        mock_run.side_effect = fake_run

        bookends = _derive_dynamic_bookends("v0.38.1", conn, repo_root=str(project_dir))

    conn.close()
    assert "v0.38.0" in bookends["bookend_mtd"]
    assert "0.32.2" not in bookends["bookend_mtd"]
    assert "5344" in bookends["bookend_today"]
    assert "v0.39.0" in bookends["bookend_horizon"]


def test_cluster_candidate_stories_by_thematic_goal():
    from synlynk.tpm_sweep import _cluster_candidate_stories
    stories = [
        {"story_id": "s1", "goal_id": "goal-A", "title": "A1"},
        {"story_id": "s2", "goal_id": "goal-B", "title": "B1"},
        {"story_id": "s3", "goal_id": "goal-A", "title": "A2"},
        {"story_id": "s4", "goal_id": "goal-A", "title": "A3"},
        {"story_id": "s5", "goal_id": "goal-C", "title": "C1"},
        {"story_id": "s6", "goal_id": "goal-B", "title": "B2"},
        {"story_id": "s7", "goal_id": "goal-A", "title": "A4"},
    ]
    clustered = _cluster_candidate_stories(stories, target_count=5)
    assert len(clustered) == 5
    goal_a_stories = [s for s in clustered if s["goal_id"] == "goal-A"]
    # All 4 stories of primary cluster goal-A must be included
    assert len(goal_a_stories) == 4



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


def test_story_done_clears_readiness_and_sweep_does_not_resweep(isolated_db, project_dir):
    from synlynk.db import cmd_story_done

    story_id = cmd_story_create(title="finish me", story_id="story-done-1")
    cmd_story_ready(story_id)

    with patch("synlynk.tpm_sweep.check_authority") as mock_auth, \
            patch("synlynk.tpm_sweep.dispatch_agent") as mock_dispatch:
        mock_auth.return_value = MagicMock(allowed=True, requires_approval=False)
        mock_dispatch.return_value = {"id": "job-done-1", "agent": "codex"}
        run_sweep_pass()

    cmd_story_done(story_id)

    conn = synlynk._get_db()
    row = conn.execute(
        "SELECT status, readiness FROM stories WHERE story_id=?", (story_id,)
    ).fetchone()
    conn.close()
    assert row == ("done", "done")

    assert _ready_stories() == []

    with patch("synlynk.tpm_sweep.check_authority") as mock_auth, \
            patch("synlynk.tpm_sweep.dispatch_agent") as mock_dispatch:
        mock_auth.return_value = MagicMock(allowed=True, requires_approval=False)
        mock_dispatch.return_value = {"id": "job-done-2", "agent": "codex"}
        summary = run_sweep_pass()

    assert summary == {"advanced": 0, "parked": 0, "failed": 0}
    mock_dispatch.assert_not_called()


def _staged_backlog_item(title="raw issue", issue_number=901):
    """Insert one staged backlog_items row and return its integer id."""
    conn = synlynk._get_db()
    cur = conn.execute(
        "INSERT INTO backlog_items (item_id, title, body, issue_number, "
        "fingerprint, role, stage, governs_stage, complexity_tier, status) "
        "VALUES (?, ?, 'body', ?, ?, 'dev', 'open', 'open', 2, 'staged')",
        (f"backlog-issue-{issue_number}", title, issue_number, f"fp-{issue_number}"),
    )
    row_id = cur.lastrowid
    conn.commit()
    conn.close()
    return row_id


def _backlog_status(row_id):
    conn = synlynk._get_db()
    row = conn.execute(
        "SELECT status FROM backlog_items WHERE id=?", (row_id,)
    ).fetchone()
    conn.close()
    return row[0]


def _triaged(row_id, goal_id="goal-d3333441", complexity_tier=2):
    return {
        "id": row_id,
        "item_id": f"backlog-item-{row_id}",
        "title": "raw issue",
        "issue_number": 901,
        "role": "dev",
        "stage": "open",
        "governs_stage": "open",
        "complexity_tier": complexity_tier,
        "goal_id": goal_id,
        "acceptance_criteria": [],
        "fingerprint": f"fp-{row_id}",
        "status": "triaged",
    }


def test_tpm_wake_cycle_routes_routine_item_to_tpm_drafted(isolated_db, project_dir):
    row_id = _staged_backlog_item()

    with patch("synlynk.tpm_sweep.ingest_backlog") as mock_ingest, \
            patch("synlynk.tpm_sweep.triage_backlog") as mock_triage, \
            patch("synlynk.tpm_sweep.run_sweep_pass") as mock_sweep:
        mock_ingest.return_value = {"ingested": 1, "duplicates": 0}
        mock_triage.return_value = [_triaged(row_id)]
        mock_sweep.return_value = {"advanced": 0, "parked": 0, "failed": 0}

        result = run_tpm_wake_cycle()

    assert _backlog_status(row_id) == "tpm_drafted"
    assert result["triaged"] == 1
    assert result["routed"]["tpm_drafted"] == 1
    assert result["routed"]["needs_pm_priority_input"] == 0
    assert result["routed"]["needs_architect_input"] == 0
    assert result["sweep"] == {"advanced": 0, "parked": 0, "failed": 0}
    mock_ingest.assert_called_once()
    mock_sweep.assert_called_once()


def test_tpm_wake_cycle_routes_tier3_item_to_needs_pm_priority_input(isolated_db, project_dir):
    row_id = _staged_backlog_item(title="big ambiguous epic", issue_number=902)

    with patch("synlynk.tpm_sweep.ingest_backlog") as mock_ingest, \
            patch("synlynk.tpm_sweep.triage_backlog") as mock_triage, \
            patch("synlynk.tpm_sweep.run_sweep_pass") as mock_sweep:
        mock_ingest.return_value = {"ingested": 1, "duplicates": 0}
        mock_triage.return_value = [_triaged(row_id, complexity_tier=3)]
        mock_sweep.return_value = {"advanced": 0, "parked": 0, "failed": 0}

        result = run_tpm_wake_cycle()

    assert _backlog_status(row_id) == "needs_pm_priority_input"
    assert result["routed"]["needs_pm_priority_input"] == 1
    assert result["routed"]["tpm_drafted"] == 0


def test_tpm_wake_cycle_routes_missing_goal_to_needs_architect_input(isolated_db, project_dir):
    row_id = _staged_backlog_item(title="unmoored request", issue_number=903)

    with patch("synlynk.tpm_sweep.ingest_backlog") as mock_ingest, \
            patch("synlynk.tpm_sweep.triage_backlog") as mock_triage, \
            patch("synlynk.tpm_sweep.run_sweep_pass") as mock_sweep:
        mock_ingest.return_value = {"ingested": 1, "duplicates": 0}
        mock_triage.return_value = [_triaged(row_id, goal_id="")]
        mock_sweep.return_value = {"advanced": 0, "parked": 0, "failed": 0}

        result = run_tpm_wake_cycle()

    assert _backlog_status(row_id) == "needs_architect_input"
    assert result["routed"]["needs_architect_input"] == 1
    assert result["routed"]["tpm_drafted"] == 0


def test_package_next_release_proposal_derives_version_from_active_arc(tmp_path):
    from synlynk.db import _get_db
    from synlynk.tpm_sweep import package_next_release_proposal

    # Create dummy VERSION file with an older version 0.38.3
    vfile = tmp_path / "VERSION"
    vfile.write_text("0.38.3\n", encoding="utf-8")

    conn = _get_db()
    try:
        # Create goals and active arc v0.39.2
        conn.execute(
            "INSERT INTO goals (goal_id, outcome, criterion, status, arc_version, placement_status) "
            "VALUES ('goal-test-regen', 'Harness capability routing regen', 'criterion', 'active', 'v0.39.2', 'placed')"
        )
        conn.execute(
            "INSERT INTO stories (story_id, title, role, goal_id, status, readiness) "
            "VALUES ('story-test-1', 'Regen CLI command', 'dev', 'goal-test-regen', 'open', 'ready')"
        )
        conn.commit()

        proposal = package_next_release_proposal(conn=conn, repo_root=str(tmp_path))
        assert proposal is not None
        # Must resolve to v0.39.2 from the canonical arc/goal, NOT v0.38.4 from VERSION file!
        assert proposal["release_version"] == "v0.39.2"
        assert proposal["target_goal_id"] == "goal-test-regen"
    finally:
        conn.close()

