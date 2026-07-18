import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_maybe_open_worktree_pr_returns_pr_number(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import subprocess

    from synlynk import jobs as jobs_mod

    def fake_run(cmd, **kwargs):
        class FakeResult:
            pass

        result = FakeResult()
        if cmd[:3] == ["gh", "pr", "list"]:
            result.returncode = 0
            result.stdout = "[]"
            result.stderr = ""
        elif cmd[:3] == ["gh", "pr", "create"]:
            result.returncode = 0
            result.stdout = "https://github.com/owner/repo/pull/42\n"
            result.stderr = ""
        return result

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(
        jobs_mod,
        "_pkg",
        lambda name, default=None: (lambda: ("owner", "repo")) if name == "detect_remote_owner_repo" else default,
    )

    job = {"id": "job-1", "task": "test task"}
    pr_number = jobs_mod._maybe_open_worktree_pr(job, "/fake/worktree", "feat/test-branch")
    assert pr_number == 42


def test_review_cycle_multiplier_one_shot_is_ten_percent_bonus():
    from synlynk.pr_multiplier import _review_cycle_multiplier

    assert abs(_review_cycle_multiplier(1) - 1.10) < 0.0001


def test_review_cycle_multiplier_two_shot_is_about_minus_nine_percent():
    from synlynk.pr_multiplier import _review_cycle_multiplier

    assert abs(_review_cycle_multiplier(2) - 0.9075) < 0.0001


def test_review_cycle_multiplier_three_shot_is_about_minus_25_percent():
    from synlynk.pr_multiplier import _review_cycle_multiplier

    assert abs(_review_cycle_multiplier(3) - 0.7486875) < 0.0001


def test_review_cycle_multiplier_floors_at_quarter():
    from synlynk.pr_multiplier import _review_cycle_multiplier

    assert _review_cycle_multiplier(20) == 0.25


def test_apply_review_cycle_multiplier_updates_quality_and_clamps(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import os

    os.makedirs(".synlynk", exist_ok=True)

    import synlynk as sl
    from synlynk.pr_multiplier import _apply_review_cycle_multiplier

    conn = sl._get_db()
    conn.execute("INSERT INTO stories (story_id, title) VALUES ('s1', 'test')")
    conn.execute(
        "INSERT INTO capability_ratings (story_id, agent, model_version, quality, pr_number) "
        "VALUES ('s1', 'codex', 'gpt-5-codex', 9.5, 42)"
    )
    conn.commit()

    _apply_review_cycle_multiplier(conn, pr_number=42, changes_requested_count=0)

    row = conn.execute("SELECT quality FROM capability_ratings WHERE pr_number=42").fetchone()
    conn.close()
    assert row[0] == 10.0


def test_current_pr_number_uses_gh_pr_view(monkeypatch):
    import subprocess

    from synlynk import pr_multiplier

    def fake_run(cmd, **kwargs):
        class FakeResult:
            pass

        result = FakeResult()
        assert cmd[:3] == ["gh", "pr", "view"]
        result.returncode = 0
        result.stdout = '{"number": 17}'
        result.stderr = ""
        return result

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert pr_multiplier._current_pr_number() == 17


def test_current_pr_number_returns_none_when_gh_fails(monkeypatch):
    import subprocess

    from synlynk import pr_multiplier

    def fake_run(cmd, **kwargs):
        class FakeResult:
            pass

        result = FakeResult()
        result.returncode = 1
        result.stdout = ""
        result.stderr = "no pull requests found"
        return result

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert pr_multiplier._current_pr_number() is None
