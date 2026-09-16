"""Authoritative preflight for unattended pull-request merges.

GitHub CI and the qa-gate are the merge signals.  Local job/HUD state is
intentionally not consulted: a ``failed_unverified`` dispatch record can be
stale even when the PR's current checks are green.
"""

from __future__ import annotations

from typing import Any, Callable, Optional


def _run_pr_check(pr_number: Optional[int]) -> tuple[bool, str]:
    """Run the repository's PR check and normalize its exit status."""
    from synlynk.db import cmd_pr_check

    try:
        cmd_pr_check(pr_number=pr_number)
    except SystemExit as exc:
        return False, f"synlynk pr check exited {exc.code}"
    except Exception as exc:  # a merge preflight must fail closed
        return False, f"synlynk pr check failed: {exc}"
    return True, "synlynk pr check passed"


def _run_qa_gate(pr_number: Optional[int]) -> dict[str, Any]:
    from synlynk import detect_remote_owner_repo
    from synlynk.qa_gate import qa_gate_verdict

    owner, repo = detect_remote_owner_repo()
    if not owner or not repo:
        return {"verdict": "red", "reason": "could not determine GitHub owner/repo"}
    return qa_gate_verdict(owner, repo, pr_number=pr_number)


def require_merge_oracle(
    pr_number: Optional[int] = None,
    *,
    role: str = "qa",
    hud: Optional[dict[str, Any]] = None,
    pr_check: Optional[Callable[[Optional[int]], tuple[bool, str]]] = None,
    qa_gate: Optional[Callable[[Optional[int]], dict[str, Any]]] = None,
) -> dict[str, Any]:
    """Return a JSON-ready merge decision after all authoritative preflights.

    ``hud`` is retained only as diagnostic context in the returned JSON.  It
    never participates in the decision, so ``failed_unverified`` cannot block
    a PR whose current CI and qa-gate are green.  If the C8 policy helper is
    present, it is composed here before any merge caller invokes ``gh``.
    """
    check = pr_check or _run_pr_check
    gate_check = qa_gate or _run_qa_gate
    check_ok, check_reason = check(pr_number)
    gate = gate_check(pr_number)

    policy_ok = True
    policy_reason = "policy check not required"
    try:
        from synlynk.policy_cli import cmd_policy_check_merge

        policy_code = cmd_policy_check_merge(role=role)
        policy_ok = policy_code == 0
        policy_reason = "policy check passed" if policy_ok else f"policy check exited {policy_code}"
    except Exception as exc:
        policy_ok = False
        policy_reason = f"policy check failed: {exc}"

    gate_ok = gate.get("verdict") == "green"
    allowed = bool(check_ok and gate_ok and policy_ok)
    reasons = []
    if not check_ok:
        reasons.append(check_reason)
    if not gate_ok:
        reasons.append(gate.get("reason", "qa gate is not green"))
    if not policy_ok:
        reasons.append(policy_reason)

    return {
        "merge_allowed": allowed,
        "pr_number": pr_number,
        "pr_check": {"green": check_ok, "reason": check_reason},
        "qa_gate": gate,
        "policy": {"green": policy_ok, "reason": policy_reason},
        "hud": hud if isinstance(hud, dict) else None,
        "reason": "all merge checks green" if allowed else "; ".join(reasons),
    }


# Descriptive alias for callers that prefer predicate naming.
can_merge = require_merge_oracle
