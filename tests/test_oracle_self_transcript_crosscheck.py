"""Regression tests for gh:#2309: job-status oracle emits false-negative failure labels.

Asserts that job-status oracle cross-checks the job's own transcript for positive
GitHub effect evidence instead of falsely failing when out-of-band checks fail or
when GitHub effects (like PR merges, PR creation, or issue comments) do not touch git.

Three real fixtures tested:
1. job-cbe2a362: Grok review/merge on PR #2577 -> merged cleanly, must not be labeled succeeded_gh_write_failed
2. job-77e59e43: Codex implement opening PR #2579 -> created cleanly, must not be labeled
   succeeded_gh_write_failed / TASK_DELIVERY_FAILED / FAILED_NOOP_DENIED
3. job-c801eb96: probe task posting issue comment on #2138 -> commented cleanly, must not be labeled
   TASK_DELIVERY_FAILED
"""

import os
import pytest

import synlynk
import synlynk.jobs as jobs_mod
from synlynk.verify_effects import (
    extract_transcript_gh_evidence,
    verify_job_effects,
    STATUS_FAILED_NOOP_DENIED,
)


# ---------------------------------------------------------------------------
# Fixture 1: job-cbe2a362 (Grok, review/merge on PR #2577)
# ---------------------------------------------------------------------------
def test_job_cbe2a362_pr_merge_not_succeeded_gh_write_failed(project_dir, monkeypatch):
    """Fixture 1: job-cbe2a362 (Grok, review/merge on PR #2577).

    RECONSTRUCTED FROM TICKET TEXT:
    Job: job-cbe2a362
    Agent: grok
    Story: story-issue-2577
    Task: Review and, if clean, approve+merge PR #2577 (docs-only cost-telemetry sync, 3 files in project-docs/, no code changes)
    Ground truth: gh pr view 2577 shows MERGED PR, commit e86d17c2.
    Transcript shows gh pr merge succeeded.

    Oracle must cross-check job transcript and NOT downgrade to succeeded_gh_write_failed.
    """
    transcript = (
        "RECONSTRUCTED FROM TICKET TEXT\n"
        "Job: job-cbe2a362\n"
        "Agent: grok\n"
        "Task: Review and, if clean, approve+merge PR #2577\n"
        "$ gh pr merge 2577 --squash --delete-branch\n"
        "Merged #2577\n"
    )

    log_path = os.path.join(project_dir, ".synlynk", "logs", "job-cbe2a362.log")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with open(log_path, "w") as f:
        f.write(transcript)

    conn = synlynk._get_db()
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, story_id, task, status, pid, enqueued_at, "
        "started_at, log_path, requires_gh_write, gh_write_target, gh_write_expect) "
        "VALUES ('job-cbe2a362', 'grok', 'story-issue-2577', 'merge PR 2577', 'running', NULL, "
        "'2026-10-24T06:25:00', '2026-10-24T06:25:00', ?, 1, 'pr:2577', 'merged')",
        (log_path,),
    )
    conn.commit()

    # Out-of-band gh check returns False (simulating API timing / since-window mismatch)
    monkeypatch.setattr(jobs_mod, "gh_write_verified", lambda *a, **kw: False)

    status, verified_str = jobs_mod._apply_gh_write_verification(
        conn,
        "job-cbe2a362",
        requires_gh_write=True,
        gh_write_target="pr:2577",
        status="done",
        since="2026-10-24T06:25:00",
        expect="merged",
        log_text=transcript,
    )

    assert status != "succeeded_gh_write_failed", f"Got false-negative status: {status}"
    assert status == "done"
    assert verified_str == "true"

    row = conn.execute(
        "SELECT status, gh_write_verified FROM daemon_jobs WHERE job_id='job-cbe2a362'"
    ).fetchone()
    conn.close()
    assert row[0] != "succeeded_gh_write_failed"
    assert row[1] == "true"


# ---------------------------------------------------------------------------
# Fixture 2: job-77e59e43 (Codex, implement, opened PR #2579 for gh:#2576)
# ---------------------------------------------------------------------------
def test_job_77e59e43_pr_create_not_failed(project_dir, monkeypatch):
    """Fixture 2: job-77e59e43 (Codex, implement, opened PR #2579 for gh:#2576).

    RECONSTRUCTED FROM TICKET TEXT:
    Job: job-77e59e43
    Agent: codex
    Story: story-issue-2576
    Task: Fix gh:#2576's documented Muse capability-sweep blocker in synlynk/capability_sweep.py.
    Ground truth: gh pr view 2579 shows PR open/created by this job.
    Transcript shows pr_created evidence (https://github.com/nikhilsoman/synlynk/pull/2579).

    Oracle must NOT label succeeded_gh_write_failed / TASK_DELIVERY_FAILED / FAILED_NOOP_DENIED.
    """
    transcript = (
        "RECONSTRUCTED FROM TICKET TEXT\n"
        "Job: job-77e59e43\n"
        "Agent: codex\n"
        "Task: Fix gh:#2576 Muse capability-sweep blocker\n"
        "$ gh pr create --title 'fix: Muse capability sweep' --body 'Closes #2576'\n"
        "https://github.com/nikhilsoman/synlynk/pull/2579\n"
    )

    log_path = os.path.join(project_dir, ".synlynk", "logs", "job-77e59e43.log")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with open(log_path, "w") as f:
        f.write(transcript)

    conn = synlynk._get_db()
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, story_id, task, task_type, status, pid, enqueued_at, "
        "started_at, log_path, requires_gh_write, gh_write_target, gh_write_expect) "
        "VALUES ('job-77e59e43', 'codex', 'story-issue-2576', 'Fix gh:#2576', 'implement', 'running', NULL, "
        "'2026-10-24T06:45:00', '2026-10-24T06:45:00', ?, 1, 'issue:2576', 'closed')",
        (log_path,),
    )
    conn.commit()

    # Out-of-band gh check returns False
    monkeypatch.setattr(jobs_mod, "gh_write_verified", lambda *a, **kw: False)

    # 1. Check _apply_gh_write_verification
    status, verified_str = jobs_mod._apply_gh_write_verification(
        conn,
        "job-77e59e43",
        requires_gh_write=True,
        gh_write_target="issue:2576",
        status="done",
        since="2026-10-24T06:45:00",
        expect="closed",
        log_text=transcript,
    )
    conn.close()

    assert status != "succeeded_gh_write_failed", f"Got false-negative status: {status}"
    assert status != "failed_noop_denied"
    assert status != "task_delivery_failed"
    assert verified_str == "true"

    # 2. Check verify_job_effects
    effect_res = verify_job_effects(
        worktree_path=None,
        task_class="gh_write",
        expected_gh_effect="closed",
        gh_verify_kwargs={"target": "issue:2576", "expect": "closed", "log_text": transcript},
    )
    assert effect_res.status != STATUS_FAILED_NOOP_DENIED, f"Got FAILED_NOOP_DENIED: {effect_res.reason}"
    assert effect_res.verified is True

    # 3. Check _task_delivery_has_corroborating_activity
    job_dict = {
        "id": "job-77e59e43",
        "agent": "codex",
        "task_type": "implement",
        "requires_gh_write": 1,
        "gh_write_target": "issue:2576",
    }
    has_activity = jobs_mod._task_delivery_has_corroborating_activity(
        job_dict, git_state=None, log_text=transcript
    )
    assert has_activity is True

    delivery = jobs_mod._classify_task_delivery("absent", has_activity)
    assert delivery["hard_fail"] is False


# ---------------------------------------------------------------------------
# Fixture 3: job-c801eb96 (probe/investigate closing gh:#2138)
# ---------------------------------------------------------------------------
def test_job_c801eb96_issue_comment_not_task_delivery_failed():
    """Fixture 3: job-c801eb96 (probe/investigate task closing gh:#2138).

    RECONSTRUCTED FROM TICKET TEXT:
    Job: job-c801eb96
    Agent: agy
    Story: story-issue-2138
    Task: GH-write verification probe for issue #2138. Post comment on issue #2138.
    Ground truth: gh issue view 2138 shows comment 6381647614 posted.
    Transcript shows gh issue comment succeeded.

    Job was not tagged requires_gh_write and had zero git diff (work was an issue comment).
    Oracle must detect comment_posted in transcript and NOT label TASK_DELIVERY_FAILED.
    """
    transcript = (
        "RECONSTRUCTED FROM TICKET TEXT\n"
        "Job: job-c801eb96\n"
        "Agent: agy\n"
        "Task: GH-write verification probe for issue #2138\n"
        "$ gh issue comment 2138 --body 'GH-write verification probe from job-c801eb96'\n"
        "https://github.com/nikhilsoman/synlynk/issues/2138#issuecomment-6381647614\n"
    )

    # 1. extract_transcript_gh_evidence must detect comment_posted and issue_number
    ev = extract_transcript_gh_evidence(transcript)
    assert ev.get("comment_posted") is True, f"Failed to detect comment_posted: {ev}"
    assert str(ev.get("issue_number")) == "2138", f"Failed to extract issue_number 2138: {ev}"

    # 2. _task_delivery_has_corroborating_activity must treat comment_posted as corroborating
    # regardless of requires_gh_write flag or task_type
    job_dict = {
        "id": "job-c801eb96",
        "agent": "agy",
        "task_type": "probe",
        "requires_gh_write": 0,
        "task": "GH-write verification probe for issue #2138",
    }
    git_state = {"has_activity": False, "remote_has_activity": False, "commits_ahead": 0}

    has_activity = jobs_mod._task_delivery_has_corroborating_activity(
        job_dict, git_state, log_text=transcript
    )
    assert has_activity is True, "Expected corroborating activity from issue comment transcript"

    # 3. Receipt status 'absent' combined with corroborating activity must not hard fail
    delivery = jobs_mod._classify_task_delivery("absent", has_activity)
    assert delivery["hard_fail"] is False
    assert delivery["warn"] is True
