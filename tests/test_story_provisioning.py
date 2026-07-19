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


def test_resolve_or_create_story_id_reachable_from_top_level_package():
    import synlynk as sl

    assert callable(sl.resolve_or_create_story_id)


def test_backfill_capability_ratings_skips_jobs_with_existing_story_id(project_dir, monkeypatch):
    from synlynk import story_provisioning as sp
    import synlynk as sl

    sl._save_jobs([{
        "id": "job-1",
        "agent": "claude",
        "story_id": "story-existing",
        "task": "already has a story",
        "log_file": None,
    }])

    backfilled, skipped = sp.cmd_backfill_capability_ratings()

    assert backfilled == 0
    assert skipped == 0


def test_backfill_capability_ratings_skips_jobs_with_missing_log_file(project_dir, monkeypatch, tmp_path):
    from synlynk import story_provisioning as sp
    import synlynk as sl

    missing_log = str(tmp_path / "does-not-exist.log")
    sl._save_jobs([{
        "id": "job-2",
        "agent": "claude",
        "story_id": "",
        "task": "no log on disk",
        "log_file": missing_log,
    }])

    backfilled, skipped = sp.cmd_backfill_capability_ratings()

    assert backfilled == 0
    assert skipped == 1


def test_backfill_capability_ratings_resolves_story_and_writes_rating(project_dir, monkeypatch, tmp_path):
    from synlynk import story_provisioning as sp
    import synlynk as sl

    monkeypatch.setattr(
        sp.subprocess,
        "run",
        lambda *a, **kw: (_ for _ in ()).throw(FileNotFoundError("gh not found")),
    )
    monkeypatch.setattr(sl, "_sign_capability_rating", lambda payload: "")

    log_file = tmp_path / "job-3.log"
    log_file.write_text("47 passed in 3.2s\n")
    sl._save_jobs([{
        "id": "job-3",
        "agent": "claude",
        "story_id": "",
        "task": "fix the thing #501",
        "log_file": str(log_file),
        "model_at_dispatch": "claude-sonnet-5",
    }])

    backfilled, skipped = sp.cmd_backfill_capability_ratings()

    assert backfilled == 1
    assert skipped == 0
    jobs = sl._load_jobs()
    assert jobs[0]["story_id"] == "story-issue-501"
    conn = sl._get_db()
    rating = conn.execute(
        "SELECT story_id FROM capability_ratings WHERE story_id=?",
        ("story-issue-501",)
    ).fetchone()
    conn.close()
    assert rating is not None


def test_cmd_backfill_capability_ratings_reachable_from_top_level_package():
    import synlynk as sl

    assert callable(sl.cmd_backfill_capability_ratings)
