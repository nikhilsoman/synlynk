import pytest
from synlynk.maintainer import is_issue_remediated


def test_detects_remediated_invariant_issue():
    issue_text = "Invariant 1: effect-verified completion contract not enforced in code"
    commits = [
        "docs: update readme",
        "feat(verify): enforce Invariant 1 (Effect-Verified Completion Contract) (#1806)",
    ]
    assert is_issue_remediated(issue_text, commits)


def test_open_bug_not_flagged_remediated():
    issue_text = "Objective-C fork() runtime abort on macOS daemon startup"
    commits = ["docs: update devlog", "fix: bump linkify"]
    assert not is_issue_remediated(issue_text, commits)


def test_detects_remediated_circuit_breaker_issue():
    issue_text = "LIVE-19: circuit breaker does not trip on repeated daemon crash loop"
    commits = [
        "chore: formatting",
        "fix(daemon): implement circuit breaker trip on crash loop (LIVE-19)",
    ]
    assert is_issue_remediated(issue_text, commits)


def test_detects_remediated_daemon_supervision_issue():
    issue_text = "daemon supervision fails to restart worker after OOM kill"
    commits = [
        "feat(daemon): add daemon supervision restart-on-OOM handling",
    ]
    assert is_issue_remediated(issue_text, commits)


def test_unrelated_commits_do_not_remediate_circuit_breaker_issue():
    issue_text = "circuit breaker never resets after cooldown window"
    commits = ["fix: typo in README", "chore: bump deps"]
    assert not is_issue_remediated(issue_text, commits)


def test_empty_commit_list_is_not_remediated():
    issue_text = "Invariant 1: effect-verified completion contract not enforced in code"
    assert not is_issue_remediated(issue_text, [])
