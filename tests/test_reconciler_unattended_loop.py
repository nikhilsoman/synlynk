"""Tests for Reconciler Integrity, GitHub Write Expectation, and Launch DAG (Sprint 4)."""
import os
import sqlite3
import subprocess
import time
from unittest.mock import MagicMock, patch

import pytest
import synlynk as sl
import synlynk.dispatch as dispatch_mod
import synlynk.jobs as jobs_mod
from synlynk.daemon import _current_repo_revision, _daemon_state_path


# --- Track 1: GitHub Write Expectation Tests (#1511) ---

def test_gh_write_expectation_comment_intent():
    """PM grooming, audit, triage, and summary tasks expect comment_posted, not closed."""
    assert dispatch_mod._gh_write_expectation("Post PM grooming comment on issue #1496") == "comment_posted"
    assert dispatch_mod._gh_write_expectation("Audit issue #1496 and post findings") == "comment_posted"
    assert dispatch_mod._gh_write_expectation("Summarize issue #1496") == "comment_posted"
    assert dispatch_mod._gh_write_expectation("Post update on #1496") == "comment_posted"
    assert dispatch_mod._gh_write_expectation("Triage issue #1496") == "comment_posted"
    assert dispatch_mod._gh_write_expectation("Leave feedback on #1496") == "comment_posted"
    assert dispatch_mod._gh_write_expectation("General analysis", target="issue:1496") == "comment_posted"
    assert dispatch_mod._gh_write_expectation("Review PR #1497", target="pr:1497") == "review_posted"
    assert dispatch_mod._gh_write_expectation("Merge PR #1497", target="pr:1497") == "merged"
    assert dispatch_mod._gh_write_expectation("Close issue #1496", target="issue:1496") == "closed"


def test_gh_write_expectation_explicit_override(isolated_db, project_dir, monkeypatch):
    """Explicit --gh-write-expect override is respected over auto-detection."""
    wt = project_dir / "worktrees" / "job-exp-test"
    wt.mkdir(parents=True)
    (wt / ".git").mkdir()
    log_dir = project_dir / ".synlynk" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    conn = sl._get_db()
    dispatch_mod._ensure_daemon_job_worktree_columns(conn)
    dispatch_mod._ensure_daemon_job_gh_write_columns(conn)

    monkeypatch.setenv("SYNLYNK_GH_WRITE_ALLOW_HOST_AUTH", "1")
    mock_proc = MagicMock(pid=99901)
    mock_proc.__enter__.return_value = mock_proc
    mock_proc.communicate.return_value = ("{}", "")
    mock_proc.poll.return_value = None
    mock_proc.returncode = 0
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: mock_proc)

    dispatch_mod.dispatch_agent(
        agent="codex",
        task="Do something on issue #1496",
        issue=1496,
        requires_gh_write=True,
        role="builder",
        gh_write_expect="comment_posted",
        skip_preflight=True,
        db_conn=conn,
    )

    row = conn.execute(
        "SELECT gh_write_target, gh_write_expect FROM daemon_jobs WHERE pid=99901"
    ).fetchone()
    assert row is not None
    assert row[0] == "issue:1496"
    assert row[1] == "comment_posted"
    conn.close()


# --- Track 2: Reconciler Exit Marker & Worktree Preservation (#1500) ---

def test_reconciler_reads_exit_file_even_if_no_git_activity(tmp_path, project_dir, monkeypatch):
    """Worker exiting 0 without git activity (review/design) is settled as completed/done, not zombie."""
    wt = tmp_path / "worktrees" / "job-review-0"
    wt.mkdir(parents=True)
    (wt / ".git").mkdir()
    log_dir = tmp_path / "logs"
    log_dir.mkdir(parents=True)
    log_file = log_dir / "job-review-0.log"
    log_file.write_text("Review complete: LGTM")
    exit_file = log_dir / "job-review-0.log.exit"
    exit_file.write_text("0\n")

    monkeypatch.setattr(jobs_mod, "_pid_is_alive", lambda pid: False)
    monkeypatch.setattr(jobs_mod, "_daemon_job_worktree_path", lambda *a, **kw: str(wt))
    monkeypatch.setattr(jobs_mod, "_job_has_real_work_landed", lambda git_state: False)

    conn = sl._get_db()
    dispatch_mod._ensure_daemon_job_worktree_columns(conn)
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, story_id, task, status, pid, enqueued_at, "
        "started_at, log_path, requires_gh_write, worktree_path) "
        "VALUES ('job-review-0', 'codex', 's-rev', 'review', 'running', 88810, "
        "'2026-09-08T00:00:00', '2026-09-08T00:00:00', ?, 0, ?)",
        (str(log_file), str(wt)),
    )
    conn.commit()
    conn.close()

    jobs_mod._reconcile_daemon_jobs()

    conn = sl._get_db()
    row = conn.execute(
        "SELECT status, exit_code FROM daemon_jobs WHERE job_id='job-review-0'"
    ).fetchone()
    assert row is not None
    assert row[0] == "completed" or row[0] == "done"
    assert row[1] == 0
    conn.close()


def test_reconciler_preserves_logs_and_updates_db_path_on_worktree_reap(tmp_path, project_dir, monkeypatch):
    """When a worktree is reaped, logs are copied to central logs and daemon_jobs.log_path is updated."""
    wt = tmp_path / "worktrees" / "job-reap-test"
    wt_synlynk_logs = wt / ".synlynk" / "logs"
    wt_synlynk_logs.mkdir(parents=True)
    log_file = wt_synlynk_logs / "job-reap-test.log"
    log_file.write_text("Executed task with 1500 tokens. Completed.")
    exit_file = wt_synlynk_logs / "job-reap-test.log.exit"
    exit_file.write_text("0\n")

    monkeypatch.setattr(jobs_mod, "_pid_is_alive", lambda pid: False)
    monkeypatch.setattr(jobs_mod, "_daemon_job_worktree_path", lambda *a, **kw: str(wt))

    conn = sl._get_db()
    dispatch_mod._ensure_daemon_job_worktree_columns(conn)
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, story_id, task, status, pid, enqueued_at, "
        "started_at, log_path, requires_gh_write, worktree_path) "
        "VALUES ('job-reap-test', 'codex', 's-reap', 'task', 'running', 88820, "
        "'2026-09-08T00:00:00', '2026-09-08T00:00:00', ?, 0, ?)",
        (str(log_file), str(wt)),
    )
    conn.commit()

    reaped = jobs_mod._reap_zombie_worktree("job-reap-test", str(log_file), conn=conn)
    assert reaped is True
    assert not wt.exists()

    central_log = _daemon_state_path("logs", "job-reap-test.log")
    assert os.path.exists(central_log)
    assert "1500 tokens" in open(central_log).read()

    content = jobs_mod._read_job_log(str(log_file))
    assert "1500 tokens" in content

    updated_path = conn.execute(
        "SELECT log_path FROM daemon_jobs WHERE job_id='job-reap-test'"
    ).fetchone()[0]
    assert updated_path == central_log
    conn.close()


# --- Track 3: Transient Git Inspection Error Handling (#1501, #1502) ---

def test_reconciler_initial_git_inspection_error_fails_closed(tmp_path, project_dir, monkeypatch):
    """Initial git inspection raising OSError must fail closed and NOT settle job as killed_zombie."""
    wt = tmp_path / "worktrees" / "job-git-err-1"
    wt.mkdir(parents=True)
    (wt / ".git").mkdir()
    log_file = tmp_path / "logs" / "job-git-err-1.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    log_file.write_text("")

    monkeypatch.setattr(jobs_mod, "_pid_is_alive", lambda pid: False)
    monkeypatch.setattr(jobs_mod, "_daemon_job_worktree_path", lambda *a, **kw: str(wt))

    def fail_inspect(*a, **kw):
        raise OSError("Transient git disk read failure")

    monkeypatch.setattr(jobs_mod, "_worktree_git_state_inspector", lambda: fail_inspect)

    conn = sl._get_db()
    dispatch_mod._ensure_daemon_job_worktree_columns(conn)
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, story_id, task, status, pid, enqueued_at, "
        "started_at, log_path, requires_gh_write, worktree_path) "
        "VALUES ('job-git-err-1', 'codex', 's-err1', 'implement', 'running', 88830, "
        "'2026-09-08T00:00:00', '2026-09-08T00:00:00', ?, 0, ?)",
        (str(log_file), str(wt)),
    )
    conn.commit()
    conn.close()

    jobs_mod._reconcile_daemon_jobs()

    conn = sl._get_db()
    row = conn.execute(
        "SELECT status, terminal_claim_token FROM daemon_jobs WHERE job_id='job-git-err-1'"
    ).fetchone()
    assert row[0] == "running"
    assert row[1] is None
    assert wt.exists()
    conn.close()


# --- Track 4: Daemon Revision Drift Sentinel (#1511) ---

def test_daemon_revision_drift_detection(tmp_path, project_dir, monkeypatch):
    """Daemon detects git HEAD drift from its startup revision and records sentinel alert."""
    sentinel_file = tmp_path / "sentinel.md"
    monkeypatch.setattr(subprocess, "run", lambda cmd, **k: MagicMock(returncode=0, stdout="commit_bbb_new\n"))

    from synlynk.daemon import SynlynkDaemon
    daemon = SynlynkDaemon()
    daemon.start_revision = "commit_aaa_start"
    daemon.sentinel_path = str(sentinel_file)
    daemon.workspace_root = str(tmp_path)

    curr = _current_repo_revision(str(tmp_path))
    assert curr == "commit_bbb_new"

    if daemon.start_revision and curr and curr != daemon.start_revision:
        jobs_mod._write_sentinel_alert(
            "WARN",
            "RUNTIME_REVISION_DRIFT",
            f"Daemon was started at commit {daemon.start_revision[:8]}, but repo HEAD is at {curr[:8]}.",
            str(sentinel_file),
        )

    assert sentinel_file.exists()
    content = sentinel_file.read_text()
    assert "RUNTIME_REVISION_DRIFT" in content
    assert "commit_aaa_start"[:8] in content


# --- Track 5: Durable Launch DAG & Unattended Loop (#1527) ---

def test_launch_dag_structure_and_readiness(isolated_db):
    """Launch DAG maps stories into implement -> review -> merge stages with dependency gating."""
    from synlynk.launch_dag import LaunchDAG

    dag = LaunchDAG()
    stories = [
        {"story_id": "s-1", "title": "Add auth", "role": "builder", "depends_on": []},
        {"story_id": "s-2", "title": "Add style", "role": "builder", "depends_on": []},
        {"story_id": "s-3", "title": "Secure route", "role": "builder", "depends_on": ["s-1"]},
    ]
    dag.build_from_stories(stories)

    ready_nodes = dag.get_ready_nodes()
    ready_ids = {n.node_id for n in ready_nodes}

    assert "impl:s-1" in ready_ids
    assert "impl:s-2" in ready_ids
    assert "impl:s-3" not in ready_ids

    dag.advance_node("impl:s-1", "done")
    ready_after_impl = {n.node_id for n in dag.get_ready_nodes()}
    assert "review:s-1" in ready_after_impl

    dag.advance_node("review:s-1", "done")
    ready_after_rev = {n.node_id for n in dag.get_ready_nodes()}
    assert "merge:s-1" in ready_after_rev
    assert "impl:s-3" not in ready_after_rev

    dag.advance_node("merge:s-1", "done")
    ready_after_merge = {n.node_id for n in dag.get_ready_nodes()}
    assert "impl:s-3" in ready_after_merge


def test_launch_dag_unattended_escalation_on_reserved_gate(isolated_db, monkeypatch):
    """Launch DAG escalates unresolvable failures to GitHub issue assigned to @nikhilsoman."""
    from synlynk.launch_dag import LaunchDAG

    dag = LaunchDAG()
    stories = [
        {"story_id": "s-gate", "title": "Breaking arch change", "role": "architect", "depends_on": []},
        {"story_id": "s-indep", "title": "Independent bugfix", "role": "builder", "depends_on": []},
    ]
    dag.build_from_stories(stories)

    escalations = []
    def fake_escalate(story_id, context, decision_required, options, assignee):
        escalations.append({
            "story_id": story_id,
            "context": context,
            "decision_required": decision_required,
            "assignee": assignee,
        })
        return "https://github.com/nikhilsoman/synlynk/issues/9999"

    monkeypatch.setattr("synlynk.launch_dag.raise_escalation_ticket", fake_escalate)

    dag.escalate_node(
        "impl:s-gate",
        context="Gate 1: Architectural Spec Sign-off",
        decision_required="Approve breaking API spec changes",
        options=["Approve spec as proposed", "Reject and keep backward compatibility"],
        assignee="nikhilsoman",
    )

    node = dag.get_node("impl:s-gate")
    assert node.status in ("awaiting_approval", "blocked")
    assert len(escalations) == 1
    assert escalations[0]["assignee"] == "nikhilsoman"
    assert escalations[0]["story_id"] == "s-gate"

    ready_ids = {n.node_id for n in dag.get_ready_nodes()}
    assert "impl:s-indep" in ready_ids
