"""CLI surface for policy.json enforcement outside of dispatch_agent()."""
from __future__ import annotations

import os
import json
import subprocess

from synlynk.policy import check_authority, load_policy
from synlynk import _get_db
from synlynk.policy_gates import RE_HARDEN_THRESHOLD, gate_streak

REQUIRED_STATUS_CHECKS = ["test (3.8)", "test (3.10)", "test (3.12)", "qa-gate"]
GATES = ("governs_authority", "cross_harness_review")


def cmd_policy_gate_status() -> int:
    """Print each observe-mode gate's current clean-pass streak."""
    conn = _get_db()
    for gate in GATES:
        streak = gate_streak(conn, gate)
        if streak is None:
            print(f"  {gate}: no data yet")
            continue
        print(f"  {gate}: streak: {streak} / {RE_HARDEN_THRESHOLD}")
        if streak >= RE_HARDEN_THRESHOLD:
            print(f"    → {streak} consecutive clean passes. Consider flipping this gate's mode to \"enforce\" in .synlynk/policy.json.")
    conn.close()
    return 0


def _current_repo_slug() -> str:
    result = subprocess.run(
        ["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"],
        capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


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


def cmd_policy_show() -> int:
    policy = load_policy(repo_path=os.getcwd())
    print(json.dumps(policy, indent=2))
    return 0


def cmd_policy_sync_branch_protection(dry_run: bool = False) -> int:
    policy = load_policy(repo_path=os.getcwd())
    review_count = 1 if policy["merge_authority"]["require_non_authoring_review"] else 0
    body = {
        "required_status_checks": {"strict": True, "contexts": REQUIRED_STATUS_CHECKS},
        "enforce_admins": False,
        "required_pull_request_reviews": {"required_approving_review_count": review_count},
        "restrictions": None,
    }
    if dry_run:
        print(json.dumps(body, indent=2))
        return 0

    repo_slug = _current_repo_slug()
    result = subprocess.run(
        [
            "gh", "api", "--method", "PUT",
            f"repos/{repo_slug}/branches/main/protection", "--input", "-",
        ],
        input=json.dumps(body), capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"FAILED to sync branch protection: {result.stderr}")
        return 1
    print(f"branch protection synced for {repo_slug}: required checks {REQUIRED_STATUS_CHECKS}, review_count={review_count}")
    return 0
