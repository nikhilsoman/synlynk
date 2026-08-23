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
                "gh_write": {"harness": "claude", "fallback": ["agy"]},
            },
        },
        "merge_authority": {
            "can_merge": ["qa"],
            "require_non_authoring_review": True,
            "review_fallback": "comment_checklist",
        },
        "release_authority": {"can_cut_release": ["pm"], "requires_human_approval": True},
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
