import json
import os
from pathlib import Path

import pytest

from synlynk.policy import load_policy, DEFAULT_WORKSPACE_POLICY
from synlynk.policy import check_authority, AuthorityResult


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))


def test_load_policy_falls_back_to_hardcoded_defaults_when_no_files_exist(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    repo = tmp_path / "repo"
    repo.mkdir()
    policy = load_policy(repo_path=str(repo), workspace_name="default")
    assert policy["merge_authority"]["can_merge"] == DEFAULT_WORKSPACE_POLICY["defaults"]["merge_authority"]["can_merge"]


def test_load_policy_reads_workspace_defaults(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    ws_policy_path = tmp_path / ".synlynk" / "workspaces" / "acme" / "policy.json"
    _write_json(ws_policy_path, {
        "schema_version": 1,
        "org": {"org_id": "acme", "teams": [], "sso_provider": None, "seat_limits": None},
        "defaults": {
            "merge_authority": {"can_merge": ["qa"], "require_non_authoring_review": True, "review_fallback": "comment_checklist"},
        },
    })
    repo = tmp_path / "repo"
    repo.mkdir()
    policy = load_policy(repo_path=str(repo), workspace_name="acme")
    assert policy["merge_authority"]["can_merge"] == ["qa"]
    assert policy["org"]["org_id"] == "acme"


def test_load_policy_repo_override_replaces_whole_object(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    ws_policy_path = tmp_path / ".synlynk" / "workspaces" / "acme" / "policy.json"
    _write_json(ws_policy_path, {
        "schema_version": 1,
        "org": {"org_id": "acme", "teams": [], "sso_provider": None, "seat_limits": None},
        "defaults": {
            "merge_authority": {"can_merge": ["qa"], "require_non_authoring_review": True, "review_fallback": "comment_checklist"},
            "release_authority": {"can_cut_release": ["pm"], "requires_human_approval": True},
        },
    })
    repo = tmp_path / "repo"
    repo_policy_path = repo / ".synlynk" / "policy.json"
    _write_json(repo_policy_path, {
        "schema_version": 1,
        "repo_id": "rxcc",
        "overrides": {
            "merge_authority": {"can_merge": ["qa", "architect"], "require_non_authoring_review": True, "review_fallback": "comment_checklist"},
        },
    })
    policy = load_policy(repo_path=str(repo), workspace_name="acme")
    assert policy["merge_authority"]["can_merge"] == ["qa", "architect"]
    # release_authority untouched by the override — inherited from workspace defaults
    assert policy["release_authority"]["can_cut_release"] == ["pm"]


def test_load_policy_stub_org_fields_present_but_inert(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    repo = tmp_path / "repo"
    repo.mkdir()
    policy = load_policy(repo_path=str(repo), workspace_name="default")
    assert policy["org"]["teams"] == []
    assert policy["org"]["sso_provider"] is None
    assert policy["org"]["seat_limits"] is None


def test_check_authority_allows_role_in_can_merge(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    repo = tmp_path / "repo"
    repo.mkdir()
    result = check_authority("merge", role="qa", repo_path=str(repo))
    assert isinstance(result, AuthorityResult)
    assert result.allowed is True
    assert result.requires_approval is False


def test_check_authority_denies_role_not_in_can_merge(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    repo = tmp_path / "repo"
    repo.mkdir()
    result = check_authority("merge", role="dev", repo_path=str(repo))
    assert result.allowed is False
    assert "dev" in result.reason


def test_check_authority_release_cut_requires_approval(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    repo = tmp_path / "repo"
    repo.mkdir()
    result = check_authority("release_cut", role="pm", repo_path=str(repo))
    assert result.allowed is True
    assert result.requires_approval is True
    assert "named_release" in result.reason


def test_check_authority_task_dispatch_checked_against_allocation_table(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    repo = tmp_path / "repo"
    repo.mkdir()
    result = check_authority("task_dispatch:css", role="dev", repo_path=str(repo))
    assert result.allowed is True


def test_check_authority_unknown_action_raises_value_error(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    repo = tmp_path / "repo"
    repo.mkdir()
    with pytest.raises(ValueError):
        check_authority("not_a_real_action", role="pm", repo_path=str(repo))


def test_load_policy_missing_repo_override_file_inherits_workspace_defaults(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    ws_policy_path = tmp_path / ".synlynk" / "workspaces" / "acme" / "policy.json"
    _write_json(ws_policy_path, {
        "schema_version": 1,
        "org": {"org_id": "acme", "teams": [], "sso_provider": None, "seat_limits": None},
        "defaults": {"merge_authority": {"can_merge": ["architect"], "require_non_authoring_review": True, "review_fallback": "comment_checklist"}},
    })
    repo = tmp_path / "repo"
    repo.mkdir()  # no .synlynk/policy.json created here
    policy = load_policy(repo_path=str(repo), workspace_name="acme")
    assert policy["merge_authority"]["can_merge"] == ["architect"]


def test_check_authority_task_dispatch_unknown_task_type_denied(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    repo = tmp_path / "repo"
    repo.mkdir()
    result = check_authority("task_dispatch:not_a_real_type", role="dev", repo_path=str(repo))
    assert result.allowed is False


def test_repo_policy_json_authorizes_review_task_type():
    """Regression guard for the #1166/#1172 gap: overrides.dev_authority does a
    whole-object replace over the workspace default (see load_policy()'s merge
    rule), so this repo's own .synlynk/policy.json must carry its own "review"
    entry — it does not inherit one from DEFAULT_WORKSPACE_POLICY.
    """
    repo_root = Path(__file__).resolve().parent.parent
    result = check_authority("task_dispatch:review", role="dev", repo_path=str(repo_root))
    assert result.allowed is True
