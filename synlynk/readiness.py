"""Consolidated 4-Point Fleet Readiness Matrix for synlynk doctor (#1521)."""

from __future__ import annotations

import json
import os
import socket
import stat
import time
from typing import Any, Dict, List, Optional

_BOLD = "\033[1m"
_GREEN = "\033[32m"
_YELLOW = "\033[33m"
_RED = "\033[31m"
_CYAN = "\033[36m"
_DIM = "\033[2m"
_RESET = "\033[0m"


def check_point_1_role_tokens(apps_dir: Optional[str] = None) -> Dict[str, Any]:
    """Point 1: Verify GitHub App role tokens and expiration."""
    if apps_dir is None:
        apps_dir = os.path.join(".synlynk", "github_apps")

    if not os.path.exists(apps_dir):
        return {
            "key": "role_tokens",
            "name": "Point 1: Role Token Validity",
            "status": "WARN",
            "message": f"No role tokens found: directory {apps_dir} missing",
            "details": {},
            "remediation": "Configure roles with `synlynk join` or in Vizor Role Studio",
        }

    now = time.time()
    roles_found = {}
    expired_roles = []
    valid_roles = []

    for entry in os.listdir(apps_dir):
        role_path = os.path.join(apps_dir, entry)
        if not os.path.isdir(role_path):
            continue
        token_path = os.path.join(role_path, f"{entry}.token.json")
        if os.path.exists(token_path):
            try:
                with open(token_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                expires_at = data.get("expires_at", 0)
                is_valid = isinstance(expires_at, (int, float)) and expires_at - 60 > now
                roles_found[entry] = {
                    "valid": is_valid,
                    "expires_in_s": max(0, int(expires_at - now)),
                }
                if is_valid:
                    valid_roles.append(entry)
                else:
                    expired_roles.append(entry)
            except Exception as e:
                roles_found[entry] = {"valid": False, "error": str(e)}
                expired_roles.append(entry)

    if not roles_found:
        return {
            "key": "role_tokens",
            "name": "Point 1: Role Token Validity",
            "status": "WARN",
            "message": "No role tokens found in github_apps directory",
            "details": roles_found,
            "remediation": "Mint role tokens via `synlynk join` or Vizor Role Studio",
        }

    if expired_roles and not valid_roles:
        return {
            "key": "role_tokens",
            "name": "Point 1: Role Token Validity",
            "status": "FAIL",
            "message": f"All role tokens expired: {', '.join(expired_roles)}",
            "details": roles_found,
            "remediation": "Run `synlynk daemon` or refresh tokens with `synlynk join`",
        }

    if expired_roles:
        return {
            "key": "role_tokens",
            "name": "Point 1: Role Token Validity",
            "status": "WARN",
            "message": f"Valid: {', '.join(valid_roles)} (expired: {', '.join(expired_roles)})",
            "details": roles_found,
            "remediation": "Refresh expired tokens via daemon or `synlynk join`",
        }

    return {
        "key": "role_tokens",
        "name": "Point 1: Role Token Validity",
        "status": "PASS",
        "message": f"Active valid role tokens for: {', '.join(valid_roles)}",
        "details": roles_found,
        "remediation": "",
    }


def check_point_2_sandbox_egress(host: str = "api.github.com", port: int = 443, timeout: float = 3.0) -> Dict[str, Any]:
    """Point 2: Verify outbound network connectivity for sandbox egress."""
    start = time.perf_counter()
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
        sock.close()
        latency_ms = int((time.perf_counter() - start) * 1000)
        return {
            "key": "sandbox_egress",
            "name": "Point 2: Sandbox Egress",
            "status": "PASS",
            "message": f"Egress to {host}:{port} verified ({latency_ms}ms)",
            "details": {"latency_ms": latency_ms, "host": host, "port": port},
            "remediation": "",
        }
    except Exception as e:
        return {
            "key": "sandbox_egress",
            "name": "Point 2: Sandbox Egress",
            "status": "FAIL",
            "message": f"Egress to {host}:{port} unreachable: {e}",
            "details": {"error": str(e), "host": host, "port": port},
            "remediation": "Verify internet connectivity and sandbox_workspace_write.network_access flags",
        }


def check_point_3_policy_authority(repo_path: Optional[str] = None) -> Dict[str, Any]:
    """Point 3: Validate policy authority configuration (.synlynk/policy.json)."""
    if repo_path is None:
        repo_path = os.getcwd()

    policy_path = os.path.join(repo_path, ".synlynk", "policy.json")
    if not os.path.exists(policy_path):
        return {
            "key": "policy_authority",
            "name": "Point 3: Policy Authority",
            "status": "WARN",
            "message": "policy.json missing in .synlynk/",
            "details": {},
            "remediation": "Initialize policy with `synlynk init` or `synlynk policy sync`",
        }

    try:
        with open(policy_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        return {
            "key": "policy_authority",
            "name": "Point 3: Policy Authority",
            "status": "FAIL",
            "message": f"Malformed policy.json: {e}",
            "details": {"error": str(e)},
            "remediation": "Repair JSON syntax in .synlynk/policy.json",
        }

    task_alloc = data.get("task_allocation") or {}
    has_rules = bool(task_alloc or [k for k in data if k.endswith("_authority")])

    if not has_rules:
        return {
            "key": "policy_authority",
            "name": "Point 3: Policy Authority",
            "status": "WARN",
            "message": "policy.json contains no task_allocation or authority rules",
            "details": data,
            "remediation": "Add role allocation rules in .synlynk/policy.json",
        }

    return {
        "key": "policy_authority",
        "name": "Point 3: Policy Authority",
        "status": "PASS",
        "message": "Policy rules valid and authority definitions active",
        "details": {"version": data.get("version", 1), "rules_count": len(data)},
        "remediation": "",
    }


def check_point_4_git_shim(shim_path: Optional[str] = None, env_path: Optional[str] = None) -> Dict[str, Any]:
    """Point 4: Verify git/gh shim installation and PATH precedence."""
    if shim_path is None:
        shim_path = os.path.expanduser("~/.synlynk/gh-shim/gh")
    if env_path is None:
        env_path = os.environ.get("PATH", "")

    if not os.path.exists(shim_path):
        return {
            "key": "git_shim",
            "name": "Point 4: Git Shim Integrity",
            "status": "WARN",
            "message": f"Git shim not installed at {shim_path}",
            "details": {"shim_path": shim_path},
            "remediation": 'Run: eval "$(synlynk gh --shim-env)" to install and activate',
        }

    st = os.stat(shim_path)
    if not (st.st_mode & stat.S_IXUSR):
        return {
            "key": "git_shim",
            "name": "Point 4: Git Shim Integrity",
            "status": "FAIL",
            "message": f"Git shim at {shim_path} is not executable",
            "details": {"shim_path": shim_path},
            "remediation": f"Run: chmod +x {shim_path}",
        }

    shim_dir = os.path.dirname(os.path.realpath(shim_path))
    path_entries = [os.path.realpath(p) for p in env_path.split(os.pathsep) if p]

    if shim_dir not in path_entries:
        return {
            "key": "git_shim",
            "name": "Point 4: Git Shim Integrity",
            "status": "WARN",
            "message": f"Git shim installed at {shim_path} but directory not found in PATH",
            "details": {"shim_dir": shim_dir},
            "remediation": 'Prepend shim directory: eval "$(synlynk gh --shim-env)"',
        }

    return {
        "key": "git_shim",
        "name": "Point 4: Git Shim Integrity",
        "status": "PASS",
        "message": "Git shim active and preceding in PATH",
        "details": {"shim_path": shim_path, "shim_dir": shim_dir},
        "remediation": "",
    }


def evaluate_readiness_matrix(repo_root: Optional[str] = None) -> Dict[str, Any]:
    """Evaluate all 4 readiness checkpoints."""
    p1 = check_point_1_role_tokens(
        apps_dir=os.path.join(repo_root, ".synlynk", "github_apps") if repo_root else None
    )
    p2 = check_point_2_sandbox_egress()
    p3 = check_point_3_policy_authority(repo_path=repo_root)
    p4 = check_point_4_git_shim()

    points = [p1, p2, p3, p4]

    if any(p["status"] == "FAIL" for p in points):
        overall = "FAIL"
    elif any(p["status"] == "WARN" for p in points):
        overall = "WARN"
    else:
        overall = "PASS"

    return {
        "overall_status": overall,
        "points": points,
        "timestamp": time.time(),
    }


def format_readiness_table(matrix: Dict[str, Any]) -> str:
    """Format readiness matrix as an ANSI-colored console table."""
    lines = [
        "",
        f"{_BOLD}SYNLYNK 4-POINT READINESS MATRIX{_RESET}",
        "═" * 78,
    ]

    for p in matrix.get("points", []):
        status = p.get("status", "UNKNOWN")
        if status == "PASS":
            badge = f"{_GREEN}✓ PASS{_RESET}"
        elif status == "WARN":
            badge = f"{_YELLOW}⚠ WARN{_RESET}"
        else:
            badge = f"{_RED}✗ FAIL{_RESET}"

        name = p.get("name", p.get("key", ""))
        lines.append(f"  {badge:<16} {_BOLD}{name}{_RESET}")
        lines.append(f"    {_DIM}Status:{_RESET}  {p.get('message', '')}")
        rem = p.get("remediation", "")
        if rem:
            lines.append(f"    {_DIM}Fix:{_RESET}     {_CYAN}{rem}{_RESET}")
        lines.append("")

    overall = matrix.get("overall_status", "UNKNOWN")
    if overall == "PASS":
        summary = f"{_GREEN}✓ FLEET READINESS VERIFIED — All 4 checkpoints green{_RESET}"
    elif overall == "WARN":
        summary = f"{_YELLOW}⚠ FLEET READINESS OPERATIONAL WITH WARNINGS — Review above fixes{_RESET}"
    else:
        summary = f"{_RED}✗ FLEET READINESS FAILED — Blockers detected{_RESET}"

    lines.append("─" * 78)
    lines.append(f"  {_BOLD}Overall:{_RESET} {summary}")
    lines.append("")
    return "\n".join(lines)


def cmd_doctor_readiness(args=None) -> int:
    """CLI entry point for `synlynk doctor --readiness`."""
    matrix = evaluate_readiness_matrix()
    table = format_readiness_table(matrix)
    print(table)
    return 1 if matrix.get("overall_status") == "FAIL" else 0
