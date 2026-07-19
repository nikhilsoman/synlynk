import json
import subprocess

import pytest


def test_detect_issue_number_prefers_explicit_issue_arg():
    from synlynk import story_provisioning as sp

    assert sp._detect_issue_number("fix something #999", issue=395) == 395


def test_detect_issue_number_falls_back_to_regex_on_task_text():
    from synlynk import story_provisioning as sp

    assert sp._detect_issue_number("rebind DB_PATH per #395", issue=None) == 395


def test_detect_issue_number_returns_none_when_no_match():
    from synlynk import story_provisioning as sp

    assert sp._detect_issue_number("free text task with no issue ref", issue=None) is None


def test_classify_heuristic_matches_docs_keyword_when_gh_unavailable(monkeypatch):
    from synlynk import story_provisioning as sp

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **kw: (_ for _ in ()).throw(FileNotFoundError("gh not found")),
    )
    result = sp._classify_heuristic(issue_number=None, task_text="Update the README docs")

    assert result["discipline"] == "docs"
    assert result["title"] == "Update the README docs"


def test_classify_heuristic_uses_gh_issue_labels_when_available(monkeypatch):
    from synlynk import story_provisioning as sp

    class FakeResult:
        returncode = 0
        stdout = json.dumps(
            {
                "title": "Rebind DB_PATH in selftest",
                "body": "The live selftest writes to the wrong DB",
                "labels": [{"name": "bug"}],
            }
        )
        stderr = ""

    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: FakeResult())
    result = sp._classify_heuristic(issue_number=395, task_text="rebind DB_PATH #395")

    assert result["title"] == "Rebind DB_PATH in selftest"
    assert result["discipline"] == "backend"


def test_classify_heuristic_falls_back_to_none_fields_when_nothing_matches(monkeypatch):
    from synlynk import story_provisioning as sp

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **kw: (_ for _ in ()).throw(FileNotFoundError("gh not found")),
    )
    result = sp._classify_heuristic(issue_number=None, task_text="do the thing")

    assert result["discipline"] is None
    assert result["org_domain"] is None
    assert result["role"] is None
    assert result["stage"] is None


def test_classify_story_raises_not_implemented_for_llm_method():
    from synlynk import story_provisioning as sp

    with pytest.raises(NotImplementedError):
        sp.classify_story(issue_number=None, task_text="anything", method="llm")


def test_classify_story_raises_not_implemented_for_pm_manual_method():
    from synlynk import story_provisioning as sp

    with pytest.raises(NotImplementedError):
        sp.classify_story(issue_number=None, task_text="anything", method="pm_manual")
