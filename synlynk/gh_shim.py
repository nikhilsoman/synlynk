"""Shared ``gh`` guard for interactive and dispatched harness sessions.

The harness markers are set by supported agent CLIs or by synlynk when it
starts a child: ``SYNLYNK_HARNESS``, ``CLAUDECODE``, ``CURSOR_AGENT``,
``CODEX_SANDBOX``, ``GROK_BUILD``, ``ANTIGRAVITY``, and ``GEMINI_CLI``.
``CI`` and ``GITHUB_ACTIONS`` deliberately do not count; CI jobs must keep
using their real or test ``gh`` binary.
"""

from __future__ import annotations

import os
import shlex
import shutil
import stat
import subprocess
import sys
from datetime import datetime, timezone
from typing import Mapping, Optional


HARNESS_ENV_KEYS = (
    "SYNLYNK_HARNESS",
    "CLAUDECODE",
    "CURSOR_AGENT",
    "CODEX_SANDBOX",
    "GROK_BUILD",
    "ANTIGRAVITY",
    "GEMINI_CLI",
)
KNOWN_ROLES = (
    "dev", "qa", "pm", "architect", "tpm", "designer", "marketing", "synlynk-bot",
)
REFUSAL = "synlynk gh refused: use synlynk gh --role <role> -- …; host identity is not used"


def _is_harness_session(env: Optional[Mapping[str, str]] = None) -> bool:
    """Return whether any supported harness marker is set to a non-empty value."""
    values = env if env is not None else os.environ
    return any(values.get(key, "") for key in HARNESS_ENV_KEYS)


def _truthy(value: str) -> bool:
    return (value or "").strip().lower() in ("1", "true", "yes", "on")


def _repo_slug(env: Mapping[str, str]) -> str:
    """Return the repository targeted by a host-auth call, when discoverable."""
    args = list(env.get("SYNLYNK_GH_CALL_ARGS", "").split("\0")) if env.get("SYNLYNK_GH_CALL_ARGS") else []
    if "--repo" in args:
        index = args.index("--repo")
        if index + 1 < len(args):
            return args[index + 1]
    try:
        remote = subprocess.run(
            ["git", "-C", os.getcwd(), "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            check=False,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        remote = ""
    if remote:
        remote = remote.removesuffix(".git")
        if remote.startswith("git@github.com:"):
            return remote.split(":", 1)[1]
        if "github.com/" in remote:
            return remote.split("github.com/", 1)[1]
    return "unknown"


def record_host_auth_gh_call(args: list, *, env: Optional[Mapping[str, str]] = None) -> None:
    """Record an invocation that is proceeding with the host GitHub identity."""
    values = env if env is not None else os.environ
    try:
        from synlynk.sentinel import log_telemetry_event

        log_telemetry_event({
            "type": "gh_host_auth",
            "actor": values.get("GITHUB_ACTOR") or values.get("USER") or values.get("LOGNAME") or "unknown",
            "recorded_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "repo": _repo_slug({**values, "SYNLYNK_GH_CALL_ARGS": "\0".join(str(item) for item in args)}),
            "gh_call": "gh " + shlex.join([str(item) for item in args]),
            "args": [str(item) for item in args],
        })
    except Exception:
        # Auditing must never prevent the explicitly opted-in command from running.
        pass


def _real_gh_path(env: Mapping[str, str], shim_dir: str) -> Optional[str]:
    """Find ``gh`` after removing this shim directory from PATH."""
    entries = env.get("PATH", "").split(os.pathsep)
    shim_real = os.path.realpath(shim_dir)
    real_path = os.pathsep.join(
        entry for entry in entries if os.path.realpath(entry or os.curdir) != shim_real
    )
    return shutil.which("gh", path=real_path)


def write_shim(path: str) -> str:
    """Write an executable wrapper at *path* and return the path."""
    shim_dir = os.path.dirname(os.path.realpath(path))
    package_root = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    script = (
        f"#!{sys.executable}\n"
        "import os\n"
        "import sys\n"
        f"sys.path.insert(0, {package_root!r})\n"
        "from synlynk.gh_shim import main\n"
        "raise SystemExit(main(shim_dir=os.path.dirname(os.path.realpath(__file__))))\n"
    )
    os.makedirs(shim_dir, mode=0o700, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(script)
    os.chmod(path, stat.S_IRWXU)
    return path


def install_shim() -> str:
    shim_dir = os.path.expanduser("~/.synlynk/gh-shim")
    write_shim(os.path.join(shim_dir, "gh"))
    return shim_dir


def shim_env() -> str:
    return f'export PATH="{install_shim()}:$PATH"'


def run_shim(args: list, env: Optional[Mapping[str, str]] = None, shim_dir: Optional[str] = None) -> int:
    child_env = dict(env if env is not None else os.environ)
    current_shim_dir = shim_dir or os.path.dirname(os.path.realpath(sys.argv[0]))
    harness = _is_harness_session(child_env)
    has_token = bool(child_env.get("GH_TOKEN") or child_env.get("GITHUB_TOKEN"))
    role = child_env.get("SYNLYNK_GH_ROLE", "")
    if harness and not has_token and role in KNOWN_ROLES:
        os.execvpe(
            sys.executable,
            [sys.executable, "-m", "synlynk", "gh", "--role", role, "--"] + list(args),
            child_env,
        )
    if harness and not has_token and not _truthy(child_env.get("SYNLYNK_GH_WRITE_ALLOW_HOST_AUTH", "")):
        print(REFUSAL, file=sys.stderr)
        return 1

    real_gh = _real_gh_path(child_env, current_shim_dir)
    if not real_gh:
        print("synlynk gh shim: real gh binary not found on PATH", file=sys.stderr)
        return 127
    if harness and not has_token and _truthy(child_env.get("SYNLYNK_GH_WRITE_ALLOW_HOST_AUTH", "")):
        record_host_auth_gh_call(args, env=child_env)
    os.execvpe(real_gh, [real_gh] + list(args), child_env)
    return 127


def run_gh(args: list, *, env: Optional[Mapping[str, str]] = None, **kwargs):
    """Run an internal ``gh`` call through the harness identity guard.

    Internal Python callers cannot rely on the caller having sourced the shell
    shim.  Apply the same fail-closed rule here, and resolve a marked role to
    its cached App token before invoking the real binary.
    """
    child_env = dict(env if env is not None else os.environ)
    if _is_harness_session(child_env) and not (
        child_env.get("GH_TOKEN") or child_env.get("GITHUB_TOKEN")
    ):
        role = child_env.get("SYNLYNK_GH_ROLE", "")
        token = None
        if role in KNOWN_ROLES:
            try:
                from synlynk.dispatch import _isolated_gh_config_dir, _resolve_dispatch_gh_token
                token = _resolve_dispatch_gh_token(role)
                if token:
                    child_env["GH_TOKEN"] = token
                    child_env["GITHUB_TOKEN"] = token
                    child_env["GH_CONFIG_DIR"] = _isolated_gh_config_dir()
            except Exception:
                token = None
        if not token and not _truthy(child_env.get("SYNLYNK_GH_WRITE_ALLOW_HOST_AUTH", "")):
            return subprocess.CompletedProcess(
                ["gh"] + list(args), 1, "", REFUSAL + "\n"
            )
        if not token:
            record_host_auth_gh_call(args, env=child_env)
    call_kwargs = dict(kwargs)
    call_kwargs["env"] = child_env
    return subprocess.run(["gh"] + list(args), **call_kwargs)


def main(args: Optional[list] = None, shim_dir: Optional[str] = None) -> int:
    return run_shim(list(sys.argv[1:] if args is None else args), shim_dir=shim_dir)


__all__ = ["_is_harness_session", "install_shim", "main", "run_gh", "run_shim", "shim_env", "write_shim"]
