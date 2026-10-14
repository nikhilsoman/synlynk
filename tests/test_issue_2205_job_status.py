import json
import pytest
from synlynk.costs import _log_has_permission_denied_signature, _event_shows_real_activity
from synlynk.dispatch import _write_job_summary, _summary_status_label, _job_summary_path
from synlynk.jobs import _should_classify_permission_denied


def test_codex_log_with_embedded_sandbox_phrase_not_permission_denied():
    """Finding 1 of #2205: A Codex job reading AGENTS.md or documentation that mentions
    'sandbox denies shell execution' must not be misclassified as PERMISSION_DENIED
    when the job ran multiple turns, executed commands, and completed work.
    """
    lines = [
        json.dumps({
            "type": "item.completed",
            "item": {"id": "item_1", "type": "agent_message", "text": "Starting task"}
        }),
        json.dumps({
            "type": "item.completed",
            "item": {
                "id": "item_2",
                "type": "command_execution",
                "command": "sed -n '1,100p' AGENTS.md",
                "aggregated_output": "Note: Grok's dispatch sandbox denies shell execution entirely in this environment",
                "exit_code": 0
            }
        }),
        json.dumps({
            "type": "item.completed",
            "item": {
                "id": "item_3",
                "type": "command_execution",
                "command": "pytest tests/test_foo.py",
                "aggregated_output": "21 passed in 1.2s",
                "exit_code": 0
            }
        }),
        json.dumps({
            "type": "item.completed",
            "item": {
                "id": "item_4",
                "type": "agent_message",
                "text": "All 21 tests passed. Verified PR #1809."
            }
        }),
        json.dumps({
            "type": "turn.completed",
            "usage": {"input_tokens": 1000, "output_tokens": 200}
        })
    ]
    log_text = "\n".join(lines)
    assert not _log_has_permission_denied_signature(log_text)


def test_real_headless_auto_denial_detected():
    """Genuine headless auto-denial without activity must still be detected."""
    denial_log = "Error: execution denied in headless sandbox\nauto-denied permission that headless mode cannot prompt for"
    assert _log_has_permission_denied_signature(denial_log)


def test_succeeded_gh_write_failed_updates_summary_status(tmp_path, monkeypatch):
    """Finding 2 of #2205: when a job's status is reconciled to succeeded_gh_write_failed,
    the summary file must not remain stuck at 'OK (exit 0)'.
    """
    monkeypatch.chdir(tmp_path)
    job_id = "job-test-2205"

    # 1. Initial process exit writes OK (exit 0)
    _write_job_summary(
        job_id=job_id,
        agent="claude",
        story_id="story-1",
        exit_code=0,
        duration_s=10.0,
        in_tokens=100,
        out_tokens=50,
        cost_usd=0.01,
        files_touched=[],
    )
    summary_file = _job_summary_path(job_id)
    with open(summary_file) as f:
        initial_content = f.read()
    assert _summary_status_label(initial_content) == "OK (exit 0)"

    # 2. Reconciled terminal settlement with succeeded_gh_write_failed
    _write_job_summary(
        job_id=job_id,
        agent="claude",
        story_id="story-1",
        exit_code=0,
        duration_s=10.0,
        in_tokens=100,
        out_tokens=50,
        cost_usd=0.01,
        files_touched=[],
        status_label="succeeded_gh_write_failed",
    )
    with open(summary_file) as f:
        reconciled_content = f.read()
    assert _summary_status_label(reconciled_content) == "succeeded_gh_write_failed"
