import json
from types import SimpleNamespace

from scripts.intake_check import COMMENT, main, needs_bundle_comment


def test_issue_without_fingerprint_gets_comment():
    assert needs_bundle_comment({"labels": ["bug", "early-adopter"], "body": "it broke"})


def test_issue_with_fingerprint_is_left_alone():
    assert not needs_bundle_comment(
        {"labels": ["early-adopter"], "body": "x\nfingerprint: abc123abc123\n"}
    )


def test_non_early_adopter_issues_ignored():
    assert not needs_bundle_comment({"labels": ["bug"], "body": "no bundle"})


def test_main_posts_only_the_bundle_comment(tmp_path, monkeypatch):
    event_path = tmp_path / "event.json"
    event_path.write_text(
        json.dumps(
            {
                "issue": {
                    "number": 42,
                    "body": "it broke",
                    "labels": [{"name": "early-adopter"}],
                }
            }
        )
    )
    calls = []

    def run(command):
        calls.append(command)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr("scripts.intake_check.subprocess.run", run)

    assert main([str(event_path)]) == 0
    assert calls == [["gh", "issue", "comment", "42", "--body", COMMENT]]
