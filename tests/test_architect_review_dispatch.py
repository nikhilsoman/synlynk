"""gh:#2258 — architect is an authorized role for the review task_type.

AGENTS.md / AI_INSTRUCTIONS.md route feature/architecture-impacting reviews
through the architect role, so role_task_type_compat must authorize
architect for review alongside qa. The --dry-run preview path must enforce
the same policy gate as the live dispatch_agent() path.
"""
from pathlib import Path

import pytest

from synlynk.dispatch import _render_dispatch_preview
from synlynk.policy import check_authority, load_policy


def test_role_task_type_compat_authorizes_architect_for_review(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    repo = tmp_path / "repo"
    repo.mkdir()
    policy = load_policy(repo_path=str(repo), workspace_name="default")
    assert "review" in policy["role_task_type_compat"]["architect"]
    assert "review" in policy["role_task_type_compat"]["qa"]
    assert check_authority(
        "task_dispatch:review", role="architect", repo_path=str(repo)
    ).allowed is True


def test_repo_policy_json_authorizes_architect_for_review():
    repo_root = Path(__file__).resolve().parent.parent
    result = check_authority(
        "task_dispatch:review", role="architect", repo_path=str(repo_root)
    )
    assert result.allowed is True
    qa_result = check_authority(
        "task_dispatch:review", role="qa", repo_path=str(repo_root)
    )
    assert qa_result.allowed is True


def test_dev_review_refusal_names_qa_and_architect():
    repo_root = Path(__file__).resolve().parent.parent
    with pytest.raises(RuntimeError, match=r"correct role for task_type 'review' is qa or architect"):
        check_authority("task_dispatch:review", role="dev", repo_path=str(repo_root))


def test_dry_run_preview_allows_architect_review(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    preview = _render_dispatch_preview(
        "claude", "architecture review of auth module", "none",
        task_type="review", role="architect",
    )
    assert preview["agent"] == "claude"


def test_dry_run_preview_still_allows_qa_review(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    preview = _render_dispatch_preview(
        "claude", "architecture review of auth module", "none",
        task_type="review", role="qa",
    )
    assert preview["agent"] == "claude"


def test_dry_run_preview_refuses_dev_review_like_live_dispatch(tmp_path, monkeypatch):
    """Dry-run and live dispatch must agree: dev + review is refused on both."""
    monkeypatch.chdir(tmp_path)
    with pytest.raises(RuntimeError, match="not an authorized task_type"):
        _render_dispatch_preview(
            "claude", "architecture review of auth module", "none",
            task_type="review", role="dev",
        )
    with pytest.raises(RuntimeError, match="not an authorized task_type"):
        check_authority("task_dispatch:review", role="dev", repo_path=str(tmp_path))


def test_dry_run_preview_without_role_or_task_type_unchanged(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    preview = _render_dispatch_preview("claude", "some task", "none")
    assert preview["agent"] == "claude"
