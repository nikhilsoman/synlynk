import json
from types import SimpleNamespace

from synlynk import support_engineer as se
from synlynk.support_engineer import find_duplicate_by_fingerprint


def test_exact_fingerprint_match_is_duplicate():
    existing = [{"number": 10, "body": "x\nfingerprint: abc123abc123\n"}]
    new = {"number": 11, "body": "y\nfingerprint: abc123abc123\n"}
    assert find_duplicate_by_fingerprint(new, existing) == 10


def test_no_fingerprint_no_duplicate():
    assert (
        find_duplicate_by_fingerprint(
            {"number": 2, "body": "none"},
            [{"number": 1, "body": "fingerprint: abc123abc123"}],
        )
        is None
    )


def test_issue_ingest_attaches_older_exact_match(monkeypatch):
    issues = [
        {
            "number": 11,
            "title": "new report",
            "body": "fingerprint: abc123abc123",
            "labels": [{"name": "early-adopter"}],
        },
        {
            "number": 10,
            "title": "older report",
            "body": "fingerprint: abc123abc123",
            "labels": [{"name": "early-adopter"}],
        },
    ]

    monkeypatch.setattr(
        se.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout=json.dumps(issues),
            stderr="",
        ),
    )

    findings = se._collect_github_issues({"labels": ["early-adopter"]})
    newer = next(finding for finding in findings if finding["issue_number"] == 11)
    assert newer["early_adopter"] is True
    assert newer["duplicate_number"] == 10


def test_early_adopter_triage_publishes_comment_only(monkeypatch):
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout="https://example.test/comment", stderr="")

    monkeypatch.setattr(se.subprocess, "run", run)
    finding = {
        "type": "github_issues",
        "severity": "medium",
        "issue_number": 11,
        "early_adopter": True,
        "duplicate_number": 10,
    }

    assert se._publish_triage_result(finding, {"summary": "investigated"}) == (
        "https://example.test/comment"
    )
    assert calls[0][:5] == ["gh", "issue", "comment", "11", "--body"]
    assert not {"create", "close", "edit", "--add-label"}.intersection(calls[0])
    assert "possible duplicate of #10" in calls[0][5].lower()
    assert "Sev2" in calls[0][5]
