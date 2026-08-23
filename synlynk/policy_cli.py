"""CLI surface for policy.json enforcement outside of dispatch_agent()."""
from __future__ import annotations

import os

from synlynk.policy import check_authority


def cmd_policy_check_merge(role: str) -> int:
    """Print + return whether `role` may merge in the current repo, per policy.json.

    Intended to be run by a dispatched reviewer agent before it calls
    `gh pr merge` itself, per the project's PR Review Discipline convention
    ("the reviewer alone must merge"). Non-zero exit means: do not merge.
    """
    result = check_authority("merge", role=role, repo_path=os.getcwd())
    if not result.allowed:
        print(f"BLOCKED: role {role!r} is not authorized to merge — {result.reason}")
        return 1
    if result.requires_approval:
        print(f"BLOCKED: merge requires human approval per policy.json ({result.reason})")
        return 2
    print(f"cleared to merge: role {role!r} is authorized per policy.json")
    return 0


def cmd_policy_sync_branch_protection(dry_run: bool = False) -> int:
    """Implemented in Task 5."""
    raise NotImplementedError
