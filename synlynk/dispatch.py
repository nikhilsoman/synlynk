"""synlynk dispatch: preflight gates, agent dispatch, exec wrapper."""

import hashlib
import json
import os
import random
import re
import shutil
from dataclasses import asdict
import select
import signal
import subprocess
import sys
import threading
import time
from typing import Optional, Tuple

from synlynk._constants import HARNESS_CAPABILITY_BASELINES, _CODEX_NETWORK_PERMISSION

_ORG_ROLE_TO_BASELINE_ROLE = {
    "dev": "builder",
    "qa": "verifier",
    "architect": "architect",
    "tpm": "architect",
    "pm": "architect",
    "designer": "builder",
    "marketing": "builder",
    "synlynk-bot": "builder",
}

_GH_WRITE_HARNESS_PRIORITY = ("claude", "agy")
_STARTUP_FAILOVER_ORDER = ("codex", "agy", "claude")
_CODEX_REVIEW_WRITABLE_ROOTS = "sandbox_workspace_write.writable_roots=[]"


def _codex_network_flags(read_only: bool = False) -> list:
    """Enable Codex network access while keeping review worktrees unwritable."""
    flags = ["-c", "sandbox_workspace_write.network_access=true"]
    if read_only:
        flags += ["-c", _CODEX_REVIEW_WRITABLE_ROOTS]
    return flags


def _secondary_harness(agent: str, baselines_map: dict = None) -> Optional[str]:
    """Return the next configured harness for a launch-time failover."""
    available = baselines_map or HARNESS_CAPABILITY_BASELINES
    try:
        index = _STARTUP_FAILOVER_ORDER.index(agent)
    except ValueError:
        return None
    for candidate in _STARTUP_FAILOVER_ORDER[index + 1:]:
        if candidate in available:
            return candidate
    return None


def _harness_for_org_role(org_role: str, baselines_map: dict, requires_gh_write: bool = False):
    """Deterministic fallback harness selection for agent_id-driven dispatch.

    Picks the first harness whose declared baseline "roles" (architect/
    builder/verifier — a different vocabulary than org-chart roles, see
    docs/superpowers/specs/2026-08-16-agent-dispatch-integration-design.md
    §6) includes the mapped tag for this org role. Does not consult the
    story_id-based capability_scores DB table — that stays story_id-only.
    When requires_gh_write is set, candidates are tried in the fixed
    priority order claude -> agy first, then any remaining CORE_FLEET members
    alphabetically. Non-gh-write selection is untouched: plain alphabetical
    order over CORE_FLEET.
    """
    baseline_role = _ORG_ROLE_TO_BASELINE_ROLE.get(org_role)
    if not baseline_role:
        return None
    from synlynk._constants import CORE_FLEET

    candidates = [n for n in baselines_map if n in CORE_FLEET]
    if requires_gh_write:
        ordered = [n for n in _GH_WRITE_HARNESS_PRIORITY if n in candidates]
        ordered += sorted(n for n in candidates if n not in _GH_WRITE_HARNESS_PRIORITY)
    else:
        ordered = sorted(candidates)

    for name in ordered:
        baseline = baselines_map[name]
        if baseline_role not in baseline.get("roles", []):
            continue
        if requires_gh_write and not baseline.get("can_gh_write", False):
            continue
        return name
    return None

from synlynk.github_app_auth import read_cached_installation_token
from synlynk.fencing import FenceData, is_fenced_command, render_task_fence
from synlynk.git_ref_lock import git_ref_operation_lock
from synlynk.gh_verify import gh_write_verified
from synlynk.sentinel import _read_sentinel_alerts, _write_sentinel_alert
from synlynk.policy import check_authority
from synlynk.capability import expected_value as _capability_expected_value, route_expected_value


def expected_dispatch_value(success_probability: float, criticality: float,
                            amortized_cost: float, p95_latency: float,
                            lambda_: float = 1.0) -> float:
    """Return the adaptive dispatch expected value."""
    return _capability_expected_value(success_probability, criticality, amortized_cost,
                                      p95_latency, lambda_)


def _pkg(name: str, default=None):
    package = sys.modules.get("synlynk")
    if package is None:
        return default
    return getattr(package, name, default)


def _run_tc7() -> dict:
    """Load the Agy gh-write preflight lazily to avoid the doctor cycle."""
    from synlynk.doctor import _run_tc7 as doctor_run_tc7

    return doctor_run_tc7()


def _print_pending_nudges() -> None:
    """Print any queued workspace-agent nudges when enabled by config."""
    load_config_fn = _pkg("load_config")
    config = load_config_fn() if load_config_fn else {}
    if not config.get("nudges", {}).get("enabled", True):
        return
    try:
        from synlynk.workspace_agent import cmd_workspace_agent_run

        cmd_workspace_agent_run()
    except Exception:
        pass
    try:
        from synlynk.fencing import render_nudge_fence
        from synlynk.ux_nudges import pending_ux_tip

        tip = pending_ux_tip()
        if tip:
            print(render_nudge_fence(tip))
    except Exception:
        pass


def _dispatch_flags_for_agent(agent: str) -> list:
    """Return the executable dispatch flags for an agent baseline."""
    baselines_map = _pkg("HARNESS_CAPABILITY_BASELINES", HARNESS_CAPABILITY_BASELINES)
    baselines = baselines_map.get(agent, {})
    dispatch_flags = baselines.get("dispatch_flags", [])
    flags = []
    if isinstance(dispatch_flags, dict):
        for flag in dispatch_flags.get("required_flags", []) or []:
            if flag not in flags:
                flags.append(flag)
    else:
        flags = list(dispatch_flags or [])
    if agent == "local":
        from synlynk.local_agent import _local_dispatch_model_flags

        flags = flags + _local_dispatch_model_flags()
    return flags


_BOOLEAN_CLI_FLAGS = frozenset(
    {
        "--always-approve",
        "--dangerously-skip-permissions",
        "--no-auto-commits",
        "--non-interactive",
        "--print",
        "--verbose",
        "--yes",
        "--yes-always",
    }
)


def _deduplicate_boolean_cli_flags(flags: list) -> list:
    """Remove repeated boolean flags while preserving stable flag ordering."""
    seen = set()
    result = []
    for flag in flags or []:
        if flag in _BOOLEAN_CLI_FLAGS:
            if flag in seen:
                continue
            seen.add(flag)
        result.append(flag)
    return result


def _ensure_daemon_job_context_columns(conn) -> None:
    """Add context_mode / context_bytes if missing (legacy schemas + unit fixtures).

    Safe to call on every dispatch write path. No-ops when columns already exist
    or when the connection has no daemon_jobs table.
    """
    try:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(daemon_jobs)").fetchall()}
    except Exception:
        return
    if not cols:
        return
    if "context_mode" not in cols:
        try:
            conn.execute("ALTER TABLE daemon_jobs ADD COLUMN context_mode TEXT")
        except Exception:
            pass
    if "context_bytes" not in cols:
        try:
            conn.execute("ALTER TABLE daemon_jobs ADD COLUMN context_bytes INTEGER")
        except Exception:
            pass


def _ensure_daemon_job_session_column(conn) -> None:
    """Add session_id if missing (legacy schemas + unit fixtures). Mirrors
    _ensure_daemon_job_context_columns above — same no-op-on-absence contract.
    """
    try:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(daemon_jobs)").fetchall()}
    except Exception:
        return
    if not cols:
        return
    if "session_id" not in cols:
        try:
            conn.execute(
                "ALTER TABLE daemon_jobs ADD COLUMN session_id TEXT REFERENCES sessions(session_id)"
            )
        except Exception:
            pass


def _ensure_daemon_job_agent_id_column(conn) -> None:
    """Add agent_id if missing (legacy schemas + unit fixtures). Mirrors
    _ensure_daemon_job_session_column above — same no-op-on-absence contract.
    """
    try:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(daemon_jobs)").fetchall()}
    except Exception:
        return
    if not cols:
        return
    if "agent_id" not in cols:
        try:
            conn.execute("ALTER TABLE daemon_jobs ADD COLUMN agent_id TEXT")
        except Exception:
            pass


def _ensure_daemon_job_gh_write_columns(conn) -> None:
    """Add Task 0 gh-write columns for legacy/unit-test daemon schemas."""
    try:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(daemon_jobs)").fetchall()}
    except Exception:
        return
    if not cols:
        return
    definitions = {
        "requires_gh_write": "INTEGER NOT NULL DEFAULT 0",
        "gh_write_target": "TEXT",
        "gh_write_verified": "TEXT",
        "gh_write_author": "TEXT",
        "gh_write_expect": "TEXT DEFAULT 'closed'",
    }
    for name, definition in definitions.items():
        if name not in cols:
            try:
                conn.execute(f"ALTER TABLE daemon_jobs ADD COLUMN {name} {definition}")
            except Exception:
                pass


def _ensure_daemon_job_harness_columns(conn) -> None:
    """Add Phase 4 harness and role columns for legacy/unit-test daemon schemas."""
    try:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(daemon_jobs)").fetchall()}
    except Exception:
        return
    if not cols:
        return
    definitions = {
        "harness": "TEXT",
        "role": "TEXT",
    }
    for name, definition in definitions.items():
        if name not in cols:
            try:
                conn.execute(f"ALTER TABLE daemon_jobs ADD COLUMN {name} {definition}")
            except Exception:
                pass


def _context_mode_hint(context_mode: str, task: str) -> Optional[str]:
    if context_mode != "full":
        return None
    has_code_fence = "```" in task
    has_exact_commit = re.search(r"commit\s+-m|commit message", task, re.IGNORECASE) is not None
    if has_code_fence and has_exact_commit:
        return (
            "[context-mode hint] Task text looks fully self-contained "
            "(includes code + an exact commit message) — full project context "
            "may not be needed. Consider --context-mode task or none to reduce "
            "implementer token usage."
        )
    return None


def _load_harness_overrides(agent: str) -> dict:
    """Read per-project harness overrides from .agents/<agent>.json."""
    empty = {"dispatch_flags": {}, "env": {}, "network_deps": []}
    path = os.path.join(".agents", f"{agent}.json")
    if not os.path.exists(path):
        return empty
    try:
        with open(path) as f:
            data = json.load(f)
        return data.get("harness_overrides") or empty
    except (json.JSONDecodeError, OSError):
        sys.stderr.write(f"Warning: corrupt {path}, ignoring harness overrides\n")
        return empty


def _resolve_github_apps_dir() -> str:
    """Resolve the provisioned GitHub App directory across git worktrees."""
    cwd_apps_dir = os.path.join(".synlynk", "github_apps")
    if os.path.isdir(cwd_apps_dir):
        return cwd_apps_dir

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            check=True,
            capture_output=True,
            text=True,
        )
        git_common_dir = result.stdout.strip()
        if git_common_dir:
            git_common_dir = os.path.abspath(git_common_dir)
            main_repo_apps_dir = os.path.join(
                os.path.dirname(git_common_dir), ".synlynk", "github_apps"
            )
            if os.path.isdir(main_repo_apps_dir):
                return main_repo_apps_dir
    except Exception:
        pass

    return cwd_apps_dir


def _resolve_dispatch_gh_token(role: str) -> Optional[str]:
    """Resolve a role-scoped GitHub App installation token for dispatch.

    Reads the daemon-maintained token cache only — never signs a JWT or calls
    the GitHub API itself (that live-credential action is what triggered
    Claude Code's auto-mode classifier to block dispatch, #1140).
    Falls back to the synlynk-bot catch-all identity if the role has no
    provisioned App. Returns None if neither is provisioned, or if the
    provisioned role's cached token is missing/stale (daemon not running or
    hasn't refreshed yet) — dispatch's caller decides whether that's a
    fail-closed error (--requires-gh-write) or a silent host-auth fallback.
    """
    apps_dir = _resolve_github_apps_dir()
    for candidate_role in (role, "synlynk-bot"):
        json_path = os.path.join(apps_dir, f"{candidate_role}.json")
        if not os.path.exists(json_path):
            continue
        try:
            with open(json_path) as fh:
                app_config = json.load(fh)
        except (OSError, json.JSONDecodeError):
            continue
        if not app_config.get("installation_id"):
            continue
        return read_cached_installation_token(candidate_role, apps_dir)
    return None


def _resolve_dispatch_gh_bot_login(role: str) -> Optional[str]:
    """Resolve a provisioned GitHub App bot login for dispatch.

    Mirrors _resolve_dispatch_gh_token's lookup order, but derives the bot
    login from each App's ``app_slug`` instead of minting a token. Returns
    None if no App is provisioned; it never guesses a login.
    """
    apps_dir = _resolve_github_apps_dir()
    for candidate_role in (role, "synlynk-bot"):
        json_path = os.path.join(apps_dir, f"{candidate_role}.json")
        if not os.path.exists(json_path):
            continue
        try:
            with open(json_path) as fh:
                app_slug = json.load(fh).get("app_slug")
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(app_slug, str) or not app_slug:
            continue
        return app_slug if app_slug.endswith("[bot]") else f"{app_slug}[bot]"
    return None


def _role_for_story(story_id: str) -> Optional[str]:
    """Look up stories.role for a story_id. Returns None if no story_id or no row."""
    if not story_id:
        return None
    get_db = _pkg("_get_db")
    if not get_db:
        return None
    conn = get_db()
    if conn is None:
        return None
    row = conn.execute("SELECT role FROM stories WHERE story_id=?", (story_id,)).fetchone()
    return row[0] if row else None


def _local_concurrency_exceeded(conn, max_concurrent: int = 1) -> bool:
    """True if the 'local' agent already has max_concurrent running jobs."""
    row = conn.execute(
        "SELECT COUNT(*) FROM daemon_jobs WHERE status='running' AND agent='local'"
    ).fetchone()
    running = row[0] if row else 0
    return running >= max_concurrent


def _resolve_dispatch_permissions(
    agent: str,
    role_list: list = None,
    grants: list = None,
    revokes: list = None,
    read_only: bool = False,
) -> list:
    """Compute effective permissions from role defaults, grants, and revokes.

    Review dispatches are allowed to retain read and explicitly requested
    execution capabilities, but never write scopes.  This filter belongs at
    permission resolution so grants cannot bypass the review policy.
    """
    from synlynk._constants import _ROLE_PERMISSION_DEFAULTS

    del agent
    effective = set()
    for role in role_list or []:
        effective.update(_ROLE_PERMISSION_DEFAULTS.get(role, []))
    effective.update(grants or [])
    effective.difference_update(revokes or [])
    if read_only:
        effective = {perm for perm in effective if not perm.startswith("write:")}
    return sorted(effective)


_GROK_PERMISSION_RULES = {
    "read:*": ["Read", "Grep", "Glob", "LS"],
    "write:src/": ["Edit", "Write", "MultiEdit"],
    "write:docs/": ["Edit", "Write", "MultiEdit"],
    "run:tests": ["Bash(pytest:*)"],
    "run:shell": ["Bash"],
}


def _grok_permission_flags(permissions: list) -> list:
    """Translate resolved permission strings into Grok CLI permission flags."""
    permission_set = {perm for perm in (permissions or []) if perm}
    if not permission_set:
        return []

    # Headless Grok auto-cancels compound shell in dontAsk (stopReason: cancelled).
    if "run:shell" in permission_set or "run:tests" in permission_set:
        return ["--always-approve"]

    if set(_GROK_PERMISSION_RULES).issubset(permission_set):
        return ["--always-approve"]

    flags = ["--permission-mode", "dontAsk"]
    allow_rules = []
    has_write = "write:src/" in permission_set or "write:docs/" in permission_set
    has_tests = "run:tests" in permission_set
    has_shell = "run:shell" in permission_set

    for perm in permissions or []:
        rules = _GROK_PERMISSION_RULES.get(perm)
        if not rules:
            continue
        allow_rules.extend(rules)

    if not allow_rules:
        return []

    deny_rules = []
    if not has_write:
        deny_rules.extend(["Edit", "Write", "MultiEdit"])
    if not (has_tests or has_shell):
        deny_rules.append("Bash")

    seen = set()
    for rule in allow_rules:
        if rule not in seen:
            flags.extend(["--allow", rule])
            seen.add(rule)

    seen = set()
    for rule in deny_rules:
        if rule not in seen:
            flags.extend(["--deny", rule])
            seen.add(rule)

    return flags


class PermissionEnforcementError(RuntimeError):
    """Raised when an agent has no real mechanism to enforce requested permissions."""


def _merge_codex_permission_flags(flags: list, permission_flags: list) -> list:
    """Merge Codex permission flags, giving permission-derived sandbox mode precedence."""
    if not any(
        flag in {"-s", "--sandbox"} or flag.startswith("--sandbox=")
        for flag in permission_flags
    ):
        return flags + permission_flags

    merged = []
    index = 0
    while index < len(flags):
        flag = flags[index]
        if flag in {"-s", "--sandbox"}:
            index += 2
            continue
        if flag.startswith("--sandbox="):
            index += 1
            continue
        merged.append(flag)
        index += 1
    return merged + permission_flags


def _permissions_to_flags(agent: str, permissions: list, read_only: bool = False) -> list:
    """Translate permission strings into harness-specific CLI flags."""
    from synlynk._constants import _PERMISSION_TO_TOOL_MAP

    if agent == "agy":
        if not permissions:
            print(
                "  ⚠ agy dispatched with no write/run permissions granted -- "
                "headless mode will auto-deny command/write tool calls and may silently no-op"
            )
            return []
        if set(permissions) <= {"read:*"}:
            return ["--mode", "plan"]
        return ["--dangerously-skip-permissions"]
    if agent == "claude":
        tools = []
        for perm in permissions or []:
            tools.extend(_PERMISSION_TO_TOOL_MAP.get(perm, []))
        tools = sorted(set(tools))
        if not tools:
            return []
        return ["--allowedTools", ",".join(tools)]
    if agent == "codex":
        has_write = any((perm or "").startswith("write:") for perm in (permissions or []))
        flags = []
        if read_only and _CODEX_NETWORK_PERMISSION in (permissions or []):
            # Codex's read-only profile also blocks networking. workspace-write
            # plus an empty writable-roots override provides the required split:
            # network egress without repository working-tree writes.
            flags = ["-s", "workspace-write"]
        elif read_only or (not has_write and _CODEX_NETWORK_PERMISSION not in (permissions or [])):
            flags = ["-s", "read-only"]
        if _CODEX_NETWORK_PERMISSION in (permissions or []):
            flags += _codex_network_flags(read_only=read_only)
        return flags
    if agent == "grok":
        return _grok_permission_flags(permissions)
    if agent == "local":
        if permissions:
            raise PermissionEnforcementError(
                f"local (aider) has no mechanism to enforce permissions {sorted(permissions)}; "
                "aider's declared CLI flags include no read-only/file-scope restriction. Refusing "
                "to dispatch rather than silently granting full read/write access."
            )
        return []
    return []


_ENV_ALLOWLIST_BASE = [
    "PATH",
    "HOME",
    "LANG",
    "LC_ALL",
    "TERM",
    "TMPDIR",
    "USER",
    "SHELL",
    "SSH_AUTH_SOCK",
    "GIT_AUTHOR_NAME",
    "GIT_AUTHOR_EMAIL",
    "GIT_COMMITTER_NAME",
    "GIT_COMMITTER_EMAIL",
    "GIT_SSH_COMMAND",
]


def _gh_write_allow_host_auth() -> bool:
    """Operator opt-in to use host `gh` keyring when no App token is available (#569)."""
    raw = (os.environ.get("SYNLYNK_GH_WRITE_ALLOW_HOST_AUTH") or "").strip().lower()
    return raw in ("1", "true", "yes", "on")


def _isolated_gh_config_dir() -> str:
    """Return a directory for GH_CONFIG_DIR so `gh` cannot use the host keyring session.

    `gh` prefers GH_TOKEN when set, but still consults config under HOME. Pointing
    GH_CONFIG_DIR at an empty synlynk-managed dir isolates host `gh auth login`
    state from the dispatched child (#569).
    """
    path = os.path.join(os.path.expanduser("~/.synlynk"), "gh-config", "dispatch")
    os.makedirs(path, mode=0o700, exist_ok=True)
    return path


def _build_subprocess_env(agent: str, overrides: dict, requires_gh_write: bool, story_id: str, agent_role: str = None) -> dict:
    """Build a minimal, allowlisted environment for a dispatched subprocess.

    Replaces copying the full parent environment: only a fixed base set of
    vars (PATH/HOME/git identity/etc.) plus each agent's declared
    env_passthrough vars are inherited. Everything else the operator's shell
    happens to have set (AWS keys, unrelated API tokens, etc.) is excluded by
    default.

    When ``requires_gh_write`` is set (#569 / Epic B0-B1):
    - Role App token present → inject GH_TOKEN + isolate GH_CONFIG_DIR.
    - Token missing → **fail closed** (raise RuntimeError) unless
      SYNLYNK_GH_WRITE_ALLOW_HOST_AUTH is truthy.
    """
    baseline = HARNESS_CAPABILITY_BASELINES.get(agent, {})
    allowed = set(_ENV_ALLOWLIST_BASE) | set(baseline.get("env_passthrough", []))
    proc_env = {k: v for k, v in os.environ.items() if k in allowed}
    proc_env.update(overrides.get("env", {}))

    for var in baseline.get("headless_contract", {}).get("env_vars_required", []):
        if "=" in var:
            k, v = var.split("=", 1)
            proc_env[k] = v

    if requires_gh_write:
        role = agent_role or _role_for_story(story_id)
        if not role:
            raise RuntimeError(
                "Dispatch refused: --requires-gh-write requires a resolvable role identity "
                "(agent_role or a story-tagged role), but none was provided. Pass --role "
                "<role> to dispatch, or use --as-agent/--story with a role-tagged entry. "
                "Refusing to default to 'dev' for a GitHub-write dispatch (see #423, #569)."
            )
        gh_token = _resolve_dispatch_gh_token(role)
        # Never inherit ambient tokens from the parent shell for GH-write jobs.
        proc_env.pop("GH_TOKEN", None)
        proc_env.pop("GITHUB_TOKEN", None)
        if gh_token:
            proc_env["GH_TOKEN"] = gh_token
            proc_env["GITHUB_TOKEN"] = gh_token
            proc_env["GH_CONFIG_DIR"] = _isolated_gh_config_dir()
        elif _gh_write_allow_host_auth():
            print(
                "  ⚠ --requires-gh-write: no role-scoped GitHub App token; "
                "SYNLYNK_GH_WRITE_ALLOW_HOST_AUTH is set — child may use host `gh` "
                f"keyring under shared personal identity (role={role!r}). "
                "Provision a role App: synlynk identity init --role " + role,
                file=sys.stderr,
            )
        else:
            raise RuntimeError(
                "Dispatch refused: --requires-gh-write requires a role-scoped GitHub App "
                f"token, but none is available for role {role!r} "
                f"(checked .synlynk/github_apps/{role}.json and synlynk-bot.json). "
                f"If the App is provisioned, ensure the token cache is fresh: "
                f"synlynk daemon status  (start it with: synlynk daemon start — "
                f"it refreshes tokens automatically every ~50 min). "
                f"If the App isn't provisioned yet: synlynk identity init --role {role}  "
                "Or set SYNLYNK_GH_WRITE_ALLOW_HOST_AUTH=1 to opt into host `gh` auth "
                "(uses personal keyring — not recommended; see #569)."
            )
    return proc_env


def _spawn_with_pty_fallback(cmd, env, cwd):
    """Try pipe mode first; fall back to PTY if stdout hangs (POSIX only)."""
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            env=env, cwd=cwd)
    try:
        out, _ = proc.communicate(timeout=5)
        if out:
            return proc, out
    except subprocess.TimeoutExpired:
        proc.kill()
    if sys.platform != "win32":
        import pty

        master_fd, slave_fd = pty.openpty()
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=slave_fd,
                stderr=slave_fd,
                env=env,
                cwd=cwd,
                close_fds=True,
            )
            os.close(slave_fd)
            out_chunks = []
            while True:
                r, _, _ = select.select([master_fd], [], [], 5)
                if not r:
                    proc.kill()
                    break
                try:
                    data = os.read(master_fd, 1024)
                    if not data:
                        break
                    out_chunks.append(data)
                except OSError:
                    break
            proc.wait(timeout=5)
            return proc, b"".join(out_chunks)
        finally:
            try:
                os.close(master_fd)
            except OSError:
                pass
    return None, b""


def _is_interactive(cmd_args: list) -> bool:
    """Returns True if the command needs a real TTY (no stdout capture)."""
    non_interactive = ["--no-tty", "--output-format json", "--print", "--non-interactive", "-p "]
    cmd_str = " ".join(cmd_args)
    return not any(flag in cmd_str for flag in non_interactive)


def _dispatch_context() -> str:
    """Return whether this dispatch was initiated from an operator TTY."""
    try:
        return "home" if sys.stdin.isatty() else "headless"
    except (AttributeError, OSError, ValueError):
        # stdin may be closed or replaced with an object without a usable fd
        # when dispatch is invoked from a daemon, CI, or another process.
        return "headless"


def _inject_grok_rules(cmd_args: list) -> list:
    """Adds Grok rules flags when invoking grok and the rule files exist."""
    if not cmd_args or cmd_args[0] != "grok":
        return list(cmd_args)

    injected = [cmd_args[0]]
    if os.path.exists("GROK.md"):
        injected.extend(["--rules", "GROK.md"])
    if "-p" in cmd_args and os.path.exists(os.path.join(".synlynk", "context.md")):
        injected.extend(["--rules", os.path.join(".synlynk", "context.md")])
    injected.extend(cmd_args[1:])
    return injected


def _tee_process(process, buffer: list, meta: Optional[dict] = None) -> None:
    """Reads process stdout line-by-line, writes to terminal and appends to buffer."""
    for line in iter(process.stdout.readline, b""):
        if meta is not None:
            meta["output_bytes"] = meta.get("output_bytes", 0) + len(line)
            if not meta.get("first_output_at") and line.strip():
                meta["first_output_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        sys.stdout.buffer.write(line)
        sys.stdout.buffer.flush()
        buffer.append(line.decode("utf-8", errors="replace"))
    process.stdout.close()


def _check_pre_exec_gate(force: bool = False) -> bool:
    """Checks for active sentinel alerts. Returns False to abort if CRITICAL and not forced."""
    warns = _read_sentinel_alerts(severity="WARN")
    criticals = _read_sentinel_alerts(severity="CRITICAL")
    for w in warns:
        print(f"  ⚠ {w}")
    if criticals:
        for c in criticals:
            print(f"  🚨 {c}")
        if not force:
            print("  Exec blocked by CRITICAL sentinel alert. "
                  "Fix the issue or re-run with --force to bypass.")
            return False
    return True


def _check_job_stall(job: dict, config: dict, sentinel_path: str) -> bool:
    """Returns True if job was stalled and killed."""
    if job.get("status") != "running":
        return False
    log_file = job.get("log_file", "")
    if not log_file or not os.path.exists(log_file):
        return False

    agent = job.get("agent", "")
    global_timeout = config.get("stall_timeout_minutes", 30)
    if job.get("task_type") == "review":
        timeout = config.get("review_stall_timeout_minutes", 90)
    else:
        timeout = config.get("agents", {}).get(agent, {}).get("stall_timeout_minutes", global_timeout)

    stale_minutes = (time.time() - os.path.getmtime(log_file)) / 60
    if stale_minutes < timeout:
        return False

    if job.get("requires_gh_write"):
        target = job.get("gh_write_target")
        expect = job.get("gh_write_expect") or "closed"
        verified = gh_write_verified(
            target,
            expect=expect,
            since=job.get("started_at"),
            expect_author=job.get("gh_write_author"),
        )
        job["gh_write_verified"] = (
            "true" if verified is True else ("false" if verified is False else "unknown")
        )
        if verified is True:
            print(
                f"  Stall check extended for job {job.get('id')}: gh-write target {target} "
                "verified delivered (ground truth)."
            )
            return False
        if verified is False:
            pid = job.get("pid")
            if pid:
                try:
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            job["status"] = "failed"
            job["exit_code"] = -1
            job["ended_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            write_alert = _pkg("_write_sentinel_alert", _write_sentinel_alert)
            write_alert(
                "CRITICAL", "STALL_GH_WRITE_UNVERIFIED",
                f"Job {job.get('id')} on agent '{job.get('agent', '')}' stalled and its "
                f"declared gh-write target {target} was confirmed NOT delivered. Process killed.",
                sentinel_path,
            )
            return True

    inspect_worktree_git_state = _pkg("_inspect_worktree_git_state")
    git_state = (
        inspect_worktree_git_state(
            job.get("worktree_path"),
            job.get("worktree_branch"),
            job.get("started_at"),
        )
        if inspect_worktree_git_state
        else None
    )
    if git_state and git_state.get("has_activity"):
        worktree_path = job.get("worktree_path")
        commit_count = git_state.get("commits_ahead", 0)
        dirty = git_state.get("dirty", False)
        parts = []
        if commit_count:
            parts.append(f"{commit_count} commit(s)")
        if dirty:
            parts.append("uncommitted changes")
        details = " and ".join(parts) if parts else "git activity"
        print(
            f"  Stall check extended for job {job.get('id')}: git activity detected in "
            f"{worktree_path} ({details})."
        )
        return False
    if git_state and git_state.get("remote_has_activity"):
        remote_ref = git_state.get("remote_ref")
        remote_commit_count = git_state.get("remote_commit_count", 0)
        print(
            f"  Stall check extended for job {job.get('id')}: remote activity detected on "
            f"{remote_ref} ({remote_commit_count} commit(s) since {job.get('started_at')})."
        )
        return False

    pid = job.get("pid")
    if pid:
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass

    job["status"] = "failed"
    job["exit_code"] = -1
    job["ended_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")

    write_alert = _pkg("_write_sentinel_alert", _write_sentinel_alert)
    write_alert(
        "CRITICAL", "STALL_NO_OUTPUT",
        f"Job {job.get('id')} on agent '{agent}' stalled with zero output after {timeout}min. Process killed.",
        sentinel_path,
    )
    write_alert(
        "WARN", "HANDOFF_PENDING",
        f"Job {job.get('id')} on agent '{agent}' is awaiting handoff to another agent.",
        sentinel_path,
    )
    return True


def _resolve_worktree_base_commit(worktree_path: Optional[str]) -> Optional[dict]:
    """Find the merge-base used to compare a worktree against mainline refs."""
    if not _worktree_path_is_available(worktree_path, "resolve base commit"):
        return None

    for ref in ("origin/main", "origin/master", "main", "master"):
        try:
            base_result = subprocess.run(
                ["git", "-C", worktree_path, "merge-base", "HEAD", ref],
                capture_output=True,
                text=True,
                check=False,
            )
        except Exception:
            continue

        base_commit = (base_result.stdout or "").strip()
        if base_result.returncode != 0 or not base_commit:
            continue

        return {"base_commit": base_commit, "base_ref": ref}

    return None


def _worktree_files_touched(worktree_path: Optional[str]) -> list:
    """Return sorted file paths committed in a worktree since the resolved merge-base."""
    if not _worktree_path_is_available(worktree_path, "collect touched files"):
        return []

    inspect_worktree_git_state = _pkg("_inspect_worktree_git_state")
    git_state = inspect_worktree_git_state(worktree_path) if inspect_worktree_git_state else None
    base_commit = (git_state or {}).get("base_commit") or (
        _resolve_worktree_base_commit(worktree_path) or {}
    ).get("base_commit")
    if not base_commit:
        return []

    touched = set()

    try:
        diff_result = subprocess.run(
            ["git", "-C", worktree_path, "diff", "--name-only", base_commit, "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        diff_result = None

    if diff_result and diff_result.returncode == 0:
        for path in (diff_result.stdout or "").splitlines():
            path = path.strip()
            if path:
                touched.add(path)

    return sorted(touched)


def _run_dispatch_gate(job: dict, gate_suite_cmd: str) -> Optional[dict]:
    """Runs the configured test-suite command inside a job's worktree.

    Returns {"passed": int, "failed": int, "skipped": int} parsed from the
    command's combined output, or None if no gate command is configured or
    the worktree is unavailable.
    """
    if not gate_suite_cmd:
        return None
    worktree_path = job.get("worktree_path")
    if not _worktree_path_is_available(worktree_path, "run dispatch gate"):
        return None

    try:
        result = subprocess.run(
            gate_suite_cmd,
            shell=True,
            cwd=worktree_path,
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        return None

    combined = (result.stdout or "") + "\n" + (result.stderr or "")

    def _count(pattern: str) -> int:
        match = re.search(pattern, combined)
        return int(match.group(1)) if match else 0

    return {
        "passed": _count(r"(\d+)\s+passed"),
        "failed": _count(r"(\d+)\s+failed"),
        "skipped": _count(r"(\d+)\s+skipped"),
    }


def _check_dispatch_base_still_fresh(job: dict, repo_path: Optional[str] = None) -> bool:
    """Returns False if job base_branch has moved past job base_sha since dispatch.

    True (fresh) when no base was recorded (legacy jobs, or stacking: never).
    """
    base_branch = job.get("base_branch")
    base_sha = job.get("base_sha")
    if not base_branch or not base_sha:
        return True

    repo_path = repo_path or os.getcwd()
    try:
        tip_result = subprocess.run(
            ["git", "-C", repo_path, "rev-parse", base_branch],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except Exception:
        return True

    current_tip = (tip_result.stdout or "").strip()
    if tip_result.returncode != 0 or not current_tip:
        return True

    return current_tip == base_sha


def _render_dispatch_preview(agent: str, task: str, context_mode: str,
                              agent_id: str = None, story_id: str = None,
                              force_agent: bool = False, requires_gh_write: bool = False,
                              static_baseline: bool = False,
                              task_type: str = None) -> dict:
    """Compute task/context digest data for dispatch inspection."""
    requires_gh_write = bool(
        requires_gh_write or _task_requires_gh_write(task, task_type=task_type)
    )
    agent = resolve_dispatch_harness(
        agent, agent_id=agent_id, story_id=story_id,
        force_agent=force_agent, requires_gh_write=requires_gh_write,
        static_baseline=static_baseline,
    )
    task_sha256 = hashlib.sha256(task.encode("utf-8")).hexdigest()
    context_digest = None
    context_bytes = None
    if context_mode != "none":
        context_path = os.path.join(".synlynk", "context.md")
        if os.path.exists(context_path):
            try:
                with open(context_path, "rb") as f:
                    content = f.read()
                context_digest = hashlib.sha256(content).hexdigest()
                context_bytes = len(content)
            except OSError:
                pass
    return {
        "agent": agent,
        "task": task,
        "task_len": len(task),
        "task_sha256": task_sha256,
        "context_mode": context_mode,
        "context_digest": context_digest,
        "context_bytes": context_bytes,
        "requires_gh_write": requires_gh_write,
    }


_GH_CLI_WRITE_RE = re.compile(
    r"\bgh\s+(?:issue|pr|release)\s+(?:create|review|comment|close|merge|edit|reopen|delete)\b",
    re.IGNORECASE,
)

_GH_ACTION_TARGET_RE = re.compile(
    r"(?:"
    r"\b(?:review|approv(?:e|ing))\s+(?:(?:the|this)\s+)?(?:github\s+)?(?:pr|pull\s+request)\s*#?\d+\b|"
    r"\b(?:post|submit|add)\s+(?:(?:a|an)\s+)?(?:formal\s+)?(?:github\s+)?(?:pr\s+|pull\s+request\s+)?review\b|"
    r"\b(?:do|conduct|perform)\s+(?:a\s+)?(?:code\s+)?review\s+of\s+(?:github\s+)?(?:pr|pull\s+request)\s*#?\d+\b|"
    r"\b(?:pr|pull\s+request)\s+review\s+(?:for|on|of)\s+(?:pr|pull\s+request)?\s*#?\d+\b|"
    r"\breview\s+and\s+post\b|"
    r"\bclose\s+(?:(?:the|this|all)\s+)?(?:github\s+)?(?:issues?|prs?|pull\s+requests?)\s*#?\d+\b|"
    r"\bclose\s+(?:(?:the|this|all)\s+)?(?:github\s+)?(?:issues?|prs?|pull\s+requests?)\s+(?:as|citing)\b|"
    r"\bmerge\s+(?:(?:the|this)\s+)?(?:github\s+)?(?:pr|pull\s+request)\s*#?\d+\b|"
    r"\bmerge\s+(?:(?:the|this)\s+)?(?:pr|pull\s+request)\s+via\b|"
    r"\bcomment\s+on\s+(?:(?:the|this)\s+)?(?:github\s+)?(?:issues?|prs?|pull\s+requests?)\s*#?\d+\b|"
    r"\bpost\s+(?:(?:a|an)\s+)?(?:comment|response)\s+(?:on|to)\s+(?:(?:the|this)\s+)?(?:github\s+)?(?:issues?|prs?|pull\s+requests?)\s*#?\d+\b|"
    r"\b(?:create|open)\s+(?:(?:a|an)\s+)?(?:new\s+)?(?:github\s+)?(?:pr|pull\s+request)\b"
    r")",
    re.IGNORECASE,
)

_REVIEW_TASK_RE = re.compile(
    r"(?:"
    r"\breview\s+and\s+post\b|"
    r"\bpost(?:\s+(?:a|an))?\s+(?:github\s+)?(?:pr|pull\s+request)\s+review\b|"
    r"\bpost(?:\s+(?:a|an))?\s+review\b|"
    r"\b(?:pr|pull\s+request)\s+review\b|"
    r"\bcode\s+review\s+of\s+(?:github\s+)?(?:pr|pull\s+request)\b|"
    r"\breview\s+(?:github\s+)?(?:pr|pull\s+request)\s*#?\d+\b"
    r")",
    re.IGNORECASE,
)

_PR_OPEN_TASK_RE = re.compile(
    r"\b(?:gh\s+pr\s+create|(?:create|open)\s+(?:(?:a|an)\s+)?(?:new\s+)?(?:github\s+)?(?:pr|pull\s+request))\b",
    re.IGNORECASE,
)


def _task_opens_pr(task: str) -> bool:
    return bool(_PR_OPEN_TASK_RE.search(task or ""))


def _gh_write_expectation(task: str, task_type: str = None) -> str:
    """Return the delivery effect expected from a GitHub-writing task."""
    if task_type == "review" or _REVIEW_TASK_RE.search(task or ""):
        return "review_posted"
    if _task_opens_pr(task):
        return "pr_open"
    text = task or ""
    if re.search(r"\b(?:gh\s+)?pr\s+merge\b|\bmerge\s+(?:the\s+)?(?:github\s+)?(?:pr|pull\s+request)\b", text, re.IGNORECASE):
        return "merged"
    if re.search(r"\b(?:gh\s+)?(?:pr|issue)\s+comment\b|\b(?:comment|post\s+(?:a\s+)?comment)\s+(?:on|to)\b", text, re.IGNORECASE):
        return "comment_posted"
    if re.search(r"\b(?:gh\s+)?(?:pr|issue)\s+(?:close|reopen)\b|\bclose\s+", text, re.IGNORECASE):
        return "closed"
    # Preserve the historical contract for explicitly targeted legacy writes.
    return "closed"


def _task_requires_gh_write(task: str, task_type: str = None) -> bool:
    """Infer GitHub-write intent so operators do not have to remember a flag.

    The explicit ``--requires-gh-write`` flag remains the override. This detector
    checks for explicit ``gh`` CLI write invocations or tight co-occurrence of
    GitHub write actions directly paired with target objects (PRs/issues), preventing
    false positives on file paths, tracking issue mentions, and non-action prose.
    """
    text = task or ""
    if _GH_CLI_WRITE_RE.search(text):
        return True
    return bool(_GH_ACTION_TARGET_RE.search(text))


def _infer_task_type(task: str) -> Optional[str]:
    """Infer only an unambiguous PR review task type from task text."""
    text = task or ""
    if _REVIEW_TASK_RE.search(text):
        return "review"
    return None


def _job_summary_path(job_id: str) -> str:
    return os.path.join(".synlynk/logs", f"{job_id}.summary")


def _summary_status_label(summary_text: str) -> Optional[str]:
    match = re.search(r"^status:\s+(.*)$", summary_text, re.MULTILINE)
    if not match:
        return None
    return match.group(1).strip()


def _summary_files_touched_count(summary_text: str) -> Optional[int]:
    match = re.search(r"^files:\s+(\d+)\s+touched$", summary_text, re.MULTILINE)
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


_GITHUB_MCP_CANCELLATION_MARKERS = (
    '"message":"user cancelled MCP tool call"',
    "GitHub review submission was cancelled by the connector again;",
)


def _has_github_mcp_cancellation(log_text: Optional[str]) -> bool:
    """Return whether a job log records a cancelled GitHub MCP write.

    The connector's JSON error is the primary marker.  The agent-emitted
    summary phrase is retained as a fallback for logs where the structured
    MCP event is abbreviated or omitted.
    """
    return bool(log_text) and any(marker in log_text for marker in _GITHUB_MCP_CANCELLATION_MARKERS)


def _format_job_summary(job_id: str, agent: str, story_id: Optional[str],
                        exit_code: Optional[int], duration_s: Optional[float],
                        in_tokens: int, out_tokens: int, cost_usd: float,
                        files_touched: Optional[list] = None,
                        worktree_path: Optional[str] = None,
                        worktree_branch: Optional[str] = None,
                        status_label: Optional[str] = None,
                        note: Optional[str] = None,
                        base_branch: Optional[str] = None,
                        base_sha: Optional[str] = None,
                        suite_result: Optional[dict] = None,
                        task_sha256: Optional[str] = None,
                        task_preview: Optional[str] = None,
                        log_text: Optional[str] = None) -> str:
    """Formats the structured completion summary for a finished job."""
    files_touched = sorted(set(files_touched or []))
    story_label = story_id or "-"
    exit_code = -1 if exit_code is None else exit_code
    status_label = status_label or ("OK (exit 0)" if exit_code == 0 else f"FAILED (exit {exit_code})")
    if exit_code == 0 and _has_github_mcp_cancellation(log_text):
        status_label = f"{status_label} — GH WRITE CANCELLED"
    duration_label = f"{duration_s:.1f}s" if duration_s is not None else "?s"
    worktree_line = ""
    note_line = f"note:     {note}\n" if note else ""
    task_line = f"task:     {task_preview}\n" if task_preview else ""
    task_sha_line = f"task_sha256: {task_sha256}\n" if task_sha256 else ""
    base_line = ""
    if base_branch:
        sha_label = f" @ {base_sha[:8]}" if base_sha else ""
        base_line = f"base:     {base_branch}{sha_label}\n"
    suite_line = ""
    if suite_result:
        suite_line = (
            f"suite:    {suite_result.get('passed', 0)} passed, "
            f"{suite_result.get('failed', 0)} failed, "
            f"{suite_result.get('skipped', 0)} skipped\n"
        )
    if worktree_path:
        branch_note = f" (branch: {worktree_branch})" if worktree_branch else ""
        worktree_line = f"worktree: {worktree_path}{branch_note}\n"
    files_line = f"files:    {len(files_touched)} touched\n"
    if files_touched:
        visible_files = files_touched[:20]
        rendered_files = "".join(f"          {path}\n" for path in visible_files)
        more_count = len(files_touched) - len(visible_files)
        if more_count > 0:
            rendered_files += f"          +{more_count} more\n"
        files_line += rendered_files
    load_config_fn = _pkg("load_config")
    config = load_config_fn() if load_config_fn else {}
    if is_fenced_command("jobs", config):
        fence = FenceData(
            command="jobs",
            kind="actual",
            in_tokens=in_tokens,
            out_tokens=out_tokens,
            cost_usd=cost_usd,
            basis="structured_output",
            hints=["Run \"synlynk watch\" for a live overview"],
            label=job_id,
        )
        return (
            f"-- job {job_id} complete ---------\n"
            f"agent:    {agent}   story: {story_label}\n"
            f"status:   {status_label}\n"
            f"{note_line}"
            f"{base_line}"
            f"{suite_line}"
            f"duration: {duration_label}\n"
            f"{render_task_fence(fence)}"
            f"{worktree_line}"
            f"{files_line}"
            f"{task_line}"
            f"{task_sha_line}"
            f"---------------------------------\n"
        )
    return (
        f"-- job {job_id} complete ---------\n"
        f"agent:    {agent}   story: {story_label}\n"
        f"status:   {status_label}\n"
        f"{note_line}"
        f"{base_line}"
        f"{suite_line}"
        f"duration: {duration_label}\n"
        f"tokens:   in {in_tokens:,}  out {out_tokens:,}  (~${cost_usd:.2f})\n"
        f"{worktree_line}"
        f"{files_line}"
        f"{task_line}"
        f"{task_sha_line}"
        f"---------------------------------\n"
    )


def _write_job_summary(job_id: str, agent: str, story_id: Optional[str],
                       exit_code: Optional[int], duration_s: Optional[float],
                       in_tokens: int, out_tokens: int, cost_usd: float,
                       files_touched: Optional[list],
                       worktree_path: Optional[str] = None,
                       worktree_branch: Optional[str] = None,
                       status_label: Optional[str] = None,
                       note: Optional[str] = None,
                       base_branch: Optional[str] = None,
                       base_sha: Optional[str] = None,
                       suite_result: Optional[dict] = None,
                       task_sha256: Optional[str] = None,
                       task_preview: Optional[str] = None,
                       log_text: Optional[str] = None) -> str:
    """Writes a structured completion summary for a job and returns the text."""
    os.makedirs(".synlynk/logs", exist_ok=True)
    summary = _format_job_summary(
        job_id, agent, story_id, exit_code, duration_s, in_tokens, out_tokens,
        cost_usd, files_touched, worktree_path=worktree_path, worktree_branch=worktree_branch,
        status_label=status_label, note=note, base_branch=base_branch, base_sha=base_sha,
        suite_result=suite_result, task_sha256=task_sha256, task_preview=task_preview,
        log_text=log_text,
    )
    summary_path = _job_summary_path(job_id)
    existing_summary = None
    if os.path.exists(summary_path):
        try:
            with open(summary_path) as f:
                existing_summary = f.read()
        except OSError:
            existing_summary = None
    existing_status = _summary_status_label(existing_summary) if existing_summary else None
    existing_files_touched = _summary_files_touched_count(existing_summary) if existing_summary else None
    new_status = _summary_status_label(summary)
    # Do not downgrade a verified OK summary with an ambiguous race rewrite
    # (FAILED_UNVERIFIED / UNKNOWN / fabricated timed_out exit -9 from #753 reconcile).
    if existing_status == "OK (exit 0)" and new_status:
        if (
            new_status.startswith("FAILED")
            or new_status.startswith("FAILED_UNVERIFIED")
            or new_status == "UNKNOWN (exit unknown)"
            or "timed_out" in new_status.lower()
        ):
            return existing_summary
    if (
        existing_summary
        and existing_files_touched
        and not (files_touched or [])
        and exit_code in (None, -1, -9)
        and existing_status
        and re.match(r"^(?:OK|FAILED)\s+\(exit\s+-?\d+\)$", existing_status)
    ):
        return existing_summary
    with open(summary_path, "w") as f:
        f.write(summary)
    return summary


def _render_task_receipt_instruction(task_sha256: Optional[str]) -> str:
    """Returns a prompt-prepend block instructing the agent to echo the
    task digest as its literal first output line (see #720 receipt protocol)."""
    if not task_sha256:
        return ""
    return (
        "## Task Receipt (required)\n"
        "Before doing anything else, print this exact line as your very "
        "first output:\n"
        f"SYNLYNK_TASK_RECEIVED: {task_sha256}\n"
        "Then proceed with the task below.\n\n"
    )


def _render_instruction_receipt_instruction(instruction_file: Optional[str]) -> str:
    """Returns a prompt-prepend block instructing the agent to confirm that
    its project instruction file was loaded by echoing its version tag
    (see #347 instruction-receipt protocol)."""
    if not instruction_file:
        return ""
    return (
        "## Instruction Receipt (required)\n"
        f"Confirm that your project instruction file ({instruction_file}) is loaded.\n"
        "Print this exact line as your second output line (immediately after SYNLYNK_TASK_RECEIVED if present):\n"
        "SYNLYNK_INSTRUCTION_VERSION: <version>\n"
        "where <version> is the version string from your instruction file (e.g. from `synlynk:start version=\"...\"` or `synlynk:harness ...`).\n"
        "If no instruction file is loaded, print:\n"
        "SYNLYNK_INSTRUCTION_VERSION: none\n\n"
    )


def _format_prompt_for_agent(agent: str, context_text: str, story_id: str,
                              task: str, file_section: str, verify_section: str,
                              cwd_hint: Optional[str] = None,
                              task_sha256: Optional[str] = None,
                              instruction_file: Optional[str] = None,
                              *, requires_gh_write: bool = False) -> str:
    """Returns a prompt formatted for the agent's preferred input style."""
    requires_gh_write = bool(
        requires_gh_write or _task_requires_gh_write(task)
    )
    receipt_instruction = _render_task_receipt_instruction(task_sha256)
    instruction_receipt = _render_instruction_receipt_instruction(instruction_file)
    headers = f"{receipt_instruction}{instruction_receipt}"
    story_ref = f"\n\n## Story / Task Reference\nStory ID: {story_id}" if story_id else ""
    gh_write_instruction = ""
    if requires_gh_write:
        gh_write_instruction = (
            "## GitHub Write Instructions (MANDATORY)\n"
            "This task requires a real GitHub write. You MUST use the `gh` CLI "
            "directly through the shell for every write: `gh pr review`, `gh pr "
            "comment`, `gh pr merge`, `gh issue comment`, or `gh issue close`. "
            "Do not use MCP GitHub tools for these writes. NEVER call the MCP "
            "GitHub write tool `close_issue` or any similar `github_*` write "
            "tool. MCP writes are structurally unreliable "
            "in dispatched sessions and have caused confirmed silent cancellations. "
            "After running `gh`, verify its exit status and report the result.\n\n"
        )
    if agent == "codex":
        sentences = [s.strip() for s in re.split(r"[.!?]", task) if s.strip()]
        criteria = "\n".join(f"- {s}" for s in sentences) if sentences else f"- {task}"
        return (
            f"{headers}"
            f"{gh_write_instruction}"
            f"## Task Criteria\n{criteria}\n"
            f"{file_section}\n"
            f"{verify_section}\n"
            f"## Context\n{context_text}"
            f"{story_ref}\n"
        )
    if agent == "agy":
        working_dir = cwd_hint or os.getcwd()
        stitch_hint = ""
        if "stitch" in (task or "").lower() or "mcp__stitch" in (task or "").lower():
            stitch_hint = (
                "## Stitch MCP Tool Usage Note\n"
                "On Agy, Stitch MCP tools are invoked via the built-in meta-tool:\n"
                "`call_mcp_tool(server=\"stitch\", tool=\"<tool_name>\", arguments={...})`\n"
                "Do not call `mcp__stitch__<tool_name>` directly.\n\n"
            )
        return (
            f"{headers}"
            f"{gh_write_instruction}"
            f"{stitch_hint}"
            f"## Working Directory\n{working_dir}\n"
            f"All file edits MUST be in this directory.\n\n"
            f"Task: {task}\n"
            f"{story_ref}\n"
            f"{file_section}\n"
            f"{verify_section}\n"
            f"Context summary:\n{context_text}"
        )
    if agent == "grok":
        working_dir = cwd_hint or os.getcwd()
        return (
            f"{headers}"
            f"{gh_write_instruction}"
            f"## Working Directory\n{working_dir}\n"
            f"All file edits MUST be in this directory.\n\n"
            f"{context_text}"
            f"{story_ref}"
            f"{file_section}"
            f"\n\n## Your Task\n{task}"
            f"{verify_section}\n"
        )
    return (
        f"{headers}"
        f"{gh_write_instruction}"
        f"{context_text}"
        f"{story_ref}"
        f"{file_section}"
        f"\n\n## Your Task\n{task}"
        f"{verify_section}\n"
    )


_CONTEXT_WARN_BYTES = 81920


def _warn_context_size(context_text: str) -> None:
    size = len(context_text.encode("utf-8"))
    if size > _CONTEXT_WARN_BYTES:
        print(f"  ⚠ context: full ({size // 1024}KB) — exceeds soft limit "
              f"({_CONTEXT_WARN_BYTES // 1024}KB)")
        print("    Use --context-mode task to reduce size")


def _worktree_path_is_available(worktree_path: Optional[str], operation: str) -> bool:
    """Check a persisted worktree path and explain silent-path failures."""
    if not worktree_path:
        return False
    if os.path.isdir(worktree_path):
        return True
    if os.path.isabs(worktree_path):
        reason = "the absolute path does not exist"
    else:
        reason = (
            "the stored path is relative and cannot be resolved from the current CWD; "
            "the worktree may exist elsewhere"
        )
    print(
        f"  ⚠ worktree unavailable while trying to {operation}: {worktree_path} ({reason})",
        file=sys.stderr,
    )
    return False


def _job_worktree_details(job_id: str, agent: str) -> Tuple[str, str]:
    """Returns the per-job worktree path and branch name."""
    worktree_path = os.path.abspath(os.path.join("worktrees", job_id))
    worktree_branch = f"dispatch/{agent}/{job_id}"
    return worktree_path, worktree_branch


def _git_ref_exists(repo_path: str, ref: str) -> bool:
    try:
        result = subprocess.run(
            ["git", "-C", repo_path, "rev-parse", "--verify", f"{ref}^{{commit}}"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except Exception:
        return False
    return result.returncode == 0 and bool((result.stdout or "").strip())


def _fetch_origin_branch(repo_path: str, branch: str) -> bool:
    """Best-effort `git fetch origin <branch>`. Returns True if fetch exit 0."""
    try:
        result = subprocess.run(
            ["git", "fetch", "origin", branch],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=repo_path,
        )
    except Exception:
        return False
    return result.returncode == 0


def _resolve_explicit_base_ref(repo_path: Optional[str], explicit_base: str) -> str:
    """Resolve ``--base`` to a fresh tip (#832).

    Bare branch names (e.g. ``main``) previously returned as-is and were
    ``rev-parse``'d against the **local** ref, which can lag ``origin/main``.
    Prefer ``origin/<branch>`` after a fetch when available.
    """
    base = (explicit_base or "").strip()
    if not base:
        return "HEAD"
    # Full commit SHA — use as-is.
    if re.fullmatch(r"[0-9a-fA-F]{7,40}", base):
        return base

    path = repo_path if repo_path and os.path.isdir(repo_path) else os.getcwd()

    # Already a remote-tracking ref: freshen then use.
    if base.startswith("origin/"):
        branch = base[len("origin/") :]
        if branch:
            _fetch_origin_branch(path, branch)
        return base

    # Other remote forms (upstream/foo) — leave alone after optional fetch of suffix.
    if "/" in base and not base.startswith("."):
        return base

    # Bare branch name: fetch origin/<name> and prefer it.
    fetched = _fetch_origin_branch(path, base)
    remote_ref = f"origin/{base}"
    if _git_ref_exists(path, remote_ref):
        if _git_ref_exists(path, base):
            try:
                local_sha = subprocess.run(
                    ["git", "-C", path, "rev-parse", base],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                remote_sha = subprocess.run(
                    ["git", "-C", path, "rev-parse", remote_ref],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                l = (local_sha.stdout or "").strip()
                r = (remote_sha.stdout or "").strip()
                if l and r and l != r:
                    print(
                        f"  ⚠ worktree base: local '{base}' ({l[:8]}) differs from "
                        f"{remote_ref} ({r[:8]}) — using remote tip (#832)"
                    )
            except Exception:
                pass
        if not fetched:
            print(
                f"  ⚠ worktree base: fetch origin {base} failed; using existing {remote_ref}"
            )
        return remote_ref

    if _git_ref_exists(path, base):
        print(
            f"  ⚠ worktree base: origin/{base} unavailable — using local '{base}' "
            f"(may be stale if remotes exist)"
        )
        return base

    # Unknown ref — return as given so rev-parse / worktree add fails loudly.
    return base


def _resolve_dispatch_worktree_base_ref(
    repo_path: Optional[str],
    stacking_mode: str = "auto",
    explicit_base: Optional[str] = None,
) -> str:
    """Resolve the base ref a new dispatch worktree should be anchored to.

    stacking_mode: "auto" (stack on current non-mainline branch, else mainline),
    "always" (stack on current branch, error on mainline/detached HEAD),
    "never" (always mainline — legacy behavior)

    ``explicit_base`` (``--base``) is freshened via :func:`_resolve_explicit_base_ref`
    so ``--base main`` tracks ``origin/main`` after fetch (#832).
    """
    if explicit_base:
        return _resolve_explicit_base_ref(repo_path, explicit_base)

    if not repo_path or not os.path.isdir(repo_path):
        return "HEAD"

    if stacking_mode != "never":
        try:
            branch_result = subprocess.run(
                ["git", "-C", repo_path, "branch", "--show-current"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except Exception:
            branch_result = None
        current_branch = (
            (branch_result.stdout or "").strip()
            if branch_result and branch_result.returncode == 0
            else ""
        )
        if current_branch and current_branch not in ("main", "master"):
            return current_branch
        if stacking_mode == "always":
            raise RuntimeError(
                f"dispatch stacking is 'always' but current branch is "
                f"'{current_branch or '(detached HEAD)'}' — refusing to stack on mainline"
            )

    for candidate in ("main", "master"):
        if _fetch_origin_branch(repo_path, candidate) and _git_ref_exists(
            repo_path, f"origin/{candidate}"
        ):
            return f"origin/{candidate}"

    for candidate in ("origin/main", "origin/master", "main", "master"):
        if _git_ref_exists(repo_path, candidate):
            return candidate

    return "HEAD"


def _assert_dispatch_worktree_base_is_fresh(worktree_path: str, base_ref: str) -> None:
    """Fail loudly if a new worktree is not anchored to the intended mainline tip."""
    if not worktree_path or not base_ref or base_ref == "HEAD":
        return

    try:
        ref_result = subprocess.run(
            ["git", "-C", worktree_path, "rev-parse", base_ref],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        merge_base_result = subprocess.run(
            ["git", "-C", worktree_path, "merge-base", "HEAD", base_ref],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
    except Exception as exc:
        raise RuntimeError(
            f"Failed to verify worktree base for {worktree_path} against {base_ref}: {exc}"
        ) from exc

    ref_commit = (ref_result.stdout or "").strip()
    merge_base = (merge_base_result.stdout or "").strip()
    if (
        ref_result.returncode != 0
        or merge_base_result.returncode != 0
        or not ref_commit
        or not merge_base
        or ref_commit != merge_base
    ):
        raise RuntimeError(
            f"Worktree {worktree_path} is not anchored to fresh {base_ref} "
            f"(expected {ref_commit or 'unknown'}, merge-base {merge_base or 'unknown'})."
        )

    print(f"  worktree base verified against {base_ref} @ {ref_commit}")


def _preflight_auth_check(harness_name: str, auth_check: dict) -> Optional[dict]:
    """Run a lightweight auth probe and fail when it reports an unauthenticated state."""
    if not auth_check:
        return None

    probe_cmd = auth_check.get("probe")
    if not probe_cmd:
        return None

    probe_exe = probe_cmd[0] if isinstance(probe_cmd, (list, tuple)) and probe_cmd else None
    if not probe_exe or shutil.which(probe_exe) is None:
        return None

    required_paths = [
        os.path.expanduser(path)
        for path in auth_check.get("required_paths", [])
        if path
    ]
    missing_paths = [path for path in required_paths if not os.path.exists(path)]
    if missing_paths:
        return {
            "passed": False,
            "sentinel": "HARNESS_PREFLIGHT_FAIL",
            "reason": (
                f"Harness '{harness_name}' auth preflight failed: missing required auth state "
                f"file(s) {', '.join(missing_paths)}. Re-authenticate before dispatch."
            ),
        }

    try:
        probe_result = subprocess.run(
            probe_cmd,
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
    except FileNotFoundError:
        return {
            "passed": False,
            "sentinel": "HARNESS_PREFLIGHT_FAIL",
            "reason": (
                f"Harness '{harness_name}' auth preflight failed: probe command "
                f"{' '.join(probe_cmd)!r} is unavailable."
            ),
        }
    except subprocess.TimeoutExpired:
        return {
            "passed": False,
            "sentinel": "HARNESS_PREFLIGHT_FAIL",
            "reason": (
                f"Harness '{harness_name}' auth preflight failed: probe command "
                f"{' '.join(probe_cmd)!r} timed out."
            ),
        }

    auth_text = "\n".join(
        part for part in [probe_result.stdout or "", probe_result.stderr or ""] if part
    ).lower()
    markers = [marker.lower() for marker in auth_check.get("unauthenticated_markers", []) if marker]
    if markers and any(marker in auth_text for marker in markers):
        return {
            "passed": False,
            "sentinel": "HARNESS_PREFLIGHT_FAIL",
            "reason": (
                f"Harness '{harness_name}' is not authenticated: "
                f"{(probe_result.stderr or probe_result.stdout or 'auth probe failed').strip()}"
            ),
        }
    return None


def _known_headless_permission_denial(harness_name: str) -> Optional[dict]:
    """Return a known matching permission-denial log id when we have one."""
    get_db = _pkg("_get_db")
    if get_db:
        try:
            conn = get_db()
        except Exception:
            conn = None
        if conn is not None:
            try:
                row = conn.execute(
                    "SELECT job_id, log_path FROM daemon_jobs "
                    "WHERE agent=? AND status='permission_denied' "
                    "ORDER BY completed_at DESC LIMIT 1",
                    (harness_name,),
                ).fetchone()
            except Exception:
                row = None
            finally:
                try:
                    conn.close()
                except Exception:
                    pass
            if row:
                job_id, log_path = row
                if log_path and os.path.exists(log_path):
                    try:
                        with open(log_path) as fh:
                            log_text = fh.read()
                    except OSError:
                        log_text = ""
                    detector = _pkg("_log_has_permission_denied_signature")
                    if detector and detector(log_text):
                        return {
                            "job_id": job_id,
                            "log_path": log_path,
                        }

    load_jobs = _pkg("_load_jobs")
    if not load_jobs:
        return None
    try:
        jobs = load_jobs() or []
    except Exception:
        return None
    for job in reversed(jobs):
        if job.get("agent") != harness_name:
            continue
        log_path = job.get("log_file") or job.get("log_path")
        if not log_path or not os.path.exists(log_path):
            continue
        try:
            with open(log_path) as fh:
                log_text = fh.read()
        except OSError:
            continue
        detector = _pkg("_log_has_permission_denied_signature")
        if detector and detector(log_text):
            return {
                "job_id": job.get("id") or job.get("job_id"),
                "log_path": log_path,
            }
    return None


def _preflight_headless_permission_check(harness_name: str, permissions: list, dispatch_flags: list) -> Optional[dict]:
    """Block known headless permission auto-denials before dispatching."""
    if harness_name != "agy":
        return None

    permissions = permissions or []
    dispatch_flags = dispatch_flags or []
    has_write_or_run = any(not (perm or "").startswith("read:*") for perm in permissions)
    bypass_flag = "--dangerously-skip-permissions" in dispatch_flags
    if has_write_or_run or bypass_flag:
        return None

    known = _known_headless_permission_denial(harness_name)
    if known:
        return {
            "passed": False,
            "sentinel": "HARNESS_PREFLIGHT_FAIL",
            "reason": (
                f"Harness '{harness_name}' would dispatch headless with read-only permissions, "
                f"and prior job {known['job_id']} hit the same auto-denial pattern. "
                "Grant a write/run permission or reroute this work."
            ),
        }

    return {
        "passed": False,
        "sentinel": "HARNESS_PREFLIGHT_FAIL",
        "reason": (
            f"Harness '{harness_name}' would dispatch headless with read-only permissions, "
            "which is a known auto-denial pattern. Grant a write/run permission or reroute this work."
        ),
    }


def _create_job_worktree(job_id: str, agent: str, base: Optional[str] = None) -> dict:
    """Create the isolated git worktree for a dispatched job.

    Returns {"path": str, "branch": str, "base_branch": str, "base_sha": str}
    """
    worktree_path, worktree_branch = _job_worktree_details(job_id, agent)
    os.makedirs(os.path.dirname(worktree_path), exist_ok=True)

    load_config_fn = _pkg("load_config")
    config = load_config_fn() if load_config_fn else {}
    stacking_mode = (config.get("dispatch") or {}).get("stacking", "auto")

    base_ref = _resolve_dispatch_worktree_base_ref(
        os.getcwd(), stacking_mode=stacking_mode, explicit_base=base
    )

    base_sha = None
    if base_ref and base_ref != "HEAD":
        sha_result = subprocess.run(
            ["git", "-C", os.getcwd(), "rev-parse", base_ref],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if sha_result.returncode == 0:
            base_sha = (sha_result.stdout or "").strip()
    # Always log resolved base before worktree create (#832 diagnosability).
    if base_sha:
        print(f"  worktree base resolving against {base_ref} @ {base_sha}")
    else:
        print(f"  worktree base resolving against {base_ref}")

    worktree_cmd = ["git", "worktree", "add", worktree_path, "-b", worktree_branch]
    if base_sha:
        worktree_cmd.append(base_sha)
    elif base_ref and base_ref != "HEAD":
        worktree_cmd.append(base_ref)
    with git_ref_operation_lock(os.getcwd()):
        for attempt in range(1, 4):
            result = subprocess.run(
                worktree_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=os.getcwd(),
            )
            if result.returncode == 0:
                break
            stderr = (result.stderr or "").lower()
            contention = any(
                signature in stderr
                for signature in (
                    "eperm",
                    "operation not permitted",
                    "file exists",
                    "cannot lock ref",
                    "already exists",
                )
            ) or ("unable to create" in stderr and "lock" in stderr)
            if not contention or attempt == 3:
                break
            time.sleep(random.uniform(0.01, 0.05))
    if result.returncode != 0:
        details = "\n".join(
            part for part in [result.stdout.strip(), result.stderr.strip()] if part
        )
        raise RuntimeError(
            f"Failed to create worktree for job {job_id} at {worktree_path} "
            f"on branch {worktree_branch} after 3 attempts."
            + (f" {details}" if details else "")
        )
    _assert_dispatch_worktree_base_is_fresh(worktree_path, base_ref)
    return {
        "path": worktree_path,
        "branch": worktree_branch,
        "base_branch": base_ref,
        "base_sha": base_sha,
    }


def _probe_results_trustworthy() -> bool:
    """Hard gate for TC1-5 trust.

    #578/#580 are still open, so literal probe pass/fail values are not
    # authoritative yet. Flip this to True only when that fix stack lands.
    """
    return False


def _parse_probe_timestamp(last_probe_at: Optional[str]) -> Optional[float]:
    if not last_probe_at:
        return None
    try:
        return time.mktime(time.strptime(last_probe_at, "%Y-%m-%dT%H:%M:%SZ"))
    except (TypeError, ValueError):
        return None


def _normalize_dispatch_requires(requires: Optional[list] = None, requires_gh_write: bool = False) -> list:
    declared = []
    for requirement in list(requires or []):
        if requirement and requirement not in declared:
            declared.append(requirement)
    del requires_gh_write
    return declared


def _capability_block_remediation(agent: str, declared_requires: list) -> str:
    if agent == "agy":
        return "Run `synlynk doctor --fix agy` and review the diff, then rerun dispatch."
    if declared_requires:
        declared = ", ".join(f"`{cap}`" for cap in declared_requires)
        return f"Remove {declared} from `--requires` if the job does not truly need it, or rerun after a fresh probe."
    return f"Run `synlynk probe {agent}` and rerun dispatch."


def _reprobe_harness_sync(agent: str, timeout_s: int = 120) -> dict:
    """Re-run probe in-process via the CLI when the cached probe is stale."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "synlynk", "probe", agent],
            capture_output=True,
            text=True,
            timeout=timeout_s,
            cwd=os.getcwd(),
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {
            "passed": False,
            "timed_out": True,
            "reason": f"Fresh probe for '{agent}' timed out after {timeout_s}s.",
        }
    except Exception as exc:
        return {
            "passed": False,
            "timed_out": False,
            "reason": f"Fresh probe for '{agent}' could not run: {exc}",
        }

    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip() or "probe command failed"
        return {
            "passed": False,
            "timed_out": False,
            "reason": f"Fresh probe for '{agent}' failed: {detail}",
        }

    return {"passed": True, "timed_out": False, "reason": None}


def _dispatch_capability_preflight(
    agent: str,
    task: str,
    *,
    db_conn=None,
    cwd: Optional[str] = None,
    requires: Optional[list] = None,
) -> dict:
    """Preflight the capability gate before dispatch spawns a subprocess."""
    from synlynk.probe import _scan_repo_requirements

    del task
    cwd = cwd or os.getcwd()
    declared_requires = _normalize_dispatch_requires(requires=requires)
    repo_requirements = sorted(_scan_repo_requirements(cwd))

    probe_row = None
    if db_conn is not None:
        try:
            probe_row = db_conn.execute(
                "SELECT compliance_status, last_probe_at FROM harness_records WHERE harness_name=?",
                (agent,),
            ).fetchone()
        except Exception:
            probe_row = None

    probe_status = (probe_row[0] if probe_row else None) or "unknown"
    last_probe_at = probe_row[1] if probe_row else None
    probe_age_seconds = None
    probe_state = "no_coverage"
    trusted = _probe_results_trustworthy()
    if probe_row:
        probe_ts = _parse_probe_timestamp(last_probe_at)
        if probe_ts is not None:
            probe_age_seconds = max(0.0, time.time() - probe_ts)
        if trusted:
            if probe_ts is None:
                probe_state = "no_coverage"
            elif probe_age_seconds is not None and probe_age_seconds > 3600:
                probe_state = "stale"
            elif probe_status not in {"ok", "passed"}:
                probe_state = "failing"
            else:
                probe_state = "covered"
        else:
            probe_state = "no_coverage"

    stale_reprobe = None
    if probe_state == "stale":
        stale_reprobe = _reprobe_harness_sync(agent)
        if not stale_reprobe.get("passed", False):
            return {
                "passed": False,
                "status": "blocked",
                "decision": "block",
                "branch": "stale",
                "reason": stale_reprobe.get("reason") or (
                    f"Cached probe for '{agent}' is stale and a fresh probe failed."
                ),
                "remediation": _capability_block_remediation(agent, declared_requires),
                "probe_trustworthy": trusted,
                "probe_status": probe_status,
                "probe_age_seconds": probe_age_seconds,
                "repo_requirements": repo_requirements,
                "declared_requires": declared_requires,
            }
        probe_state = "covered"

    if probe_state == "failing":
        return {
            "passed": False,
            "status": "blocked",
            "decision": "block",
            "branch": "failing",
            "reason": f"Latest probe for '{agent}' reports compliance_status={probe_status!r}.",
            "remediation": _capability_block_remediation(agent, declared_requires),
            "probe_trustworthy": trusted,
            "probe_status": probe_status,
            "probe_age_seconds": probe_age_seconds,
            "repo_requirements": repo_requirements,
            "declared_requires": declared_requires,
        }

    hard_required = list(declared_requires)
    soft_requirements = [cap for cap in repo_requirements if cap not in hard_required]

    if hard_required and probe_state in {"no_coverage", "stale", "failing"}:
        return {
            "passed": False,
            "status": "blocked",
            "decision": "block",
            "branch": "no-coverage",
            "reason": (
                f"Dispatch for '{agent}' explicitly requires {', '.join(sorted(hard_required))}, "
                "but the current probe state is treated as no-coverage."
            ),
            "remediation": _capability_block_remediation(agent, hard_required),
            "probe_trustworthy": trusted,
            "probe_status": probe_status,
            "probe_age_seconds": probe_age_seconds,
            "repo_requirements": repo_requirements,
            "declared_requires": hard_required,
        }

    if probe_state == "no_coverage" and (soft_requirements or not hard_required):
        reason_bits = []
        if soft_requirements:
            reason_bits.append(
                "repo artifacts present for " + ", ".join(sorted(soft_requirements))
            )
        if not hard_required:
            reason_bits.append("no explicit `--requires` declaration")
        reason = "; ".join(reason_bits) or "no authoritative probe coverage"
        return {
            "passed": True,
            "status": "degraded",
            "decision": "degrade",
            "branch": "no-coverage",
            "reason": reason,
            "remediation": None,
            "probe_trustworthy": trusted,
            "probe_status": probe_status,
            "probe_age_seconds": probe_age_seconds,
            "repo_requirements": repo_requirements,
            "declared_requires": hard_required,
        }

    if soft_requirements:
        return {
            "passed": True,
            "status": "degraded",
            "decision": "degrade",
            "branch": "repo-present",
            "reason": "repo artifacts present: " + ", ".join(sorted(soft_requirements)),
            "remediation": None,
            "probe_trustworthy": trusted,
            "probe_status": probe_status,
            "probe_age_seconds": probe_age_seconds,
            "repo_requirements": repo_requirements,
            "declared_requires": hard_required,
        }

    return {
        "passed": True,
        "status": "ok",
        "decision": "allow",
        "branch": probe_state,
        "reason": None,
        "remediation": None,
        "probe_trustworthy": trusted,
        "probe_status": probe_status,
        "probe_age_seconds": probe_age_seconds,
        "repo_requirements": repo_requirements,
        "declared_requires": hard_required,
        "stale_probe": stale_reprobe,
    }


def _preflight_dispatch(
    harness_name: str,
    dispatch_flags: list,
    db_conn=None,
    _task_hint: str = "",
    permissions: Optional[list] = None,
    force_agent: bool = False,
    root: Optional[str] = None,
    declared_requires: Optional[list] = None,
) -> dict:
    import socket as _socket
    from synlynk._constants import CORE_FLEET as _CORE_FLEET, CORE_INSTRUCTION_FILES as _CORE_INSTRUCTION_FILES
    from synlynk.fleet import repo_has_any_core_instruction_file

    check_root = root or os.getcwd()
    if harness_name in _CORE_FLEET and repo_has_any_core_instruction_file(check_root):
        expected_file = _CORE_INSTRUCTION_FILES.get(harness_name)
        if expected_file and not os.path.exists(os.path.join(check_root, expected_file)):
            if not force_agent:
                return {
                    "passed": False,
                    "sentinel": "INSTRUCTION_FILE_MISSING",
                    "reason": f"Missing instruction file '{expected_file}' for Core 4 agent '{harness_name}' (LIVE-1 / #343 class error). Run synlynk init or pass --force-harness.",
                }

    if harness_name == "agy" and declared_requires:
        req_set = set(declared_requires)
        if "stitch" in req_set or "mcp" in req_set:
            from synlynk.doctor import _run_tc8
            tc8_res = _run_tc8()
            if not tc8_res["passed"]:
                if not force_agent:
                    return {
                        "passed": False,
                        "sentinel": "MCP_SERVER_MISSING",
                        "reason": f"Agy requires Stitch MCP server ({tc8_res['error']}). Run 'synlynk doctor --fix agy' or configure with 'agy mcp add'.",
                    }

    baseline = HARNESS_CAPABILITY_BASELINES.get(harness_name, {})

    if db_conn:
        try:
            _row = db_conn.execute(
                "SELECT installed_version, last_probe_at FROM harness_records WHERE harness_name=?",
                (harness_name,),
            ).fetchone()
        except Exception:
            _row = None
        if _row:
            _recorded_version, _last_probe_at = _row
            _is_stale = True
            if _last_probe_at:
                try:
                    _probe_ts = time.mktime(time.strptime(_last_probe_at, "%Y-%m-%dT%H:%M:%SZ"))
                    _is_stale = (time.time() - _probe_ts) > 3600
                except ValueError:
                    _is_stale = True
            if _is_stale:
                try:
                    _ver_result = subprocess.run(
                        [harness_name, "--version"], capture_output=True, text=True, timeout=3
                    )
                    _live_version = _ver_result.stdout.strip().split()[-1] if _ver_result.stdout.strip() else "unknown"
                    if _live_version != _recorded_version:
                        write_alert = _pkg("_write_sentinel_alert", _write_sentinel_alert)
                        write_alert(
                            "WARNING",
                            "HARNESS_VERSION_DRIFT",
                            f"Harness '{harness_name}' version changed: {_recorded_version} -> {_live_version}. Run synlynk probe to update.",
                        )
                except (FileNotFoundError, subprocess.TimeoutExpired):
                    pass

    flags_spec = baseline.get("dispatch_flags", {})
    invalid_flags = set(flags_spec.get("invalid_flags", [])) if isinstance(flags_spec, dict) else set()
    for flag in dispatch_flags or []:
        f = flag.split("=", 1)[0]
        if f in invalid_flags:
            return {
                "passed": False,
                "sentinel": "HARNESS_PREFLIGHT_FAIL",
                "reason": f"Flag {f!r} is invalid for agent '{harness_name}' (LIVE-1 class error)",
            }

    if isinstance(flags_spec, dict):
        valid_flags = list(flags_spec.get("valid_flags", []))
        required_flags = list(flags_spec.get("required_flags", []))
    else:
        valid_flags, required_flags = [], []
    if valid_flags or required_flags:
        probe_row = None
        if db_conn:
            try:
                probe_row = db_conn.execute(
                    "SELECT compliance_status, active_flags FROM harness_records WHERE harness_name=?",
                    (harness_name,),
                ).fetchone()
            except Exception:
                probe_row = None
        if not probe_row:
            return {
                "passed": False,
                "sentinel": "HARNESS_PREFLIGHT_FAIL",
                "reason": f"no probe data for agent; run synlynk probe {harness_name}",
            }
        compliance_status, _active_flags_json = probe_row
        if compliance_status != "ok":
            return {
                "passed": False,
                "sentinel": "HARNESS_PREFLIGHT_FAIL",
                "reason": (
                    f"TC-2 flag check failed for {harness_name}: probe status is {compliance_status!r}. "
                    f"Run synlynk probe {harness_name} to update."
                ),
            }

    required = baseline.get("network_deps", {}).get("required_endpoints", [])
    for endpoint in required:
        host, _, port_str = endpoint.rpartition(":")
        if not host:
            host = endpoint
        port = int(port_str) if port_str.isdigit() else 443
        try:
            sock = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
            sock.settimeout(2.0)
            sock.connect((host, port))
            sock.close()
        except (OSError, ConnectionRefusedError, _socket.timeout):
            return {
                "passed": False,
                "sentinel": "HARNESS_PREFLIGHT_FAIL",
                "reason": f"Required endpoint {endpoint!r} unreachable for agent '{harness_name}'",
            }

    auth_check = baseline.get("auth_check", {})
    auth_failure = _preflight_auth_check(harness_name, auth_check)
    if auth_failure:
        return auth_failure

    headless_failure = _preflight_headless_permission_check(harness_name, permissions or [], dispatch_flags or [])
    if headless_failure:
        return headless_failure

    if db_conn and _task_hint:
        try:
            from synlynk.status import TIER1_CAPACITY, estimate_dispatch_tokens

            ctx_path = os.path.join(".synlynk", "context.md")
            context_md = ""
            if os.path.exists(ctx_path):
                with open(ctx_path) as f:
                    context_md = f.read()

            est = estimate_dispatch_tokens(_task_hint, context_md, harness_name)
            cap_row = None
            try:
                cap_row = db_conn.execute(
                    "SELECT read_budget_tokens, write_budget_tokens, tool_budget_count "
                    "FROM harness_status WHERE harness_name=?",
                    (harness_name,),
                ).fetchone()
            except Exception:
                cap_row = None

            if cap_row and any(v is not None for v in cap_row):
                read_budget, write_budget, tool_budget = cap_row
            else:
                tier1 = TIER1_CAPACITY.get(harness_name, {})
                read_budget = tier1.get("read_budget_tokens", 999_999)
                write_budget = tier1.get("write_budget_tokens", 32_000)
                tool_budget = tier1.get("tool_budget_count", 200)

            if est["input"] >= (read_budget or 0):
                return {
                    "passed": False,
                    "sentinel": "CAPACITY_EXCEEDED_INPUT",
                    "reason": (
                        f"task needs ~{est['input']:,} input tokens; "
                        f"{harness_name} budget is {(read_budget or 0):,}."
                    ),
                }

            if est["output"] >= (write_budget or 0):
                return {
                    "passed": False,
                    "sentinel": "CAPACITY_EXCEEDED_OUTPUT",
                    "reason": (
                        f"task needs ~{est['output']:,} output tokens; "
                        f"{harness_name} write budget is {(write_budget or 0):,}."
                    ),
                }

            if tool_budget and est["tools"] > tool_budget * 0.7:
                write_alert = _pkg("_write_sentinel_alert", _write_sentinel_alert)
                write_alert(
                    "WARNING",
                    "TOOL_PRESSURE",
                    f"{harness_name} tool budget ~{tool_budget}; estimated usage {est['tools']}",
                )
        except Exception:
            pass

    return {"passed": True, "sentinel": None, "reason": None}


def resolve_dispatch_harness(agent: str, agent_id: str = None, story_id: str = None,
                              force_agent: bool = False, requires_gh_write: bool = False,
                              static_baseline: bool = False, task_domain: str = None,
                              criticality: float = 1.0, lambda_: float = 1.0) -> str:
    """Resolve which harness a dispatch will actually run on.

    Side-effect-free (no subprocess spawn, no DB write) so both the live
    dispatch path and the --dry-run preview path can call it and see the
    same answer. Raises ValueError for an unregistered/disabled agent_id,
    same as the live path always has.
    static_baseline=True bypasses learned capability-score routing entirely
    (both real story_id and synthetic role-dispatch story lookups) and
    forces the deterministic _harness_for_org_role static pick.
    """
    resolved_agent_role = None
    if agent_id:
        from synlynk import agent_store
        entry = next(
            (a for a in agent_store.list_agents() if a["agent_id"] == agent_id), None
        )
        if entry is None:
            raise ValueError(
                f"agent_id {agent_id!r} is unregistered — cannot dispatch. "
                f"Run `synlynk agent list` to see registered agents."
            )
        if entry.get("disabled"):
            raise ValueError(
                f"agent {agent_id!r} is disabled — cannot dispatch. "
                f"Use `synlynk agent show {agent_id}` to check status."
            )
        resolved_agent_role = next(
            (a["value"] for a in entry["aliases"] if a["kind"] == "role_slug"), None
        )

    if force_agent:
        return agent

    baselines_map = _pkg("HARNESS_CAPABILITY_BASELINES", HARNESS_CAPABILITY_BASELINES)
    picked = None
    if task_domain and not static_baseline:
        try:
            from synlynk import _get_db
            conn = _get_db()
            has_evidence = conn.execute(
                "SELECT 1 FROM capability_ledger WHERE task_domain=? LIMIT 1", (task_domain,)
            ).fetchone()
            if has_evidence:
                from synlynk._constants import CORE_FLEET
                candidates = [name for name in baselines_map if name in CORE_FLEET]
                choice = route_expected_value(candidates, task_domain, criticality,
                                               conn=conn, lambda_=lambda_)
                picked = choice["harness"] if choice else None
        except Exception:
            picked = None
    if story_id and not static_baseline and picked is None:
        best_agent = _pkg("_best_agent_for_story")
        if best_agent:
            best = best_agent(story_id)
            if best and best in baselines_map:
                picked = best
    if picked is None and resolved_agent_role and not static_baseline:
        from synlynk._constants import _role_dispatch_story_id

        synthetic_story_id = _role_dispatch_story_id(resolved_agent_role)
        best_agent = _pkg("_best_agent_for_story")
        if best_agent:
            best = best_agent(synthetic_story_id)
            if best and best in baselines_map:
                picked = best
    if picked is None and resolved_agent_role:
        picked = _harness_for_org_role(resolved_agent_role, baselines_map, requires_gh_write)
    return picked or agent


def dispatch_agent(agent: str, task: str, story_id: str = None,
                   agent_id: str = None,
                   force_agent: bool = False,
                   context_mode: str = None,
                   cycle: str = "work",
                   skip_preflight: bool = False,
                   requires_gh_write: bool = False,
                   static_baseline: bool = False,
                   task_type: str = None,
                   requires: list = None,
                   grants: list = None,
                   revokes: list = None,
                   job_id: str = None,
                   issue: int = None,
                   base: str = None,
                   scope_paths: list = None,
                   session_id: str = None,
                   gh_write_target_kind: str = "issue",
                   model: str = None,
                   role: str = None,
                   task_domain: str = None,
                   criticality: float = 1.0,
                   lambda_: float = 1.0,
                   db_conn=None,
                   _startup_failover: bool = True) -> dict:
    if not task or not task.strip():
        raise ValueError(
            "--task is empty or whitespace-only; refusing to dispatch (see #720)"
        )
    if task_type:
        try:
            authority = check_authority(
                f"task_dispatch:{task_type}", role=role or "dev", repo_path=os.getcwd(),
            )
        except ValueError:
            authority = None  # unknown task_type action shape — not a policy-covered task_type, skip gate
        if authority is not None and not authority.allowed:
            raise RuntimeError(
                f"Dispatch refused: task_type {task_type!r} is not an authorized task_type "
                f"for role {role or 'dev'!r} per policy.json (see #423, #569)."
            )
    # Keep the explicit flag as an override, but infer the same safety and
    # identity requirements for obvious GitHub-write task shapes (#659).
    requires_gh_write = bool(
        requires_gh_write or _task_requires_gh_write(task, task_type=task_type)
    )
    agent = resolve_dispatch_harness(
        agent, agent_id=agent_id, story_id=story_id,
        force_agent=force_agent, requires_gh_write=requires_gh_write,
        static_baseline=static_baseline,
        task_domain=task_domain, criticality=criticality, lambda_=lambda_,
    )
    resolved_agent_role = None
    if agent_id:
        from synlynk import agent_store
        entry = next(
            (a for a in agent_store.list_agents() if a["agent_id"] == agent_id), None
        )
        if entry:
            resolved_agent_role = next(
                (a["value"] for a in entry["aliases"] if a["kind"] == "role_slug"), None
            )
    resolved_agent_role = role or resolved_agent_role
    if requires_gh_write and not resolved_agent_role:
        resolved_agent_role = _role_for_story(story_id)
    if requires_gh_write and not resolved_agent_role:
        raise RuntimeError(
            "Dispatch refused: --requires-gh-write requires a resolvable role identity, "
            "but none was provided. Pass --role <role>, or dispatch via --as-agent "
            "<registered-agent-id> or --story <id> with a role-tagged story. Refusing to "
            "silently default to the 'dev' identity for a GitHub-write dispatch "
            "(see #423, #569)."
        )
    if session_id is None:
        from synlynk.session import _read_active_session
        session_id = _read_active_session()
    baselines_map = _pkg("HARNESS_CAPABILITY_BASELINES", HARNESS_CAPABILITY_BASELINES)
    dispatch_time = None
    if not story_id:
        dispatch_time = time.time()
    if requires_gh_write:
        current_baseline = baselines_map.get(agent, {})
        if not current_baseline.get("can_gh_write", False):
            capable_agents = [
                name for name, baseline in baselines_map.items()
                if baseline.get("can_gh_write", False)
            ]
            if not capable_agents:
                raise ValueError(
                    "No agent in HARNESS_CAPABILITY_BASELINES has can_gh_write: True"
                )
            if force_agent:
                print(
                    f"  ⚠ '{agent}' cannot reliably complete GitHub-write actions "
                    f"headless (see #426) — proceeding because --force-agent was set",
                    file=sys.stderr,
                )
            else:
                rerouted_to = capable_agents[0]
                print(
                    f"  ↪ rerouted '{agent}' -> '{rerouted_to}' "
                    f"(--requires-gh-write; '{agent}' cannot do this headless, see #426)"
                )
                agent = rerouted_to

    if requires_gh_write and agent == "agy":
        tc7_result = _run_tc7()
        if not tc7_result["passed"]:
            print(
                "  ✗ TC-7 preflight failed: Agy is missing required gh-write allow-rules: "
                f"{', '.join(tc7_result['missing'])}"
            )
            print(
                "    Configure ~/.gemini/antigravity-cli/settings.json with these allowRules, "
                "or dispatch to a different agent (Codex/Grok)."
            )
            raise SystemExit(1)

    if agent not in baselines_map:
        raise ValueError(f"Unknown agent: '{agent}'. Known: {list(baselines_map)}")

    import hashlib as _hashlib_early
    if not job_id:
        _job_seed = dispatch_time if dispatch_time is not None else time.time()
        job_id = "job-" + _hashlib_early.md5(f"{agent}{task}{_job_seed}".encode()).hexdigest()[:8]

    dconn = db_conn
    owns_dconn = False
    if dconn is None:
        get_db_fn = _pkg("_get_db")
        if get_db_fn:
            dconn = get_db_fn() if callable(get_db_fn) else get_db_fn
            owns_dconn = True
    elif callable(dconn):
        dconn = dconn()
        owns_dconn = True

    if dconn is not None:
        resolve_story_fn = _pkg("resolve_or_create_story_id")
        _est_tokens = None
        if story_id and resolve_story_fn:
            _row = dconn.execute(
                "SELECT estimated_tokens FROM stories WHERE story_id=?", (story_id,)
            ).fetchone()
            if _row and _row[0]:
                _est_tokens = int(_row[0])
        if _est_tokens is None:
            # Ad-hoc call with no story estimate: rough heuristic, ~4 chars/token.
            _est_tokens = max(1000, len(task) // 4)

        quota_status_fn = _pkg("_quota_status_for_agent")
        qstatus = (
            quota_status_fn(dconn, agent, estimated_tokens=_est_tokens)
            if quota_status_fn
            else {"status": "unknown", "degraded": True}
        )

        if qstatus.get("status") == "exhausted":
            reset_at = None
            rows_fn = _pkg("_read_agent_quota_rows")
            if rows_fn:
                for _r in rows_fn(dconn, agent) or []:
                    if _r.get("reset_at"):
                        reset_at = _r["reset_at"]
                        break
            now_iso = time.strftime("%Y-%m-%dT%H:%M:%S")
            existing_job = dconn.execute(
                "SELECT 1 FROM daemon_jobs WHERE job_id=?", (job_id,)
            ).fetchone()
            if existing_job:
                dconn.execute(
                    "UPDATE daemon_jobs SET status='queued', "
                    "blocked_reason='quota_exhausted' WHERE job_id=?",
                    (job_id,),
                )
            else:
                dconn.execute(
                    "INSERT INTO daemon_jobs (job_id, agent, task, story_id, status, "
                    "priority, depends_on, enqueued_at, blocked_reason) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (job_id, agent, task, story_id, "queued", 5, "[]", now_iso,
                     "quota_exhausted"),
                )
            dconn.commit()
            if owns_dconn and dconn is not None:
                try:
                    dconn.close()
                except Exception:
                    pass
            return {
                "deferred": True,
                "reason": qstatus.get("reason", "quota_exhausted"),
                "retry_after": reset_at,
                "job_id": job_id,
            }

        open_reservation_fn = _pkg("_open_reservation")
        has_reservations_table = dconn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='harness_reservations'"
        ).fetchone()
        if open_reservation_fn and has_reservations_table:
            _scope = "plan" if os.environ.get("SYNLYNK_SCHEDULE_RUN_ID") else "session"
            existing_reservation = dconn.execute(
                "SELECT 1 FROM harness_reservations "
                "WHERE status='open' AND job_id=?",
                (job_id,),
            ).fetchone()
            if not existing_reservation:
                open_reservation_fn(
                    dconn,
                    agent,
                    _est_tokens,
                    scope=_scope,
                    scope_id=os.environ.get("SYNLYNK_SCHEDULE_RUN_ID"),
                    job_id=job_id,
                )

    resolve_or_create_story_id = _pkg("resolve_or_create_story_id")
    if resolve_or_create_story_id:
        if story_id:
            story_id = resolve_or_create_story_id(
                task, issue=issue, timestamp=dispatch_time, story_id=story_id
            )
        else:
            story_id = resolve_or_create_story_id(task, issue=issue, timestamp=dispatch_time)

    if agent == "local":
        get_db = _pkg("_get_db")
        conn = get_db() if get_db else None
        if conn is not None:
            try:
                local_config = json.load(open(os.path.join(".agents", "local.json")))
            except (OSError, json.JSONDecodeError):
                local_config = {}
            max_concurrent = local_config.get("max_concurrent", 1)
            if _local_concurrency_exceeded(conn, max_concurrent=max_concurrent):
                raise RuntimeError(
                    f"local agent at max concurrency ({max_concurrent}); "
                    "wait for the running job to finish"
                )

    baselines = baselines_map[agent]
    cli = baselines["cli"]
    flags = baselines["non_interactive_flags"] + _dispatch_flags_for_agent(agent)
    overrides = _load_harness_overrides(agent)
    for key, value in overrides.get("dispatch_flags", {}).items():
        flags = flags + [f"--{key}"] if value in (None, "") else flags + [f"--{key}", str(value)]
    if model:
        flags += ["--model", model]
    load_config = _pkg("load_config")
    cfg = load_config() if load_config else {}
    role_list = (cfg.get("roles", {}) or {}).get(agent, [])
    if task_type == "review":
        role_list = ["review"]
    effective_grants = list(grants or [])
    if requires_gh_write:
        if "run:shell" not in effective_grants:
            effective_grants.append("run:shell")
        if agent == "codex" and _CODEX_NETWORK_PERMISSION not in effective_grants:
            effective_grants.append(_CODEX_NETWORK_PERMISSION)
    permissions = _resolve_dispatch_permissions(
        agent,
        role_list=role_list,
        grants=effective_grants,
        revokes=revokes,
        read_only=task_type == "review",
    )
    if task_type == "review":
        # Keep compatibility with test/integration adapters that implement the
        # historical two-argument translator while using the hardened native
        # translator when available.
        import inspect as _inspect
        if "read_only" in _inspect.signature(_permissions_to_flags).parameters:
            permission_flags = _permissions_to_flags(agent, permissions, read_only=True)
        else:
            permission_flags = _permissions_to_flags(agent, permissions)
    else:
        permission_flags = _permissions_to_flags(agent, permissions)
    if agent == "codex":
        flags = _merge_codex_permission_flags(flags, permission_flags)
    else:
        flags = flags + permission_flags
    if agent == "agy" and permissions:
        perm_lines = "\n".join(f"- {p}" for p in permissions)
        task = f"## Permissions\n{perm_lines}\n\n{task}"
    declared_requires = _normalize_dispatch_requires(requires=requires, requires_gh_write=requires_gh_write)
    if not skip_preflight:
        # Core 4: missing instruction file is a hard preflight fail unless --force-agent
        try:
            from synlynk.fleet import check_core_instruction_files, preflight_blocks_dispatch
            from synlynk._constants import CORE_FLEET as _CORE_FLEET

            if agent in _CORE_FLEET:
                _cwd = os.getcwd()
                _missing = check_core_instruction_files(_cwd, agents=[agent])
                if preflight_blocks_dispatch(
                    agent,
                    missing_instructions=_missing,
                    force_agent=force_agent,
                    root=_cwd,
                ):
                    raise RuntimeError(
                        f"Dispatch blocked — missing instruction file for Core 4 agent "
                        f"'{agent}' (run from repo root or pass --force-agent)"
                    )
                if _missing and force_agent:
                    print(
                        f"  ⚠ missing instruction for '{agent}' — proceeding because "
                        f"--force-agent was set"
                    )
        except RuntimeError:
            raise
        except Exception:
            pass
        capability_gate_fn = _pkg("_dispatch_capability_preflight", _dispatch_capability_preflight)
        capability_gate = capability_gate_fn(
            agent,
            task,
            db_conn=dconn,
            cwd=os.getcwd(),
            requires=declared_requires,
        )
        if not capability_gate.get("passed", False):
            return capability_gate
        if capability_gate.get("status") == "degraded":
            print(f"  ⚠ capability gate degraded: {capability_gate.get('reason')}")
    if not skip_preflight:
        preflight_fn = _pkg("_preflight_dispatch", _preflight_dispatch)
        try:
            preflight = preflight_fn(
                harness_name=agent,
                dispatch_flags=flags,
                db_conn=dconn,
                _task_hint=task,
                permissions=permissions,
                force_agent=force_agent,
                declared_requires=declared_requires,
            )
        except TypeError:
            try:
                preflight = preflight_fn(
                    harness_name=agent,
                    dispatch_flags=flags,
                    db_conn=dconn,
                    _task_hint=task,
                )
            except TypeError:
                try:
                    preflight = preflight_fn(
                        agent_name=agent, dispatch_flags=flags, db_conn=dconn
                    )
                except TypeError:
                    raise
        if isinstance(preflight, dict):
            if not preflight.get("passed", False):
                sentinel_path = os.path.join(".synlynk", "sentinel.md")
                write_alert = _pkg("_write_sentinel_alert", _write_sentinel_alert)
                write_alert("CRITICAL", preflight["sentinel"], preflight["reason"], sentinel_path)
                raise RuntimeError(f"Dispatch blocked — preflight failed: {preflight['reason']}")
        elif preflight:
            sentinel_path = os.path.join(".synlynk", "sentinel.md")
            write_alert = _pkg("_write_sentinel_alert", _write_sentinel_alert)
            write_alert("CRITICAL", "HARNESS_PREFLIGHT_FAIL", str(preflight), sentinel_path)
            raise RuntimeError(f"Dispatch blocked — preflight failed: {preflight}")

    load_profile = _pkg("_load_agent_profile")
    profile = load_profile(agent) if load_profile else {}
    dispatch_mode = (cfg or {}).get("dispatch_mode", "daily-grind") if load_config else "daily-grind"
    if agent == "grok" and profile.get("always_approve_unsupported"):
        flags = [flag for flag in flags if flag != "--always-approve"]
        flags = flags + ["--permission-mode", "bypassPermissions"]
    if agent == "grok":
        flags = flags + ["--output-format", "json"]
    if agent == "claude":
        flags = flags + ["--output-format", "stream-json", "--verbose"]
    if agent == "agy":
        flags = flags + ["--output-format", "json"]
        if "--print-timeout" not in flags:
            flags = flags + ["--print-timeout", "30m0s"]
    if agent == "codex":
        flags = flags + ["--json"]
        if _CODEX_NETWORK_PERMISSION in permissions and not any(
            "network_access=true" in flag for flag in flags
        ):
            flags = flags + _codex_network_flags(read_only=task_type == "review")
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
                capture_output=True,
                text=True,
                cwd=os.getcwd(),
                timeout=5,
            )
            if result.returncode == 0:
                git_common_dir = result.stdout.strip()
                if git_common_dir:
                    flags = flags + ["--add-dir", git_common_dir]
        except Exception:
            pass

    # Baseline, override, permission, and harness-specific sources can each
    # contribute the same boolean flag (notably Grok's --always-approve).
    flags = _deduplicate_boolean_cli_flags(flags)

    probe_model = _pkg("_probe_model_version")
    model_at_dispatch = model or (probe_model(agent, cli) if probe_model else "unknown")
    if context_mode is None:
        context_mode = profile.get("context_mode", "task")
    hint = _context_mode_hint(context_mode, task)
    if hint:
        print(f"    {hint}")

    _unused_path, worktree_branch = _job_worktree_details(job_id, agent)
    worktree_info = _create_job_worktree(job_id, agent, base=base)
    worktree_path = worktree_info["path"]
    base_branch = worktree_info["base_branch"]
    base_sha = worktree_info["base_sha"]
    if agent == "grok" and worktree_path and "--cwd" not in flags:
        flags = flags + ["--cwd", worktree_path]
    if agent == "codex" and worktree_path and "-C" not in flags and "--cd" not in flags:
        flags = flags + ["-C", worktree_path]
    worktree_synlynk_dir = os.path.join(worktree_path, ".synlynk")
    logs_dir = os.path.join(worktree_synlynk_dir, "logs")
    prompts_dir = os.path.join(worktree_synlynk_dir, "prompts")
    contexts_dir = os.path.join(worktree_synlynk_dir, "contexts")
    os.makedirs(logs_dir, exist_ok=True)
    os.makedirs(prompts_dir, exist_ok=True)
    os.makedirs(contexts_dir, exist_ok=True)

    log_file = os.path.abspath(os.path.join(logs_dir, f"{job_id}.log"))
    prompt_file = os.path.abspath(os.path.join(prompts_dir, f"{job_id}.md"))
    context_file = os.path.abspath(os.path.join(contexts_dir, f"{job_id}.md"))

    context_text = ""
    if context_mode != "none":
        if context_mode == "task":
            scope = f"task:{story_id}" if story_id else "task"
        else:
            scope = "full"
        try:
            generate_context = _pkg("generate_context")
            try:
                context_text = generate_context(scope=scope, out_path=context_file, role=resolved_agent_role) or ""
            except TypeError as te:
                if "unexpected keyword argument 'role'" in str(te) or "unexpected keyword argument \"role\"" in str(te):
                    context_text = generate_context(scope=scope, out_path=context_file) or ""
                else:
                    raise
        except Exception:
            pass
    warn_context = _pkg("_warn_context_size", _warn_context_size)
    warn_context(context_text)

    context_max_bytes = profile.get("context_max_bytes")
    if context_max_bytes is not None:
        try:
            context_max_bytes = int(context_max_bytes)
        except (TypeError, ValueError):
            context_max_bytes = None
    if context_max_bytes is not None:
        encoded_context = context_text.encode("utf-8")
        if len(encoded_context) > context_max_bytes:
            context_text = encoded_context[:context_max_bytes].decode("utf-8", errors="ignore")
            print(f"  context truncated to {context_max_bytes}B (agent profile limit)")
    # Bytes after truncation — the payload the agent actually received.
    context_bytes = len(context_text.encode("utf-8")) if context_text else 0

    relevant_files = _pkg("_relevant_files_for_story")
    file_list = relevant_files(story_id) if (story_id and relevant_files) else []
    file_section = ""
    if file_list:
        file_section = "\n\n## Relevant Files\n" + "\n".join(f"- `{f}`" for f in file_list)

    verify_contract = _pkg("_verify_contract_for_story")
    verify_section = verify_contract(story_id, task) if (story_id and verify_contract) else ""

    task_sha256_for_receipt = hashlib.sha256(task.encode("utf-8")).hexdigest()
    from synlynk.instructions import extract_instruction_version, get_instruction_file_for_agent

    instruction_file = get_instruction_file_for_agent(agent)
    expected_instruction_version = None
    if instruction_file:
        instr_path = os.path.join(worktree_path or os.getcwd(), instruction_file)
        if not os.path.exists(instr_path):
            instr_path = os.path.join(os.getcwd(), instruction_file)
        if os.path.exists(instr_path):
            try:
                with open(instr_path, "r", encoding="utf-8") as _f:
                    expected_instruction_version = extract_instruction_version(_f.read())
            except Exception:
                pass

    format_prompt = _pkg("_format_prompt_for_agent", _format_prompt_for_agent)
    try:
        prompt = format_prompt(
            agent,
            context_text,
            story_id or "",
            task,
            file_section,
            verify_section,
            cwd_hint=worktree_path,
            task_sha256=task_sha256_for_receipt,
            instruction_file=instruction_file,
            requires_gh_write=requires_gh_write,
        )
    except TypeError:
        prompt = format_prompt(agent, context_text, story_id or "", task, file_section, verify_section)
    with open(prompt_file, "w") as f:
        f.write(prompt)

    fence_data = None
    load_config_fn = _pkg("load_config")
    fence_config = load_config_fn() if load_config_fn else {}
    from synlynk.fencing import FenceData, is_fenced_command
    from synlynk.status import estimate_dispatch_tokens
    if is_fenced_command("dispatch", fence_config):
        rate_fn = _pkg("_model_rate_for_version")
        if context_mode != "none":
            est = estimate_dispatch_tokens(prompt, context_text, agent)
            in_tok, out_tok = est["input"], est["output"]
            basis = "prompt_estimate"
        else:
            db_conn = _pkg("_get_db")
            conn = db_conn() if db_conn else None
            if conn is not None:
                if story_id:
                    row = conn.execute(
                        "SELECT estimated_tokens FROM stories WHERE story_id=?",
                        (story_id,),
                    ).fetchone()
                    if row and row[0]:
                        total_tokens = int(row[0])
                        half = total_tokens // 2
                        in_tok, out_tok, basis = half, total_tokens - half, "story_estimate"
                    else:
                        discipline = None
                        phase = None
                        row = conn.execute(
                            "SELECT discipline, phase FROM stories WHERE story_id=?",
                            (story_id,),
                        ).fetchone()
                        if row:
                            discipline, phase = row[0], row[1]
                        if discipline and phase:
                            rows = conn.execute(
                                """SELECT cost_entries.input_tokens, cost_entries.output_tokens
                                   FROM cost_entries
                                   JOIN stories ON cost_entries.story_id = stories.story_id
                                   WHERE stories.discipline = ?
                                     AND stories.phase = ?
                                     AND cost_entries.cost_source IN ('actual', 'estimated_token_rate')
                                   ORDER BY cost_entries.id DESC
                                   LIMIT ?""",
                                (discipline, phase, 20),
                            ).fetchall()
                            if len(rows) >= 3:
                                avg_in = sum((row[0] or 0) for row in rows) // len(rows)
                                avg_out = sum((row[1] or 0) for row in rows) // len(rows)
                                in_tok, out_tok, basis = avg_in, avg_out, "historical_avg"
                            else:
                                in_tok, out_tok, basis = 5000, 2000, "fixed_default"
                        else:
                            in_tok, out_tok, basis = 5000, 2000, "fixed_default"
                else:
                    in_tok, out_tok, basis = 5000, 2000, "fixed_default"
            else:
                in_tok, out_tok, basis = 5000, 2000, "fixed_default"
        rates = rate_fn(model_at_dispatch, agent=agent) if rate_fn else {"input": 0.003, "output": 0.015}
        cost_usd = (in_tok / 1000 * rates["input"]) + (out_tok / 1000 * rates["output"])
        fence_data = FenceData(
            command="dispatch",
            kind="estimate",
            in_tokens=in_tok,
            out_tokens=out_tok,
            cost_usd=cost_usd,
            basis=basis,
        )

    import shlex as _shlex
    prompt_file_flag = baselines.get("prompt_file_flag")
    prompt_via_arg = baselines.get("prompt_via_arg", False)
    prompt_flag = baselines.get("prompt_flag")
    if prompt_file_flag:
        cmd_str = " ".join(
            _shlex.quote(c) for c in [cli] + flags + [prompt_file_flag, prompt_file]
        )
        shell_cmd = f"{cmd_str} > {_shlex.quote(log_file)} 2>&1; echo $? > {_shlex.quote(log_file)}.exit"
    elif prompt_via_arg:
        if prompt_flag:
            cmd_str = " ".join(_shlex.quote(c) for c in [cli] + flags + [prompt_flag])
        else:
            cmd_str = " ".join(_shlex.quote(c) for c in [cli] + flags)
        shell_cmd = (
            f"PROMPT=$(cat {_shlex.quote(prompt_file)}); "
            f"{cmd_str} \"$PROMPT\" > {_shlex.quote(log_file)} 2>&1; "
            f"echo $? > {_shlex.quote(log_file)}.exit"
        )
    else:
        cmd_str = " ".join(_shlex.quote(c) for c in [cli] + flags)
        shell_cmd = f"{cmd_str} < {_shlex.quote(prompt_file)} > {_shlex.quote(log_file)} 2>&1; echo $? > {_shlex.quote(log_file)}.exit"

    proc_env = _build_subprocess_env(agent, overrides, requires_gh_write, story_id, agent_role=resolved_agent_role)
    gh_write_target_value = None
    gh_write_author_value = None
    gh_write_expect_value = None
    gh_write_target_number = issue
    resolved_gh_write_target_kind = gh_write_target_kind
    if requires_gh_write and gh_write_target_number is None:
        task_target_match = re.search(
            r"\b(?:pr|pull\s+request)\s*#?\s*(\d+)\b",
            task or "",
            re.IGNORECASE,
        )
        issue_target_match = re.search(
            r"\bissues?\s*#?\s*(\d+)\b",
            task or "",
            re.IGNORECASE,
        )
        if task_target_match:
            resolved_gh_write_target_kind = "pr"
            gh_write_target_number = int(task_target_match.group(1))
        elif issue_target_match:
            resolved_gh_write_target_kind = "issue"
            gh_write_target_number = int(issue_target_match.group(1))
        else:
            print(
                "  ⚠ --requires-gh-write task has no numbered PR/issue target; "
                "falling back to worktree activity verification",
                file=sys.stderr,
            )
    if requires_gh_write and gh_write_target_number is not None:
        target_prefix = "pr" if resolved_gh_write_target_kind == "pr" else "issue"
        gh_write_target_value = f"{target_prefix}:{gh_write_target_number}"
        gh_write_role = resolved_agent_role or _role_for_story(story_id)
        gh_write_author_value = _resolve_dispatch_gh_bot_login(gh_write_role)
        gh_write_expect_value = _gh_write_expectation(task, task_type)
    gh_write_expect_for_job = gh_write_expect_value or "closed"

    proc = subprocess.Popen(
        ["sh", "-c", shell_cmd],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        cwd=worktree_path,
        env=proc_env,
    )

    # A process that has already exited failed during CLI startup (bad flag,
    # missing binary, or sandbox setup). Give the task one deterministic
    # failover before recording a normal running job. Fake processes used by
    # callers/tests may not expose poll(), hence this is deliberately best effort.
    try:
        startup_exit = proc.poll()
    except (AttributeError, OSError):
        startup_exit = None
    if _startup_failover and startup_exit not in (None, 0):
        secondary = _secondary_harness(agent, baselines_map)
        touched = _worktree_files_touched(worktree_path) if worktree_path else []
        if secondary and not touched:
            print(f"  ↪ startup failure on '{agent}' (exit {startup_exit}); failing over to '{secondary}'")
            return dispatch_agent(
                secondary, task, story_id=story_id, agent_id=agent_id,
                force_agent=force_agent, context_mode=context_mode, cycle=cycle,
                skip_preflight=skip_preflight, requires_gh_write=requires_gh_write,
                static_baseline=static_baseline, task_type=task_type, requires=requires,
                grants=grants, revokes=revokes, job_id=job_id, issue=issue, base=base,
                scope_paths=scope_paths, session_id=session_id,
                gh_write_target_kind=gh_write_target_kind, model=model, role=role,
                db_conn=db_conn, _startup_failover=False,
            )

    job = {
        "id": job_id,
        "agent": agent,
        "harness": agent,
        "role": resolved_agent_role or "",
        "agent_role": resolved_agent_role or "",
        "story_id": story_id or "",
        "task": task,
        "cycle": cycle,
        "pid": proc.pid,
        "log_file": log_file,
        "prompt_file": prompt_file,
        "context_file": context_file if context_mode != "none" else "",
        "context_mode": context_mode,
        "context_bytes": context_bytes,
        "worktree_path": worktree_path,
        "worktree_branch": worktree_branch,
        "base_branch": base_branch,
        "base_sha": base_sha,
        "suite_result": None,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "ended_at": None,
        "status": "running",
        "exit_code": None,
        "dispatch_mode": dispatch_mode,
        "dispatch_rework": _pkg("_count_dispatch_rework")(story_id or "") if _pkg("_count_dispatch_rework") else 0,
        "micro_rework": 0,
        "retry_count": 0,
        "model_at_dispatch": model_at_dispatch,
        "fence": fence_data,
        "scope_paths": scope_paths or [],
        "requires_gh_write": requires_gh_write,
        "gh_write_target": gh_write_target_value,
        "gh_write_author": gh_write_author_value,
        "gh_write_expect": gh_write_expect_for_job,
        "task_type": task_type or "",
        "agent_id": agent_id or "",
        "resolved_agent_role": resolved_agent_role or "",
        "instruction_file": instruction_file or "",
        "expected_instruction_version": expected_instruction_version or "",
        "instruction_receipt": None,
        "charter_role": resolved_agent_role or "",
        "charter_revision": _pkg("resolve_role_charter")(role=resolved_agent_role)[2] if (_pkg("resolve_role_charter") and resolved_agent_role) else None,
    }

    load_jobs = _pkg("_load_jobs")
    save_jobs = _pkg("_save_jobs")
    jobs = load_jobs() if load_jobs else []
    jobs.append(job)
    if save_jobs:
        jobs_to_save = []
        for saved_job in jobs:
            if hasattr(saved_job.get("fence"), "__dataclass_fields__"):
                saved_job = dict(saved_job)
                saved_job["fence"] = asdict(saved_job["fence"])
            jobs_to_save.append(saved_job)
        save_jobs(jobs_to_save)

    try:
        if dconn is not None:
            # Tests and older DBs may create daemon_jobs without these columns;
            # ensure before INSERT so dispatch never hard-fails on schema lag.
            _ensure_daemon_job_context_columns(dconn)
            _ensure_daemon_job_session_column(dconn)
            _ensure_daemon_job_agent_id_column(dconn)
            _ensure_daemon_job_gh_write_columns(dconn)
            _ensure_daemon_job_harness_columns(dconn)
            existing = dconn.execute(
                "SELECT 1 FROM daemon_jobs WHERE job_id=?", (job_id,)
            ).fetchone()
            if existing:
                # Preserve priority/depends_on/enqueued_at from the queue row.
                dispatch_context = _dispatch_context()
                dconn.execute(
                    "UPDATE daemon_jobs SET status='running', pid=?, started_at=?, "
                    "log_path=?, agent=?, harness=?, role=?, task=?, story_id=?, "
                    "dispatch_context=COALESCE(dispatch_context, ?), "
                    "context_mode=?, context_bytes=?, "
                    "session_id=COALESCE(session_id, ?), "
                    "agent_id=COALESCE(agent_id, ?), "
                    "gh_write_author=COALESCE(gh_write_author, ?), "
                    "gh_write_expect=COALESCE(gh_write_expect, ?) WHERE job_id=?",
                    (
                        proc.pid,
                        job["started_at"],
                        log_file,
                        agent,
                        agent,
                        resolved_agent_role or None,
                        task,
                        story_id,
                        dispatch_context,
                        context_mode,
                        context_bytes,
                        session_id,
                        agent_id,
                        gh_write_author_value,
                        gh_write_expect_for_job,
                        job_id,
                    ),
                )
            else:
                dispatch_context = _dispatch_context()
                dconn.execute(
                    "INSERT OR REPLACE INTO daemon_jobs "
                    "(job_id, agent, harness, role, task, story_id, status, priority, depends_on, pid, "
                    "enqueued_at, started_at, log_path, dispatch_context, context_mode, context_bytes, session_id, "
                    "agent_id, requires_gh_write, gh_write_target, gh_write_author, gh_write_expect) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        job_id,
                        agent,
                        agent,
                        resolved_agent_role or None,
                        task,
                        story_id,
                        "running",
                        5,
                        "[]",
                        proc.pid,
                        job["started_at"],
                        job["started_at"],
                        log_file,
                        dispatch_context,
                        context_mode,
                        context_bytes,
                        session_id,
                        agent_id,
                        1 if requires_gh_write else 0,
                        gh_write_target_value,
                        gh_write_author_value,
                        gh_write_expect_for_job,
                    ),
                )
            dconn.commit()
    finally:
        if owns_dconn and dconn is not None:
            try:
                dconn.close()
            except Exception:
                pass

    log_telemetry = _pkg("log_telemetry_event")
    if log_telemetry:
        log_telemetry({
            "type": "dispatch",
            "agent": agent,
            "story_id": story_id,
            "job_id": job_id,
            "context_mode": context_mode,
            "context_bytes": context_bytes,
        })
    return job


def exec_command(cmd_args: list, force: bool = False) -> int:
    if not cmd_args:
        print("Error: No command provided to exec.")
        return 1

    generate_context = _pkg("generate_context")
    check_budgets = _pkg("check_budgets")
    set_state = _pkg("set_state")
    check_costs = _pkg("_check_costs_freshness", lambda: None)
    log_telemetry = _pkg("log_telemetry_event")
    check_sentinels = _pkg("check_sentinel_patterns")
    update_costs = _pkg("update_costs")
    extract_tokens = _pkg("extract_tokens")
    extract_model_version = _pkg("extract_model_version")
    model_rate_for_version = _pkg("_model_rate_for_version")
    get_username = _pkg("get_username")
    check_drift = _pkg("_check_instruction_drift", lambda: None)
    watch_daemon_cls = _pkg("WatchDaemon")

    if generate_context:
        generate_context()
    cmd_args = _inject_grok_rules(cmd_args)
    if check_budgets:
        check_budgets()

    check_gate = _pkg("_check_pre_exec_gate", _check_pre_exec_gate)
    run_housekeeping = _pkg("_run_daily_housekeeping", lambda: None)
    if run_housekeeping:
        run_housekeeping()
    if not check_gate(force=force):
        return 1

    if set_state:
        set_state("active")
    print(f"  Executing: {' '.join(cmd_args)}")
    start_time = time.time()
    exit_code = 0
    output_text = ""

    try:
        interactive = _is_interactive(cmd_args)
        if interactive:
            process = subprocess.Popen(cmd_args)
            process.wait()
            exit_code = process.returncode
        else:
            process = subprocess.Popen(
                cmd_args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            buffer: list = []
            stream_meta = {"first_output_at": None, "output_bytes": 0}
            tee_thread = threading.Thread(target=_tee_process, args=(process, buffer, stream_meta))
            tee_thread.start()
            process.wait()
            tee_thread.join()
            exit_code = process.returncode
            output_text = "".join(buffer)
    except FileNotFoundError:
        exit_code = 127
        print(f"  Error: Command '{cmd_args[0]}' not found.")
    except Exception as e:
        exit_code = 1
        print(f"  Error: {e}")
    finally:
        duration = time.time() - start_time
        print(f"\n  ✓ Execution finished in {duration:.2f}s")

        if extract_tokens:
            token_counts = extract_tokens(output_text, agent=cmd_args[0])
            in_tokens, out_tokens = token_counts
            cache_read_tokens = getattr(token_counts, "cache_read_tokens", 0)
            basis = getattr(token_counts, "basis", "none")
        else:
            in_tokens, out_tokens, cache_read_tokens, basis = 0, 0, 0, "none"

        if not _is_interactive(cmd_args):
            model_version = extract_model_version(output_text, agent=cmd_args[0]) if extract_model_version else "unknown"
            if update_costs:
                cmd_label = " ".join(cmd_args)
                if exit_code != 0 and in_tokens == 0 and out_tokens == 0:
                    cmd_label = "[failed job] " + cmd_label
                update_costs(
                    cmd_label,
                    in_tokens,
                    out_tokens,
                    duration,
                    cache_read_tokens=cache_read_tokens,
                    model_version=model_version,
                    agent=cmd_args[0],
                    basis=basis,
                )
            if in_tokens > 0 or out_tokens > 0:
                rates = model_rate_for_version(model_version, agent=cmd_args[0]) if model_rate_for_version else {
                    "input": 0.003,
                    "output": 0.015,
                    "cache_read": 0.0000003,
                }
                est_cost = (
                    (in_tokens / 1000 * rates["input"]) +
                    (out_tokens / 1000 * rates["output"]) +
                    (cache_read_tokens / 1000 * rates["cache_read"])
                )
                load_config_fn = _pkg("load_config")
                fence_config = load_config_fn() if load_config_fn else {}
                if is_fenced_command("exec", fence_config):
                    fence = FenceData(
                        command="exec",
                        kind="actual",
                        in_tokens=in_tokens,
                        out_tokens=out_tokens,
                        cost_usd=est_cost,
                        basis=basis,
                    )
                    print(render_task_fence(fence))
                else:
                    print(f"  ⚡ Tokens: {in_tokens:,} in / {out_tokens:,} out  |  est. ${est_cost:.4f}")
            else:
                print(f"  ⚡ Token count unavailable — logged as estimated_tshirt fallback")
        else:
            print("  ⚡ Token count unavailable (interactive mode)")

        if check_costs:
            check_costs()
        if log_telemetry:
            tool_call_count = _pkg("_count_tool_calls", lambda _text: 0)(output_text)
            output_bytes = 0
            first_output_at = None
            output_velocity_bpm = None
            if not _is_interactive(cmd_args):
                output_bytes = len(output_text.encode("utf-8"))
                if output_text:
                    first_output_at = stream_meta.get("first_output_at") if "stream_meta" in locals() else None
                if duration > 0 and output_bytes > 0:
                    output_velocity_bpm = round(output_bytes / (duration / 60.0), 1)
            log_telemetry({
                "type": "exec",
                "schema_version": 1,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "_ts": time.time(),
                "user": get_username() if get_username else "unknown",
                "command": " ".join(cmd_args),
                "duration": round(duration, 2),
                "exit_code": exit_code,
                "in_tokens": in_tokens,
                "out_tokens": out_tokens,
                "first_output_at": first_output_at,
                "tool_call_count": tool_call_count,
                "rescue_agent": None,
                "output_velocity_bpm": output_velocity_bpm,
            })
            # #291: roll exec usage into harness_quotas so stage-2 headroom is live
            refresh_quotas = _pkg("_refresh_agent_quotas_from_telemetry") or _pkg(
                "refresh_agent_quotas_from_telemetry"
            )
            if refresh_quotas:
                try:
                    refresh_quotas()
                except Exception:
                    pass
        _print_pending_nudges()
        if check_sentinels:
            check_sentinels(output_text=output_text, exit_code=exit_code, cmd=" ".join(cmd_args))
        if check_drift:
            check_drift()
        if watch_daemon_cls is not None:
            daemon = watch_daemon_cls()
            if set_state:
                set_state("watching" if daemon._is_running() else "stopped")

    return exit_code
