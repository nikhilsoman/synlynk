import pytest

from synlynk.concierge import ConciergeResult, synthesize_github_issue


def test_synthesize_github_issue_formats_markdown():
    answers = {
        "title": "Support Fal.ai Media Gateway",
        "problem": "No unified API for generative media models",
        "scope": "synlynk/media.py, synlynk/dispatch.py",
        "criteria": "synlynk media generate invokes Fal endpoint",
    }
    issue_md = synthesize_github_issue(answers)
    assert "## Summary" in issue_md
    assert "Support Fal.ai Media Gateway" in issue_md
    assert "synlynk/media.py" in issue_md
    assert "## Acceptance Criteria" in issue_md


def test_synthesize_github_issue_includes_problem_statement_and_scope():
    answers = {
        "title": "Add retry policy",
        "problem": "Dispatch jobs fail silently on transient errors",
        "scope": "synlynk/dispatch.py",
        "criteria": "Retries 3x with backoff before marking job failed",
    }
    issue_md = synthesize_github_issue(answers)
    assert "### Problem Statement" in issue_md
    assert "Dispatch jobs fail silently on transient errors" in issue_md
    assert "### Proposed Scope" in issue_md
    assert "synlynk/dispatch.py" in issue_md
    assert "Retries 3x with backoff before marking job failed" in issue_md


def test_synthesize_github_issue_handles_missing_answers():
    issue_md = synthesize_github_issue({})
    assert "## Summary" in issue_md
    assert "### Problem Statement" in issue_md
    assert "### Proposed Scope" in issue_md
    assert "## Acceptance Criteria" in issue_md
    assert "New Feature Proposal" in issue_md


def test_concierge_result_dataclass_fields():
    result = ConciergeResult(
        title="Add retry policy",
        body_markdown="## Summary\nAdd retry policy\n",
        target="local_spec",
    )
    assert result.title == "Add retry policy"
    assert result.body_markdown.startswith("## Summary")
    assert result.target == "local_spec"
