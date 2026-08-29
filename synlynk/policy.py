"""Two-tier (workspace/repo) policy configuration for authority gating.

Follows the same re-read-every-call convention as load_config() in
__init__.py — no caching, no mtime tracking. Policy files are small and
read infrequently relative to dispatch/merge/release actions.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

DEFAULT_WORKSPACE_POLICY: Dict[str, Any] = {
    "schema_version": 1,
    "org": {"org_id": None, "teams": [], "sso_provider": None, "seat_limits": None},
    "defaults": {
        "roadmap_authority": {
            "can_edit_roadmap": ["pm"],
            "can_create_goals": ["pm", "architect"],
        },
        "dev_authority": {
            "task_allocation": {
                "implement": {"harness": "codex", "fallback": ["grok", "agy"]},
                "test": {"harness": "codex", "fallback": ["grok", "agy"]},
                "css": {"harness": "agy", "fallback": []},
                "templates": {"harness": "agy", "fallback": []},
                "canvas": {"harness": "grok", "fallback": []},
                "js": {"harness": "grok", "fallback": []},
                "infra": {"harness": "grok", "fallback": []},
                "refactor": {"harness": "codex", "fallback": []},
                "cli-plumbing": {"harness": "codex", "fallback": []},
                "review": {"harness": "codex", "fallback": ["claude", "agy"]},
                "gh_write": {"harness": "codex", "fallback": ["claude", "agy"]},
                "pm": {"harness": "claude", "fallback": []},
                "brainstorm": {"harness": "claude", "fallback": []},
                "architecture-review": {"harness": "claude", "fallback": []},
            },
        },
        "merge_authority": {
            "can_merge": ["qa"],
            "require_non_authoring_review": True,
            "review_fallback": "comment_checklist",
        },
        "release_authority": {"can_cut_release": ["pm"], "requires_human_approval": True},
        "human_authority_role": {"role": "pm", "requires_human_approval": True},
        "approval_required_for": [
            "security_sensitive_paths:.github/workflows/**,.synlynk/policy.json,.synlynk/github_apps/**",
            "irreversible_merge",
            "named_release",
            "roadmap_authority_change",
        ],
        "agent_roles": {
            "pm": {"default_harness": "claude", "scope": ["roadmap", "review", "deploy", "brainstorm"]},
            "qa": {"default_harness": "claude", "scope": ["review", "merge"]},
            "dev": {"default_harness": "codex", "scope": ["implement", "test"]},
            "architect": {"default_harness": "claude", "scope": ["roadmap", "brainstorm"]},
        },
    },
}


def _read_json(path: Path) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def _workspace_policy_path(workspace_name: str) -> Path:
    return Path(os.path.expanduser("~/.synlynk/workspaces")) / workspace_name / "policy.json"


def _repo_policy_path(repo_path: str) -> Path:
    return Path(repo_path) / ".synlynk" / "policy.json"


def load_policy(repo_path: str, workspace_name: str = "default") -> Dict[str, Any]:
    """Merge workspace defaults with a repo's sparse overrides.

    Merge rule: for each top-level key under "defaults", if the repo's
    "overrides" supplies that key, the repo's value REPLACES the workspace
    default's value entirely (whole-object replace, one level deep — not a
    recursive deep merge).
    """
    ws_raw = _read_json(_workspace_policy_path(workspace_name))
    workspace_doc = ws_raw if ws_raw is not None else DEFAULT_WORKSPACE_POLICY

    merged = json.loads(json.dumps(workspace_doc.get("defaults", DEFAULT_WORKSPACE_POLICY["defaults"])))
    merged["org"] = workspace_doc.get("org", DEFAULT_WORKSPACE_POLICY["org"])

    repo_raw = _read_json(_repo_policy_path(repo_path))
    if repo_raw:
        for key, value in repo_raw.get("overrides", {}).items():
            merged[key] = value

    return merged


def get_human_authority_role(repo_path: str, workspace_name: str = "default") -> str:
    """Return the role currently holding the human-authority pointer."""
    policy = load_policy(repo_path=repo_path, workspace_name=workspace_name)
    pointer = policy.get("human_authority_role") or {}
    return pointer.get("role") or "pm"


import fnmatch
from dataclasses import dataclass, field
from typing import List


@dataclass
class AuthorityResult:
    allowed: bool
    requires_approval: bool = False
    reason: str = ""


_ACTION_PREFIXES = ("roadmap_edit", "goal_create", "merge", "release_cut", "task_dispatch:")


def _matches_approval_rule(action: str, policy: Dict[str, Any]) -> Optional[str]:
    for rule in policy.get("approval_required_for", []):
        if rule == "named_release" and action == "release_cut":
            return rule
        if rule == "roadmap_authority_change" and action in ("roadmap_edit", "goal_create"):
            return rule
        if rule.startswith("security_sensitive_paths:") and action.startswith("task_dispatch:"):
            continue  # path-based rules are checked by callers that know the changed files, not here
    return None


def check_authority(action: str, role: str, repo_path: str, workspace_name: str = "default") -> AuthorityResult:
    if not any(action == p or action.startswith(p) for p in _ACTION_PREFIXES):
        raise ValueError(f"check_authority: unknown action {action!r}")

    policy = load_policy(repo_path=repo_path, workspace_name=workspace_name)

    if action == "roadmap_edit":
        allowed = role in policy["roadmap_authority"]["can_edit_roadmap"]
    elif action == "goal_create":
        allowed = role in policy["roadmap_authority"]["can_create_goals"]
    elif action == "merge":
        allowed = role in policy["merge_authority"]["can_merge"]
    elif action == "release_cut":
        allowed = role in policy["release_authority"]["can_cut_release"]
    elif action.startswith("task_dispatch:"):
        task_type = action.split(":", 1)[1]
        table = policy["dev_authority"]["task_allocation"]
        allowed = task_type in table  # presence in the table = an authorized task type
    else:  # pragma: no cover - guarded by the ValueError check above
        allowed = False

    if not allowed:
        return AuthorityResult(
            allowed=False,
            reason=f"role {role!r} is not authorized for action {action!r} per policy.json",
        )

    matched_rule = _matches_approval_rule(action, policy)
    if matched_rule:
        return AuthorityResult(allowed=True, requires_approval=True, reason=matched_rule)

    return AuthorityResult(allowed=True, requires_approval=False, reason="")
