import json
import os
from pathlib import Path

import pytest

from synlynk.policy import load_policy, DEFAULT_WORKSPACE_POLICY


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
