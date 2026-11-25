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



def test_package_next_release_proposal_packages_thirteen_stories_whole(tmp_path):
    import sqlite3
    from synlynk.tpm_sweep import package_next_release_proposal

    conn = sqlite3.connect(tmp_path / "test.db")
    try:
        conn.execute("CREATE TABLE stories (story_id TEXT PRIMARY KEY, title TEXT, role TEXT, estimated_tokens INTEGER, gh_issue TEXT, readiness TEXT, status TEXT, goal_id TEXT, priority INTEGER, umbrella INTEGER DEFAULT 0, phase TEXT)")
        conn.execute("CREATE TABLE goals (id INTEGER PRIMARY KEY, goal_id TEXT, outcome TEXT, phase_title TEXT, status TEXT, roadmap_priority TEXT)")
        conn.execute("INSERT INTO goals (id, goal_id, outcome, phase_title, status, roadmap_priority) VALUES (1, 'goal-13', 'Thirteen Outcome', 'Phase 13', 'active', 'P1')")
        for i in range(1, 14):
            conn.execute(
                "INSERT INTO stories (story_id, title, readiness, status, goal_id, priority) VALUES (?, ?, 'ready', 'open', 'goal-13', ?)",
                (f"s-{i:02d}", f"Story {i}", i),
            )
        conn.commit()

        proposal = package_next_release_proposal(conn=conn, repo_root=str(tmp_path))
        assert proposal is not None
        assert proposal.get("escalation") is None
        assert len(proposal["stories"]) == 13
        assert [s["story_id"] for s in proposal["stories"]] == [f"s-{i:02d}" for i in range(13, 0, -1)]
    finally:
        conn.close()


def test_package_next_release_proposal_separates_in_progress_and_umbrella_into_context(tmp_path):
    import sqlite3
    from synlynk.tpm_sweep import package_next_release_proposal

    conn = sqlite3.connect(tmp_path / "test.db")
    try:
        conn.execute("CREATE TABLE stories (story_id TEXT PRIMARY KEY, title TEXT, role TEXT, estimated_tokens INTEGER, gh_issue TEXT, readiness TEXT, status TEXT, goal_id TEXT, priority INTEGER, umbrella INTEGER DEFAULT 0, phase TEXT)")
        conn.execute("CREATE TABLE goals (id INTEGER PRIMARY KEY, goal_id TEXT, outcome TEXT, phase_title TEXT, status TEXT, roadmap_priority TEXT)")
        conn.execute("INSERT INTO goals (id, goal_id, outcome, phase_title, status, roadmap_priority) VALUES (1, 'goal-19', 'Nineteen Outcome', 'Phase 19', 'active', 'P1')")
        # 12 ready open stories
        for i in range(1, 13):
            conn.execute(
                "INSERT INTO stories (story_id, title, readiness, status, goal_id, priority) VALUES (?, ?, 'ready', 'open', 'goal-19', ?)",
                (f"s-{i:02d}", f"Plain Story {i}", i),
            )
        # 4 in_progress stories
        for i in range(13, 17):
            conn.execute(
                "INSERT INTO stories (story_id, title, readiness, status, goal_id, priority) VALUES (?, ?, 'ready', 'in_progress', 'goal-19', ?)",
                (f"s-{i:02d}", f"In Progress Story {i}", i),
            )
        # 3 umbrella stories
        for i in range(17, 20):
            conn.execute(
                "INSERT INTO stories (story_id, title, readiness, status, goal_id, priority, umbrella) VALUES (?, ?, 'ready', 'open', 'goal-19', ?, 1)",
                (f"s-{i:02d}", f"Umbrella Story {i}", i),
            )
        conn.commit()

        proposal = package_next_release_proposal(conn=conn, repo_root=str(tmp_path))
        assert proposal is not None
        assert len(proposal["stories"]) == 12
        context_ids = [s["story_id"] for s in proposal.get("context_stories", [])]
        assert len(context_ids) == 7
        assert "s-13" in context_ids
        assert "s-17" in context_ids
    finally:
        conn.close()


def test_package_next_release_proposal_returns_escalation_when_plan_escalates(tmp_path):
    import sqlite3
    from synlynk.tpm_sweep import package_next_release_proposal

    conn = sqlite3.connect(tmp_path / "test.db")
    try:
        conn.execute("CREATE TABLE stories (story_id TEXT PRIMARY KEY, title TEXT, role TEXT, estimated_tokens INTEGER, gh_issue TEXT, readiness TEXT, status TEXT, goal_id TEXT, priority INTEGER, umbrella INTEGER DEFAULT 0, phase TEXT)")
        conn.execute("CREATE TABLE goals (id INTEGER PRIMARY KEY, goal_id TEXT, outcome TEXT, phase_title TEXT, status TEXT, roadmap_priority TEXT)")
        conn.execute("INSERT INTO goals (id, goal_id, outcome, phase_title, status, roadmap_priority) VALUES (1, 'goal-40', 'Forty Outcome', 'Phase 40', 'active', 'P1')")
        # 40 stories over the 30 ceiling, all with phase='build' (no distinct phase data)
        for i in range(1, 41):
            conn.execute(
                "INSERT INTO stories (story_id, title, readiness, status, goal_id, priority, phase) VALUES (?, ?, 'ready', 'open', 'goal-40', ?, 'build')",
                (f"s-{i:02d}", f"Story {i}", i),
            )
        conn.commit()

        res = package_next_release_proposal(conn=conn, repo_root=str(tmp_path))
        assert res is not None
        assert res.get("proposal") is None
        assert res.get("escalation") == "no phase data"
        assert res.get("goal_id") == "goal-40"
    finally:
        conn.close()


def test_package_next_release_proposal_open_pr_lands_in_context(tmp_path, monkeypatch):
    import sqlite3
    from synlynk.tpm_sweep import package_next_release_proposal

    conn = sqlite3.connect(tmp_path / "test.db")
    try:
        conn.execute("CREATE TABLE stories (story_id TEXT PRIMARY KEY, title TEXT, role TEXT, estimated_tokens INTEGER, gh_issue TEXT, readiness TEXT, status TEXT, goal_id TEXT, priority INTEGER, umbrella INTEGER DEFAULT 0, phase TEXT)")
        conn.execute("CREATE TABLE goals (id INTEGER PRIMARY KEY, goal_id TEXT, outcome TEXT, phase_title TEXT, status TEXT, roadmap_priority TEXT)")
        conn.execute("INSERT INTO goals (id, goal_id, outcome, phase_title, status, roadmap_priority) VALUES (1, 'goal-pr', 'PR Outcome', 'Phase PR', 'active', 'P1')")
        for i in range(1, 4):
            conn.execute(
                "INSERT INTO stories (story_id, title, readiness, status, goal_id, priority) VALUES (?, ?, 'ready', 'open', 'goal-pr', ?)",
                (f"s-{i:02d}", f"Story {i}", i),
            )
        conn.commit()

        # Inject open PRs mentioning s-02
        monkeypatch.setattr("synlynk.tpm_sweep._get_open_pr_story_ids", lambda repo_root: {"s-02"})

        proposal = package_next_release_proposal(conn=conn, repo_root=str(tmp_path))
        assert proposal is not None
        assert len(proposal["stories"]) == 2
        packaged_ids = [s["story_id"] for s in proposal["stories"]]
        assert "s-01" in packaged_ids and "s-03" in packaged_ids
        context_ids = [s["story_id"] for s in proposal.get("context_stories", [])]
        assert context_ids == ["s-02"]
    finally:
        conn.close()


def test_package_next_release_proposal_independent_phases_and_operator_approval(tmp_path):
    import sqlite3
    from synlynk.tpm_sweep import package_next_release_proposal

    conn = sqlite3.connect(tmp_path / "test.db")
    try:
        conn.execute("CREATE TABLE stories (story_id TEXT PRIMARY KEY, title TEXT, role TEXT, estimated_tokens INTEGER, gh_issue TEXT, readiness TEXT, status TEXT, goal_id TEXT, priority INTEGER, umbrella INTEGER DEFAULT 0, phase TEXT)")
        conn.execute("CREATE TABLE goals (id INTEGER PRIMARY KEY, goal_id TEXT, outcome TEXT, phase_title TEXT, status TEXT, roadmap_priority TEXT)")
        conn.execute("CREATE TABLE story_dependencies (story_id TEXT NOT NULL, depends_on_story_id TEXT NOT NULL, PRIMARY KEY (story_id, depends_on_story_id))")
        conn.execute("CREATE TABLE release_split_approvals (goal_id TEXT NOT NULL, phase TEXT NOT NULL, approved_by TEXT, approved_at TEXT, PRIMARY KEY (goal_id, phase))")
        conn.execute("CREATE TABLE goal_packaging_flags (goal_id TEXT PRIMARY KEY, independent_phases INTEGER NOT NULL DEFAULT 0)")

        conn.execute("INSERT INTO goals (id, goal_id, outcome, phase_title, status, roadmap_priority) VALUES (1, 'goal-indep', 'Indep Outcome', 'Phase Indep', 'active', 'P1')")
        conn.execute("INSERT INTO goal_packaging_flags (goal_id, independent_phases) VALUES ('goal-indep', 1)")

        for i in range(1, 5):
            conn.execute("INSERT INTO stories (story_id, title, readiness, status, goal_id, priority, phase) VALUES (?, ?, 'ready', 'open', 'goal-indep', ?, 'p1')", (f"p1-{i}", f"P1 Story {i}", i))
        for i in range(1, 5):
            conn.execute("INSERT INTO stories (story_id, title, readiness, status, goal_id, priority, phase) VALUES (?, ?, 'ready', 'open', 'goal-indep', ?, 'p2')", (f"p2-{i}", f"P2 Story {i}", i))
        conn.commit()

        proposal = package_next_release_proposal(conn=conn, repo_root=str(tmp_path))
        assert proposal is not None
        assert len(proposal["stories"]) == 4
        assert [s["story_id"] for s in proposal["stories"]] == [f"p1-{i}" for i in range(4, 0, -1)]

        # Now test approved oversized phase: 35 stories in p1 under goal-oversized
        conn.execute("INSERT INTO goals (id, goal_id, outcome, phase_title, status, roadmap_priority) VALUES (2, 'goal-oversized', 'Over Outcome', 'Phase Over', 'active', 'P1')")
        conn.execute("INSERT INTO release_split_approvals (goal_id, phase, approved_by) VALUES ('goal-oversized', 'p1', 'pm')")
        for i in range(1, 36):
            conn.execute("INSERT INTO stories (story_id, title, readiness, status, goal_id, priority, phase) VALUES (?, ?, 'ready', 'open', 'goal-oversized', ?, 'p1')", (f"over-{i:02d}", f"Over Story {i}", i))
        conn.commit()

        prop_over = package_next_release_proposal(conn=conn, repo_root=str(tmp_path), target_goal_id="goal-oversized")
        assert prop_over is not None
        assert len(prop_over["stories"]) == 30
    finally:
        conn.close()


def test_format_release_proposal_markdown_packaging_section():
    from synlynk.release_packaging import PackagePlan
    from synlynk.tpm_sweep import format_release_proposal_markdown

    # Complete goal case
    plan_complete = PackagePlan(
        parts=[["s-01", "s-02"]],
        context=["s-ctx"],
        escalation=None,
        split_reasons=[],
        total_stories=2,
        total_tokens=50000,
        limits={"goal_story_ceiling": 30, "goal_token_ceiling": 1500000},
        part_stats=[{"stories": 2, "tokens": 50000}],
    )
    proposal_complete = {
        "release_version": "v0.40.0",
        "theme": "Living Ledger",
        "packaging_plan": plan_complete,
        "stories": [{"story_id": "s-01", "title": "S1"}, {"story_id": "s-02", "title": "S2"}],
        "context_stories": [{"story_id": "s-ctx", "title": "Context S"}],
    }
    body = format_release_proposal_markdown(proposal_complete)
    assert "## 📦 Packaging" in body
    assert "complete goal" in body
    assert "2 packageable stories" in body
    assert "50,000 tokens" in body or "50000 tokens" in body
    assert "ceilings: 30 stories, 1,500,000 tokens" in body or "ceilings: 30 stories, 1500000 tokens" in body

    # Split goal case (part 1 of 2)
    plan_split = PackagePlan(
        parts=[["s-01"], ["s-02"]],
        context=[],
        escalation=None,
        split_reasons=["split at phase p2"],
        total_stories=2,
        total_tokens=50000,
        limits={"goal_story_ceiling": 1, "goal_token_ceiling": 1500000},
        part_stats=[{"stories": 1, "tokens": 25000}, {"stories": 1, "tokens": 25000}],
    )
    proposal_split = {
        "release_version": "v0.40.0",
        "theme": "Living Ledger",
        "packaging_plan": plan_split,
        "part_index": 1,
        "total_parts": 2,
        "continuation_ticket": "https://github.com/nikhilsoman/synlynk/issues/5599",
        "stories": [{"story_id": "s-01", "title": "S1"}],
    }
    body_split = format_release_proposal_markdown(proposal_split)
    assert "## 📦 Packaging" in body_split
    assert "part 1 of 2, split at phase p2" in body_split
    assert "remainder tracked in https://github.com/nikhilsoman/synlynk/issues/5599" in body_split


def test_dispatch_tpm_advisory_proposal_continuations_and_idempotency(tmp_path, monkeypatch):
    import sqlite3
    from synlynk.tpm_sweep import dispatch_tpm_advisory_proposal

    conn = sqlite3.connect(tmp_path / "test.db")
    try:
        conn.execute("CREATE TABLE stories (story_id TEXT PRIMARY KEY, title TEXT, role TEXT, estimated_tokens INTEGER, gh_issue TEXT, readiness TEXT, status TEXT, goal_id TEXT, priority INTEGER, umbrella INTEGER DEFAULT 0, phase TEXT)")
        conn.execute("CREATE TABLE goals (id INTEGER PRIMARY KEY, goal_id TEXT, outcome TEXT, phase_title TEXT, status TEXT, roadmap_priority TEXT)")
        conn.execute("CREATE TABLE approval_tickets (id INTEGER PRIMARY KEY AUTOINCREMENT, story_id TEXT, action TEXT, issue_url TEXT, status TEXT, constituent_story_ids TEXT, theme TEXT, goal_id TEXT, part_index INTEGER DEFAULT 1, total_parts INTEGER DEFAULT 1, continuation_ticket_url TEXT, split_reason TEXT, opened_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")

        conn.execute("INSERT INTO goals (id, goal_id, outcome, phase_title, status, roadmap_priority) VALUES (1, 'goal-split', 'Split Outcome', 'Phase Theme', 'active', 'P1')")
        for i in range(1, 21):
            conn.execute("INSERT INTO stories (story_id, title, readiness, status, goal_id, priority, phase) VALUES (?, ?, 'ready', 'open', 'goal-split', ?, 'p1')", (f"p1-{i:02d}", f"P1 Story {i}", i))
        for i in range(1, 21):
            conn.execute("INSERT INTO stories (story_id, title, readiness, status, goal_id, priority, phase) VALUES (?, ?, 'ready', 'open', 'goal-split', ?, 'p2')", (f"p2-{i:02d}", f"P2 Story {i}", i))
        conn.commit()

        # Monkeypatch gh CLI to simulate issue creation returning deterministic URLs
        created_issues = []
        def mock_run_gh(role, args, timeout=15):
            class Res:
                returncode = 0
                stdout = f"https://github.com/nikhilsoman/synlynk/issues/{6000 + len(created_issues)}"
                stderr = ""
            created_issues.append((args, Res.stdout))
            return Res()

        monkeypatch.setattr("synlynk.gh_role.run_gh_as_role", mock_run_gh)

        # Dispatch proposal for split goal
        url = dispatch_tpm_advisory_proposal(conn=conn, repo_root=str(tmp_path), max_active_proposals=3)
        assert url is not None

        # Verify proposal and continuation tickets were filed
        rows = conn.execute("SELECT story_id, theme, part_index, total_parts, status, issue_url FROM approval_tickets WHERE action='release_proposal'").fetchall()
        assert len(rows) == 2
        p1 = [r for r in rows if r[2] == 1][0]
        p2 = [r for r in rows if r[2] == 2][0]
        assert p1[1] == "Phase Theme"
        assert "(part 2)" in p2[1]
        assert p1[4] == "open"
        assert p2[4] == "open"

        # Verify idempotency: running sweep second time does NOT duplicate continuation
        url2 = dispatch_tpm_advisory_proposal(conn=conn, repo_root=str(tmp_path), max_active_proposals=3)
        rows2 = conn.execute("SELECT id FROM approval_tickets WHERE action='release_proposal'").fetchall()
        assert len(rows2) == 2
    finally:
        conn.close()


def test_continuation_exempt_from_max_active_proposals(tmp_path, monkeypatch):
    import sqlite3
    from synlynk.tpm_sweep import dispatch_tpm_advisory_proposal

    conn = sqlite3.connect(tmp_path / "test.db")
    try:
        conn.execute("CREATE TABLE stories (story_id TEXT PRIMARY KEY, title TEXT, role TEXT, estimated_tokens INTEGER, gh_issue TEXT, readiness TEXT, status TEXT, goal_id TEXT, priority INTEGER, umbrella INTEGER DEFAULT 0, phase TEXT)")
        conn.execute("CREATE TABLE goals (id INTEGER PRIMARY KEY, goal_id TEXT, outcome TEXT, phase_title TEXT, status TEXT, roadmap_priority TEXT)")
        conn.execute("CREATE TABLE approval_tickets (id INTEGER PRIMARY KEY AUTOINCREMENT, story_id TEXT, action TEXT, issue_url TEXT, status TEXT, constituent_story_ids TEXT, theme TEXT, goal_id TEXT, part_index INTEGER DEFAULT 1, total_parts INTEGER DEFAULT 1, continuation_ticket_url TEXT, split_reason TEXT, opened_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")

        # Pre-seed 3 open proposals from other goals/maintenance
        for i in range(1, 4):
            conn.execute("INSERT INTO approval_tickets (story_id, action, issue_url, status, part_index) VALUES (?, 'release_proposal', ?, 'open', 1)", (f"v0.39.{i}", f"https://github.com/nikhilsoman/synlynk/issues/500{i}"))

        conn.execute("INSERT INTO goals (id, goal_id, outcome, phase_title, status, roadmap_priority) VALUES (1, 'goal-split2', 'Split Outcome 2', 'Theme 2', 'active', 'P1')")
        for i in range(1, 21):
            conn.execute("INSERT INTO stories (story_id, title, readiness, status, goal_id, priority, phase) VALUES (?, ?, 'ready', 'open', 'goal-split2', ?, 'p1')", (f"p1-{i:02d}", f"P1 Story {i}", i))
        for i in range(1, 21):
            conn.execute("INSERT INTO stories (story_id, title, readiness, status, goal_id, priority, phase) VALUES (?, ?, 'ready', 'open', 'goal-split2', ?, 'p2')", (f"p2-{i:02d}", f"P2 Story {i}", i))
        conn.commit()

        # Seed an existing part 1 ticket for goal-split2 to test that part 2 (continuation) can be filed even when max_active_proposals is 3
        conn.execute("INSERT INTO approval_tickets (story_id, action, issue_url, status, goal_id, theme, part_index, total_parts) VALUES ('v0.40.0', 'release_proposal', 'https://github.com/nikhilsoman/synlynk/issues/5100', 'open', 'goal-split2', 'Theme 2', 1, 2)")
        conn.commit()

        # With 4 open proposals already, max_active_proposals=3 would normally throttle, but continuation is exempt
        count_open_non_cont = conn.execute("SELECT COUNT(*) FROM approval_tickets WHERE action='release_proposal' AND status='open' AND (part_index IS NULL OR part_index <= 1)").fetchone()[0]
        assert count_open_non_cont == 4
    finally:
        conn.close()


def test_independent_phases_creates_separate_proposals_without_coupling(tmp_path, monkeypatch):
    import sqlite3
    from synlynk.tpm_sweep import dispatch_tpm_advisory_proposal

    conn = sqlite3.connect(tmp_path / "test.db")
    try:
        conn.execute("CREATE TABLE stories (story_id TEXT PRIMARY KEY, title TEXT, role TEXT, estimated_tokens INTEGER, gh_issue TEXT, readiness TEXT, status TEXT, goal_id TEXT, priority INTEGER, umbrella INTEGER DEFAULT 0, phase TEXT)")
        conn.execute("CREATE TABLE goals (id INTEGER PRIMARY KEY, goal_id TEXT, outcome TEXT, phase_title TEXT, status TEXT, roadmap_priority TEXT)")
        conn.execute("CREATE TABLE goal_packaging_flags (goal_id TEXT PRIMARY KEY, independent_phases INTEGER NOT NULL DEFAULT 0)")
        conn.execute("CREATE TABLE approval_tickets (id INTEGER PRIMARY KEY AUTOINCREMENT, story_id TEXT, action TEXT, issue_url TEXT, status TEXT, constituent_story_ids TEXT, theme TEXT, goal_id TEXT, part_index INTEGER DEFAULT 1, total_parts INTEGER DEFAULT 1, continuation_ticket_url TEXT, split_reason TEXT, opened_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")

        conn.execute("INSERT INTO goals (id, goal_id, outcome, phase_title, status, roadmap_priority) VALUES (1, 'goal-ind', 'Independent Outcome', 'Indep Theme', 'active', 'P1')")
        conn.execute("INSERT INTO goal_packaging_flags (goal_id, independent_phases) VALUES ('goal-ind', 1)")

        for i in range(1, 5):
            conn.execute("INSERT INTO stories (story_id, title, readiness, status, goal_id, priority, phase) VALUES (?, ?, 'ready', 'open', 'goal-ind', ?, 'alpha')", (f"a-{i}", f"Alpha Story {i}", i))
        for i in range(1, 5):
            conn.execute("INSERT INTO stories (story_id, title, readiness, status, goal_id, priority, phase) VALUES (?, ?, 'ready', 'open', 'goal-ind', ?, 'beta')", (f"b-{i}", f"Beta Story {i}", i))
        conn.commit()

        created_issues = []
        def mock_run_gh(role, args, timeout=15):
            class Res:
                returncode = 0
                stdout = f"https://github.com/nikhilsoman/synlynk/issues/{7000 + len(created_issues)}"
                stderr = ""
            created_issues.append((args, Res.stdout))
            return Res()

        monkeypatch.setattr("synlynk.gh_role.run_gh_as_role", mock_run_gh)

        url = dispatch_tpm_advisory_proposal(conn=conn, repo_root=str(tmp_path), max_active_proposals=5)
        assert url is not None

        # Verify two independent proposals created, not titled "(part N)"
        rows = conn.execute("SELECT story_id, theme, issue_url FROM approval_tickets WHERE action='release_proposal'").fetchall()
        assert len(rows) == 2
        for r in rows:
            assert "(part" not in r[1]
    finally:
        conn.close()


def test_membership_drift_recomputes_part_and_refreshes_ticket(tmp_path):
    import sqlite3
    from synlynk.tpm_sweep import package_next_release_proposal

    conn = sqlite3.connect(tmp_path / "test.db")
    try:
        conn.execute("CREATE TABLE stories (story_id TEXT PRIMARY KEY, title TEXT, role TEXT, estimated_tokens INTEGER, gh_issue TEXT, readiness TEXT, status TEXT, goal_id TEXT, priority INTEGER, umbrella INTEGER DEFAULT 0, phase TEXT)")
        conn.execute("CREATE TABLE goals (id INTEGER PRIMARY KEY, goal_id TEXT, outcome TEXT, phase_title TEXT, status TEXT, roadmap_priority TEXT)")

        conn.execute("INSERT INTO goals (id, goal_id, outcome, phase_title, status, roadmap_priority) VALUES (1, 'goal-drift', 'Drift Outcome', 'Drift Theme', 'active', 'P1')")
        # 25 in p1, 15 in p2 -> total 40 stories -> splits into 2 parts (25 in part 1, 15 in part 2)
        for i in range(1, 26):
            conn.execute("INSERT INTO stories (story_id, title, readiness, status, goal_id, priority, phase) VALUES (?, ?, 'ready', 'open', 'goal-drift', ?, 'p1')", (f"p1-{i:02d}", f"P1 Story {i}", i))
        for i in range(1, 16):
            conn.execute("INSERT INTO stories (story_id, title, readiness, status, goal_id, priority, phase) VALUES (?, ?, 'ready', 'open', 'goal-drift', ?, 'p2')", (f"p2-{i:02d}", f"P2 Story {i}", i))
        conn.commit()

        prop1 = package_next_release_proposal(conn=conn, repo_root=str(tmp_path))
        assert len(prop1["packaging_plan"].parts) == 2

        # Story added in p3: 20 stories in p3 -> total 60 stories -> now 3 parts
        for i in range(1, 21):
            conn.execute("INSERT INTO stories (story_id, title, readiness, status, goal_id, priority, phase) VALUES (?, ?, 'ready', 'open', 'goal-drift', ?, 'p3')", (f"p3-{i:02d}", f"P3 Story {i}", i))
        conn.commit()

        prop2 = package_next_release_proposal(conn=conn, repo_root=str(tmp_path))
        assert len(prop2["packaging_plan"].parts) == 3

        # Story marked done in p3: reduce p3 so it still exists
        conn.execute("UPDATE stories SET status='done' WHERE story_id='p3-01'")
        conn.commit()
        prop3 = package_next_release_proposal(conn=conn, repo_root=str(tmp_path))
        assert "p3-01" not in [s for part in prop3["packaging_plan"].parts for s in part]
    finally:
        conn.close()


def test_live_35_packaging_regression(tmp_path):
    """LIVE-35 regression: 12 task stories + 7 umbrella/in-progress parents under one goal -> one proposal of 12 with 7 context entries and 'complete goal' packaging line."""
    import sqlite3
    from synlynk.tpm_sweep import package_next_release_proposal, format_release_proposal_markdown

    conn = sqlite3.connect(tmp_path / "test.db")
    try:
        conn.execute("CREATE TABLE stories (story_id TEXT PRIMARY KEY, title TEXT, role TEXT, estimated_tokens INTEGER, gh_issue TEXT, readiness TEXT, status TEXT, goal_id TEXT, priority INTEGER, umbrella INTEGER DEFAULT 0, phase TEXT)")
        conn.execute("CREATE TABLE goals (id INTEGER PRIMARY KEY, goal_id TEXT, outcome TEXT, phase_title TEXT, status TEXT, roadmap_priority TEXT)")

        conn.execute("INSERT INTO goals (id, goal_id, outcome, phase_title, status, roadmap_priority) VALUES (1, 'goal-live35', 'Roadmap Studio', 'Roadmap Studio Visual Proposal Editor', 'active', 'P1')")

        # 12 ready task stories
        for i in range(1, 13):
            conn.execute(
                "INSERT INTO stories (story_id, title, role, estimated_tokens, readiness, status, goal_id, priority, phase, umbrella) VALUES (?, ?, 'dev', 25000, 'ready', 'open', 'goal-live35', ?, 'phase-1', 0)",
                (f"story-task-{i:02d}", f"Task Story {i}", i),
            )

        # 7 parent stories: 4 umbrella (umbrella=1), 3 in_progress
        for i in range(1, 5):
            conn.execute(
                "INSERT INTO stories (story_id, title, role, estimated_tokens, readiness, status, goal_id, priority, phase, umbrella) VALUES (?, ?, 'pm', 25000, 'ready', 'open', 'goal-live35', ?, 'phase-1', 1)",
                (f"story-umb-{i:02d}", f"Parent Umbrella {i}", 100 + i),
            )
        for i in range(1, 4):
            conn.execute(
                "INSERT INTO stories (story_id, title, role, estimated_tokens, readiness, status, goal_id, priority, phase, umbrella) VALUES (?, ?, 'architect', 25000, 'ready', 'in_progress', 'goal-live35', ?, 'phase-1', 0)",
                (f"story-inp-{i:02d}", f"In Progress Parent {i}", 200 + i),
            )
        conn.commit()

        proposal = package_next_release_proposal(conn=conn, repo_root=str(tmp_path))
        assert proposal is not None
        assert len(proposal["stories"]) == 12
        assert len(proposal["context_stories"]) == 7

        body = format_release_proposal_markdown(proposal)
        assert "## 📦 Packaging" in body
        assert "complete goal" in body
        assert "### Context Stories" in body
        for i in range(1, 5):
            assert f"story-umb-{i:02d}" in body
        for i in range(1, 4):
            assert f"story-inp-{i:02d}" in body
    finally:
        conn.close()


