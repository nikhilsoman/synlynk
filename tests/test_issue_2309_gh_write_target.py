"""#2309: a comment or close must be verified on the object that was written.

A pull request named only as context must not become the verification target,
and a cross-branch commit check on that PR must not override a confirmed
comment or close.
"""

import synlynk as sl
import synlynk.jobs as jobs_mod
from synlynk.dispatch import _gh_write_expectation, _resolve_gh_write_target


COMMENT_TASK = (
    "Post one concise but complete comment on parent #2458 recording the sweep. "
    "PR #2539 merged as f4d3ba0 and closed #2530. closed #2237 documents the risk."
)
CLOSE_TASK = (
    "Verify live PR #2543 and PR #2538. Post a concise comment on #2543, "
    "then close #2543 as duplicate. Leave #2538 open and do not close #2538."
)


def test_comment_target_stays_on_the_issue_when_task_names_a_context_pr():
    assert _gh_write_expectation(COMMENT_TASK) == "comment_posted"
    target, kind, cross = _resolve_gh_write_target(COMMENT_TASK, 2458, "issue", True)
    assert (target, kind, cross) == ("issue:2458", "issue", None)


def test_close_target_is_the_pr_being_closed_not_the_pr_left_open():
    assert _gh_write_expectation(CLOSE_TASK) == "closed"
    target, kind, cross = _resolve_gh_write_target(CLOSE_TASK, 2543, "pr", True)
    assert (target, kind, cross) == ("pr:2543", "pr", None)


def test_review_still_verifies_the_named_pr_not_the_governs_issue():
    task = "Review PR #2054. --issue is only the GOVERNS link."
    assert _gh_write_expectation(task) == "review_posted"
    target, kind, cross = _resolve_gh_write_target(task, 2051, "issue", True)
    assert (target, kind, cross) == ("pr:2054", "pr", "pr:2054")


def test_comment_job_accepts_github_confirmed_issue_when_context_pr_has_no_new_commit(project_dir, monkeypatch):
    conn = sl._get_db()
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, status, enqueued_at, started_at, requires_gh_write, "
        "gh_write_target, gh_write_expect, gh_write_author, cross_branch_pr) "
        "VALUES ('job-2309c', 'codex', 'comment', 'done', '2026-10-23T02:06:57', '2026-10-23T02:06:57', 1, "
        "'pr:2539', 'comment_posted', 'synlynk-synlynk-dev[bot]', 'pr:2539')"
    )
    conn.commit()
    log = "https://github.com/nikhilsoman/synlynk/issues/2458#issuecomment-6350774929\n"

    def fake_cross(*_args, **kwargs):
        kwargs["evidence"].update({"matched": False, "cross_branch": True})
        return False

    def fake_verified(target, expect, **_kwargs):
        assert expect == "comment_posted"
        return target == "issue:2458"

    monkeypatch.setattr(jobs_mod, "cross_branch_pr_effect_verified", fake_cross)
    monkeypatch.setattr(jobs_mod, "gh_write_verified", fake_verified)

    status, verified = jobs_mod._verify_daemon_terminal_status(
        conn, "job-2309c", True, "pr:2539", "done",
        "2026-10-23T02:06:57", "synlynk-synlynk-dev[bot]", "comment_posted",
        log_text=log,
    )

    assert (status, verified) == ("done", "true")
    row = conn.execute(
        "SELECT gh_write_target, gh_write_verified FROM daemon_jobs WHERE job_id='job-2309c'"
    ).fetchone()
    assert (row[0], row[1]) == ("issue:2458", "true")


def test_close_job_accepts_github_confirmed_pr_when_other_pr_was_stored(project_dir, monkeypatch):
    conn = sl._get_db()
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, status, enqueued_at, started_at, requires_gh_write, "
        "gh_write_target, gh_write_expect, cross_branch_pr) "
        "VALUES ('job-2309x', 'codex', 'close', 'done', '2026-10-23T02:15:45', '2026-10-23T02:15:45', 1, "
        "'pr:2538', 'closed', 'pr:2538')"
    )
    conn.commit()

    def fake_cross(*_args, **kwargs):
        kwargs["evidence"].update({"matched": False, "cross_branch": True})
        return False

    def fake_verified(target, expect, **_kwargs):
        assert expect == "closed"
        return target == "pr:2543"

    monkeypatch.setattr(jobs_mod, "cross_branch_pr_effect_verified", fake_cross)
    monkeypatch.setattr(jobs_mod, "gh_write_verified", fake_verified)

    status, verified = jobs_mod._verify_daemon_terminal_status(
        conn, "job-2309x", True, "pr:2538", "done",
        "2026-10-23T02:15:45", None, "closed",
        log_text="gh pr close 2543\n",
    )

    assert (status, verified) == ("done", "true")
    row = conn.execute(
        "SELECT gh_write_target, gh_write_verified FROM daemon_jobs WHERE job_id='job-2309x'"
    ).fetchone()
    assert (row[0], row[1]) == ("pr:2543", "true")


def test_unconfirmed_transcript_object_stays_a_failed_write(project_dir, monkeypatch):
    conn = sl._get_db()
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, status, enqueued_at, started_at, requires_gh_write, "
        "gh_write_target, gh_write_expect, cross_branch_pr) "
        "VALUES ('job-2309n', 'codex', 'comment', 'done', '2026-10-23T02:06:57', '2026-10-23T02:06:57', 1, "
        "'pr:2539', 'comment_posted', 'pr:2539')"
    )
    conn.commit()

    def fake_cross(*_args, **kwargs):
        kwargs["evidence"].update({"matched": False, "cross_branch": True})
        return False

    monkeypatch.setattr(jobs_mod, "cross_branch_pr_effect_verified", fake_cross)
    monkeypatch.setattr(jobs_mod, "gh_write_verified", lambda *_a, **_k: False)

    status, verified = jobs_mod._verify_daemon_terminal_status(
        conn, "job-2309n", True, "pr:2539", "done",
        "2026-10-23T02:06:57", None, "comment_posted",
        log_text="https://github.com/nikhilsoman/synlynk/issues/2458#issuecomment-1\n",
    )

    assert (status, verified) == ("succeeded_gh_write_failed", "false")
    row = conn.execute(
        "SELECT gh_write_target FROM daemon_jobs WHERE job_id='job-2309n'"
    ).fetchone()
    assert row[0] == "pr:2539"


def test_review_cross_branch_miss_is_still_a_failed_write(project_dir, monkeypatch):
    conn = sl._get_db()
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, status, enqueued_at, started_at, requires_gh_write, "
        "gh_write_target, gh_write_expect, cross_branch_pr) "
        "VALUES ('job-2309r', 'codex', 'review', 'done', '2026-10-23T02:06:57', '2026-10-23T02:06:57', 1, "
        "'pr:2054', 'review_posted', 'pr:2054')"
    )
    conn.commit()

    def fake_cross(*_args, **kwargs):
        kwargs["evidence"].update({"matched": False, "cross_branch": True})
        return False

    monkeypatch.setattr(jobs_mod, "cross_branch_pr_effect_verified", fake_cross)
    monkeypatch.setattr(jobs_mod, "gh_write_verified", lambda *_a, **_k: True)

    status, verified = jobs_mod._verify_daemon_terminal_status(
        conn, "job-2309r", True, "pr:2054", "done",
        "2026-10-23T02:06:57", None, "review_posted",
        log_text="no review landed\n",
    )

    assert (status, verified) == ("succeeded_gh_write_failed", "false")
