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


def _policy_requires_gh_write(repo_root: Optional[str]) -> bool:
    """Return whether the repo policy declares a GitHub-write route."""
    if not repo_root:
        repo_root = os.getcwd()
    policy_path = os.path.join(repo_root, ".synlynk", "policy.json")
    try:
        with open(policy_path, "r", encoding="utf-8") as f:
            policy = json.load(f)
    except (OSError, ValueError):
        return False

    def contains_gh_write(value: Any) -> bool:
        if isinstance(value, dict):
            return any(key == "gh_write" or contains_gh_write(item) for key, item in value.items())
        if isinstance(value, list):
            return any(contains_gh_write(item) for item in value)
        return False

    return contains_gh_write(policy)


def _declared_durable_roles() -> List[str]:
    """Return active role slugs whose canonical charter is durable."""
    try:
        from synlynk import agent_store, charter_schema

        durable = []
        for entry in agent_store.list_agents():
            if entry.get("disabled"):
                continue
            role = next(
                (alias.get("value") for alias in entry.get("aliases", [])
                 if alias.get("kind") == "role_slug"),
                None,
            )
            if not role:
                continue
            charter, _revision = agent_store.read_charter(entry.get("agent_id", ""))
            frontmatter, _body = charter_schema.split_frontmatter(charter)
            metadata = charter_schema.parse_frontmatter(frontmatter or "")
            if metadata.get("durability") == "durable" and role not in durable:
                durable.append(role)
        return durable
    except Exception:
        # A missing/unreadable durable-agent registry should not turn this
        # targeted material check into a false positive.
        return []


def check_durable_role_app_material(
    apps_dir: Optional[str] = None,
    *,
    repo_root: Optional[str] = None,
    gh_write_required: Optional[bool] = None,
) -> Dict[str, Any]:
    """Check App material for durable roles when GitHub writes are configured.

    App material is intentionally checked in the role-scoped directory created
    by the provisioning flow (``github_apps/<role>``). Token-only files do not
    satisfy this check because they cannot authenticate a GitHub App.
    """
    if repo_root is None:
        repo_root = os.getcwd()
    if apps_dir is None:
        from synlynk.product_store import resolve_github_apps_dir
        apps_dir = str(resolve_github_apps_dir(repo_root))
    if gh_write_required is None:
        gh_write_required = _policy_requires_gh_write(repo_root)

    durable_roles = _declared_durable_roles()
    if not gh_write_required or not durable_roles:
        return {
            "key": "durable_role_app_material",
            "name": "Durable Role App Material",
            "status": "PASS",
            "message": "No durable-role GitHub App material is required",
            "details": {"gh_write_required": bool(gh_write_required), "roles": durable_roles},
            "remediation": "",
        }

    missing = []
    for role in durable_roles:
        flat_json = os.path.join(apps_dir, f"{role}.json")
        flat_pem = os.path.join(apps_dir, f"{role}.pem")
        role_dir = os.path.join(apps_dir, role)
        has_material = (os.path.isfile(flat_json) and os.path.isfile(flat_pem)) or (
            os.path.isdir(role_dir) and any(
                os.path.isfile(os.path.join(role_dir, filename))
                and (filename.endswith(".app.json") or filename.endswith(".private-key.pem") or filename.endswith(".pem"))
                for filename in os.listdir(role_dir)
            )
        )
        if not has_material:
            missing.append(role)

    if not missing:
        status = "PASS"
        message = f"GitHub App material present for durable role(s): {', '.join(durable_roles)}"
        remediation = ""
    else:
        status = "FAIL"
        message = f"Missing GitHub App material for durable role(s): {', '.join(missing)}"
        remediation = "Provision role Apps with `synlynk identity init --role <role>`"
    return {
        "key": "durable_role_app_material",
        "name": "Durable Role App Material",
        "status": status,
        "message": message,
        "details": {"gh_write_required": True, "roles": durable_roles, "missing": missing},
        "remediation": remediation,
    }


def _with_durable_role_app_material(
    result: Dict[str, Any],
    apps_dir: Optional[str],
    repo_root: Optional[str],
) -> Dict[str, Any]:
    """Apply the durable-material failure without renaming Point 1."""
    material = check_durable_role_app_material(apps_dir, repo_root=repo_root)
    if material["status"] != "FAIL":
        return result

    details = dict(result.get("details") or {})
    details["durable_role_app_material"] = material["details"]
    return {
        **result,
        "status": "FAIL",
        "message": f"{result['message']}; {material['message']}",
        "details": details,
        "remediation": material["remediation"],
    }


def check_point_1_role_tokens(
    apps_dir: Optional[str] = None, *, repo_root: Optional[str] = None
) -> Dict[str, Any]:
    """Point 1: Verify GitHub App role tokens and expiration."""
    using_default_apps_dir = apps_dir is None
    if apps_dir is None:
        apps_dir = os.path.join(".synlynk", "github_apps")

    # Custom app directories are used by callers/tests as isolated token
    # fixtures. Only apply the repo-scoped durable-material guard when the
    # default directory is used or a repo root was explicitly supplied.
    check_material = repo_root is not None or using_default_apps_dir

    if not os.path.exists(apps_dir):
        result = {
            "key": "role_tokens",
            "name": "Point 1: Role Token Validity",
            "status": "WARN",
            "message": f"No role tokens found: directory {apps_dir} missing",
            "details": {},
            "remediation": "Configure roles with `synlynk join` or in Vizor Role Studio",
        }
        return _with_durable_role_app_material(result, apps_dir, repo_root) if check_material else result

    now = time.time()
    roles_found = {}
    expired_roles = []
    valid_roles = []

    for entry in os.listdir(apps_dir):
        token_path = None
        role_name = None
        role_path = os.path.join(apps_dir, entry)
        if os.path.isdir(role_path):
            cand = os.path.join(role_path, f"{entry}.token.json")
            if os.path.exists(cand):
                token_path = cand
                role_name = entry
        elif entry.endswith(".token.json"):
            token_path = role_path
            role_name = entry[:-len(".token.json")]

        if not token_path or not role_name or role_name in roles_found:
            continue

        try:
            with open(token_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            expires_at = data.get("expires_at", 0)
            is_valid = isinstance(expires_at, (int, float)) and expires_at - 60 > now
            roles_found[role_name] = {
                "valid": is_valid,
                "expires_in_s": max(0, int(expires_at - now)),
            }
            if is_valid:
                valid_roles.append(role_name)
            else:
                expired_roles.append(role_name)
        except Exception as e:
            roles_found[role_name] = {"valid": False, "error": str(e)}
            expired_roles.append(role_name)

    if not roles_found:
        result = {
            "key": "role_tokens",
            "name": "Point 1: Role Token Validity",
            "status": "WARN",
            "message": "No role tokens found in github_apps directory",
            "details": roles_found,
            "remediation": "Mint role tokens via `synlynk join` or Vizor Role Studio",
        }
        return _with_durable_role_app_material(result, apps_dir, repo_root) if check_material else result

    if expired_roles and not valid_roles:
        result = {
            "key": "role_tokens",
            "name": "Point 1: Role Token Validity",
            "status": "FAIL",
            "message": f"All role tokens expired: {', '.join(expired_roles)}",
            "details": roles_found,
            "remediation": "Run `synlynk daemon` or refresh tokens with `synlynk join`",
        }
        return _with_durable_role_app_material(result, apps_dir, repo_root) if check_material else result

    if expired_roles:
        result = {
            "key": "role_tokens",
            "name": "Point 1: Role Token Validity",
            "status": "WARN",
            "message": f"Valid: {', '.join(valid_roles)} (expired: {', '.join(expired_roles)})",
            "details": roles_found,
            "remediation": "Refresh expired tokens via daemon or `synlynk join`",
        }
        return _with_durable_role_app_material(result, apps_dir, repo_root) if check_material else result

    result = {
        "key": "role_tokens",
        "name": "Point 1: Role Token Validity",
        "status": "PASS",
        "message": f"Active valid role tokens for: {', '.join(valid_roles)}",
        "details": roles_found,
        "remediation": "",
    }
    return _with_durable_role_app_material(result, apps_dir, repo_root) if check_material else result


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

    overrides = data.get("overrides", {})
    task_alloc = (
        data.get("task_allocation")
        or (data.get("dev_authority") or {}).get("task_allocation")
        or overrides.get("task_allocation")
        or (overrides.get("dev_authority") or {}).get("task_allocation")
        or {}
    )
    has_rules = bool(
        task_alloc
        or [k for k in data if k.endswith("_authority")]
        or [k for k in overrides if k.endswith("_authority")]
    )

    if not has_rules:
        return {
            "key": "policy_authority",
            "name": "Point 3: Policy Authority",
            "status": "WARN",
            "message": "policy.json contains no task_allocation or authority rules",
            "details": data,
            "remediation": "Add role allocation rules in .synlynk/policy.json",
        }

    rules_count = (
        len([k for k in data if k.endswith("_authority")])
        + len([k for k in overrides if k.endswith("_authority")])
    )
    if task_alloc:
        rules_count += len(task_alloc)

    return {
        "key": "policy_authority",
        "name": "Point 3: Policy Authority",
        "status": "PASS",
        "message": "Policy rules valid and authority definitions active",
        "details": {
            "version": data.get("version") or data.get("schema_version", 1),
            "rules_count": rules_count or len(data),
        },
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
        apps_dir=os.path.join(repo_root, ".synlynk", "github_apps") if repo_root else None,
        repo_root=repo_root,
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
