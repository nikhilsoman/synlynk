import json
import os
from pathlib import Path

import pytest

from synlynk.policy import load_policy, DEFAULT_WORKSPACE_POLICY
from synlynk.policy import check_authority, AuthorityResult


def test_load_policy_defaults_human_authority_role_to_pm(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    repo = tmp_path / "repo"
    repo.mkdir()
    policy = load_policy(repo_path=str(repo), workspace_name="default")
    assert policy["human_authority_role"] == {"role": "pm", "requires_human_approval": True}


def test_agent_roles_includes_marketing_harness_agy(tmp_path, monkeypatch):
    from synlynk.policy import load_policy

    monkeypatch.setenv("HOME", str(tmp_path))
    policy = load_policy(repo_path=str(tmp_path))
    assert policy["agent_roles"]["marketing"] == {
        "default_harness": "agy",
        "scope": ["content", "blog", "comms"],
    }


def test_get_human_authority_role_reads_pointer(tmp_path, monkeypatch):
    from synlynk.policy import get_human_authority_role

    monkeypatch.setenv("HOME", str(tmp_path))
    repo = tmp_path / "repo"
    repo.mkdir()
    assert get_human_authority_role(repo_path=str(repo)) == "pm"


def test_get_human_authority_role_reads_repo_override(tmp_path, monkeypatch):
    from synlynk.policy import get_human_authority_role

    monkeypatch.setenv("HOME", str(tmp_path))
    repo = tmp_path / "repo"
    repo_policy_path = repo / ".synlynk" / "policy.json"
    _write_json(repo_policy_path, {
        "schema_version": 1,
        "repo_id": "test",
        "overrides": {
            "human_authority_role": {"role": "architect", "requires_human_approval": True},
        },
    })
    assert get_human_authority_role(repo_path=str(repo)) == "architect"


def test_task_allocation_covers_pm_and_architect_task_types(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    repo = tmp_path / "repo"
    repo.mkdir()
    policy = load_policy(repo_path=str(repo), workspace_name="default")
    table = policy["dev_authority"]["task_allocation"]
    assert table["pm"]["harness"] == "claude"
    assert table["brainstorm"]["harness"] == "claude"
    assert table["architecture-review"]["harness"] == "claude"


def test_check_authority_task_dispatch_pm_allowed(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    repo = tmp_path / "repo"
    repo.mkdir()
    result = check_authority("task_dispatch:pm", role="pm", repo_path=str(repo))
    assert result.allowed


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))


def test_load_policy_falls_back_to_hardcoded_defaults_when_no_files_exist(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    repo = tmp_path / "repo"
    repo.mkdir()
    policy = load_policy(repo_path=str(repo), workspace_name="default")
    assert policy["merge_authority"]["can_merge"] == DEFAULT_WORKSPACE_POLICY["defaults"]["merge_authority"]["can_merge"]
    assert policy["merge_authority"]["review_fallback"] == "same_identity_comment_checklist"


def test_load_policy_reads_workspace_defaults(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    ws_policy_path = tmp_path / ".synlynk" / "workspaces" / "acme" / "policy.json"
    _write_json(ws_policy_path, {
        "schema_version": 1,
        "org": {"org_id": "acme", "teams": [], "sso_provider": None, "seat_limits": None},
        "defaults": {
            "merge_authority": {"can_merge": ["qa"], "require_non_authoring_review": True, "review_fallback": "same_identity_comment_checklist"},
        },
    })
    repo = tmp_path / "repo"
    repo.mkdir()
    policy = load_policy(repo_path=str(repo), workspace_name="acme")
    assert policy["merge_authority"]["can_merge"] == ["qa"]
    assert policy["merge_authority"]["review_fallback"] == "same_identity_comment_checklist"
    assert policy["org"]["org_id"] == "acme"


def test_load_policy_repo_cannot_replace_product_merge_authority(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    ws_policy_path = tmp_path / ".synlynk" / "workspaces" / "acme" / "policy.json"
    _write_json(ws_policy_path, {
        "schema_version": 1,
        "org": {"org_id": "acme", "teams": [], "sso_provider": None, "seat_limits": None},
        "defaults": {
            "merge_authority": {"can_merge": ["qa"], "require_non_authoring_review": True, "review_fallback": "same_identity_comment_checklist"},
            "release_authority": {"can_cut_release": ["pm"], "requires_human_approval": True},
        },
    })
    repo = tmp_path / "repo"
    repo_policy_path = repo / ".synlynk" / "policy.json"
    _write_json(repo_policy_path, {
        "schema_version": 1,
        "repo_id": "rxcc",
        "overrides": {
            "merge_authority": {"can_merge": ["qa", "architect"], "require_non_authoring_review": True, "review_fallback": "same_identity_comment_checklist"},
        },
    })
    policy = load_policy(repo_path=str(repo), workspace_name="acme")
    assert policy["merge_authority"]["can_merge"] == ["qa"]
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
        "defaults": {"merge_authority": {"can_merge": ["architect"], "require_non_authoring_review": True, "review_fallback": "same_identity_comment_checklist"}},
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

    Review stays an authorized task type, now for qa (#2068). dev is no longer
    silently accepted for it.
    """
    repo_root = Path(__file__).resolve().parent.parent
    policy = load_policy(repo_path=str(repo_root))
    assert "review" in policy["dev_authority"]["task_allocation"]
    result = check_authority("task_dispatch:review", role="qa", repo_path=str(repo_root))
    assert result.allowed is True
    with pytest.raises(RuntimeError, match=r"correct role for task_type 'review' is qa"):
        check_authority("task_dispatch:review", role="dev", repo_path=str(repo_root))


def test_check_authority_pm_implement_names_dev(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    repo = tmp_path / "repo"
    repo.mkdir()
    with pytest.raises(RuntimeError, match=r"correct role for task_type 'implement' is dev"):
        check_authority("task_dispatch:implement", role="pm", repo_path=str(repo))


def test_dispatch_agent_pm_implement_names_dev(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    from synlynk.dispatch import dispatch_agent

    with pytest.raises(RuntimeError, match=r"correct role for task_type 'implement' is dev"):
        dispatch_agent(
            "codex", "implement the compatibility check",
            task_type="implement", role="pm", context_mode="none",
        )


def test_check_authority_compatible_pairs_stay_allowed(tmp_path, monkeypatch):
    """Every role/task_type pair in role_task_type_compat that is also in the
    allocation table still passes. Pairs absent from task_allocation stay on
    the existing deny path (content/subpages/deploy are repo-policy-only).
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    repo = tmp_path / "repo"
    repo.mkdir()
    policy = load_policy(repo_path=str(repo), workspace_name="default")
    table = policy["dev_authority"]["task_allocation"]
    seen = 0
    for role, task_types in policy["role_task_type_compat"].items():
        for task_type in task_types:
            if task_type not in table:
                result = check_authority(
                    f"task_dispatch:{task_type}", role=role, repo_path=str(repo),
                )
                assert result.allowed is False
                continue
            result = check_authority(
                f"task_dispatch:{task_type}", role=role, repo_path=str(repo),
            )
            assert result.allowed is True, (role, task_type)
            seen += 1
    assert seen > 0


def test_repo_policy_compatible_pairs_include_repo_only_task_types():
    repo_root = Path(__file__).resolve().parent.parent
    policy = load_policy(repo_path=str(repo_root))
    table = policy["dev_authority"]["task_allocation"]
    for task_type in ("content", "subpages", "deploy"):
        assert task_type in table
    for role, task_types in policy["role_task_type_compat"].items():
        for task_type in task_types:
            assert task_type in table, (role, task_type)
            result = check_authority(
                f"task_dispatch:{task_type}", role=role, repo_path=str(repo_root),
            )
            assert result.allowed is True, (role, task_type)


def test_check_authority_gh_write_stays_allocation_only(tmp_path, monkeypatch):
    """gh_write is in task_allocation and not owned by the compatibility matrix."""
    monkeypatch.setenv("HOME", str(tmp_path))
    repo = tmp_path / "repo"
    repo.mkdir()
    result = check_authority("task_dispatch:gh_write", role="dev", repo_path=str(repo))
    assert result.allowed is True
