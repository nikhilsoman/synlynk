"""Two-tier (workspace/repo) policy configuration for authority gating.

Follows the same re-read-every-call convention as load_config() in
__init__.py — no caching, no mtime tracking. Policy files are small and
read infrequently relative to dispatch/merge/release actions.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

# Derived from CLAUDE.md's Capability-Based Task Allocation table (#2068).
# Task types that exist in task_allocation but not here (for example gh_write)
# stay on the allocation-only gate.
ROLE_TASK_TYPE_COMPAT: Dict[str, List[str]] = {
    "dev": [
        "implement", "test", "css", "templates", "content", "subpages",
        "canvas", "js", "infra", "refactor", "cli-plumbing",
    ],
    "qa": ["review", "test"],
    "pm": ["pm", "brainstorm", "architecture-review", "deploy"],
}


DEFAULT_WORKSPACE_POLICY: Dict[str, Any] = {
    "schema_version": 1,
    "org": {"org_id": None, "teams": [], "sso_provider": None, "seat_limits": None},
    "defaults": {
        "role_task_type_compat": ROLE_TASK_TYPE_COMPAT,
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
            "review_fallback": "same_identity_comment_checklist",
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
            "marketing": {"default_harness": "agy", "scope": ["content", "blog", "comms"]},
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


def load_policy(repo_path: str, workspace_name: str = None) -> Dict[str, Any]:
    """Merge workspace defaults with a repo's sparse overrides.

    Merge rule: for each top-level key under "defaults", if the repo's
    "overrides" supplies that key, the repo's value REPLACES the workspace
    default's value entirely (whole-object replace, one level deep — not a
    recursive deep merge).
    """
    if workspace_name is None:
        from synlynk.product_store import identity_slug_from_config
        workspace_name = identity_slug_from_config(repo_path)
    ws_raw = _read_json(_workspace_policy_path(workspace_name))
    workspace_doc = ws_raw if ws_raw is not None else DEFAULT_WORKSPACE_POLICY

    if "defaults" in workspace_doc:
        base = workspace_doc.get("defaults", {})
    else:
        base = {key: value for key, value in workspace_doc.items()
                if key in DEFAULT_WORKSPACE_POLICY["defaults"]}
    merged = json.loads(json.dumps(DEFAULT_WORKSPACE_POLICY["defaults"]))
    merged.update(json.loads(json.dumps(base)))
    merged["org"] = workspace_doc.get("org", DEFAULT_WORKSPACE_POLICY["org"])

    repo_raw = _read_json(_repo_policy_path(repo_path))
    if repo_raw:
        for key, value in repo_raw.get("overrides", {}).items():
            if key in {"merge_authority", "connector_authority"}:
                continue
            merged[key] = value

    return merged


def get_human_authority_role(repo_path: str, workspace_name: str = None) -> str:
    """Return the role currently holding the human-authority pointer."""
    policy = load_policy(repo_path=repo_path, workspace_name=workspace_name)
    pointer = policy.get("human_authority_role") or {}
    return pointer.get("role") or "pm"


import fnmatch
from dataclasses import dataclass, field
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


def _correct_roles_for_task_type(compat: Dict[str, Any], task_type: str) -> List[str]:
    """Roles whose compatibility list contains task_type, in table order."""
    return [name for name, types in compat.items() if task_type in (types or [])]


def _reject_incompatible_role_task(
    policy: Dict[str, Any], role: str, task_type: str, *, enforce: bool,
) -> None:
    """Hard-fail when an explicit role is not allowed to dispatch task_type.

    Unknown task types stay on the allocation-table deny path (allowed=False,
    RuntimeError raised by dispatch). A mismatch against role_task_type_compat
    raises here, naming the role that owns the task type (#2068).
    Omitted roles are not checked: dispatch's historical stand-in of "dev"
    is only for the allocation gate, not an explicit --role.
    """
    if not enforce or not role:
        return
    compat = policy.get("role_task_type_compat") or {}
    if not compat:
        return
    allowed_types = compat.get(role) or []
    if task_type in allowed_types:
        return
    correct = _correct_roles_for_task_type(compat, task_type)
    if not correct:
        return
    named = " or ".join(correct)
    raise RuntimeError(
        f"Dispatch refused: task_type {task_type!r} is not an authorized task_type "
        f"for role {role!r} per policy.json (role_task_type_compat). "
        f"The correct role for task_type {task_type!r} is {named}."
    )


def check_authority(
    action: str,
    role: str,
    repo_path: str,
    workspace_name: str = None,
    enforce_role_compat: bool = True,
) -> AuthorityResult:
    if not any(action == p or action.startswith(p) for p in _ACTION_PREFIXES):
        raise ValueError(f"check_authority: unknown action {action!r}")

    policy = load_policy(repo_path=repo_path, workspace_name=workspace_name)

    if action == "roadmap_edit":
        allowed = role in policy["roadmap_authority"]["can_edit_roadmap"]
    elif action == "goal_create":
        allowed = role in policy["roadmap_authority"]["can_create_goals"]
    elif action == "merge":
        allowed = _merge_role_allowed(role, policy, repo_path)
    elif action == "release_cut":
        allowed = role in policy["release_authority"]["can_cut_release"]
    elif action.startswith("task_dispatch:"):
        task_type = action.split(":", 1)[1]
        table = policy["dev_authority"]["task_allocation"]
        if task_type not in table:
            allowed = False
        else:
            _reject_incompatible_role_task(
                policy, role, task_type, enforce=enforce_role_compat,
            )
            allowed = True
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


def _merge_role_allowed(role: str, policy: Dict[str, Any], repo_path: str) -> bool:
    """Resolve product type ids for merge authority, with legacy fallback."""
    can_merge = policy.get("merge_authority", {}).get("can_merge", [])
    try:
        from synlynk.product_store import identity_slug_from_config
        from synlynk.types_registry import load_types
        types = load_types(identity_slug_from_config(repo_path))
        type_info = types.get(role)
        if type_info is not None:
            return bool(type_info.get("canonical") and type_info.get("kind") == "qa"
                        and (role in can_merge or "qa" in can_merge))
    except (OSError, ValueError, TypeError):
        pass
    return role in can_merge


def verify_testbed_receipt(
    commit_sha: str,
    receipts_dir: Optional[Path] = None,
    repo_path: Optional[str] = None,
) -> bool:
    """Verifies that an attested testbed receipt exists for the commit and passed."""
    if receipts_dir is None:
        base = Path(repo_path) if repo_path else Path.cwd()
        receipts_dir = base / "project-docs" / "receipts"

    if not receipts_dir.exists():
        return False

    receipt_path = receipts_dir / f"testbed-receipt-{commit_sha}.json"
    if not receipt_path.exists():
        # Check matching wildcards
        matches = list(receipts_dir.glob(f"*{commit_sha}*.json"))
        if not matches:
            return False
        receipt_path = matches[0]

    try:
        with open(receipt_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("overall_verdict") == "PASSED" and bool(data.get("signature"))
    except Exception:
        return False

